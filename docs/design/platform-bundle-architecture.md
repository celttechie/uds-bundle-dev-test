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
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI: Lula lint, KinD runtime gate, unit tests, Gitleaks
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
│       └── manifests/          # Kubernetes manifests (Namespace, NetPol, Workloads)
├── scripts/
│   ├── common.py               # KUBECONFIG discovery, SSH tunnel auto-recovery & runner
│   ├── drill_manager.py        # Interactive CLI Tutor & Chaos Injection Engine
│   ├── build-bundle.sh         # Builds individual Zarf packages + UDS bundle (.tar.zst)
│   ├── test-deploy.sh          # Cluster deploy verification
│   ├── test-compliance.sh      # Lula OSCAL IL5 compliance validator
│   └── verify-airgap.sh        # Air-gap zero-egress auditor (auto-delegated over SSH)
├── docs/
│   ├── adr/                    # Architecture Decision Records (0001–0003)
│   ├── compliance/             # NIST SP 800-53 Rev 5 OSCAL 1.1.2 component & assessment
│   │   ├── oscal-il5.yaml
│   │   └── assessment-results.yaml
│   ├── design/
│   │   └── platform-bundle-architecture.md
│   └── troubleshooting-drills/ # CLI diagnostic field manual & scenario walkthroughs
├── tests/                      # Automated unit, OSCAL schema, and shift-left IL5 test suite
├── Makefile                    # Unified developer & drill CLI interface
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

1. **Pre-Commit & CI Validation**: Automated linting (`make lint`), OSCAL schema validation (`lula tools lint`), and static shift-left IL5 control assertions (`make test`) run on every PR.
2. **KinD Ephemeral Compliance Gate**: GitHub Actions deploys the workload manifests to an ephemeral KinD cluster and executes runtime `lula validate` against DoD IL5 NIST 800-53 controls.
3. **Package Compilation**: Each package in `packages/*` is packaged using `zarf package create`.
4. **Bundle Assembly**: `uds create bundles/` bundles all package `.tar.zst` files into a single bundle `.tar.zst`.
5. **Air-Gap Ingestion & Delivery**: The bundle archive is transferred to the air-gapped target host (e.g. Dell T5600 `airgapped-sandbox-hypervisor`) and deployed with `uds deploy <bundle-archive>`.

---

## 5. Continuous Compliance-as-Code with Lula

The platform bundle natively integrates with **Defense Unicorns Lula** to achieve Continuous Authority to Operate (cATO):

- **OSCAL Component Definition** (`docs/compliance/oscal-il5.yaml`): Formally specifies how the platform stack satisfies NIST SP 800-53 Rev 5 controls (`AC-3`, `AC-4`, `IA-2`, `SC-8`, `CM-8`) with embedded OPA Rego policies.
- **Continuous Assessment Results** (`docs/compliance/assessment-results.yaml`): Version-controlled, cryptographically verifiable assessment artifact tracking satisfied controls and providing an immutable audit trail.
- **Air-Gap Runtime Audit** (`make compliance`): Evaluates live cluster resources against OSCAL controls without requiring internet access.

---

## 6. Interactive CLI Troubleshooting Tutor & Chaos Engine

To train platform engineers and validate incident response in disconnected environments, the repository includes a chaos injection and diagnostic tutoring engine (`scripts/drill_manager.py`):

- **10 Diagnostic Scenarios**: Spans Zarf/Air-gap image seeding, mutating webhook bypass, zero-trust NetworkPolicy blocks, Service targetPort/selector mismatches, OOMKills, liveness probe loops, unschedulable pods, pending PVCs, and Lula compliance drift.
- **4-Phase Diagnostic Protocol**: Structured triage loop: *Detect* $\rightarrow$ *Isolate* $\rightarrow$ *Root Cause* $\rightarrow$ *Remediate & Verify*.
- **Mystery Fault Injection**: Blind chaos mode (`make drill-mystery`) to diagnose and resolve unannounced platform failures from scratch.
