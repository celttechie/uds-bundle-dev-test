#!/usr/bin/env python3
"""
Common utilities for the UDS Air-Gapped Bundle & Troubleshooting Drill Engine.
Provides ANSI terminal styling, KUBECONFIG auto-discovery, namespace detection,
and subprocess execution helpers.
"""

import os
import subprocess
from pathlib import Path

# ANSI Terminal Styling
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
MAGENTA = "\033[0;35m"
CYAN = "\033[0;36m"
RESET = "\033[0m"

REPO_ROOT = Path(__file__).resolve().parent.parent
PREP_KUBECONFIG = REPO_ROOT.parent / "uds-platform-prep" / "kubeconfig"


def ensure_sandbox_tunnel(kubeconfig_path: Path) -> None:
    """If kubeconfig uses 127.0.0.1:16443, ensure the SSH tunnel to t5600 -> 10.160.0.34:6443 is up."""
    try:
        text = kubeconfig_path.read_text()
    except OSError:
        return
    if "127.0.0.1:16443" not in text:
        return

    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        if sock.connect_ex(("127.0.0.1", 16443)) == 0:
            return

    subprocess.run(
        "ssh -f -N -o StrictHostKeyChecking=no -o ExitOnForwardFailure=yes -L 16443:10.160.0.34:6443 t5600 </dev/null >/dev/null 2>&1",
        shell=True,
        check=False,
        timeout=5,
    )


def configure_kube_env() -> dict[str, str]:
    """Ensure KUBECONFIG and local binary paths (~/.local/bin) are available."""
    env = os.environ.copy()
    local_bin = str(Path.home() / ".local" / "bin")
    prep_bin = str(REPO_ROOT.parent / "uds-platform-prep" / "payloads" / "bin")

    path_parts = env.get("PATH", "").split(os.pathsep)
    for extra in (local_bin, prep_bin):
        if os.path.isdir(extra) and extra not in path_parts:
            path_parts.insert(0, extra)
    env["PATH"] = os.pathsep.join(path_parts)

    if not env.get("KUBECONFIG") and PREP_KUBECONFIG.is_file():
        env["KUBECONFIG"] = str(PREP_KUBECONFIG)
        ensure_sandbox_tunnel(PREP_KUBECONFIG)

    return env


def run_cmd(
    cmd: str,
    check: bool = False,
    capture: bool = True,
    timeout: int | None = 60,
) -> subprocess.CompletedProcess:
    """Execute a shell command with KUBECONFIG and toolchain PATH configured."""
    env = configure_kube_env()
    try:
        return subprocess.run(
            cmd,
            shell=True,
            executable="/bin/bash",
            text=True,
            capture_output=capture,
            check=check,
            timeout=timeout,
            env=env,
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=124,
            stdout="",
            stderr=f"Command timed out after {timeout}s: {cmd}",
        )


def detect_training_namespace(default: str = "training-app", query_cluster: bool = True) -> str:
    """
    Detect whether the training workload is running in 'training-app' or 'training'.
    Can be overridden via DRILL_NAMESPACE environment variable.
    """
    override = os.environ.get("DRILL_NAMESPACE")
    if override:
        return override
    if not query_cluster:
        return default

    res = run_cmd(
        "kubectl get deploy order-api -n training-app --request-timeout=2s -o name 2>/dev/null",
        check=False,
        capture=True,
        timeout=3,
    )
    if res.returncode == 0 and "order-api" in (res.stdout or ""):
        return "training-app"

    res_alt = run_cmd(
        "kubectl get deploy order-api -n training --request-timeout=2s -o name 2>/dev/null",
        check=False,
        capture=True,
        timeout=3,
    )
    if res_alt.returncode == 0 and "order-api" in (res_alt.stdout or ""):
        return "training"

    return default
