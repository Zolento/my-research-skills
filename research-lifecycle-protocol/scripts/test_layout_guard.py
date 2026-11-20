#!/usr/bin/env python3
"""test_layout_guard.py — layout_guard.py 的离线测试（stdlib unittest，不联网）

运行：
    python3 -m unittest discover -s scripts -p "test_*.py"
    python3 scripts/test_layout_guard.py

为什么需要它
------------
`references/project-layout.md` 的 DI-1—DI-8 与「手工检查清单」在 v2.4.0 之前没有执行器。
六个真实项目全部漂移（未声明顶层目录、`log/` 与 `logs/` 并存、控制目录 31 份 state 备份、
`docs/` 子目录、缺 `STATUS.md`）。把规则写成脚本还不够：**每条判定必须有允许与拒绝两侧的
fixture 钉住**，否则「已实现」仍然是自述。

覆盖点
------
1. 允许侧：13 类 kind 各自的合法路径（含 anchor 必须 000、review 不占序号）。
2. 拒绝侧：R 阶段目录、路线内 src、docs 子目录、跨路线 ID、未登记 XID、根级散文件、
   受保护入口（dataset/store/旧控制根）、绝对路径与 `..`。
3. 登记来源：registry 两种真实形状（`name: "A"` 与 `name` 是标题、`path` 带斜杠）、
   预注册 / manifest / canonical state 三处 XID 登记。
4. 例外策略：窄模式允许一层、不覆盖更深路径；`**/*.md` 这类宽模式必须被拒绝（退出码 4）。
5. 审计：DI-1 / DI-3 / DI-4 / DI-8 / ROOT-3 / AGENTS-1 各至少一个 fixture；block 与
   warn 分级；`--json` 可解析；有 block 时退出码 3。
6. 环境：根不存在 → 4；双存储根 → 4；`--kind` 只用于 preflight。
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import layout_guard as guard
import rlp_paths as rlp


class GuardCase(unittest.TestCase):
    """每个用例一个临时「项目」，含一条已注册路线与一个已预注册实验。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        (self.root / "routes/A").mkdir(parents=True)
        (self.root / "routes/A/README.md").write_text("# A", encoding="utf-8")
        (self.root / "routes/A/STATUS.md").write_text("# A", encoding="utf-8")
        (self.root / "routes/A/INDEX.md").write_text("# A", encoding="utf-8")
        self.control = self.root / rlp.STORAGE_ROOT
        (self.control / "project").mkdir(parents=True)
        prereg = self.control / "routes/A/experiments/X021"
        prereg.mkdir(parents=True)
        (prereg / "preregistration.json").write_text("{}", encoding="utf-8")
        (self.root / "docs/refs").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def allow(self, path: str, kind: str | None = None) -> None:
        ok, reason = guard.check_path(self.root, path, kind)
        self.assertTrue(ok, f"{path} 应允许：{reason}")

    def block(self, path: str, kind: str | None = None) -> None:
        ok, reason = guard.check_path(self.root, path, kind)
        self.assertFalse(ok, f"{path} 应拒绝")


class AllowTests(GuardCase):
    def test_thirteen_kinds(self) -> None:
        cases = [
            ("src/models/net.py", "code"),
            ("shared/ops.py", "code"),
            ("scripts/train.py", "script"),
            ("tests/test_fft.py", "test"),
            ("configs/base/default.yaml", "config"),
            ("configs/routes/A/X021.yaml", "config"),
            ("routes/A/docs/A003-proposal.md", "route-doc"),
            ("routes/A/docs/A000-anchor.md", "route-doc"),
            ("routes/A/docs/A003-review-r01.md", "route-doc"),
            ("experiments/A/X021-trial/README.md", "experiment"),
            ("results/A/X021/figures/comparison.png", "result"),
            ("logs/A/X021/run1/train.log", "log"),
            ("checkpoints/A/X021/run1/best_val.pt", "checkpoint"),
            ("docs/refs/papers/paper.pdf", "project-doc"),
            (f"{rlp.STORAGE_ROOT}/runtime/temp.txt", "scratch"),
            (f"{rlp.STORAGE_ROOT}/routes/A/history/v1.json", "control"),
        ]
        for path, kind in cases:
            with self.subTest(path=path):
                self.allow(path, kind)

    def test_root_files_and_route_triad(self) -> None:
        for path in ("AGENTS.md", "README.md", "INDEX.md", ".gitignore",
                     "requirements.txt", "pyproject.toml",
                     "routes/A/README.md", "routes/A/STATUS.md", "routes/A/INDEX.md"):
            with self.subTest(path=path):
                self.allow(path)

    def test_all_enumerated_slugs(self) -> None:
        slugs = ("anchor", "field-map", "discovery", "theory", "evidence", "proposal",
                 "experiment-plan", "result-analysis", "decision", "narrative")
        for index, slug in enumerate(slugs, start=1):
            number = "000" if slug == "anchor" else f"{index:03d}"
            with self.subTest(slug=slug):
                self.allow(f"routes/A/docs/A{number}-{slug}.md", "route-doc")


