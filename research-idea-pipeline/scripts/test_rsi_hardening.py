#!/usr/bin/env python3
"""test_rsi_hardening.py — RSI 加固回归：P1/P2 六项缺陷的正向与对抗性覆盖。

每项都先在**基线 `6d00e50`** 上复现（见 `.dev/round10/record.md` 的旧版证据），再验证修复后
被阻断：

P1  每 case 运行分布 / run 身份（3+1 冒充 2+2、重复 run、跨 case 错配）
P1  Bounded Trial 派遣凭证必须与调度器遥测互相印证（禁止自述；模拟凭证不得 L3）
P1  Global 背书必须绑定候选策略（无关历史轨迹不得凑数）
P2  回滚后旧策略的缓存决策不得生效（身份 + 合法动作集合）
P2  等级计算必须使用同一份冻结规则快照
P2  非法指标值必须给出 INVALID/HOLD，而不是未捕获异常
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import cognition as cg
import policy_evolution as pe
import preset_router as pr
import research_replay as rr
import rsi_test_support as support

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "policy_evolution.py"
BENEFIT = "search_efficiency"
SCIENCE = "mechanistic_understanding"


def fixture_state(version=3):
    return {"_schema": "research-idea-pipeline/research-state@1", "state_version": version,
            "contract": {"goal": "g", "primary_anchor": "A0", "constraints": [],
                         "resources": {}, "out_of_scope": []},
            "claims": [], "evidence": [], "assumptions": [],
            "hypotheses": [{"id": "H1", "statement": "h", "status": "active",
                            "validity": "valid", "island": "P1", "operator": "reframe"}],
            "experiments": [], "literature": [], "failures": [],
            "uncertainties": [{"id": "U1", "question": "q", "importance": "high",
                               "uncertainty": "high", "status": "open", "validity": "valid"}],
            "assurance": [], "repairs": [], "narrative_view": {}, "reviews": [],
            "decision": {"verdict": "continue", "rationale": "", "next_phase": "R3"}}


class HardeningCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.route = pathlib.Path(self.temp.name) / "A"
        self.route.mkdir(parents=True)
        self.workdir = pathlib.Path(self.temp.name) / "work"
        self.state_path = self.route / cg.STATE_NAME
        self.state_path.write_text(json.dumps(fixture_state(), ensure_ascii=False) + "\n",
                                   encoding="utf-8")
        self.scheduler_path = self.route / cg.SCHEDULER_NAME
        self.scheduler_path.write_text(json.dumps({
            "state_version": 3,
            "next_actions": [{"action": "R1", "type": "repair", "target": "C1"},
                             {"action": "R2", "type": "repair", "target": "C1"}],
            "eig_calibration": {"records": []},
            "operator_stats": {"by_operator": {}, "recurring_failure_patterns": []}},
            ensure_ascii=False) + "\n", encoding="utf-8")
        self.digest = pe.freeze_evaluation_rules(self.state_path)["digest"]

    def tearDown(self):
        self.temp.cleanup()

    def shadow(self, policy_id="P-1", **overrides):
        payload = {"policy_id": policy_id, "policy_schema_version": "1",
                   "parent_policy_id": None, "status": "PROPOSED",
                   "scope": {"scope_kind": "local", "problem_structure": "reframe-loop"},
                   "applicable_conditions": [{"kind": "min_open_uncertainties", "value": 1}],
                   "strategy_changes": [{"kind": "same_tier_preference", "prefer_action": "R2"}],
                   "supporting_trajectory_ids": ["DT-1"], "counterexamples": ["c"],
                   "expected_effect": {"mechanism": "m", "direction": "up"},
                   "revalidation_conditions": ["r"], "evaluation_refs": [],
                   "rollback_target": None, "evaluation_rules_digest": self.digest}
        payload.update(overrides)
        assert pe.propose(self.state_path, payload,
                          trajectory_support={"DT-1"})["status"] == "PROPOSED"
        assert pe.transition(self.state_path, policy_id, "SHADOW",
                             level="L1")["status"] == "SHADOW"

    def evaluated(self, policy_id="P-1", **overrides):
        """A policy that has reached REPLAY_EVALUATED (the state a trial may start from)."""
        self.shadow(policy_id, **overrides)
        assert pe.evaluate_candidate(self.state_path, policy_id,
                                     self.report())["status"] == "REPLAY_EVALUATED"
        return policy_id

    def report(self, *, cases=3, runs=2, mutate=None):
        report = rr.run_suite(rr.adversarial_cases()[:cases], arms=["rsi_full", "full_cie"],
                              runs=runs)
        for arm, shift in (("rsi_full", 0.5), ("full_cie", -0.05)):
            for row in report["per_arm"][arm]["results"]:
                row["evaluation"]["metrics"][BENEFIT] = {"value": round(0.5 + shift, 4)}
            self._rebuild(report["per_arm"][arm])
        if mutate:
            report = mutate(report)
        return report

    @staticmethod
    def _rebuild(block):
        block["dimensions"] = {}
        for name in rr.METRIC_DIMENSIONS:
            values = [row["evaluation"]["metrics"][name]["value"] for row in block["results"]
                      if isinstance(row["evaluation"]["metrics"][name].get("value"), (int, float))
                      and not isinstance(row["evaluation"]["metrics"][name]["value"], bool)]
            block["dimensions"][name] = {
                "mean": round(sum(values) / len(values), 4) if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None}

    def signature(self, policy_id="P-1"):
        return pe.policy_record(pe.load_records(self.state_path)[0], policy_id)["signature"]

    def credential(self, policy_id="P-1", **overrides):
        kwargs = {"signature": self.signature(policy_id),
                  "rules_digest": pe.evaluation_rules_digest(self.state_path)}
        kwargs.update(overrides)
        return support.research_validation(self.state_path, policy_id, self.workdir, **kwargs)


# ---------------------------------------------------------------------------
# P1 — run distribution and run identity
# ---------------------------------------------------------------------------

class TestRunDistribution(HardeningCase):
    def test_an_uneven_distribution_cannot_masquerade_as_paired_runs(self):
        """3+1 must not pass as two runs for each of two cases."""
        self.shadow()

        def uneven(report):
            for arm in report["per_arm"]:
                rows = report["per_arm"][arm]["results"]
                report["per_arm"][arm]["results"] = [rows[0], rows[0], rows[0], rows[1]]
                self._rebuild(report["per_arm"][arm])
            report["cases"] = 2
            report["runs_per_case"] = 2
            return report

        result = pe.evaluate_candidate(self.state_path, "P-1",
                                       self.report(cases=2, runs=2, mutate=uneven))
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("每 case 运行次数", " ".join(result["diagnostics"]))

    def test_a_repeated_run_identity_is_refused(self):
        self.shadow()

        def duplicate(report):
            for arm in report["per_arm"]:
                for row in report["per_arm"][arm]["results"]:
                    row["run_id"] = "run-1"
                self._rebuild(report["per_arm"][arm])
            return report

        result = pe.evaluate_candidate(self.state_path, "P-1", self.report(mutate=duplicate))
        self.assertEqual(result["status"], "INVALID", result)
        self.assertTrue(any("重复" in item or "不一致" in item for item in result["diagnostics"]),
                        result["diagnostics"])

    def test_an_unpaired_run_is_refused(self):
        """A case that is missing one of the arm's runs is not a complete paired sample."""
        self.shadow()

        def unpaired(report):
            for arm in report["per_arm"]:
                rows = report["per_arm"][arm]["results"]
                rows[-1]["run_id"] = "run-9"
                self._rebuild(report["per_arm"][arm])
            return report

        result = pe.evaluate_candidate(self.state_path, "P-1", self.report(mutate=unpaired))
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("不一致", " ".join(result["diagnostics"]))

    def test_an_l3_credential_with_an_uneven_distribution_is_refused(self):
        self.evaluated()
        support.record_dispatch(self.state_path, policy_id="P-1", action="R2")
        self.assertEqual(support.begin_trial(self.state_path, "P-1")["status"], "BOUNDED_TRIAL")
        credential = self.credential()
        for arm in credential["per_arm"].values():
            rows = arm["results"]
            arm["results"] = [rows[0], rows[0], rows[0], rows[1]]
        credential["cases"] = 2
        credential["runs_per_case"] = 2
        support.approve(self.state_path, "P-1", credential)
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "INVALID", result)


