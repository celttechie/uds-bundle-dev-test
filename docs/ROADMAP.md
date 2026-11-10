# Capabilities Roadmap & Enhancement Backlog

This document tracks modular, independent capabilities planned for the `uds-bundle-dev-test` workspace. Unlike sequential milestones, these capability tracks are **non-blocking** and can be implemented, tested, and merged independently in any order.

---

## Capability Tracks Overview

```
                                  CAPABILITY TRACKS
  ┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
  │ Track 1: GitOps & Argo  │ │ Track 2: Release CI/CD  │ │ Track 3: cATO & OSCAL   │ │ Track 4: Platform Pkgs  │
  ├─────────────────────────┤ ├─────────────────────────┤ ├─────────────────────────┤ ├─────────────────────────┤
  │ • Argo CD Applications  │ │ • Tag-triggered bundle  │ │ • Additional IL5 controls│ │ • Security policies pkg │
  │ • Lula PostSync Hook    │ │   build (.tar.zst)      │ │   (cm-6, si-4, au-2)    │ │   (Kyverno/Gatekeeper)  │
  │ • GitOps Drift Drill    │ │ • Syft/Grype SBOM gen   │ │ • Automated compliance  │ │ • Monitoring dashboard  │
  │                         │ │ • Checksum & provenance │ │   assessment reporting  │ │   Grafana provisioning  │
  └─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘
```

---

## Track 1: GitOps Integration with Argo CD
**Labels:** `enhancement`, `area:gitops`  
**Goal:** Connect the declarative deployment loop between Git, Argo CD (already running in the air-gapped target cluster), and Lula continuous compliance.

### Proposed Capabilities
1. **Declarative Application Manifests (`gitops/`):**
   - Author Argo CD `Application` and `ApplicationSet` manifests referencing the `packages/training-app` manifests.
   - Support zero-egress repository sync via local Git server or internal registry cache.
2. **Lula as an Argo CD PostSync Hook:**
   - Define a Kubernetes `Job` or Argo CD sync hook template running `lula validate` against the live cluster state immediately following a sync.
   - If an Argo CD sync introduces drift or violates DoD IL5 OSCAL policies, mark the application health as `Degraded` or emit an alert.
3. **GitOps Chaos Scenario in Drill Manager:**
   - Add a scenario (`gitops-drift-sync`) demonstrating automated reconciliation: injecting a manual edit via `kubectl` and observing Argo CD self-healing back to Git state.

---

## Track 2: Automated Bundle Build & Release Pipeline
**Labels:** `enhancement`, `area:ci-cd`, `area:packaging`  
**Goal:** Automate end-to-end packaging of modular Zarf packages and compiled `.tar.zst` UDS bundles on release tags.

### Proposed Capabilities
1. **GitHub Actions Release Workflow (`.github/workflows/release.yml`):**
   - Trigger on release tags (`v*`).
   - Run `zarf package create` across all packages in `packages/`.
   - Run `uds create` in `bundles/` to generate `uds-bundle-*.tar.zst`.
2. **Software Bill of Materials (SBOM) & Attestation:**
   - Export CycloneDX and SPDX SBOMs for every bundled container image.
   - Generate SHA-256 checksums and cryptographic signatures for bundle artifacts.
   - Attach `.tar.zst` bundles and SBOM tarballs to the GitHub Release.

---

## Track 3: Expanded DoD IL5 Compliance Controls (cATO)
**Labels:** `enhancement`, `area:compliance`  
**Goal:** Broaden continuous compliance coverage across NIST SP 800-53 Rev 5 to provide an out-of-the-box Continuous Authority to Operate (cATO) baseline.

### Proposed Capabilities
1. **Additional NIST SP 800-53 Rev 5 OSCAL Controls:**
   - **`cm-6` (Configuration Settings):** Enforce container security context constraints (`readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `drop: [ALL]` capabilities) across all namespaced workloads.
   - **`si-4` (Information System Monitoring):** Validate active DaemonSets and metric scrapers (Prometheus `node-exporter`) across all nodes.
   - **`au-2` / `au-12` (Event & Audit Logging):** Verify Kubernetes API server audit logging configuration and structured JSON container output.
2. **Automated Assessment Report Publishing:**
   - Output `assessment-results.yaml` directly from CI runs.
   - Generate human-readable Markdown / HTML compliance summaries suitable for Authorizing Officials (AOs).

---

## Track 4: Modular Platform Packages
**Labels:** `enhancement`, `area:packaging`, `area:compliance`  
**Goal:** Expand `packages/` beyond `training-app` to include reusable, zero-egress platform capabilities in the UDS bundle.

### Proposed Capabilities
1. **`security-policies` Zarf Package (`packages/security-policies/`):**
   - Package declarative Kyverno or Gatekeeper admission policies enforcing non-root execution, registry restrictions, and mandatory labels.
2. **`monitoring-dashboards` Zarf Package (`packages/monitoring-dashboards/`):**
   - Provision ConfigMaps containing Grafana dashboards tracking cluster health, zero-egress network drops, and Lula compliance scores.