class BlockTests(GuardCase):
    def test_layout_violations(self) -> None:
        cases = [
            "R0/study.md", "R9/experiment.md", "routes/A/src/net.py",
            "routes/A/docs/new-plan.md", "routes/A/docs/extra/A004-theory.md",
            "routes/A/docs/B001-proposal.md", "routes/A/docs/A000-proposal.md",
            "routes/A/docs/A001-anchor.md", "routes/A/docs/A1-review-r01.md",
            "random-output/final.md", "results_new/X021/foo.json",
            "log/A/X021/train.log", "docs/A001-proposal.md",
            "docs/unknown-category/x.md", "docs/dev", "docs",
        ]
        for path in cases:
            with self.subTest(path=path):
                self.block(path)

    def test_registration_required(self) -> None:
        cases = [
            "routes/B/docs/B001-proposal.md",
            "configs/routes/B/X001.yaml",
            "experiments/A/X999-trial/README.md",
            "results/A/X999/metrics.json",
            "experiments/A/X021-trial/model.pt",
            "results/A/X021-trial/metrics.json",
            "experiments/A/X021/README.md",
        ]
        for path in cases:
            with self.subTest(path=path):
                self.block(path)

    def test_protected_roots(self) -> None:
        for path in ("dataset/raw/sample.h5", "store/weights.pt", ".git/config"):
            with self.subTest(path=path):
                self.block(path)

    def test_path_normalization(self) -> None:
        for path in ("/tmp/move.txt", "../escape.md", "src/./x.py", "src//x.py",
                     "src\\x.py", "src/"):
            with self.subTest(path=path):
                self.block(path)

    def test_legacy_control_root_is_read_only(self) -> None:
        """只有旧根的项目：旧根可读，但写入被判违规（迁移前只读）。"""
        legacy_root = Path(self._tmp.name) / "legacy_proj"
        (legacy_root / "routes/A").mkdir(parents=True)
        (legacy_root / "routes/A/README.md").write_text("# A", encoding="utf-8")
        legacy = legacy_root / rlp.LEGACY_STORAGE_ROOT
        (legacy / "routes/A").mkdir(parents=True)
        (legacy / "routes/A/research-state.json").write_text("{}", encoding="utf-8")
        ok, reason = guard.check_path(
            legacy_root, f"{rlp.LEGACY_STORAGE_ROOT}/routes/A/research-state.json")
        self.assertFalse(ok, reason)
        self.assertIn("只读", reason)
        routes, _ = guard.registered_routes(legacy_root, legacy)
        self.assertEqual(routes, {"A"})

    def test_kind_mismatch(self) -> None:
        self.block("docs/dev/dev-notes.md", "route-doc")
        self.block("src/models/net.py", "config")

    def test_symlink_traversal(self) -> None:
        outside = Path(self._tmp.name) / "outside"
        outside.mkdir()
        (self.root / "results").symlink_to(outside, target_is_directory=True)
        self.block("results/A/X021/output.pt")
        ok, reason = guard.check_path(self.root, "results/A/X021/output.pt")
        self.assertIn("软链接", reason)


