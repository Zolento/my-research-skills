#!/usr/bin/env python3
"""test_promotion_integrity.py — Skill-RSI 第六轮：晋升证据可信性与评价正确性。

这些测试针对的是 **旧版会通过** 的伪造路径，因此在本轮修复前应当失败：

P0-A  Policy Promotion 绕过
  * 调用方自述的全 True JSON 布尔不得完成 REPLAY_EVALUATED / VALIDATED / ACTIVE
  * 晋升必须验证有来源、有完整性摘要、绑定策略版本与冻结评价规则、且有执行记录的评价产物
  * 必须核验目标所需的证据等级，而不是只检查字段是否存在
  * 伪造全部布尔、伪造 Replay Report、缺失评价记录、错误候选绑定、评价结果替换、
    评价规则篡改、绕过受控晋升入口 —— 全部必须被拒绝

P0-B  Replay 收益方向
  * 严格区分 DIFFERENT 与 BETTER；只有预先定义的收益维度取得正向改善、且科学可靠性未退化，
    才允许进入支持晋升的评价结果
  * 必须判断方向、覆盖率、未观测结果、不确定性、样本充分性

P1-A  PT9 每一项独立评价引用都要有来源支持（不是 any()）

P1-B  冻结评价规则的内容必须与 digest 一致；评价必须读取候选绑定的规则版本；
      生命周期转换必须原子，两个并发晋升不得产生多个有效 ACTIVE

P2    非法 ASCII / 截断 / 不可读的 `.head` 必须转为可预期错误，不得泄漏 traceback
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest

import cognition as cg
import decision_trajectory as dt
import policy_evolution as pe
import rsi_test_support as support
import policy_transfer as pt
import research_replay as rr

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "policy_evolution.py"

DIMENSIONS = rr.METRIC_DIMENSIONS

#: 预注册的「收益维度」与「科学可靠性维度」（修复后由 policy_evolution 冻结定义）。
BENEFIT = ("search_efficiency", "stagnation_recovery", "memory_accumulation")
RELIABILITY = ("prediction_quality", "intervention_quality", "scientific_novelty")


def fixture_state(version=3):
    return {"_schema": "research-idea-pipeline/research-state@1", "state_version": version,
            "contract": {"goal": "g", "primary_anchor": "A0", "constraints": [], "resources": {},
                         "out_of_scope": []},
            "claims": [], "evidence": [], "assumptions": [],
            "hypotheses": [{"id": "H1", "statement": "h", "status": "active",
                            "validity": "valid", "island": "P1", "operator": "reframe"}],
            "experiments": [], "literature": [], "failures": [],
            "uncertainties": [{"id": "U1", "question": "q", "importance": "high",
                               "uncertainty": "high", "status": "open", "validity": "valid"}],
            "assurance": [], "repairs": [], "narrative_view": {}, "reviews": [],
            "decision": {"verdict": "continue", "rationale": "", "next_phase": "R3"}}


def report(*, candidate=None, control=None, cases=5, runs=2, results=True,
           unobservable=0, schema="research-idea-pipeline/replay-ablation@1",
           runner="offline CIE runner (no model calls)", arms=("rsi_full", "full_cie")):
    """A realistic ablation report whose declared summary matches its execution record."""
    candidate = dict(candidate or {d: 0.9 for d in DIMENSIONS})
    control = dict(control or {d: 0.3 for d in DIMENSIONS})

    def block(means):
        rows = []
        if results:
            for run in range(runs):
                for index in range(cases):
                    rows.append({
                        "case_id": f"C{index}", "run": run,
                        "leak_checked": True, "isolation_verified": True,
                        "evaluation": {"metrics": {d: {"value": means.get(d, 0.5)}
                                                   for d in DIMENSIONS},
                                       "evidence_support": {"class": "OBSERVED"}}})
        dims = {}
        for d in DIMENSIONS:
            values = [row["evaluation"]["metrics"][d]["value"] for row in rows]
            dims[d] = {"mean": round(sum(values) / len(values), 4) if values else None,
                       "min": min(values) if values else None,
                       "max": max(values) if values else None}
        return {"dimensions": dims, "results": rows,
                "evidence_support": {"OBSERVED": len(rows)} if rows else {}}

    return {"schema": schema, "cases": cases, "runs_per_case": runs,
            "sample_size": cases * runs, "sufficient_sample": True,
            "unobservable_decisions": unobservable, "delta_vs_baseline": {},
            "per_arm": {arms[0]: block(candidate), arms[1]: block(control)},
            "runner": runner}


class PromotionCase(unittest.TestCase):
    """A valid candidate that has reached SHADOW."""

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

    def propose(self, policy_id="P-1", **overrides):
        payload = self.candidate(policy_id, **overrides)
        payload["evaluation_rules_digest"] = self.digest
        return pe.propose(self.state_path, payload, trajectory_support={"DT-1"})

    def to_shadow(self, policy_id="P-1"):
        # The OLD convention (and still valid afterwards): L1 booleans for SHADOW.
        return pe.transition(self.state_path, policy_id, "SHADOW", level="L1",
                             evidence={"format_ok": True, "invariants_ok": True,
                                       "permissions_ok": True})

    # --- old-convention helpers: these encode exactly the bypass under test ---------
    def old_bounded_trial(self, policy_id="P-1"):
        return pe.transition(self.state_path, policy_id, "BOUNDED_TRIAL", level="L2",
                             evidence={"budget_expanded": False,
                                       "hard_gates_unchanged": True,
                                       "dispatch_evidence": True})

    def old_validated(self, policy_id="P-1"):
        return pe.transition(self.state_path, policy_id, "VALIDATED", level="L3",
                             evidence={"independent": True, "distinguishable": True,
                                       "degraded_dimensions": []})

    def ready(self, policy_id="P-1", **overrides):
        self.assertEqual(self.propose(policy_id, **overrides)["status"], "PROPOSED")
        self.assertEqual(self.to_shadow(policy_id)["status"], "SHADOW")
        return policy_id

    def stored_report(self, policy_id="P-1", **kwargs):
        return pe.evaluate_candidate(self.state_path, policy_id, report(**kwargs))

    def record_l3(self, policy_id="P-1", **overrides):
        """Record a valid L3 research-validation credential (the only route to L3)."""
        records, _ = pe.load_records(self.state_path)
        signature = pe.policy_record(records, policy_id)["signature"]
        credential = support.research_validation(
            self.state_path, policy_id, pathlib.Path(self.temp.name),
            signature=signature, rules_digest=pe.evaluation_rules_digest(self.state_path),
            **overrides)
        result = pe.record_research_validation(self.state_path, policy_id, credential)
        assert result["status"] == "VALIDATED", result
        return result


# ---------------------------------------------------------------------------
# P0-A: promotion bypass
# ---------------------------------------------------------------------------

class TestNoBooleanPromotion(PromotionCase):
    """Caller-asserted booleans must never complete a gated promotion."""

    def test_all_true_booleans_cannot_reach_replay_evaluated(self):
        self.ready()
        result = pe.transition(self.state_path, "P-1", "REPLAY_EVALUATED", level="L2",
                               evidence={"replay_verdict": "SUPPORTED",
                                         "leakage_checked": True, "reproducible": True,
                                         "independent": True, "sample_adequate": True,
                                         "distinguishable": True, "degraded_dimensions": []})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertFalse(result["written"])

    def test_all_true_booleans_cannot_reach_validated_or_active(self):
        """Even after a legitimate replay evaluation, L3 steps need a real L3 artifact."""
        self.ready()
        self.stored_report()
        for target in ("VALIDATED", "ACTIVE"):
            result = pe.transition(self.state_path, "P-1", target, level="L3",
                                   evidence={"independent": True, "distinguishable": True,
                                             "degraded_dimensions": [],
                                             "rules_digest_unchanged": True,
                                             "scope_evidence_ok": True,
                                             "sample_adequate": True,
                                             "leakage_checked": True,
                                             "reproducible": True,
                                             "replay_verdict": "SUPPORTED"})
            self.assertEqual(result["status"], "INVALID", (target, result))

    def test_the_cli_cannot_forge_a_promotion(self):
        self.ready()
        self.stored_report()
        payload = json.dumps({"independent": True, "distinguishable": True,
                              "degraded_dimensions": [], "rules_digest_unchanged": True,
                              "scope_evidence_ok": True, "sample_adequate": True,
                              "replay_verdict": "SUPPORTED", "leakage_checked": True,
                              "reproducible": True})
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "transition", "--state", str(self.state_path),
             "--policy-id", "P-1", "--to", "ACTIVE", "--level", "L3", "--reason", payload],
            capture_output=True, text=True)
        self.assertEqual(json.loads(proc.stdout)["status"], "INVALID", proc.stdout)

    def test_the_whole_ladder_cannot_climb_on_booleans_alone(self):
        """OLD behaviour: every gated step accepted hand-written booleans end to end."""
        self.ready()
        steps = [
            ("REPLAY_EVALUATED", {"replay_verdict": "SUPPORTED", "leakage_checked": True,
                                  "reproducible": True, "independent": True,
                                  "sample_adequate": True, "distinguishable": True,
                                  "degraded_dimensions": []}),
            ("BOUNDED_TRIAL", {"budget_expanded": False, "hard_gates_unchanged": True,
                               "dispatch_evidence": True, "independent": True,
                               "leakage_checked": True, "reproducible": True,
                               "sample_adequate": True, "distinguishable": True,
                               "degraded_dimensions": []}),
            ("VALIDATED", {"independent": True, "distinguishable": True,
                           "degraded_dimensions": []}),
            ("ACTIVE", {"independent": True, "distinguishable": True,
                        "degraded_dimensions": [], "rules_digest_unchanged": True,
                        "scope_evidence_ok": True}),
        ]
        for target, evidence in steps:
            result = pe.transition(self.state_path, "P-1", target, level="L3",
                                   evidence=evidence)
            self.assertEqual(result["status"], "INVALID", (target, result))
        records, _ = pe.load_records(self.state_path)
        self.assertNotIn("ACTIVE", pe.latest_status(records).values())

    def test_a_missing_evaluation_record_blocks_validated(self):
        self.ready()
        result = pe.transition(self.state_path, "P-1", "REPLAY_EVALUATED", level="L2",
                               evidence={"replay_verdict": "SUPPORTED"})
        self.assertEqual(result["status"], "INVALID")
        # even after a real evaluation, a hand-written transition still cannot validate
        self.stored_report()
        forged = pe.transition(self.state_path, "P-1", "VALIDATED", level="L3",
                               evidence={"independent": True, "distinguishable": True,
                                         "degraded_dimensions": []})
        self.assertEqual(forged["status"], "INVALID", forged)

    def test_a_fabricated_report_is_not_an_execution_record(self):
        """A report with no per-case results is not a trusted execution record."""
        self.ready()
        result = pe.evaluate_candidate(self.state_path, "P-1", report(results=False))
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)

    def test_a_report_without_the_ablation_schema_is_refused(self):
        self.ready()
        result = pe.evaluate_candidate(self.state_path, "P-1", report(schema="nonsense"))
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)

    def test_a_report_with_no_control_arm_is_refused(self):
        self.ready()
        broken = report()
        broken["per_arm"].pop("full_cie")
        result = pe.evaluate_candidate(self.state_path, "P-1", broken)
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)


class TestEvaluationArtifactBinding(PromotionCase):
    """The promotion must be bound to a stored, digest-checked evaluation artifact."""

    def test_the_artifact_is_bound_to_policy_and_rules(self):
        self.ready()
        result = self.stored_report()
        self.assertEqual(result["status"], "REPLAY_EVALUATED", result)
        records, _ = pe.load_records(self.state_path)
        artifact = pe.latest_evaluation_artifact(self.state_path, "P-1", records)
        self.assertIsNotNone(artifact, "no evaluation artifact was stored")
        self.assertEqual(artifact["policy_id"], "P-1")
        self.assertEqual(artifact["rules_digest"], self.digest)
        self.assertTrue(artifact["digest"])
        self.assertTrue(artifact["produced_by"])
        self.assertTrue(artifact["report_digest"])

    def _artifact(self, policy_id="P-1"):
        records, _ = pe.load_records(self.state_path)
        artifact = pe.latest_evaluation_artifact(self.state_path, policy_id, records)
        self.assertIsNotNone(artifact, "no evaluation artifact was stored")
        return artifact

    def _gate(self, ref, target="REPLAY_EVALUATED", policy_id="P-1"):
        """Run the artifact verification layer directly (that is the layer under test)."""
        records, _ = pe.load_records(self.state_path)
        candidate = pe.policy_record(records, policy_id)
        key = "trial_ref" if target == "BOUNDED_TRIAL" else "evaluation_ref"
        return [item.render() for item in pe._artifact_gate_errors(
            self.state_path, records, candidate, target, {key: ref})]

    def test_an_artifact_outside_the_policy_store_is_refused(self):
        self.ready()
        self.stored_report()
        outside = pathlib.Path(self.temp.name) / "forged.json"
        outside.write_text(json.dumps({"policy_id": "P-1"}), encoding="utf-8")
        diagnostics = self._gate({"path": str(outside), "digest": "sha256:x"})
        self.assertTrue(diagnostics, "an outside artifact was accepted")
        self.assertIn("策略存储目录", " ".join(diagnostics))

    def test_a_symlinked_artifact_escape_is_refused(self):
        """A symlink inside the store that resolves outside must not be accepted."""
        self.ready()
        self.stored_report()
        outside = pathlib.Path(self.temp.name) / "outside.json"
        outside.write_text(json.dumps({"policy_id": "P-1"}), encoding="utf-8")
        link = pe.evaluations_dir(self.state_path) / "evil.json"
        os.symlink(outside, link)
        diagnostics = self._gate({"path": str(link), "digest": "sha256:x"})
        self.assertTrue(diagnostics, "a symlinked escape was accepted")
        self.assertIn("策略存储目录", " ".join(diagnostics))

    def test_an_artifact_for_another_policy_is_refused(self):
        self.ready("P-1")
        self.stored_report("P-1")
        self.ready("P-2")
        self.stored_report("P-2")
        stolen = self._artifact("P-1")
        diagnostics = self._gate(stolen["ref"], policy_id="P-2")
        self.assertTrue(diagnostics, "another policy's artifact was accepted")
        self.assertIn("另一个策略", " ".join(diagnostics))

    def test_a_replaced_evaluation_result_is_detected(self):
        self.ready()
        self.stored_report()
        artifact = self._artifact()
        path = pathlib.Path(artifact["ref"]["path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        # A REAL change: the digest must no longer describe the body.
        payload["verdict"]["sample_adequate"] = False
        payload["gates"]["assessable_dimensions"] = 0
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        diagnostics = self._gate(artifact["ref"])
        self.assertTrue(diagnostics, "a replaced result was accepted")
        self.assertIn("完整性摘要", " ".join(diagnostics))

    def test_evaluation_rules_tampering_invalidates_the_artifact(self):
        self.ready()
        self.stored_report()
        artifact = self._artifact()
        document = json.loads(pe.rules_path(self.state_path).read_text(encoding="utf-8"))
        document["rules"]["delta_tolerance"] = 0.99
        document["digest"] = cg.digest_of(document["rules"])
        pe.rules_path(self.state_path).write_text(json.dumps(document), encoding="utf-8")
        diagnostics = self._gate(artifact["ref"])
        self.assertTrue(diagnostics, "a rules mismatch was accepted")
        self.assertIn("评价规则", " ".join(diagnostics))

    def test_an_artifact_whose_level_exceeds_its_evidence_is_refused(self):
        """The stored level is recomputed; an inflated level must not be believed."""
        self.ready()
        self.stored_report()
        artifact = self._artifact()
        path = pathlib.Path(artifact["ref"]["path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["level"] = "L3"
        payload["gates"]["runner"] = None          # no executor -> not L2 either
        body = {k: v for k, v in payload.items() if k != "digest"}
        payload["digest"] = cg.digest_of(body)     # keep the digest self-consistent
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        diagnostics = self._gate({"path": str(path), "digest": payload["digest"]})
        self.assertTrue(diagnostics, "an inflated level was accepted")
        self.assertIn("等级", " ".join(diagnostics))

    def test_a_trial_artifact_cannot_stand_in_for_a_replay_evaluation(self):
        self.ready()
        self.stored_report()
        pe.begin_bounded_trial(self.state_path, "P-1", dispatch_evidence={"dispatched": "R2"})
        # Place the dispatch record where an evaluation artifact is expected: the credential
        # class, not merely the location, is what must refuse it.
        trial = pathlib.Path(support.trial_ref(self.state_path, "P-1")["path"])
        relocated = pe.evaluations_dir(self.state_path) / "disguised-trial.json"
        relocated.write_bytes(trial.read_bytes())
        payload = json.loads(relocated.read_text(encoding="utf-8"))
        diagnostics = self._gate({"path": str(relocated), "digest": payload["digest"]},
                                 target="REPLAY_EVALUATED")
        self.assertTrue(diagnostics, "a dispatch record was accepted as an evaluation")
        self.assertIn("凭证", " ".join(diagnostics))

    def test_the_full_controlled_lifecycle_still_reaches_active(self):
        self.ready()
        self.assertEqual(self.stored_report()["status"], "REPLAY_EVALUATED")
        trial = pe.begin_bounded_trial(self.state_path, "P-1",
                                       dispatch_evidence={"dispatched": "R2"})
        self.assertEqual(trial["status"], "BOUNDED_TRIAL", trial)
        validated = self.record_l3("P-1")
        self.assertEqual(validated["status"], "VALIDATED", validated)
        active = pe.promote_to_active(self.state_path, "P-1", {"scope_evidence_ok": True})
        self.assertEqual(active["status"], "ACTIVE", active)


# ---------------------------------------------------------------------------
# P0-B: benefit direction
# ---------------------------------------------------------------------------

class TestBenefitDirection(unittest.TestCase):
    def verdict(self, **kwargs):
        return pe.ablation_verdict(report(**kwargs))

    def test_better_is_distinguished_from_merely_different(self):
        comparison = pe.distinguishable(report(), "rsi_full", "full_cie")
        block = comparison["dimensions"]["search_efficiency"]
        self.assertEqual(block.get("direction"), "BETTER", block)

    def test_only_efficiency_degradation_is_not_supported(self):
        candidate = {d: 0.5 for d in DIMENSIONS}
        control = {d: 0.5 for d in DIMENSIONS}
        candidate["search_efficiency"] = 0.1
        control["search_efficiency"] = 0.9
        outcome = self.verdict(candidate=candidate, control=control)
        self.assertNotEqual(outcome["verdict"], "SUPPORTED", outcome)
        self.assertIn(outcome["verdict"], ("REJECTED", "UNDIFFERENTIATED"))

    def test_only_a_non_critical_dimension_improves_is_not_supported(self):
        candidate = {d: 0.5 for d in DIMENSIONS}
        control = {d: 0.5 for d in DIMENSIONS}
        candidate["mechanistic_understanding"] = 0.9   # not a benefit dimension
        control["mechanistic_understanding"] = 0.3
        outcome = self.verdict(candidate=candidate, control=control)
        self.assertNotEqual(outcome["verdict"], "SUPPORTED", outcome)

    def test_no_positive_dimension_is_undifferentiated(self):
        flat = {d: 0.5 for d in DIMENSIONS}
        outcome = self.verdict(candidate=flat, control=dict(flat))
        self.assertEqual(outcome["verdict"], "UNDIFFERENTIATED", outcome)

    def test_a_reliability_regression_outweighs_an_efficiency_gain(self):
        candidate = {d: 0.5 for d in DIMENSIONS}
        control = {d: 0.5 for d in DIMENSIONS}
        candidate["search_efficiency"] = 0.95        # big benefit
        control["search_efficiency"] = 0.30
        candidate["prediction_quality"] = 0.10       # science regresses
        control["prediction_quality"] = 0.90
        outcome = self.verdict(candidate=candidate, control=control)
        self.assertEqual(outcome["verdict"], "REJECTED", outcome)

    def test_an_insufficient_sample_is_never_supported(self):
        outcome = self.verdict(cases=2, runs=1)
        self.assertEqual(outcome["verdict"], "INSUFFICIENT_SAMPLE", outcome)

    def test_a_fabricated_report_is_invalid(self):
        self.assertEqual(pe.ablation_verdict({})["verdict"], "INVALID")
        self.assertEqual(pe.ablation_verdict({"per_arm": {}})["verdict"], "INVALID")

    def test_unobserved_decisions_block_support(self):
        outcome = self.verdict(unobservable=3)
        self.assertNotEqual(outcome["verdict"], "SUPPORTED", outcome)

    def test_a_real_benefit_with_intact_reliability_is_supported(self):
        candidate = {d: 0.5 for d in DIMENSIONS}
        control = {d: 0.5 for d in DIMENSIONS}
        candidate["search_efficiency"] = 0.9
        control["search_efficiency"] = 0.3
        outcome = self.verdict(candidate=candidate, control=control)
        self.assertEqual(outcome["verdict"], "SUPPORTED", outcome)
        self.assertTrue(outcome["benefit_dimensions"])


# ---------------------------------------------------------------------------
# P1-A: PT9 every reference must be sourced
# ---------------------------------------------------------------------------

class TestPT9PerReference(unittest.TestCase):
    def state(self):
        return {"state_version": 3, "contract": {"goal": "g", "primary_anchor": "phenomenon"},
                "hypotheses": [{"id": "H1", "statement": "m", "status": "active",
                                "operator": "reframe", "island": "P1",
                                "validity": {"status": "valid"}}],
                "uncertainties": [], "claims": [], "evidence": [], "assumptions": [],
                "experiments": [], "literature": [], "failures": [], "assurance": [],
                "repairs": []}

    def attested(self, *projects):
        records = []
        for project in projects:
            ident = f"DT-{project.lower()}"
            records.append({"_schema": "research-idea-pipeline/decision-trajectory@1",
                            "record": "decision", "trajectory_id": ident, "project": project,
                            "route": project,
                            "context": {"state_version": 3, "state_digest": "sha256:x",
                                        "scientific_question": "q",
                                        "decided_at": "2026-01-01T00:00:00Z"},
                            "decision": {"chosen": "X1", "dispatch_status": "dispatched",
                                         "candidates": []},
                            "recorded_at": "2026-01-01T00:00:00Z"})
            records.append({"_schema": "research-idea-pipeline/decision-trajectory@1",
                            "record": "outcome", "trajectory_id": ident, "project": project,
                            "evidence_qualification": "qualified",
                            "result": {"kind": "experiment_result",
                                       "summary": "observed x=0.42"},
                            "observed_at": "2026-01-02T00:00:00Z", "at_state_version": 3,
                            "scientific_delta": "none", "decision_delta": "none",
                            "policy_delta": "none"})
        return records

    def policy(self, refs):
        return {"policy_id": "P", "scope": {"kind": "global", "structures": ["reframe"]},
                "applicable_conditions": [],
                "required_tools": [], "validation_protocol": {},
                "evidence_level": "independent",
                "independent_evaluation_refs": refs,
                "supporting_trajectory_ids": [],
                "counterexamples": []}

    def test_every_reference_must_be_backed_not_just_one(self):
        state = self.state()
        decision = pt.transfer_decision(self.policy(["DT-a", "DT-ghost"]), state,
                                        source_state=state,
                                        source_trajectories=self.attested("A", "B"))
        self.assertEqual(decision["status"], "BLOCK", decision)
        self.assertIn("PT9", decision["codes"])

    def test_project_names_are_not_independent_evaluation_evidence(self):
        state = self.state()
        policy = self.policy([])
        policy["evidence_projects"] = ["A", "B"]
        decision = pt.transfer_decision(policy, state, source_state=state)
        self.assertEqual(decision["status"], "BLOCK", decision)
        self.assertIn("PT9", decision["codes"])


# ---------------------------------------------------------------------------
# P1-B: frozen rules integrity and atomic transitions
# ---------------------------------------------------------------------------

class TestFrozenRulesIntegrity(PromotionCase):
    def test_a_stale_digest_field_cannot_mask_edited_rules(self):
        document = json.loads(pe.rules_path(self.state_path).read_text(encoding="utf-8"))
        document["rules"]["delta_tolerance"] = 0.99          # content changed
        pe.rules_path(self.state_path).write_text(json.dumps(document), encoding="utf-8")
        # the digest field still says the old value; the reader must recompute
        self.assertNotEqual(pe.evaluation_rules_digest(self.state_path), self.digest)

    def test_evaluation_refuses_a_candidate_bound_to_other_rules(self):
        self.assertEqual(self.propose("P-1")["status"], "PROPOSED")
        self.assertEqual(self.to_shadow("P-1")["status"], "SHADOW")
        # replace the frozen rules after the candidate was generated
        path = pe.rules_path(self.state_path)
        document = json.loads(path.read_text(encoding="utf-8"))
        document["rules"]["delta_tolerance"] = 0.4242
        document["digest"] = cg.digest_of(document["rules"])
        path.write_text(json.dumps(document), encoding="utf-8")
        result = pe.evaluate_candidate(self.state_path, "P-1", report())
        self.assertNotEqual(result["status"], "REPLAY_EVALUATED", result)

    def test_concurrent_promotions_yield_one_active_policy(self):
        self.ready("P-1")
        self.stored_report("P-1")
        pe.begin_bounded_trial(self.state_path, "P-1", dispatch_evidence={"dispatched": "R2"})
        self.record_l3("P-1")
        outcomes = []
        barrier = threading.Barrier(4)

        def promote():
            barrier.wait()
            outcomes.append(pe.promote_to_active(self.state_path, "P-1",
                                                 {"scope_evidence_ok": True})["status"])

        threads = [threading.Thread(target=promote) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        records, _ = pe.load_records(self.state_path)
        statuses = pe.latest_status(records)
        active = [ident for ident, status in statuses.items() if status == "ACTIVE"]
        actives_appended = [item for item in records
                            if item.get("record") == "transition" and item.get("to") == "ACTIVE"]
        self.assertEqual(len(active), 1, (statuses, outcomes))
        self.assertEqual(len(actives_appended), 1, "a promotion was applied twice")


# ---------------------------------------------------------------------------
# P2: damaged head file
# ---------------------------------------------------------------------------

class TestDamagedHead(unittest.TestCase):
    def _store(self, temp):
        path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
        dt.append_chained(path, {"_schema": "research-idea-pipeline/decision-trajectory@1",
                                 "record": "candidate", "policy_id": "P"})
        return path

    def test_a_head_with_invalid_ascii_is_a_trajectory_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self._store(temp)
            dt.head_path(path).write_bytes(b"\xff\xfe\x00not-ascii")
            with self.assertRaises(dt.TrajectoryError):
                dt.load_records(path)

    def test_a_truncated_head_is_a_trajectory_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self._store(temp)
            dt.head_path(path).write_text("sha256:dead", encoding="ascii")
            with self.assertRaises(dt.TrajectoryError):
                dt.load_records(path)

    def test_a_tolerant_read_reports_the_head_problem(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self._store(temp)
            dt.head_path(path).write_bytes(b"\xff\xfe\x00")
            _, diagnostics = dt.load_records(path, tolerant=True)
            self.assertTrue(any(item.rule == "DT0" for item in diagnostics), diagnostics)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Second-pass review of round six: two defects found in the new code itself
# ---------------------------------------------------------------------------

class TestSecondPassReview(PromotionCase):
    def _promote(self, policy_id):
        self.ready(policy_id)
        self.stored_report(policy_id)
        pe.begin_bounded_trial(self.state_path, policy_id,
                               dispatch_evidence={"dispatched": "R2"})
        self.record_l3(policy_id)
        self.assertEqual(pe.promote_to_active(self.state_path, policy_id,
                                              {"scope_evidence_ok": True})["status"],
                         "ACTIVE")

    def test_a_restored_policy_keeps_its_evidence_level(self):
        """Restoring an L3-backed policy must not relabel it L1."""
        self._promote("P-1")
        self._promote("P-2")
        self.assertEqual(pe.rollback(self.state_path, "P-2", to_policy_id="P-1",
                                     reason="regression")["status"], "ROLLED_BACK")
        records, _ = pe.load_records(self.state_path)
        restores = [item for item in records
                    if item.get("record") == "transition" and item.get("policy_id") == "P-1"
                    and item.get("from") == "SUPERSEDED" and item.get("to") == "ACTIVE"]
        self.assertEqual(len(restores), 1, records)
        self.assertEqual(restores[0]["level"], "L3", restores[0])

    def test_a_bounded_trial_records_a_dispatch_not_an_evaluation_verdict(self):
        """A trial artifact must not claim an evaluation result it never produced."""
        self.ready("P-1")
        self.stored_report("P-1")
        self.assertEqual(pe.begin_bounded_trial(
            self.state_path, "P-1", dispatch_evidence={"dispatched": "R2"})["status"],
            "BOUNDED_TRIAL")
        artifacts = list(pe.trials_dir(self.state_path).glob("*.json"))
        self.assertEqual(len(artifacts), 1, artifacts)
        payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["_schema"], pe.SCHEMA_TRIAL)
        self.assertNotEqual(payload["verdict"]["verdict"], "SUPPORTED")
        self.assertTrue(payload["gates"]["dispatch_record"])
        self.assertFalse(payload["gates"]["budget_expanded"])
        self.assertEqual(payload["level"], "L2")

    def test_a_trial_artifact_cannot_stand_in_for_an_evaluation(self):
        """Pointing VALIDATED at a trial artifact must not satisfy the L3 requirement."""
        self.ready("P-1")
        self.stored_report("P-1")
        pe.begin_bounded_trial(self.state_path, "P-1", dispatch_evidence={"dispatched": "R2"})
        trial = json.loads(next(pe.trials_dir(self.state_path).glob("*.json"))
                           .read_text(encoding="utf-8"))
        ref = {"path": str(next(pe.trials_dir(self.state_path).glob("*.json"))),
               "digest": trial["digest"]}
        result = pe.validate_candidate(self.state_path, "P-1", evaluation_ref=ref)
        self.assertEqual(result["status"], "INVALID", result)