# ---------------------------------------------------------------------------
# P1 — the dispatch credential must be corroborated
# ---------------------------------------------------------------------------

class TestDispatchCredential(HardeningCase):
    def test_a_self_issued_dispatch_claim_is_refused(self):
        """No scheduler telemetry: a caller-supplied dict proves nothing."""
        self.evaluated()
        result = pe.begin_bounded_trial(self.state_path, "P-1",
                                        dispatch_evidence={"dispatched": True,
                                                           "action": "R2"})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE11", result["codes"])

    def test_the_cli_no_longer_fabricates_a_dispatch(self):
        self.evaluated()
        proc = subprocess.run([sys.executable, str(SCRIPT), "trial",
                               "--state", str(self.state_path), "--policy-id", "P-1"],
                              capture_output=True, text=True)
        self.assertNotIn("Traceback", proc.stderr, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "INVALID", payload)

    def test_a_stale_dispatch_record_is_refused(self):
        self.evaluated()
        support.record_dispatch(self.state_path, policy_id="P-1", action="R2")
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state["state_version"] = state["state_version"] + 1
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        result = pe.begin_bounded_trial(self.state_path, "P-1",
                                        dispatch_evidence={"action": "R2"})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("陈旧", " ".join(result["diagnostics"]))

    def test_a_dispatch_record_for_another_policy_is_refused(self):
        self.evaluated("P-1")
        support.record_dispatch(self.state_path, policy_id="P-2", action="R2")
        result = pe.begin_bounded_trial(self.state_path, "P-1",
                                        dispatch_evidence={"action": "R2"})
        self.assertEqual(result["status"], "INVALID", result)

    def test_a_claim_that_contradicts_the_telemetry_is_refused(self):
        self.evaluated()
        support.record_dispatch(self.state_path, policy_id="P-1", action="R2")
        result = pe.begin_bounded_trial(self.state_path, "P-1",
                                        dispatch_evidence={"action": "R9"})
        self.assertEqual(result["status"], "INVALID", result)

    def test_a_corroborated_dispatch_is_accepted(self):
        self.evaluated()
        support.record_dispatch(self.state_path, policy_id="P-1", action="R2")
        result = support.begin_trial(self.state_path, "P-1")
        self.assertEqual(result["status"], "BOUNDED_TRIAL", result)
        artifact = next(pe.trials_dir(self.state_path).glob("*.json"))
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        self.assertEqual(payload["dispatch_state"], "dispatched")
        self.assertEqual(payload["dispatch_record"]["action"], "R2")
        self.assertIsNotNone(payload["dispatch_record"]["scheduler_digest"])

    def test_a_simulated_credential_cannot_reach_l3(self):
        self.evaluated()
        simulated = pe.begin_bounded_trial(self.state_path, "P-1",
                                           dispatch_evidence={"simulated": True})
        self.assertEqual(simulated["status"], "BOUNDED_TRIAL", simulated)
        credential = self.credential()
        support.approve(self.state_path, "P-1", credential)
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("模拟", " ".join(result["diagnostics"]))


