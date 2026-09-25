#!/usr/bin/env bash
# ==============================================================================
# UDS Bundle Build & Packaging Script (Connected Workstation)
# ==============================================================================
# Builds all underlying Zarf packages and creates the self-contained UDS bundle.
# Output is saved to the build/ directory for delivery across the air-gap boundary.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_DIR="${REPO_ROOT}/build"

echo "=============================================================================="
echo "                   BUILDING UDS BUNDLE FOR AIR-GAP DELIVERY                   "
echo "=============================================================================="

mkdir -p "${BUILD_DIR}"

# 1. Verify Prerequisites
for tool in zarf uds; do
  if ! command -v "${tool}" &>/dev/null; then
    echo "ERROR: '${tool}' CLI tool is required but not installed on host PATH."
    echo "Please install ${tool} before running this build script."
    exit 1
  fi
done

# 2. Build Zarf Packages
echo "=== [1/2] Building Component Zarf Packages ==="
if [ -d "${REPO_ROOT}/packages" ]; then
  for pkg_dir in "${REPO_ROOT}/packages"/*; do
    if [ -d "${pkg_dir}" ] && [ -f "${pkg_dir}/zarf.yaml" ]; then
      echo "  -> Building package in: ${pkg_dir}"
      (cd "${pkg_dir}" && zarf package create --confirm --output .)
    fi
  done
fi

# 3. Create UDS Bundle
echo "=== [2/2] Creating UDS Bundle Artifact ==="
if [ -f "${REPO_ROOT}/bundles/uds-bundle.yaml" ]; then
  (cd "${REPO_ROOT}/bundles" && uds create . --confirm -o "${BUILD_DIR}")
  echo "UDS Bundle created successfully in: ${BUILD_DIR}"
else
  echo "ERROR: No uds-bundle.yaml found in ${REPO_ROOT}/bundles/"
  exit 1
fi

echo "=============================================================================="
echo " Build complete. Ready for transfer to air-gapped test sandbox."
echo " Artifacts located in: ${BUILD_DIR}"
echo "=============================================================================="
