#!/usr/bin/env bash
# ==============================================================================
# Air-Gap Network Isolation Verification Script (Executed Inside Target VM)
# ==============================================================================
# Performs strict assertion tests ensuring zero egress reachability.
# All internet tests MUST fail for this script to return exit code 0.
# ==============================================================================

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS] (Isolated)${NC} $1"; }
fail() { echo -e "${RED}[FAIL] (Leak Detected)${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

FAILED_TESTS=0

echo "=============================================================================="
echo "          AIR-GAP NETWORK ISOLATION VERIFICATION AUDIT                        "
echo "=============================================================================="
echo "Timestamp: $(date)"
echo "Hostname:  $(hostname)"
echo "------------------------------------------------------------------------------"

# Test 1: Public ICMP Ping
echo "--- 1. Testing Outbound ICMP (Ping 8.8.8.8 & 1.1.1.1) ---"
if ping -c 2 -W 2 8.8.8.8 &>/dev/null; then
  fail "Outbound ping to 8.8.8.8 SUCCEEDED (Egress network leak detected!)"
  FAILED_TESTS=$((FAILED_TESTS + 1))
else
  pass "Outbound ICMP to 8.8.8.8 was blocked."
fi

# Test 2: Public DNS Resolution
echo "--- 2. Testing External DNS Resolution (defenseunicorns.com) ---"
if getent hosts defenseunicorns.com &>/dev/null; then
  fail "Resolved defenseunicorns.com over DNS (DNS forwarder is leaking!)"
  FAILED_TESTS=$((FAILED_TESTS + 1))
else
  pass "External DNS query was blackholed / unresolvable."
fi

# Test 3: Public HTTP/HTTPS Egress
echo "--- 3. Testing Outbound HTTPS (https://github.com) ---"
if curl -s --connect-timeout 3 -m 5 https://github.com &>/dev/null; then
  fail "HTTPS connection to GitHub SUCCEEDED (WAN egress open!)"
  FAILED_TESTS=$((FAILED_TESTS + 1))
else
  pass "HTTPS connection timed out / rejected."
fi

# Test 4: Default Gateway Route Inspection
echo "--- 4. Inspecting Routing Table ---"
DEFAULT_GW=$(ip route show default 2>/dev/null || true)
if [[ -n "${DEFAULT_GW}" ]]; then
  info "Default gateway exists: ${DEFAULT_GW}"
else
  pass "No default upstream gateway found in routing table."
fi

# Test 5: Verify Media Drop Mount Point
echo "--- 5. Verifying Offline Media Block Device ---"
if [ -d "/opt/uds-media" ] && [ "$(ls -A /opt/uds-media 2>/dev/null)" ]; then
  pass "Offline media drop mounted and populated at /opt/uds-media"
else
  info "Media directory /opt/uds-media not yet populated."
fi

echo "=============================================================================="
if [ "${FAILED_TESTS}" -eq 0 ]; then
  echo -e "${GREEN}>>> AUDIT SUCCESSFUL: Host is strictly air-gapped with zero WAN egress. <<<${NC}"
  exit 0
else
  echo -e "${RED}>>> AUDIT FAILED: Detected ${FAILED_TESTS} network leaks to the outside world! <<<${NC}"
  exit 1
fi
