#!/usr/bin/env python3
"""test_domain_replay_pack.py — the replay evaluation interface (v2.0.1 §11).

The shipped packs are structural fixtures distilled from the CT-FM and Wave-TOF task
descriptions; running them exercises the harness and the domain machinery. They are
NOT real project histories and prove nothing about research effectiveness
(L3 NOT YET VALIDATED until a blinded real-project A/B).
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import domain_replay as dr

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKS = ROOT / "examples" / "domain" / "mri-reconstruction"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "domain_replay.py"),
                           *map(str, args)], capture_output=True, text=True,
                          cwd=str(ROOT))


class TestPackSchema(unittest.TestCase):

    def test_shipped_packs_are_valid(self):
        packs, problems = dr.load_packs(PACKS)
        self.assertEqual(problems, [], problems)
        self.assertEqual(len(packs), 4)
        tasks = {pack["task"] for pack in packs}
        self.assertEqual(tasks, {"cross_domain_generative_prior", "wave_3d_structure"})

    def test_every_pack_declares_hidden_materials(self):
        """防泄漏：每个 pack 必须声明 hidden_after，作为盲化审计依据。"""
        packs, problems = dr.load_packs(PACKS)
        self.assertEqual(problems, [])
        for pack in packs:
            self.assertTrue(pack.get("hidden_after"), pack["decision_point"])
            self.assertTrue(pack.get("visible"), pack["decision_point"])

    def test_an_invalid_pack_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            bad = pathlib.Path(temp) / "bad.json"
            bad.write_text(json.dumps({"task": "wave_3d_structure"}),
                           encoding="utf-8")
            _packs, problems = dr.load_packs(pathlib.Path(temp))
            self.assertTrue(any("schema" in p or "hidden_after" in p
                                for p in problems), problems)


class TestRunner(unittest.TestCase):

    def test_all_shipped_packs_behave(self):
        reports, ok = dr.run(PACKS)
        self.assertTrue(ok, json.dumps(reports, ensure_ascii=False)[:400])
        behaviours = {report["pack"]: report["behaviour"] for report in reports}
        # the repeated-noise probes are recognised as repeats, not re-dispatched
        repeated = [behaviour for behaviour in behaviours.values()
                    if behaviour == "REPEATED_ATTRIBUTION"]
        self.assertEqual(len(repeated), 3, behaviours)

    def test_a_fallback_probe_is_caught(self):
        """Agent 复现平凡归因回退时，运行器必须给出失败行为判定。"""
        packs, _ = dr.load_packs(PACKS)
        pack = copy_pack(packs[0])
        pack["visible"]["prior_declarations"] = []
        pack["expected"]["allow"] = ["INSUFFICIENT_EVIDENCE"]
        verdict = dr.run_pack(pack)
        self.assertEqual(verdict["behaviour"], "NOVEL_DECISION_RELEVANT_DIAGNOSIS")

    def test_cli_run_and_validate(self):
        proc = run_cli("validate", "--pack", str(PACKS))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc = run_cli("run", "--pack", str(PACKS))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("NOT YET VALIDATED", proc.stdout)
        self.assertIn("PASS", proc.stdout)

    def test_cli_reports_failure_for_a_misbehaving_pack(self):
        with tempfile.TemporaryDirectory() as temp:
            packs, _ = dr.load_packs(PACKS)
            pack = copy_pack(packs[0])
            pack["expected"] = {"no_fallbacks": ["noise_level"],
                                "allow": ["PHYSICAL_LIMIT_WITH_SCOPE"]}
            (pathlib.Path(temp) / "misbehaving.json").write_text(
                json.dumps(pack, ensure_ascii=False), encoding="utf-8")
            proc = run_cli("run", "--pack", temp)
            self.assertEqual(proc.returncode, 3, proc.stdout)
            self.assertIn("FAIL", proc.stdout)


def copy_pack(pack: dict) -> dict:
    import copy
    return copy.deepcopy(pack)


class TestSelftest(unittest.TestCase):

    def test_module_selftest_passes(self):
        proc = run_cli("--selftest")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("[ok] domain_replay selftest", proc.stdout)


if __name__ == "__main__":
    unittest.main()
