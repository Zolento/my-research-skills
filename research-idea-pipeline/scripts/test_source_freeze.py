#!/usr/bin/env python3
"""test_source_freeze.py — Skill 源码冻结与写入守卫的对抗测试。

所有用例都在 `tempfile` 假的 skill 树上运行，**绝不触碰真实 Skill 源码**。
覆盖：确定性清单、篡改检测、受保护路径拒绝、`../` 与 symlink 越界、
允许范围放行、隐藏评测数据/发布元数据、canonical state、候选对抗扫描、
哈希链审计、`SourceFreeze` 的 HOLD 行为与只读部署的剩余风险声明。
"""

from __future__ import annotations

import hashlib
import pathlib
import tempfile
import unittest

import source_freeze as sf

ROOT = pathlib.Path(__file__).resolve().parent.parent

TREE = (
    "SKILL.md",
    "shared-contract.md",
    "preset-registry.json",
    "router-fixtures.json",
    "scripts/guard.py",
    "scripts/util.py",
    "presets/research-loop.md",
    "references/policy.md",
    "templates/research-state.template.json",
    "schemas/x.schema.json",
    ".dev/hidden-answer.md",
    "examples/demo.md",
)


def line_digest(line: str) -> str:
    return "sha256:" + hashlib.sha256(line.encode("utf-8")).hexdigest()