class RegistryTests(GuardCase):
    def test_two_real_registry_shapes(self) -> None:
        shapes = [
            {"routes": [{"name": "A", "path": "routes/A", "status": "active"}]},
            {"routes": [{"name": "SSDU-CIB theory audit", "path": "routes/A/"}]},
            {"routes": {"A": {"path": "routes/A"}}},
            {"routes": ["A"]},
        ]
        for payload in shapes:
            with self.subTest(payload=payload):
                (self.control / "project/route-registry.json").write_text(
                    json.dumps(payload), encoding="utf-8")
                routes, _ = guard.registered_routes(self.root, self.control)
                self.assertEqual(routes, {"A"})

    def test_title_is_not_a_route(self) -> None:
        (self.control / "project/route-registry.json").write_text(
            json.dumps({"routes": [{"name": "A 路线标题", "path": "routes/A/"}]}),
            encoding="utf-8")
        routes, _ = guard.registered_routes(self.root, self.control)
        self.assertEqual(routes, {"A"})

    def test_registry_missing_falls_back_to_docs(self) -> None:
        routes, source = guard.registered_routes(self.root, self.control)
        self.assertEqual(routes, {"A"})
        self.assertIn("routes", source)

    def test_xid_registration_sources(self) -> None:
        ok, source = guard.xid_registered(self.root, self.control, "A", "X021")
        self.assertTrue(ok)
        self.assertEqual(source, "preregistration")

        manifest = self.root / "experiments/A/X022-slug"
        manifest.mkdir(parents=True)
        (manifest / "manifest.json").write_text("{}", encoding="utf-8")
        ok, source = guard.xid_registered(self.root, self.control, "A", "X022")
        self.assertTrue(ok)
        self.assertEqual(source, "manifest")

        state = self.control / "routes/A/research-state.json"
        state.write_text(json.dumps({"experiments": [{"id": "X023"}]}), encoding="utf-8")
        ok, source = guard.xid_registered(self.root, self.control, "A", "X023")
        self.assertTrue(ok)
        self.assertEqual(source, "state")

        ok, _ = guard.xid_registered(self.root, self.control, "A", "X999")
        self.assertFalse(ok)

    def test_corrupt_registry_is_environment_error(self) -> None:
        (self.control / "project/route-registry.json").write_text("{oops", encoding="utf-8")
        with self.assertRaises(guard.GuardEnvError):
            guard.registered_routes(self.root, self.control)


class PolicyTests(GuardCase):
    def write_policy(self, payload: object) -> None:
        (self.control / "project/layout-policy.json").write_text(
            json.dumps(payload), encoding="utf-8")

    def test_narrow_exception_allows_one_level_only(self) -> None:
        self.write_policy({"additional_paths": ["paper/*.tex"]})
        self.allow("paper/main.tex")
        self.block("paper/arbitrary/extra.tex")

    def test_wide_pattern_is_rejected(self) -> None:
        for pattern in ("**/*.md", "*.md", "../shared/*.py", "./docs/*", "dataset/*"):
            with self.subTest(pattern=pattern):
                self.write_policy({"additional_paths": [pattern]})
                with self.assertRaises(guard.GuardEnvError):
                    guard.load_policy(self.root, self.control)

    def test_approved_doc_subdir(self) -> None:
        self.write_policy({"additional_doc_subdirs": ["manuscript"]})
        self.allow("docs/manuscript/intro.md")
        self.block("docs/other/intro.md")

    def test_reference_tool_allowlist_is_read(self) -> None:
        legacy = self.root / "docs/dev"
        legacy.mkdir(parents=True)
        (legacy / "path-allowlist.json").write_text(
            json.dumps({"additional_paths": ["paper/*.tex"]}), encoding="utf-8")
        self.allow("paper/main.tex")


