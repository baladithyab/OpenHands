# Monitoring and Alerting Architecture

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Monitoring Stack                          │
├─────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │ Prometheus  │   │  Grafana    │   │ AlertManager │      │
│  │  Operator   │   │  Operator   │   │             │      │
│  └─────────────┘   └─────────────┘   └─────────────┘      │
│                                                            │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │   Loki      │   │   Tempo     │   │  Thanos     │      │
│  │  (Logs)     │   │  (Traces)   │   │ (Metrics)   │      │
│  └─────────────┘   └─────────────┘   └─────────────┘      │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

## Prometheus Operator Configuration

```yaml
# prometheus-operator.yaml
apiVersion: monitoring.coreos.com/v1
kind: Prometheus
metadata:
  name: prometheus
  namespace: monitoring
spec:
  replicas: 2
  serviceMonitorSelector:
    matchLabels:
      team: openhands
  retention: 15d
  storage:
    volumeClaimTemplate:
      spec:
        storageClassName: rook-ceph-block
        resources:
          requests:
            storage: 100Gi
  thanos:
    baseImage: quay.io/thanos/thanos
    version: v0.31.0
    objectStorageConfig:
      key: thanos.yaml
      name: thanos-objstore-config
```

## Service Monitors

### Model Server Monitoring
```yaml
# model-monitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: model-server
  namespace: monitoring
  labels:
    team: openhands
spec:
  selector:
    matchLabels:
      app: model-server
  endpoints:
  - port: metrics
    interval: 15s
    path: /metrics
    metricRelabelings:
    - sourceLabels: [__name__]
      regex: 'inference_latency_.*'
      action: keep
  - port: metrics
    interval: 30s
    path: /metrics/detailed
    metricRelabelings:
    - sourceLabels: [__name__]
      regex: 'model_.*'
      action: keep
```

### OLLAMA Fleet Monitoring
```yaml
# ollama-monitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: ollama-fleet
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: ollama-server
  endpoints:
  - port: metrics
    interval: 15s
    path: /metrics
    metricRelabelings:
    - sourceLabels: [__name__]
      regex: 'ollama_.*'
      action: keep
```

## Alert Rules

```yaml
# alert-rules.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: model-alerts
  namespace: monitoring
spec:
  groups:
  - name: model.rules
    rules:
    - alert: HighInferenceLatency
      expr: |
        rate(inference_latency_seconds_sum[5m]) / 
        rate(inference_latency_seconds_count[5m]) > 0.5
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: High inference latency
        description: "Model {{ $labels.model }} has high latency"

    - alert: HighErrorRate
      expr: |
        sum(rate(inference_errors_total[5m])) /
        sum(rate(inference_requests_total[5m])) > 0.05
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: High error rate
        description: "Error rate is above 5%"

    - alert: LowGPUUtilization
      expr: |
        avg_over_time(nvidia_gpu_duty_cycle[5m]) < 30
      for: 15m
      labels:
        severity: warning
      annotations:
        summary: Low GPU utilization
        description: "GPU utilization is below 30%"

    - alert: HighMemoryUsage
      expr: |
        container_memory_usage_bytes{container!=""} /
        container_spec_memory_limit_bytes{container!=""} * 100 > 85
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: High memory usage
        description: "Container {{ $labels.container }} using > 85% memory"
```

## Grafana Dashboards

### Model Performance Dashboard
```yaml
# model-dashboard.yaml
apiVersion: grafana.integreatly.org/v1alpha1
kind: GrafanaDashboard
metadata:
  name: model-performance
spec:
  json: |
    {
      "annotations": {
        "list": []
      },
      "editable": true,
      "panels": [
        {
          "title": "Inference Latency",
          "type": "graph",
          "datasource": "Prometheus",
          "targets": [
            {
              "expr": "rate(inference_latency_seconds_sum[5m]) / rate(inference_latency_seconds_count[5m])",
              "legendFormat": "{{model}}"
            }
          ]
        },
        {
          "title": "Request Rate",
          "type": "graph",
          "datasource": "Prometheus",
          "targets": [
            {
              "expr": "sum(rate(inference_requests_total[5m])) by (model)",
              "legendFormat": "{{model}}"
            }
          ]
        },
        {
          "title": "Error Rate",
          "type": "graph",
          "datasource": "Prometheus",
          "targets": [
            {
              "expr": "sum(rate(inference_errors_total[5m])) by (model) / sum(rate(inference_requests_total[5m])) by (model)",
              "legendFormat": "{{model}}"
            }
          ]
        }
      ]
    }
```

## Loki Configuration

```yaml
# loki-config.yaml
apiVersion: loki.grafana.com/v1
kind: LokiStack
metadata:
  name: logging
  namespace: monitoring
spec:
  size: 1x.small
  storage:
    schemas:
    - version: v12
      effectiveDate: "2022-06-01"
    secret:
      name: loki-storage-secret
  storageClassName: rook-ceph-block
  targets:
    ruler:
      scalingFactor: 1
```

## Tempo Configuration

