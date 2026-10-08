#!/usr/bin/env python3
"""test_legacy_handoff.py — regression tests for taking over an existing project.

The scenario this file protects is concrete: a researcher has already run the pipeline,
so a canonical `research-state.json`, a scheduler, failure memory and spent diagnostic
budget exist. Loading a newer skill must not look like a fresh start, must not reset
anything, and must not repair a broken state by building a new one.

Coverage required by the specification: lossless takeover, cross-session restart, repeated
takeover, missing history, evidence-invalidation propagation, prediction time leakage,
multi-route isolation, and use of the recovered knowledge in the next round.
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import shutil
import tempfile
import unittest

import cognition as cg
import legacy_handoff as lh
import prediction_compare as pc

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "examples" / "cognition"


def quiet(callable_, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()) as sink:
        result = callable_(*args, **kwargs)
    return result, sink.getvalue()


def quiet_all(callable_, *args, **kwargs):
    """Both streams: blocking findings are printed to stderr by design."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        result = callable_(*args, **kwargs)
    return result, out.getvalue() + err.getvalue()


class Project:
    """A legacy project laid out the way the pipeline expects on disk."""

    def __init__(self, root: pathlib.Path, route: str = "A", state: dict | None = None):
        self.root = root
        self.route = route
        self.route_dir = root / ".research-idea-pipeline" / "routes" / route
        self.route_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.route_dir / cg.STATE_NAME
        payload = state if state is not None else lh._legacy_state()
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        (root / "routes" / route).mkdir(parents=True, exist_ok=True)
        for name in ("README.md", "STATUS.md", "INDEX.md"):
            (root / "routes" / route / name).write_text(f"# {name}\n", encoding="utf-8")

    @property
    def cognition_dir(self) -> pathlib.Path:
        return self.route_dir / cg.COGNITION_DIRNAME

    def add_scheduler(self, version: int = 7) -> pathlib.Path:
        path = self.route_dir / "scheduler.json"
        path.write_text(json.dumps({
            "_schema": "research-idea-pipeline/scheduler@1",
            "state_version": version,
            "next_actions": [{"action": "X2", "type": "discriminating_experiment",
                              "target": "U1", "eig": "high", "cost": "low"}],
            "eig_calibration": {"records": []},
            "operator_stats": {"by_operator": {}, "recurring_failure_patterns": []},
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def add_execution_ledger(self) -> pathlib.Path:
        ledger = self.route_dir / ".execution"
        ledger.mkdir(exist_ok=True)
        (ledger / "policy.json").write_text(json.dumps({"max_preflight_revisions": 3}),
                                            encoding="utf-8")
        return ledger

    def snapshot(self) -> dict:
        """Every canonical artifact, byte for byte."""
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for path in sorted(self.route_dir.rglob("*")) if path.is_file()
        }


# ---------------------------------------------------------------------------
# 1. Lossless takeover
# ---------------------------------------------------------------------------

class TestLosslessTakeover(unittest.TestCase):

    def test_canonical_artifacts_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            project.add_scheduler()
            project.add_execution_ledger()
            before = project.snapshot()
            self.assertEqual(quiet(lh._take, project.state_path, project.root)[0], lh.EXIT_OK)
            after = project.snapshot()
            for name, payload in before.items():
                self.assertEqual(after.get(name), payload, msg=f"{name} changed during takeover")

    def test_state_version_claim_status_ids_and_anchor_are_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            original = json.loads(project.state_path.read_text(encoding="utf-8"))
            quiet(lh._take, project.state_path, project.root)
            current = json.loads(project.state_path.read_text(encoding="utf-8"))
            self.assertEqual(current, original)
            self.assertEqual(current["state_version"], original["state_version"])
            self.assertEqual(current["contract"], original["contract"])
            self.assertEqual([c["status"] for c in current["claims"]],
                             [c["status"] for c in original["claims"]])
            self.assertEqual([e["id"] for e in current["evidence"]],
                             [e["id"] for e in original["evidence"]])
            self.assertEqual([x["id"] for x in current["experiments"]],
                             [x["id"] for x in original["experiments"]])

    def test_execution_ledger_is_not_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            ledger = project.add_execution_ledger()
            before = (ledger / "policy.json").read_bytes()
            quiet(lh._take, project.state_path, project.root)
            self.assertEqual((ledger / "policy.json").read_bytes(), before)

    def test_takeover_does_not_create_a_new_state(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            before = {path.name for path in project.route_dir.iterdir()}
            quiet(lh._take, project.state_path, project.root)
            after = {path.name for path in project.route_dir.iterdir()}
            self.assertEqual(after - before, {cg.COGNITION_DIRNAME})
            self.assertEqual(len(list(project.route_dir.glob(cg.STATE_NAME))), 1)

    def test_handoff_declares_that_nothing_canonical_changed(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            quiet(lh._take, project.state_path, project.root)
            handoff = json.loads((project.cognition_dir / lh.HANDOFF_NAME).read_text("utf-8"))
            self.assertTrue(handoff["canonical_untouched"])
            self.assertEqual(handoff["state_digest"], cg.digest_of(
                json.loads(project.state_path.read_text(encoding="utf-8"))))


# ---------------------------------------------------------------------------
# 2. Cross-session restart
# ---------------------------------------------------------------------------

class TestCrossSessionRestart(unittest.TestCase):

    def test_a_fresh_session_recovers_understanding_not_just_a_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            quiet(lh._take, project.state_path, project.root)
            # Simulate a new session: nothing in memory, everything re-read from disk.
            state = cg.load_state(project.state_path)
            revisions, _ = cg.load_revisions(project.cognition_dir / cg.REVISIONS_NAME)
            index, _ = cg.full_index(state, revisions, project.route)
            brief = (project.cognition_dir / cg.BRIEF_NAME).read_text(encoding="utf-8")
            self.assertTrue(index["mechanisms"])
            self.assertIn("## Hot memory", brief)
            self.assertIn("[RETROSPECTIVE]", brief)
            self.assertIn("## Boundaries", brief)
            self.assertIn("## Failure memory", brief)
            self.assertIn("[", brief)

    def test_recovered_memory_is_usable_without_a_manual_path(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            quiet(lh._take, project.state_path, project.root)
            # `cognition check` uses the default cognition directory next to the state.
            self.assertEqual(quiet(cg.op_check, project.state_path, project.cognition_dir)[0],
                             cg.EXIT_OK)
            self.assertEqual(quiet(cg.op_build, project.state_path, project.cognition_dir)[0],
                             cg.EXIT_OK)
            self.assertEqual(quiet(cg.op_check, project.state_path, project.cognition_dir)[0],
                             cg.EXIT_OK)

    def test_restart_after_a_state_change_requires_a_rebuild_not_silent_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            quiet(lh._take, project.state_path, project.root)
            state = json.loads(project.state_path.read_text(encoding="utf-8"))
            state["uncertainties"][0]["uncertainty"] = "medium"
            project.state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(quiet(cg.op_check, project.state_path, project.cognition_dir)[0],
                             cg.EXIT_HARD)
            quiet(cg.op_build, project.state_path, project.cognition_dir)
            self.assertEqual(quiet(cg.op_check, project.state_path, project.cognition_dir)[0],
                             cg.EXIT_OK)


# ---------------------------------------------------------------------------
# 3. Repeated takeover
# ---------------------------------------------------------------------------

class TestRepeatedTakeover(unittest.TestCase):

    def test_second_takeover_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            quiet(lh._take, project.state_path, project.root)
            first = {name: (project.cognition_dir / name).read_bytes() for name in lh.OWNED_FILES}
            _, stdout = quiet(lh._take, project.state_path, project.root)
            second = {name: (project.cognition_dir / name).read_bytes() for name in lh.OWNED_FILES}
            self.assertEqual(first, second)
            self.assertTrue(json.loads(stdout)["already_initialized"])

    def test_first_takeover_reports_not_already_initialized(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            _, stdout = quiet(lh._take, project.state_path, project.root)
            self.assertFalse(json.loads(stdout)["already_initialized"])

    def test_rollback_then_take_over_again(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            quiet(lh._take, project.state_path, project.root)
            first = (project.cognition_dir / cg.INDEX_NAME).read_bytes()
            self.assertEqual(quiet(lh._rollback, project.state_path)[0], lh.EXIT_OK)
            self.assertFalse(project.cognition_dir.exists())
            self.assertEqual(quiet(lh._take, project.state_path, project.root)[0], lh.EXIT_OK)
            self.assertEqual((project.cognition_dir / cg.INDEX_NAME).read_bytes(), first)

    def test_rollback_refuses_unknown_content(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            quiet(lh._take, project.state_path, project.root)
            (project.cognition_dir / "hand-notes.txt").write_text("x", encoding="utf-8")
            self.assertEqual(quiet(lh._rollback, project.state_path)[0], lh.EXIT_HARD)
            self.assertTrue((project.cognition_dir / cg.INDEX_NAME).is_file())


# ---------------------------------------------------------------------------
# 4. Missing history
# ---------------------------------------------------------------------------

class TestMissingHistory(unittest.TestCase):

    def test_a_project_with_no_revision_log_still_projects_understanding(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            self.assertEqual(quiet(lh._take, project.state_path, project.root)[0], lh.EXIT_OK)
            index = json.loads((project.cognition_dir / cg.INDEX_NAME).read_text("utf-8"))
            self.assertEqual(index["provenance_mode"], "legacy_derivation")
            for mechanism in index["mechanisms"]:
                self.assertEqual(mechanism["provenance"]["origin"], cg.LEGACY_ORIGIN)
                self.assertTrue(mechanism["provenance"]["retrospective"])
                self.assertEqual(mechanism["revision_ids"], [])

    def test_no_prediction_is_invented_for_an_unregistered_outcome(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            quiet(lh._take, project.state_path, project.root)
            handoff = json.loads((project.cognition_dir / lh.HANDOFF_NAME).read_text("utf-8"))
            retro = [item for item in handoff["unrecovered"]
                     if item["status"] == "retrospective"]
            self.assertTrue(retro, "an outcome without a criterion must be marked")
            blob = json.dumps(handoff, ensure_ascii=False)
            self.assertNotIn('"PREDICTION_HELD"', blob)
            self.assertNotIn('"PREDICTION_DEVIATED"', blob)

    def test_missing_route_documents_are_reported_not_written(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            project = Project(root)
            for name in ("README.md", "STATUS.md", "INDEX.md"):
                (root / "routes" / project.route / name).unlink()
            quiet(lh._take, project.state_path, project.root)
            handoff = json.loads((project.cognition_dir / lh.HANDOFF_NAME).read_text("utf-8"))
            self.assertTrue(any(item["status"] == "unknown" for item in handoff["unrecovered"]))
            for name in ("README.md", "STATUS.md", "INDEX.md"):
                self.assertFalse((root / "routes" / project.route / name).exists())

    def test_a_project_with_no_scheduler_is_still_takeable(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            self.assertEqual(quiet(lh._take, project.state_path, project.root)[0], lh.EXIT_OK)
            handoff = json.loads((project.cognition_dir / lh.HANDOFF_NAME).read_text("utf-8"))
            self.assertEqual(handoff["next_action"]["source"], "cognition")


# ---------------------------------------------------------------------------
# 5. Evidence invalidation propagation
# ---------------------------------------------------------------------------

class TestInvalidationPropagation(unittest.TestCase):

    def invalidated_project(self, root: pathlib.Path) -> Project:
        state = lh._legacy_state()
        state["evidence"][0]["validity"] = {"status": "invalid",
                                            "reason": "源实验作废", "since_state_version": 6}
        state["claims"][0]["supporting_evidence"] = []
        state["claims"][0]["refuting_evidence"] = []
        state["claims"][0]["status"] = "ungrounded"
        state["claims"][0]["validity"] = {"status": "stale", "reason": "上游失效",
                                          "since_state_version": 6}
        return Project(root, state=state)

    def test_invalidated_evidence_marks_the_derived_mechanism_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.invalidated_project(pathlib.Path(temp))
            quiet(lh._take, project.state_path, project.root)
            index = json.loads((project.cognition_dir / cg.INDEX_NAME).read_text("utf-8"))
            stale = [m for m in index["mechanisms"] if m["stale"]]
            self.assertTrue(stale, "no derived mechanism followed the invalidation")
            for mechanism in stale:
                self.assertTrue(mechanism["stale_reasons"])

    def test_stale_memory_leaves_hot_recall(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.invalidated_project(pathlib.Path(temp))
            quiet(lh._take, project.state_path, project.root)
            state = cg.load_state(project.state_path)
            revisions, _ = cg.load_revisions(project.cognition_dir / cg.REVISIONS_NAME)
            index, _ = cg.full_index(state, revisions, project.route)
            selection = cg.recall(index, state)
            hot_ids = {m["id"] for m in selection["hot"]["mechanisms"]}
            stale_ids = {m["id"] for m in index["mechanisms"] if m["stale"]}
            self.assertFalse(hot_ids & stale_ids)
            self.assertTrue(stale_ids)

    def test_invalidation_boundary_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.invalidated_project(pathlib.Path(temp))
            quiet(lh._take, project.state_path, project.root)
            index = json.loads((project.cognition_dir / cg.INDEX_NAME).read_text("utf-8"))
            self.assertTrue(any(item["kind"] == "invalidated_object"
                                for item in index["boundaries"]))

    def test_invalidation_does_not_change_the_state(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.invalidated_project(pathlib.Path(temp))
            before = project.state_path.read_bytes()
            quiet(lh._take, project.state_path, project.root)
            self.assertEqual(project.state_path.read_bytes(), before)


# ---------------------------------------------------------------------------
# 6. Prediction time leakage
# ---------------------------------------------------------------------------

class TestPredictionTimeLeakage(unittest.TestCase):

    def test_a_prediction_frozen_after_the_result_blocks_takeover(self):
        with tempfile.TemporaryDirectory() as temp:
            state = lh._legacy_state()
            state["experiments"][0]["preregistration"]["frozen_at_state_version"] = 99
            project = Project(pathlib.Path(temp), state=state)
            code, stdout = quiet(lh._take, project.state_path, project.root)
            self.assertEqual(code, lh.EXIT_HARD)
            self.assertFalse(project.cognition_dir.exists())

    def test_the_blocking_reason_names_the_leak(self):
        with tempfile.TemporaryDirectory() as temp:
            state = lh._legacy_state()
            state["experiments"][0]["preregistration"]["frozen_at_state_version"] = 99
            project = Project(pathlib.Path(temp), state=state)
            audit = lh.compatibility_audit(project.state_path, project.root)
            rules = {finding.rule for finding in audit["findings"]}
            self.assertIn("LH13", rules)
            self.assertTrue(audit["blocking"])

    def test_freeze_at_the_same_version_as_the_result_is_legal(self):
        with tempfile.TemporaryDirectory() as temp:
            state = lh._legacy_state()
            state["experiments"][0]["preregistration"]["frozen_at_state_version"] = 6
            project = Project(pathlib.Path(temp), state=state)
            audit = lh.compatibility_audit(project.state_path, project.root)
            self.assertFalse([f for f in audit["findings"] if f.rule == "LH13"])

    def test_an_unfinished_experiment_with_a_freezer_is_not_leakage(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            audit = lh.compatibility_audit(project.state_path, project.root)
            self.assertFalse([f for f in audit["findings"] if f.rule == "LH13"])

    def test_takeover_never_writes_into_a_blocked_project(self):
        with tempfile.TemporaryDirectory() as temp:
            state = lh._legacy_state()
            state["experiments"][0]["preregistration"]["frozen_at_state_version"] = 99
            project = Project(pathlib.Path(temp), state=state)
            before = project.snapshot()
            quiet(lh._take, project.state_path, project.root)
            self.assertEqual(project.snapshot(), before)


# ---------------------------------------------------------------------------
# 7. Multi-route isolation
# ---------------------------------------------------------------------------

class TestMultiRouteIsolation(unittest.TestCase):

    def two_routes(self, root: pathlib.Path):
        left = Project(root, route="A")
        right_state = lh._legacy_state()
        right_state["claims"][0]["id"] = "C7"
        right_state["claims"][0]["supporting_evidence"] = ["E7"]
        right_state["evidence"][0]["id"] = "E7"
        right_state["evidence"][0]["supports"] = ["C7"]
        right_state["experiments"][0]["claim_targeted"] = ["C7"]
        right_state["experiments"][0]["id"] = "X7"
        right_state["evidence"][0]["depends_on"] = ["X7"]
        right_state["claims"][0]["contract"]["supporting_required"] = ["E7"]
        right_state["claims"][0]["contract"]["minimal_discriminating_experiment"] = "X7"
        right_state["experiments"][1]["id"] = "X8"
        right_state["experiments"][1]["parent"] = "X7"
        right_state["experiments"][1]["claim_targeted"] = ["C7"]
        right_state["experiments"][1]["depends_on"] = ["X7"]
        right_state["failures"][0]["referenced_by"] = ["C7", "X7"]
        right_state["claims"][0]["known_flaws"] = ["F1"]
        right_state["uncertainties"][0]["cheapest_discriminating_test"] = "TBD"
        right_state["contract"]["goal"] = "判断机制 A 在路线 B 上是否成立"
        right = Project(root, route="B", state=right_state)
        return left, right

    def test_each_route_gets_its_own_cognition_layer(self):
        with tempfile.TemporaryDirectory() as temp:
            left, right = self.two_routes(pathlib.Path(temp))
            quiet(lh._take, left.state_path, left.root)
            quiet(lh._take, right.state_path, right.root)
            left_index = json.loads((left.cognition_dir / cg.INDEX_NAME).read_text("utf-8"))
            right_index = json.loads((right.cognition_dir / cg.INDEX_NAME).read_text("utf-8"))
            self.assertEqual(left_index["route"], "A")
            self.assertEqual(right_index["route"], "B")
            self.assertNotEqual(left_index["digest"]["state"], right_index["digest"]["state"])

    def test_no_cross_route_content_leaks(self):
        with tempfile.TemporaryDirectory() as temp:
            left, right = self.two_routes(pathlib.Path(temp))
            quiet(lh._take, left.state_path, left.root)
            quiet(lh._take, right.state_path, right.root)
            left_brief = (left.cognition_dir / cg.BRIEF_NAME).read_text("utf-8")
            right_brief = (right.cognition_dir / cg.BRIEF_NAME).read_text("utf-8")
            self.assertIn("C1", left_brief)
            self.assertNotIn("C7", left_brief)
            self.assertIn("C7", right_brief)
            self.assertNotIn("C1", right_brief)

    def test_building_one_route_leaves_the_other_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            left, right = self.two_routes(pathlib.Path(temp))
            quiet(lh._take, left.state_path, left.root)
            quiet(lh._take, right.state_path, right.root)
            right_before = {name: (right.cognition_dir / name).read_bytes()
                            for name in lh.OWNED_FILES}
            left_state = json.loads(left.state_path.read_text(encoding="utf-8"))
            left_state["state_version"] = 8
            left.state_path.write_text(json.dumps(left_state, ensure_ascii=False),
                                       encoding="utf-8")
            quiet(cg.op_build, left.state_path, left.cognition_dir)
            right_after = {name: (right.cognition_dir / name).read_bytes()
                           for name in lh.OWNED_FILES}
            self.assertEqual(right_before, right_after)

    def test_a_route_index_cannot_be_validated_against_another_route_state(self):
        with tempfile.TemporaryDirectory() as temp:
            left, right = self.two_routes(pathlib.Path(temp))
            quiet(lh._take, left.state_path, left.root)
            quiet(lh._take, right.state_path, right.root)
            self.assertEqual(
                quiet(cg.op_check, right.state_path, left.cognition_dir)[0], cg.EXIT_HARD)


# ---------------------------------------------------------------------------
# 8. The next round must use the recovered knowledge
# ---------------------------------------------------------------------------

class TestNextRoundUsesRecoveredKnowledge(unittest.TestCase):

    def recover(self, root: pathlib.Path):
        project = Project(root)
        project.add_scheduler()
        quiet(lh._take, project.state_path, project.root)
        state = cg.load_state(project.state_path)
        revisions, _ = cg.load_revisions(project.cognition_dir / cg.REVISIONS_NAME)
        index, _ = cg.full_index(state, revisions, project.route)
        return project, state, index

    def test_prioritised_actions_come_from_the_existing_scheduler(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _, _ = self.recover(pathlib.Path(temp))
            handoff = json.loads((project.cognition_dir / lh.HANDOFF_NAME).read_text("utf-8"))
            self.assertEqual(handoff["next_action"]["source"], "scheduler.json")
            self.assertEqual(handoff["next_action"]["action"], "X2")

    def test_forbidden_repeats_are_recovered_and_reenforced(self):
        with tempfile.TemporaryDirectory() as temp:
            _, state, index = self.recover(pathlib.Path(temp))
            constraints = cg.failure_constraints(state)
            self.assertTrue(constraints)
            self.assertEqual(constraints[0]["retry"], "blocked")
            self.assertTrue(any(item["kind"] == "failed_repeat" for item in index["boundaries"]))
            handoff = index["boundaries"]
            self.assertTrue(handoff)

    def test_the_next_round_recalls_the_mechanism_behind_the_live_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            _, state, index = self.recover(pathlib.Path(temp))
            selection = cg.recall(index, state)
            hot_ids = {m["id"] for m in selection["hot"]["mechanisms"]}
            self.assertIn("LM-C1", hot_ids)
            self.assertIn("C1", selection["focus"])

    def test_the_recovered_competition_drives_the_diagnosis_switch(self):
        with tempfile.TemporaryDirectory() as temp:
            _, state, index = self.recover(pathlib.Path(temp))
            switch = pc.diagnosis_switch(state, index.get("competitions", []),
                                         None, index.get("mechanisms"))
            self.assertIn(switch["action"], pc.SWITCH_ACTIONS)
            self.assertNotEqual(switch["action"], "CONTINUE_ATTRIBUTION")
            self.assertTrue(switch["independent_exploration_allowed"])
            self.assertTrue(any(v["competition"] for v in switch["competition_verdicts"]))

    def test_the_brief_points_at_the_next_action(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _, _ = self.recover(pathlib.Path(temp))
            brief = (project.cognition_dir / cg.BRIEF_NAME).read_text("utf-8")
            self.assertIn("## Next action", brief)
            self.assertIn("## Boundaries", brief)

    def test_in_flight_work_is_not_rerun_or_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _, _ = self.recover(pathlib.Path(temp))
            handoff = json.loads((project.cognition_dir / lh.HANDOFF_NAME).read_text("utf-8"))
            running = [item for item in handoff["in_flight"] if item["id"] == "X2"]
            self.assertEqual(len(running), 1)
            self.assertTrue(running[0]["must_not_rerun"])
            self.assertTrue(running[0]["must_not_auto_close"])
            after = json.loads(project.state_path.read_text(encoding="utf-8"))
            self.assertEqual(next(x for x in after["experiments"] if x["id"] == "X2")["status"],
                             "running")


# ---------------------------------------------------------------------------
# Severe errors block the write and never trigger a rebuild
# ---------------------------------------------------------------------------

class TestSevereErrorsBlockWriteback(unittest.TestCase):

    def test_an_invalid_state_blocks_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            state = lh._legacy_state()
            state["claims"][0]["supporting_evidence"] = ["E404"]
            project = Project(pathlib.Path(temp), state=state)
            before = project.snapshot()
            code, _ = quiet(lh._take, project.state_path, project.root)
            self.assertEqual(code, lh.EXIT_HARD)
            self.assertFalse(project.cognition_dir.exists())
            self.assertEqual(project.snapshot(), before)

    def test_no_replacement_state_is_created(self):
        with tempfile.TemporaryDirectory() as temp:
            state = lh._legacy_state()
            state["claims"][0]["supporting_evidence"] = ["E404"]
            project = Project(pathlib.Path(temp), state=state)
            quiet(lh._take, project.state_path, project.root)
            states = sorted(project.route_dir.glob("*.json"))
            self.assertEqual([path.name for path in states], [cg.STATE_NAME])

    def test_a_stale_scheduler_blocks_the_takeover(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            project.add_scheduler(version=3)
            code, _ = quiet(lh._take, project.state_path, project.root)
            self.assertEqual(code, lh.EXIT_HARD)
            self.assertFalse(project.cognition_dir.exists())

    def test_a_corrupt_existing_index_blocks_rather_than_being_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            quiet(lh._take, project.state_path, project.root)
            index_path = project.cognition_dir / cg.INDEX_NAME
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["mechanisms"] = []
            index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
            payload = index_path.read_bytes()
            code, _ = quiet(lh._take, project.state_path, project.root)
            self.assertEqual(code, lh.EXIT_HARD)
            self.assertEqual(index_path.read_bytes(), payload)

    def test_an_implemented_higher_history_version_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            history = project.route_dir / "history"
            history.mkdir()
            (history / "state-v9.json").write_text(json.dumps({"state_version": 9}),
                                                   encoding="utf-8")
            audit = lh.compatibility_audit(project.state_path, project.root)
            self.assertIn("LH3", {f.rule for f in audit["findings"]})
            self.assertTrue(audit["blocking"])


# ---------------------------------------------------------------------------
# Bootstrap guard and detection
# ---------------------------------------------------------------------------

class TestBootstrapGuard(unittest.TestCase):

    def test_an_existing_state_forbids_a_fresh_bootstrap(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            detection = lh.detect(project.state_path)
            self.assertTrue(detection["initialized"])
            self.assertTrue(detection["bootstrap_forbidden"])
            self.assertEqual(quiet(lh._guard_bootstrap, project.state_path)[0], lh.EXIT_HARD)

    def test_a_missing_state_allows_bootstrap(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = pathlib.Path(temp) / "routes" / "A" / cg.STATE_NAME
            detection = lh.detect(missing)
            self.assertFalse(detection["initialized"])
            self.assertFalse(detection["bootstrap_forbidden"])

    def test_detection_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp))
            before = project.snapshot()
            lh.detect(project.state_path)
            self.assertEqual(project.snapshot(), before)


# ---------------------------------------------------------------------------
# The shipped fixture is a real legacy project
# ---------------------------------------------------------------------------

class TestShippedFixtureIsTakeable(unittest.TestCase):

    def test_taking_over_the_shipped_state_without_its_revision_log(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            project = Project(root, state=json.loads(
                (FIXTURES / "state.json").read_text(encoding="utf-8")))
            self.assertFalse(project.cognition_dir.exists())
            code, stdout = quiet(lh._take, project.state_path, project.root)
            self.assertEqual(code, lh.EXIT_OK, stdout)
            index = json.loads((project.cognition_dir / cg.INDEX_NAME).read_text("utf-8"))
            self.assertGreater(index["counts"]["legacy_mechanisms"], 0)
            self.assertGreater(index["counts"]["competitions"], 0)
            self.assertGreater(index["counts"]["anomalies"], 0)
            self.assertGreater(index["counts"]["boundaries"], 0)

    def test_a_project_with_an_existing_cognitive_layer_is_still_takeable(self):
        """The takeover rebuilds the projection with the same inputs the builder used.

        Before this was fixed, a project holding insight cards or a `scheduler.json` looked
        like index drift (`LH12`) and the takeover refused a healthy project — the projection
        was inconsistent, not the project.
        """
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp), state=json.loads(
                (FIXTURES / "state.json").read_text(encoding="utf-8")))
            project.add_scheduler(version=5)
            project.cognition_dir.mkdir(parents=True, exist_ok=True)
            for name in (cg.REVISIONS_NAME, pc.INSIGHT_CARDS_NAME):
                shutil.copy(FIXTURES / name, project.cognition_dir / name)
            self.assertEqual(quiet(cg.op_build, project.state_path,
                                   project.cognition_dir)[0], cg.EXIT_OK)
            stored = json.loads((project.cognition_dir / cg.INDEX_NAME).read_text("utf-8"))
            self.assertEqual(len(stored["insights"]), 1)
            code, output = quiet_all(lh._take, project.state_path, project.root)
            self.assertEqual(code, lh.EXIT_OK, output[-400:])
            rebuilt = json.loads((project.cognition_dir / cg.INDEX_NAME).read_text("utf-8"))
            self.assertEqual(len(rebuilt["insights"]), 1)
            self.assertEqual(rebuilt["digest"], stored["digest"])
            # And the written context brief still matches the index it was built from.
            self.assertEqual(quiet(cg.op_check, project.state_path,
                                   project.cognition_dir)[0], cg.EXIT_OK)

    def test_a_legacy_warning_does_not_block_or_break_idempotence(self):
        """The self-lock: a takeover wrote an index that made the next takeover refuse.

        A pre-`criterion` project derives a competition it cannot decide (`CM10`). The first
        takeover has no index to validate, so it succeeds and writes one carrying that
        diagnostic; escalating the diagnostic to a blocking `LH12` made every later takeover —
        including the idempotence check — fail on the project's own healthy output.
        """
        import test_cognition as tc
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp), state=tc.legacy_project_state())
            code, output = quiet_all(lh._take, project.state_path, project.root)
            self.assertEqual(code, lh.EXIT_OK, output[-400:])
            first = {name: (project.cognition_dir / name).read_bytes()
                     for name in lh.OWNED_FILES}
            index = json.loads((project.cognition_dir / cg.INDEX_NAME).read_text("utf-8"))
            self.assertTrue(any(item["rule"] == "CM10" for item in index["diagnostics"]),
                            "the fixture no longer produces CM10")
            code, output = quiet_all(lh._take, project.state_path, project.root)
            self.assertEqual(code, lh.EXIT_OK, output[-400:])
            second = {name: (project.cognition_dir / name).read_bytes()
                      for name in lh.OWNED_FILES}
            self.assertEqual(first, second)
            audit = lh.compatibility_audit(project.state_path, project.root)
            self.assertFalse(audit["blocking"])
            self.assertFalse([f for f in audit["findings"]
                              if f.rule == "LH12" and f.severity == lh.BLOCKING])

    def test_a_warning_diagnostic_is_never_escalated_to_blocking_lh12(self):
        """`LH12` blocks on drift. A documented warning must stay a warning."""
        import test_cognition as tc
        from unittest import mock
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp), state=tc.legacy_project_state())
            project.cognition_dir.mkdir(parents=True, exist_ok=True)
            (project.cognition_dir / cg.INDEX_NAME).write_text("{}", encoding="utf-8")
            warning = cg.Diagnostic("CM10", "competitions[LCP-C1]",
                                    "历史竞争无法判定区分力：X1:O1 没有可判定判据")
            with mock.patch.object(cg, "validate_index", return_value=[warning]):
                audit = lh.compatibility_audit(project.state_path, project.root)
            lh12 = [finding for finding in audit["findings"] if finding.rule == "LH12"]
            self.assertEqual([finding.severity for finding in lh12], [lh.WARNING])
            self.assertIn("legacy 提示", lh12[0].detail)

    def test_genuine_index_drift_still_blocks_the_takeover(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp), state=json.loads(
                (FIXTURES / "state.json").read_text(encoding="utf-8")))
            project.add_scheduler(version=5)
            project.cognition_dir.mkdir(parents=True, exist_ok=True)
            for name in (cg.REVISIONS_NAME, pc.INSIGHT_CARDS_NAME):
                shutil.copy(FIXTURES / name, project.cognition_dir / name)
            quiet(cg.op_build, project.state_path, project.cognition_dir)
            index_path = project.cognition_dir / cg.INDEX_NAME
            tampered = json.loads(index_path.read_text("utf-8"))
            tampered["mechanisms"] = []
            index_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
            code, output = quiet_all(lh._take, project.state_path, project.root)
            self.assertEqual(code, lh.EXIT_HARD)
            self.assertIn("LH12", output)

    def test_the_fixture_state_still_passes_the_canonical_gate_after_takeover(self):
        import state_check as sc
        with tempfile.TemporaryDirectory() as temp:
            project = Project(pathlib.Path(temp), state=json.loads(
                (FIXTURES / "state.json").read_text(encoding="utf-8")))
            before = project.state_path.read_bytes()
            quiet(lh._take, project.state_path, project.root)
            self.assertEqual(project.state_path.read_bytes(), before)
            report = sc.check_state(json.loads(project.state_path.read_text(encoding="utf-8")))
            self.assertTrue(report.ok, [v.render() for v in report.all_violations()])


if __name__ == "__main__":
    unittest.main()
