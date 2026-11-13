#!/usr/bin/env python3
"""
Defense Unicorns & Kubernetes Interactive CLI Troubleshooting Drill Manager
Injects, verifies, teaches, and heals cluster, Zarf, UDS, and Lula compliance failures.
"""

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import random
import sys
from typing import Any

import yaml

from common import (
    BLUE,
    BOLD,
    CYAN,
    DIM,
    GREEN,
    MAGENTA,
    RED,
    REPO_ROOT,
    RESET,
    YELLOW,
    detect_training_namespace,
    run_cmd,
)

DRILLS_DIR = REPO_ROOT / "scripts" / "drills"
CHEATSHEET_FILE = DRILLS_DIR / "cheatsheet.yaml"
MYSTERY_STATE_FILE = REPO_ROOT / ".active_mystery_drill.json"

DOMAIN_ORDER = [
    "Zarf/Air-Gap",
    "UDS/Networking",
    "Compute",
    "Storage",
    "Lula/Security",
]


@dataclass
class TutorStep:
    phase: str
    prompt: str
    recommended_cmd: str
    hint: str
    explanation: str


@dataclass
class Scenario:
    id: str
    domain: str
    tools: list[str]
    title: str
    description: str
    symptoms: str
    inject_cmds: list[str]
    heal_cmds: list[str]
    verify_cmd: str
    tutor_steps: list[TutorStep]

    @classmethod
    def from_dict(cls, data: dict[str, Any], sc_id: str) -> "Scenario":
        tutor_steps = [
            TutorStep(
                phase=step["phase"],
                prompt=step["prompt"],
                recommended_cmd=step["recommended_cmd"],
                hint=step["hint"],
                explanation=step["explanation"],
            )
            for step in data.get("tutor_steps", [])
        ]
        return cls(
            id=data.get("id") or sc_id,
            domain=data["domain"],
            tools=data["tools"],
            title=data["title"],
            description=data["description"],
            symptoms=data["symptoms"],
            inject_cmds=data["inject_cmds"],
            heal_cmds=data["heal_cmds"],
            verify_cmd=data["verify_cmd"],
            tutor_steps=tutor_steps,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_scenario_file(path: Path, ns: str) -> Scenario:
    """Load a single scenario YAML definition and substitute namespace parameters."""
    raw = path.read_text(encoding="utf-8")
    rendered = raw.replace("${NAMESPACE}", ns).replace("${ns}", ns)
    data = yaml.safe_load(rendered)
    sc_id = data.get("id") or path.stem
    return Scenario.from_dict(data, sc_id)


def build_scenarios(ns: str) -> dict[str, dict[str, Any]]:
    """Build the scenario catalog parameterized by the active training namespace.

    Discovers all scenario YAML files in `scripts/drills/`, validates schema,
    and returns a catalog ordered by learning domains.
    """
    scenarios: dict[str, dict[str, Any]] = {}
    if not DRILLS_DIR.is_dir():
        return scenarios

    loaded: list[tuple[int, str, Scenario]] = []
    for yaml_path in DRILLS_DIR.glob("*.yaml"):
        if yaml_path.name == "cheatsheet.yaml":
            continue
        try:
            scenario = load_scenario_file(yaml_path, ns)
            domain_idx = DOMAIN_ORDER.index(scenario.domain) if scenario.domain in DOMAIN_ORDER else 99
            loaded.append((domain_idx, scenario.id, scenario))
        except Exception as e:
            print(f"{YELLOW}Warning: Failed to load drill scenario from {yaml_path.name}: {e}{RESET}", file=sys.stderr)

    # Sort primarily by curriculum domain progression, then by scenario ID
    loaded.sort(key=lambda item: (item[0], item[1]))

    for _, sc_id, sc in loaded:
        scenarios[sc_id] = sc.to_dict()

    return scenarios


def domain_badge(domain: str) -> str:
    colors = {
        "Zarf/Air-Gap": MAGENTA,
        "UDS/Networking": GREEN,
        "Compute": YELLOW,
        "Storage": BLUE,
        "Lula/Security": CYAN,
    }
    color = colors.get(domain, BLUE)
    return f"{color}{domain:<15}{RESET}"


def list_drills(scenarios: dict[str, dict[str, Any]]) -> None:
    print(f"\n{BOLD}{BLUE}===================================================================================={RESET}")
    print(f"{BOLD}{BLUE}     DEFENSE UNICORNS & KUBERNETES CLI TROUBLESHOOTING DRILL CATALOG                {RESET}")
    print(f"{BOLD}{BLUE}===================================================================================={RESET}\n")
    print(f"{BOLD}{'DOMAIN':<15} {'SCENARIO ID':<24} {'CLI TOOLS':<16} {'TITLE'}{RESET}")
    print(f"{'-' * 84}")
    for sc_id, data in scenarios.items():
        tools_str = ", ".join(data["tools"])
        print(f"{domain_badge(data['domain'])} {BOLD}{sc_id:<24}{RESET} {CYAN}{tools_str:<16}{RESET} {data['title']}")
        print(f"                {DIM}Symptoms: {data['symptoms']}{RESET}\n")

    print(f"{BOLD}Interactive Learning & Chaos Commands:{RESET}")
    print(f"  {BOLD}make drill-tutor SCENARIO=<id>{RESET}   -> Step-by-step interactive CLI tutor for a scenario")
    print(f"  {BOLD}make drill-mystery{RESET}               -> Inject a random blind fault to diagnose from scratch")
    print(f"  {BOLD}make drill-check{RESET}                 -> Audit cluster & Lula compliance health (solves mystery)")
    print(f"  {BOLD}make drill-inject SCENARIO=<id>{RESET}  -> Inject specific defect")
    print(f"  {BOLD}make drill-verify SCENARIO=<id>{RESET}  -> Observe live symptoms")
    print(f"  {BOLD}make drill-heal SCENARIO=<id|all>{RESET}-> Restore cluster to healthy state")
    print(f"  {BOLD}make drill-cheatsheet{RESET}            -> Print CLI diagnostic reference card\n")


def print_cheatsheet(ns: str) -> None:
    print(f"\n{BOLD}{BLUE}===================================================================================={RESET}")
    print(f"{BOLD}{BLUE}     AIR-GAPPED PLATFORM ENGINEERING CLI TROUBLESHOOTING CHEAT SHEET                {RESET}")
    print(f"{BOLD}{BLUE}===================================================================================={RESET}\n")

    if not CHEATSHEET_FILE.is_file():
        print(f"{YELLOW}Warning: Cheatsheet file not found at {CHEATSHEET_FILE}{RESET}")
        return

    raw = CHEATSHEET_FILE.read_text(encoding="utf-8")
    rendered = raw.replace("${NAMESPACE}", ns).replace("${ns}", ns)
    sections = yaml.safe_load(rendered) or []

    for sec in sections:
        header = sec.get("title", "")
        print(f"{BOLD}{YELLOW}{header}{RESET}")
        for item in sec.get("commands", []):
            cmd = item.get("cmd", "")
            desc = item.get("desc", "")
            print(f"  {GREEN}{cmd:<68}{RESET} {DIM}# {desc}{RESET}")
        print()


def pause_argocd_sync() -> None:
    """Temporarily pause ArgoCD automated sync if present so injected faults persist."""
    run_cmd(
        "kubectl patch application root-application -n argocd --type='merge' -p='{\"spec\":{\"syncPolicy\":null}}' 2>/dev/null || true",
        check=False,
        capture=True,
    )


def resume_argocd_sync() -> None:
    """Re-enable ArgoCD automated sync if present."""
    run_cmd(
        "kubectl patch application root-application -n argocd --type='merge' -p='{\"spec\":{\"syncPolicy\":{\"automated\":{\"prune\":true,\"selfHeal\":true}}}}' 2>/dev/null || true",
        check=False,
        capture=True,
    )


def inject_drill(sc_id: str, scenarios: dict[str, dict[str, Any]], quiet: bool = False) -> bool:
    if sc_id not in scenarios:
        print(f"{RED}Error: Unknown scenario ID '{sc_id}'. Run --list for options.{RESET}")
        return False
    scenario = scenarios[sc_id]
    if not quiet:
        print(f"\n{BOLD}{YELLOW}>>> Injecting Failure Scenario: {sc_id} ({scenario['title']}){RESET}")

    pause_argocd_sync()

    all_success = True
    for cmd in scenario["inject_cmds"]:
        res = run_cmd(cmd)
        if res.returncode != 0:
            if not quiet and res.stderr:
                print(f"{YELLOW}Warning executing injection: {res.stderr.strip()}{RESET}")
            all_success = False

    if all_success and not quiet:
        print(f"{GREEN}✓ Scenario '{sc_id}' successfully injected!{RESET}")
        print(f"{BOLD}Symptoms:{RESET} {scenario['symptoms']}")
        print(f"{BOLD}Tools to Practice:{RESET} {', '.join(scenario['tools'])}")
        print(f"Run {BOLD}make drill-tutor SCENARIO={sc_id} NO_INJECT=1{RESET} for guided CLI walk-through.\n")
    elif not all_success and not quiet:
        print(f"{RED}✗ Scenario '{sc_id}' injection encountered errors (is the cluster reachable?).{RESET}\n")
    return all_success


def heal_drill_single(sc_id: str, scenarios: dict[str, dict[str, Any]]) -> bool:
    scenario = scenarios[sc_id]
    print(f"{BLUE}Healing Scenario: {sc_id} ({scenario['title']})...{RESET}")
    all_success = True
    for cmd in scenario["heal_cmds"]:
        res = run_cmd(cmd)
        if res.returncode != 0:
            all_success = False
    if all_success:
        print(f"{GREEN}✓ Scenario '{sc_id}' healed.{RESET}")
    else:
        print(f"{RED}✗ Failed to heal Scenario '{sc_id}'.{RESET}")
    return all_success


def heal_drill(sc_id: str, scenarios: dict[str, dict[str, Any]]) -> bool:
    if sc_id == "all":
        print(f"\n{BOLD}{GREEN}>>> Healing all drill scenarios...{RESET}")
        has_error = False
        for s_id in scenarios:
            if not heal_drill_single(s_id, scenarios):
                has_error = True
        resume_argocd_sync()
        if MYSTERY_STATE_FILE.exists():
            MYSTERY_STATE_FILE.unlink()
        return not has_error

    if sc_id not in scenarios:
        print(f"{RED}Error: Unknown scenario ID '{sc_id}'.{RESET}")
        return False

    ok = heal_drill_single(sc_id, scenarios)
    resume_argocd_sync()
    if MYSTERY_STATE_FILE.exists():
        try:
            state = json.loads(MYSTERY_STATE_FILE.read_text())
            if state.get("scenario_id") == sc_id:
                MYSTERY_STATE_FILE.unlink()
        except (OSError, json.JSONDecodeError):
            pass
    return ok


def verify_drill(sc_id: str, scenarios: dict[str, dict[str, Any]], ns: str) -> None:
    if sc_id not in scenarios:
        print(f"{RED}Error: Unknown scenario ID '{sc_id}'.{RESET}")
        sys.exit(1)
    scenario = scenarios[sc_id]
    print(f"\n{BOLD}{BLUE}=== Diagnostic Status for Scenario: {sc_id} ==={RESET}")
    print(f"{BOLD}Expected Symptoms:{RESET} {scenario['symptoms']}\n")

    print(f"{BOLD}1. Scenario-Specific Check (`{scenario['verify_cmd']}`):{RESET}")
    v_res = run_cmd(scenario["verify_cmd"])
    print((v_res.stdout or "") + (v_res.stderr or ""))

    print(f"{BOLD}2. Active Pods in '{ns}' namespace:{RESET}")
    res = run_cmd(f"kubectl get pods -n {ns} -o wide")
    print(res.stdout if res.stdout else res.stderr)

    print(f"\n{BOLD}3. Recent Events in '{ns}' namespace:{RESET}")
    events_res = run_cmd(f"kubectl get events -n {ns} --sort-by=.metadata.creationTimestamp | tail -n 10")
    print(events_res.stdout if events_res.stdout else events_res.stderr)


def run_tutor(sc_id: str, scenarios: dict[str, dict[str, Any]], inject_first: bool = True) -> None:
    """Interactive 4-Phase CLI Tutor walking the user through real diagnostic commands."""
    if sc_id not in scenarios:
        print(f"{RED}Error: Unknown scenario ID '{sc_id}'. Run --list for options.{RESET}")
        sys.exit(1)

    scenario = scenarios[sc_id]
    print(f"\n{BOLD}{BLUE}===================================================================================={RESET}")
    print(f"{BOLD}{BLUE}  INTERACTIVE CLI TROUBLESHOOTING TUTOR: {sc_id}{RESET}")
    print(f"{BOLD}{BLUE}  {scenario['title']} [{scenario['domain']}]{RESET}")
    print(f"{BOLD}{BLUE}===================================================================================={RESET}")

    if inject_first:
        inject_drill(sc_id, scenarios, quiet=False)

    print(f"{BOLD}{YELLOW}INCIDENT TICKET:{RESET} {scenario['symptoms']}")
    print(f"{BOLD}{CYAN}CLI Tools Involved:{RESET} {', '.join(scenario['tools'])}")
    print(
        f"{DIM}Commands at any prompt: type a shell command to run it, or type "
        f"'hint' (show command), 'run' (auto-run recommended command), 'next' (skip step), "
        f"'heal' (fix & exit), or 'quit'.{RESET}\n"
    )

    steps = scenario.get("tutor_steps", [])
    for idx, step in enumerate(steps, start=1):
        print(f"{BOLD}{MAGENTA}--- [{idx}/{len(steps)}] {step['phase']} ---{RESET}")
        print(f"{BOLD}Task:{RESET} {step['prompt']}")

        while True:
            try:
                user_input = input(f"\n{BOLD}{GREEN}tutor ({sc_id}) [{idx}/{len(steps)}]> {RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{YELLOW}Exiting tutor. Run `make drill-heal SCENARIO={sc_id}` to restore cluster.{RESET}")
                return

            if not user_input:
                continue

            low = user_input.lower()
            if low in ("quit", "exit", "q"):
                print(f"{YELLOW}Exiting tutor. Run `make drill-heal SCENARIO={sc_id}` if the fault is still active.{RESET}")
                return
            if low == "heal":
                heal_drill(sc_id, scenarios)
                return
            if low in ("next", "skip", "n"):
                break
            if low in ("hint", "h", "?"):
                print(f"  {YELLOW}💡 Hint:{RESET} {step['hint']}")
                print(f"  {CYAN}Recommended Command:{RESET} {BOLD}{step['recommended_cmd']}{RESET}")
                continue
            if low == "explain":
                print(f"  {BLUE}📘 What to look for:{RESET} {step['explanation']}")
                continue

            cmd_to_run = step["recommended_cmd"] if low == "run" else user_input
            if low == "run":
                print(f"  {DIM}$ {cmd_to_run}{RESET}")

            res = run_cmd(cmd_to_run)
            if res.stdout:
                print(res.stdout.rstrip())
            if res.stderr:
                print(f"{YELLOW}{res.stderr.rstrip()}{RESET}")

            print(f"\n  {BLUE}📘 Takeaway:{RESET} {step['explanation']}")
            cont = input(f"  {DIM}Press Enter to advance to the next phase (or type 'retry' to run another command): {RESET}").strip().lower()
            if cont != "retry":
                break
        print()

    print(f"{BOLD}{GREEN}🎉 Completed all 4 diagnostic phases for '{sc_id}'!{RESET}")
    try:
        cleanup = input(f"Run automated heal check for '{sc_id}' now? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        cleanup = "n"
    if cleanup in ("", "y", "yes"):
        heal_drill(sc_id, scenarios)


def inject_mystery(scenarios: dict[str, dict[str, Any]]) -> None:
    """Pick a random scenario, inject it silently, and challenge the operator to diagnose & fix it."""
    sc_id = random.choice(list(scenarios.keys()))
    scenario = scenarios[sc_id]

    print(f"\n{BOLD}{MAGENTA}===================================================================================={RESET}")
    print(f"{BOLD}{MAGENTA}  🕵️  BLIND CHAOS INJECTION (MYSTERY TROUBLESHOOTING MODE)                           {RESET}")
    print(f"{BOLD}{MAGENTA}===================================================================================={RESET}\n")
    print("Injecting a random cluster, Zarf, UDS, or Lula compliance anomaly into the environment...")

    ok = inject_drill(sc_id, scenarios, quiet=True)
    MYSTERY_STATE_FILE.write_text(
        json.dumps({"scenario_id": sc_id, "domain": scenario["domain"], "title": scenario["title"]}, indent=2)
    )

    if ok:
        print(f"{GREEN}✓ Mystery fault injected!{RESET}\n")
    else:
        print(f"{YELLOW}⚠️ Mystery fault injection returned non-zero (cluster may be offline or unreachable).{RESET}\n")

    print(f"{BOLD}Your Mission:{RESET}")
    print("  1. Use `kubectl`, `zarf`, `uds`, and `lula` to detect, isolate, and remediate the issue.")
    print("  2. Need a CLI refresher? Run:  `make drill-cheatsheet`")
    print("  3. Ready to test your fix? Run: `make drill-check`")
    print("  4. Stuck? Reveal the fault via: `make drill-check REVEAL=1` or reset via `make drill-heal SCENARIO=all`\n")


def check_cluster_health(scenarios: dict[str, dict[str, Any]], ns: str, reveal: bool = False) -> bool:
    """Audit live cluster workloads, services, PVCs, and Lula compliance to verify remediation."""
    print(f"\n{BOLD}{BLUE}===================================================================================={RESET}")
    print(f"{BOLD}{BLUE}  CLUSTER & LULA COMPLIANCE HEALTH AUDIT (Namespace: {ns})                          {RESET}")
    print(f"{BOLD}{BLUE}===================================================================================={RESET}\n")

    if MYSTERY_STATE_FILE.exists():
        state = json.loads(MYSTERY_STATE_FILE.read_text())
        if reveal:
            sc_id = state["scenario_id"]
            print(f"{YELLOW}🔎 Active Mystery Scenario:{RESET} {BOLD}{sc_id}{RESET} — {state['title']} [{state['domain']}]")
            print(f"   Symptoms: {scenarios[sc_id]['symptoms']}\n")
        else:
            print(f"{MAGENTA}🕵️  A Mystery Drill is currently active (pass --reveal to see which one).{RESET}\n")

    checks_passed = True

    # 1. Check Pods in training namespace
    print(f"{BOLD}[1/4] Checking Pod Readiness in '{ns}'...{RESET}")
    pod_res = run_cmd(f"kubectl get pods -n {ns} --no-headers 2>/dev/null")
    if pod_res.returncode != 0 or not pod_res.stdout.strip():
        print(f"  {RED}✗ Unable to list pods in '{ns}' (or namespace is empty).{RESET}")
        checks_passed = False
    else:
        bad_pods = []
        for line in pod_res.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 3:
                name, ready, status = parts[0], parts[1], parts[2]
                if status == "Terminating":
                    continue
                if status != "Running" or ready.split("/")[0] != ready.split("/")[1]:
                    bad_pods.append(f"{name} ({ready}, {status})")
        if bad_pods:
            print(f"  {RED}✗ Unhealthy pods detected:{RESET} {', '.join(bad_pods)}")
            checks_passed = False
        else:
            print(f"  {GREEN}✓ All pods in '{ns}' are Running and Ready.{RESET}")

    # 2. Check Service Endpoints & Port 8080 on order-api
    print(f"{BOLD}[2/4] Checking Service Endpoints & TargetPorts in '{ns}'...{RESET}")
    ep_res = run_cmd(f"kubectl get ep order-api -n {ns} -o jsonpath='{{.subsets[*].ports[*].port}}' 2>/dev/null")
    netpol_res = run_cmd(f"kubectl get netpol deny-order-api-ingress -n {ns} --no-headers 2>/dev/null")
    if ep_res.returncode != 0 or "8080" not in (ep_res.stdout or ""):
        print(f"  {RED}✗ Service 'order-api' is missing healthy port 8080 endpoints (got: '{ep_res.stdout}').{RESET}")
        checks_passed = False
    elif netpol_res.returncode == 0 and "deny-order-api-ingress" in (netpol_res.stdout or ""):
        print(f"  {RED}✗ Rogue NetworkPolicy 'deny-order-api-ingress' is still blocking ingress.{RESET}")
        checks_passed = False
    else:
        print(f"  {GREEN}✓ Service 'order-api' endpoints and NetworkPolicies are healthy.{RESET}")

    # 3. Check Pending PVCs
    print(f"{BOLD}[3/4] Checking PersistentVolumeClaims in '{ns}'...{RESET}")
    pvc_res = run_cmd(f"kubectl get pvc -n {ns} --no-headers 2>/dev/null")
    if pvc_res.returncode == 0 and "Pending" in (pvc_res.stdout or ""):
        print(f"  {RED}✗ Pending PersistentVolumeClaim detected in '{ns}'.{RESET}")
        checks_passed = False
    else:
        print(f"  {GREEN}✓ No stuck Pending PVCs in '{ns}'.{RESET}")

    # 4. Check Lula OSCAL Compliance (compare baseline vs live cluster state)
    print(f"{BOLD}[4/4] Running Lula DoD IL5 OSCAL Validation...{RESET}")
    lula_res = run_cmd(
        "cp docs/compliance/assessment-results.yaml /tmp/lula-drill-assessment.yaml && "
        "lula validate -f docs/compliance/oscal-il5.yaml -o /tmp/lula-drill-assessment.yaml"
    )
    eval_res = run_cmd("lula evaluate -f /tmp/lula-drill-assessment.yaml")
    if lula_res.returncode != 0 or eval_res.returncode != 0:
        print(f"  {RED}✗ Lula OSCAL compliance validation failed (control drift detected).{RESET}")
        checks_passed = False
    else:
        print(f"  {GREEN}✓ All NIST SP 800-53 Rev 5 Lula controls are SATISFIED.{RESET}")

    print(f"\n{'=' * 84}")
    if checks_passed:
        print(f"{BOLD}{GREEN}✅ ALL CHECKS PASSED: Cluster and compliance controls are 100% healthy!{RESET}\n")
        if MYSTERY_STATE_FILE.exists():
            state = json.loads(MYSTERY_STATE_FILE.read_text())
            print(f"{BOLD}{CYAN}🏆 Mystery Solved! You remediated: {state['scenario_id']} ({state['title']}){RESET}\n")
            MYSTERY_STATE_FILE.unlink()
    else:
        print(f"{BOLD}{RED}❌ ISSUES REMAIN: Use `kubectl`, `zarf`, `uds`, or `lula` to investigate above failures.{RESET}\n")

    return checks_passed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Defense Unicorns & Kubernetes Interactive CLI Troubleshooting Drill Manager"
    )
    parser.add_argument("--list", action="store_true", help="List all available troubleshooting drill scenarios")
    parser.add_argument("--cheatsheet", action="store_true", help="Print CLI diagnostic reference card")
    parser.add_argument("--inject", type=str, metavar="ID", help="Scenario ID to inject")
    parser.add_argument("--heal", type=str, metavar="ID", help="Scenario ID to heal (or 'all')")
    parser.add_argument("--verify", type=str, metavar="ID", help="Verify live symptoms of a scenario")
    parser.add_argument("--tutor", type=str, metavar="ID", help="Launch interactive 4-phase CLI tutor for a scenario")
    parser.add_argument("--no-inject", action="store_true", help="Do not inject fault when starting --tutor")
    parser.add_argument("--mystery", action="store_true", help="Inject a random blind scenario for mystery troubleshooting")
    parser.add_argument("--check", action="store_true", help="Audit cluster & Lula compliance health")
    parser.add_argument("--reveal", action="store_true", help="Reveal the active mystery scenario during --check")
    parser.add_argument("--namespace", type=str, default=None, help="Override training workload namespace")

    args = parser.parse_args()
    offline_only = args.list or args.cheatsheet or len(sys.argv) == 1
    ns = args.namespace or detect_training_namespace(query_cluster=not offline_only)
    scenarios = build_scenarios(ns)

    if args.list or len(sys.argv) == 1:
        list_drills(scenarios)
    elif args.cheatsheet:
        print_cheatsheet(ns)
    elif args.inject:
        if not inject_drill(args.inject, scenarios):
            sys.exit(1)
    elif args.heal:
        if not heal_drill(args.heal, scenarios):
            sys.exit(1)
    elif args.verify:
        verify_drill(args.verify, scenarios, ns)
    elif args.tutor:
        run_tutor(args.tutor, scenarios, inject_first=not args.no_inject)
    elif args.mystery:
        inject_mystery(scenarios)
    elif args.check and not check_cluster_health(scenarios, ns, reveal=args.reveal):
        sys.exit(1)


if __name__ == "__main__":
    main()
