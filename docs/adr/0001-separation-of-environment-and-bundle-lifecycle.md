# 1. Separation of Environment Infrastructure and UDS Bundle Lifecycles

Date: 2026-09-24
Status: Accepted

## Context

In Defense Unicorns' UDS (Unicorn Delivery Service) architecture, deploying workloads into an air-gapped environment requires distinct operational responsibilities:
1. **Infrastructure Provisioning**: Standing up the hypervisor (Dell T5600 / Libvirt / KVM), configuring isolated virtual networking with zero WAN egress, provisioning VMs, and bootstrapping the foundational Kubernetes distribution (e.g., K3s / RKE2).
2. **Bundle Development & Packaging**: Authoring Zarf packages (`zarf.yaml`), assembling UDS bundles (`uds-bundle.yaml`), integrating Helm charts, configuring zero-trust networking/security policies (Istio, Keycloak, Pepr, Lula), and building the self-contained `.tar.zst` artifacts.
3. **Operational Delivery**: Handing off the `.tar.zst` artifact to a field operator to execute a single declarative deployment command (`uds deploy`).

Initially, infrastructure provisioning (OpenTofu + Libvirt) and bundle manifests coexisted in a single repository. However, this coupled the lifecycle of the hypervisor to bundle iterations, increasing testing friction and blurring persona boundaries.

## Decision

We decouple infrastructure provisioning from bundle authoring into two dedicated repositories:

1. **`airgapped-sandbox-vm` (Infrastructure & Environment)**:
   - Contains OpenTofu/Libvirt and Cloud-Init automation.
   - Manages the long-lived, isolated target VM and K3s cluster on the T5600 hypervisor.
   - Provides the target environment for air-gap validation.

2. **`uds-bundle-dev-test` (This Repository - Bundle Authoring & Testing)**:
   - Contains Zarf package definitions, UDS bundle definitions, Helm values, and compliance test suites.
   - Contains automation scripts for compiling packages (`zarf package create`, `uds create`), verifying bundle contents, and running test deployments (`uds deploy`).
   - Produces the immutable, cryptographically verifiable `.tar.zst` bundle artifacts.

## Consequences

### Positive
- **Fast Iteration**: Bundle authors can rapidly build and test bundle changes directly against a running sandbox cluster without tearing down and recreating VMs.
- **Accurate Persona Modeling**: Simulates real-world operational workflows where target air-gapped clusters are pre-existing.
- **Clean CI/CD Pipeline**: Upstream connected build pipelines can focus strictly on packaging container images and Helm charts into artifacts without needing hypervisor privileges.
- **Modularity**: The developed UDS bundles can be deployed to any compliant Kubernetes cluster, not just the local T5600 test VM.

### Negative / Trade-offs
- Requires managing two git repositories and keeping deployment endpoints synchronized.
