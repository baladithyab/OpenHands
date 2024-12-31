# Cross-Cloud Deployment with Crossplane

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Management Cluster                       │
├─────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │ Crossplane  │   │   ArgoCD    │   │  Prometheus │      │
│  │  Provider   │   │             │   │  Operator   │      │
│  └─────────────┘   └─────────────┘   └─────────────┘      │
│                                                            │
└────────────┬────────────────┬────────────────┬────────────┘
             │                │                │
    ┌────────┴───────┐ ┌─────┴──────┐  ┌──────┴─────┐
    │   AWS EKS      │ │ Azure AKS  │  │ GCP GKE    │
    │   Cluster      │ │  Cluster   │  │  Cluster   │
    └────────────────┘ └────────────┘  └────────────┘
```

## Crossplane Installation

```yaml
# crossplane-config.yaml
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-aws
spec:
  package: crossplane/provider-aws:v1.14.1
---
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-azure
spec:
  package: crossplane/provider-azure:v1.14.0
---
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-gcp
spec:
  package: crossplane/provider-gcp:v1.14.0
```

## Cloud Provider Configurations

### AWS Configuration
```yaml
# aws-provider-config.yaml
apiVersion: aws.crossplane.io/v1beta1
kind: ProviderConfig
metadata:
  name: aws-provider-config
spec:
  credentials:
    source: Secret
    secretRef:
      namespace: crossplane-system
      name: aws-creds
      key: credentials
---
apiVersion: eks.aws.crossplane.io/v1beta1
kind: Cluster
metadata:
  name: openhands-eks
spec:
  forProvider:
    region: us-west-2
    version: "1.28"
    roleArnRef:
      name: eks-cluster-role
    resourcesVpcConfig:
      subnetIds:
        - subnet-1
        - subnet-2
      endpointPrivateAccess: true
      endpointPublicAccess: true
```

### Azure Configuration
```yaml
# azure-provider-config.yaml
apiVersion: azure.crossplane.io/v1beta1
kind: ProviderConfig
metadata:
  name: azure-provider-config
spec:
  credentials:
    source: Secret
    secretRef:
      namespace: crossplane-system
      name: azure-creds
      key: credentials
---
apiVersion: compute.azure.crossplane.io/v1beta1
kind: AKSCluster
metadata:
  name: openhands-aks
spec:
  forProvider:
    location: westus2
    version: "1.28.0"
    nodeResourceGroup: openhands-nodes
    networkProfile:
      networkPlugin: azure
    defaultNodePool:
      name: default
      nodeCount: 3
      vmSize: Standard_DS2_v2
```

### GCP Configuration
```yaml
# gcp-provider-config.yaml
apiVersion: gcp.crossplane.io/v1beta1
kind: ProviderConfig
metadata:
  name: gcp-provider-config
spec:
  credentials:
    source: Secret
    secretRef:
      namespace: crossplane-system
      name: gcp-creds
      key: credentials
---
apiVersion: container.gcp.crossplane.io/v1beta1
kind: GKECluster
metadata:
  name: openhands-gke
spec:
  forProvider:
    location: us-west1
    initialClusterVersion: "1.28"
    network: default
    subnetwork: default
    ipAllocationPolicy:
      useIpAliases: true
```

## Composition for Model Serving Infrastructure

```yaml
# model-infra-composition.yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: model-infrastructure
spec:
  compositeTypeRef:
    apiVersion: openhands.ai/v1alpha1
    kind: ModelInfrastructure
  resources:
    - base:
        apiVersion: compute.crossplane.io/v1alpha1
        kind: KubernetesCluster
        spec:
          parameters:
            size: large
            region: ${region}
      patches:
        - fromFieldPath: spec.provider
          toFieldPath: spec.providerConfigRef.name
    - base:
        apiVersion: storage.crossplane.io/v1alpha1
        kind: FileSystem
        spec:
          parameters:
            type: ${storageType}
            size: 1Ti
      patches:
        - fromFieldPath: spec.provider
          toFieldPath: spec.providerConfigRef.name
```

## Cloud-Native Storage Solutions

### 1. Rook-Ceph Distributed Storage
```yaml
# rook-ceph-cluster.yaml
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
  storage:
    useAllNodes: true
    useAllDevices: false
    config:
      databaseSizeMB: "1024"
      journalSizeMB: "1024"
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: rook-ceph-block
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  clusterID: rook-ceph
  pool: replicapool
  imageFormat: "2"
  imageFeatures: layering
  csi.storage.k8s.io/provisioner-secret-name: rook-csi-rbd-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: rook-ceph
  csi.storage.k8s.io/controller-expand-secret-name: rook-csi-rbd-provisioner
  csi.storage.k8s.io/controller-expand-secret-namespace: rook-ceph
  csi.storage.k8s.io/node-stage-secret-name: rook-csi-rbd-node
  csi.storage.k8s.io/node-stage-secret-namespace: rook-ceph
  csi.storage.k8s.io/fstype: ext4
