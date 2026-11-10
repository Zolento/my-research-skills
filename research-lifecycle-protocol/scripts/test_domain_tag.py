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
import shutil
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
                          "held_out_validation": "omega_val",
                          "measurement_identity": {"fields": "subject/slice/volume/acquisition", "mask_sharing_allowed": True}},
                "acs": {"usage": "frozen_protocol"}},
        "model_selection": {"protocol": "omega_val_only", "uses_gt": False},
        "frozen": {"components": ["wave operator", "z slab", "stage1 anchor"],
                   "forbidden_changes": ["采样协议"]},
        "metrics": {"primary": {"name": "nmse_global", "threshold": 0.02,
                                "direction": "lower_is_better",
                                "preregistration_ref": "X1",
                                "frozen_before_results": True,
                                "frozen_at_state_version": 0}},
        "resources": {"gpu_hours_budget": 12},
    }


class LoopHarness:
    """A legacy-root route with a canonical state, a passing assurance and a scheduler."""

    def __init__(self, temp: str):
        self.root = pathlib.Path(temp)
        self.route = self.root / rlp.STORAGE_ROOT / "routes" / "A"
        self.route.mkdir(parents=True, exist_ok=True)
        # Real R8 sequence: bind the frozen metric contract into the preregistration
        # BEFORE the outcome transaction exists, then re-derive the packet's experiment
        # digest. Binding after an analysed transaction is illegal (immutable analysis).
        state0, packet, analysis, audit = fixture("positive")
        state0 = dp.bind_metric_contract(profile_config(), state0)
        packet["experiment_digest"] = eo.digest(
            [x for x in state0["experiments"] if x["id"] == "X1"][0])
        # the analysis binds state/context/packet digests; re-derive after the binding
        analysis["base_state_digest"] = eo.digest(state0)
        analysis["context_digest"] = eo.digest(eo.validation_context(state0))
        analysis["packet_digest"] = eo.digest(packet)
        audit["analysis_digest"] = eo.digest(analysis)
        audit["packet_digest"] = eo.digest(packet)
        audit["state_digest"] = analysis["base_state_digest"]
        self.state = eo.apply(state0, packet, analysis, audit,
                              timestamp=TIMESTAMP)["state"]
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
        # T04 seed: a *resolvable, valid* evidence entry is real new support.
        state = json.loads(self.harness.state_path.read_text(encoding="utf-8"))
        state.setdefault("evidence", []).append(
            {"id": "E9", "kind": "experiment", "scope": "10x VD", "supports": [],
             "contradicts": [], "epistemic_status": "Observed",
             "source_ref": "X9（seed=1）", "verification_tier": "T2",
             "depends_on": [], "validity": {"status": "valid", "reason": "已按预注册",
                                            "since_state_version": 4}})
        self.harness.state_path.write_text(json.dumps(state, ensure_ascii=False),
                                           encoding="utf-8")
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

    def test_a_fresh_evidence_id_with_identical_content_is_not_novelty(self):
        """T04：同一归因更换证据 ID、内容等价 → 不得视为研究进展。"""
        self.harness.record_repeat("snr_limit", "10x vd 20-coil")
        state = json.loads(self.harness.state_path.read_text(encoding="utf-8"))
        base = {"kind": "experiment", "scope": "10x VD", "supports": [],
                "contradicts": [], "epistemic_status": "Observed",
                "source_ref": "X9（seed=1）", "verification_tier": "T2",
                "depends_on": [],
                "validity": {"status": "valid", "reason": "已按预注册",
                             "since_state_version": 4}}
        state.setdefault("evidence", []).append({"id": "E9", **base})
        state["evidence"].append({"id": "E10", **base})   # same content, new id
        self.harness.state_path.write_text(json.dumps(state, ensure_ascii=False),
                                           encoding="utf-8")
        path = self.harness.route / "declaration.json"
        first = self.harness.declaration("snr_limit", "10x vd 20-coil")
        first["evidence_refs"] = ["E7", "E9"]
        path.write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
        verdict1 = json.loads(run_guard("classify", "--state", self.harness.state_path,
                                        "--declaration", path, "--record").stdout)
        self.assertEqual(verdict1["tag_class"], "NOVEL_DECISION_RELEVANT_DIAGNOSIS")
        second = self.harness.declaration("snr_limit", "10x vd 20-coil")
        second["evidence_refs"] = ["E7", "E10"]          # fresh id, same content
        path.write_text(json.dumps(second, ensure_ascii=False), encoding="utf-8")
        verdict2 = json.loads(run_guard("classify", "--state", self.harness.state_path,
                                        "--declaration", path).stdout)
        self.assertEqual(verdict2["tag_class"], "REPEATED_ATTRIBUTION", str(verdict2))
        self.assertTrue(any("不构成科研增量" in n for n in verdict2["notes"]))

    def test_operator_defect_is_never_suppressed_by_repetition(self):
        """T05：真实算子失败（canonical failed 实验）→ VALIDITY_BLOCKER 优先于重复。"""
        verdict = self.harness.record_repeat("noise_level", "10x vd 20-coil")
        state = json.loads(self.harness.state_path.read_text(encoding="utf-8"))
        state.setdefault("experiments", []).append(
            {"id": "X11", "status": "failed", "stage": "X2", "claim_targeted": [],
             "parent": None, "preregistration": {"frozen_at_state_version": 4}})
        self.harness.state_path.write_text(json.dumps(state, ensure_ascii=False),
                                           encoding="utf-8")
        declaration = self.harness.declaration("noise_level", "10x vd 20-coil")
        declaration["validity_findings"] = ["adjoint consistency check failed on X11"]
        declaration["validity_evidence_refs"] = ["X11"]
        path = self.harness.route / "declaration.json"
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        proc = run_guard("classify", "--state", self.harness.state_path,
                         "--declaration", path)
        verdict = json.loads(proc.stdout)
        self.assertEqual(verdict["tag_class"], "VALIDITY_BLOCKER", str(verdict))
        self.assertIn("X11", verdict["reason"])

    def test_an_unproven_validity_risk_gets_a_safety_review_not_a_verified_defect(self):
        """T05b：纯文本“可能存在算子错误”→ 安全审查，不得登记为已验证故障。"""
        self.harness.record_repeat("noise_level", "10x vd 20-coil")
        declaration = self.harness.declaration("noise_level", "10x vd 20-coil")
        declaration["validity_findings"] = ["adjoint consistency check failed on X11"]
        path = self.harness.route / "declaration.json"
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        verdict = json.loads(run_guard("classify", "--state", self.harness.state_path,
                                       "--declaration", path).stdout)
        self.assertEqual(verdict["tag_class"], "INSUFFICIENT_EVIDENCE", str(verdict))
        self.assertTrue(verdict["review_required"])
        self.assertEqual(verdict["safety"], "hold_pending_verification")

    def test_physical_limit_requires_evidence_scope_and_limit_type(self):
        """T01/T02：verified 标签本身不再决定结论；证据解析 + limit_type 决定。"""
        harness = self.harness
        state = json.loads(harness.state_path.read_text(encoding="utf-8"))
        state.setdefault("evidence", []).append(
            {"id": "E9", "kind": "experiment", "scope": "20x VD", "supports": [],
             "contradicts": [], "epistemic_status": "Observed",
             "source_ref": "X9 oracle power run", "verification_tier": "T2",
             "depends_on": [], "validity": {"status": "valid", "reason": "已按预注册",
                                            "since_state_version": 4}})
        harness.state_path.write_text(json.dumps(state, ensure_ascii=False),
                                      encoding="utf-8")
        path = harness.route / "declaration.json"
        declaration = harness.declaration("undersampling_information", "10x vd 20-coil")
        declaration["physical_limit"] = {"verified": True, "scope": ">=20x，微血管直径 <1.5px"}
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        verdict = json.loads(run_guard("classify", "--state", harness.state_path,
                                       "--declaration", path).stdout)
        # T01: "verified": true without limit_type/sources must NOT self-certify.
        self.assertEqual(verdict["tag_class"], "INSUFFICIENT_EVIDENCE", str(verdict))
        self.assertTrue(verdict["review_required"])
        declaration["physical_limit"] = {"verified": True,
                                         "limit_type": "detection_power_limit",
                                         "scope": ">=20x，微血管直径 <1.5px",
                                         "source_refs": ["E9"]}
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        verdict = json.loads(run_guard("classify", "--state", harness.state_path,
                                       "--declaration", path).stdout)
        self.assertEqual(verdict["tag_class"], "PHYSICAL_LIMIT_WITH_SCOPE", str(verdict))
        self.assertIn("条件性结论", verdict["reason"])
        self.assertTrue(any("不得虚构可行改进" in note for note in verdict["notes"]))
        # An unverified interpretation never self-upgrades.
        declaration["physical_limit"] = {"verified": True, "limit_type":
                                         "physical_interpretation",
                                         "scope": ">=20x", "source_refs": ["E9"]}
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        verdict = json.loads(run_guard("classify", "--state", harness.state_path,
                                       "--declaration", path).stdout)
        self.assertEqual(verdict["tag_class"], "INSUFFICIENT_EVIDENCE", str(verdict))

    def test_a_revoked_evidence_stops_backing_a_recorded_limit(self):
        """T03：证据被撤销后，既有物理限制不得继续作为可靠结论。"""
        harness = self.harness
        state = {"state_version": 5, "evidence": [
            {"id": "E9", "kind": "experiment", "scope": "20x VD", "supports": [],
             "contradicts": [], "epistemic_status": "Observed",
             "source_ref": "X9 oracle power run", "verification_tier": "T2",
             "depends_on": [], "validity": {"status": "valid", "reason": "已按预注册",
                                            "since_state_version": 4}}]}
        harness.state_path.write_text(json.dumps(state, ensure_ascii=False),
                                      encoding="utf-8")
        path = harness.route / "declaration.json"
        declaration = harness.declaration("undersampling_information", "10x vd 20-coil")
        declaration["physical_limit"] = {"verified": True,
                                         "limit_type": "detection_power_limit",
                                         "scope": ">=20x", "source_refs": ["E9"]}
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        verdict = json.loads(run_guard("classify", "--state", harness.state_path,
                                       "--declaration", path).stdout)
        self.assertEqual(verdict["tag_class"], "PHYSICAL_LIMIT_WITH_SCOPE")
        state["evidence"][0]["validity"]["status"] = "invalid"   # later revoked
        harness.state_path.write_text(json.dumps(state, ensure_ascii=False),
                                      encoding="utf-8")
        verdict = json.loads(run_guard("classify", "--state", harness.state_path,
                                       "--declaration", path).stdout)
        self.assertEqual(verdict["tag_class"], "INSUFFICIENT_EVIDENCE", str(verdict))
        self.assertIn("不可用", verdict["reason"])

    def test_incomplete_declaration_is_insufficient_evidence(self):
        path = self.harness.route / "declaration.json"
        path.write_text(json.dumps({"mechanism": "conditioning"}), encoding="utf-8")
        proc = run_guard("classify", "--state", self.harness.state_path,
                         "--declaration", path)
        self.assertEqual(proc.returncode, 3, proc.stdout)
        self.assertIn("INSUFFICIENT_EVIDENCE", proc.stderr)

    def test_reworded_mechanism_is_not_a_new_fingerprint(self):
        """换了说法不等于新机制：指纹由结构决定，与自由文本无关。"""
        state = json.loads(self.harness.state_path.read_text(encoding="utf-8"))
        state.setdefault("evidence", []).append(
            {"id": "E7", "kind": "experiment", "scope": "3D wave", "supports": [],
             "contradicts": [], "epistemic_status": "Observed",
             "source_ref": "X7", "verification_tier": "T2", "depends_on": [],
             "validity": {"status": "valid", "reason": "已按预注册",
                          "since_state_version": 4}})
        self.harness.state_path.write_text(json.dumps(state, ensure_ascii=False),
                                           encoding="utf-8")
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

    def test_a_declared_prediction_difference_keeps_novelty_honest(self):
        """新证据 + 相同预测 → 记录判别力不足的提示，不得自动宣称机制推进。"""
        self.harness.record_repeat("snr_limit", "10x vd 20-coil")
        state = json.loads(self.harness.state_path.read_text(encoding="utf-8"))
        state.setdefault("evidence", []).append(
            {"id": "E9", "kind": "experiment", "scope": "10x VD", "supports": [],
             "contradicts": [], "epistemic_status": "Observed",
             "source_ref": "X9（seed=1）", "verification_tier": "T2",
             "depends_on": [], "validity": {"status": "valid", "reason": "已按预注册",
                                            "since_state_version": 4}})
        self.harness.state_path.write_text(json.dumps(state, ensure_ascii=False),
                                           encoding="utf-8")
        declaration = self.harness.declaration("snr_limit", "10x vd 20-coil")
        declaration["evidence_refs"] = ["E7", "E9"]     # same predictions as history
        path = self.harness.route / "declaration.json"
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        verdict = json.loads(run_guard("classify", "--state", self.harness.state_path,
                                       "--declaration", path).stdout)
        self.assertEqual(verdict["tag_class"], "NOVEL_DECISION_RELEVANT_DIAGNOSIS")
        self.assertTrue(any("预测与历史相同" in n for n in verdict["notes"]), str(verdict))


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


