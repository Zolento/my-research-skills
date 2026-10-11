#!/usr/bin/env python3
"""test_research_taste.py — 科研选择质量验收（判断质量，不是接口正确性）。

**诚实的边界：** 这些是**专家撰写的场景夹具**，灵感来自架构审查里的「更理想的选择」以及
TASTE / Elegant Science / Novelty Bias 等方法学结论。它们**不是**人类标注的成对偏好数据，
因此本文件**不能**证明「人类科研品味一致性」。它证明的是：判断**有依据、可解释、可判为不可比、
顺序/措辞稳定、能被真实实验反馈修正，且不越过任何硬门禁**。
真正的验收需要独立专家对真实领域案例做成对判断（含分歧与不确定性），尚未进行。
"""

from __future__ import annotations

import copy
import json
import pathlib
import tempfile
import unittest

import insight_to_method as i2m
import preset_router as pr
import test_insight_to_method as shared


def candidate(cid, **overrides):
    base = {"candidate_id": cid, "intervention": {"kind": "objective"},
            "how_it_addresses": "针对核心问题", "mechanism_basis": "机制给出干预方向",
            "structural_difference": "d", "minimal_implementation_complexity": "low",
            "why_not_simpler": "单处改动即可解释", "expected_benefit": "b",
            "resource_cost": "low", "failure_boundary": ["不升则否定"],
            "falsifiable_predictions": ["判别预测"], "distinctive_mechanism": cid + "-m",
            "mathematical_formulation": "L-" + cid}
    base.update(overrides)
    return base


class TasteCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.route = pathlib.Path(self.temp.name) / "A"
        self.route.mkdir(parents=True)
        self.state_path = self.route / "research-state.json"

    def tearDown(self):
        self.temp.cleanup()

    def judge(self, left, right, **kwargs):
        return i2m.compare_candidates([left, right], **kwargs)


class TestJudgementQuality(TasteCase):
    def test_1_an_important_but_complex_method_beats_a_simple_low_value_one(self):
        important = candidate("M-important", importance_level="high",
                              minimal_implementation_complexity="high",
                              complexity_necessary=True, decisive_experiment="关键判别实验")
        trivial = candidate("M-trivial", importance_level="low")
        verdict = self.judge(important, trivial)
        self.assertEqual(verdict["judgement"], i2m.JUDGEMENT_PREFER)
        self.assertEqual(verdict["preference"], "M-important")
        self.assertTrue(verdict["complexity"]["necessary"])

    def test_2_at_equal_value_justified_simplicity_beats_unnecessary_complexity(self):
        simple = candidate("M-simple", importance_level="high", complexity_necessary=True)
        bloated = candidate("M-bloated", importance_level="high",
                            minimal_implementation_complexity="high",
                            complexity_necessary=False)
        verdict = self.judge(bloated, simple)
        self.assertEqual(verdict["preference"], "M-simple")

    def test_3_a_genuinely_novel_high_risk_candidate_is_not_eliminated_without_grounds(self):
        risky = candidate("M-risky", importance_level="high", novelty_risk="high",
                          prior_art_overlap="low", decisive_experiment="决定性判别",
                          insights_directness=None)
        safe = candidate("M-safe", importance_level="low", falsifiable_predictions=[])
        verdict = self.judge(safe, risky)
        self.assertEqual(verdict["preference"], "M-risky")
        self.assertIn("M-safe", verdict["alternatives"])

    def test_4_large_structural_difference_with_weak_contribution_is_not_preferred(self):
        exotic = candidate("M-exotic", importance_level="low",
                           distinctive_mechanism="跨域拼接", mathematical_formulation="复杂")
        direct = candidate("M-direct", importance_level="high", insight_directness="direct",
                           decisive_experiment="决定性实验")
        verdict = self.judge(exotic, direct)
        self.assertEqual(verdict["preference"], "M-direct")
        self.assertIn("M-exotic", verdict["alternatives"])

    def test_5_order_and_verbosity_do_not_change_the_judgement(self):
        left = candidate("A", importance_level="high", insight_directness="direct",
                         decisive_experiment="d")
        right = candidate("B", importance_level="low")
        padded = copy.deepcopy(right)
        padded["how_it_addresses"] = "非常冗长的说明。" * 40
        padded["mechanism_basis"] = "很长的机制描述。" * 40
        first = self.judge(left, right)
        second = self.judge(padded, left)          # reversed order + padded text
        self.assertEqual(first["preference"], "A")
        self.assertEqual(second["preference"], "A")

    def test_6_incomparable_methods_are_not_forced_into_a_winner(self):
        # A is important but over-engineered; B is elegant but addresses little - equal margins,
        # conflicting grounds: the honest answer is "cannot reliably compare".
        first = candidate("M-1", importance_level="high",
                          minimal_implementation_complexity="high", complexity_necessary=False)
        second = candidate("M-2", importance_level="low", why_not_simpler="w",
                           decisive_experiment="")
        verdict = self.judge(first, second)
        self.assertEqual(verdict["judgement"], i2m.JUDGEMENT_INDETERMINATE)
        self.assertIsNone(verdict["preference"])
        self.assertTrue(verdict["uncertainty"])

    def test_6b_candidates_without_any_grounds_are_indeterminate(self):
        verdict = self.judge(candidate("X"), candidate("Y"))
        self.assertEqual(verdict["judgement"], i2m.JUDGEMENT_INDETERMINATE)

    def test_no_aggregate_score_is_produced(self):
        verdict = self.judge(candidate("A", importance_level="high"), candidate("B"))
        for banned in ("score", "weight", "total", "rank", "utility"):
            self.assertNotIn(banned, verdict)
        self.assertIn("不是分数", verdict["note"])