```

### 2. Longhorn Distributed Storage
```yaml
# longhorn-storage.yaml
apiVersion: longhorn.io/v1beta2
kind: Setting
metadata:
  name: default-setting
  namespace: longhorn-system
spec:
  defaultSettings:
    backupTarget: s3://openhands-backup/
    backupTargetCredentialSecret: aws-s3-secret
    createDefaultDiskLabeledNodes: true
    defaultDataPath: /var/lib/longhorn/
    replicaAutoBalance: best-effort
    storageOverProvisioningPercentage: 200
    storageMinimalAvailablePercentage: 10
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: longhorn
provisioner: driver.longhorn.io
allowVolumeExpansion: true
parameters:
  numberOfReplicas: "3"
  staleReplicaTimeout: "30"
  fromBackup: ""
```

### 3. Cloud Provider Native Storage

#### AWS EFS
```yaml
# aws-efs.yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: efs-sc
provisioner: efs.csi.aws.com
parameters:
  provisioningMode: efs-ap
  fileSystemId: fs-1234567
  directoryPerms: "700"
  gidRangeStart: "1000"
  gidRangeEnd: "2000"
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: model-storage
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: efs-sc
  resources:
    requests:
      storage: 100Gi
```

#### Azure Files
```yaml
# azure-files.yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: azurefile-premium
provisioner: file.csi.azure.com
allowVolumeExpansion: true
parameters:
  skuName: Premium_LRS
mountOptions:
  - dir_mode=0777
  - file_mode=0777
  - uid=0
  - gid=0
  - mfsymlinks
  - cache=strict
```

#### Google Cloud Filestore
```yaml
# gcp-filestore.yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: filestore-premium
provisioner: filestore.csi.storage.gke.io
parameters:
  tier: premium
  network: default
allowVolumeExpansion: true
```

## OLLAMA Fleet Management

### 1. OLLAMA Custom Resource Definition
```yaml
# ollama-crd.yaml
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
```

### 2. OLLAMA Fleet Operator
```yaml
# ollama-operator.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama-operator
  namespace: openhands-system
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
```

### 3. OLLAMA Fleet Example
```yaml
# ollama-fleet.yaml
apiVersion: openhands.ai/v1alpha1
kind: OllamaFleet
metadata:
  name: llama2-fleet
spec:
  model: llama2
  replicas: 3
  resources:
    gpu: true
    memory: "16Gi"
    cpu: "4"
  storage:
    size: "100Gi"
    class: "rook-ceph-block"
  scaling:
    minReplicas: 1
    maxReplicas: 5
    targetCPUUtilization: 70
    targetMemoryUtilization: 80
  monitoring:
    enabled: true
    scrapeInterval: "30s"
```

## Storage Comparison

| Feature | Rook-Ceph | Longhorn | Cloud Native (EFS/Files/Filestore) |
|---------|-----------|----------|-----------------------------------|
| Performance | High | Medium | Medium-High |
| Scalability | Excellent | Good | Excellent |
| Complexity | High | Low | Low |
| Cost | Low | Low | Medium-High |
| Cross-Cloud | Yes | Yes | No |
| Data Locality | Yes | Yes | Limited |
| Backup/DR | Built-in | Built-in | Provider-specific |

## Recommendations

1. Development/Testing:
   - Use Longhorn for simplicity
   - Good performance and features
   - Easy to manage

2. Production/Scale:
   - Use Rook-Ceph for high performance
   - Better control over data placement
   - More advanced features

3. Hybrid/Multi-Cloud:
   - Use cloud provider storage in single-cloud
   - Use Rook-Ceph for multi-cloud
   - Consider data locality requirements

4. OLLAMA Deployment:
   - Use node affinity for GPU nodes
   - Implement auto-scaling based on load
   - Use distributed storage for model files

## Implementation Steps

1. Storage Layer (Week 1-2)
   - Deploy chosen storage solution
   - Configure replication and backup
   - Test performance and failover

2. OLLAMA Infrastructure (Week 2-3)
   - Deploy OLLAMA operator
   - Configure model storage
   - Set up auto-scaling

3. Cross-Cloud Setup (Week 3-4)
   - Deploy Crossplane
   - Configure cloud providers
   - Test cross-cloud operations

4. Monitoring and Management (Week 4-5)
   - Set up monitoring stack
   - Configure alerts
   - Implement backup procedures