class AuditTests(GuardCase):
    def codes(self) -> set:
        return {finding["code"] for finding in guard.audit(self.root)}

    def test_clean_project_has_no_blocks(self) -> None:
        (self.root / "AGENTS.md").write_text("# 执行边界\n", encoding="utf-8")
        blocks = [f for f in guard.audit(self.root) if f["severity"] == guard.BLOCK]
        self.assertEqual(blocks, [], blocks)

    def test_each_rule_has_a_counterexample(self) -> None:
        (self.root / "R9").mkdir()
        (self.root / "log").mkdir()
        (self.root / "routes/A/docs/figures").mkdir(parents=True)
        (self.root / "routes/A/src").mkdir()
        (self.root / "routes/A/STATUS.md").unlink()
        (self.control / "routes/A/research-state.v2.json").write_text("{}", encoding="utf-8")
        (self.root / "docs/A004-theory.md").write_text("x", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("x" * 30000, encoding="utf-8")
        (self.root / "results/audit/x.json").parent.mkdir(parents=True)
        (self.root / "results/audit/x.json").write_text("{}", encoding="utf-8")
        (self.root / "research").mkdir()
        codes = self.codes()
        for code in ("DI-1", "DI-3", "DI-4", "DI-6", "DI-8", "ROOT-3", "ROOT-1",
                     "AGENTS-1", "DI-5"):
            self.assertIn(code, codes)

    def test_warn_is_not_block(self) -> None:
        (self.root / ".unknown-hidden").mkdir()
        findings = guard.audit(self.root)
        blocks = [f for f in findings if f["severity"] == guard.BLOCK]
        self.assertEqual(blocks, [])
        self.assertTrue(any(f["severity"] == guard.WARN for f in findings))

    def test_agents_size_budget(self) -> None:
        (self.root / "AGENTS.md").write_text("x" * 13000, encoding="utf-8")
        severities = {f["code"]: f["severity"] for f in guard.audit(self.root)
                      if f["code"] == "AGENTS-1"}
        self.assertEqual(severities.get("AGENTS-1"), guard.WARN)
        (self.root / "AGENTS.md").write_text("x" * 25000, encoding="utf-8")
        severities = {f["code"]: f["severity"] for f in guard.audit(self.root)
                      if f["code"] == "AGENTS-1"}
        self.assertEqual(severities.get("AGENTS-1"), guard.BLOCK)

    def test_policy_overrides_budget(self) -> None:
        (self.control / "project/layout-policy.json").write_text(
            json.dumps({"agents_max_bytes": 40000}), encoding="utf-8")
        (self.root / "AGENTS.md").write_text("x" * 25000, encoding="utf-8")
        severities = [f["severity"] for f in guard.audit(self.root)
                      if f["code"] == "AGENTS-1"]
        self.assertNotIn(guard.BLOCK, severities)


class ManagedBlockTests(GuardCase):
    """Skill 注入的受管块不计入项目自撰体量。"""

    BLOCK = ("<!-- BEGIN RLP MRI TRAINING -->\n## MRI 硬约束\n" + "x" * 4000
             + "\n<!-- END RLP MRI TRAINING -->\n")

    def test_managed_block_is_excluded_from_budget(self) -> None:
        (self.root / "AGENTS.md").write_text("# 边界\n" + self.BLOCK, encoding="utf-8")
        blocks = [f for f in guard.audit(self.root) if f["code"] == "AGENTS-1"]
        self.assertEqual(blocks, [], blocks)

    def test_project_text_over_budget_still_blocks(self) -> None:
        (self.root / "AGENTS.md").write_text("x" * 25000 + self.BLOCK, encoding="utf-8")
        severities = [f["severity"] for f in guard.audit(self.root) if f["code"] == "AGENTS-1"]
        self.assertIn(guard.BLOCK, severities)

    def test_block_bytes_measurement(self) -> None:
        measured = guard.managed_block_bytes(self.BLOCK.encode("utf-8"))
        self.assertGreater(measured, 4000)
        self.assertEqual(guard.managed_block_bytes(b"# plain\n"), 0)

    def test_unterminated_block_is_not_exempted(self) -> None:
        text = "x" * 25000 + "<!-- BEGIN RLP MRI TRAINING -->\n"
        (self.root / "AGENTS.md").write_text(text, encoding="utf-8")
        self.assertEqual(guard.managed_block_bytes(text.encode("utf-8")), 0)


class CliTests(GuardCase):
    def run_cli(self, *argv: str) -> tuple:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = guard.main(list(argv))
        return code, out.getvalue()

    def test_preflight_exit_codes(self) -> None:
        code, text = self.run_cli("preflight", "--root", str(self.root),
                                  "--path", "routes/A/docs/A003-proposal.md")
        self.assertEqual(code, 0)
        self.assertIn("PASS", text)
        code, text = self.run_cli("preflight", "--root", str(self.root),
                                  "--path", "R9/study.md")
        self.assertEqual(code, 3)
        self.assertIn("BLOCK", text)

    def test_audit_json_and_exit(self) -> None:
        (self.root / "research").mkdir()
        code, text = self.run_cli("audit", "--root", str(self.root), "--json")
        self.assertEqual(code, 3)
        payload = json.loads(text)
        self.assertGreater(payload["blocked"], 0)
        self.assertIn("by_code", payload)
        self.assertIn("ROOT-1", payload["by_code"])

    def test_audit_clean_exit_zero(self) -> None:
        (self.root / "AGENTS.md").write_text("# 边界\n", encoding="utf-8")
        code, _ = self.run_cli("audit", "--root", str(self.root))
        self.assertEqual(code, 0)

    def test_environment_errors(self) -> None:
        code, _ = self.run_cli("audit", "--root", str(self.root / "missing"))
        self.assertEqual(code, 4)
        (self.root / rlp.LEGACY_STORAGE_ROOT).mkdir()
        code, _ = self.run_cli("audit", "--root", str(self.root))
        self.assertEqual(code, 4)

    def test_kind_only_for_preflight(self) -> None:
        with self.assertRaises(SystemExit):
            self.run_cli("check", "--root", str(self.root), "--kind", "code")

    def test_selftest_and_list_kinds(self) -> None:
        code, text = self.run_cli("selftest")
        self.assertEqual(code, 0, text)
        code, text = self.run_cli("list-kinds")
        self.assertEqual(code, 0)
        self.assertIn("route-doc", text)


if __name__ == "__main__":
    unittest.main()
