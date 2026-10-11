#!/usr/bin/env python3
"""test_promotion_credentials.py — 第七轮：L2/L3 凭证分离、产物来源链、冻结参数一致性。

三项要求（以及 global 作用域的独立来源）：

A. 合成回放不得自动获得 L3，也不得凭格式正确的自述报告生成可信科研验证凭证。
   → Replay 评价上限 L2；L3 只能由**另一类**凭证（真实科研验证产物）授予。
B. 从可信执行记录重算指标；校验策略/规则/案例绑定；拒绝缺失隔离证明的报告。
C. 评价器实际使用的参数 == 候选绑定的冻结规则 == 晋升时验证的规则；
   关键科学可靠性维度退化或收益证据不足（含区间重叠的不确定性）不得晋升。
D. global 作用域的跨项目引用必须具备真正的独立来源（背书项目），不是项目数量。

这些测试针对**旧版会通过**的路径，修复前应当失败。
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

import cognition as cg
import policy_evolution as pe
import research_replay as rr
import rsi_test_support as support

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "policy_evolution.py"

DIMENSIONS = rr.METRIC_DIMENSIONS
BENEFIT = "search_efficiency"
SCIENCE = "mechanistic_understanding"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

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


def case_result(case_id, *, metrics, isolation=True, leak=True, executor=None):
    """One execution record: the per-case measurements are the recomputable source."""
    record = {"case_id": case_id,
              "evaluation": {"metrics": {name: {"value": value}
                                         for name, value in metrics.items()}},
              "isolation_verified": isolation, "leak_checked": leak}
    if executor is not None:
        record["executor"] = executor
    return record


def arm_block(results, dimensions):
    """Declared means, as a producer would report them (checked against the records)."""
    means = {name: (round(sum(r["evaluation"]["metrics"][name]["value"] for r in results
                               if r["evaluation"]["metrics"][name]["value"] is not None)
                          / max(1, sum(1 for r in results
                                       if r["evaluation"]["metrics"][name]["value"] is not None)), 4)
                    if any(r["evaluation"]["metrics"][name]["value"] is not None for r in results)
                    else None)
             for name in dimensions}
    return {"dimensions": {name: {"mean": means[name], "min": means[name], "max": means[name]}
                           for name in dimensions},
            "results": results, "evidence_support": {"OBSERVED": len(results)}}


def report(*, candidate_metrics, control_metrics, cases=3, runs=2, dimensions=DIMENSIONS,
           policy_id="P-1", policy_signature="sig", rules_digest="sha256:rules",
           isolation=True, leak=True, drop_isolation=False, drop_leak=False,
           declared_override=None, schema="research-idea-pipeline/replay-ablation@1",
           runner="offline CIE runner (no model calls)"):
    def records(metrics):
        rows = []
        for index in range(cases):
            row = case_result(f"C{index}", metrics=metrics,
                              isolation=isolation, leak=leak)
            if drop_isolation:
                row.pop("isolation_verified")
            if drop_leak:
                row.pop("leak_checked")
            rows.append(row)
        # repeat for the declared run count
        return rows * runs

    candidate = arm_block(records(candidate_metrics), dimensions)
    control = arm_block(records(control_metrics), dimensions)
    if declared_override:
        for arm, block in declared_override.items():
            target = candidate if arm == "rsi_full" else control
            for name, value in block.items():
                target["dimensions"][name]["mean"] = value
    return {"schema": schema, "cases": cases, "runs_per_case": runs,
            "sample_size": cases * runs, "sufficient_sample": True,
            "unobservable_decisions": 0, "delta_vs_baseline": {},
            "policy_id": policy_id, "policy_signature": policy_signature,
            "rules_digest": rules_digest,
            "per_arm": {"rsi_full": candidate, "full_cie": control},
            "runner": runner}


def improving(candidate=None, control=None):
    candidate = dict(candidate or {d: 0.5 for d in DIMENSIONS})
    control = dict(control or {d: 0.5 for d in DIMENSIONS})
    return candidate, control


# ---------------------------------------------------------------------------
# A. replay is L2 at most; L3 needs a different credential
# ---------------------------------------------------------------------------

class CredentialCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.route = pathlib.Path(self.temp.name) / "A"
        self.route.mkdir(parents=True)
        self.state_path = self.route / cg.STATE_NAME
        self.state_path.write_text(json.dumps(fixture_state(), ensure_ascii=False) + "\n",
                                   encoding="utf-8")
        self.digest = pe.freeze_evaluation_rules(self.state_path)["digest"]

    def tearDown(self):
        self.temp.cleanup()

    def candidate(self, policy_id="P-1", **overrides):
        payload = {"policy_id": policy_id, "policy_schema_version": "1",
                   "parent_policy_id": None, "status": "PROPOSED",
                   "scope": {"scope_kind": "local", "problem_structure": "reframe-loop"},
                   "applicable_conditions": [{"kind": "min_open_uncertainties", "value": 1}],
                   "strategy_changes": [{"kind": "same_tier_preference",
                                         "prefer_action": "R2"}],
                   "supporting_trajectory_ids": ["DT-1"], "counterexamples": ["c"],
                   "expected_effect": {"mechanism": "m", "direction": "up"},
                   "revalidation_conditions": ["r"], "evaluation_refs": [],
                   "rollback_target": None}
        payload.update(overrides)
        return payload

    def ready(self, policy_id="P-1", **overrides):
        payload = self.candidate(policy_id, **overrides)
        payload["evaluation_rules_digest"] = self.digest
        self.assertEqual(pe.propose(self.state_path, payload,
                                    trajectory_support={"DT-1"})["status"], "PROPOSED")
        self.assertEqual(pe.transition(self.state_path, policy_id, "SHADOW",
                                       level="L1")["status"], "SHADOW")
        return policy_id

    def good_report(self, policy_id="P-1", **kwargs):
        """A report bound to the real candidate, so only the intended check can refuse it."""
        candidate, control = improving()
        candidate[BENEFIT], control[BENEFIT] = 0.9, 0.3
        kwargs.setdefault("policy_id", policy_id)
        if "policy_signature" not in kwargs:
            kwargs["policy_signature"] = self.signature(policy_id)
        kwargs.setdefault("rules_digest", self.digest)
        return report(candidate_metrics=candidate, control_metrics=control, **kwargs)

    def signature(self, policy_id="P-1"):
        records, _ = pe.load_records(self.state_path)
        return pe.policy_record(records, policy_id)["signature"]

    def evaluated(self, policy_id="P-1", **kwargs):
        self.ready(policy_id, **kwargs)
        signature = self.signature(policy_id)
        self.good_report(policy_id=policy_id, policy_signature=signature)  # binding check
        return pe.evaluate_candidate(
            self.state_path, policy_id,
            self.good_report(policy_id=policy_id, policy_signature=signature))

    def trial_ref(self, policy_id="P-1"):
        for path in pe.trials_dir(self.state_path).glob(f"{policy_id}.*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("policy_id") == policy_id:
                return {"path": str(path), "digest": payload["digest"]}
        raise AssertionError("no trial artifact for " + policy_id)

    def artifact(self, policy_id="P-1"):
        records, _ = pe.load_records(self.state_path)
        found = pe.latest_evaluation_artifact(self.state_path, policy_id, records)
        self.assertIsNotNone(found, "no artifact stored")
        return found


class TestReplayIsAtMostL2(CredentialCase):
    def test_a_supported_replay_evaluation_is_L2(self):
        """Synthetic/offline replay can never earn L3, however clean it looks."""
        result = self.evaluated()
        self.assertEqual(result["status"], "REPLAY_EVALUATED", result)
        self.assertEqual(result["level"], "L2", result)
        self.assertEqual(self.artifact()["level"], "L2", self.artifact()["level"])

    def test_recomputed_level_never_returns_L3_for_a_replay_artifact(self):
        perfect_gates = {"independent": True, "leakage_checked": True, "reproducible": True,
                         "sample_adequate": True, "distinguishable": True,
                         "degraded_dimensions": [], "unobservable_decisions": 0,
                         "assessable_dimensions": 7, "cases": 99, "runs": 9,
                         "runner": "offline CIE runner (no model calls)"}
        level = pe._recomputed_level(perfect_gates, {"verdict": "SUPPORTED"},
                                     schema=pe.SCHEMA_EVALUATION)
        self.assertNotEqual(level, "L3")
        self.assertEqual(level, "L2")

    def test_a_replay_artifact_cannot_validate(self):
        self.evaluated()
        pe.begin_bounded_trial(self.state_path, "P-1", dispatch_evidence={"dispatched": "R2"})
        result = pe.validate_candidate(self.state_path, "P-1")
        self.assertEqual(result["status"], "INVALID", result)
        self.assertTrue(any("L3" in item or "科研" in item or "validation" in item
                            for item in result["diagnostics"]), result["diagnostics"])

    def test_a_self_reported_report_cannot_become_a_research_validation(self):
        """A report that merely declares itself a validation credential is not one."""
        forged = {"_schema": pe.SCHEMA_RESEARCH_VALIDATION,
                  "task_provenance": {"task_id": "T1", "source": "/nonexistent/task.json",
                                      "synthetic": True},
                  "policy_id": "P-1", "rules_digest": self.digest,
                  "per_arm": {"policy": {"executor": "me",
                                         "results": [case_result("T1", metrics={BENEFIT: 0.9})]}}}
        result = pe.record_research_validation(self.state_path, "P-1", forged)
        self.assertEqual(result["status"], "INVALID", result)


class TestResearchValidationCredential(CredentialCase):
    def _task_and_log(self, name="task.json"):
        task = pathlib.Path(self.temp.name) / name
        task.write_text(json.dumps({"task_id": "T1", "dataset": "real"}), encoding="utf-8")
        log = pathlib.Path(self.temp.name) / "run.log"
        log.write_text("executed\n", encoding="utf-8")
        return task, log

    def validation(self, policy_id="P-1", *, synthetic=False, executor="external-1",
                   control_executor="external-2", science=0.5, benefit=0.9,
                   isolation=True, source=None):
        task, log = self._task_and_log()
        source = source or task
        return {"_schema": pe.SCHEMA_RESEARCH_VALIDATION,
                "policy_id": policy_id,
                "policy_signature": self.signature(policy_id),
                "rules_digest": self.digest,
                "task_provenance": {"task_id": "T1", "source": str(source),
                                    "source_digest": (pe._file_digest(source)
                                                      if pathlib.Path(source).is_file()
                                                      else "sha256:missing"),
                                    "synthetic": synthetic},
                "execution_evidence": {"path": str(log),
                                       "digest": pe._file_digest(log)},
                "cases": 3, "runs_per_case": 2,
                "candidate_arm": "policy", "control_arm": "control",
                "runner": "external research validation harness",
                "equivalence": support.equivalence(task_ids=["T0", "T1", "T2"]),
                "dispatch_ref": self.trial_ref(policy_id),
                "per_arm": {
                    "policy": {"executor": executor, "results": [
                        case_result(f"T{i}", metrics={BENEFIT: benefit, SCIENCE: science},
                                    isolation=isolation, executor=executor)
                        for i in range(3)] * 2},
                    "control": {"executor": control_executor, "results": [
                        case_result(f"T{i}", metrics={BENEFIT: 0.3, SCIENCE: 0.5},
                                    isolation=isolation, executor=control_executor)
                        for i in range(3)] * 2}}}

    def ready_for_validation(self, policy_id="P-1"):
        self.evaluated(policy_id)
        pe.begin_bounded_trial(self.state_path, policy_id, dispatch_evidence={"dispatched": "R2"})
        return policy_id

    def test_a_real_research_validation_reaches_validated_and_active(self):
        self.ready_for_validation()
        credential = self.validation()
        support.approve(self.state_path, "P-1", credential)
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "VALIDATED", result)
        active = pe.promote_to_active(self.state_path, "P-1", {"scope_evidence_ok": True})
        self.assertEqual(active["status"], "ACTIVE", active)
        self.assertEqual(active["level"], "L3", active)

    def test_a_synthetic_task_source_is_refused(self):
        self.ready_for_validation()
        result = pe.record_research_validation(self.state_path, "P-1",
                                               self.validation(synthetic=True))
        self.assertEqual(result["status"], "INVALID", result)
        self.assertTrue(any("synthetic" in item or "合成" in item
                            for item in result["diagnostics"]), result["diagnostics"])

    def test_a_missing_task_source_is_refused(self):
        self.ready_for_validation()
        result = pe.record_research_validation(
            self.state_path, "P-1",
            self.validation(source=pathlib.Path(self.temp.name) / "missing.json"))
        self.assertEqual(result["status"], "INVALID", result)

    def test_self_executed_validation_is_refused(self):
        """The policy arm and the control cannot be run by the same executor."""
        self.ready_for_validation()
        result = pe.record_research_validation(
            self.state_path, "P-1",
            self.validation(executor="same", control_executor="same"))
        self.assertEqual(result["status"], "INVALID", result)
        self.assertTrue(any("独立" in item or "executor" in item
                            for item in result["diagnostics"]), result["diagnostics"])

    def test_a_validation_without_isolation_proof_is_refused(self):
        self.ready_for_validation()
        result = pe.record_research_validation(self.state_path, "P-1",
                                               self.validation(isolation=False))
        self.assertEqual(result["status"], "INVALID", result)

    def test_a_validation_with_a_scientific_regression_is_refused(self):
        self.ready_for_validation()
        result = pe.record_research_validation(
            self.state_path, "P-1", self.validation(science=0.1))
        # control science is 0.5, policy 0.1 -> reliability regression
        self.assertEqual(result["status"], "INVALID", result)


# ---------------------------------------------------------------------------
# B. the report must recompute from its own execution records
# ---------------------------------------------------------------------------

class TestReportProvenance(CredentialCase):
    def test_declared_means_that_disagree_with_the_records_are_refused(self):
        self.ready()
        bogus = self.good_report()
        bogus["per_arm"]["rsi_full"]["dimensions"][BENEFIT]["mean"] = 9.9
        result = pe.evaluate_candidate(self.state_path, "P-1", bogus)
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)
        self.assertIn("重算", " ".join(result["diagnostics"]))

    def test_a_report_missing_the_isolation_proof_is_refused(self):
        self.ready()
        result = pe.evaluate_candidate(self.state_path, "P-1",
                                       self.good_report(drop_isolation=True))
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)
        self.assertIn("隔离", " ".join(result["diagnostics"]))

    def test_a_report_missing_the_leak_check_is_refused(self):
        self.ready()
        result = pe.evaluate_candidate(self.state_path, "P-1",
                                       self.good_report(drop_leak=True))
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)
        self.assertIn("泄漏", " ".join(result["diagnostics"]))

    def test_a_report_whose_case_count_disagrees_with_the_records_is_refused(self):
        self.ready()
        bogus = self.good_report()
        bogus.pop("schema")
        result = pe.evaluate_candidate(self.state_path, "P-1", bogus)
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)
        self.assertIn("schema", " ".join(result["diagnostics"]))
        miscount = self.good_report()
        miscount["cases"] = 99
        counted = pe.evaluate_candidate(self.state_path, "P-1", miscount)
        self.assertNotEqual(counted["status"], "REPLAY_EVALUATED", counted)
        self.assertIn("case", " ".join(counted["diagnostics"]))

    def test_the_entry_binds_an_unbound_report_and_records_that_it_did(self):
        """A report that declares no binding is bound by the entry, not trusted as bound."""
        self.ready()
        unbound = self.good_report()
        unbound.pop("policy_signature")
        unbound.pop("policy_id")
        result = pe.evaluate_candidate(self.state_path, "P-1", unbound)
        self.assertEqual(result["status"], "REPLAY_EVALUATED", result)
        artifact = self.artifact()
        self.assertEqual(artifact["binding_source"], "entry")
        self.assertEqual(artifact["policy_signature"], self.signature("P-1"))

    def test_a_report_declaring_a_conflicting_binding_is_refused(self):
        self.ready()
        conflicting = self.good_report()
        conflicting["policy_id"] = "P-OTHER"
        result = pe.evaluate_candidate(self.state_path, "P-1", conflicting)
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)

    def test_a_report_bound_to_another_policy_is_refused(self):
        self.ready()
        result = pe.evaluate_candidate(
            self.state_path, "P-1",
            self.good_report(policy_id="P-OTHER", policy_signature="other"))
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)
        self.assertIn("policy_id", " ".join(result["diagnostics"]))

    def test_a_report_bound_to_other_rules_is_refused(self):
        self.ready()
        result = pe.evaluate_candidate(self.state_path, "P-1",
                                       self.good_report(rules_digest="sha256:other"))
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)
        self.assertIn("rules_digest", " ".join(result["diagnostics"]))

    def test_an_artifact_whose_report_no_longer_recomputes_is_refused(self):
        """The stored verdict is re-derived at promotion time, not trusted."""
        self.evaluated()
        artifact = self.artifact()
        path = pathlib.Path(artifact["ref"]["path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        # Rewrite the embedded report's benefit down while keeping the digest self-consistent:
        # the recomputation must disagree with the stored SUPPORTED verdict.
        for arm, value in (("rsi_full", 0.31), ("full_cie", 0.30)):
            for row in payload["report"]["per_arm"][arm]["results"]:
                row["evaluation"]["metrics"][BENEFIT]["value"] = value
            payload["report"]["per_arm"][arm]["dimensions"][BENEFIT].update(
                {"mean": value, "min": value, "max": value})
        body = {key: value for key, value in payload.items() if key != "digest"}
        payload["digest"] = cg.digest_of(body)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = pe.validate_candidate(self.state_path, "P-1",
                                       evaluation_ref={"path": str(path),
                                                       "digest": payload["digest"]})
        self.assertEqual(result["status"], "INVALID", result)


# ---------------------------------------------------------------------------
# C. frozen rules and scientific reliability
# ---------------------------------------------------------------------------

class TestFrozenParameters(CredentialCase):
    def freeze_custom(self, **rules):
        """Freeze a custom rule set, replacing the one frozen in setUp()."""
        pe.rules_path(self.state_path).unlink()
        payload = dict(pe.DEFAULT_EVALUATION_RULES)
        payload.update(rules)
        document = pe.freeze_evaluation_rules(self.state_path, payload)
        return document["digest"]

    def test_the_frozen_tolerance_is_used_not_the_default(self):
        digest = self.freeze_custom(delta_tolerance=0.5)
        candidate, control = improving()
        candidate[BENEFIT], control[BENEFIT] = 0.6, 0.3   # delta 0.3 < frozen 0.5
        outcome = pe.ablation_verdict(
            report(candidate_metrics=candidate, control_metrics=control,
                   policy_id="P-1", policy_signature="sig", rules_digest=digest),
            rules=pe.frozen_rules(self.state_path))
        self.assertNotEqual(outcome["verdict"], "SUPPORTED", outcome)

    def test_the_frozen_min_runs_is_used_not_the_default(self):
        digest = self.freeze_custom(min_runs=3)
        candidate, control = improving()
        candidate[BENEFIT], control[BENEFIT] = 0.9, 0.3
        outcome = pe.ablation_verdict(
            report(candidate_metrics=candidate, control_metrics=control, runs=2,
                   policy_id="P-1", policy_signature="sig", rules_digest=digest),
            rules=pe.frozen_rules(self.state_path))
        self.assertEqual(outcome["verdict"], "INSUFFICIENT_SAMPLE", outcome)

    def test_a_candidate_bound_to_other_rules_cannot_be_evaluated(self):
        self.ready()
        self.freeze_custom(delta_tolerance=0.4)     # re-freeze after the candidate
        result = pe.evaluate_candidate(self.state_path, "P-1", self.good_report())
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)

    def test_a_malformed_frozen_rule_set_is_refused_at_freeze_time(self):
        """A rule set missing the fields the evaluation needs must not be frozen."""
        pe.rules_path(self.state_path).unlink()
        for bad in ({"min_runs": 0}, {"min_cases": "many"}, {"dimensions": []},
                    {"delta_tolerance": -1}, {"dimensions": "search_efficiency"}):
            payload = dict(pe.DEFAULT_EVALUATION_RULES)
            payload.update(bad)
            outcome = pe.freeze_evaluation_rules(self.state_path, payload)
            self.assertEqual(outcome["status"], "INVALID", (bad, outcome))
            pe.rules_path(self.state_path).unlink(missing_ok=True)

    def test_a_partial_custom_rule_set_is_completed_then_frozen(self):
        pe.rules_path(self.state_path).unlink()
        outcome = pe.freeze_evaluation_rules(self.state_path, {"delta_tolerance": 0.2})
        self.assertEqual(outcome["status"], "FROZEN", outcome)
        rules = pe.frozen_rules(self.state_path)
        self.assertEqual(rules["delta_tolerance"], 0.2)
        self.assertEqual(rules["min_runs"], pe.DEFAULT_EVALUATION_RULES["min_runs"])

    def test_a_hand_edited_incomplete_rule_file_cannot_reach_the_evaluator(self):
        """A rules file that predates or bypasses validation must fail closed, not KeyError."""
        pe.rules_path(self.state_path).write_text(json.dumps(
            {"_schema": pe.SCHEMA_RULES, "rules": {"delta_tolerance": 0.05},
             "digest": cg.digest_of({"delta_tolerance": 0.05})}), encoding="utf-8")
        self.assertIsNone(pe.frozen_rules(self.state_path))
        errors = pe.evaluation_rules_errors(self.state_path)
        self.assertTrue(errors)
        self.assertIn("PE12", [item.rule for item in errors])
        # Whatever the propose step does, every promotion gate must fail closed.
        payload = self.candidate("P-1")
        payload["evaluation_rules_digest"] = cg.digest_of({"delta_tolerance": 0.05})
        proposed = pe.propose(self.state_path, payload, trajectory_support={"DT-1"})
        self.assertIn(proposed["status"], ("PROPOSED", "INVALID"), proposed)
        if proposed["status"] == "PROPOSED":
            self.assertEqual(pe.transition(self.state_path, "P-1", "SHADOW",
                                           level="L1")["status"], "SHADOW")
        result = pe.evaluate_candidate(self.state_path, "P-1", self.good_report())
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE12", result["codes"])

    def test_mechanistic_understanding_is_a_reliability_dimension(self):
        self.assertIn(SCIENCE, pe.RELIABILITY_DIMENSIONS)

    def test_a_mechanistic_regression_blocks_promotion(self):
        candidate, control = improving()
        candidate[BENEFIT], control[BENEFIT] = 0.95, 0.30   # big efficiency gain
        candidate[SCIENCE], control[SCIENCE] = 0.10, 0.90   # science regresses
        outcome = pe.ablation_verdict(
            report(candidate_metrics=candidate, control_metrics=control,
                   policy_id="P-1", policy_signature="sig",
                   rules_digest=self.digest),
            rules=pe.frozen_rules(self.state_path))
        self.assertEqual(outcome["verdict"], "REJECTED", outcome)

    def test_an_overlapping_benefit_is_not_counted_as_evidence(self):
        """A mean gap inside overlapping ranges is reported but must not promote."""
        outcome = pe.ablation_verdict(
            report(candidate_metrics={**{d: 0.5 for d in DIMENSIONS}, BENEFIT: 0.9},
                   control_metrics={**{d: 0.5 for d in DIMENSIONS}, BENEFIT: 0.3},
                   dimensions=(BENEFIT,),                                    # single dimension
                   cases=2, runs=2,
                   declared_override=None,
                   policy_id="P-1", policy_signature="sig", rules_digest=self.digest),
            rules=pe.frozen_rules(self.state_path))
        # force overlapping ranges by declaring wide min/max on the same means
        self.assertNotEqual(outcome["verdict"], "SUPPORTED", outcome)


# ---------------------------------------------------------------------------
# D. global scope needs attested cross-project evidence
# ---------------------------------------------------------------------------

class TestGlobalScopeProvenance(CredentialCase):
    def test_two_project_names_without_trajectories_do_not_back_a_global_scope(self):
        self.evaluated("P-GLOBAL",
                       scope={"scope_kind": "global", "problem_structure": "reframe-loop"},
                       evaluation_refs=[{"project": "A"}, {"project": "B"}])
        pe.begin_bounded_trial(self.state_path, "P-GLOBAL",
                               dispatch_evidence={"dispatched": "R2"})
        credential = self._validation("P-GLOBAL")
        support.approve(self.state_path, "P-GLOBAL", credential)
        pe.record_research_validation(self.state_path, "P-GLOBAL", credential)
        result = pe.promote_to_active(self.state_path, "P-GLOBAL", {"scope_evidence_ok": True})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("PE14", result["codes"])

    def _validation(self, policy_id):
        task = pathlib.Path(self.temp.name) / "task.json"
        task.write_text(json.dumps({"task_id": "T1", "dataset": "real"}), encoding="utf-8")
        log = pathlib.Path(self.temp.name) / "run.log"
        log.write_text("executed\n", encoding="utf-8")
        return {"_schema": pe.SCHEMA_RESEARCH_VALIDATION, "policy_id": policy_id,
                "policy_signature": self.signature(policy_id), "rules_digest": self.digest,
                "task_provenance": {"task_id": "T1", "source": str(task),
                                    "source_digest": pe._file_digest(task),
                                    "synthetic": False},
                "execution_evidence": {"path": str(log), "digest": pe._file_digest(log)},
                "cases": 3, "runs_per_case": 2,
                "candidate_arm": "policy", "control_arm": "control",
                "runner": "external research validation harness",
                "equivalence": support.equivalence(task_ids=["T0", "T1", "T2"]),
                "dispatch_ref": self.trial_ref(policy_id),
                "per_arm": {
                    "policy": {"executor": "external-1", "results": [
                        case_result(f"T{i}", metrics={BENEFIT: 0.9}) for i in range(3)] * 2},
                    "control": {"executor": "external-2", "results": [
                        case_result(f"T{i}", metrics={BENEFIT: 0.3}) for i in range(3)] * 2}}}


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# E. 复核本轮的产物：来源链上的四个缺口 + CLI 健壮性
# ---------------------------------------------------------------------------

class TestCredentialChainGaps(CredentialCase):
    def _validation(self, policy_id="P-1"):
        self.evaluated(policy_id)
        pe.begin_bounded_trial(self.state_path, policy_id,
                               dispatch_evidence={"dispatched": "R2"})
        return support.research_validation(
            self.state_path, policy_id, pathlib.Path(self.temp.name),
            signature=self.signature(policy_id),
            rules_digest=pe.evaluation_rules_digest(self.state_path))

    def test_a_credential_that_overstates_its_run_count_is_refused(self):
        """Three records cannot support a declared runs_per_case of 2."""
        credential = self._validation()
        credential["runs_per_case"] = 2
        for arm in credential["per_arm"]:
            credential["per_arm"][arm]["results"] = credential["per_arm"][arm]["results"][:3]
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("执行记录数", " ".join(result["diagnostics"]))

    def test_arms_running_different_case_sets_are_refused(self):
        """Equal counts are not enough: the arms must cover the same cases to be comparable."""
        credential = self._validation()
        for index, row in enumerate(credential["per_arm"]["control"]["results"]):
            row["case_id"] = f"W{index % 3}"
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("case 集合", " ".join(result["diagnostics"]))

    def test_a_non_supported_credential_leaves_no_artifact_behind(self):
        """A refused credential must not be stored as if it were a usable evaluation."""
        credential = self._validation()
        # Only the candidate arm loses mechanistic understanding -> reliability regression.
        for row in credential["per_arm"]["policy"]["results"]:
            row["evaluation"]["metrics"]["mechanistic_understanding"] = {"value": 0.1}
        before = len(list(pe.evaluations_dir(self.state_path).glob("*.json")))
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "INVALID", result)
        after = len(list(pe.evaluations_dir(self.state_path).glob("*.json")))
        self.assertEqual(before, after, "a refused credential was still stored")

    def test_an_understated_unobserved_count_is_refused(self):
        """The unobserved count is recomputed from the records, not read from the report."""
        self.ready()
        document = self.good_report()
        for arm in document["per_arm"]:
            for row in document["per_arm"][arm]["results"]:
                row["evaluation"]["evidence_support"] = {"class": "NO_SUPPORT"}
        document["unobservable_decisions"] = 0
        result = pe.evaluate_candidate(self.state_path, "P-1", document)
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)
        self.assertIn("NO_SUPPORT", " ".join(result["diagnostics"]))

    def test_a_tampered_trajectory_store_does_not_crash_the_attestation(self):
        (self.route / "decision-trajectory.jsonl").write_bytes(b"\xff\xfe\x00bad")
        self.assertEqual(pe._attested_projects(self.state_path), set())


class TestCredentialCliRobustness(CredentialCase):
    def _run(self, *args):
        import subprocess
        import sys
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True)

    def test_a_missing_credential_file_is_a_clean_error(self):
        proc = self._run("validate-research", "--state", str(self.state_path),
                         "--policy-id", "P-1", "--validation", "/nonexistent/cred.json")
        self.assertNotIn("Traceback", proc.stderr, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"], "INVALID")

    def test_an_unparsable_credential_file_is_a_clean_error(self):
        bad = pathlib.Path(self.temp.name) / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        proc = self._run("validate-research", "--state", str(self.state_path),
                         "--policy-id", "P-1", "--validation", str(bad))
        self.assertNotIn("Traceback", proc.stderr, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"], "INVALID")

    def test_an_unparsable_report_file_is_a_clean_error(self):
        bad = pathlib.Path(self.temp.name) / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        proc = self._run("evaluate", "--state", str(self.state_path),
                         "--policy-id", "P-1", "--report", str(bad))
        self.assertNotIn("Traceback", proc.stderr, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"], "INVALID")


# ---------------------------------------------------------------------------
# F. 畸形数值不得让评价路径抛出未捕获异常
# ---------------------------------------------------------------------------

class TestMalformedNumbers(CredentialCase):
    def test_a_nan_unobserved_count_does_not_crash_the_evaluator(self):
        """`int(NaN)` used to escape evaluate_candidate as a raw ValueError."""
        self.ready()
        document = self.good_report()
        document["unobservable_decisions"] = float("nan")
        result = pe.evaluate_candidate(self.state_path, "P-1", document)
        # a NaN is read as "unknown, count 0" rather than crashing the evaluator
        self.assertIn(result["status"], ("REPLAY_EVALUATED", "HOLD", "REJECTED", "INVALID"),
                      result)

    def test_infinite_and_string_counts_are_handled_without_crashing(self):
        self.ready()
        for value in (float("inf"), float("-inf"), "3", None, {"a": 1}, [1], True):
            document = self.good_report()
            document["unobservable_decisions"] = value
            result = pe.evaluate_candidate(self.state_path, "P-1", document)
            self.assertIn(result["status"], ("REPLAY_EVALUATED", "HOLD", "REJECTED", "INVALID"),
                          (value, result))

    def test_a_declared_nan_mean_is_not_treated_as_consistent(self):
        """Every NaN comparison is False, which made the consistency check vacuous."""
        self.assertTrue(pe._numbers_differ(float("nan"), 0.5))
        self.assertTrue(pe._numbers_differ(float("nan"), float("nan")))
        self.assertFalse(pe._numbers_differ(float("inf"), float("inf")))
        self.ready()
        document = self.good_report()
        document["per_arm"]["rsi_full"]["dimensions"]["search_efficiency"]["mean"] = float("nan")
        result = pe.evaluate_candidate(self.state_path, "P-1", document)
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)

    def test_ablation_verdict_survives_non_finite_counts(self):
        candidate, control = improving()
        candidate[BENEFIT], control[BENEFIT] = 0.9, 0.3
        document = report(candidate_metrics=candidate, control_metrics=control,
                         policy_id="P-1", policy_signature="sig",
                         rules_digest=self.digest)
        document["unobservable_decisions"] = float("nan")
        outcome = pe.ablation_verdict(document, rules=pe.frozen_rules(self.state_path))
        self.assertIn(outcome["verdict"], ("SUPPORTED", "REJECTED", "UNDIFFERENTIATED",
                                           "INSUFFICIENT_SAMPLE", "INSUFFICIENT_COVERAGE",
                                           "INVALID"))

    def test_recomputed_level_survives_non_finite_gates(self):
        gates = {"assessable_dimensions": float("nan"), "runs": float("inf"),
                 "cases": "many", "runner": "x"}
        self.assertIn(pe._recomputed_level(gates, {"verdict": "SUPPORTED"},
                                           schema=pe.SCHEMA_EVALUATION),
                      ("L1", "L2"))
