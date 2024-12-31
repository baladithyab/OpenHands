# Runtime Container Architecture

## Overview

This proposal outlines the container runtime architecture for OpenHands, focusing on efficient model serving, OLLAMA integration, and resource optimization.

```
┌──────────────────────────────────────────────────────────────┐
│                   Container Runtime Stack                     │
├──────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐   │
│  │  Containerd │   │   NVIDIA    │   │    CRI-O        │   │
│  │  Runtime    │   │   Container │   │    Runtime      │   │
│  └──────┬──────┘   └──────┬──────┘   └───────┬─────────┘   │
│         │                 │                   │             │
│  ┌──────┴──────┐   ┌─────┴─────┐   ┌────────┴──────────┐  │
│  │   OLLAMA    │   │  Model     │   │     API           │  │
│  │   Fleet     │   │  Server    │   │     Server        │  │
│  └──────┬──────┘   └─────┬─────┘   └────────┬──────────┘  │
│         │                 │                   │             │
│  ┌──────┴──────┐   ┌─────┴─────┐   ┌────────┴──────────┐  │
│  │  Shared     │   │  Cache     │   │     Metrics       │  │
│  │  Storage    │   │  Layer     │   │     Exporter      │  │
│  └─────────────┘   └───────────┘   └─────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Container Components

### 1. Base Images

```dockerfile
# Base CUDA Image
FROM nvidia/cuda:12.3.1-runtime-ubuntu22.04 as cuda-base
RUN apt-get update && apt-get install -y --no-install-recommends \
    cuda-toolkit-12-3 \
    && rm -rf /var/lib/apt/lists/*

# Base Python Image
FROM python:3.12-slim as python-base
RUN pip install --no-cache-dir \
    torch \
    transformers \
    accelerate

# Base OLLAMA Image
FROM ollama/ollama:latest as ollama-base
```

### 2. Model Server Container

```dockerfile
FROM cuda-base as model-server

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy model server code
COPY ./model_server /app/model_server

# Set up model cache directory
VOLUME /cache
ENV MODEL_CACHE_DIR=/cache

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["python", "/app/model_server/main.py"]
```

### 3. OLLAMA Fleet Configuration

```yaml
# ollama-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: ollama-fleet
spec:
  serviceName: ollama
  replicas: 3
  selector:
    matchLabels:
      app: ollama
  template:
    spec:
      containers:
      - name: ollama
        image: ollama-custom:latest
        resources:
          limits:
            nvidia.com/gpu: 1
        volumeMounts:
        - name: models
          mountPath: /root/.ollama
        - name: shared-cache
          mountPath: /cache
  volumeClaimTemplates:
  - metadata:
      name: models
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: local-nvme
      resources:
        requests:
          storage: 100Gi
```

## Storage Architecture

### 1. Local Cache Layer

```yaml
# local-cache.yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: local-nvme
provisioner: kubernetes.io/no-provisioner
volumeBindingMode: WaitForFirstConsumer
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: nvme-cache-1
spec:
  capacity:
    storage: 100Gi
  volumeMode: Filesystem
  accessModes:
  - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: local-nvme
  local:
    path: /mnt/nvme/cache-1
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - gpu-node-1
```

### 2. Shared Storage Layer

```yaml
# shared-storage.yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: shared-models
provisioner: kubernetes.io/nfs
parameters:
  server: nfs.example.com
  path: /exports/models
  readOnly: "false"
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: shared-models
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: shared-models
  resources:
    requests:
      storage: 1Ti
```

## Resource Management

### 1. GPU Allocation

```yaml
# gpu-policy.yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: gpu-priority
value: 1000000
globalDefault: false
description: "Priority class for GPU workloads"
---
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: nvidia
handler: nvidia
scheduling:
  nodeSelector:
    nvidia.com/gpu: "present"
```

### 2. Resource Quotas

```yaml
# resource-quotas.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: gpu-quota
spec:
  hard:
    requests.nvidia.com/gpu: 8
    limits.nvidia.com/gpu: 8
---
apiVersion: v1
kind: LimitRange
metadata:
  name: gpu-limits
spec:
  limits:
  - type: Container
    defaultRequest:
      nvidia.com/gpu: "1"
    default:
      nvidia.com/gpu: "1"
```

## Performance Optimizations

### 1. Cache Configuration

```yaml
# cache-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cache-config
data:
  cache.conf: |
    max_size = "50GB"
    eviction_policy = "lru"
    compression = true
    shared_cache = true
    cache_dir = "/cache"
    metrics_enabled = true
```

### 2. Network Optimization

```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: model-server-policy
spec:
  podSelector:
    matchLabels:
      app: model-server
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: api-server
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: cache-server
    ports:
    - protocol: TCP
      port: 6379
```

## Implementation Strategy

### Phase 1: Base Infrastructure (Week 1-2)
1. Set up container runtimes
2. Configure GPU support
3. Implement storage classes
4. Deploy monitoring

### Phase 2: OLLAMA Integration (Week 3-4)
1. Deploy OLLAMA fleet
2. Configure model sharing
3. Set up caching
4. Implement scaling

### Phase 3: Optimization (Week 5-6)
1. Performance tuning
2. Resource optimization
3. Network policies
4. Security hardening

## Best Practices

1. Container Security:
- Use minimal base images
- Regular security scans
- Proper privilege management
- Image signing

2. Resource Management:
- GPU sharing optimization
- Memory limits
- Cache size management
- Network policies

3. Storage:
- Local NVMe for hot cache
- Shared storage for models
- Backup strategies
- Data persistence

4. Monitoring:
- Container metrics
- GPU utilization
- Cache hit rates
- Network performance

## Recommendations

1. Development Environment:
- Use local storage
- Minimal replication
- Debug-friendly configs
- Fast iteration

2. Production Environment:
- High availability
- Resource quotas
- Security policies
- Performance monitoring

3. GPU Utilization:
- Fractional allocation
- Time-sharing
- Priority classes
- Resource limits

4. Storage Strategy:
- Tiered storage
- Cache optimization
- Data locality
- Backup procedures

## Next Steps

1. Infrastructure Setup:
- Container runtime installation
- GPU driver configuration
- Storage provisioning
- Network setup

2. OLLAMA Deployment:
- Custom image building
- Fleet management
- Cache configuration
- Scaling setup

3. Performance Tuning:
- Resource optimization
- Cache tuning
- Network optimization
- Monitoring setup

4. Documentation:
- Setup guides
- Best practices
- Troubleshooting
- Maintenance procedures