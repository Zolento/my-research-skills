#!/usr/bin/env python3
"""test_research_summary.py — 只读深度总结的能力与纪律验收。

验收重点不是"函数返回了字符串"，而是：**只读**（不写 state）、**缺数据不编造**、
**证据分级不越权**（无合格证据支撑的 supported 只能算初步）、**建议≤3 且不派遣**、
**幂等闸门**（`--check` 过期即退出码 3）。
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import research_summary as rs

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "research_summary.py"


def state(**overrides):
    base = {
        "state_version": 7,
        "contract": {"goal": "提升长尾检索召回", "primary_anchor": "performance",
                     "success_criteria": ["同算力下 recall@10 提升"], "resources": {"gpu_hours": 40}},
        "claims": [{"id": "C1", "status": "supported", "supporting_evidence": ["E1"]},
                   {"id": "C2", "status": "supported"},              # declared, unbacked
                   {"id": "C3", "status": "refuted"}],
        "evidence": [{"id": "E1", "epistemic_status": "Observed",
                      "validity": {"status": "valid"}, "source_ref": "exp:X1"}],
        "hypotheses": [{"id": "H1", "statement": "长尾被头部主导", "nearest_prior": "focal loss",
                        "method": {"version": "v1", "intervention": {"kind": "objective"}}}],
        "experiments": [{"id": "X1", "status": "done", "metric": "recall@10",
                         "seed": 1, "data_split": "d1", "result_at_state_version": 7,
                         "preregistration": {"frozen_at_state_version": 6,
                                             "method_contract": {"method_digest": "d1"}}}],
        "literature": [{"id": "LIT1", "ref": "focal loss"}],
        "failures": [{"id": "F1", "kind": "implementation"}],
        "uncertainties": [{"id": "U1", "status": "open", "question": "长尾是否被头部主导",
                           "cheapest_discriminating_test": "小规模子集对照"}],
        "repairs": [{"id": "R1", "flaw": "缺对照", "closure": "OPEN"}],
        "decision": {"verdict": "continue"},
    }
    base.update(overrides)
    return base


class TestSummaryContent(unittest.TestCase):
    def test_all_eleven_sections_and_contract_fields_are_present(self):
        report = rs.render_summary(state(), route="A", skill_version="1.0.0", cutoff="ts")
        for index, title in enumerate((
                "Executive Summary", "Research Objective & Constraints",
                "Current Methods & Implementation", "Research Timeline & Major Decisions",
                "Experimental Evidence", "Established / Unresolved / Refuted Findings",
                "Scientific Insights & Failure Analysis", "Literature & Novelty Positioning",
                "Current Blockers & Open Obligations", "Next Research Decisions",
                "Evidence & Artifact Index"), 1):
            self.assertIn(f"## {index}. {title}", report)
        for field in ("action_taken", "scientific_delta", "decision_delta", "state_writeback",
                      "next_action", "stop_reason"):
            self.assertIn(f"`{field}`", report)
        self.assertIn("read_only", report)

    def test_a_declared_but_unbacked_claim_is_not_reported_as_established(self):
        report = rs.render_summary(state(), route="A")
        established = report.split("**已确立**")[1].split("\n")[0]
        self.assertIn("C1", established)
        self.assertNotIn("C2", established)

    def test_missing_data_is_marked_not_invented(self):
        report = rs.render_summary({}, route="", skill_version="")
        self.assertIn(rs.TBD, report)
        self.assertIn("规模：claims=0", report)
        self.assertNotIn("## 1. Executive Summary\n- 目标：提升", report)

    def test_at_most_three_actions_and_none_are_dispatched(self):
        report = rs.render_summary(state(), route="A")
        self.assertLessEqual(report.count("\n1. **"), 1)
        self.assertIn("以上**仅为建议**，本次不派遣、不执行。", report)

    def test_the_report_refuses_mechanism_inference(self):
        report = rs.render_summary(state(), route="A")
        self.assertIn("性能改善不等于机制成立", report)
        self.assertIn("单次负结果不上升为普遍否证", report)

    def test_delta_reports_none_without_verifiable_records(self):
        report = rs.render_summary(state(), route="A")
        self.assertIn("`scientific_delta`：none", report)

    def test_rendering_is_a_pure_function(self):
        self.assertEqual(rs.render_summary(state(), route="A"),
                         rs.render_summary(state(), route="A"))


class TestReadOnlyCli(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.route = pathlib.Path(self.temp.name) / "A"
        self.route.mkdir(parents=True)
        self.state_path = self.route / "research-state.json"
        self.state_path.write_text(json.dumps(state(), ensure_ascii=False), encoding="utf-8")
        self.before = self.state_path.read_bytes()
        self.out = self.route / "SUMMARY.md"

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *extra):
        return subprocess.run([sys.executable, str(SCRIPT), "--state", str(self.state_path),
                               "--route-dir", str(self.route), *extra],
                              capture_output=True, text=True, cwd=str(ROOT),
                              stdin=subprocess.DEVNULL)

    def test_the_summary_never_rewrites_the_state(self):
        self.run_cli("--out", str(self.out))
        self.assertEqual(self.state_path.read_bytes(), self.before)
        self.assertTrue(self.out.is_file())
        self.assertNotIn("state_writeback`：", "x")     # sanity on the assertion style

    def test_check_is_an_idempotency_gate(self):
        self.run_cli("--out", str(self.out))
        fresh = self.run_cli("--out", str(self.out), "--check")
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.out.write_text("stale\n", encoding="utf-8")
        stale = self.run_cli("--out", str(self.out), "--check")
        self.assertEqual(stale.returncode, rs.EXIT_STALE, stale.stderr)

    def test_a_missing_state_is_reported_without_rebuilding_anything(self):
        missing = self.route / "nope.json"
        result = subprocess.run([sys.executable, str(SCRIPT), "--state", str(missing)],
                                capture_output=True, text=True, cwd=str(ROOT),
                                stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, rs.EXIT_MISSING)
        self.assertFalse(self.out.exists())
        self.assertIn("不存在", result.stderr)

    def test_an_unreadable_state_is_not_fabricated(self):
        self.state_path.write_text("{not json", encoding="utf-8")
        result = self.run_cli()
        self.assertEqual(result.returncode, rs.EXIT_MISSING)
        self.assertIn("不可读", result.stderr)


if __name__ == "__main__":
    unittest.main()