# ---------------------------------------------------------------------------
# P1 — cross-project endorsement must be bound to the candidate
# ---------------------------------------------------------------------------

class TestAttestationBinding(HardeningCase):
    def _trajectory(self, project, *, policy_version, qualified=True):
        import decision_trajectory as dt
        ident = f"DT-{project}"
        dt.append_chained(self.route / dt.TRAJECTORY_NAME, {
            "_schema": "research-idea-pipeline/decision-trajectory@1", "record": "decision",
            "trajectory_id": ident, "project": project, "route": project,
            "context": {"state_version": 3, "state_digest": "sha256:x",
                        "scientific_question": "q", "decided_at": "2026-01-01T00:00:00Z"},
            "decision": {"chosen": "R2", "dispatch_status": "dispatched", "candidates": []},
            "policy_version": policy_version, "recorded_at": "2026-01-01T00:00:00Z"})
        dt.append_chained(self.route / dt.TRAJECTORY_NAME, {
            "_schema": "research-idea-pipeline/decision-trajectory@1", "record": "outcome",
            "trajectory_id": ident, "project": project,
            "evidence_qualification": "qualified" if qualified else "unqualified",
            "result": {"kind": "experiment_result", "summary": "observed x=0.42"},
            "observed_at": "2026-01-02T00:00:00Z", "at_state_version": 3})

    def _global_policy(self, policy_id="P-GLOBAL"):
        self.evaluated(policy_id, scope={"scope_kind": "global",
                                         "problem_structure": "reframe-loop"},
                       evaluation_refs=[])
        support.record_dispatch(self.state_path, policy_id=policy_id, action="R2")
        support.begin_trial(self.state_path, policy_id)
        credential = self.credential(policy_id)
        support.approve(self.state_path, policy_id, credential)
        assert pe.record_research_validation(self.state_path, policy_id,
                                             credential)["status"] == "VALIDATED"

    def test_unrelated_history_does_not_back_a_global_policy(self):
        """Trajectories from other policies in the same route must not count."""
        self._trajectory("PROJ-A", policy_version="P-OTHER")
        self._trajectory("PROJ-B", policy_version="P-OTHER")
        self._global_policy()
        result = pe.promote_to_active(self.state_path, "P-GLOBAL",
                                      {"scope_evidence_ok": True})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE14", result["codes"])

    def test_candidate_bound_history_backs_a_global_policy(self):
        self._trajectory("PROJ-A", policy_version="P-GLOBAL")
        self._trajectory("PROJ-B", policy_version="P-GLOBAL")
        self._global_policy()
        result = pe.promote_to_active(self.state_path, "P-GLOBAL",
                                      {"scope_evidence_ok": True})
        self.assertEqual(result["status"], "ACTIVE", result)

    def test_an_unqualified_outcome_does_not_count(self):
        self._trajectory("PROJ-A", policy_version="P-GLOBAL")
        self._trajectory("PROJ-B", policy_version="P-GLOBAL", qualified=False)
        self._global_policy()
        result = pe.promote_to_active(self.state_path, "P-GLOBAL",
                                      {"scope_evidence_ok": True})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE14", result["codes"])


