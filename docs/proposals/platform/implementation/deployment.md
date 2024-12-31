# OpenHands Kubernetes Deployment Architecture

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                               │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────┐    ┌──────────────────────────────┐    │
│ │      Route 53       │    │         AWS WAF              │    │
│ │   (DNS + Routing)   │    │    (Security + Filtering)    │    │
│ └──────────┬──────────┘    └─────────────┬────────────────┘    │
│            │                             │                      │
│ ┌──────────┴─────────────────────────────┴──────────────────┐  │
│ │                    Application Load Balancer               │  │
│ └──────────────────────────────┬───────────────────────────┬┘  │
│                                │                           │    │
│ ┌──────────────────────────────┴───────────────────────────┴┐  │
│ │                        Amazon EKS                         │  │
│ │  ┌─────────────────┐    ┌─────────────────┐             │  │
│ │  │   Node Group 1  │    │   Node Group 2  │     ...     │  │
│ │  │  (On-Demand)    │    │     (Spot)      │             │  │
│ │  └─────────────────┘    └─────────────────┘             │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                               │
│ ┌──────────────────┐    ┌──────────────────┐                 │
│ │   Amazon ECR     │    │   AWS Secrets    │                 │
│ │  (Container      │    │    Manager       │                 │
│ │   Registry)      │    │                  │                 │
│ └──────────────────┘    └──────────────────┘                 │
│                                                               │
│ ┌──────────────────┐    ┌──────────────────┐                 │
│ │   Amazon S3      │    │   DynamoDB       │                 │
│ │  (Storage)       │    │   (State)        │                 │
│ └──────────────────┘    └──────────────────┘                 │
└───────────────────────────────────────────────────────────────┘
```

## Kubernetes Components

### 1. Core Services

```yaml
# core-services.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: openhands-system
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: openhands-controller
  namespace: openhands-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: openhands-controller
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "configmaps", "secrets"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
  - apiGroups: ["autoscaling"]
    resources: ["horizontalpodautoscalers"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

### 2. Model Serving

```yaml
# model-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-server
  namespace: openhands-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: model-server
  template:
    metadata:
      labels:
        app: model-server
    spec:
      containers:
      - name: model-server
        image: openhands/model-server:latest
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"
            nvidia.com/gpu: "1"
        env:
        - name: MODEL_CACHE_SIZE
          value: "2048"
        - name: MAX_BATCH_SIZE
          value: "32"
        volumeMounts:
        - name: model-cache
          mountPath: /cache
      volumes:
      - name: model-cache
        emptyDir: {}
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: model-server-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: model-server
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
```

### 3. API Gateway

```yaml
# api-gateway.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: openhands-ingress
  annotations:
    kubernetes.io/ingress.class: "alb"
    alb.ingress.kubernetes.io/scheme: "internet-facing"
    alb.ingress.kubernetes.io/target-type: "ip"
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'
    alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:region:account:certificate/certificate-id"
spec:
  rules:
  - host: api.openhands.dev
    http:
      paths:
      - path: /v1
        pathType: Prefix
        backend:
          service:
            name: api-gateway
            port:
              number: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
      - name: api-gateway
        image: openhands/api-gateway:latest
        ports:
        - containerPort: 80
        env:
        - name: MODEL_SERVICE_URL
          value: "http://model-server:8080"
        - name: ENABLE_CACHING
          value: "true"
        - name: RATE_LIMIT
          value: "100"
```

### 4. Monitoring Stack

```yaml
# monitoring.yaml
apiVersion: monitoring.coreos.com/v1
kind: Prometheus
metadata:
  name: prometheus
  namespace: monitoring
spec:
  serviceAccountName: prometheus
  serviceMonitorSelector:
    matchLabels:
      team: openhands
  resources:
    requests:
      memory: 400Mi
  enableAdminAPI: false
---
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
---
apiVersion: grafana.integreatly.org/v1alpha1
kind: Grafana
metadata:
  name: grafana
  namespace: monitoring
spec:
  deployment:
    spec:
      template:
        spec:
          containers:
          - name: grafana
            image: grafana/grafana:latest
```

## Terraform Infrastructure

```hcl
# main.tf
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = "openhands-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["us-west-2a", "us-west-2b", "us-west-2c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = false
}

module "eks" {
  source = "terraform-aws-modules/eks/aws"

  cluster_name    = "openhands-cluster"
  cluster_version = "1.28"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    general = {
      desired_size = 2
      min_size     = 1
      max_size     = 10

      instance_types = ["m5.large"]
      capacity_type  = "ON_DEMAND"
    }

    compute = {
      desired_size = 1
      min_size     = 0
      max_size     = 10

      instance_types = ["g4dn.xlarge"]
      capacity_type  = "SPOT"

      labels = {
        workload = "gpu"
      }

      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
  }
}

module "load_balancer_controller" {
  source = "terraform-aws-modules/eks/aws//modules/aws-load-balancer-controller"

  cluster_name = module.eks.cluster_name

  enable_cross_zone_load_balancing = true
  enable_deletion_protection       = true
}
```

## Deployment Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy to EKS
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v1
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-west-2

    - name: Login to Amazon ECR
      id: login-ecr
      uses: aws-actions/amazon-ecr-login@v1

    - name: Build and push Docker images
      env:
        ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
      run: |
        docker build -t $ECR_REGISTRY/openhands/model-server:$GITHUB_SHA ./model-server
        docker build -t $ECR_REGISTRY/openhands/api-gateway:$GITHUB_SHA ./api-gateway
        docker push $ECR_REGISTRY/openhands/model-server:$GITHUB_SHA
        docker push $ECR_REGISTRY/openhands/api-gateway:$GITHUB_SHA

    - name: Update kube config
      run: aws eks update-kubeconfig --name openhands-cluster --region us-west-2

    - name: Deploy to EKS
      run: |
        # Update image tags
        kustomize edit set image model-server=$ECR_REGISTRY/openhands/model-server:$GITHUB_SHA
        kustomize edit set image api-gateway=$ECR_REGISTRY/openhands/api-gateway:$GITHUB_SHA
        
        # Apply configurations
        kubectl apply -k ./k8s/overlays/production
```

## Scaling and High Availability

### Node Group Configuration
```hcl
# node_groups.tf
resource "aws_eks_node_group" "on_demand" {
  cluster_name    = module.eks.cluster_name
  node_group_name = "on-demand"
  node_role_arn   = aws_iam_role.eks_node_group.arn
  subnet_ids      = module.vpc.private_subnets

  scaling_config {
    desired_size = 2
    max_size     = 10
    min_size     = 1
  }

  instance_types = ["m5.large"]
  capacity_type  = "ON_DEMAND"

  labels = {
    workload = "general"
  }
}

resource "aws_eks_node_group" "spot" {
  cluster_name    = module.eks.cluster_name
  node_group_name = "spot"
  node_role_arn   = aws_iam_role.eks_node_group.arn
  subnet_ids      = module.vpc.private_subnets

  scaling_config {
    desired_size = 1
    max_size     = 10
    min_size     = 0
  }

  instance_types = ["m5.large", "m5a.large", "m5n.large"]
  capacity_type  = "SPOT"

  labels = {
    workload = "batch"
  }
}
```

### Cluster Autoscaler
```yaml
# cluster-autoscaler.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cluster-autoscaler
  namespace: kube-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: cluster-autoscaler
  template:
    metadata:
      labels:
        app: cluster-autoscaler
    spec:
      serviceAccountName: cluster-autoscaler
      containers:
      - name: cluster-autoscaler
        image: k8s.gcr.io/autoscaling/cluster-autoscaler:v1.28.0
        args:
        - --v=4
        - --stderrthreshold=info
        - --cloud-provider=aws
        - --skip-nodes-with-local-storage=false
        - --expander=least-waste
        - --node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/openhands-cluster
        env:
        - name: AWS_REGION
          value: us-west-2
```

## Key Features

1. Multi-AZ Deployment
- Nodes spread across availability zones
- Automatic failover
- Zone-aware routing

2. Auto-scaling
- Pod-level HPA
- Node-level cluster autoscaler
- Mixed instance types (on-demand/spot)

3. Security
- Network policies
- RBAC
- Secrets management
- WAF integration

4. Monitoring
- Prometheus metrics
- Grafana dashboards
- CloudWatch integration
- Custom resource metrics

5. Cost Optimization
- Spot instance usage
- Resource quotas
- Automatic scaling
- Cache optimization

## Next Steps

1. Infrastructure Setup (Week 1-2)
- Deploy VPC and networking
- Set up EKS cluster
- Configure node groups
- Set up monitoring

2. Core Services (Week 3-4)
- Deploy model servers
- Configure auto-scaling
- Set up API gateway
- Implement caching

3. Security & Compliance (Week 5)
- Configure RBAC
- Set up network policies
- Implement secrets management
- Configure WAF rules

4. Monitoring & Optimization (Week 6)
- Set up Prometheus/Grafana
- Configure alerts
- Implement cost optimization
- Fine-tune auto-scaling

5. Testing & Validation (Week 7-8)
- Load testing
- Failover testing
- Security testing
- Performance optimization