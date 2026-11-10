#!/usr/bin/env python3
"""test_domain_replay.py — the MRI domain scenarios as an executable replay, plus the
domain ablation (core / +profile / +tag / +mms).

Honesty header (this is the L2/L3 boundary the release notes declare):

* Every case here is **synthetic**. No real CT-FM or Wave-TOF run is replayed; the real
  project histories live in private project routes and are not shipped with the skill.
* What the scenarios prove is **mechanism wiring (L2)**: the classification, the loop
  behaviour, the claim gates and the candidate contract react as specified when the
  described situation is presented through the real entry points.
* What they do **not** prove is **research effectiveness (L3)**: that TAG/MMS improve
  discovery on unseen real research requires a real-project A/B, which has not been run.

The four-arm ablation compares arms on the same scenario set and reports counts, not
scores: repeated-diagnosis dispatches withheld, novel diagnoses preserved, validity
defects never suppressed. It extends — never replaces — the CIE four-arm ablation in
`rsi_ablation.py`.
"""

from __future__ import annotations

import copy
import json
import pathlib
import tempfile
import unittest

import domain_guard as dg
import domain_mms as mms
import domain_profile as dp
import evidence_outcome as eo
import preset_router as pr
import rlp_paths as rlp
from test_domain_tag import LoopHarness, profile_config
from test_evidence_outcome import TIMESTAMP, fixture

SCENARIO_SCHEMA = "research-idea-pipeline/domain-scenario@1"

DIAGNOSIS = {"action": "X13", "type": "discriminating_experiment", "target": "U2",
             "eig": "high", "cost": "low"}


def diagnosis(mechanism: str, scope: str = "10x vd 20-coil",
              assumptions=None) -> dict:
    return {**DIAGNOSIS, "attribution_mechanism": mechanism,
            "attribution_scope": scope,
            "attribution_assumptions": assumptions or ["高斯噪声"]}


def harness_with(tmp: str) -> LoopHarness:
    return LoopHarness(tmp)


# ---------------------------------------------------------------------------
# The ten specification scenarios, each driven through the real entries
# ---------------------------------------------------------------------------

