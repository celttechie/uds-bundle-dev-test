# UDS Bundle Development & Test (`uds-bundle-dev-test`)

A dedicated development and testing repository for authoring, packaging, and validating **Defense Unicorns UDS Bundles** and **Zarf Packages** targeted for air-gapped Kubernetes environments.

---

## Architecture & Lifecycle Separation

This repository is strictly focused on **Software & Bundle Engineering**. The hypervisor and air-gapped Kubernetes environment are managed independently in the `airgapped-sandbox-vm` repository.

```
┌─────────────────────────────────────────────────────────────┐
│  CONNECTED ENVIRONMENT (This Repo: uds-bundle-dev-test)     │
│  • Author Zarf packages (zarf.yaml) & manifests             │
│  • Assemble UDS Bundles (uds-bundle.yaml)                   │
│  • Run `uds create` to package into immutable .tar.zst      │
└──────────────────────────────┬──────────────────────────────┘
                               │ Transfer .tar.zst
┌──────────────────────────────▼──────────────────────────────┐
│  AIR-GAPPED TARGET (T5600 Sandbox / airgapped-sandbox-vm)   │
│  • Running K3s / RKE2 cluster with zero WAN access          │
│  • Run `uds deploy <bundle.tar.zst>` (Operator Persona)     │
│  • Validate zero-trust policies, health probes, and Lula    │
└─────────────────────────────────────────────────────────────┘
```

For the architectural rationale, see [ADR 0001: Separation of Environment Infrastructure and UDS Bundle Lifecycles](file:///home/bjarrett/Projects/uds-bundle-dev-test/docs/adr/0001-separation-of-environment-and-bundle-lifecycle.md).

---

## Directory Structure

```
uds-bundle-dev-test/
├── bundles/                # Top-level UDS bundle definitions
│   ├── uds-bundle.yaml     # Bundle orchestrating Zarf packages & dependencies
│   └── zarf.yaml           # Demo / local package definition
├── packages/               # Modular Zarf packages (apps, services, tools)
├── scripts/                # Development, build, and validation scripts
│   ├── build-bundle.sh     # Builds Zarf packages and creates .tar.zst bundle
│   ├── test-deploy.sh      # Tests deploying the bundle to a cluster
│   └── verify-airgap.sh    # Audits network isolation / zero egress
├── docs/                   # Architecture decision records & guides
│   └── adr/
│       └── 0001-separation-of-environment-and-bundle-lifecycle.md
└── README.md
```

---

## Getting Started

### Prerequisites (Connected Machine)
- [UDS CLI](https://github.com/defenseunicorns/uds-cli) (`uds`)
- [Zarf CLI](https://github.com/zarf-dev/zarf) (`zarf`)
- [Lula CLI](https://github.com/defenseunicorns/lula) (optional, for compliance validation)
- Docker or Podman (for packaging container images)

### 1. Build the UDS Bundle
Run the build script on your connected workstation to package all container images and manifests into a single offline artifact:
```bash
./scripts/build-bundle.sh
```
The compiled bundle (`uds-bundle-<name>-<arch>-<version>.tar.zst`) will be generated in `build/`.

### 2. Deliver and Deploy to Air-Gapped Sandbox
Transfer the generated `.tar.zst` artifact to the target air-gapped test environment (e.g., your Dell T5600 sandbox node) and run:
```bash
uds deploy ./build/uds-bundle-*.tar.zst --confirm
```

---

## Testing & Verification

- **Air-Gap Network Audit**: Run `./scripts/verify-airgap.sh` inside the target VM to assert zero WAN egress prior to deployment.
- **Cluster Deployment Test**: Run `./scripts/test-deploy.sh` against the active `KUBECONFIG`.
