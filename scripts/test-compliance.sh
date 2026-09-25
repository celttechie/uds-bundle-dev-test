#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OSCAL_FILE="${ROOT_DIR}/docs/compliance/oscal-il5.yaml"
OUTPUT_FILE="${ROOT_DIR}/docs/compliance/assessment-results.yaml"

echo "=== Running DoD IL5 Lula Compliance Validation ==="

if ! command -v lula &>/dev/null; then
    echo "⚠️  Lula CLI is not found in PATH."
    echo "ℹ️  To install: curl -fsSL https://raw.githubusercontent.com/defenseunicorns/lula/main/install.sh | bash"
    echo "ℹ️  Or using pre-built binary in your environment."
    exit 0
fi

if [[ ! -f "${OSCAL_FILE}" ]]; then
    echo "❌ Error: OSCAL component file not found at ${OSCAL_FILE}"
    exit 1
fi

echo "Validating cluster against NIST SP 800-53 Rev 5 (DoD IL5)..."
lula validate -f "${OSCAL_FILE}" -o "${OUTPUT_FILE}"

echo "✅ Compliance validation completed. Results saved to ${OUTPUT_FILE}."
