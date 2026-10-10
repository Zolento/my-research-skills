#!/usr/bin/env python3
"""test_source_freeze.py — Skill 源码冻结与写入守卫的对抗测试。

所有用例都在 `tempfile` 假的 skill 树上运行，**绝不触碰真实 Skill 源码**。
覆盖：确定性清单、篡改检测、受保护路径拒绝、`../` 与 symlink 越界、
允许范围放行、隐藏评测数据/发布元数据、canonical state、候选对抗扫描、
哈希链审计、`SourceFreeze` 的 HOLD 行为与只读部署的剩余风险声明。

对抗回归（E-* 审计）：fail-closed 默认范围（E-1）、硬链接 inode 拒绝（E-2）、
审计链不可伪造/可核验/有 head 摘要/日志受保护（E-3）、相对 allowed_roots 按
cwd 解析（E-4）、畸形清单返回 VIOLATION（E-6）、非 dict 核验结果 HOLD（E-7）、
嵌套排除目录可见（E-8）、Skill 根目录拒绝（E-14）、scope 常量强制（E-15）。
"""

from __future__ import annotations

import hashlib
import os
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
        # E-1：即使 allow_canonical=True，canonical 也必须落在显式 allowed_root 内。
        unbound = sf.guard_write(target, skill_root=self.skill, allow_canonical=True)
        self.assertFalse(unbound["allowed"])
        self.assertEqual(unbound["code"], "OUTSIDE_ALLOWED_SCOPE")
        allowed = sf.guard_write(target, skill_root=self.skill,
                                 allowed_roots=[self.route], allow_canonical=True)
        self.assertTrue(allowed["allowed"], allowed)
        # 同一 flag 不能把 canonical 放进别的目录。
        elsewhere = sf.guard_write(self.base / "other" / "research-state.json",
                                   skill_root=self.skill,
                                   allowed_roots=[self.route], allow_canonical=True)
        self.assertFalse(elsewhere["allowed"])
        self.assertEqual(elsewhere["code"], "OUTSIDE_ALLOWED_SCOPE")

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

    # E-1 ------------------------------------------------------------------
    def test_guard_write_default_is_fail_closed_outside_the_skill_root(self):
        """E-1：默认 allowed_roots=() 不再等于全盘放行。"""
        for target in ("/etc/passwd", str(self.base / "outside" / "x.txt")):
            with self.subTest(target=target):
                result = sf.guard_write(target, skill_root=self.skill)
                self.assertFalse(result["allowed"], result)
                self.assertEqual(result["code"], "OUTSIDE_ALLOWED_SCOPE")
        # skill_root 内非受保护路径仍然是允许的（保持原有用途）。
        inside = sf.guard_write(self.skill / "docs" / "x.md", skill_root=self.skill)
        self.assertTrue(inside["allowed"], inside)
        # 显式范围能放行范围外目标。
        scoped = sf.guard_write(self.route / "policy" / "p.json",
                                skill_root=self.skill, allowed_roots=[self.route])
        self.assertTrue(scoped["allowed"], scoped)

    # E-2 ------------------------------------------------------------------
    def test_guard_write_denies_hard_links_to_protected_files(self):
        """E-2：路径不同但共享 inode 的硬链接必须被拒绝。"""
        link = self.route / "hard-SKILL.md"
        try:
            os.link(self.skill / "SKILL.md", link)
        except OSError:  # pragma: no cover - 文件系统不支持硬链接
            self.skipTest("hard links unsupported on this filesystem")
        result = sf.guard_write(link, skill_root=self.skill,
                                allowed_roots=[self.route])
        self.assertFalse(result["allowed"], result)
        self.assertEqual(result["code"], "HARD_LINK_TO_PROTECTED")
        # 守卫拒绝后受保护内容保持不变。
        self.assertEqual((self.skill / "SKILL.md").read_text(encoding="utf-8"),
                         "# SKILL.md\n")
        # 残余风险（写进 docstring）：真的绕过守卫写入后，verify 只能靠内容发现。
        frozen = sf.manifest(self.skill)
        link.write_text("OWNED\n", encoding="utf-8")
        self.assertEqual(sf.verify(frozen, self.skill)["status"], "VIOLATION")
        self.assertIn("SKILL.md", sf.verify(frozen, self.skill)["changed"])

    # E-3 ------------------------------------------------------------------
    def test_integrity_event_chain_fields_are_not_caller_overridable(self):
        """E-3(a)：seq / previous / recorded_at 由写入器决定。"""
        sf.record_integrity_event(self.route, {"action": "A"})
        sf.record_integrity_event(self.route, {"action": "B"})
        sf.record_integrity_event(self.route, {
            "action": "FORGED", "seq": 1,
            "previous": "sha256:deadbeef",
            "recorded_at": "1999-01-01T00:00:00+00:00",
        })
        forged = sf.integrity_events(self.route)[-1]
        self.assertEqual(forged["seq"], 3)
        self.assertNotEqual(forged["previous"], "sha256:deadbeef")
        self.assertNotEqual(forged["recorded_at"], "1999-01-01T00:00:00+00:00")
        self.assertEqual(forged["schema"], sf.SCHEMA_INTEGRITY_EVENT)

    def test_integrity_events_detects_a_deleted_middle_line(self):
        """E-3(b)：链断裂时非宽容读取抛错，宽容读取给出诊断。"""
        for index in range(3):
            sf.record_integrity_event(self.route, {"action": f"E{index}"})
        log = self.route / sf.INTEGRITY_NAME
        lines = log.read_text(encoding="utf-8").splitlines()
        log.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
        with self.assertRaises(sf.SourceFreezeError):
            sf.integrity_events(self.route)
        records, diagnostics = sf.integrity_events(self.route, tolerant=True)
        self.assertTrue(diagnostics)
        self.assertEqual(len(records), 2)
        self.assertTrue(sf.integrity_diagnostics(self.route))

    def test_integrity_events_detects_a_truncated_tail_via_head_sidecar(self):
        """E-3(c)：head sidecar 检测尾部截断。"""
        for index in range(3):
            sf.record_integrity_event(self.route, {"action": f"E{index}"})
        head = self.route / (sf.INTEGRITY_NAME + sf.INTEGRITY_HEAD_SUFFIX)
        self.assertTrue(head.is_file())
        log = self.route / sf.INTEGRITY_NAME
        lines = log.read_text(encoding="utf-8").splitlines()
        log.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")
        with self.assertRaises(sf.SourceFreezeError):
            sf.integrity_events(self.route)
        _, diagnostics = sf.integrity_events(self.route, tolerant=True)
        self.assertTrue(any("head" in item["message"] for item in diagnostics))

    def test_integrity_events_have_no_head_gap_for_a_missing_log(self):
        """空 route 没有日志也没有 head，读取返回空列表而不是抛错。"""
        self.assertEqual(sf.integrity_events(self.route), [])
        self.assertEqual(sf.integrity_diagnostics(self.route), [])

    def test_integrity_events_detect_full_log_deletion_via_orphan_head(self):
        """E-3(c)：整份日志被删除但 head 留下时必须报错。"""
        sf.record_integrity_event(self.route, {"action": "E0"})
        (self.route / sf.INTEGRITY_NAME).unlink()
        with self.assertRaises(sf.SourceFreezeError):
            sf.integrity_events(self.route)
        _, diagnostics = sf.integrity_events(self.route, tolerant=True)
        self.assertTrue(any("日志缺失" in item["message"] for item in diagnostics))

    def test_guard_write_protects_the_integrity_log_outside_its_route(self):
        """E-3(d)：审计日志（及其锁）只能写入显式 route。"""
        inside = sf.guard_write(self.route / sf.INTEGRITY_NAME,
                                skill_root=self.skill, allowed_roots=[self.route])
        self.assertTrue(inside["allowed"], inside)
        outside_route = sf.guard_write(self.route / sf.INTEGRITY_NAME,
                                       skill_root=self.skill)
        self.assertFalse(outside_route["allowed"], outside_route)
        self.assertEqual(outside_route["code"], "AUDIT_LOG_OUTSIDE_ROUTE")
        in_skill = sf.guard_write(self.skill / sf.INTEGRITY_NAME,
                                  skill_root=self.skill, allowed_roots=[self.route])
        self.assertFalse(in_skill["allowed"], in_skill)
        self.assertEqual(in_skill["code"], "AUDIT_LOG_OUTSIDE_ROUTE")
        lock = sf.guard_write(self.skill / sf.INTEGRITY_LOCK_NAME,
                              skill_root=self.skill, allowed_roots=[self.route])
        self.assertEqual(lock["code"], "AUDIT_LOG_OUTSIDE_ROUTE")
        head = sf.guard_write(self.skill / (sf.INTEGRITY_NAME
                                            + sf.INTEGRITY_HEAD_SUFFIX),
                              skill_root=self.skill, allowed_roots=[self.route])
        self.assertEqual(head["code"], "AUDIT_LOG_OUTSIDE_ROUTE")

    # E-4 ------------------------------------------------------------------
    def test_relative_allowed_roots_resolve_against_cwd_not_the_skill_root(self):
        """E-4：allowed_roots=["."] 不再静默放行整个 Skill。"""
        work = self.base / "work"
        work.mkdir()
        previous = os.getcwd()
        os.chdir(work)
        self.addCleanup(os.chdir, previous)
        # 旧行为："." 相对 skill_root 解析 → skill/docs/x.txt 会被 ALLOWED。
        denied = sf.guard_write(self.skill / "docs" / "x.txt",
                                skill_root=self.skill, allowed_roots=["."])
        self.assertFalse(denied["allowed"], denied)
        self.assertEqual(denied["code"], "OUTSIDE_ALLOWED_SCOPE")
        # "." 指向 cwd（work），cwd 下的 route scope 仍然放行。
        scoped = sf.guard_write(work / "policy" / "p.json",
                                skill_root=self.skill, allowed_roots=["."])
        self.assertTrue(scoped["allowed"], scoped)

    # E-7 ------------------------------------------------------------------
    def test_hold_on_violation_fails_closed_on_unknown_verification(self):
        """E-7：非 dict / 缺失核验结果是 UNKNOWN，必须 HOLD。"""
        for bogus in (None, ["x"], "tampered", 0):
            with self.subTest(bogus=bogus):
                result = sf.hold_on_violation(self.route, bogus,
                                              context="regression")
                self.assertEqual(result["status"], "HOLD", result)
                self.assertTrue(result["event"])
        self.assertEqual(sf.hold_on_violation(self.route, {})["status"], "HOLD")
        self.assertEqual(sf.hold_on_violation(self.route, {"status": "PASS"})["status"],
                         "PASS")
        events = sf.integrity_events(self.route)
        self.assertTrue(all(event["action"] == "HOLD" for event in events))

    # E-8 ------------------------------------------------------------------
    def test_nested_excluded_dirs_are_manifested_and_reported_as_added(self):
        """E-8：`.dev` 在受保护树内部可见；`.git` 与 `__pycache__` 在任意深度排除。

        `__pycache__` 必须排除：解释器每次生成 `.pyc` 都会改变清单，从而把「删掉字节码
        后第一次运行」误判为源码改动（新增 .pyc → VIOLATION → HOLD）。这是部署级误报。
        """
        frozen = sf.manifest(self.skill)
        for rel in ("scripts/.dev/evil.py",
                    "references/__pycache__/payload.pyc",
                    "presets/.git/hooks/post-checkout"):
            path = self.skill / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x\n", encoding="utf-8")

        result = sf.verify(frozen, self.skill)
        self.assertEqual(result["status"], "VIOLATION")
        self.assertIn("scripts/.dev/evil.py", result["added"])
        self.assertNotIn("references/__pycache__/payload.pyc", result["added"])
        self.assertNotIn("presets/.git/hooks/post-checkout", result["added"])
        self.assertIn("scripts/.dev/evil.py", sf.manifest(self.skill)["files"])

    def test_a_cold_bytecode_cache_does_not_look_like_a_source_change(self):
        """回归：`__pycache__` 出现在清单里会让第一次运行的 HOLD 变成常态。"""
        self.skill.mkdir(parents=True, exist_ok=True)
        (self.skill / "scripts").mkdir(parents=True, exist_ok=True)
        (self.skill / "scripts" / "guard.py").write_text("x\n", encoding="utf-8")
        frozen = sf.manifest(self.skill)
        cache = self.skill / "scripts" / "__pycache__"
        cache.mkdir(parents=True, exist_ok=True)
        for name in ("guard.cpython-314.pyc", "extra.pyc"):
            (cache / name).write_text("bytecode\n", encoding="utf-8")
        self.assertEqual(sf.verify(frozen, self.skill)["status"], "PASS")
        self.assertNotIn("scripts/__pycache__/extra.pyc", sf.manifest(self.skill)["files"])

    # E-6 ------------------------------------------------------------------
    def test_malformed_manifest_returns_violation_not_attribute_error(self):
        """E-6：files[rel] 不是对象时返回 VIOLATION + malformed 诊断。"""
        bad = {
            "schema": sf.SCHEMA_MANIFEST,
            "root": str(self.skill),
            "files": {
                "SKILL.md": "not-a-dict",
                "scripts/guard.py": None,
                "ghost/file.py": 1,
            },
        }
        result = sf.verify(bad, self.skill)  # 不抛异常
        self.assertEqual(result["status"], "VIOLATION")
        self.assertIn("SKILL.md", result["malformed"])
        self.assertIn("scripts/guard.py", result["malformed"])
        self.assertIn("ghost/file.py", result["malformed"])
        self.assertIn("SKILL.md", result["changed"])
        self.assertIn("ghost/file.py", result["removed"])
        # load_manifest 的 JSON 契约不变。
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write("{}")
            name = handle.name
        self.addCleanup(os.unlink, name)
        self.assertEqual(sf.load_manifest(pathlib.Path(name)), {})

    # E-14 -----------------------------------------------------------------
    def test_guard_write_denies_the_skill_root_itself(self):
        """E-14：Skill 根目录是定义上最宽的目标，必须拒绝。"""
        result = sf.guard_write(self.skill, skill_root=self.skill)
        self.assertFalse(result["allowed"], result)
        self.assertEqual(result["code"], "PROTECTED_SKILL_SOURCE")

    # E-15 -----------------------------------------------------------------
    def test_allowed_write_scopes_are_actually_enforced(self):
        """E-15：ALLOWED_WRITE_SCOPES 不再是装饰性常量。"""
        self.assertIn("policy", sf.ALLOWED_WRITE_SCOPES)
        denied = sf.guard_write(self.route / "unscoped.txt",
                                skill_root=self.skill, allowed_roots=[self.route])
        self.assertFalse(denied["allowed"], denied)
        self.assertEqual(denied["code"], "OUTSIDE_WRITE_SCOPE")
        for rel in ("policy/priors.json", "decision-trajectory/step-001.json",
                    "scheduler.json"):
            with self.subTest(rel=rel):
                result = sf.guard_write(self.route / rel, skill_root=self.skill,
                                        allowed_roots=[self.route])
                self.assertTrue(result["allowed"], result)