# ---------------------------------------------------------------------------
# P2 — frozen-rule snapshot and illegal metrics
# ---------------------------------------------------------------------------

class TestFrozenSnapshotAndMetrics(HardeningCase):
    def test_the_recorded_level_uses_the_frozen_rule_snapshot(self):
        """A customised min_cases/min_runs must give the same level everywhere."""
        pe.rules_path(self.state_path).unlink()
        rules = dict(pe.DEFAULT_EVALUATION_RULES)
        rules.update({"min_cases": 1, "min_runs": 1})
        self.digest = pe.freeze_evaluation_rules(self.state_path, rules)["digest"]
        self.shadow()
        report = self.report(cases=2, runs=1)
        report["cases"] = 2
        report["runs_per_case"] = 1
        result = pe.evaluate_candidate(self.state_path, "P-1", report)
        self.assertEqual(result["status"], "REPLAY_EVALUATED", result)
        records, _ = pe.load_records(self.state_path)
        artifact = pe.latest_evaluation_artifact(self.state_path, "P-1", records)
        self.assertEqual(artifact["level"], "L2", artifact["level"])
        # the transition record must agree with the artifact computed under the frozen rules
        self.assertEqual(result["level"], "L2", result)

    def test_a_non_numeric_metric_is_a_diagnosable_refusal(self):
        for label, value in (("string", "0.9"), ("bool", True), ("list", [1, 2]),
                             ("object", {"a": 1}), ("nan", float("nan")),
                             ("inf", float("inf"))):
            with self.subTest(label=label):
                case = HardeningCase("setUp")
                case.setUp()
                try:
                    case.shadow()

                    def bad(report, value=value):
                        for arm in report["per_arm"]:
                            for row in report["per_arm"][arm]["results"]:
                                row["evaluation"]["metrics"][BENEFIT] = {"value": value}
                            case._rebuild(report["per_arm"][arm])
                        return report

                    result = pe.evaluate_candidate(case.state_path, "P-1",
                                                   case.report(mutate=bad))
                    self.assertEqual(result["status"], "INVALID", (label, result))
                    self.assertIn("有限数值", " ".join(result["diagnostics"]))
                finally:
                    case.tearDown()


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# P2 — a cached scheduler decision must belong to the policy in force
# ---------------------------------------------------------------------------

class TestCachedDecisionValidity(HardeningCase):
    def _dispatch(self, *, cached_policy, action="R2", next_actions=None):
        import strategy_memory as sm
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        scheduler = json.loads(self.scheduler_path.read_text(encoding="utf-8"))
        if next_actions is not None:
            scheduler["next_actions"] = next_actions
        advice = {"policy_id": cached_policy} if cached_policy else None
        updated = sm.record_strategy_decision(scheduler, {
            "state_version": state.get("state_version"), "advice": advice, "chosen": action,
            "adopted": True, "strategy_applied": bool(cached_policy), "decision_changed": False,
            "reason_if_not": None, "hard_gates": {}, "dispatch": {"action": action}},
            dispatch_result=f"dispatched {action}")
        return pr.strategy_dispatch({"state_path": self.state_path, "state": state,
                                     "index": None, "scheduler": updated, "revisions": [],
                                     "route_dir": self.route})

    def test_a_cached_decision_from_a_policy_no_longer_in_force_is_not_consumed(self):
        """Rollback changes the policy without changing the state version."""
        dispatch = self._dispatch(cached_policy="P-ROLLED-BACK")
        self.assertFalse(dispatch["applied"], dispatch)
        self.assertEqual(dispatch["source"], "stale_cached_decision", dispatch)
        self.assertEqual(dispatch["reason"], "stale_cached_policy_decision", dispatch)

    def test_a_cached_action_outside_the_legal_action_set_is_not_consumed(self):
        dispatch = self._dispatch(cached_policy=None, action="R9",
                                  next_actions=[{"action": "R1", "type": "repair",
                                                 "target": "C1"}])
        self.assertFalse(dispatch["applied"], dispatch)
        self.assertEqual(dispatch["reason"], "cached_action_not_in_legal_set", dispatch)
        self.assertEqual(dispatch["source"], "stale_cached_decision", dispatch)

    def test_a_scheduler_only_cached_decision_is_still_consumed(self):
        """No policy is involved, so the existing scheduler fallback must keep working."""
        dispatch = self._dispatch(cached_policy=None)
        self.assertTrue(dispatch["applied"], dispatch)
        self.assertEqual(dispatch["source"], "recorded_strategy_decision", dispatch)
        self.assertEqual(dispatch["action"], "R2", dispatch)
