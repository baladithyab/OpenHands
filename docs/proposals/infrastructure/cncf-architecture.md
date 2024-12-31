# CNCF-Based Cloud Native Architecture

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     OpenHands Platform                       │
├──────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐   │
│  │   Cilium    │   │    Istio    │   │    Contour     │   │
│  │  (Network)  │   │  (Service   │   │   (Ingress)    │   │
│  │            │   │   Mesh)     │   │               │   │
│  └─────┬───────┘   └──────┬──────┘   └───────┬─────────┘   │
│        │                  │                   │             │
│  ┌─────┴──────┐   ┌──────┴──────┐   ┌───────┴─────────┐   │
│  │   Linkerd   │   │   Kyverno   │   │     Crossplane  │   │
│  │  (Service   │   │  (Policy)   │   │     (Multi-     │   │
│  │   Mesh)     │   │             │   │      Cloud)     │   │
│  └─────┬──────┘   └──────┬──────┘   └───────┬─────────┘   │
│        │                  │                   │             │
│  ┌─────┴──────┐   ┌──────┴──────┐   ┌───────┴─────────┐   │
│  │    Rook    │   │    KEDA     │   │     Knative     │   │
│  │  (Storage) │   │  (Scaling)  │   │   (Serverless)  │   │
│  └─────┬──────┘   └──────┬──────┘   └───────┬─────────┘   │
│        │                  │                   │             │
│  ┌─────┴──────┐   ┌──────┴──────┐   ┌───────┴─────────┐   │
│  │  OpenTele- │   │ Prometheus  │   │     Grafana     │   │
│  │   metry    │   │ Operator    │   │    Operator     │   │
│  └────────────┘   └─────────────┘   └─────────────────┘   │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Networking & Service Mesh

#### Cilium for Networking
```yaml
# cilium-config.yaml
apiVersion: cilium.io/v1alpha1
kind: CiliumConfig
metadata:
  name: cilium-config
  namespace: kube-system
spec:
  ipam:
    mode: kubernetes
  kubeProxyReplacement: strict
  hubble:
    enabled: true
    metrics:
      enabled:
        - dns:query;ignoreAAAA
        - drop
        - tcp
        - flow
        - icmp
        - http
  loadBalancer:
    algorithm: maglev
    mode: snat
  bandwidthManager:
    enabled: true
```

#### Istio Service Mesh
```yaml
# istio-config.yaml
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
metadata:
  name: istio-control-plane
spec:
  profile: default
  components:
    egressGateways:
    - name: istio-egressgateway
      enabled: true
    ingressGateways:
    - name: istio-ingressgateway
      enabled: true
    pilot:
      enabled: true
  values:
    global:
      proxy:
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 2000m
            memory: 1024Mi
      meshConfig:
        enableTracing: true
        defaultConfig:
          envoyMetricsService:
            address: otel-collector.monitoring:4317
```

### 2. Storage & Data Management

#### Rook-Ceph Cluster
```yaml
# rook-cluster.yaml
apiVersion: ceph.rook.io/v1
kind: CephCluster
metadata:
  name: rook-ceph
  namespace: rook-ceph
spec:
  dataDirHostPath: /var/lib/rook
  mon:
    count: 3
    allowMultiplePerNode: false
  dashboard:
    enabled: true
    ssl: true
  storage:
    useAllNodes: true
    useAllDevices: false
    config:
      osdsPerDevice: "1"
      storeType: bluestore
      databaseSizeMB: "1024"
      journalSizeMB: "1024"
```

#### MinIO Operator (S3-compatible storage)
```yaml
# minio-tenant.yaml
apiVersion: minio.min.io/v2
kind: Tenant
metadata:
  name: minio-tenant
  namespace: minio-operator
spec:
  pools:
    - servers: 4
      volumesPerServer: 4
      volumeClaimTemplate:
        metadata:
          name: data
        spec:
          accessModes:
            - ReadWriteOnce
          resources:
            requests:
              storage: 1Ti
          storageClassName: rook-ceph-block
  credsSecret:
    name: minio-creds-secret
  prometheusOperator: true
  logging:
    audit:
      diskCapacityGB: 10
```

### 3. Autoscaling & Resource Management

#### KEDA Scaler
```yaml
# keda-scaler.yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ollama-scaler
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ollama-deployment
  pollingInterval: 15
  cooldownPeriod: 300
  minReplicaCount: 1
  maxReplicaCount: 10
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus-operated.monitoring.svc:9090
      metricName: http_requests_total
      threshold: '100'
      query: sum(rate(http_requests_total{service="ollama"}[2m]))
```

#### Knative Serving
```yaml
# knative-serving.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ollama-service
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/class: "keda.autoscaling.knative.dev"
        autoscaling.knative.dev/metric: "rps"
        autoscaling.knative.dev/target: "100"
    spec:
      containers:
      - image: ollama/ollama:latest
        resources:
          limits:
            nvidia.com/gpu: 1
        env:
        - name: MODEL_NAME
          value: "llama2"
```

