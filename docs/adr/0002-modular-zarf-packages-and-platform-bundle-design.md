# ADR 0002: Modular Zarf Packages and Platform Bundle Architecture

## Status
Accepted

## Context
The goal of this repository is to build and validate Defense Unicorns UDS (Unified Delivery System) bundles for air-gapped Kubernetes environments (such as our Dell T5600 sandbox hypervisor).

We previously developed a comprehensive GitOps-driven Kubernetes platform in `talos-k8s-platform` featuring:
- Argo CD (GitOps deployment and sync engine)
- Observability stack (`kube-prometheus-stack`, Prometheus, Grafana, Alertmanager, Exporters)
- Workload / Application tiers (`training-app`)

We needed to decide whether to:
1. Design an entirely new synthetic application stack from scratch.
2. Adapt and modularize the battle-tested manifests, Helm charts, and configurations from `talos-k8s-platform` into modular Zarf packages orchestrated by a top-level UDS bundle.

## Decision
We decide to **port and decompose the proven platform configurations from `talos-k8s-platform` into modular Zarf packages**:

1. **`packages/argocd/zarf.yaml`**: Packages the Argo CD control plane, server, repo-server, and dex components into an offline-ready Zarf package.
2. **`packages/monitoring/zarf.yaml`**: Packages the Prometheus, Grafana, Alertmanager, and Node Exporter stack with pre-configured dashboard and alerting rules.
3. **`packages/training-app/zarf.yaml`**: Packages the mission workload / training application container images, services, and routing manifests.
4. **`bundles/uds-bundle.yaml`**: The top-level UDS bundle descriptor that binds the packages, establishes deployment ordering, and exposes configuration variables.

## Consequences

### Positive
- **Proven Stability**: Reuses tested Helm chart versions, value overrides, and resource definitions rather than untested toys.
- **Modularity & Reusability**: Each Zarf package (`argocd`, `monitoring`, `training-app`) can be independently built, tested, and published to an OCI registry or packaged collectively in a UDS bundle.
- **True Air-Gap Verification**: Guarantees all container images, charts, and configurations are bundled and pushed to the cluster's internal Zarf registry without external egress.
- **Clear Separation**: Infrastructure-level primitives (OS, Talos, Cilium CNI, Longhorn CSI) remain in the environment layer, while platform services live in the UDS bundle layer.

### Negative
- Bundle compilation will download and compress multiple large container images (Prometheus, Grafana, ArgoCD), requiring several hundred megabytes of storage per `.tar.zst` artifact.
