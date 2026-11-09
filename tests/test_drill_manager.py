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


if __name__ == "__main__":
    unittest.main(verbosity=2)
