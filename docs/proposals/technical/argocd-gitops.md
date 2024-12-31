# ArgoCD GitOps Architecture for OpenHands

## Overview

This proposal outlines an ArgoCD-based GitOps architecture for managing OpenHands deployments and upstream synchronization.

```
┌──────────────────────────────────────────────────────────────┐
│                     ArgoCD Platform                          │
├──────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐   │
│  │   App of    │   │    Repo     │   │    Config       │   │
│  │    Apps     │   │   Server    │   │   Management    │   │
│  └──────┬──────┘   └──────┬──────┘   └───────┬─────────┘   │
│         │                 │                   │             │
│  ┌──────┴──────┐   ┌─────┴─────┐   ┌────────┴──────────┐  │
│  │  Upstream   │   │   Fork     │   │     Cluster       │  │
│  │   Sync      │   │  Manager   │   │     Config        │  │
│  └──────┬──────┘   └─────┬─────┘   └────────┬──────────┘  │
│         │                 │                   │             │
│  ┌──────┴──────┐   ┌─────┴─────┐   ┌────────┴──────────┐  │
│  │ Development │   │ Staging   │   │    Production     │  │
│  │   Cluster   │   │  Cluster  │   │     Cluster       │  │
│  └─────────────┘   └───────────┘   └─────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Components

### 1. Application Structure

```yaml
# Root Application (App of Apps)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: openhands-root
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_ORG/OpenHands.git
    path: argocd/apps
    targetRevision: HEAD
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 2. Upstream Sync Configuration

```yaml
# Upstream Sync Application
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: upstream-sync
  namespace: argocd
spec:
  project: openhands
  source:
    repoURL: https://github.com/baladithyab/OpenHands.git
    path: kubernetes
    targetRevision: main
  destination:
    server: https://kubernetes.default.svc
    namespace: openhands-system
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

### 3. Environment-Specific Applications

```yaml
# Development Environment
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: openhands-dev
  namespace: argocd
spec:
  project: openhands
  source:
    repoURL: https://github.com/YOUR_ORG/OpenHands.git
    path: kubernetes/overlays/development
    targetRevision: HEAD
  destination:
    server: https://kubernetes.default.svc
    namespace: openhands-dev
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true

# Production Environment
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: openhands-prod
  namespace: argocd
spec:
  project: openhands
  source:
    repoURL: https://github.com/YOUR_ORG/OpenHands.git
    path: kubernetes/overlays/production
    targetRevision: HEAD
  destination:
    server: https://kubernetes.default.svc
    namespace: openhands-prod
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

## Sync Process

### 1. Automated Sync Workflow

1. Upstream Detection:
   - ArgoCD monitors upstream repository
   - Detects changes in main branch
   - Triggers sync workflow

2. Fork Synchronization:
   - Creates sync branch in fork
   - Applies changes from upstream
   - Handles conflicts if any

3. Pull Request:
   - Creates PR in fork repository
   - Adds labels and reviewers
   - Links to upstream changes

4. Validation:
   - Runs automated tests
   - Checks for breaking changes
   - Validates configurations

5. Deployment:
   - Auto-deploys to development
   - Requires approval for production
   - Monitors deployment health

### 2. Manual Sync Process

```bash
# Sync Script (sync.sh)
#!/bin/bash

# Configuration
UPSTREAM_REPO="https://github.com/baladithyab/OpenHands.git"
FORK_REPO="https://github.com/YOUR_ORG/OpenHands.git"
SYNC_BRANCH="sync/upstream"

# Sync Process
1. Fetch upstream changes
2. Create sync branch
3. Apply changes
4. Create pull request
5. Run validation
6. Notify team
```

## Monitoring & Notifications

### 1. ArgoCD Monitoring

```yaml
# Prometheus ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: argocd-metrics
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: argocd-metrics
  endpoints:
  - port: metrics
```

### 2. Notification Configuration

```yaml
# Notification Configuration
apiVersion: notification.argoproj.io/v1alpha1
kind: NotificationConfiguration
metadata:
  name: openhands-notifications
spec:
  triggers:
  - name: sync-failed
    condition: app.status.sync.status == 'Failed'
    template: sync-failed
  - name: sync-succeeded
    condition: app.status.sync.status == 'Succeeded'
    template: sync-succeeded
  templates:
  - name: sync-failed
    slack:
      message: |
        Sync failed for {{.app.metadata.name}}
        Error: {{.app.status.operationState.message}}
  - name: sync-succeeded
    slack:
      message: |
        Successfully synced {{.app.metadata.name}}
        Revision: {{.app.status.sync.revision}}
```

## Security Considerations

1. Repository Access:
   - Use deploy keys for read-only access
   - Use GitHub Actions tokens for PR creation
   - Rotate credentials regularly

2. RBAC Configuration:
   - Limit access to ArgoCD
   - Use project-based permissions
   - Enable SSO integration

3. Secrets Management:
   - Use external secret stores
   - Encrypt sensitive data
   - Regular secret rotation

## Implementation Plan

### Phase 1: Initial Setup (Week 1-2)
1. Install ArgoCD
2. Configure repositories
3. Set up basic sync
4. Configure RBAC

### Phase 2: Automation (Week 3-4)
1. Implement sync automation
2. Configure notifications
3. Set up monitoring
4. Add validation checks

### Phase 3: Production Ready (Week 5-6)
1. Security hardening
2. Disaster recovery
3. Documentation
4. Team training

## Best Practices

1. Repository Management:
   - Use semantic versioning
   - Clean branch strategy
   - Regular pruning

2. Sync Process:
   - Regular sync intervals
   - Automated conflict resolution
   - Validation before merge

3. Monitoring:
   - Health checks
   - Performance metrics
   - Audit logging

4. Security:
   - Least privilege access
   - Regular security scans
   - Compliance checks

## Advantages Over Flux

1. User Interface:
   - Rich web UI
   - Visual sync status
   - Resource tree view

2. Multi-Cluster:
   - Better multi-cluster support
   - Cluster management
   - Cross-cluster sync

3. Authentication:
   - Built-in SSO
   - RBAC integration
   - Audit logging

4. Tooling:
   - CLI tools
   - SDK support
   - Plugin ecosystem

## Recommendations

1. Development Environment:
   - Automatic sync
   - Frequent updates
   - Loose validation

2. Production Environment:
   - Manual approval
   - Strict validation
   - Scheduled updates

3. Monitoring:
   - Real-time alerts
   - Performance tracking
   - Audit trails

4. Security:
   - Regular audits
   - Access reviews
   - Compliance checks