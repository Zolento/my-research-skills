#!/usr/bin/env python3
"""test_rsi_round11.py — 第十一轮：配对完整性、派遣归属、L2/L3 指标一致性、run_id 类型安全。

四项问题都在 `293c7ff` 上复现过（见 `.dev/round11/record.md`）：

P1-A 两臂各自内部自洽，但跨臂 `(case_id, pairing_key)` 不一致仍被判合格 → 不成对数据进入配对统计
P1-B 普通 Scheduler 派遣（无策略身份）被当作某候选策略的派遣凭证
P2-A L3 凭证的非法指标值只在重算层被过滤，L2 拒绝而 L3 接受 → 审计标准不一致
P2-B 非法 `run_id`（list/dict/bool/混合）在集合运算中抛未捕获 TypeError
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

BENEFIT = "search_efficiency"
SCIENCE = "mechanistic_understanding"


class Round11Case(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.route = pathlib.Path(self.temp.name) / "A"
        self.route.mkdir(parents=True)
        self.workdir = pathlib.Path(self.temp.name) / "work"
        self.state_path = self.route / cg.STATE_NAME
        self.state_path.write_text(json.dumps({
            "_schema": "research-idea-pipeline/research-state@1", "state_version": 3,
            "contract": {"goal": "g", "primary_anchor": "A0", "constraints": [],
                         "resources": {}, "out_of_scope": []},
            "claims": [], "evidence": [], "assumptions": [],
            "hypotheses": [{"id": "H1", "statement": "h", "status": "active",
                            "validity": "valid", "island": "P1", "operator": "reframe"}],
            "experiments": [], "literature": [], "failures": [], "uncertainties": [],
            "assurance": [], "repairs": [], "narrative_view": {}, "reviews": [],
            "decision": {"verdict": "continue", "rationale": "", "next_phase": "R3"}},
            ensure_ascii=False) + "\n", encoding="utf-8")
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

    @staticmethod
    def _set_first_run_id(report, value):
        report["per_arm"]["rsi_full"]["results"][0]["run_id"] = value
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

    def shadow(self, policy_id="P-1"):
        payload = {"policy_id": policy_id, "policy_schema_version": "1",
                   "parent_policy_id": None, "status": "PROPOSED",
                   "scope": {"scope_kind": "local", "problem_structure": "reframe-loop"},
                   "applicable_conditions": [{"kind": "min_open_uncertainties", "value": 1}],
                   "strategy_changes": [{"kind": "same_tier_preference", "prefer_action": "R2"}],
                   "supporting_trajectory_ids": ["DT-1"], "counterexamples": ["c"],
                   "expected_effect": {"mechanism": "m", "direction": "up"},
                   "revalidation_conditions": ["r"], "evaluation_refs": [],
                   "rollback_target": None, "evaluation_rules_digest": self.digest}
        assert pe.propose(self.state_path, payload,
                          trajectory_support={"DT-1"})["status"] == "PROPOSED"
        assert pe.transition(self.state_path, policy_id, "SHADOW",
                             level="L1")["status"] == "SHADOW"

    def evaluated(self, policy_id="P-1"):
        self.shadow(policy_id)
        assert pe.evaluate_candidate(self.state_path, policy_id,
                                     self.report())["status"] == "REPLAY_EVALUATED"
        return policy_id

    def credential(self, policy_id="P-1", **overrides):
        kwargs = {"signature": pe.policy_record(pe.load_records(self.state_path)[0],
                                                policy_id)["signature"],
                  "rules_digest": pe.evaluation_rules_digest(self.state_path)}
        kwargs.update(overrides)
        return support.research_validation(self.state_path, policy_id, self.workdir, **kwargs)

    def l3_ready(self, policy_id="P-1"):
        """A policy at BOUNDED_TRIAL with a corroborated dispatch."""
        self.evaluated(policy_id)
        support.record_dispatch(self.state_path, policy_id=policy_id, action="R2")
        assert support.begin_trial(self.state_path, policy_id)["status"] == "BOUNDED_TRIAL"
        return policy_id


# ---------------------------------------------------------------------------
# P1-A — cross-arm pairing completeness
# ---------------------------------------------------------------------------

class TestCrossArmPairing(Round11Case):
    def test_a_legal_paired_experiment_is_accepted(self):
        """Positive: the ordinary paired replay must not be rejected."""
        self.shadow()
        result = pe.evaluate_candidate(self.state_path, "P-1", self.report())
        self.assertEqual(result["status"], "REPLAY_EVALUATED", result)

    def test_cross_arm_pairing_mismatch_is_refused(self):
        """Each arm is internally consistent, but the arms are not paired."""
        self.shadow()

        def shift_control(report):
            mapping = {"run-1": "run-1", "run-2": "run-9"}
            for row in report["per_arm"]["full_cie"]["results"]:
                row["run_id"] = mapping[row["run_id"]]
            return report

        result = pe.evaluate_candidate(self.state_path, "P-1",
                                       self.report(mutate=shift_control))
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("配对", " ".join(result["diagnostics"]))

    def test_a_missing_pairing_across_arms_is_refused(self):
        """One arm has a run the other does not: the comparison is not paired."""
        self.shadow()

        def drop_one(report):
            report["per_arm"]["full_cie"]["results"] = \
                report["per_arm"]["full_cie"]["results"][:-1]
            return report

        result = pe.evaluate_candidate(self.state_path, "P-1", self.report(mutate=drop_one))
        self.assertEqual(result["status"], "INVALID", result)

    def test_an_explicit_independent_pairing_key_is_honoured(self):
        """Arm-local execution ids plus an explicit pairing_key must be accepted."""
        self.shadow()

        def independent_ids(report):
            for arm, prefix in (("rsi_full", "a"), ("full_cie", "b")):
                for index, row in enumerate(report["per_arm"][arm]["results"]):
                    row["run_id"] = f"{prefix}-{index}"
                    row["pairing_key"] = f"pair-{index % 2 + 1}"
            return report

        result = pe.evaluate_candidate(self.state_path, "P-1",
                                       self.report(mutate=independent_ids))
        self.assertEqual(result["status"], "REPLAY_EVALUATED", result)

    def test_a_mismatched_pairing_key_is_refused(self):
        """Different pairing keys across arms means the arms are not paired."""
        self.shadow()

        def mismatched(report):
            for index, row in enumerate(report["per_arm"]["full_cie"]["results"]):
                row["pairing_key"] = f"other-{index}"
            for index, row in enumerate(report["per_arm"]["rsi_full"]["results"]):
                row["pairing_key"] = f"pair-{index}"
            return report

        result = pe.evaluate_candidate(self.state_path, "P-1",
                                       self.report(mutate=mismatched))
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("配对", " ".join(result["diagnostics"]))

    def test_an_explicitly_unpaired_design_is_not_promotion_evidence(self):
        """We must not silently switch statistical protocol for a non-paired design."""
        self.shadow()

        def unpaired(report):
            report["design"] = "unpaired"
            return report

        result = pe.evaluate_candidate(self.state_path, "P-1", self.report(mutate=unpaired))
        self.assertEqual(result["status"], "INVALID", result)

    def test_l3_uses_the_same_pairing_rule(self):
        self.l3_ready()
        credential = self.credential()
        for row in credential["per_arm"]["control"]["results"]:
            if row["run_id"] == "run-2":
                row["run_id"] = "run-9"
        support.approve(self.state_path, "P-1", credential)
        result = pe.record_research_validation(self.state_path, "P-1", credential)
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("配对", " ".join(result["diagnostics"]))


# ---------------------------------------------------------------------------
# P1-B — the dispatch must belong to this candidate policy
# ---------------------------------------------------------------------------

class TestDispatchOwnership(Round11Case):
    def test_an_ordinary_scheduler_dispatch_is_not_a_policy_credential(self):
        """A plain scheduler decision (no policy identity) proves nothing about a policy."""
        self.evaluated()
        support.record_dispatch(self.state_path, action="R2", policy_id=None)
        result = pe.begin_bounded_trial(self.state_path, "P-1",
                                        dispatch_evidence={"action": "R2"})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn("策略", " ".join(result["diagnostics"]))

    def test_a_dispatch_without_any_identity_is_refused(self):
        self.evaluated()
        import strategy_memory as sm
        scheduler = json.loads(self.scheduler_path.read_text(encoding="utf-8"))
        updated = sm.record_strategy_decision(scheduler, {
            "state_version": 3, "chosen": "R2", "adopted": True, "strategy_applied": True,
            "decision_changed": False, "dispatch": {"action": "R2"}},
            dispatch_result="dispatched R2")
        self.scheduler_path.write_text(json.dumps(updated), encoding="utf-8")
        result = pe.begin_bounded_trial(self.state_path, "P-1",
                                        dispatch_evidence={"action": "R2"})
        self.assertEqual(result["status"], "INVALID", result)

    def test_a_legitimate_policy_dispatch_is_accepted_and_bound(self):
        self.evaluated()
        support.record_dispatch(self.state_path, policy_id="P-1", action="R2")
        result = support.begin_trial(self.state_path, "P-1")
        self.assertEqual(result["status"], "BOUNDED_TRIAL", result)
        artifact = json.loads(next(pe.trials_dir(self.state_path).glob("*.json"))
                              .read_text(encoding="utf-8"))
        record = artifact["dispatch_record"]
        self.assertEqual(record["policy_id"], "P-1")
        self.assertEqual(record["action"], "R2")
        self.assertEqual(record["state_version"], 3)
        self.assertTrue(record.get("event_id"), "the dispatch event needs a stable identity")

    def test_the_trial_entry_never_writes_an_identity_into_the_scheduler(self):
        """Attribution must be read, never injected at validation time."""
        self.evaluated()
        support.record_dispatch(self.state_path, policy_id="P-1", action="R2")
        before = self.scheduler_path.read_bytes()
        # call the entry directly: the test helper records a dispatch of its own
        result = pe.begin_bounded_trial(self.state_path, "P-1",
                                        dispatch_evidence={"action": "R2"})
        self.assertEqual(result["status"], "BOUNDED_TRIAL", result)
        self.assertEqual(self.scheduler_path.read_bytes(), before,
                         "the trial entry modified the telemetry it relies on")

    def test_an_event_cannot_be_replayed_for_a_second_trial(self):
        self.evaluated()
        support.record_dispatch(self.state_path, policy_id="P-1", action="R2")
        assert support.begin_trial(self.state_path, "P-1")["status"] == "BOUNDED_TRIAL"
        first = json.loads(sorted(pe.trials_dir(self.state_path).glob("*.json"))[0]
                           .read_text(encoding="utf-8"))
        # move back through a second trial cycle without recording a new event
        pe.transition(self.state_path, "P-1", "HOLD", level="L2", evidence={"reason": "retry"})
        pe.evaluate_candidate(self.state_path, "P-1", self.report())
        result = pe.begin_bounded_trial(self.state_path, "P-1",
                                        dispatch_evidence={"action": "R2"})
        self.assertEqual(result["status"], "INVALID", result)
        self.assertTrue(first["dispatch_record"]["event_id"])


# ---------------------------------------------------------------------------
# P2-A — L2/L3 metric validation consistency
# ---------------------------------------------------------------------------

class TestMetricValidityConsistency(Round11Case):
    ILLEGAL = (("string", "0.9"), ("bool", True), ("list", [1, 2]), ("object", {"a": 1}),
               ("nan", float("nan")), ("inf", float("inf")))

    def _poison(self, metrics_owner, dimension=SCIENCE):
        for label, value in self.ILLEGAL:
            metrics_owner(label, value)

    def test_l3_rejects_every_illegal_metric_value(self):
        for label, value in self.ILLEGAL:
            with self.subTest(label=label):
                case = Round11Case("setUp")
                case.setUp()
                try:
                    case.l3_ready()
                    credential = case.credential()
                    for row in credential["per_arm"]["policy"]["results"]:
                        row["evaluation"]["metrics"][SCIENCE] = {"value": value}
                    support.approve(case.state_path, "P-1", credential)
                    result = pe.record_research_validation(case.state_path, "P-1", credential)
                    self.assertEqual(result["status"], "INVALID", (label, result))
                finally:
                    case.tearDown()

    def test_l2_and_l3_agree_on_illegal_metrics(self):
        for label, value in self.ILLEGAL:
            with self.subTest(label=label):
                case = Round11Case("setUp")
                case.setUp()
                try:
                    case.shadow()

                    def poison(report, value=value):
                        for arm in report["per_arm"]:
                            for row in report["per_arm"][arm]["results"]:
                                row["evaluation"]["metrics"][BENEFIT] = {"value": value}
                            case._rebuild(report["per_arm"][arm])
                        return report

                    l2 = pe.evaluate_candidate(case.state_path, "P-1",
                                               case.report(mutate=poison))
                    self.assertEqual(l2["status"], "INVALID", (label, l2))
                finally:
                    case.tearDown()

    def test_a_missing_metric_key_is_a_structural_error(self):
        """Every dimension must be reported; a missing key is not 'unobservable'."""
        self.shadow()

        def drop_key(report):
            for arm in report["per_arm"]:
                for row in report["per_arm"][arm]["results"]:
                    row["evaluation"]["metrics"].pop(SCIENCE, None)
            return report

        result = pe.evaluate_candidate(self.state_path, "P-1", self.report(mutate=drop_key))
        self.assertEqual(result["status"], "INVALID", result)
        self.assertIn(SCIENCE, " ".join(result["diagnostics"]))

    def test_an_unobservable_value_is_legitimate_and_zero_is_a_measurement(self):
        """`None` means unobservable; `0.0` is a real measurement, not a missing value."""
        self.shadow()

        def null_and_zero(report):
            for index, row in enumerate(report["per_arm"]["rsi_full"]["results"]):
                row["evaluation"]["metrics"]["scientific_novelty"] = {"value": None}
                row["evaluation"]["metrics"]["memory_accumulation"] = {"value": 0.0}
            for row in report["per_arm"]["full_cie"]["results"]:
                row["evaluation"]["metrics"]["scientific_novelty"] = {"value": None}
                row["evaluation"]["metrics"]["memory_accumulation"] = {"value": 0.0}
            for arm in report["per_arm"]:
                self._rebuild(report["per_arm"][arm])
            return report

        result = pe.evaluate_candidate(self.state_path, "P-1", self.report(mutate=null_and_zero))
        self.assertNotEqual(result["status"], "INVALID", result)


# ---------------------------------------------------------------------------
# P2-B — run_id type safety
# ---------------------------------------------------------------------------

class TestRunIdTypes(Round11Case):
    @staticmethod
    def _mutate_first(report, value):
        report["per_arm"]["rsi_full"]["results"][0]["run_id"] = value
        return report

    def test_illegal_run_id_types_are_diagnosable_refusals(self):
        for label, value in (("list", ["run-1"]), ("dict", {"a": 1}), ("bool", True),
                             ("float", 1.5), ("empty", "")):
            with self.subTest(label=label):
                case = Round11Case("setUp")
                case.setUp()
                try:
                    case.shadow()
                    work = pe.evaluations_dir(case.state_path)
                    before = sorted(q.name for q in work.glob("*.json")) if work.is_dir() else []
                    result = pe.evaluate_candidate(
                        case.state_path, "P-1",
                        case.report(mutate=lambda r, v=value: Round11Case._set_first_run_id(r, v)))
                    self.assertEqual(result["status"], "INVALID", (label, result))
                    self.assertTrue(result["diagnostics"], label)
                    after = sorted(q.name for q in work.glob("*.json")) if work.is_dir() else []
                    self.assertEqual(before, after, "invalid input persisted an artifact")
                except Exception as exc:                       # noqa: BLE001 - the bug under test
                    self.fail(f"{label}: raised {type(exc).__name__}: {exc}")
                finally:
                    case.tearDown()

    def test_mixed_run_id_types_are_refused_without_raising(self):
        self.shadow()

        def mixed(report):
            rows = report["per_arm"]["rsi_full"]["results"]
            rows[0]["run_id"] = "run-1"
            rows[1]["run_id"] = 2
            return report

        try:
            result = pe.evaluate_candidate(self.state_path, "P-1", self.report(mutate=mixed))
        except Exception as exc:                               # noqa: BLE001 - the bug under test
            self.fail(f"mixed run_id types raised {type(exc).__name__}: {exc}")
        self.assertEqual(result["status"], "INVALID", result)

    def test_valid_string_and_integer_run_ids_are_accepted(self):
        for label, base in (("string", lambda index: f"run-{index + 1}"),
                            ("integer", lambda index: index + 1)):
            with self.subTest(label=label):
                case = Round11Case("setUp")
                case.setUp()
                try:
                    case.shadow()

                    def renumber(report, base=base):
                        cases = report.get("cases") or 3
                        for arm in report["per_arm"]:
                            for position, row in enumerate(report["per_arm"][arm]["results"]):
                                row["run_id"] = base(position // cases)   # paired by run index
                        return report

                    result = pe.evaluate_candidate(case.state_path, "P-1",
                                                   case.report(mutate=renumber))
                    self.assertEqual(result["status"], "REPLAY_EVALUATED", (label, result))
                finally:
                    case.tearDown()

    def test_a_string_and_an_integer_run_id_never_collide(self):
        """Coercing to string would merge `1` and `"1"`; the contract refuses the mix."""
        self.shadow()

        def collide(report):
            rows = report["per_arm"]["rsi_full"]["results"]
            rows[0]["run_id"] = 1
            rows[1]["run_id"] = "1"
            return report

        result = pe.evaluate_candidate(self.state_path, "P-1", self.report(mutate=collide))
        self.assertEqual(result["status"], "INVALID", result)


if __name__ == "__main__":
    unittest.main()
