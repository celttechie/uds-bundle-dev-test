#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OSCAL_FILE="${ROOT_DIR}/docs/compliance/oscal-il5.yaml"
OUTPUT_FILE="${ROOT_DIR}/docs/compliance/assessment-results.yaml"

export PATH="${HOME}/.local/bin:${PATH}"

echo "=============================================================================="
echo "          RUNNING DOD IL5 LULA COMPLIANCE VALIDATION                         "
echo "=============================================================================="

if ! command -v lula &>/dev/null; then
    echo "⚠️  Lula CLI is not found in PATH."
    echo "ℹ️  Install lula or check ~/.local/bin/lula."
    exit 1
fi

if [[ ! -f "${OSCAL_FILE}" ]]; then
    echo "❌ Error: OSCAL component file not found at ${OSCAL_FILE}"
    exit 1
fi

# Use local kubeconfig if available and KUBECONFIG not already set
if [[ -z "${KUBECONFIG:-}" && -f "${ROOT_DIR}/../uds-platform-prep/kubeconfig" ]]; then
    export KUBECONFIG="${ROOT_DIR}/../uds-platform-prep/kubeconfig"
fi

echo "Validating target cluster against NIST SP 800-53 Rev 5 (DoD IL5)..."
rm -f "${OUTPUT_FILE}"
lula validate -f "${OSCAL_FILE}" -o "${OUTPUT_FILE}"

echo "=============================================================================="
echo " ✅ Compliance validation completed successfully!"
echo " Findings saved to: ${OUTPUT_FILE}"
echo "=============================================================================="
