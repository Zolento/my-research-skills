#!/usr/bin/env python3
"""test_strategy_memory.py — Phase 3: scientific value and adaptive discovery.

The failure modes under test are the ones the specification names explicitly: a
subjective total score, an anchor quietly rewritten by learning, an operator banned
forever after a few failures, exploration rounds added for their own sake, and a
cross-domain analogy contaminated by another island's answer.
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import cognition as cg
import state_check as sc
import strategy_memory as sm

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "strategy_memory.py"


def clone(value):
    return json.loads(json.dumps(value))


def quiet(callable_, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()) as sink:
        result = callable_(*args, **kwargs)
    return result, sink.getvalue()


class Base(unittest.TestCase):

    def setUp(self):
        self.state, self.revisions, self.scheduler = sm._fixture()
        self.index, _ = cg.full_index(self.state, self.revisions, "A")

    def quiet_scheduler(self):
        return {"state_version": 4, "next_actions": [],
                "eig_calibration": {"records": []},
                "operator_stats": {"by_operator": {}}}


# ---------------------------------------------------------------------------
# 3.1 Value model
# ---------------------------------------------------------------------------

class TestValueModel(Base):

    def test_the_two_judgements_are_independent_groups(self):
        assessment = sm.value_assessment(self.state, self.index, "H1", self.scheduler)
        self.assertEqual(set(assessment["decision_value"]), set(sm.VALUE_DIMENSIONS))
        self.assertEqual(set(assessment["discovery_potential"]), set(sm.POTENTIAL_DIMENSIONS))

    def test_a_valid_assessment_has_no_violations(self):
        assessment = sm.value_assessment(self.state, self.index, "H1", self.scheduler)
        self.assertEqual(sm.validate_value(assessment), [])

    def test_no_aggregate_score_is_produced(self):
        assessment = sm.value_assessment(self.state, self.index, "H1", self.scheduler)
        for key in sm.BANNED_AGGREGATE_KEYS:
            self.assertNotIn(key, assessment)

    def test_an_aggregate_is_rejected(self):
        assessment = sm.value_assessment(self.state, self.index, "H1", self.scheduler)
        for key in ("score", "overall", "composite"):
            broken = dict(assessment)
            broken[key] = 0.9
            self.assertIn("SV1", {d.rule for d in sm.validate_value(broken)}, msg=key)

    def test_every_dimension_cites_a_source(self):
        assessment = sm.value_assessment(self.state, self.index, "H1", self.scheduler)
        for group in ("decision_value", "discovery_potential"):
            for dimension, entry in assessment[group].items():
                self.assertTrue(entry["basis"], msg=f"{group}.{dimension}")
                self.assertIn(entry["assessment"], sm.ASSESSMENTS)

    def test_a_dimension_without_a_source_is_rejected(self):
        assessment = sm.value_assessment(self.state, self.index, "H1", self.scheduler)
        broken = clone(assessment)
        broken["discovery_potential"]["reveals_new_structure"]["basis"] = []
        self.assertIn("SV2", {d.rule for d in sm.validate_value(broken)})

    def test_a_missing_dimension_is_rejected(self):
        assessment = sm.value_assessment(self.state, self.index, "H1", self.scheduler)
        broken = clone(assessment)
        del broken["decision_value"]["changes_route"]
        self.assertIn("SV2", {d.rule for d in sm.validate_value(broken)})

    def test_value_refers_to_the_research_contract(self):
        assessment = sm.value_assessment(self.state, self.index, "H1", self.scheduler)
        relation = assessment["considerations"]["contract_relation"]
        self.assertIn("contract:primary_anchor", relation["basis"])
        self.assertIn(self.state["contract"]["primary_anchor"], relation["note"])

    def test_the_strongest_objection_is_required(self):
        claim = sm.value_assessment(self.state, self.index, "C1", self.scheduler)
        self.assertTrue(any("替代解释" in item for item in claim["objections"]))
        hypothesis = sm.value_assessment(self.state, self.index, "H1", self.scheduler)
        self.assertTrue(hypothesis["objections"])
        self.assertTrue(any("尚未登记反对意见" in item for item in hypothesis["objections"]))

    def test_an_unknown_target_is_an_environment_error(self):
        with self.assertRaises(cg.CognitionError):
            sm.value_assessment(self.state, self.index, "H404", self.scheduler)

    def test_cost_comes_from_the_scheduler_when_it_exists(self):
        with_scheduler = sm.value_assessment(self.state, self.index, "C1", self.scheduler)
        self.assertEqual(with_scheduler["considerations"]["experiment_cost"], "low")
        without = sm.value_assessment(self.state, self.index, "H1", self.scheduler)
        self.assertEqual(without["considerations"]["experiment_cost"], "unknown")


# ---------------------------------------------------------------------------
# 3.2 Taste memory
# ---------------------------------------------------------------------------

class TestTasteMemory(Base):

    def test_human_preferences_come_from_the_contract_and_are_read_only(self):
        taste = sm.calibrated_preferences(self.state, self.index, self.scheduler)
        human = taste["human_specified"]
        self.assertEqual(human["authority"], "user")
        self.assertFalse(human["mutable_by_agent"])
        self.assertEqual(human["primary_anchor"], self.state["contract"]["primary_anchor"])
        self.assertEqual(human["out_of_scope"], self.state["contract"]["out_of_scope"])

    def test_the_anchor_is_never_touched(self):
        taste = sm.calibrated_preferences(self.state, self.index, self.scheduler)
        self.assertTrue(taste["anchor_untouched"])
        self.assertEqual(self.state["contract"]["primary_anchor"], "phenomenon")

    def test_calibrated_preferences_cite_evidence(self):
        taste = sm.calibrated_preferences(self.state, self.index, self.scheduler)
        self.assertTrue(taste["evidence_calibrated"])
        for item in taste["evidence_calibrated"]:
            self.assertTrue(item["basis"])
            self.assertTrue(item["revisit_conditions"])
            self.assertEqual(item["kind"], "evidence_calibrated")

    def test_empty_diagnostics_and_productive_interventions_are_learned(self):
        taste = sm.calibrated_preferences(self.state, self.index, self.scheduler)
        ids = {item["id"] for item in taste["evidence_calibrated"]}
        self.assertIn("TP-DIAG", ids)
        self.assertIn("TP-INTERV", ids)

    def test_a_dormant_operator_does_not_become_a_mechanism_class_verdict(self):
        taste = sm.calibrated_preferences(self.state, self.index, self.scheduler)
        entry = next(item for item in taste["evidence_calibrated"] if item["id"] == "TP-DORMANT")
        self.assertIn("不构成永久淘汰", entry["statement"])
        self.assertTrue(entry["revisit_conditions"])

    def test_learning_updates_when_the_evidence_changes(self):
        silent = sm.calibrated_preferences(self.state, self.index, self.quiet_scheduler())
        loud = sm.calibrated_preferences(self.state, self.index, self.scheduler)
        self.assertNotEqual(silent["carried_experience"], loud["carried_experience"])

    def test_preferences_do_not_reference_a_score(self):
        taste = sm.calibrated_preferences(self.state, self.index, self.scheduler)
        blob = json.dumps(taste, ensure_ascii=False)
        for key in sm.BANNED_AGGREGATE_KEYS:
            self.assertNotIn(f'"{key}"', blob)


# ---------------------------------------------------------------------------
# 3.3 Adaptive discovery
# ---------------------------------------------------------------------------

class TestAdaptiveDiscovery(Base):

    def test_menu_table_reuses_frozen_operators_and_islands(self):
        for entry in sm.STRATEGY_MENUS:
            self.assertIn(entry["operator"], sc.OPERATORS)
            self.assertIn(entry["island"], sc.ISLANDS)

    def test_no_new_operator_or_agent_is_introduced(self):
        operators = {entry["operator"] for entry in sm.STRATEGY_MENUS}
        self.assertTrue(operators <= set(sc.OPERATORS))
        module_source = (ROOT / "scripts" / "strategy_memory.py").read_text(encoding="utf-8")
        self.assertNotIn("class ExplorationAgent", module_source)

    def test_a_failure_history_deprioritises_but_never_bans(self):
        priors = sm.operator_priors(self.state, self.index, self.scheduler)
        self.assertEqual(sm.validate_priors(priors), [])
        for name, entry in priors["by_operator"].items():
            self.assertIn(entry["status"], sm.OPERATOR_STATUSES)
            self.assertNotIn(entry["status"], ("forbidden", "banned", "disabled"))
            if entry["status"] in ("discouraged", "dormant"):
                self.assertTrue(entry["reactivation_conditions"], msg=name)

    def test_one_failure_cannot_condemn_an_operator(self):
        priors = sm.operator_priors(self.state, self.index, self.scheduler)
        broken = clone(priors)
        broken["by_operator"]["remote_analogy"] = {
            "status": "discouraged", "failures": ["H2"], "successes": [],
            "scope": ["mechanism-shift"], "reactivation_conditions": ["x"]}
        self.assertIn("SV5", {d.rule for d in sm.validate_priors(broken)})

    def test_a_discouraged_operator_must_be_scoped(self):
        priors = sm.operator_priors(self.state, self.index, self.scheduler)
        broken = clone(priors)
        broken["by_operator"]["theory_lens"]["scope"] = []
        self.assertIn("SV5", {d.rule for d in sm.validate_priors(broken)})

    def test_dropping_the_exploration_floor_is_rejected(self):
        priors = sm.operator_priors(self.state, self.index, self.scheduler)
        broken = clone(priors)
        broken["exploration_floor"] = []
        self.assertIn("SV7", {d.rule for d in sm.validate_priors(broken)})

    def test_the_exploration_floor_is_never_empty(self):
        for scheduler in (None, self.scheduler, self.quiet_scheduler()):
            priors = sm.operator_priors(self.state, self.index, scheduler)
            self.assertTrue(priors["exploration_floor"])

    def test_a_discouraged_operator_remains_an_admissible_menu(self):
        recommendation = sm.recommend_strategy(self.state, self.index, self.scheduler,
                                               self.revisions)
        self.assertTrue(set(recommendation["discouraged_but_admissible"]) <=
                        {entry["operator"] for entry in sm.STRATEGY_MENUS})
        self.assertEqual(len(recommendation["ordered_menus"]), len(sm.STRATEGY_MENUS))

    def test_the_same_operator_is_not_banned_across_different_structures(self):
        """Deprioritising one operator must not remove the others from consideration."""
        priors = sm.operator_priors(self.state, self.index, self.scheduler)
        discouraged = set(priors["discouraged"])
        self.assertTrue(set(priors["by_operator"]) - discouraged)

    def test_a_recommendation_is_lexicographic_and_carries_no_score(self):
        recommendation = sm.recommend_strategy(self.state, self.index, self.scheduler,
                                               self.revisions)
        self.assertEqual(sm.validate_recommendation(recommendation), [])
        blob = json.dumps(recommendation, ensure_ascii=False)
        for key in sm.BANNED_AGGREGATE_KEYS:
            self.assertNotIn(f'"{key}"', blob)

    def test_unconditional_extra_rounds_are_rejected(self):
        recommendation = sm.recommend_strategy(self.state, self.index, self.scheduler,
                                               self.revisions)
        self.assertEqual(recommendation["exploration_rounds_delta"], 0)
        broken = clone(recommendation)
        broken["exploration_rounds_delta"] = 2
        self.assertIn("SV7", {d.rule for d in sm.validate_recommendation(broken)})

    def test_independent_exploration_is_never_globally_blocked(self):
        recommendation = sm.recommend_strategy(self.state, self.index, self.scheduler,
                                               self.revisions)
        self.assertTrue(recommendation["independent_exploration_allowed"])
        broken = clone(recommendation)
        broken["independent_exploration_allowed"] = False
        self.assertIn("SV7", {d.rule for d in sm.validate_recommendation(broken)})

    def test_stop_rules_remove_a_menu_from_the_top(self):
        state = clone(self.state)
        state["failures"] = [{
            "id": "F1", "kind": "failed-to-reproduce", "what": "theory_lens 只产出重述",
            "why": "两次独立复现", "referenced_by": ["H1"], "depends_on": [],
            "validity": {"status": "valid", "reason": "x", "since_state_version": 4},
            "source_review": None,
        }]
        index, _ = cg.full_index(state, self.revisions, "A")
        recommendation = sm.recommend_strategy(state, index, self.scheduler, self.revisions)
        self.assertIn("change_research_scale", recommendation["blocked_menus"])


# ---------------------------------------------------------------------------
# P4 context isolation
# ---------------------------------------------------------------------------

class TestCrossDomainIsolation(unittest.TestCase):

    def build(self, payload):
        temp = tempfile.TemporaryDirectory()
        root = pathlib.Path(temp.name)
        (root / "skeleton.json").write_text(json.dumps(payload), encoding="utf-8")
        return temp, root

    def test_a_clean_skeleton_crosses(self):
        temp, root = self.build({"object": "o", "relation": "r", "constraint": "c",
                                 "failure_mode": "f", "core_unknown": "u"})
        self.addCleanup(temp.cleanup)
        context = sm.p4_context(root)
        self.assertEqual(len(context["skeletons"]), 1)
        self.assertEqual(context["diagnostics"], [])

    def test_candidate_content_is_refused(self):
        for key in sm.CANDIDATE_LEAK_KEYS:
            payload = {"object": "o", "relation": "r", "constraint": "c",
                       "failure_mode": "f", "core_unknown": "u", key: "leak"}
            temp, root = self.build(payload)
            self.addCleanup(temp.cleanup)
            context = sm.p4_context(root)
            self.assertEqual(context["skeletons"], [], msg=key)
            self.assertTrue(context["diagnostics"], msg=key)

    def test_a_skeleton_missing_a_slot_is_refused(self):
        temp, root = self.build({"object": "o", "relation": "r"})
        self.addCleanup(temp.cleanup)
        context = sm.p4_context(root)
        self.assertEqual(context["skeletons"], [])
        self.assertTrue(any("槽位" in d.detail for d in context["diagnostics"]))

    def test_a_missing_directory_is_reported_not_assumed_empty(self):
        context = sm.p4_context(pathlib.Path("/nonexistent/intermediates"))
        self.assertEqual(context["skeletons"], [])
        self.assertIn("SV6", {d.rule for d in context["diagnostics"]})

    def test_a_polluted_context_is_rejected(self):
        polluted = {"skeletons": [{"object": "o", "relation": "r", "constraint": "c",
                                   "failure_mode": "f", "core_unknown": "u",
                                   "answer": "another island's candidate"}]}
        self.assertIn("SV6", {d.rule for d in sm.validate_p4_context(polluted)})


# ---------------------------------------------------------------------------
# 3.4 The learning loop closes
# ---------------------------------------------------------------------------

class TestLearningLoop(Base):

    def test_history_changes_the_ordered_menus(self):
        before = sm.recommend_strategy(self.state, self.index, self.quiet_scheduler(),
                                       self.revisions)
        after = sm.recommend_strategy(self.state, self.index, self.scheduler, self.revisions)
        self.assertNotEqual(before["ordered_menus"], after["ordered_menus"])

    def test_the_operator_with_no_output_is_deprioritised(self):
        before = sm.recommend_strategy(self.state, self.index, self.quiet_scheduler(),
                                       self.revisions)
        after = sm.recommend_strategy(self.state, self.index, self.scheduler, self.revisions)
        self.assertGreater(after["ordered_menus"].index("change_research_scale"),
                           before["ordered_menus"].index("change_research_scale"))

    def test_the_trace_from_outcome_to_next_action_is_complete(self):
        """One traceable chain: telemetry → prior → menu ordering → recommendation."""
        priors = sm.operator_priors(self.state, self.index, self.scheduler)
        taste = sm.calibrated_preferences(self.state, self.index, self.scheduler)
        recommendation = sm.recommend_strategy(self.state, self.index, self.scheduler,
                                               self.revisions)
        self.assertEqual(priors["by_operator"]["theory_lens"]["status"], "dormant")
        self.assertIn("TP-DORMANT", {item["id"] for item in taste["evidence_calibrated"]})
        self.assertIn("theory_lens", priors["discouraged"])
        self.assertEqual(recommendation["exploration_rounds_delta"], 0)
        self.assertTrue(recommendation["basis"])

    def test_a_repeated_menu_forces_divergence(self):
        repeated = list(self.revisions)
        for index in range(sm.STAGNANT_MENU_RUN):
            repeated.append({
                "_schema": cg.SCHEMA_REVISION, "id": f"REV{index + 10}",
                "seq": index + 10, "kind": "strategy_update",
                "subject": "assumption_breaker", "actor": "R6", "at_state_version": 4,
                "summary": "repeat", "trigger": {"kind": "exploration_outcome", "ref": "H1"},
                "refs": {"hypotheses": ["H1"]},
                "after": {"menu": "invert_hidden_assumption",
                          "operator": "assumption_breaker"}})
        recommendation = sm.recommend_strategy(self.state, self.index, self.scheduler,
                                               repeated)
        self.assertNotEqual(recommendation["ordered_menus"][0], "invert_hidden_assumption")

    def test_the_loop_emits_only_sourced_updates(self):
        loop = sm.strategy_updates(self.state, self.index, self.scheduler)
        self.assertTrue(loop["updates"])
        for update in loop["updates"]:
            self.assertTrue(any(update["refs"].get(key) for key in cg.REF_KEYS))
            self.assertEqual(update["kind"], "strategy_update")
            self.assertIn(update["after"]["action"], ("encourage", "discourage"))

    def test_the_loop_does_not_touch_the_state(self):
        before = cg.canonical_json(self.state)
        sm.strategy_updates(self.state, self.index, self.scheduler)
        sm.recommend_strategy(self.state, self.index, self.scheduler, self.revisions)
        self.assertEqual(cg.canonical_json(self.state), before)


# ---------------------------------------------------------------------------
# Recorded strategy updates
# ---------------------------------------------------------------------------

class TestStrategyRevisionValidation(Base):

    def record(self, **after):
        return {"kind": "strategy_update", "actor": "R6", "id": "REV9", "seq": 9,
                "refs": {"hypotheses": ["H1"]}, "after": after}

    def rules(self, record):
        return {d.rule for d in sm.validate_strategy_revisions(self.state, [record])}

    def test_a_valid_update_passes(self):
        self.assertEqual(self.rules(self.record(operator="assumption_breaker",
                                                action="discourage")), set())

    def test_an_anchor_change_is_rejected(self):
        for key in ("contract", "primary_anchor", "anchor", "out_of_scope", "research_goal"):
            self.assertIn("SV3", self.rules(self.record(**{key: "performance"})), msg=key)

    def test_a_score_is_rejected(self):
        for key in sm.BANNED_AGGREGATE_KEYS:
            self.assertIn("SV1", self.rules(self.record(**{key: 0.5})), msg=key)

    def test_an_invented_operator_is_rejected(self):
        self.assertIn("SV5", self.rules(self.record(operator="paradigm_magic")))

    def test_a_read_only_stage_cannot_write_cognition(self):
        for actor in ("R7", "R12", "R13", "R14"):
            record = self.record(operator="reframe", action="encourage")
            record["actor"] = actor
            self.assertIn("SV6", self.rules(record), msg=actor)

    def test_an_unsourced_update_is_rejected(self):
        record = self.record(operator="reframe", action="encourage")
        record["refs"] = {}
        self.assertIn("SV8", self.rules(record))

    def test_a_dangling_reference_is_rejected(self):
        record = self.record(operator="reframe", action="encourage")
        record["refs"] = {"hypotheses": ["H404"]}
        self.assertIn("SV8", self.rules(record))


# ---------------------------------------------------------------------------
# Scheduler boundary
# ---------------------------------------------------------------------------

class TestSchedulerBoundary(Base):

    def test_the_scheduler_is_read_only(self):
        scheduler = clone(self.scheduler)
        before = cg.canonical_json(scheduler)
        sm.operator_priors(self.state, self.index, scheduler)
        sm.calibrated_preferences(self.state, self.index, scheduler)
        sm.recommend_strategy(self.state, self.index, scheduler, self.revisions)
        sm.strategy_updates(self.state, self.index, scheduler)
        self.assertEqual(cg.canonical_json(scheduler), before)

    def test_no_priority_level_is_redefined(self):
        recommendation = sm.recommend_strategy(self.state, self.index, self.scheduler,
                                               self.revisions)
        source = (ROOT / "scripts" / "strategy_memory.py").read_text(encoding="utf-8")
        self.assertNotIn("next_action_policy", recommendation)
        self.assertNotIn("\"priority\":", source)

    def test_telemetry_is_labelled_as_telemetry(self):
        index, _ = cg.full_index(self.state, self.revisions, "A", None, self.scheduler)
        self.assertIn("telemetry", index["strategy"]["source"])
        self.assertIn("never evidence", index["strategy"]["source"])

    def test_history_is_read_from_operator_stats(self):
        priors = sm.operator_priors(self.state, self.index, self.scheduler)
        self.assertEqual(priors["by_operator"]["theory_lens"]["status"], "dormant")
        self.assertTrue(priors["by_operator"]["theory_lens"]["telemetry_dormant"])


# ---------------------------------------------------------------------------
# Cognitive index integration
# ---------------------------------------------------------------------------

class TestIndexIntegration(Base):

    def test_the_index_projects_the_strategy_layer(self):
        index, diagnostics = cg.full_index(self.state, self.revisions, "A", None, self.scheduler)
        self.assertIn("strategy", index)
        self.assertIn("recommendation", index["strategy"])
        self.assertIn("operators", index["strategy"])
        self.assertEqual(index["counts"]["discouraged_operators"],
                         len(index["strategy"]["operators"]["discouraged"]))

    def test_the_index_omits_the_strategy_layer_without_telemetry(self):
        index, _ = cg.full_index(self.state, self.revisions, "A")
        self.assertNotIn("strategy", index)

    def test_a_scheduler_change_invalidates_the_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path = root / cg.STATE_NAME
            state_path.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
            (root / cg.SCHEDULER_NAME).write_text(json.dumps(self.scheduler), encoding="utf-8")
            cognition_dir = root / cg.COGNITION_DIRNAME
            cognition_dir.mkdir()
            (cognition_dir / cg.REVISIONS_NAME).write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in self.revisions),
                encoding="utf-8")
            self.assertEqual(quiet(cg.op_build, state_path, cognition_dir)[0], cg.EXIT_OK)
            self.assertEqual(quiet(cg.op_check, state_path, cognition_dir)[0], cg.EXIT_OK)
            changed = clone(self.scheduler)
            changed["operator_stats"]["by_operator"] = {}
            (root / cg.SCHEDULER_NAME).write_text(json.dumps(changed), encoding="utf-8")
            self.assertEqual(quiet(cg.op_check, state_path, cognition_dir)[0], cg.EXIT_HARD)

    def test_the_brief_carries_the_strategy_section(self):
        index, _ = cg.full_index(self.state, self.revisions, "A", None, self.scheduler)
        brief = cg.render_brief(index, self.state)
        self.assertIn("## Scientific value and adaptive discovery", brief)
        self.assertIn("Telemetry is labelled", brief)
        self.assertIn("exploration floor", brief)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCLI(Base):

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, cwd=str(ROOT))

    def project(self, root: pathlib.Path):
        state_path = root / cg.STATE_NAME
        state_path.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        (root / cg.SCHEDULER_NAME).write_text(json.dumps(self.scheduler), encoding="utf-8")
        cognition_dir = root / cg.COGNITION_DIRNAME
        cognition_dir.mkdir()
        (cognition_dir / cg.REVISIONS_NAME).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in self.revisions),
            encoding="utf-8")
        return state_path, cognition_dir

    def test_selftest_passes(self):
        proc = self.run_cli("--selftest")
        self.assertEqual(proc.returncode, sm.EXIT_OK, proc.stdout + proc.stderr)
        self.assertIn("selftest: PASS", proc.stdout)

    def test_list_menus(self):
        proc = self.run_cli("--list-menus")
        self.assertEqual(proc.returncode, sm.EXIT_OK)
        self.assertEqual(len([line for line in proc.stdout.splitlines() if line.strip()]),
                         len(sm.STRATEGY_MENUS))

    def test_value_command(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path, cognition_dir = self.project(pathlib.Path(temp))
            proc = self.run_cli("value", "--state", str(state_path),
                                "--cognition", str(cognition_dir), "--target", "H1")
            self.assertEqual(proc.returncode, sm.EXIT_OK, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertIn("decision_value", payload)

    def test_operators_recommend_and_apply(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path, cognition_dir = self.project(pathlib.Path(temp))
            for command in ("operators", "recommend", "apply", "taste"):
                proc = self.run_cli(command, "--state", str(state_path),
                                    "--cognition", str(cognition_dir))
                self.assertEqual(proc.returncode, sm.EXIT_OK,
                                 msg=f"{command}: {proc.stdout}{proc.stderr}")
                self.assertTrue(json.loads(proc.stdout))

    def test_a_missing_state_is_an_environment_error(self):
        self.assertEqual(self.run_cli("taste", "--state", "/nope.json").returncode,
                         sm.EXIT_ENV)

    def test_a_broken_scheduler_is_an_environment_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state_path, cognition_dir = self.project(root)
            (root / cg.SCHEDULER_NAME).write_text("{not json", encoding="utf-8")
            proc = self.run_cli("taste", "--state", str(state_path),
                                "--cognition", str(cognition_dir))
            self.assertEqual(proc.returncode, sm.EXIT_ENV)

    def test_missing_command_is_an_argument_error(self):
        self.assertEqual(self.run_cli().returncode, sm.EXIT_ERROR)


if __name__ == "__main__":
    unittest.main()
