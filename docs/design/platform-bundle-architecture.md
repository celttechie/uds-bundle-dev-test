# Platform UDS Bundle Architectural Design

## 1. Overview

The **Platform UDS Bundle** bundles core platform services (GitOps, Observability) alongside sample mission workloads into a single, cryptographically verifiable, air-gappable `.tar.zst` artifact.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      uds-bundle.yaml (Platform Stack)                  │
├────────────────────┬─────────────────────┬─────────────────────────────┤
│ 1. Argo CD         │ 2. Monitoring Stack │ 3. Mission Workload         │
│ • Argo CD Server   │ • Prometheus        │ • Training App Front/API    │
│ • Repo Server      │ • Grafana           │ • Service & Ingress Config  │
│ • Controller / Dex │ • Node Exporter     │                             │
│ • CRDs & RBAC      │ • Alertmanager      │                             │
└────────────────────┴─────────────────────┴─────────────────────────────┘
```

---

## 2. Directory Layout

```
uds-bundle-dev-test/
├── bundles/
│   └── uds-bundle.yaml         # Orchestrates the 3 packages & exports/imports
├── packages/
│   ├── argocd/
│   │   ├── zarf.yaml           # Zarf package definition for Argo CD
│   │   └── values/             # Helm values and customized CRDs
│   ├── monitoring/
│   │   ├── zarf.yaml           # Zarf package for kube-prometheus-stack
│   │   └── values/             # Prometheus / Grafana dashboards & alerts
│   └── training-app/
│       ├── zarf.yaml           # Zarf package for mission app
│       └── manifests/          # Kubernetes manifests / kustomization
├── scripts/
│   ├── build-bundle.sh         # Builds individual Zarf packages + UDS bundle
│   ├── test-deploy.sh          # Local cluster deploy verification
│   └── verify-airgap.sh        # Air-gap zero-egress auditor
├── docs/
│   ├── adr/
│   │   ├── 0001-separation-of-environment-and-bundle-lifecycle.md
│   │   └── 0002-modular-zarf-packages-and-platform-bundle-design.md
│   └── design/
│       └── platform-bundle-architecture.md
└── README.md
```

---

## 3. Package Specifications

### 3.1 `package-argocd` (`packages/argocd/`)
- **Upstream Helm Chart**: `argo/argo-cd`
- **Container Images**:
  - `quay.io/argoproj/argocd`
  - `ghcr.io/dexidp/dex`
  - `redis`
- **Capabilities**:
  - Offline GitOps sync loop against local in-cluster git server or OCI manifests.
  - Custom RBAC policies and admin credentials configuration.

### 3.2 `package-monitoring` (`packages/monitoring/`)
- **Upstream Helm Chart**: `prometheus-community/kube-prometheus-stack`
- **Container Images**:
  - `quay.io/prometheus/prometheus`
  - `quay.io/prometheus/alertmanager`
  - `quay.io/prometheus/node-exporter`
  - `registry.k8s.io/kube-state-metrics/kube-state-metrics`
  - `docker.io/grafana/grafana`
  - `quay.io/kiwigrid/k8s-sidecar`
- **Capabilities**:
  - Cluster node and workload metric collection.
  - Pre-provisioned Grafana dashboards for cluster health and pod metrics.

### 3.3 `package-training-app` (`packages/training-app/`)
- **Workload Manifests**: Ported from `talos-k8s-platform/gitops/apps/training-app/`.
- **Container Images**: Application container images and dependencies.
- **Capabilities**:
  - End-to-end verification that user-facing workloads deploy and link to platform monitoring without internet access.

---

## 4. Lifecycle & Build Pipeline

1. **Package Compilation**: Each package in `packages/*` is packaged using `zarf package create`.
2. **Bundle Assembly**: `uds create bundles/` bundles all package `.tar.zst` files into a single bundle `.tar.zst`.
3. **Air-Gap Ingestion**: The bundle archive is transferred to the air-gapped target host and deployed with `uds deploy <bundle-archive>`.
