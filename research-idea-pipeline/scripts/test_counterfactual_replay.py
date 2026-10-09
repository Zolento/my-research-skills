#!/usr/bin/env python3
"""test_counterfactual_replay.py — Skill-RSI Phase 3 acceptance.

The failure modes under test are the ones that turn "replay" into a false-positive
generator: scoring a branch that was never executed, letting a candidate policy act
without a promotion gate, treating a literature search that crosses the decision
time as visible, or reading a hidden answer out of a file on disk.

The four frozen ablation arms must keep their exact meaning; the RSI arms are additive.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

import cognition as cg
import decision_trajectory as dt
import research_replay as rr

ROOT = pathlib.Path(__file__).resolve().parent.parent


def base_case():
    return rr.adversarial_cases()[0]


def policy_case(base=None, *, status="ACTIVE", prefer="X9", scope=True, trajectory=True,
                replay_ref=True, support=("X9", "X1")):
    case = json.loads(json.dumps(base if base is not None else base_case()))
    case["visible"]["policy_candidates"] = [{
        "policy_id": "P-1",
        "status": status,
        "strategy_changes": [{"kind": "same_tier_preference", "prefer_action": prefer}],
        "supporting_trajectory_ids": ["DT-1"] if trajectory else [],
        "evaluation_refs": [{"independent": True, "verdict": "SUPPORTED"}] if replay_ref else [],
        "scope": {"problem_structure": "fixture"} if scope else {},
    }]
    case["visible"]["legal_actions"] = [
        {"action": prefer, "type": "repair", "target": "C1", "eig": "high", "cost": "low"},
        {"action": "X1", "type": "discriminating_experiment", "target": "C1",
         "eig": "high", "cost": "low"}]
    case["visible"]["evidence_support"] = {
        "observed_actions": [],
        "replay_supported_actions": list(support) if support is not None else [],
    }
    return case


class TestEvidenceSupportClasses(unittest.TestCase):
    def test_an_observed_action_is_observed(self):
        tag = rr.classify_evidence_support({}, {"chosen_intervention": "X9"},
                                           {"observed_actions": ["X9"],
                                            "replay_supported_actions": ["X9"]})
        self.assertEqual(tag["class"], "OBSERVED")

    def test_a_historically_executed_branch_is_replay_supported(self):
        tag = rr.classify_evidence_support({}, {"chosen_intervention": "X9"},
                                           {"observed_actions": ["X1"],
                                            "replay_supported_actions": ["X1", "X9"]})
        self.assertEqual(tag["class"], "REPLAY_SUPPORTED")

    def test_a_never_executed_branch_is_no_support(self):
        tag = rr.classify_evidence_support({}, {"chosen_intervention": "X9"},
                                           {"observed_actions": ["X1"],
                                            "replay_supported_actions": ["X1"]})
        self.assertEqual(tag["class"], "NO_SUPPORT")
        self.assertIn("不可观测", tag["reason"])

    def test_an_empty_declared_map_is_not_replaced_by_a_derived_one(self):
        case = policy_case(support=None)
        self.assertEqual(
            rr.classify_evidence_support(case, {"chosen_intervention": "X9"})["class"],
            "NO_SUPPORT")

    def test_every_case_reports_a_class_without_being_summed(self):
        result = rr.run_case(base_case(), "full_cie")
        evaluation = result["evaluation"]
        self.assertIn(evaluation["evidence_support"]["class"], rr.EVIDENCE_SUPPORT_CLASSES)
        blob = json.dumps(evaluation, ensure_ascii=False)
        for key in ("total", "overall", "score", "weighted"):
            self.assertNotIn(f'"{key}"', blob)


class TestPolicyGuardAblation(unittest.TestCase):
    def test_full_rsi_applies_an_evaluated_scoped_policy(self):
        result = rr.run_case(policy_case(), "rsi_full")
        self.assertTrue(result["decision"].get("policy_applied"))
        self.assertEqual(result["decision"]["candidate_choice"], "X9")

    def test_shadow_records_intent_without_acting(self):
        result = rr.run_case(policy_case(), "rsi_shadow")
        self.assertEqual(result["decision"].get("policy_shadow_choice"), "X9")
        self.assertNotEqual(result["decision"].get("chosen_intervention"), "X9")
        self.assertFalse(result["decision"].get("policy_applied"))

    def test_the_promotion_gate_blocks_a_proposed_policy(self):
        blocked = rr.run_case(policy_case(status="PROPOSED"), "rsi_full")
        self.assertFalse(blocked["decision"].get("policy_applied"))
        self.assertIn("candidate_not_promoted", blocked["decision"].get("policy_reason_if_not", ""))
        without = rr.run_case(policy_case(status="PROPOSED"), "rsi_without_promotion")
        self.assertTrue(without["decision"].get("policy_gate_bypassed"))

    def test_scope_and_replay_guards_are_measurable(self):
        unscoped = rr.run_case(policy_case(scope=False), "rsi_full")
        self.assertFalse(unscoped["decision"].get("policy_applied"))
        without_scope = rr.run_case(policy_case(scope=False), "rsi_without_scope")
        self.assertTrue(without_scope["decision"].get("policy_scope_bypassed"))
        unevaluated = rr.run_case(policy_case(replay_ref=False), "rsi_full")
        self.assertFalse(unevaluated["decision"].get("policy_applied"))
        without_replay = rr.run_case(policy_case(replay_ref=False), "rsi_without_replay")
        self.assertTrue(without_replay["decision"].get("policy_support_bypassed"))

    def test_an_unobserved_branch_is_refused_and_flagged(self):
        result = rr.run_case(policy_case(support=None), "rsi_full")
        self.assertFalse(result["decision"].get("policy_applied"))
        self.assertTrue(result["decision"].get("policy_used_unobserved_branch"))
        self.assertEqual(result["evaluation"]["evidence_support"]["class"], "NO_SUPPORT")
        self.assertTrue(rr._behaviour_present("use_unobserved_branch", result["decision"],
                                              policy_case(support=None)))

    def test_the_ablation_extends_the_frozen_ladder(self):
        case = policy_case()
        report = rr.run_suite([case], rr.RSI_ARMS, 1)
        self.assertEqual(set(report["per_arm"]), set(rr.RSI_ARMS))
        self.assertTrue(set(rr.ABLATION_ARMS).isdisjoint(set(rr.RSI_ARMS)))
        self.assertEqual(set(rr.ABLATION_ARMS), {"baseline", "memory_only",
                                                 "memory_prediction", "full_cie"})
        self.assertTrue(all("evidence_support" in block
                            for block in report["per_arm"].values()))

    def test_the_default_suite_still_runs_the_four_frozen_arms(self):
        report = rr.run_suite([base_case()], runs=1)
        self.assertEqual(set(report["per_arm"]), set(rr.ABLATION_ARMS))


class TestLeakageIsolation(unittest.TestCase):
    def test_the_original_substring_guard_still_fires(self):
        case = json.loads(json.dumps(base_case()))
        case["visible"]["known_conditions"].append(case["hidden"]["later_results"][0])
        self.assertTrue(rr.leak_scan(case, rr.visible_view(case)))

    def test_a_literature_time_boundary_violation_is_detected(self):
        case = json.loads(json.dumps(base_case()))
        case["visible"]["decision_time"] = "2020-05-01"
        case["visible"]["available_literature"] = ["[Journal 2026] a later result"]
        audit = rr.leak_audit(case, rr.visible_view(case))
        self.assertTrue(any(item.startswith("RP6") for item in audit), audit)

    def test_a_hidden_answer_in_a_readable_file_is_detected(self):
        case = base_case()
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "case.json").write_text(json.dumps(case), encoding="utf-8")
            (root / "notes.txt").write_text(case["hidden"]["later_results"][0], encoding="utf-8")
            audit = rr.leak_audit(case, rr.visible_view(case), case_dir=root)
            self.assertTrue(any(item.startswith("RP7") for item in audit), audit)

    def test_a_symlink_out_of_the_case_directory_is_detected(self):
        case = base_case()
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            root = pathlib.Path(temp)
            secret = pathlib.Path(outside) / "answer.txt"
            secret.write_text(case["hidden"]["later_results"][0], encoding="utf-8")
            (root / "link.txt").symlink_to(secret)
            audit = rr.leak_audit(case, rr.visible_view(case), case_dir=root)
            self.assertTrue(any("符号链接" in item for item in audit), audit)

    def test_cognitive_memory_carrying_future_information_is_detected(self):
        case = json.loads(json.dumps(base_case()))
        case["visible"]["cognition"] = {"mechanisms": [
            {"id": "LM-1", "statement": case["hidden"]["later_results"][0]}]}
        audit = rr.leak_audit(case, rr.visible_view(case))
        self.assertTrue(any(item.startswith("RP8") for item in audit), audit)

    def test_evaluation_refuses_a_case_without_isolation(self):
        case = json.loads(json.dumps(base_case()))
        case["visible"]["decision_time"] = "2019"
        case["visible"]["available_literature"] = ["[Journal 2027] future"]
        with self.assertRaises(cg.CognitionError):
            rr.run_case(case, "full_cie", require_isolation=True)


class TestRealHistoryIngestion(unittest.TestCase):
    def _trajectory(self, root):
        path = root / dt.TRAJECTORY_NAME
        state = json.loads((ROOT / "templates" / "research-state.template.json")
                           .read_text(encoding="utf-8"))
        context = dt.build_context(state, scientific_question="q",
                                   active_hypotheses=["H1"], key_uncertainties=["U1"],
                                   visible_evidence=[], decided_at="2026-01-01T00:00:00Z")
        decision = dt.build_decision_record(
            state, route="A", project="fixture", context=context,
            candidates=[{"action": "X1", "type": "discriminating_experiment", "target": "U1",
                         "eig": "high", "cost": "low"}],
            chosen="X1", scheduler_priority={"level": 4, "label": "high_information_gain_test"},
            recorded_at="2026-01-01T00:00:00Z")
        dt.append_record(path, decision, state=state, route="A")
        outcome = dt.build_outcome_record(
            decision["trajectory_id"], at_state_version=state["state_version"],
            result={"kind": "experiment_result", "summary": "observed value 0.42"},
            decision_delta="decision", evidence_qualification="qualified",
            observed_at="2026-01-02T00:00:00Z")
        dt.append_record(path, outcome, state=state, route="A")
        return path, state

    def test_support_map_separates_observed_from_pending(self):
        with tempfile.TemporaryDirectory() as temp:
            path, _ = self._trajectory(pathlib.Path(temp))
            support = rr.support_map_from_trajectory(path)
            self.assertEqual(support["observed_actions"], ["X1"])
            self.assertIn("X1", support["replay_supported_actions"])

    def test_coverage_report_states_the_unobservable_part(self):
        with tempfile.TemporaryDirectory() as temp:
            path, _ = self._trajectory(pathlib.Path(temp))
            report = rr.coverage_report(path)
            self.assertEqual(report["trajectories"], 1)
            self.assertEqual(report["evaluable_fraction"], 1.0)
            self.assertIn("不得用模型预测补造结果", report["note"])

    def test_cases_from_trajectory_never_invents_a_hidden_answer(self):
        with tempfile.TemporaryDirectory() as temp:
            path, state = self._trajectory(pathlib.Path(temp))
            self.assertEqual(rr.cases_from_trajectory(path, state=state, hidden_answers={}), [])
            built = rr.cases_from_trajectory(
                path, state=state,
                hidden_answers={dt.rebuild_trajectories(dt.load_records(path)[0]).popitem()[0]:
                                {"true_outcome_class": "PREDICTION_HELD",
                                 "discriminating_intervention": "X1"}})
            self.assertEqual(len(built), 1)
            self.assertEqual(rr.case_errors(built[0]), [])


if __name__ == "__main__":
    unittest.main()