class TestExecutionCalibration(TasteCase):
    def _state(self, experiment="X600", extra=()):
        """A state with genuine result records: analysed experiment bound to H42 + evidence."""
        import copy as _copy
        state, _ = shared.progress_fixture()
        state = _copy.deepcopy(state)
        state["experiments"] = [
            {"id": "X600", "status": "done", "metric": "recall@10", "hypothesis_targeted": ["H42"],
             "result_at_state_version": 3,
             "outcome_analysis": {"packet": {}, "analysis": {"id": "A600"},
                                  "audit": {}, "validation_context": {}, "audit_trail": {}},
             "preregistration": {"frozen_at_state_version": 1, "method_contract": {
                 "method_digest": "d1", "version": 1, "method_hypothesis_ref": "H42"}}}]
        state["evidence"] = [*state["evidence"],
                             {"id": "E600", "epistemic_status": "Observed",
                              "validity": {"status": "valid"}, "supports": ["H42"],
                              "source_ref": "exp:X600", "verification_tier": "T2",
                              "method_version": "d1"}]
        return state

    def test_7_a_credible_result_revises_the_preference_with_recorded_reasons(self):
        state = self._state()
        first = i2m.record_outcome_feedback(
            state, self.route, "H42", experiment_id="X600", outcome="supported",
            supported_axes=["evidence"], weakened_axes=["importance"],
            judgement="prefer M-A -> M-B", source="exp:X600")
        self.assertTrue(first["written"])
        repeat = i2m.record_outcome_feedback(
            state, self.route, "H42", experiment_id="X600", outcome="supported",
            supported_axes=["evidence"], weakened_axes=["importance"])
        self.assertFalse(repeat["written"], "同一结果不得重复消费")
        calibration = i2m.taste_calibration(self.route, "H42")
        self.assertTrue(any(signal["axis"] == "evidence" for signal in calibration["signals"]))
        verdict = self.judge(candidate("A", importance_level="high"),
                             candidate("B", importance_level="low",
                                       falsifiable_predictions=[]),
                             calibration=calibration)
        self.assertEqual(verdict["judgement"], i2m.JUDGEMENT_PREFER)
        self.assertIn("有来源", calibration["note"])
        # history is preserved verbatim; nothing was rewritten
        document = json.loads(i2m.feedback_path(self.route, "H42").read_text(encoding="utf-8"))
        self.assertEqual(document["entries"][0]["judgement"], "prefer M-A -> M-B")

    def test_7b_one_failure_does_not_condemn_a_paradigm(self):
        state = self._state()
        i2m.record_outcome_feedback(state, self.route, "H42", experiment_id="X600",
                                    outcome="failed", weakened_axes=["evidence"])
        calibration = i2m.taste_calibration(self.route, "H42")
        evidence = next(signal for signal in calibration["signals"]
                        if signal["axis"] == "evidence")
        self.assertEqual(evidence["n"], 1)
        self.assertEqual(evidence["hint"], "", "低于 min_evidence 时不给提示")
        self.assertIn("一次失败不推断整个范式无价值", calibration["note"])


