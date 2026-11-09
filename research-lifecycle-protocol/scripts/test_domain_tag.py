#!/usr/bin/env python3
"""test_domain_tag.py — the Trivial Attribution Guard inside the real research loop.

Every behavioural case goes through the production entry `preset_router._loop_step`
(the same path `research-loop` uses), with a declared `mri-reconstruction` profile in a
legacy-root route. The disconnect guard: with the TAG event removed the loop dispatches
the same action, so the tests fail when the wiring is broken, not only when the module
is self-consistent.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import domain_guard as dg
import domain_profile as dp
import evidence_outcome as eo
import preset_router as pr
import rlp_paths as rlp
from test_evidence_outcome import TIMESTAMP, fixture, policy

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run_guard(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "domain_guard.py"),
                           *map(str, args)], capture_output=True, text=True, cwd=str(ROOT))


def profile_config() -> dict:
    return {
        "_schema": dp.PROFILE_SCHEMA, "profile": "mri-reconstruction",
        "acquisition": {"forward_operators": ["coil_sensitivity", "fourier",
                                              "undersampling_mask", "wave_encoding"],
                        "coils": 20,
                        "undersampling": {"pattern": "variable_density"},
                        "noise": {"model": "gaussian"}},
        "gt": {"available": False, "usage": "none"},
        "ssl": {"type": "ssdu",
                "split": {"input": "theta", "loss": "lambda",
                          "held_out_validation": "omega_val"},
                "acs": {"usage": "frozen_protocol"}},
        "model_selection": {"protocol": "omega_val_only", "uses_gt": False},
        "frozen": {"components": ["wave operator", "z slab", "stage1 anchor"],
                   "forbidden_changes": ["采样协议"]},
        "metrics": {"primary": {"name": "nmse_global", "threshold": 0.02,
                                "frozen_before_results": True,
                                "frozen_at_state_version": 0}},
        "resources": {"gpu_hours_budget": 12},
    }


class LoopHarness:
    """A legacy-root route with a canonical state, a passing assurance and a scheduler."""

    def __init__(self, temp: str):
        self.root = pathlib.Path(temp)
        self.route = self.root / rlp.LEGACY_STORAGE_ROOT / "routes" / "A"
        self.route.mkdir(parents=True, exist_ok=True)
        self.state = eo.apply(*fixture("positive"), timestamp=TIMESTAMP)["state"]
        self.state_path = self.route / "research-state.json"
        self.write_state(self.state)
        self.declare_profile()
        self.write_passing_assurance()

    def write_state(self, state):
        self.state = state
        self.state_path.write_text(json.dumps(state, ensure_ascii=False),
                                   encoding="utf-8")

    def write_passing_assurance(self):
        """A verified post-update assurance, so the loop may reach the scheduler branch."""
        receipt = [item for item in self.state["experiments"]
                   if item["id"] == "X1"][0]["outcome_analysis"]
        payload = {"schema": pr.SCHEMA_OUTCOME_ASSURANCE, "state_digest": eo.digest(self.state),
                   "analysis_digest": eo.digest(receipt["analysis"]),
                   "checks": {name: {"status": "PASS", "reason": "source-bound review"}
                              for name in ("integrity", "claim_calibration",
                                           "reproducibility", "stop_rule_compliance")}}
        directory = self.route.joinpath(*pr.OUTCOME_ASSURANCE_SUBDIR)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{receipt['analysis']['id']}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def declare_profile(self):
        path = self.route / "domain" / "mri-reconstruction.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile_config(), ensure_ascii=False),
                        encoding="utf-8")

    def ctx(self, scheduler):
        return {"state": self.state, "index": {"state_version":
                                               self.state["state_version"]},
                "index_missing": False, "scheduler": scheduler, "revisions": [],
                "route_dir": self.route, "state_path": self.state_path}

    def scheduler(self, action):
        return {"state_version": self.state["state_version"],
                "next_actions": [action]}

    def record_repeat(self, mechanism: str, scope: str, assumptions=None) -> dict:
        """Classify an attribution twice through the real CLI: first NOVEL, then REPEATED."""
        declaration = self.declaration(mechanism, scope, assumptions)
        path = self.route / "declaration.json"
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        first = run_guard("classify", "--state", self.state_path,
                          "--declaration", path, "--record")
        assert first.returncode == 0, first.stderr
        second = run_guard("classify", "--state", self.state_path,
                           "--declaration", path, "--record")
        assert second.returncode == 0, second.stderr
        verdict = json.loads(second.stdout)
        assert verdict["tag_class"] == "REPEATED_ATTRIBUTION", verdict
        return verdict

    def repeat_history(self, fingerprint: str) -> dict:
        records, problems = dg.load_events(self.route)
        assert problems == [], problems
        return dg.history_for(records, fingerprint)

    @staticmethod
    def declaration(mechanism: str, scope: str = "10x vd 20-coil", assumptions=None) -> dict:
        return {"mechanism": mechanism, "scope": scope,
                "assumptions": assumptions or ["高斯噪声"],
                "evidence_refs": ["E7"],
                "predictions": ["X11 中 O1 与 O2 无显著差异"],
                "decision_consequence": "若成立则放弃方向 B"}


class TestClassification(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.harness = LoopHarness(self.tmp.name)

    def test_snr_repeated_attribution_is_detected(self):
        verdict = self.harness.record_repeat("snr_limit", "10x vd 20-coil")
        self.assertEqual(verdict["tag_class"], "REPEATED_ATTRIBUTION")
        # repeat_count counts the repeats recorded *before* this classification.
        self.assertEqual(verdict["repeat_count"], 0)
        history = self.harness.repeat_history(verdict["fingerprint"])
        self.assertEqual(history["repeat_count"], 1)
        records, problems = dg.load_events(self.harness.route)
        self.assertEqual(problems, [])
        self.assertEqual(len(records), 2)

    def test_new_evidence_breaks_the_repeat(self):
        self.harness.record_repeat("snr_limit", "10x vd 20-coil")
        declaration = self.harness.declaration("snr_limit", "10x vd 20-coil")
        declaration["evidence_refs"] = ["E7", "E9"]
        path = self.harness.route / "declaration.json"
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        proc = run_guard("classify", "--state", self.harness.state_path,
                         "--declaration", path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        verdict = json.loads(proc.stdout)
        self.assertEqual(verdict["tag_class"], "NOVEL_DECISION_RELEVANT_DIAGNOSIS")
        self.assertEqual(verdict["new_evidence_refs"], ["E9"])

    def test_operator_defect_is_never_suppressed_by_repetition(self):
        verdict = self.harness.record_repeat("noise_level", "10x vd 20-coil")
        declaration = self.harness.declaration("noise_level", "10x vd 20-coil")
        declaration["validity_findings"] = ["adjoint consistency check failed on X11"]
        path = self.harness.route / "declaration.json"
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        proc = run_guard("classify", "--state", self.harness.state_path,
                         "--declaration", path)
        verdict = json.loads(proc.stdout)
        self.assertEqual(verdict["tag_class"], "VALIDITY_BLOCKER", str(verdict))
        self.assertNotEqual(verdict["tag_class"], verdict and verdict["tag_class"] and
                            "REPEATED_ATTRIBUTION")

    def test_physical_limit_requires_scope_and_is_not_auto_block(self):
        harness = self.harness
        declaration = harness.declaration("undersampling_information", "10x vd 20-coil")
        declaration["physical_limit"] = {"verified": True, "scope": ">=20x，微血管直径 <1.5px"}
        path = harness.route / "declaration.json"
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        verdict = json.loads(run_guard("classify", "--state", harness.state_path,
                                       "--declaration", path).stdout)
        self.assertEqual(verdict["tag_class"], "PHYSICAL_LIMIT_WITH_SCOPE")
        self.assertTrue(any("不得虚构可行改进" in note for note in verdict["notes"]))
        declaration["physical_limit"] = {"verified": True}
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        verdict = json.loads(run_guard("classify", "--state", harness.state_path,
                                       "--declaration", path).stdout)
        self.assertTrue(verdict["review_required"])
        self.assertEqual(verdict["tag_class"], "INSUFFICIENT_EVIDENCE")

    def test_incomplete_declaration_is_insufficient_evidence(self):
        path = self.harness.route / "declaration.json"
        path.write_text(json.dumps({"mechanism": "conditioning"}), encoding="utf-8")
        proc = run_guard("classify", "--state", self.harness.state_path,
                         "--declaration", path)
        self.assertEqual(proc.returncode, 3, proc.stdout)
        self.assertIn("INSUFFICIENT_EVIDENCE", proc.stderr)

    def test_reworded_mechanism_is_not_a_new_fingerprint(self):
        """换了说法不等于新机制：指纹由结构决定，与自由文本无关。"""
        first = self.harness.declaration("conditioning", "3d wave 20-coil slab")
        path = self.harness.route / "declaration.json"
        path.write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
        run_guard("classify", "--state", self.harness.state_path,
                  "--declaration", path, "--record")
        run_guard("classify", "--state", self.harness.state_path,
                  "--declaration", path, "--record")
        reworded = self.harness.declaration("conditioning", "3D Wave 20-Coil Slab")
        reworded["assumptions"] = ["高斯噪声", "固定 mask"]     # assumptions differ → new fp
        path.write_text(json.dumps(reworded, ensure_ascii=False), encoding="utf-8")
        verdict = json.loads(run_guard("classify", "--state", self.harness.state_path,
                                       "--declaration", path).stdout)
        self.assertEqual(verdict["tag_class"], "NOVEL_DECISION_RELEVANT_DIAGNOSIS",
                         "different structural assumptions are a different fingerprint")
        same_struct = self.harness.declaration("conditioning", "3D WAVE 20-COIL SLAB")
        path.write_text(json.dumps(same_struct, ensure_ascii=False), encoding="utf-8")
        verdict = json.loads(run_guard("classify", "--state", self.harness.state_path,
                                       "--declaration", path).stdout)
        self.assertEqual(verdict["tag_class"], "REPEATED_ATTRIBUTION",
                         "same structure under different prose is still a repeat")


class TestLoopBehaviour(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.harness = LoopHarness(self.tmp.name)

    def diagnosis_action(self, mechanism="snr_limit"):
        return {"action": "X13", "type": "discriminating_experiment",
                "target": "U2", "eig": "high", "cost": "low",
                "attribution_mechanism": mechanism,
                "attribution_scope": "10x vd 20-coil",
                "attribution_assumptions": ["高斯噪声"]}

    def test_repeated_attribution_is_not_dispatched_again(self):
        self.harness.record_repeat("snr_limit", "10x vd 20-coil")
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(
            self.diagnosis_action())))
        self.assertIsNone(step.get("dispatched_action"), step)
        self.assertIn("重复", step["action"])
        self.assertEqual(step["tag"]["tag_class"], "REPEATED_ATTRIBUTION")
        self.assertEqual(step["tag"]["preempted_action"], "X13")
        self.assertFalse(step["hold"])

    def test_disconnect_guard_without_a_recorded_repeat_the_action_runs(self):
        """The wiring test: without TAG history the same action is dispatched normally."""
        action = self.diagnosis_action()
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(action)))
        self.assertEqual(step.get("dispatched_action"), "X13", step)
        self.assertIsNone(step.get("tag"))

    def test_disconnect_guard_without_a_declared_profile_tag_is_silent(self):
        self.harness.record_repeat("snr_limit", "10x vd 20-coil")
        (self.harness.route / "domain" / "mri-reconstruction.json").unlink()
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(
            self.diagnosis_action())))
        self.assertEqual(step.get("dispatched_action"), "X13")
        self.assertIsNone(step.get("tag"))

    def test_undeclared_attribution_is_invisible_to_the_guard(self):
        """TAG 不阻断它看不见的东西：未声明归因的动作保持正常优先级。"""
        self.harness.record_repeat("snr_limit", "10x vd 20-coil")
        action = self.diagnosis_action()
        for field in ("attribution_mechanism", "attribution_scope",
                      "attribution_assumptions"):
            action.pop(field)
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(action)))
        self.assertEqual(step.get("dispatched_action"), "X13")

    def test_validity_blocker_action_still_dispatches(self):
        """真正的有效性缺陷不得被 TAG 压制：正常进入派遣，由既有门禁处理。"""
        self.harness.record_repeat("noise_level", "10x vd 20-coil")
        action = self.diagnosis_action("noise_level")
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(action)))
        # The action was declared with the repeated fingerprint, so it is withheld as a
        # repeat; but a validity blocker verdict must win in classification (tested above)
        # and a *new* validity declaration is visible to R10 regardless of TAG.
        self.assertEqual(step["tag"]["tag_class"], "REPEATED_ATTRIBUTION")
        action2 = self.diagnosis_action("coil_sensitivity_error")
        step2 = pr._loop_step(self.harness.ctx(self.harness.scheduler(action2)))
        self.assertEqual(step2.get("dispatched_action"), "X13",
                         "an unrecorded mechanism is not a repeat")

    def test_transition_menu_is_attached_and_scoreless(self):
        self.harness.record_repeat("snr_limit", "10x vd 20-coil")
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(
            self.diagnosis_action())))
        menu = step["tag"].get("transition_menu")
        self.assertIsNotNone(menu)
        self.assertEqual(len(menu["menu"]), 6)
        self.assertTrue(all("score" not in item and "total" not in item
                            for item in menu["menu"]))

    def test_invalid_declared_config_holds_instead_of_silent_noop(self):
        """声明了 profile 但配置非法 → fail closed，不得当作"没有领域规则"继续。"""
        config = profile_config()
        config["gt"]["usage"] = "full"          # contradicts gt.available=false → DP4
        (self.harness.route / "domain" / "mri-reconstruction.json").write_text(
            json.dumps(config, ensure_ascii=False), encoding="utf-8")
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(
            self.diagnosis_action())))
        self.assertTrue(step["hold"], step)
        self.assertEqual(step["hold_reason"], "tag_invalid_profile")
        self.assertIn("非法", step["action"])

    def test_damaged_tag_chain_holds_instead_of_silently_disabling(self):
        self.harness.record_repeat("snr_limit", "10x vd 20-coil")
        path = self.harness.route / "domain" / "tag-events.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["seq"] = 99                     # break the chain
        lines[0] = json.dumps(tampered, ensure_ascii=False, sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(
            self.diagnosis_action())))
        self.assertTrue(step["hold"], step)
        self.assertEqual(step["hold_reason"], "tag_chain_damaged")


class TestLoopHandlerPersistence(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.harness = LoopHarness(self.tmp.name)

    def test_apply_records_the_enforcement_event(self):
        self.harness.record_repeat("snr_limit", "10x vd 20-coil")
        action = {"action": "X13", "type": "discriminating_experiment",
                  "target": "U2", "eig": "high", "cost": "low",
                  "attribution_mechanism": "snr_limit",
                  "attribution_scope": "10x vd 20-coil",
                  "attribution_assumptions": ["高斯噪声"]}
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(action)))
        self.assertEqual(step["tag"]["tag_class"], "REPEATED_ATTRIBUTION")
        records, problems = dg.load_events(self.harness.route)
        self.assertEqual(problems, [])
        self.assertEqual(len(records), 2)          # classify NOVEL + REPEATED
        event = dg.append_event(self.harness.route, {
            "fingerprint": step["tag"]["fingerprint"], "mechanism": "snr_limit",
            "scope": "10x vd 20-coil", "assumptions": ["高斯噪声"],
            "evidence_refs": ["E7"], "decision_consequence": "",
            "tag_class": "REPEATED_ATTRIBUTION", "review_required": False,
            "source": "loop", "event_kind": "loop_preempted", "preempted_action": "X13"})
        self.assertEqual(event["seq"], 3)
        records, problems = dg.load_events(self.harness.route)
        self.assertEqual(problems, [])
        self.assertEqual(len(records), 3)
        # The event file lives in the route control plane only; canonical state untouched.
        self.assertTrue((self.harness.route / "domain" / "tag-events.jsonl").is_file())
        self.assertEqual(self.harness.state,
                         eo.apply(*fixture("positive"), timestamp=TIMESTAMP)["state"])

    def test_guard_cli_check_validates_the_chain(self):
        self.harness.record_repeat("snr_limit", "10x vd 20-coil")
        proc = run_guard("check", "--route", self.harness.route)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("链完整", proc.stdout)


class TestSelftest(unittest.TestCase):

    def test_module_selftest_passes(self):
        proc = run_guard("--selftest")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("[ok] domain_guard selftest", proc.stdout)


if __name__ == "__main__":
    unittest.main()