class ScenarioBase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.harness = harness_with(self.tmp.name)

    def record(self, mechanism: str, scope: str = "10x vd 20-coil", **overrides) -> dict:
        declaration = self.harness.declaration(mechanism, scope)
        declaration.update(overrides)
        path = self.harness.route / "declaration.json"
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        first = self._classify(path, record=True)
        second = self._classify(path, record=True)
        return json.loads(second.stdout)

    def _classify(self, path, record=False):
        args = ["classify", "--state", str(self.harness.state_path),
                "--declaration", str(path)]
        if record:
            args.append("--record")
        import subprocess
        import sys
        proc = subprocess.run([sys.executable, str(pathlib.Path(dg.__file__).parent
                                                    / "domain_guard.py"), *args],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return proc

    def loop(self, action: dict) -> dict:
        return pr._loop_step(self.harness.ctx(self.harness.scheduler(action)))


class TestTenScenarios(ScenarioBase):

    def test_1_verified_operator_but_stalled_does_not_repeat_operator_checks(self):
        """算子已验证、性能停滞：不再重复常规算子检查，转向机制与方法探索。"""
        verdict = self.record("forward_operator_mismatch")
        self.assertEqual(verdict["tag_class"], "REPEATED_ATTRIBUTION")
        step = self.loop(diagnosis("forward_operator_mismatch"))
        self.assertIsNone(step.get("dispatched_action"))
        self.assertEqual(step["tag"]["tag_class"], "REPEATED_ATTRIBUTION")
        self.assertIsNotNone(step["tag"]["transition_menu"],
                             "the loop must offer the method-transition menu")

    def test_2_real_operator_error_is_repaired_not_suppressed(self):
        """真正算子错误（canonical failed 实验）：进入完整性修复，TAG 永不阻断。"""
        state = json.loads(self.harness.state_path.read_text(encoding="utf-8"))
        state.setdefault("experiments", []).append(
            {"id": "X11", "status": "failed", "stage": "X2", "claim_targeted": [],
             "parent": None, "preregistration": {"frozen_at_state_version": 0}})
        self.harness.state_path.write_text(json.dumps(state, ensure_ascii=False),
                                           encoding="utf-8")
        declaration = self.harness.declaration("coil_sensitivity_error")
        declaration["validity_findings"] = ["CSM 相位与已知几何不符（回代残差系统性偏高）"]
        declaration["validity_evidence_refs"] = ["X11"]
        path = self.harness.route / "declaration.json"
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        verdict = json.loads(self._classify(path, record=True).stdout)
        self.assertEqual(verdict["tag_class"], "VALIDITY_BLOCKER")
        # Re-proposing the same diagnosis is still not withheld: a validity blocker is
        # not a repeat, and the repair path (R10) owns it.
        step = self.loop(diagnosis("coil_sensitivity_error"))
        self.assertEqual(step.get("dispatched_action"), "X13", step)

    def test_3_analysed_snr_then_noise_again_is_a_repeat(self):
        """SNR 已分析，再次归因噪声：识别重复并进入合法方法转化。"""
        self.record("snr_limit")
        step = self.loop(diagnosis("snr_limit"))
        self.assertIsNone(step.get("dispatched_action"))
        self.assertIn("重复", step["action"])

    def test_4_ssl_loss_improvement_is_not_reconstruction_success(self):
        """SSL loss 改善但图像质量未改善：识别目标错位，不得宣称训练成功。"""
        config = profile_config()
        config["metrics"]["measurement_domain"] = ["ssdu_loss"]
        claim = {"metric": "ssdu_loss", "conclusion": "训练成功，重建改善",
                 "asserts_image_improvement": True, "model_selection_uses_gt": False}
        observation = {"metrics": {"ssdu_loss": -0.31, "nmse_global": 0.004}}
        problems = dp.outcome_claim_errors(claim, observation, config)
        self.assertTrue(any(item.startswith("DP12") for item in problems), problems)
        # The honest framing: recorded as an objective mismatch for R9.O, no success claim.
        claim_honest = {"metric": "ssdu_loss", "conclusion": "objective mismatch 待分析",
                        "asserts_image_improvement": False,
                        "model_selection_uses_gt": False}
        self.assertEqual([item for item in
                          dp.outcome_claim_errors(claim_honest, observation, config)
                          if item.startswith("DP12")], [])

    def test_5_repeated_candidate_failures_require_a_scope_change(self):
        """多个方法候选连续失败：保留负证据，调整搜索空间，不换名重试。"""
        state = json.loads(json.dumps(self.harness.state))
        state["failures"] = [
            {"id": "F1", "kind": "unsupported",
             "finding": "oversmoothing 假设未获支持（等容量对照无差异）", "referenced_by": ["C1"]},
            {"id": "F2", "kind": "deprioritized",
             "finding": "oversmoothing 方向再次失败（第二组独立对照）", "referenced_by": ["C1"]}]
        candidate = {
            "_schema": mms.CANDIDATE_SCHEMA, "direction": "representation_inductive_bias",
            "target_failure_mechanism": "oversmoothing",
            "mathematical_change": {"changes_object": "正则项", "changed_rule": "加强平滑"},
            "expected_effect": {"prediction": "结构更清晰", "criterion": "vessel 指标 +0.05",
                                "falsification_test": "X16"},
            "control_condition": {"capacity_matched": True, "description": "同参数"},
            "nearest_prior_work": {"reference": "UNet baseline", "delta": "更深"},
            "ssl_boundary_compliance": {"statement": "Θ/Λ", "uses_gt_for_selection": False},
            "anchor_alignment": "theory"}
        problems = mms.candidate_errors(candidate, profile_config=profile_config(),
                                        state=state)
        self.assertTrue(any(item.startswith("MM3a") for item in problems), problems)
        candidate["scope_change_justification"] = \
            "新作用域：只在 z-slab 边界层修改正则，与 F1/F2 的全卷积作用域不同"
        problems = mms.candidate_errors(candidate, profile_config=profile_config(),
                                        state=state)
        self.assertFalse(any(item.startswith("MM3a") for item in problems), problems)

    def test_6_unauthorized_gt_selection_is_refused(self):
        """未经 GT 授权的模型选择：检测信息泄漏并拒绝违规决策。"""
        config = profile_config()
        claim = {"metric": "nmse_global", "conclusion": "选择成功",
                 "model_selection_uses_gt": True}
        observation = {"metrics": {"nmse_global": -0.02}}
        problems = dp.outcome_claim_errors(claim, observation, config)
        self.assertTrue(any(item.startswith("DP14") for item in problems), problems)

    def test_7_verified_information_limit_bounds_the_search_space(self):
        """已验证严格信息极限（证据支持的数学不可能性）：保留范围内负结论。"""
        state = json.loads(self.harness.state_path.read_text(encoding="utf-8"))
        state.setdefault("evidence", []).append(
            {"id": "E9", "kind": "experiment", "scope": "≥20x", "supports": [],
             "contradicts": [], "epistemic_status": "Observed",
             "source_ref": "X9 oracle impossibility proof", "verification_tier": "T2",
             "depends_on": [], "validity": {"status": "valid", "reason": "已按预注册",
                                            "since_state_version": 0}})
        self.harness.state_path.write_text(json.dumps(state, ensure_ascii=False),
                                           encoding="utf-8")
        declaration = self.harness.declaration("undersampling_information")
        declaration["physical_limit"] = {
            "verified": True, "limit_type": "mathematical_impossibility",
            "scope": "≥20x，直径 <1.5px 微血管不可见", "source_refs": ["E9"]}
        path = self.harness.route / "declaration.json"
        path.write_text(json.dumps(declaration, ensure_ascii=False), encoding="utf-8")
        verdict = json.loads(self._classify(path, record=True).stdout)
        self.assertEqual(verdict["tag_class"], "PHYSICAL_LIMIT_WITH_SCOPE")
        records, problems = dg.load_events(self.harness.route)
        self.assertEqual(problems, [])
        candidate = {
            "_schema": mms.CANDIDATE_SCHEMA, "direction": "target_structure_recovery",
            "target_failure_mechanism": "undersampling_information",
            "mathematical_change": {"changes_object": "采样后先验",
                                    "changed_rule": "直接 hallucinate 细血管"},
            "expected_effect": {"prediction": "恢复 <1.5px 微血管",
                                "criterion": "vessel +0.2", "falsification_test": "X17"},
            "control_condition": {"capacity_matched": True, "description": "同参"},
            "nearest_prior_work": {"reference": "baseline", "delta": "更强先验"},
            "ssl_boundary_compliance": {"statement": "Θ/Λ", "uses_gt_for_selection": False},
            "anchor_alignment": "theory"}
        found = mms.candidate_errors(candidate, profile_config=profile_config(),
                                     state=self.harness.state, tag_records=records)
        self.assertTrue(any(item.startswith("MM3b") for item in found), found)
        candidate["scope_justification"] = "目标结构直径 ≥2px，在已验证范围（<1.5px）之外"
        found = mms.candidate_errors(candidate, profile_config=profile_config(),
                                     state=self.harness.state, tag_records=records)
        self.assertFalse(any(item.startswith("MM3b") for item in found), found)

    def test_8_capacity_only_growth_requires_an_equal_capacity_control(self):
        """新方法只是扩大网络容量：要求等容量对照，不得宣称机制创新。"""
        candidate = {
            "_schema": mms.CANDIDATE_SCHEMA, "direction": "representation_inductive_bias",
            "target_failure_mechanism": "oversmoothing",
            "mathematical_change": {"changes_object": "通道数", "changed_rule": "×4 通道"},
            "expected_effect": {"prediction": "指标更好", "criterion": "NMSE 下降",
                                "falsification_test": "X18"},
            "control_condition": {"capacity_matched": False, "description": "更大网络"},
            "nearest_prior_work": {"reference": "UNet", "delta": "更宽"},
            "ssl_boundary_compliance": {"statement": "Θ/Λ", "uses_gt_for_selection": False},
            "anchor_alignment": "theory"}
        found = mms.candidate_errors(candidate, profile_config=profile_config(),
                                     state=self.harness.state)
        self.assertTrue(any(item.startswith("MM6") for item in found))

    def test_9_more_visible_detail_must_count_false_structures(self):
        """结构细节看起来变多：检查真实性，幻觉不得计为恢复成功。"""
        config = profile_config()
        config["metrics"]["structural"] = [
            {"name": "vessel_mip_connectivity", "threshold": 0.05,
             "frozen_before_results": True, "frozen_at_state_version": 0}]
        claim = {"metric": "nmse_global",
                 "conclusion": "微血管恢复成功",
                 "structural_recovery": {"structure": "微血管",
                                         "counts_false_structures": False},
                 "model_selection_uses_gt": False}
        observation = {"metrics": {"nmse_global": -0.03}}
        problems = dp.outcome_claim_errors(claim, observation, config)
        self.assertTrue(any(item.startswith("DP13") for item in problems), problems)
        self.assertEqual(len([item for item in problems if item.startswith("DP13")]), 2,
                         problems)

    def test_10_a_challenged_anchor_stays_a_user_decision(self):
        """研究锚点受到可靠证据挑战：保留 challenging 候选，改锚点由用户决定。"""
        candidate = {
            "_schema": mms.CANDIDATE_SCHEMA, "direction": "target_structure_recovery",
            "target_failure_mechanism": "other_declared",
            "mechanism_evidence": "R7 已确认的新机制记录",
            "mathematical_change": {"changes_object": "任务定义",
                                    "changed_rule": "从全局重建改为结构检测"},
            "expected_effect": {"prediction": "结构检出提升", "criterion": "检出率 +0.1",
                                "falsification_test": "X19"},
            "control_condition": {"capacity_matched": True, "description": "同参"},
            "nearest_prior_work": {"reference": "baseline", "delta": "任务重定义"},
            "ssl_boundary_compliance": {"statement": "Θ/Λ", "uses_gt_for_selection": False},
            "anchor_alignment": "structure-first 任务定义"}
        found = mms.candidate_errors(candidate, profile_config=profile_config(),
                                     state=self.harness.state)
        self.assertTrue(any(item.startswith("MM8") for item in found), found)
        candidate["anchor_change_requested"] = True
        candidate["anchor_change_justification"] = \
            "oracle 功效实验表明 theory 锚点下的全局指标与临床相关结构脱钩（F4）"
        found = mms.candidate_errors(candidate, profile_config=profile_config(),
                                     state=self.harness.state)
        self.assertFalse(any(item.startswith("MM8") for item in found), found)
        # No domain module writes the contract: the anchor stays untouched.
        self.assertEqual(self.harness.state["contract"]["primary_anchor"], "theory")


# ---------------------------------------------------------------------------
# Domain ablation: core / +profile / +tag / +mms (counts, not scores)
# ---------------------------------------------------------------------------

def run_arm(arm: str, scenarios) -> dict:
    """Run the scenario set under one arm and count dispatch behaviour.

    core      — no profile declared; the loop behaves exactly as before this release.
    +profile  — profile declared, no TAG history; nothing is withheld yet.
    +tag      — profile + recorded attribution history; repeats are withheld.
    +mms      — same as +tag, with the MMS menu attached to transitions.
    """
    with tempfile.TemporaryDirectory() as temp:
        harness = LoopHarness(temp)
        if arm != "core":
            harness.declare_profile()
        if arm in ("+tag", "+mms"):
            for declaration in scenarios["repeat_declarations"]:
                path = harness.route / "declaration.json"
                path.write_text(json.dumps(declaration, ensure_ascii=False),
                                encoding="utf-8")
                import subprocess
                import sys
                for _ in range(2):
                    subprocess.run([sys.executable,
                                    str(pathlib.Path(dg.__file__).parent
                                        / "domain_guard.py"),
                                    "classify", "--state", str(harness.state_path),
                                    "--declaration", str(path), "--record"],
                                   capture_output=True, text=True, check=True)
        counts = {"dispatched": 0, "withheld": 0, "withheld_with_menu": 0,
                  "novel_preserved": 0, "validity_dispatched": 0}
        for action in scenarios["actions"]:
            step = pr._loop_step(harness.ctx(harness.scheduler(action)))
            dispatched = step.get("dispatched_action") == action["action"]
            if action.get("action_kind") == "novel":
                counts["novel_preserved"] += int(dispatched)
            elif action.get("action_kind") == "validity":
                counts["validity_dispatched"] += int(dispatched)
            elif action.get("action_kind") == "repeat":
                counts["dispatched"] += int(dispatched)
                counts["withheld"] += int(not dispatched)
                if not dispatched and (step.get("tag") or {}).get("transition_menu"):
                    counts["withheld_with_menu"] += 1
        return counts


class TestDomainAblation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.scenarios = {
            "repeat_declarations": [
                LoopHarness.declaration("snr_limit", "10x vd 20-coil"),
                LoopHarness.declaration("noise_level", "10x vd 20-coil"),
                LoopHarness.declaration("forward_operator_mismatch", "10x vd 20-coil"),
            ],
            "actions": [
                {**diagnosis("snr_limit"), "action_kind": "repeat"},
                {**diagnosis("noise_level"), "action_kind": "repeat"},
                {**diagnosis("forward_operator_mismatch"), "action_kind": "repeat"},
                {**diagnosis("conditioning", assumptions=["固定 mask", "3D 大核"]),
                 "action": "X14", "action_kind": "novel"},
                {**diagnosis("coil_sensitivity_error", assumptions=["CSM 错误证据"]),
                 "action": "X15", "action_kind": "validity"},
            ],
        }

    def test_core_dispatches_everything_including_repeats(self):
        counts = run_arm("core", self.scenarios)
        self.assertEqual(counts["dispatched"], 3)
        self.assertEqual(counts["withheld"], 0)
        self.assertEqual(counts["novel_preserved"], 1)
        self.assertEqual(counts["validity_dispatched"], 1)

    def test_profile_alone_changes_nothing(self):
        counts = run_arm("+profile", self.scenarios)
        self.assertEqual(counts["dispatched"], 3,
                         "a declared profile without recorded history must not block")

    def test_tag_withholds_repeats_and_preserves_novel_and_validity(self):
        counts = run_arm("+tag", self.scenarios)
        self.assertEqual(counts["withheld"], 3)
        self.assertEqual(counts["dispatched"], 0)
        self.assertEqual(counts["novel_preserved"], 1)
        self.assertEqual(counts["validity_dispatched"], 1)

    def test_mms_attaches_the_menu_to_transitions(self):
        counts = run_arm("+mms", self.scenarios)
        self.assertEqual(counts["withheld_with_menu"], 3)
        self.assertEqual(counts["novel_preserved"], 1)

    def test_arms_are_a_domain_extension_not_a_cie_replacement(self):
        """领域消融只是计数对比；CIE 四臂消融保持原样。"""
        import research_replay as rr
        self.assertEqual(len(rr.ABLATION_ARMS), 4)


class TestSelftest(unittest.TestCase):

    def test_all_domain_modules_pass_their_selftests(self):
        import subprocess
        import sys
        scripts = pathlib.Path(dp.__file__).parent
        for module in ("domain_profile.py", "domain_guard.py", "domain_mms.py"):
            proc = subprocess.run([sys.executable, str(scripts / module), "--selftest"],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, f"{module}: {proc.stdout}{proc.stderr}")


if __name__ == "__main__":
    unittest.main()