class TestProductionWiring(TasteCase):
    """The new judgement must be reached by the runtime, not only by tests."""

    def _transition(self, **kwargs):
        state, _ = shared.progress_fixture()
        # comparison happens before a design contract exists; a fixture that already carries one
        # would take the contract branch and never compare
        state["experiments"] = []
        return i2m.transition(state, insight=shared.insight(), route_dir=self.route,
                              hypothesis_id="H42", **kwargs)

    def test_calibration_from_real_results_reaches_the_comparison(self):
        """Trace: producer -> runtime entry -> consumer -> decision input."""
        state = TestExecutionCalibration._state(self)
        written = i2m.record_outcome_feedback(state, self.route, "H42", experiment_id="X600",
                                              outcome="supported", supported_axes=["evidence"],
                                              judgement="prefer M-old", source="exp:X600")
        self.assertTrue(written["written"], written)          # producer, provenance-checked
        signals = i2m.taste_calibration(self.route, "H42")["signals"]
        self.assertTrue(signals, "校准未产生信号")
        # below min_evidence the hint stays empty by design; force the hint path explicitly
        signals = [dict(signal, n=2, hint="evidence 判据过去 2/2 次被结果支持：可作为偏好依据之一")
                   for signal in signals]
        candidates = [shared.candidate("M-a", "objective", "a", "L1", importance_level="high"),
                      shared.candidate("M-b", "architecture", "b", "L2", importance_level="low")]
        # the consumer (compare_candidates) receives the calibration and reports it
        comparison = i2m.compare_candidates(candidates, calibration={"signals": signals})
        self.assertTrue(comparison["calibration_hints"], comparison)
        # and the runtime step exposes the same signals (hand-written file: no fixture coupling)
        comparison_state, _ = shared.progress_fixture()
        comparison_state["experiments"] = []
        step = i2m.transition(comparison_state, insight=shared.insight(), route_dir=self.route,
                              hypothesis_id="H42", candidates=candidates)
        self.assertTrue(step["i2m"]["calibration"], step["i2m"])
        self.assertEqual(step["i2m"]["candidate_id"], "M-a")

    def test_the_step_reports_exploration_balance(self):
        step = self._transition(candidates=[
            shared.candidate("M-a", "objective", "a", "L1", importance_level="high"),
            shared.candidate("M-b", "architecture", "b", "L2", importance_level="low",
                             operator="crossover")])
        self.assertIn("exploration", step["i2m"])
        self.assertIn("paradigms", step["i2m"]["exploration"])

    def test_the_feedback_entry_is_idempotent_for_the_same_experiment(self):
        import subprocess
        import sys
        state = TestExecutionCalibration._state(self)
        self.state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        root = pathlib.Path(__file__).resolve().parent.parent
        command = [sys.executable, str(root / "scripts" / "insight_to_method.py"), "--feedback",
                   "--state", str(self.state_path), "--route-dir", str(self.route),
                   "--hypothesis", "H42",
                   "--experiment", "X600", "--outcome", "supported",
                   "--supported-axes", "evidence", "--source", "exp:X600"]
        first = json.loads(subprocess.run(command, capture_output=True, text=True,
                                         cwd=str(root), stdin=subprocess.DEVNULL).stdout)
        second = json.loads(subprocess.run(command, capture_output=True, text=True,
                                          cwd=str(root), stdin=subprocess.DEVNULL).stdout)
        self.assertTrue(first["written"])
        self.assertFalse(second["written"])
        self.assertIn("不重复", second["reason"])


class TestBoundariesAndAnchors(TasteCase):
    def test_8_a_non_method_anchor_keeps_its_native_contribution(self):
        state, _ = shared.progress_fixture()
        for anchor in ("theory", "phenomenon", "benchmark", "negative"):
            state["contract"] = dict(state.get("contract") or {}, primary_anchor=anchor)
            path = i2m.anchor_path(state, readiness=i2m.insight_readiness(
                state, shared.insight()))
            self.assertEqual(path["path"], "ANCHOR_NATIVE", anchor)
            self.assertTrue(path["contribution"])

    def test_9_taste_never_crosses_the_hard_boundaries(self):
        verdict = self.judge(candidate("A", importance_level="high"),
                             candidate("B", importance_level="low"))
        for banned in ("gate", "allow", "authorized", "dispatched", "executed",
                       "budget", "gpu"):
            self.assertNotIn(banned, verdict)
        state = shared.progress_fixture()[0]
        self.assertIn("I2M51", i2m._rules(i2m.minimal_test_errors(
            state, dict(shared.MINIMAL_PLAN, gpu_required=True))))
        self.assertIn("I2M49", i2m._rules(i2m.minimal_test_errors(
            state, dict(shared.MINIMAL_PLAN, fairness={"capacity": True}))))

    def _state_helper(self):
        state, _ = shared.progress_fixture()
        return state

    def test_10_the_loop_does_not_repeat_completed_artifacts_or_reviews(self):
        state, _ = shared.progress_fixture()
        self.state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        i2m.write_artifact(self.route, "sketch", "H42",
                           {"problem": "p", "insight": "i", "intervention": "a",
                            "falsifier": "f"},
                           basis=i2m.hypothesis_basis(state, "H42"))
        ctx = {"state_path": self.state_path, "state": state,
               "scheduler": {"state_version": state.get("state_version"), "next_actions": [],
                             "eig_calibration": {"records": []}},
               "index": {"state_version": state.get("state_version")}, "revisions": [],
               "route_dir": self.route}
        first = pr._loop_step(ctx)
        second = pr._loop_step(ctx)
        self.assertEqual(first["stage"], "synthesis")
        self.assertEqual(second["stage"], "synthesis")
        self.assertEqual(first["i2m"]["artifacts"]["sketch"], "present")
        self.assertNotIn("compatibility_audit", first.get("action", ""))

    def test_homogenised_exploration_is_flagged_without_a_quota(self):
        state, _ = shared.progress_fixture()
        state["hypotheses"] = [{"id": "H1", "operator": "mutation"},
                               {"id": "H2", "operator": "crossover"}]
        report = i2m.exploration_balance(state)
        self.assertTrue(report["homogeneous"])
        self.assertTrue(report["fusion_or_local_only"])
        self.assertIn("counterexample_or_boundary", report["open_directions"])
        self.assertIn("不设配额", report["note"])
        mixed = i2m.exploration_balance(state, [
            {"candidate_id": "A", "operator": "counterexample"},
            {"candidate_id": "B", "operator": "mutation"}])
        self.assertFalse(mixed["homogeneous"])


if __name__ == "__main__":
    unittest.main()
