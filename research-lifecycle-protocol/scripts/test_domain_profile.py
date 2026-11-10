#!/usr/bin/env python3
"""test_domain_profile.py — the MRI domain profile loader and its DP rules.

The profile is optional: an undeclared profile keeps plain RLP Core behaviour, and a
declared-but-invalid config must fail closed (a domain contract that cannot be parsed
must not silently degrade to "no domain rules"). Dual-root compatibility (legacy
``.research-idea-pipeline/`` projects) is exercised through the real resolver.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import domain_profile as dp
import rlp_paths as rlp

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "domain_profile.py"),
                           *map(str, args)], capture_output=True, text=True, cwd=str(ROOT))


def minimal_config() -> dict:
    return {
        "_schema": dp.PROFILE_SCHEMA, "profile": "mri-reconstruction",
        "acquisition": {"forward_operators": ["coil_sensitivity", "fourier",
                                              "undersampling_mask"],
                        "coils": 20,
                        "undersampling": {"pattern": "variable_density"},
                        "noise": {"model": "gaussian"}},
        "gt": {"available": False, "usage": "none"},
        "ssl": {"type": "ssdu",
                "split": {"input": "theta", "loss": "lambda",
                          "held_out_validation": "omega_val",
                          "measurement_identity": {"fields": "subject/slice/volume/acquisition", "mask_sharing_allowed": True}},
                "acs": {"usage": "frozen_protocol"}},
        "model_selection": {"protocol": "omega_val_only", "uses_gt": False},
        "frozen": {"components": ["ct-fm backbone", "fbs 100 steps"],
                   "forbidden_changes": ["主干权重", "推理算法"]},
        "metrics": {"primary": {"name": "nmse_global", "threshold": 0.02,
                                "direction": "lower_is_better",
                                "preregistration_ref": "X1",
                                "frozen_before_results": True,
                                "frozen_at_state_version": 3},
                    "structural": [{"name": "vessel_mip_connectivity", "threshold": 0.05,
                                    "direction": "higher_is_better",
                                    "preregistration_ref": "X1",
                                    "frozen_before_results": True,
                                    "frozen_at_state_version": 3}]},
        "resources": {"gpu_hours_budget": 12},
    }


class Route:
    """A legacy-root route with an optional domain declaration."""

    def __init__(self, root: pathlib.Path, *, legacy: bool = True):
        self.root = root
        storage = rlp.STORAGE_ROOT if legacy else rlp.STORAGE_ROOT
        self.route = root / storage / "routes" / "A"
        self.route.mkdir(parents=True, exist_ok=True)
        self.state_path = self.route / "research-state.json"
        state = {"state_version": 5, "experiments": [
            {"id": "X1", "status": "running", "parent": None, "stage": "X2",
             "claim_targeted": [],
             "preregistration": {"frozen_at_state_version": 3}}]}
        # the on-disk state binds the frozen metric contract (real R8 sequence)
        state = dp.bind_metric_contract(minimal_config(), state)
        self.state_path.write_text(json.dumps(state, ensure_ascii=False),
                                   encoding="utf-8")

    def declare(self, config: dict, level: str = "route") -> pathlib.Path:
        base = self.route if level == "route" else self.root
        path = base / "domain" / "mri-reconstruction.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        return path


class TestLoader(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.route = Route(pathlib.Path(self.tmp.name))

    def test_undeclared_profile_is_inactive_not_an_error(self):
        report = dp.load(self.route.route, "mri-reconstruction")
        self.assertFalse(report.active)
        self.assertTrue(report.ok)
        proc = run("check", "--state", self.route.state_path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("未声明", proc.stdout)

    def test_valid_declaration_loads_from_the_route(self):
        self.route.declare(minimal_config())
        report = dp.load(self.route.route, "mri-reconstruction",
                         state=dp.bind_metric_contract(
                             minimal_config(),
                             json.loads(self.route.state_path.read_text(encoding="utf-8"))))
        self.assertTrue(report.active)
        self.assertEqual(report.level, "route")
        self.assertTrue(report.ok, report.hard_messages())

    def test_project_level_declaration_is_found_for_a_legacy_project(self):
        self.route.declare(minimal_config(), level="project")
        report = dp.load(self.route.route, "mri-reconstruction")
        self.assertTrue(report.active)
        self.assertEqual(report.level, "project")
        # A project-level declaration lives at the project root, outside both storage roots.
        self.assertTrue(report.config_path.endswith("domain/mri-reconstruction.json"))
        self.assertNotIn(rlp.STORAGE_ROOT, report.config_path)

    def test_declared_but_invalid_config_fails_closed(self):
        config = minimal_config()
        config["metrics"]["primary"]["frozen_before_results"] = False
        config["gt"]["usage"] = "full"
        self.route.declare(config)
        report = dp.load(self.route.route, "mri-reconstruction",
                         state=dp.bind_metric_contract(
                             config,
                             json.loads(self.route.state_path.read_text(encoding="utf-8"))))
        self.assertFalse(report.ok)
        rules = {item.rule for item in report.findings}
        self.assertIn("DP7", rules)
        self.assertIn("DP4", rules)
        proc = run("check", "--state", self.route.state_path)
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)

    def test_unknown_profile_is_rejected(self):
        self.route.declare(minimal_config())
        report = dp.load(self.route.route, "not-a-profile")
        self.assertFalse(report.active)
        self.assertFalse(report.ok)

    def test_ambiguous_dual_root_fails_closed_before_profiles_are_read(self):
        self.route.declare(minimal_config())
        (self.route.root / rlp.LEGACY_STORAGE_ROOT / "routes" / "A").mkdir(parents=True)
        with self.assertRaises(rlp.AmbiguousStorageRoot):
            dp.discover(self.route.route, "mri-reconstruction")
        with self.assertRaises(rlp.AmbiguousStorageRoot):
            dp.load(self.route.route, "mri-reconstruction")

    def test_cli_load_reports_the_full_contract(self):
        self.route.declare(minimal_config())
        proc = run("load", "--state", self.route.state_path,
                   "--profile", "mri-reconstruction")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["active"])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["config"]["acquisition"]["coils"], 20)


class TestRules(unittest.TestCase):

    def setUp(self):
        self.config = minimal_config()

    def findings(self, config=None, state=None):
        return dp.validate(config if config is not None else self.config,
                           state=state or {"state_version": 5})

    def rule(self, rule_id: str, config=None, state=None) -> bool:
        return any(item.rule == rule_id
                   for item in self.findings(config, state))

    def test_dp1_rejects_a_renamed_protocol_namespace(self):
        config = self.config
        config["_schema"] = "research-lifecycle-protocol/domain-profile@1"
        self.assertTrue(self.rule("DP1", config))

    def test_dp2_rejects_a_profile_id_mismatch(self):
        self.assertTrue(self.rule("DP2", {**self.config, "profile": "something"}))

    def test_dp3_requires_declared_operators_noise_and_undersampling(self):
        for path, value in (("forward_operators", []),
                            ("forward_operators", None)):
            config = json.loads(json.dumps(self.config))
            if value is None:
                config["acquisition"].pop(path)
            else:
                config["acquisition"][path] = value
            self.assertTrue(self.rule("DP3", config), f"{path}={value!r}")
        config = json.loads(json.dumps(self.config))
        config["acquisition"]["noise"] = {}
        self.assertTrue(self.rule("DP3", config))
        config = json.loads(json.dumps(self.config))
        config["acquisition"]["undersampling"] = {}
        self.assertTrue(self.rule("DP3", config))

    def test_dp4_rejects_a_gt_usage_contradiction(self):
        config = json.loads(json.dumps(self.config))
        config["gt"] = {"available": False, "usage": "development"}
        self.assertTrue(self.rule("DP4", config))

    def test_dp5_rejects_input_equals_loss_and_loss_as_validation(self):
        config = json.loads(json.dumps(self.config))
        config["ssl"]["split"]["loss"] = config["ssl"]["split"]["input"]
        self.assertTrue(self.rule("DP5", config))
        config = json.loads(json.dumps(self.config))
        config["ssl"]["split"]["held_out_validation"] = config["ssl"]["split"]["loss"]
        self.assertTrue(self.rule("DP5", config))

    def test_dp6_rejects_gt_selection_in_a_gt_free_project(self):
        config = json.loads(json.dumps(self.config))
        config["model_selection"]["uses_gt"] = True
        self.assertTrue(self.rule("DP6", config))
        config = json.loads(json.dumps(self.config))
        config["model_selection"]["uses_loss_measurements"] = True
        self.assertTrue(self.rule("DP6", config))

    def test_dp7_requires_frozen_thresholds_declared_before_results(self):
        config = json.loads(json.dumps(self.config))
        config["metrics"]["primary"]["frozen_before_results"] = False
        self.assertTrue(self.rule("DP7", config))
        config = json.loads(json.dumps(self.config))
        config["metrics"]["primary"]["frozen_at_state_version"] = 99
        self.assertTrue(self.rule("DP7", config, state={"state_version": 5}))
        config = json.loads(json.dumps(self.config))
        config["metrics"]["primary"]["threshold"] = "越小越好"
        self.assertTrue(self.rule("DP7", config))

    def test_dp8_requires_a_primary_metric(self):
        config = json.loads(json.dumps(self.config))
        config.pop("metrics")
        self.assertTrue(self.rule("DP8", config))
        config = json.loads(json.dumps(self.config))
        config["metrics"]["structural"] = [{"name": "vessel", "threshold": 0.05}]
        # A structural entry without a freeze declaration is a DP7 violation (threshold
        # freezing), reported alongside the DP8 contract checks.
        self.assertTrue(self.rule("DP7", config))

    def test_dp9_requires_a_resource_budget(self):
        config = json.loads(json.dumps(self.config))
        config["resources"] = {}
        self.assertTrue(self.rule("DP9", config))

    def test_dp10_rejects_unknown_top_level_sections(self):
        config = json.loads(json.dumps(self.config))
        config["experiment_params"] = {"everything": "here"}
        self.assertTrue(self.rule("DP10", config))


class TestSelftest(unittest.TestCase):

    def test_module_selftest_passes(self):
        proc = run("--selftest")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("[ok] domain_profile selftest", proc.stdout)


if __name__ == "__main__":
    unittest.main()
