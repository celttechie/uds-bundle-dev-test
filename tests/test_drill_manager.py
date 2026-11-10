#!/usr/bin/env python3
"""
Unit and schema verification tests for the Defense Unicorns & Kubernetes
Interactive CLI Troubleshooting Drill Manager and OSCAL compliance artifacts.
Uses standard-library unittest so it runs out-of-the-box in any air-gapped environment.
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import drill_manager  # noqa: E402


class TestDrillManager(unittest.TestCase):
    def setUp(self) -> None:
        self.scenarios = drill_manager.build_scenarios("training-app")

    def test_scenario_catalog_completeness(self) -> None:
        """Verify all 10 scenarios across all 5 domains have required fields and 4-phase tutor steps."""
        expected_ids = {
            "zarf-untracked-image",
            "zarf-webhook-bypass",
            "net-policy-block",
            "net-port-mismatch",
            "net-service-endpoint",
            "comp-oom-killed",
            "comp-probe-fail",
            "comp-unschedulable",
            "stor-pvc-pending",
            "sec-lula-drift",
        }
        self.assertEqual(set(self.scenarios.keys()), expected_ids)

        for sc_id, sc in self.scenarios.items():
            self.assertIn(
                sc["domain"],
                {"Zarf/Air-Gap", "UDS/Networking", "Compute", "Storage", "Lula/Security"},
            )
            self.assertGreaterEqual(len(sc["tools"]), 1)
            self.assertGreaterEqual(len(sc["inject_cmds"]), 1)
            self.assertGreaterEqual(len(sc["heal_cmds"]), 1)
            self.assertTrue(sc["verify_cmd"])
            self.assertTrue(sc["symptoms"])
            self.assertEqual(
                len(sc["tutor_steps"]),
                4,
                f"Scenario {sc_id} must have 4 diagnostic phases",
            )
            for step in sc["tutor_steps"]:
                for key in ("phase", "prompt", "recommended_cmd", "hint", "explanation"):
                    self.assertIn(key, step)

    def test_yaml_drill_files_and_dataclasses(self) -> None:
        """Verify each scenario file in scripts/drills/ conforms to typed Scenario dataclass and substitutes namespace."""
        drills_dir = drill_manager.DRILLS_DIR
        self.assertTrue(drills_dir.is_dir(), "scripts/drills directory must exist")
        yaml_files = [f for f in drills_dir.glob("*.yaml") if f.name != "cheatsheet.yaml"]
        self.assertEqual(len(yaml_files), 10, "Expected 10 scenario YAML files")

        custom_ns = "custom-tenant-ns"
        for yf in yaml_files:
            raw_text = yf.read_text(encoding="utf-8")
            # Raw file should use ${NAMESPACE} rather than a hardcoded namespace
            self.assertNotIn("training-app", raw_text, f"{yf.name} should not contain hardcoded namespace")

            scenario = drill_manager.load_scenario_file(yf, custom_ns)
            self.assertIsInstance(scenario, drill_manager.Scenario)
            self.assertEqual(len(scenario.tutor_steps), 4)
            # Verify custom namespace substitution took effect
            self.assertIn(custom_ns, scenario.description)

    def test_cheatsheet_yaml_catalog(self) -> None:
        """Verify cheatsheet.yaml contains expected diagnostic sections and commands."""
        cs_file = drill_manager.CHEATSHEET_FILE
        self.assertTrue(cs_file.is_file(), "cheatsheet.yaml must exist")
        data = yaml.safe_load(cs_file.read_text(encoding="utf-8"))
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 4)
        for section in data:
            self.assertIn("title", section)
            self.assertIn("commands", section)
            for cmd_entry in section["commands"]:
                self.assertIn("cmd", cmd_entry)
                self.assertIn("desc", cmd_entry)

    def test_list_and_cheatsheet_output(self) -> None:
        """Verify --list and --cheatsheet render cleanly without errors."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            drill_manager.list_drills(self.scenarios)
        out_list = buf.getvalue()
        self.assertIn("zarf-untracked-image", out_list)
        self.assertIn("sec-lula-drift", out_list)

        buf_cs = io.StringIO()
        with redirect_stdout(buf_cs):
            drill_manager.print_cheatsheet("training-app")
        out_cs = buf_cs.getvalue()
        self.assertIn("zarf tools registry catalog", out_cs)
        self.assertIn("lula validate", out_cs)

    def test_inject_and_heal_commands_mocked(self) -> None:
        """Verify inject_drill and heal_drill invoke run_cmd with expected commands."""
        mock_res = MagicMock(returncode=0, stdout="ok", stderr="")
        with patch.object(drill_manager, "run_cmd", return_value=mock_res) as mocked_run:
            self.assertTrue(
                drill_manager.inject_drill("zarf-untracked-image", self.scenarios, quiet=True)
            )
            self.assertTrue(
                any("python:3.11-unseeded-airgap" in call.args[0] for call in mocked_run.call_args_list)
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertTrue(drill_manager.heal_drill("zarf-untracked-image", self.scenarios))
            self.assertTrue(
                any("python:3.11-alpine" in call.args[0] for call in mocked_run.call_args_list)
            )

    def test_mystery_mode_writes_and_clears_state(self) -> None:
        """Verify --mystery records active mystery scenario state and --heal all clears it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / ".active_mystery_drill.json"
            with patch.object(drill_manager, "MYSTERY_STATE_FILE", state_file):
                mock_res = MagicMock(returncode=0, stdout="ok", stderr="")
                with patch.object(drill_manager, "run_cmd", return_value=mock_res):
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        drill_manager.inject_mystery(self.scenarios)
                    self.assertTrue(state_file.exists())
                    data = json.loads(state_file.read_text())
                    self.assertIn(data["scenario_id"], self.scenarios)

                    with redirect_stdout(buf):
                        drill_manager.heal_drill("all", self.scenarios)
                    self.assertFalse(state_file.exists())

    def test_training_manifests_and_oscal_schema(self) -> None:
        """Verify all training-app manifests use namespace 'training-app' and oscal-il5.yaml is valid YAML."""
        manifests_dir = REPO_ROOT / "packages" / "training-app" / "manifests"
        for mf in manifests_dir.glob("*.yaml"):
            docs = list(yaml.safe_load_all(mf.read_text()))
            self.assertGreaterEqual(len(docs), 1)
            for doc in docs:
                if not doc:
                    continue
                if doc.get("kind") != "Namespace":
                    self.assertEqual(
                        doc["metadata"]["namespace"],
                        "training-app",
                        f"{mf.name} has wrong namespace",
                    )

        oscal_path = REPO_ROOT / "docs" / "compliance" / "oscal-il5.yaml"
        oscal_data = yaml.safe_load(oscal_path.read_text())
        self.assertIn("component-definition", oscal_data)
        resources = oscal_data["component-definition"]["back-matter"]["resources"]
        ac3_res = next(
            r for r in resources if r["uuid"] == "c65f7e81-d204-4cc6-93be-1706402f0ff8"
        )
        self.assertIn("allowPrivilegeEscalation", ac3_res["description"])

    def test_shift_left_il5_compliance_controls(self) -> None:
        """
        Shift-left compliance gate: statically enforce DoD IL5 NIST 800-53 controls
        (AC-3, AC-4, SC-8, CM-8) against packages/training-app/manifests/*.yaml
        and verify baseline assessment-results.yaml has zero 'not-satisfied' findings.
        """
        manifests_dir = REPO_ROOT / "packages" / "training-app" / "manifests"
        workloads = []
        netpols = []
        services = []
        namespaces = []

        for mf in sorted(manifests_dir.glob("*.yaml")):
            for doc in yaml.safe_load_all(mf.read_text()):
                if not doc:
                    continue
                kind = doc.get("kind")
                if kind in ("Deployment", "StatefulSet"):
                    workloads.append((mf.name, doc))
                elif kind == "NetworkPolicy":
                    netpols.append((mf.name, doc))
                elif kind == "Service":
                    services.append((mf.name, doc))
                elif kind == "Namespace":
                    namespaces.append((mf.name, doc))

        # AC-3: Every container in every Deployment/StatefulSet must explicitly set allowPrivilegeEscalation: false
        self.assertGreaterEqual(len(workloads), 5, "Expected at least 5 workloads in training-app")
        for filename, wl in workloads:
            wl_name = wl["metadata"]["name"]
            containers = wl["spec"]["template"]["spec"]["containers"]
            for c in containers:
                sec_ctx = c.get("securityContext", {})
                self.assertIn(
                    "allowPrivilegeEscalation",
                    sec_ctx,
                    f"AC-3 violation in {filename} ({wl_name}/{c['name']}): missing securityContext.allowPrivilegeEscalation",
                )
                self.assertFalse(
                    sec_ctx["allowPrivilegeEscalation"],
                    f"AC-3 violation in {filename} ({wl_name}/{c['name']}): allowPrivilegeEscalation must be false",
                )

        # AC-4: NetworkPolicies must exist and enforce Ingress + Egress
        self.assertGreaterEqual(len(netpols), 1, "AC-4 violation: missing NetworkPolicy in training-app")
        for filename, np in netpols:
            policy_types = np.get("spec", {}).get("policyTypes", [])
            self.assertIn("Ingress", policy_types, f"AC-4 violation in {filename}: missing Ingress policyType")
            self.assertIn("Egress", policy_types, f"AC-4 violation in {filename}: missing Egress policyType")

        # SC-8 & CM-8: Services and Namespace inventory
        self.assertGreaterEqual(len(services), 4, "SC-8 violation: missing required Service definitions")
        self.assertEqual(len(namespaces), 1, "CM-8 violation: missing Namespace definition")

        # Verify committed OSCAL Assessment Results artifact has all findings satisfied
        ar_path = REPO_ROOT / "docs" / "compliance" / "assessment-results.yaml"
        ar_data = yaml.safe_load(ar_path.read_text())
        results = ar_data["assessment-results"]["results"]
        self.assertGreaterEqual(len(results), 1)
        for res in results:
            for finding in res.get("findings", []):
                state = finding.get("target", {}).get("status", {}).get("state")
                self.assertEqual(
                    state,
                    "satisfied",
                    f"Unsatisfied control in assessment-results.yaml: {finding.get('target', {}).get('target-id')}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
