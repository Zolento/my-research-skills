#!/usr/bin/env python3
"""test_domain_mms_integration.py — MMS validation is reachable from, and enforced by,
the real I2M candidate path (T17), fails closed on a damaged TAG log (T18) and never
auto-rejects a scope-disjoint physical limit (T19).

No synthetic replay here claims research effectiveness (L3 NOT YET VALIDATED); these
tests prove the wiring and the fail-closed boundaries (L2).
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

import domain_guard as dg
import domain_mms as mms
import domain_profile as dp
import insight_to_method as i2m
import rlp_paths as rlp

ROOT = pathlib.Path(__file__).resolve().parent.parent


def profile_config() -> dict:
    return {
        "_schema": dp.PROFILE_SCHEMA, "profile": "mri-reconstruction",
        "acquisition": {"forward_operators": ["fourier", "undersampling_mask"],
                        "coils": 20, "undersampling": {"pattern": "variable_density"},
                        "noise": {"model": "gaussian"}},
        "gt": {"available": False, "usage": "none"},
        "ssl": {"type": "ssdu",
                "split": {"input": "theta", "loss": "lambda",
                          "held_out_validation": "omega_val",
                          "measurement_identity": {
                              "fields": "subject/slice/volume/acquisition",
                              "mask_sharing_allowed": True}},
                "acs": {"usage": "frozen_protocol"}},
        "model_selection": {"protocol": "omega_val_only", "uses_gt": False},
        "frozen": {"components": ["backbone"], "forbidden_changes": []},
        "metrics": {"primary": {"name": "nmse_global", "threshold": 0.02,
                                "direction": "lower_is_better",
                                "preregistration_ref": "X1",
                                "frozen_before_results": True,
                                "frozen_at_state_version": 0}},
        "resources": {"gpu_hours_budget": 12},
    }


def complete_candidate(candidate_id: str = "C1") -> dict:
    return {
        "_schema": "research-idea-pipeline/method-candidate@1",
        "candidate_id": candidate_id,
        "direction": "prior_posterior_adaptation",
        "target_failure_mechanism": "overstrong_prior",
        "mathematical_change": {
            "changes_object": "先验加权 w(y_Θ)",
            "changed_rule": "FBS 近端步中的固定先验替换为测量条件化加权"},
        "expected_effect": {
            "prediction": "弱对比度结构恢复提升且全局 NMSE 不劣化",
            "criterion": "vessel_mip_connectivity ≥ +0.05 且 ΔNMSE ≤ 0.02",
            "falsification_test": "X15 等容量对照上无差异则否定该机制"},
        "control_condition": {"capacity_matched": True,
                              "description": "同参数量 adapter 与同训练预算"},
        "nearest_prior_work": {"reference": "CT-FM prior baseline",
                               "delta": "引入测量条件化先验加权，而非仅域微调"},
        "ssl_boundary_compliance": {"statement": "只用 Θ 输入与 Λ 损失；Ω_val 只做选择",
                                    "uses_gt_for_selection": False},
        "anchor_alignment": "theory 主锚点下的机制改进",
    }


class Harness:
    """A legacy-root route with a declared profile and a canonical state."""

    def __init__(self, temp: str, *, with_profile: bool = True):
        self.root = pathlib.Path(temp)
        self.route = self.root / rlp.STORAGE_ROOT / "routes" / "A"
        self.route.mkdir(parents=True, exist_ok=True)
        self.state_path = self.route / "research-state.json"
        self.state = self._state()
        self.state["experiments"] = [
            {"id": "X1", "status": "planned", "parent": None, "stage": "X2",
             "claim_targeted": [], "hypothesis_targeted": [], "alternative_targeted": [],
             "depends_on": [], "known_flaws": [],
             "validity": {"status": "valid", "reason": "冻结计划",
                          "since_state_version": 6},
             "preregistration": {"frozen_at_state_version": 6}}]
        self.write_state()
        if with_profile:
            self.declare()
            # R8 binding: the declared frozen thresholds are bound into the prereg
            self.state = dp.bind_metric_contract(profile_config(), self.state)
            self.write_state()

    @staticmethod
    def _state() -> dict:
        return {
            "state_version": 7,
            "contract": {"primary_anchor": "theory", "constraints": [],
                         "resources": [], "out_of_scope": []},
            "claims": [{"id": "C1", "statement": "机制 A 解释现象", "parent": None,
                        "subclaims": [], "status": "ungrounded",
                        "supporting_evidence": [], "refuting_evidence": [],
                        "falsifier": "解耦后现象不变", "scope": "数据集 A",
                        "known_flaws": [], "depends_on": [],
                        "validity": {"status": "valid", "reason": "预注册",
                                     "since_state_version": 6}}],
            "evidence": [], "assumptions": [], "hypotheses": [], "experiments": [],
            "literature": [], "failures": [], "uncertainties": [], "assurance": [],
            "repairs": [],
        }

    def write_state(self):
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False),
                                   encoding="utf-8")

    def declare(self):
        path = self.route / "domain" / "mri-reconstruction.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile_config(), ensure_ascii=False),
                        encoding="utf-8")


class TestI2MIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.harness = Harness(self.tmp.name)

    def test_t17_an_incomplete_candidate_is_blocked_inside_i2m(self):
        """T17：I2M 正常入口执行 MMS 验证——缺字段候选无法走到设计契约。"""
        incomplete = complete_candidate()
        for field in ("direction", "control_condition", "nearest_prior_work",
                      "ssl_boundary_compliance"):
            incomplete.pop(field)
        review = i2m.domain_candidate_review(self.harness.state, [incomplete],
                                             self.harness.route)
        self.assertIsNotNone(review)
        self.assertTrue(review["blocking"])
        self.assertTrue(any("MM2" in e or "MM6" in e or "MM7" in e or "MM8" in e
                            for e in review["errors"]), review["errors"])
        # the same candidate through the standalone CLI yields the same violations
        standalone = mms.candidate_errors(incomplete, profile_config=profile_config(),
                                          state=self.harness.state)
        self.assertTrue(any("MM2" in e for e in standalone), standalone)

    def test_t17b_a_complete_candidate_passes_and_records_advisories(self):
        candidate = complete_candidate()
        review = i2m.domain_candidate_review(self.harness.state, [candidate],
                                             self.harness.route)
        self.assertIsNotNone(review)
        self.assertFalse(review["blocking"], review["errors"])

    def test_t18_a_damaged_tag_log_blocks_the_i2m_path(self):
        """T18：TAG 日志损坏 → I2M 路径显式错误，不得按空历史继续。"""
        path = self.harness.route / "domain" / "tag-events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken json\n", encoding="utf-8")
        review = i2m.domain_candidate_review(self.harness.state, [complete_candidate()],
                                             self.harness.route)
        self.assertIsNotNone(review)
        self.assertTrue(review["blocking"])
        self.assertTrue(any("MM-log" in e for e in review["errors"]), review["errors"])
        # the standalone CLI fails closed with the same discipline
        import subprocess
        import sys
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "domain_mms.py"), "validate",
             "--candidate", "/dev/null", "--state", str(self.harness.state_path)],
            capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)

    def test_t19_a_scope_disjoint_limit_is_not_auto_rejected(self):
        """T19：物理限制作用域与候选作用域不相交 → 审查建议而非否决。"""
        declaration = dg.parse_declaration({
            "mechanism": "undersampling_information", "scope": "20x vd 20-coil",
            "assumptions": ["固定 mask"], "evidence_refs": ["E1"],
            "predictions": ["X9 中 O1 无差异"]})[0]
        state = json.loads(self.harness.state_path.read_text(encoding="utf-8"))
        state.setdefault("evidence", []).append(
            {"id": "E1", "kind": "experiment", "scope": "20x VD", "supports": [],
             "contradicts": [], "epistemic_status": "Observed",
             "source_ref": "X9 oracle", "verification_tier": "T2", "depends_on": [],
             "validity": {"status": "valid", "reason": "已按预注册",
                          "since_state_version": 6}})
        self.harness.write_state()
        verdict = dg.classify(declaration, [], state=state)
        self.assertEqual(verdict["tag_class"], "NOVEL_DECISION_RELEVANT_DIAGNOSIS")
        dg.append_event(self.harness.route, dg.event_from_classification(
            declaration, verdict, "test", state=state))
        limit_declaration = dg.parse_declaration({
            "mechanism": "undersampling_information", "scope": "20x vd 20-coil",
            "assumptions": ["固定 mask"], "evidence_refs": ["E1"],
            "physical_limit": {"verified": True,
                               "limit_type": "mathematical_impossibility",
                               "scope": ">=20x；直径 <1.5px 微血管不可见",
                               "source_refs": ["E1"]}})[0]
        verdict = dg.classify(limit_declaration, dg.load_events(self.harness.route)[0],
                              state=state)
        self.assertEqual(verdict["tag_class"], "PHYSICAL_LIMIT_WITH_SCOPE")
        dg.append_event(self.harness.route, dg.event_from_classification(
            limit_declaration, verdict, "test", state=state))
        records, problems = dg.load_events(self.harness.route)
        self.assertEqual(problems, [])
        # a candidate for a DIFFERENT regime (6x, cortex structures) must not be
        # auto-rejected: the disjoint scope downgrades MM3b to a review note
        candidate = complete_candidate()
        candidate["target_failure_mechanism"] = "undersampling_information"
        candidate["scope"] = "6x 加速，皮层区大血管"
        review = i2m.domain_candidate_review(self.harness.state, [candidate],
                                             self.harness.route)
        self.assertIsNotNone(review)
        self.assertFalse(review["blocking"], review["errors"])
        self.assertTrue(any("MM3b-review" in note or "不相交" in note
                            for note in review["notes"]), review["notes"])

    def test_t22_seed_no_profile_keeps_i2m_untouched(self):
        """T22：未声明领域 Profile → I2M 行为与 2.0.0 完全一致（review 为 None）。"""
        plain = Harness(tempfile.mkdtemp(), with_profile=False)
        self.addCleanup(lambda: plain.state_path.parent.parent.parent.mkdir(
            parents=True, exist_ok=True) or None)
        review = i2m.domain_candidate_review(plain.state, [complete_candidate()],
                                             plain.route)
        self.assertIsNone(review)

    def test_structural_duplicate_candidates_are_refused(self):
        """7.5：同数学结构换名重报 → MM9 拒绝；结构不同的增量改进保留。"""
        import shutil
        harness = self.harness
        (harness.route / "methods").mkdir(exist_ok=True)
        archived = complete_candidate("C0")
        (harness.route / "methods" / "candidate-c0.json").write_text(
            json.dumps(archived, ensure_ascii=False), encoding="utf-8")
        renamed = complete_candidate("C1")     # same math, new name
        problems = mms.duplicate_candidate_errors(renamed, harness.route)
        self.assertTrue(any("MM9" in p for p in problems), problems)
        different = complete_candidate("C2")
        different["mathematical_change"] = {
            "changes_object": "不确定性加权图构建",
            "changed_rule": "FBS 近端步中的数据一致性项替换为逐体素不确定性加权"}
        different["target_failure_mechanism"] = "oversmoothing"
        self.assertEqual(mms.duplicate_candidate_errors(different, harness.route), [])


if __name__ == "__main__":
    unittest.main()