```yaml
# tempo-config.yaml
apiVersion: tempo.grafana.com/v1alpha1
kind: TempoStack
metadata:
  name: tracing
  namespace: monitoring
spec:
  storage:
    secret:
      name: tempo-storage-secret
    storageClassName: rook-ceph-block
  template:
    distributor:
      replicas: 2
    ingester:
      replicas: 2
    querier:
      replicas: 2
```

## Alert Manager Configuration

```yaml
# alertmanager-config.yaml
apiVersion: monitoring.coreos.com/v1
kind: Alertmanager
metadata:
  name: main
  namespace: monitoring
spec:
  replicas: 2
  configSecret: alertmanager-config
---
apiVersion: v1
kind: Secret
metadata:
  name: alertmanager-config
  namespace: monitoring
stringData:
  alertmanager.yaml: |
    global:
      resolve_timeout: 5m
      slack_api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'

    route:
      group_by: ['alertname', 'cluster', 'service']
      group_wait: 30s
      group_interval: 5m
      repeat_interval: 4h
      receiver: 'slack-notifications'
      routes:
      - match:
          severity: critical
        receiver: 'pagerduty-critical'
      - match:
          severity: warning
        receiver: 'slack-notifications'

    receivers:
    - name: 'slack-notifications'
      slack_configs:
      - channel: '#alerts'
        send_resolved: true
        title: '[{{ .Status | toUpper }}] {{ .CommonLabels.alertname }}'
        text: >-
          {{ range .Alerts }}
            *Alert:* {{ .Annotations.summary }}
            *Description:* {{ .Annotations.description }}
            *Severity:* {{ .Labels.severity }}
            *Started:* {{ .StartsAt }}
          {{ end }}

    - name: 'pagerduty-critical'
      pagerduty_configs:
      - service_key: YOUR_PAGERDUTY_KEY
        send_resolved: true
```

## Thanos Configuration

```yaml
# thanos-config.yaml
apiVersion: v1
kind: Secret
metadata:
  name: thanos-objstore-config
stringData:
  thanos.yaml: |
    type: s3
    config:
      bucket: openhands-metrics
      endpoint: s3.amazonaws.com
      access_key: YOUR_ACCESS_KEY
      secret_key: YOUR_SECRET_KEY
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: thanos-store-gateway
spec:
  replicas: 2
  selector:
    matchLabels:
      app: thanos-store-gateway
  template:
    spec:
      containers:
      - name: thanos-store-gateway
        image: quay.io/thanos/thanos:v0.31.0
        args:
        - store
        - --objstore.config-file=/etc/thanos/thanos.yaml
        - --data-dir=/var/thanos/store
        volumeMounts:
        - name: thanos-config
          mountPath: /etc/thanos
        - name: data
          mountPath: /var/thanos/store
      volumes:
      - name: thanos-config
        secret:
          secretName: thanos-objstore-config
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: rook-ceph-block
      resources:
        requests:
          storage: 100Gi
```

## Custom Metrics

### Model Server Metrics
```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
INFERENCE_REQUESTS = Counter(
    'inference_requests_total',
    'Total number of inference requests',
    ['model', 'version']
)

INFERENCE_ERRORS = Counter(
    'inference_errors_total',
    'Total number of inference errors',
    ['model', 'version', 'error_type']
)

# Latency metrics
INFERENCE_LATENCY = Histogram(
    'inference_latency_seconds',
    'Time spent processing inference requests',
    ['model', 'version'],
    buckets=[.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0]
)

# Resource metrics
GPU_MEMORY_USAGE = Gauge(
    'gpu_memory_usage_bytes',
    'GPU memory usage in bytes',
    ['gpu_id', 'model']
)

MODEL_MEMORY_USAGE = Gauge(
    'model_memory_usage_bytes',
    'Model memory usage in bytes',
    ['model', 'version']
)

# Cache metrics
CACHE_HITS = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['model', 'version']
)

CACHE_MISSES = Counter(
    'cache_misses_total',
    'Total number of cache misses',
    ['model', 'version']
)
```

### OLLAMA Fleet Metrics
```python
# OLLAMA specific metrics
OLLAMA_QUEUE_SIZE = Gauge(
    'ollama_queue_size',
    'Number of requests in queue',
    ['model', 'instance']
)

OLLAMA_MODEL_LOAD_TIME = Histogram(
    'ollama_model_load_seconds',
    'Time taken to load model',
    ['model', 'version']
)

OLLAMA_MEMORY_USAGE = Gauge(
    'ollama_memory_usage_bytes',
    'Memory usage per OLLAMA instance',
    ['instance', 'model']
)
```

## Implementation Steps

1. Core Monitoring (Week 1)
   - Deploy Prometheus Operator
   - Configure service monitors
   - Set up basic alerts

2. Logging & Tracing (Week 2)
   - Deploy Loki and Tempo
   - Configure log aggregation
   - Set up distributed tracing

3. Visualization (Week 3)
   - Deploy Grafana
   - Create dashboards
   - Configure data sources

4. Advanced Features (Week 4)
   - Deploy Thanos
   - Configure long-term storage
   - Set up cross-cluster monitoring

5. Testing & Tuning (Week 5)
   - Load testing
   - Alert tuning
   - Dashboard optimization