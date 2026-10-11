#!/usr/bin/env python3
"""test_research_continuity.py — 跨轮/跨会话的产物交接验收。

每个「轮次」都**从磁盘重新加载** state 与产物（不靠内存对象传递），并对独立轮次调用
`resolve_artifacts` / `transition` / `loop_step`。测试证明的是**交接真的发生**，不是函数返回了
某个字符串。执行边界（预算/GPU/预注册）必须保持，且不得把「已计划」当成「已执行」。
"""

from __future__ import annotations

import copy
import json
import pathlib
import tempfile
import unittest

import cognition as cg
import insight_to_method as i2m
import legacy_handoff as lh
import preset_router as pr
import test_insight_to_method as shared
import test_state_check as fixture

HID = "H42"


class ContinuityCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.route = pathlib.Path(self.temp.name) / "A"
        self.route.mkdir(parents=True)
        self.state_path = self.route / cg.STATE_NAME
        self.state_path.write_text(json.dumps(shared.base_state()[0], ensure_ascii=False),
                                   encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def reload(self):
        """A fresh load from disk — the only thing a new iteration may rely on."""
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def next_step(self):
        return i2m.resolve_artifacts(self.reload(), self.route, HID)["next_step"]

    def write(self, kind, payload):
        state = self.reload()
        return i2m.write_artifact(self.route, kind, HID, payload,
                                  basis=i2m.hypothesis_basis(state, HID),
                                  state_version=state.get("state_version"))


class TestI2MHandoff(ContinuityCase):
    def test_scenario_1_full_handoff_advances_without_repeating_a_stage(self):
        self.assertEqual(self.next_step(), "sketch")                      # round 0
        self.write("sketch", {"problem": "p", "insight": "i", "intervention": "a",
                              "falsifier": "f"})
        self.assertEqual(self.next_step(), "synthesis")                   # round 1: no repeat
        step = i2m.transition(self.reload(), insight=shared.insight(), route_dir=self.route,
                              hypothesis_id=HID)
        self.assertEqual(step["stage"], "synthesis")
        simple = shared.candidate("M-simple", "objective", "a", "L1",
                                  minimal_implementation_complexity="low",
                                  why_not_simpler="w", decisive_experiment="d",
                                  importance_reason="r")
        heavy = shared.candidate("M-heavy", "architecture", "b", "L2",
                                 minimal_implementation_complexity="high")
        step = i2m.transition(self.reload(), insight=shared.insight(),
                              candidates=[heavy, simple], route_dir=self.route,
                              hypothesis_id=HID)                          # round 2
        self.assertEqual(step["stage"], "contract")
        self.assertEqual(step["i2m"]["candidate_id"], "M-simple")
        self.assertEqual(self.next_step(), "contract")                    # round 3: recovered
        state = self.reload()
        archived = i2m._index(state, "hypotheses")[HID]
        statuses = i2m.resolve_artifacts(state, self.route, HID)["artifacts"]
        self.assertEqual(statuses["candidates"]["status"], "present")
        self.assertIn(archived.get("status"), ("active", "candidate", "elite", None))

    def test_scenario_2_session_restart_resumes_without_bootstrap_or_repeat(self):
        self.write("sketch", {"problem": "p", "insight": "i", "intervention": "a",
                              "falsifier": "f"})
        self.write("candidates", {"candidates": [shared.candidate(
            "M-simple", "objective", "a", "L1", single_candidate_justification="唯一自然干预",
            minimal_implementation_complexity="low")]})
        # a completely fresh process only sees the files
        decision = lh.resume_decision(self.state_path)
        self.assertIn("Research Resume", decision["route"])
        self.assertTrue(decision["bootstrap_forbidden"])
        self.assertEqual(decision["handoff_record"], None)      # missing report != damaged state
        self.assertEqual(self.next_step(), "contract")
        step = i2m.loop_step(self.reload(), {"state_version": self.reload()["state_version"],
                                             "next_actions": [], "eig_calibration": {"records": []}},
                             route_dir=self.route)
        self.assertNotEqual(step.get("stage"), "sketch")

    def test_scenario_4_a_refuted_basis_invalidates_the_artifact(self):
        self.write("sketch", {"problem": "p", "insight": "i", "intervention": "a",
                              "falsifier": "f"})
        state = self.reload()
        state["hypotheses"][0]["statement"] = "被反证的旧机制"      # basis changes
        self.state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        resolution = i2m.resolve_artifacts(self.reload(), self.route, HID)
        self.assertEqual(resolution["artifacts"]["sketch"]["status"], "stale")
        self.assertEqual(resolution["next_step"], "sketch")         # redesign, not reuse
        self.assertTrue(pathlib.Path(resolution["artifacts"]["sketch"]["path"]).is_file(),
                        "the stale artifact is kept for audit")

    def test_scenario_5_a_well_justified_single_candidate_completes_the_handoff(self):
        self.write("sketch", {"problem": "p", "insight": "i", "intervention": "a",
                              "falsifier": "f"})
        solo = shared.candidate("M-solo", "objective", "a", "L1",
                                single_candidate_justification="机制只指向一种自然干预",
                                minimal_implementation_complexity="high")
        step = i2m.transition(self.reload(), insight=shared.insight(), candidates=[solo],
                              route_dir=self.route, hypothesis_id=HID)
        self.assertEqual(step["stage"], "contract")
        self.assertEqual(step["i2m"]["candidate_id"], "M-solo")
        self.assertFalse(step["i2m"]["synthesis"]["taste"]["compared"])

    def test_scenario_6_handoff_never_implies_execution(self):
        self.write("sketch", {"problem": "p", "insight": "i", "intervention": "a",
                              "falsifier": "f"})
        state = self.reload()
        plan = dict(shared.MINIMAL_PLAN, gpu_required=True)
        self.assertIn("I2M51", i2m._rules(i2m.minimal_test_errors(state, plan)))
        self.assertIn("I2M52", i2m._rules(i2m.minimal_test_errors(
            state, plan, gate={"status": "HOLD", "errors": ["PEIG"]})))
        step = i2m.transition(state, insight=shared.insight(), route_dir=self.route,
                              hypothesis_id=HID)
        self.assertFalse(step.get("dispatched", False))
        self.assertNotIn(step.get("stage"), ("dispatched", "executed"))

    def test_writing_the_same_artifact_twice_is_idempotent(self):
        payload = {"candidates": [shared.candidate("M1", "objective", "a", "L1")]}
        first = self.write("candidates", payload)
        second = self.write("candidates", payload)
        self.assertTrue(first["written"])
        self.assertFalse(second["written"])
        self.assertEqual(second["status"], "UNCHANGED")
        self.assertEqual(len(list(i2m.methods_dir(self.route).glob("candidates-*.json"))), 1)

    def test_an_unknown_schema_is_reported_not_guessed(self):
        path = i2m.methods_dir(self.route) / f"sketch-{HID}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"_schema": "something/else@9"}), encoding="utf-8")
        self.assertEqual(i2m.read_artifact(self.route, HID, "sketch")["status"], "unsupported")
        self.assertEqual(self.next_step(), "sketch")


class TestEntryClassification(ContinuityCase):
    def test_no_state_is_bootstrap(self):
        missing = self.route / "nope.json"
        self.assertIn("Bootstrap", lh.resume_decision(missing)["route"])

    def test_a_valid_state_is_research_resume_even_after_a_version_bump(self):
        state = self.reload()
        state["state_version"] = state.get("state_version", 1) + 7
        self.state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        decision = lh.resume_decision(self.state_path)
        self.assertIn("Research Resume", decision["route"])
        self.assertIn("state_version", decision["note"])

    def test_a_missing_report_is_not_a_damaged_state(self):
        decision = lh.resume_decision(self.state_path)
        self.assertIn("Research Resume", decision["route"])
        self.assertIsNone(decision["handoff_record"])

    def test_a_corrupt_state_goes_to_recover_not_bootstrap(self):
        self.state_path.write_text("{not json", encoding="utf-8")
        decision = lh.resume_decision(self.state_path)
        self.assertIn("Recover/HOLD", decision["route"])
        self.assertNotIn("Bootstrap", decision["route"])

    def test_legacy_history_without_a_handoff_record_needs_a_cold_handoff(self):
        # route history is what marks a project as legacy-and-unhanded (not the state version)
        history = self.route / "history"
        history.mkdir(parents=True, exist_ok=True)
        (history / "0001.json").write_text(json.dumps({"state_version": 1}), encoding="utf-8")
        decision = lh.resume_decision(self.state_path)
        self.assertIn("Cold Handoff", decision["route"])
        self.assertTrue(decision["bootstrap_forbidden"])

    def test_a_valid_handoff_record_resumes(self):
        history = self.route / "history"
        history.mkdir(parents=True, exist_ok=True)
        (history / "0001.json").write_text(json.dumps({"state_version": 1}), encoding="utf-8")
        cognition_dir = self.route / cg.COGNITION_DIRNAME
        cognition_dir.mkdir(parents=True, exist_ok=True)
        (cognition_dir / lh.HANDOFF_NAME).write_text(
            json.dumps({"_schema": lh.SCHEMA_HANDOFF}), encoding="utf-8")
        decision = lh.resume_decision(self.state_path)
        self.assertIn("Research Resume", decision["route"])

    def test_normal_continuation_does_not_run_a_full_handoff(self):
        """The loop path must not re-audit compatibility every wake-up."""
        import inspect
        source = inspect.getsource(pr._loop_step)
        self.assertNotIn("compatibility_audit", source)
        self.assertNotIn("legacy_handoff", source)


if __name__ == "__main__":
    unittest.main()