### 4. Observability Stack

#### OpenTelemetry Collector
```yaml
# otel-collector.yaml
apiVersion: opentelemetry.io/v1alpha1
kind: OpenTelemetryCollector
metadata:
  name: otel
spec:
  mode: deployment
  config: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318

    processors:
      batch:
        timeout: 1s
        send_batch_size: 1024

      memory_limiter:
        check_interval: 1s
        limit_mib: 1000

    exporters:
      prometheus:
        endpoint: 0.0.0.0:8889
      
      loki:
        endpoint: http://loki:3100/loki/api/v1/push
        
      jaeger:
        endpoint: jaeger-collector:14250
        tls:
          insecure: true

    service:
      pipelines:
        metrics:
          receivers: [otlp]
          processors: [batch, memory_limiter]
          exporters: [prometheus]
        
        logs:
          receivers: [otlp]
          processors: [batch]
          exporters: [loki]
        
        traces:
          receivers: [otlp]
          processors: [batch]
          exporters: [jaeger]
```

### 5. Policy Management

#### Kyverno Policies
```yaml
# kyverno-policies.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-gpu-limits
spec:
  validationFailureAction: enforce
  rules:
  - name: check-gpu-limits
    match:
      resources:
        kinds:
        - Pod
    validate:
      message: "GPU limits are required for model pods"
      pattern:
        spec:
          containers:
          - resources:
              limits:
                nvidia.com/gpu: "?*"
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-storage-quota
spec:
  validationFailureAction: enforce
  rules:
  - name: check-storage-quota
    match:
      resources:
        kinds:
        - PersistentVolumeClaim
    validate:
      message: "Storage requests must be within quota"
      pattern:
        spec:
          resources:
            requests:
              storage: "<= 100Gi"
```

### 6. OLLAMA Fleet Management

#### Custom Resource Definition
```yaml
# ollama-fleet-crd.yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: ollamafleets.openhands.ai
spec:
  group: openhands.ai
  names:
    kind: OllamaFleet
    plural: ollamafleets
    singular: ollamafleet
    shortNames:
      - of
  scope: Namespaced
  versions:
    - name: v1alpha1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              required: ["model"]
              properties:
                model:
                  type: string
                replicas:
                  type: integer
                  minimum: 1
                resources:
                  type: object
                  properties:
                    gpu:
                      type: boolean
                    memory:
                      type: string
                    cpu:
                      type: string
                storage:
                  type: object
                  properties:
                    size:
                      type: string
                    class:
                      type: string
                scaling:
                  type: object
                  properties:
                    minReplicas:
                      type: integer
                    maxReplicas:
                      type: integer
                    metrics:
                      type: array
                      items:
                        type: object
```

#### OLLAMA Operator
```yaml
# ollama-operator.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama-operator
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ollama-operator
  template:
    metadata:
      labels:
        app: ollama-operator
    spec:
      serviceAccountName: ollama-operator
      containers:
      - name: operator
        image: openhands/ollama-operator:latest
        env:
        - name: WATCH_NAMESPACE
          valueFrom:
            fieldRef:
              fieldPath: metadata.namespace
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: OPERATOR_NAME
          value: "ollama-operator"
```

## CNCF Project Benefits

1. Networking & Service Mesh
- Cilium: eBPF-based networking
- Istio/Linkerd: Service mesh capabilities
- Contour: Ingress controller

2. Storage & Data
- Rook: Cloud-native storage orchestration
- MinIO: S3-compatible object storage
- Longhorn: Distributed block storage

3. Observability
- OpenTelemetry: Unified observability
- Prometheus: Metrics and monitoring
- Grafana: Visualization
- Jaeger: Distributed tracing

4. Scaling & Management
- KEDA: Event-driven autoscaling
- Knative: Serverless capabilities
- Kyverno: Policy management

## Implementation Strategy

1. Core Infrastructure (Week 1-2)
- Deploy Cilium networking
- Configure service mesh
- Set up storage with Rook

2. Observability (Week 2-3)
- Deploy OpenTelemetry
- Configure monitoring stack
- Set up dashboards

3. OLLAMA Integration (Week 3-4)
- Deploy OLLAMA operator
- Configure autoscaling
- Set up policies

4. Testing & Optimization (Week 4-5)
- Load testing
- Performance tuning
- Security hardening

## Advantages

1. Standardization
- CNCF-backed projects
- Active communities
- Enterprise support available

2. Interoperability
- Standard interfaces
- Cloud-native patterns
- Easy integration

3. Scalability
- Native Kubernetes integration
- Event-driven scaling
- Resource optimization

4. Observability
- Unified telemetry
- Distributed tracing
- Metrics aggregation

## Recommendations

1. Development Environment
- Use Linkerd (simpler than Istio)
- Use Longhorn (easier than Rook)
- Use K3s for lightweight clusters

2. Production Environment
- Use Cilium + Istio
- Use Rook-Ceph
- Use full observability stack

3. Multi-Cloud
- Use Crossplane
- Use cloud-agnostic storage
- Use unified observability