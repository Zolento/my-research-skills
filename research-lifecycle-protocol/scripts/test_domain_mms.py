#!/usr/bin/env python3
"""test_domain_mms.py — the Mechanism-to-Method Search contract and its loop consumption.

MMS is advisory by design: the menu changes what the loop *shows* after a TAG
transition; it does not reorder the scheduler or write state. The candidate contract
(MM1–MM8) is the mechanical part: an empty-vague candidate is refused before it can
enter the existing I2M pipeline.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import domain_mms as mms
import domain_profile as dp
import evidence_outcome as eo
import rlp_paths as rlp
from test_evidence_outcome import TIMESTAMP, fixture
from test_domain_tag import LoopHarness, profile_config

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run_mms(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "domain_mms.py"),
                           *map(str, args)], capture_output=True, text=True, cwd=str(ROOT))


def good_candidate() -> dict:
    return {
        "_schema": mms.CANDIDATE_SCHEMA,
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
        "anchor_alignment": "theory 主锚点下的机制改进（与 contract.primary_anchor 一致）",
    }


class TestCandidateContract(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.harness = LoopHarness(self.tmp.name)
        self.state = self.harness.state
        self.profile = profile_config()

    def errors(self, candidate, **kw):
        return mms.candidate_errors(candidate, profile_config=self.profile,
                                    state=self.state, **kw)

    def test_a_concrete_candidate_passes(self):
        self.assertEqual(self.errors(good_candidate()), [])

    def test_vague_directions_are_rejected(self):
        for direction in ("融合注意力", "增加频域特征", "提高网络表达能力", ""):
            candidate = good_candidate()
            candidate["direction"] = direction
            found = self.errors(candidate)
            self.assertTrue(any(item.startswith("MM2") for item in found), direction)

    def test_capacity_only_improvement_is_refused(self):
        candidate = good_candidate()
        candidate["control_condition"] = {"capacity_matched": False,
                                          "description": "加大网络"}
        found = self.errors(candidate)
        self.assertTrue(any(item.startswith("MM6") for item in found))

    def test_missing_falsification_is_refused(self):
        candidate = good_candidate()
        candidate["expected_effect"].pop("falsification_test")
        self.assertTrue(any(item.startswith("MM5") for item in self.errors(candidate)))

    def test_prior_work_without_delta_is_refused(self):
        candidate = good_candidate()
        candidate["nearest_prior_work"]["delta"] = ""
        self.assertTrue(any(item.startswith("MM7") for item in self.errors(candidate)))

    def test_gt_free_boundary_is_enforced(self):
        candidate = good_candidate()
        candidate["ssl_boundary_compliance"]["uses_gt_for_selection"] = True
        self.assertTrue(any(item.startswith("MM8") for item in self.errors(candidate)))
        candidate = good_candidate()
        candidate.pop("ssl_boundary_compliance")
        self.assertTrue(any(item.startswith("MM8") for item in self.errors(candidate)))
        # A GT-available project does not demand the SSL-boundary statement.
        gt_profile = profile_config()
        gt_profile["gt"] = {"available": True, "usage": "development"}
        candidate = good_candidate()
        candidate.pop("ssl_boundary_compliance")
        found = mms.candidate_errors(candidate, profile_config=gt_profile, state=self.state)
        self.assertFalse(any(item.startswith("MM8") and "ssl_boundary" in item
                             for item in found))

    def test_anchor_alignment_must_match_the_contract(self):
        candidate = good_candidate()
        candidate["anchor_alignment"] = "microvascular structure recovery（非本项目锚点）"
        self.assertTrue(any(item.startswith("MM8") for item in self.errors(candidate)))

    def test_other_declared_mechanism_needs_confirmation_evidence(self):
        candidate = good_candidate()
        candidate["target_failure_mechanism"] = "other_declared"
        found = self.errors(candidate)
        self.assertTrue(any(item.startswith("MM3") for item in found))
        candidate["mechanism_evidence"] = "R7 已确认的新机制记录见 F3"
        self.assertEqual(self.errors(candidate), [])


class TestMenu(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.harness = LoopHarness(self.tmp.name)

    def test_failure_memory_links_directions(self):
        state = json.loads(json.dumps(self.harness.state))
        state["failures"] = [{"id": "F1", "kind": "unsupported",
                              "finding": "conditioning 不佳的假设未被支持，弱结构被压制",
                              "referenced_by": ["C1"]}]
        menu = mms.recommend_directions(state, self.harness.route)
        top = menu["menu"][0]
        self.assertIn("conditioning", top["linked_failure_mechanisms"])
        self.assertEqual(menu["menu"][0]["direction"], "optimization_dynamics")

    def test_crowding_counts_existing_candidates(self):
        (self.harness.route / "methods").mkdir(parents=True, exist_ok=True)
        candidate = good_candidate()
        candidate["direction"] = "target_structure_recovery"
        (self.harness.route / "methods" / "candidate-c1.json").write_text(
            json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
        menu = mms.recommend_directions(self.harness.state, self.harness.route)
        crowded = {item["direction"]: item["existing_candidates"] for item in menu["menu"]}
        self.assertEqual(crowded["target_structure_recovery"], 1)

    def test_no_aggregate_score_exists(self):
        menu = mms.recommend_directions(self.harness.state, self.harness.route)
        blob = json.dumps(menu)
        for forbidden in ("score", "weighted", "overall"):
            self.assertNotIn(forbidden, blob)

    def test_cli_menu_runs_against_a_real_state(self):
        proc = run_mms("menu", "--state", self.harness.state_path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(len(payload["menu"]), 6)


class TestLoopConsumption(unittest.TestCase):

    def test_the_loop_menu_reaches_the_tag_transition(self):
        """端到端：TAG 判定重复 → loop 输出携带 MMS 菜单（真实入口）。"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        harness = LoopHarness(tmp.name)
        harness.record_repeat("snr_limit", "10x vd 20-coil")
        action = {"action": "X13", "type": "discriminating_experiment",
                  "target": "U2", "eig": "high", "cost": "low",
                  "attribution_mechanism": "snr_limit",
                  "attribution_scope": "10x vd 20-coil",
                  "attribution_assumptions": ["高斯噪声"]}
        import preset_router as pr
        step = pr._loop_step(harness.ctx(harness.scheduler(action)))
        self.assertIsNotNone(step["tag"]["transition_menu"])
        self.assertEqual(len(step["tag"]["transition_menu"]["menu"]), 6)
        self.assertIsNone(step.get("dispatched_action"))


class TestSelftest(unittest.TestCase):

    def test_module_selftest_passes(self):
        proc = run_mms("--selftest")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("[ok] domain_mms selftest", proc.stdout)


if __name__ == "__main__":
    unittest.main()
