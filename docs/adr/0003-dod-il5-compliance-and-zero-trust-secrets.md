# ADR 0003: DoD IL5 Compliance and Zero-Trust Secrets Management

## Status
Accepted

## Context
Deploying software into air-gapped DoD and national security environments requires adhering to strict security standards, notably **DoD Impact Level 5 (IL5)** and **NIST SP 800-53 Rev 5**.

Key architectural challenges include:
1. Ensuring no sensitive credentials, certificates, or keys are committed into version control or baked directly into package definitions.
2. Providing automated, machine-readable validation that deployed packages meet DoD STIGs / IL5 controls (e.g. non-root execution, network segmentation, encrypted transport, least privilege).

## Decision

1. **Shift-Left Compliance via Lula (OSCAL-as-Code)**:
   - Define a formal OSCAL (Open Security Controls Assessment Language) Component Definition in `docs/compliance/oscal-il5.yaml`.
   - Embed automated validation rules using Defense Unicorns' **Lula** framework to assess live cluster states against NIST SP 800-53 Rev 5 controls (AC-3, AC-4, IA-2, SC-8, SC-28, CM-8).
   - Provide an automated test script (`scripts/test-compliance.sh`) to execute `lula validate` and generate `assessment-results.yaml`.

2. **Zero-Trust Secrets & Credential Management**:
   - **Dynamic Zarf Generation**: Use Zarf's built-in cryptographic generator for bootstrap credentials where external secrets are not supplied.
   - **Runtime Overrides**: Enable operators to supply environment-specific credentials via `uds-config.yaml` or environment variables without modifying bundle packages.
   - **OIDC / Identity Federation**: Integrate platform applications (Argo CD, Grafana) with enterprise OIDC (Keycloak / Dex) to enforce CAC/MFA, centralized RBAC, and session expiration.

3. **Pod Security Standards (Restricted Profile)**:
   - All packaged Helm values and manifests must enforce:
     - `runAsNonRoot: true`
     - `allowPrivilegeEscalation: false`
     - `readOnlyRootFilesystem: true` (or scoped ephemeral storage)
     - `capabilities.drop: ["ALL"]`
     - `seccompProfile.type: "RuntimeDefault"`

## Consequences

### Positive
- Continuous Authorization: Automated compliance verification directly inside air-gapped environments without manual STIG checklists.
- Defense in Depth: Workloads are securely isolated by default, preventing lateral movement and privilege escalation.
- Zero Hardcoded Secrets: High cryptographic entropy without secrets leakage risk.

### Negative
- Hardened security contexts require explicit volume mounts for temp directories and caches in certain legacy or third-party containers.