class SourceFreezeTest(unittest.TestCase):

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.base = pathlib.Path(self._temp.name)
        self.skill = self.base / "skill"
        for rel in TREE:
            path = self.skill / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {rel}\n", encoding="utf-8")
        self.route = (self.base / "project" / ".research-idea-pipeline"
                      / "routes" / "A")
        self.route.mkdir(parents=True)

    # 1 -------------------------------------------------------------------
    def test_manifest_is_deterministic_and_count_matches_protected_files(self):
        first = sf.manifest(self.skill)
        second = sf.manifest(self.skill)
        self.assertEqual(sf.canonical_json(first), sf.canonical_json(second))
        self.assertEqual(first["count"], len(sf.protected_files(self.skill)))
        self.assertEqual(first["schema"], sf.SCHEMA_MANIFEST)
        self.assertEqual(first["digest"], sf.digest_of(first["files"]))
        self.assertNotIn(".dev/hidden-answer.md", first["files"])
        self.assertNotIn("examples/demo.md", first["files"])
        self.assertIn("scripts/guard.py", first["files"])

    def test_write_manifest_is_atomic_and_load_round_trips(self):
        out = self.base / "manifests" / "source.json"
        written = sf.write_manifest(out, self.skill)
        self.assertEqual(sf.load_manifest(out), written)
        self.assertFalse(out.with_name(out.name + ".pending").exists())

    # 2 -------------------------------------------------------------------
    def test_verify_detects_changed_added_and_removed_files(self):
        frozen = sf.manifest(self.skill)
        self.assertEqual(sf.verify(frozen, self.skill)["status"], "PASS")

        (self.skill / "SKILL.md").write_text("tampered\n", encoding="utf-8")
        changed = sf.verify(frozen, self.skill)
        self.assertEqual(changed["status"], "VIOLATION")
        self.assertIn("SKILL.md", changed["changed"])

        (self.skill / "SKILL.md").write_text("# SKILL.md\n", encoding="utf-8")
        (self.skill / "scripts" / "extra.py").write_text("# extra\n", encoding="utf-8")
        self.assertIn("scripts/extra.py", sf.verify(frozen, self.skill)["added"])

        (self.skill / "scripts" / "extra.py").unlink()
        (self.skill / "scripts" / "util.py").unlink()
        self.assertIn("scripts/util.py", sf.verify(frozen, self.skill)["removed"])

    def test_verify_never_raises_on_a_missing_tree(self):
        frozen = sf.manifest(self.skill)
        result = sf.verify(frozen, self.base / "does-not-exist")
        self.assertEqual(result["status"], "VIOLATION")
        self.assertTrue(result["removed"])

    # 3 -------------------------------------------------------------------
    def test_guard_denies_protected_skill_source(self):
        for rel in ("SKILL.md", "scripts/guard.py", "presets/research-loop.md",
                    "preset-registry.json", "shared-contract.md",
                    "references/policy.md", "templates/research-state.template.json",
                    "schemas/x.schema.json"):
            with self.subTest(rel=rel):
                result = sf.guard_write(self.skill / rel, skill_root=self.skill)
                self.assertFalse(result["allowed"])
                self.assertEqual(result["code"], "PROTECTED_SKILL_SOURCE")

    # 4 -------------------------------------------------------------------
    def test_guard_denies_relative_traversal(self):
        result = sf.guard_write("../escape.txt", skill_root=self.skill)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["code"], "PATH_TRAVERSAL")
        with self.assertRaises(ValueError):
            sf.normalize_target(str(self.skill / ".." / "escape.txt"), root=self.skill)

    # 5 -------------------------------------------------------------------
    def test_guard_denies_symlink_escaping_the_skill_root(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "payload.txt").write_text("x\n", encoding="utf-8")
        link = self.skill / "scripts" / "escape-link"
        link.symlink_to(outside, target_is_directory=True)

        result = sf.guard_write(link / "payload.txt", skill_root=self.skill)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["code"], "SYMLINK_ESCAPE")

        escaped = sf.manifest(self.skill)
        self.assertIn("scripts/escape-link", escaped.get("symlink_escapes", []))

    # 6 -------------------------------------------------------------------
    def test_guard_allows_policy_and_trajectory_writes_inside_the_route(self):
        for rel in ("policy/priors.json",
                    "decision-trajectory/step-001.json"):
            with self.subTest(rel=rel):
                result = sf.guard_write(self.route / rel, skill_root=self.skill,
                                        allowed_roots=[self.route])
                self.assertTrue(result["allowed"], result)
                self.assertEqual(result["code"], "ALLOWED")
        self.assertEqual(sf.ALLOWED_WRITE_SCOPES[:2], ("policy", "decision-trajectory"))

    def test_guard_denies_writes_outside_allowed_roots(self):
        result = sf.guard_write(self.base / "elsewhere" / "x.json",
                                skill_root=self.skill, allowed_roots=[self.route])
        self.assertFalse(result["allowed"])
        self.assertEqual(result["code"], "OUTSIDE_ALLOWED_SCOPE")

    # 7 -------------------------------------------------------------------
    def test_guard_denies_hidden_evaluation_and_release_metadata(self):
        for rel in (".dev/hidden-answer.md", "examples/demo.md",
                    "CHANGELOG.md", "docs/releases/v9.9.9.md"):
            with self.subTest(rel=rel):
                result = sf.guard_write(self.skill / rel, skill_root=self.skill)
                self.assertFalse(result["allowed"])
                self.assertEqual(result["code"], "HIDDEN_EVALUATION_DATA")

    # 8 -------------------------------------------------------------------
    def test_guard_denies_canonical_state_unless_explicitly_allowed(self):
        target = self.route / "research-state.json"
        denied = sf.guard_write(target, skill_root=self.skill)
        self.assertFalse(denied["allowed"])
        self.assertEqual(denied["code"], "CANONICAL_REQUIRES_STAGE")
        allowed = sf.guard_write(target, skill_root=self.skill, allow_canonical=True)
        self.assertTrue(allowed["allowed"], allowed)

    # 9 -------------------------------------------------------------------
    def test_guard_errors_rejects_unsafe_candidates(self):
        cases = (
            {"action": "edit", "target": "SKILL.md"},
            {"steps": ["echo hi && rm -rf build"]},
            {"note": "import os"},
            {"target": "../outside/preset-registry.json"},
        )
        for candidate in cases:
            with self.subTest(candidate=candidate):
                reasons = sf.guard_errors(candidate)
                self.assertTrue(reasons, candidate)
                self.assertTrue(all(isinstance(reason, str) for reason in reasons))
        self.assertEqual(sf.guard_errors({"action": "adjust_prior",
                                          "scope": "exploration"}), [])

    # 10 ------------------------------------------------------------------
    def test_integrity_events_form_a_hash_chain(self):
        first = sf.record_integrity_event(self.route, {"action": "VERIFY_PASS"})
        sf.record_integrity_event(self.route, {"action": "VERIFY_PASS"})
        events = sf.integrity_events(self.route)
        self.assertEqual(len(events), 2)
        self.assertEqual([event["seq"] for event in events], [1, 2])
        self.assertIsNone(events[0]["previous"])
        raw_first = first.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(events[1]["previous"], line_digest(raw_first))
        self.assertTrue(all(event["schema"] == sf.SCHEMA_INTEGRITY_EVENT
                            for event in events))

    # 11 ------------------------------------------------------------------
    def test_source_freeze_records_hold_and_does_not_repair(self):
        with sf.SourceFreeze(root=self.skill, route_dir=self.route,
                             context="unit-test") as freeze:
            (self.skill / "SKILL.md").write_text("tampered\n", encoding="utf-8")
        self.assertEqual(freeze.result["status"], "VIOLATION")
        self.assertIn("SKILL.md", freeze.result["changed"])

        events = sf.integrity_events(self.route)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "HOLD")
        self.assertFalse(events[0]["repair_attempted"])
        # 守卫只记录，不修复：被篡改的内容保持原样。
        self.assertEqual((self.skill / "SKILL.md").read_text(encoding="utf-8"),
                         "tampered\n")

    def test_source_freeze_records_pass_when_tree_is_clean(self):
        with sf.SourceFreeze(root=self.skill, route_dir=self.route) as freeze:
            pass
        self.assertEqual(freeze.result["status"], "PASS")
        self.assertEqual(sf.integrity_events(self.route)[0]["action"], "VERIFY_PASS")

    # 12 ------------------------------------------------------------------
    def test_read_only_deployment_plan_states_the_residual_risk(self):
        plan = sf.read_only_deployment_plan()
        self.assertTrue(plan["recommended"])
        self.assertTrue(plan["residual_risks"])
        risk = plan["residual_risk"]
        self.assertTrue(risk)
        self.assertIn("not a security boundary", risk)


if __name__ == "__main__":
    unittest.main()
