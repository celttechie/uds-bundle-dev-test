#!/usr/bin/env bash
# ==============================================================================
# UDS Bundle Test Deployment Script (Target Sandbox / Cluster)
# ==============================================================================
# Deploys the built UDS bundle to a target Kubernetes cluster (e.g. T5600 sandbox).
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_DIR="${REPO_ROOT}/build"

echo "=============================================================================="
echo "                 TESTING UDS BUNDLE DEPLOYMENT IN SANDBOX                     "
echo "=============================================================================="

# Check for UDS binary
if ! command -v uds &>/dev/null; then
  echo "ERROR: 'uds' CLI is not found on PATH."
  exit 1
fi

# Locate compiled UDS bundle
UDS_BUNDLE=$(find "${BUILD_DIR}" -maxdepth 1 -name "uds-bundle-*.tar.zst" 2>/dev/null | head -n 1 || true)

if [ -n "${UDS_BUNDLE}" ] && [ -f "${UDS_BUNDLE}" ]; then
  echo "Deploying compiled bundle: ${UDS_BUNDLE}"
  uds deploy "${UDS_BUNDLE}" --confirm
elif [ -f "${REPO_ROOT}/bundles/uds-bundle.yaml" ]; then
  echo "No pre-built .tar.zst found; deploying directly from bundle definition..."
  (cd "${REPO_ROOT}/bundles" && uds deploy . --confirm)
else
  echo "ERROR: No bundle found to deploy in ${BUILD_DIR} or ${REPO_ROOT}/bundles/"
  exit 1
fi

echo "=============================================================================="
echo " Deployment test finished. Current namespace resources:"
kubectl get all -A || true
echo "=============================================================================="
