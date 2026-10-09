#!/usr/bin/env python3
"""test_decision_trajectory.py — Skill-RSI Phase 2 acceptance.

The failure modes under test are the ones that make long-horizon policy learning
unsound: a bounded telemetry ring silently standing in for history, a decision being
rewritten once its result is known, a prediction written after the outcome, stale state
accepted as "visible information", and a trajectory leaking into canonical evidence.

Every test uses real `research-state.json` objects and the real adapter output; a JSON
file that merely parses is not a pass.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import cognition as cg
import decision_trajectory as dt
import strategy_memory as sm

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "decision_trajectory.py"


def clone(value):
    return json.loads(json.dumps(value))


def fixture_state(version=3):
    return {
        "_schema": "research-idea-pipeline/research-state@1",
        "state_version": version,
        "contract": {"goal": "g", "primary_anchor": "A0", "constraints": [], "resources": {},
                     "out_of_scope": []},
        "claims": [{"id": "C1", "statement": "s", "status": "ungrounded"}],
        "evidence": [{"id": "E1", "kind": "experiment", "supports": ["C1"], "strength": "weak",
                      "scope": "s", "epistemic_status": "grounded", "source_ref": "fixture",
                      "verification_tier": "T0", "validity": "valid"}],
        "assumptions": [],
        "hypotheses": [{"id": "H1", "statement": "h", "status": "active", "validity": "valid",
                        "island": "P1", "operator": "reframe"}],
        "experiments": [], "literature": [], "failures": [],
        "uncertainties": [{"id": "U1", "question": "q", "importance": "high",
                           "uncertainty": "high", "status": "open", "validity": "valid"}],
        "assurance": [], "repairs": [], "narrative_view": {}, "reviews": [],
        "decision": {"verdict": "continue", "rationale": "", "next_phase": "R3"},
    }


def decision_record(state, chosen="H1", at="2026-01-01T00:00:00Z",
                    dispatch_status="not_dispatched"):
    context = dt.build_context(state, scientific_question="q", active_hypotheses=["H1"],
                               key_uncertainties=["U1"], visible_evidence=["E1"],
                               decided_at=at, scheduler={"next_actions": [{"action": "H1"}]})
    return dt.build_decision_record(
        state, route="A", project="fixture", context=context,
        candidates=[{"action": "H1", "type": "repair", "target": "H1", "eig": "high",
                     "cost": "low"},
                    {"action": "H2", "type": "discriminating_experiment", "target": "U1",
                     "eig": "high", "cost": "low"}],
        chosen=chosen, scheduler_priority={"level": 4, "label": "high_information_gain_test"},
        dispatch_status=dispatch_status, recorded_at=at)


class TestTrajectoryArtefacts(unittest.TestCase):
    def test_decision_round_trips_and_rebuilds(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            record = decision_record(state)
            result = dt.append_record(path, record, state=state, route="A")
            self.assertEqual(result["status"], "APPENDED", result)
            records, diagnostics = dt.load_records(path)
            self.assertEqual(diagnostics, [])
            views = dt.rebuild_trajectories(records)
            view = views[record["trajectory_id"]]
            self.assertEqual(view["decision"]["decision"]["chosen"], "H1")
            self.assertEqual(view["decision"]["context"]["state_version"], 3)
            self.assertEqual(dt.rebuild_trajectories(records), views)

    def test_idempotent_resubmission_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            record = decision_record(state)
            self.assertEqual(dt.append_record(path, record, state=state, route="A")["status"],
                             "APPENDED")
            before = path.read_bytes()
            again = dt.append_record(path, record, state=state, route="A")
            self.assertEqual(again["status"], "DUPLICATE")
            self.assertFalse(again["written"])
            self.assertEqual(path.read_bytes(), before)

    def test_a_later_result_cannot_rewrite_an_earlier_decision(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            record = decision_record(state)
            dt.append_record(path, record, state=state, route="A")
            rewritten = clone(record)
            rewritten["decision"]["chosen"] = "H2"
            outcome = dt.append_record(path, rewritten, state=state, route="A")
            self.assertEqual(outcome["status"], "INVALID")
            self.assertIn("DT2", outcome["codes"])

    def test_stale_state_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            live = fixture_state(version=3)
            stale = fixture_state(version=2)
            result = dt.append_record(path, decision_record(stale), state=live, route="A")
            self.assertEqual(result["status"], "INVALID")
            self.assertIn("DT4", result["codes"])

    def test_outcome_cannot_precede_its_decision(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            record = decision_record(state, at="2026-01-05T00:00:00Z")
            dt.append_record(path, record, state=state, route="A")
            outcome = dt.build_outcome_record(
                record["trajectory_id"], at_state_version=3,
                result={"kind": "experiment_result", "summary": "observed value 0.42"},
                evidence_refs=[{"evidence": "E1"}], decision_delta="decision",
                evidence_qualification="qualified", observed_at="2026-01-01T00:00:00Z")
            result = dt.append_record(path, outcome, state=state, route="A")
            self.assertEqual(result["status"], "INVALID")
            self.assertIn("DT4", result["codes"])

    def test_post_hoc_prediction_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            record = decision_record(state)
            ident = record["trajectory_id"]
            dt.append_record(path, record, state=state, route="A")
            dt.append_record(path, dt.build_outcome_record(
                ident, at_state_version=3,
                result={"kind": "experiment_result", "summary": "observed value 0.42"},
                evidence_refs=[{"evidence": "E1"}], decision_delta="decision",
                evidence_qualification="qualified", observed_at="2026-01-02T00:00:00Z"),
                state=state, route="A")
            prediction = {"_schema": dt.SCHEMA_TRAJECTORY, "record": "prediction",
                          "trajectory_id": ident, "recorded_at": "2026-01-03T00:00:00Z",
                          "question": "q", "distinguishable_predictions": ["p"],
                          "project": "fixture", "route": "A"}
            result = dt.append_record(path, prediction, state=state, route="A")
            self.assertEqual(result["status"], "INVALID")
            self.assertIn("DT5", result["codes"])

    def test_outcome_leakage_into_the_frozen_decision_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            record = decision_record(state)
            ident = record["trajectory_id"]
            dt.append_record(path, record, state=state, route="A")
            # The decision's frozen context already contains the future result text.
            records, _ = dt.load_records(path)
            leaked = dt.build_outcome_record(
                ident, at_state_version=3,
                result={"kind": "experiment_result",
                        "summary": "the frozen context contains this exact later text"},
                evidence_refs=[{"evidence": "E1"}], decision_delta="decision",
                evidence_qualification="qualified", observed_at="2026-01-02T00:00:00Z")
            leaked_decision = clone(record)
            leaked_decision["context"]["extra_note"] = \
                "the frozen context contains this exact later text"
            tampered_log = [leaked_decision, leaked]
            diagnostics = dt.record_errors(leaked, state=state, records=tampered_log)
            self.assertTrue(any(item.rule == "DT6" for item in diagnostics), diagnostics)

    def test_unknown_source_reference_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            record = decision_record(state)
            record["context"]["visible_evidence"] = ["E99"]
            # state_digest no longer matches once the context changes, so rebuild both.
            result = dt.append_record(path, record, state=state, route="A")
            self.assertEqual(result["status"], "INVALID")
            self.assertIn("DT3", result["codes"])

    def test_unqualified_evidence_cannot_claim_a_scientific_delta(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            record = decision_record(state)
            dt.append_record(path, record, state=state, route="A")
            outcome = dt.build_outcome_record(
                record["trajectory_id"], at_state_version=3,
                result={"kind": "experiment_result", "summary": "engineer error 0x1"},
                evidence_refs=[{"evidence": "E1"}], scientific_delta="scientific",
                evidence_qualification="unqualified", observed_at="2026-01-02T00:00:00Z")
            result = dt.append_record(path, outcome, state=state, route="A")
            self.assertEqual(result["status"], "INVALID")
            self.assertIn("DT9", result["codes"])

    def test_tampered_history_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            dt.append_record(path, decision_record(state), state=state, route="A")
            lines = path.read_text(encoding="utf-8").splitlines()
            line = json.loads(lines[0])
            line["decision"]["chosen"] = "H2"
            path.write_text(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n",
                            encoding="utf-8")
            with self.assertRaises(dt.TrajectoryError):
                dt.load_records(path)


class TestCrossSessionRecovery(unittest.TestCase):
    def test_a_second_session_rebuilds_the_same_trajectories(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            record = decision_record(state)
            ident = record["trajectory_id"]
            dt.append_record(path, record, state=state, route="A")
            dt.append_record(path, dt.build_outcome_record(
                ident, at_state_version=3,
                result={"kind": "experiment_result", "summary": "observed value 0.42"},
                evidence_refs=[{"evidence": "E1"}], decision_delta="decision",
                evidence_qualification="qualified", observed_at="2026-01-02T00:00:00Z"),
                state=state, route="A")
            dt.append_record(path, dt.build_learning_record(
                ident, learning_value=True, bias_hypothesis="cheap diagnostics preferred",
                applicability={"problem_structure": "reframe"},
                recorded_at="2026-01-03T00:00:00Z"), state=state, route="A")
            first, _ = dt.load_records(path)
            # A fresh process (a genuinely separate session) must read the same views.
            code = (
                "import json,pathlib,sys;sys.path.insert(0,%r);import decision_trajectory as dt;"
                "r,_=dt.load_records(pathlib.Path(%r));"
                "print(json.dumps(dt.rebuild_trajectories(r),sort_keys=True))"
                % (str(ROOT / "scripts"), str(path))
            )
            out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            second = json.loads(out.stdout)
            self.assertEqual(second, json.loads(json.dumps(dt.rebuild_trajectories(first),
                                                           sort_keys=True)))
            self.assertIn(ident, dt.support_ids(first))


class TestCanonicalStateIsUntouched(unittest.TestCase):
    def test_recording_never_mutates_the_canonical_state(self):
        with tempfile.TemporaryDirectory() as temp:
            route = pathlib.Path(temp) / "A"
            route.mkdir(parents=True)
            state_path = route / cg.STATE_NAME
            state = fixture_state()
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
            before = state_path.read_bytes()
            record = decision_record(state)
            dt.append_record(route / dt.TRAJECTORY_NAME, record, state=state, route="A")
            dt.append_record(route / dt.TRAJECTORY_NAME,
                             dt.build_outcome_record(
                                 record["trajectory_id"], at_state_version=3,
                                 result={"kind": "experiment_result",
                                         "summary": "observed value 0.42"},
                                 evidence_refs=[{"evidence": "E1"}],
                                 decision_delta="decision",
                                 evidence_qualification="qualified",
                                 observed_at="2026-01-02T00:00:00Z"),
                             state=state, route="A")
            self.assertEqual(state_path.read_bytes(), before)
            self.assertEqual(cg.canonical_json(cg.load_state(state_path)), cg.canonical_json(state))

    def test_a_trajectory_is_never_written_into_evidence(self):
        state = fixture_state()
        record = decision_record(state)
        self.assertNotIn("evidence", json.dumps(record["decision"]).lower())
        # The trajectory declares itself non-canonical and the loader never writes state.
        self.assertTrue(record.get("canonical_untouched"))


class TestRealAdapterConsumer(unittest.TestCase):
    """The record must be consumable by the real Strategy Decision Adapter output."""

    def _templates(self):
        state = json.loads((ROOT / "templates" / "research-state.template.json")
                           .read_text(encoding="utf-8"))
        scheduler = json.loads((ROOT / "templates" / "scheduler.template.json")
                               .read_text(encoding="utf-8"))
        # The shipped template's illustrative EIG record has no source receipt, so it is
        # not a PASS scheduler; a fresh project has an empty calibration table.
        scheduler["eig_calibration"] = {"note": "", "records": []}
        return state, scheduler

    def test_adapter_output_binds_into_a_trajectory(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state, scheduler = self._templates()
            decision = sm.strategy_decision(state, {}, scheduler, [])
            self.assertEqual(decision["hard_gates"]["scheduler_check"], "PASS", decision)
            self.assertTrue(decision.get("candidates_before"))
            context = dt.record_context(state, scheduler=scheduler)
            record = dt.build_decision_record(
                state, route="A", project="fixture", context=context,
                candidates=decision.get("candidates_before") or [],
                chosen=decision.get("chosen"),
                scheduler_priority={"level": 4, "label": "high_information_gain_test"},
                policy_version="strategy-memory", policy_changed_order=bool(
                    decision.get("decision_changed")),
                dispatch_status="not_dispatched")
            result = dt.append_record(path, record, state=state, route="A")
            self.assertEqual(result["status"], "APPENDED", result)
            view = dt.rebuild_trajectories(dt.load_records(path)[0])[record["trajectory_id"]]
            self.assertEqual(view["decision"]["decision"]["chosen"], decision["chosen"])
            self.assertEqual(len(view["decision"]["decision"]["candidates"]),
                             len(decision["candidates_before"]))
            self.assertEqual(view["decision"]["decision"]["dispatch_status"], "not_dispatched")

    def test_cli_show_and_validate(self):
        with tempfile.TemporaryDirectory() as temp:
            route = pathlib.Path(temp) / "A"
            route.mkdir(parents=True)
            state = fixture_state()
            (route / cg.STATE_NAME).write_text(
                json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            record = decision_record(state)
            record_path = pathlib.Path(temp) / "record.json"
            record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            opened = subprocess.run(
                [sys.executable, str(SCRIPT), "open", "--state", str(route / cg.STATE_NAME),
                 "--record", str(record_path)], capture_output=True, text=True)
            self.assertEqual(opened.returncode, 0, opened.stderr)
            validated = subprocess.run(
                [sys.executable, str(SCRIPT), "validate", "--state",
                 str(route / cg.STATE_NAME)], capture_output=True, text=True)
            self.assertEqual(validated.returncode, 0, validated.stderr)
            self.assertEqual(json.loads(validated.stdout)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()


class TestLatentBugRegressions(unittest.TestCase):
    """Regressions for defects that the first acceptance suite did not expose."""

    def test_concurrent_appends_keep_the_chain_contiguous(self):
        """The read that computed `seq` used to happen outside the lock: 8 writers produced
        duplicate sequence numbers and a broken hash chain."""
        import threading
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            errors = []

            def worker(index):
                record = decision_record(state, chosen=f"H{index}", at="2026-01-01T00:00:00Z")
                record["decision"]["candidates"] = [
                    {"action": f"H{index}", "type": "repair", "target": "H1", "eig": "high",
                     "cost": "low"}]
                try:
                    dt.append_record(path, record, state=state, route="A")
                except Exception as exc:  # pragma: no cover - failure path
                    errors.append(repr(exc))

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            records, diagnostics = dt.load_records(path)
            self.assertEqual(errors, [])
            self.assertEqual(diagnostics, [])
            self.assertEqual([item["seq"] for item in records], list(range(1, 9)))

    def test_the_same_dispatch_a_second_later_is_still_a_duplicate(self):
        """The identity used to include the wall clock, so a duplicate dispatch a second
        later received a new id and was accepted."""
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            first = decision_record(state, at="2026-01-01T00:00:00Z")
            second = decision_record(state, at="2026-01-01T00:05:00Z")
            self.assertEqual(first["trajectory_id"], second["trajectory_id"])
            self.assertEqual(dt.append_record(path, first, state=state, route="A")["status"],
                             "APPENDED")
            self.assertEqual(dt.append_record(path, second, state=state, route="A")["status"],
                             "DUPLICATE")
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1)

    def test_a_blank_line_does_not_look_like_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            dt.append_record(path, decision_record(state), state=state, route="A")
            lines = path.read_text(encoding="utf-8").splitlines()
            lines.insert(1, "")
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            records, diagnostics = dt.load_records(path)
            self.assertEqual(diagnostics, [])
            self.assertEqual(len(records), 1)

    def test_a_trajectory_artifact_cannot_be_cited_as_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            record = decision_record(state)
            dt.append_record(path, record, state=state, route="A")
            outcome = dt.build_outcome_record(
                record["trajectory_id"], at_state_version=3,
                result={"kind": "experiment_result", "summary": "observed value 0.42"},
                evidence_refs=[{"evidence": "E1", "source":
                                "<route>/decision-trajectory.jsonl"}],
                decision_delta="decision", evidence_qualification="qualified",
                observed_at="2026-01-02T00:00:00Z")
            result = dt.append_record(path, outcome, state=state, route="A")
            self.assertEqual(result["status"], "INVALID")
            self.assertIn("DT7", result["codes"])

    def test_a_renamed_duplicate_dispatch_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / dt.TRAJECTORY_NAME
            state = fixture_state()
            first = decision_record(state, dispatch_status="dispatched")
            dt.append_record(path, first, state=state, route="A")
            renamed = decision_record(state, at="2026-01-01T00:00:00Z")
            renamed["trajectory_id"] = "DT-forged-renamed-id"
            renamed["decision"]["dispatch_status"] = "dispatched"
            result = dt.append_record(path, renamed, state=state, route="A")
            self.assertEqual(result["status"], "INVALID")
            self.assertIn("DT8", result["codes"])