if __name__ == "__main__":
    unittest.main()


class TestGuardWriteDeltaRegressions(unittest.TestCase):
    """H-01..H-05: incomplete fixes of the write-guard findings."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name) / "skill"
        self.root.mkdir(parents=True)
        for name in sf.PROTECTED:
            path = self.root / name
            if name.endswith((".md", ".json")):
                path.write_text("x\n", encoding="utf-8")
            else:
                path.mkdir()
                (path / "x.txt").write_text("x\n", encoding="utf-8")
        self.route = pathlib.Path(self.temp.name) / "route"
        self.route.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_a_string_allowed_root_is_one_path_not_a_character_sequence(self):
        """H-01: iterating a string made '/' an allowed root, so every absolute path passed."""
        denied = sf.guard_write("/scheduler.json", skill_root=self.root,
                               allowed_roots=str(self.route))
        self.assertFalse(denied["allowed"])
        allowed = sf.guard_write(self.route / "scheduler.json", skill_root=self.root,
                                 allowed_roots=str(self.route))
        self.assertTrue(allowed["allowed"], allowed)

    def test_none_or_non_iterable_allowed_roots_deny_instead_of_raising(self):
        """H-03: the fix regressed into an uncaught TypeError."""
        for value in (None, 42, object()):
            try:
                verdict = sf.guard_write(self.route / "scheduler.json", skill_root=self.root,
                                         allowed_roots=value)
            except TypeError as exc:  # pragma: no cover - the bug this guards
                self.fail(f"guard_write raised for allowed_roots={value!r}: {exc}")
            self.assertFalse(verdict["allowed"], value)

    def test_deleting_the_protected_original_does_not_unlock_a_hard_link(self):
        """H-04: the inode set lost the entry once the original was removed."""
        if not hasattr(os, "link"):  # pragma: no cover
            self.skipTest("hard links unsupported")
        os.link(self.root / "SKILL.md", self.route / "hard")
        os.unlink(self.root / "SKILL.md")
        verdict = sf.guard_write(self.route / "hard", skill_root=self.root,
                                 allowed_roots=[self.route])
        self.assertFalse(verdict["allowed"])
        self.assertIn(verdict["code"], ("PROTECTED_SOURCE_MISSING", "HARD_LINK_TO_PROTECTED"))

    def test_the_scope_check_applies_inside_the_skill_root_too(self):
        """H-05: an in-root "route" was allowed regardless of its scope."""
        local = self.root / "localroutes" / "A"
        local.mkdir(parents=True)
        verdict = sf.guard_write(local / "evil.sh", skill_root=self.root,
                                 allowed_roots=[self.root / "localroutes"])
        self.assertFalse(verdict["allowed"])
        self.assertEqual(verdict["code"], "OUTSIDE_WRITE_SCOPE")

    def test_the_real_route_scopes_are_all_accepted(self):
        """H-02: the whitelist named `decision-trajectory` while the real store is a file."""
        for rel in ("scheduler.json", "decision-trajectory.jsonl", "policy/candidates.jsonl",
                    "cognition/index.json", ".execution/events.jsonl",
                    "assurance/x.json", "source-integrity.jsonl"):
            verdict = sf.guard_write(self.route / rel, skill_root=self.root,
                                     allowed_roots=[self.route])
            self.assertTrue(verdict["allowed"], (rel, verdict))