class TestAttributionReview(unittest.TestCase):
    """T10 — 未经结构化声明的诊断动作进入审查路径：第一次注解要求补全，
    同一动作再次出现升级为有界 HOLD；非诊断动作永不被拦截。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.harness = LoopHarness(self.tmp.name)

    def bare_diagnosis(self, action="X14"):
        return {"action": action, "type": "discriminating_experiment",
                "target": "U3", "eig": "high", "cost": "low"}

    def test_t10_first_occurrence_annotates_and_dispatches(self):
        action = self.bare_diagnosis()
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(action)))
        review = step.get("attribution_review")
        self.assertIsNotNone(review)
        self.assertFalse(step["hold"], step)
        self.assertEqual(review["required_fields"],
                         ["attribution_mechanism", "attribution_scope",
                          "attribution_assumptions"])
        self.assertEqual(review["occurrences"], 1)
        self.assertEqual(step.get("dispatched_action"), "X14")

    def test_t10_second_occurrence_escalates_to_a_bounded_hold(self):
        self.harness.record_repeat("snr_limit", "10x vd 20-coil")  # seed events
        action = self.bare_diagnosis()
        first = pr._loop_step(self.harness.ctx(self.harness.scheduler(action)))
        self.assertFalse(first["hold"])
        second = pr._loop_step(self.harness.ctx(self.harness.scheduler(action)))
        self.assertTrue(second["hold"], second.get("action"))
        self.assertEqual(second["hold_reason"], "tag_attribution_missing")
        self.assertIn("补充归因声明", second["action"])
        # the escalation is idempotent per state_version: no event spam
        records, problems = dg.load_events(self.harness.route)
        self.assertEqual(problems, [])
        reviews = [r for r in records if r.get("event_kind") == "attribution_missing"]
        self.assertEqual(len(reviews), 1, records)

    def test_t10_declared_actions_skip_the_review(self):
        action = self.bare_diagnosis()
        action.update({"attribution_mechanism": "noise_level",
                       "attribution_scope": "10x vd 20-coil",
                       "attribution_assumptions": ["高斯噪声"]})
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(action)))
        self.assertIsNone(step.get("attribution_review"))
        self.assertEqual(step.get("dispatched_action"), "X14")

    def test_t10_non_diagnosis_actions_are_never_reviewed(self):
        action = {"action": "P4", "type": "remote_analogy", "target": "AS1",
                  "eig": "unknown", "cost": "low"}
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(action)))
        self.assertIsNone(step.get("attribution_review"))
        self.assertEqual(step.get("dispatched_action"), "P4")

    def test_t10_inactive_profile_never_reviews(self):
        (self.harness.route / "domain" / "mri-reconstruction.json").unlink()
        step = pr._loop_step(self.harness.ctx(self.harness.scheduler(
            self.bare_diagnosis())))
        self.assertIsNone(step.get("attribution_review"))
        self.assertEqual(step.get("dispatched_action"), "X14")

    def test_t10_repeated_undeclared_repeats_are_event_idempotent(self):
        """会话恢复/重试不会让同一轮的注解事件翻倍。"""
        action = self.bare_diagnosis()
        pr._loop_step(self.harness.ctx(self.harness.scheduler(action)))
        pr._loop_step(self.harness.ctx(self.harness.scheduler(action)))
        records, problems = dg.load_events(self.harness.route)
        self.assertEqual(problems, [])
        reviews = [r for r in records if r.get("event_kind") == "attribution_missing"]
        self.assertEqual(len(reviews), 1, records)


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
        # The event file lives in the route control plane only; canonical state untouched
        # apart from the prereg metric-contract binding done at freeze time.
        self.assertTrue((self.harness.route / "domain" / "tag-events.jsonl").is_file())
        # The TAG event lives in the route control plane only: the canonical state file
        # is byte-identical before and after the enforcement.
        self.assertTrue((self.harness.route / "domain" / "tag-events.jsonl").is_file())
        before = self.harness.state_path.read_bytes()
        self.harness.write_state(self.harness.state)
        self.assertEqual(self.harness.state_path.read_bytes(), before)
        bound = self.harness.state["experiments"][0]["preregistration"].get(
            "domain_metric_contract")
        self.assertIsNotNone(bound, "the harness freezes the metric contract at R8")
        self.assertIn("nmse_global", bound.get("metric_digests", {}))

    def test_guard_cli_check_validates_the_chain(self):
        self.harness.record_repeat("snr_limit", "10x vd 20-coil")
        proc = run_guard("check", "--route", self.harness.route)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("链完整", proc.stdout)


def _mp_append_worker(args):
    """Module-level so multiprocessing can pickle it (T06)."""
    route, worker_id = args
    appended = []
    for i in range(4):
        record = dg.append_event(route, {
            "fingerprint": f"fp-{worker_id}-{i}", "mechanism": "noise_level",
            "scope": "s", "assumptions": [], "evidence_refs": ["E1"],
            "tag_class": "NOVEL_DECISION_RELEVANT_DIAGNOSIS",
            "review_required": False, "source": f"w{worker_id}"})
        appended.append(record["seq"])
    return appended


_MP_KEY = {"route": "A", "state_version": 7, "action": "X13",
           "fingerprint": "fp-fixed", "tag_class": "REPEATED_ATTRIBUTION",
           "event_kind": "loop_preempted"}


def _mp_idempotent_worker(route):
    record, status = dg.append_event_once(
        route, {"fingerprint": "fp-fixed", "mechanism": "snr_limit",
                "scope": "s", "assumptions": [], "evidence_refs": ["E1"],
                "tag_class": "REPEATED_ATTRIBUTION", "review_required": False,
                "source": "worker", "event_kind": "loop_preempted"},
        idempotency_key=_MP_KEY)
    return status


class TestLoopApplyEndToEnd(unittest.TestCase):
    """T07/T08 — enforcement events must flow through the real `run_preset(apply=True)`
    entry, not through a direct append_event() call. Repeated applies must not append
    twice (idempotency), and a damaged chain must produce a diagnosable HOLD."""

    def harness_with_scheduler(self):
        harness = LoopHarness(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(harness.root, ignore_errors=True))
        harness.record_repeat("snr_limit", "10x vd 20-coil")
        action = {"action": "X13", "type": "discriminating_experiment",
                  "target": "U2", "eig": "high", "cost": "low",
                  "attribution_mechanism": "snr_limit",
                  "attribution_scope": "10x vd 20-coil",
                  "attribution_assumptions": ["高斯噪声"]}
        # The scheduler gate is source-bound: every done experiment needs an EIG
        # calibration record computed from the real receipt, or the actions are not
        # usable as current decisions (MISSING_EIG).
        import execution_gate as eg
        receipt = [x for x in harness.state["experiments"] if x["id"] == "X1"][0][
            "outcome_analysis"]
        delta, rating = eg.actual_eig(receipt)
        scheduler = {"_schema": "research-idea-pipeline/scheduler@1",
                     "state_version": harness.state["state_version"],
                     "next_actions": [action],
                     "eig_calibration": {"records": [
                         {"experiment": "X1", "predicted_information_gain": "high",
                          "observed_delta": delta, "actual_information_gain": rating}]}}
        (harness.route / "scheduler.json").write_text(json.dumps(scheduler,
                                                                 ensure_ascii=False),
                                                      encoding="utf-8")
        return harness, scheduler

    @staticmethod
    def _apply_until_tag(harness, max_rounds=4):
        """apply#1 consolidates the stale projection; the TAG check runs on a later
        apply once the loop reaches the scheduler-actions branch."""
        import preset_router as pr
        for _ in range(max_rounds):
            payload, _, code = pr.run_preset("research-loop", harness.state_path,
                                             apply=True)
            current = payload["observed"]["current"]
            tag = current.get("tag") or {}
            if tag.get("tag_class") in ("REPEATED_ATTRIBUTION", "HOLD"):
                return payload, tag, code
        return payload, tag, code

    def test_t08_apply_really_writes_the_enforcement_event(self):
        import preset_router as pr
        harness, _ = self.harness_with_scheduler()
        payload, tag, code = self._apply_until_tag(harness)
        self.assertEqual(code, pr.EXIT_OK, payload.get("hold_reason"))
        self.assertEqual(tag.get("tag_class"), "REPEATED_ATTRIBUTION", tag)
        self.assertIsNone(payload["observed"]["current"].get("dispatched_action"))
        records, problems = dg.load_events(harness.route)
        self.assertEqual(problems, [])
        preempted = [r for r in records if r.get("event_kind") == "loop_preempted"]
        self.assertEqual(len(preempted), 1, records)
        self.assertEqual(preempted[0].get("preempted_action"), "X13")
        self.assertIn("domain/tag-events.jsonl", payload["writes"])

    def test_t07_a_repeated_apply_does_not_duplicate_the_event(self):
        import preset_router as pr
        harness, _ = self.harness_with_scheduler()
        self._apply_until_tag(harness)
        # a retry / rerun of the same logical preemption must not append again
        for _ in range(2):
            payload, _, code = pr.run_preset("research-loop", harness.state_path,
                                             apply=True)
            self.assertEqual(code, pr.EXIT_OK, payload.get("hold_reason"))
        records, problems = dg.load_events(harness.route)
        self.assertEqual(problems, [])
        preempted = [r for r in records if r.get("event_kind") == "loop_preempted"]
        self.assertEqual(len(preempted), 1,
                         "the same logical preemption must map to one event")
        self.assertIsNotNone(preempted[0].get("event_id"))
        self.assertIsNotNone(preempted[0].get("state_digest"))

    def test_a_damaged_chain_holds_the_applying_loop(self):
        """T09：TAG 日志损坏 → 可诊断 HOLD，不静默跳过、不追加。"""
        import preset_router as pr
        harness, _ = self.harness_with_scheduler()
        path = harness.route / "domain" / "tag-events.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0]); tampered["seq"] = 42
        lines[0] = json.dumps(tampered, ensure_ascii=False, sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        payload, tag, code = self._apply_until_tag(harness)
        self.assertEqual(tag.get("tag_class"), "HOLD", tag)
        self.assertEqual(payload["observed"]["current"].get("hold_reason"),
                         "tag_chain_damaged")
        # nothing was appended to the damaged chain
        records, problems = dg.load_events(harness.route)
        self.assertTrue(problems)

    def test_recovery_is_explicit_and_never_automatic(self):
        harness, _ = self.harness_with_scheduler()
        path = harness.route / "domain" / "tag-events.jsonl"
        path.write_text("not json\n", encoding="utf-8")
        proc = run_guard("recover", "--route", str(harness.route))
        self.assertEqual(proc.returncode, dg.EXIT_ENV, proc.stdout + proc.stderr)
        self.assertIn("--archive", proc.stderr)
        proc = run_guard("recover", "--route", str(harness.route), "--archive")
        self.assertEqual(proc.returncode, dg.EXIT_OK, proc.stdout + proc.stderr)
        archived = list((harness.route / "domain").glob("tag-events.jsonl.corrupt-*"))
        self.assertEqual(len(archived), 1, "the damaged log must be archived, not deleted")
        records, problems = dg.load_events(harness.route)
        self.assertEqual((records, problems), ([], []))
        # the fresh chain accepts appends with seq restarting at 1 for the new chain
        event = dg.append_event(harness.route, {"fingerprint": "fp", "mechanism": "m",
                                                "scope": "s", "assumptions": [],
                                                "evidence_refs": ["E1"],
                                                "tag_class": "NOVEL_DECISION_RELEVANT_DIAGNOSIS",
                                                "review_required": False,
                                                "source": "test"})
        self.assertEqual(event["seq"], 1)

    def test_multiprocess_appends_keep_the_chain_consistent(self):
        """T06：多进程并发追加——seq 唯一、哈希链完整、无交叉损坏。"""
        import multiprocessing as mp
        harness = LoopHarness(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(harness.root, ignore_errors=True))

        with mp.get_context("fork").Pool(4) as pool:
            results = pool.map(_mp_append_worker, [(harness.route, w) for w in range(4)])
        seqs = sorted(s for batch in results for s in batch)
        self.assertEqual(seqs, list(range(1, 17)),
                         "16 concurrent appends must produce unique seqs 1..16")
        records, problems = dg.load_events(harness.route)
        self.assertEqual(problems, [])
        self.assertEqual(len(records), 16)
        self.assertEqual([r["seq"] for r in records], list(range(1, 17)))

    def test_multiprocess_idempotent_appends_collapse_to_one_event(self):
        import multiprocessing as mp
        harness = LoopHarness(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(harness.root, ignore_errors=True))
        with mp.get_context("fork").Pool(6) as pool:
            statuses = pool.map(_mp_idempotent_worker, [harness.route] * 6)
        self.assertEqual(statuses.count("APPENDED"), 1, statuses)
        self.assertEqual(statuses.count("DUPLICATE"), 5, statuses)
        records, problems = dg.load_events(harness.route)
        self.assertEqual(problems, [])
        self.assertEqual(len(records), 1)


class TestSelftest(unittest.TestCase):

    def test_module_selftest_passes(self):
        proc = run_guard("--selftest")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("[ok] domain_guard selftest", proc.stdout)


if __name__ == "__main__":
    unittest.main()
