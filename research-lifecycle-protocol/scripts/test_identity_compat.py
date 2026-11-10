#!/usr/bin/env python3
"""test_identity_compat.py — the rename boundary and the storage matrix.

Two things must never drift:

1. the identity boundary: the frontmatter/install identity uses the new skill name
   only; the machine protocol namespace stays `research-idea-pipeline/...@1`;
2. the storage matrix (v2.1.0): `.research-lifecycle-protocol/` is the ONLY runtime
   root. The legacy `.research-idea-pipeline/` is a migration source — normal runtime
   must raise MIGRATION_REQUIRED, both roots fail closed (AMBIGUOUS), an
   unrecognizable new root fails closed (INVALID_STORAGE_ROOT), and a fresh project
   resolves NEW_PROJECT without creating anything.

Read-only compat inspection (legacy_handoff.detect, migration tooling) still works on
legacy roots through `inspect_legacy_root` / `resolve_storage_root`.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import cognition as cg
import legacy_handoff as lh
import operational_reconcile as op
import rlp_paths as rlp
import state_check as sc

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
STATE_NAME = "research-state.json"


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                          capture_output=True, text=True, cwd=str(ROOT))


def write_state(route_dir: pathlib.Path) -> pathlib.Path:
    route_dir.mkdir(parents=True, exist_ok=True)
    path = route_dir / STATE_NAME
    path.write_text(json.dumps(lh._legacy_state(), ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


class TestIdentity(unittest.TestCase):

    def test_frontmatter_declares_the_new_skill_name_only(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(r"^name:\s*(\S+)\s*$", text, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), rlp.SKILL_NAME)
        self.assertEqual(rlp.SKILL_NAME, "research-lifecycle-protocol")

    def test_the_old_name_is_recorded_as_legacy_not_as_identity(self):
        self.assertIn("research-idea-pipeline", rlp.LEGACY_SKILL_NAMES)
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("legacy-name: research-idea-pipeline", text)

    def test_every_declared_schema_id_stays_in_the_frozen_namespace(self):
        """A schema id is an opaque protocol identifier, not a brand name.

        Only `_schema`/`schema` *values* count: test files also build deliberate
        counter-examples (e.g. `something/else@9`) that must stay free to differ.
        """
        pattern = re.compile(r'"(?:_schema|schema)":\s*"([a-z][a-z0-9-]*)/([a-z0-9-]+)@(\d+)"')
        found = {}
        for path in sorted(SCRIPTS.glob("*.py")):
            if path.name.startswith("test_"):
                continue   # test files build deliberate counter-examples by design
            for prefix, suffix, version in pattern.findall(path.read_text(encoding="utf-8")):
                found.setdefault(prefix, set()).add(f"{suffix}@{version}")
        self.assertTrue(found, "no schema ids found: the scan itself is broken")
        self.assertEqual(set(found), {rlp.SCHEMA_NAMESPACE},
                         f"schema namespaces drifted: {sorted(found)}")
        self.assertNotIn(rlp.SKILL_NAME, found,
                         "the new skill name must not become a schema namespace")

    def test_the_namespace_is_marked_frozen(self):
        self.assertTrue(rlp.SCHEMA_NAMESPACE_IS_FROZEN)
        self.assertEqual(rlp.SCHEMA_NAMESPACE, "research-idea-pipeline")


class TestStorageMatrix(unittest.TestCase):
    """§2.1 — the runtime behaviour for every storage-root configuration."""

    def test_both_roots_absent_resolves_new_project_without_creating_anything(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            report = rlp.runtime_status(project)
            self.assertEqual(report["status"], rlp.RUNTIME_STATUS_NEW_PROJECT)
            resolved = rlp.resolve_runtime_root(project)
            self.assertEqual(resolved.root, project / rlp.STORAGE_ROOT)
            self.assertFalse(resolved.root.exists(),
                             "resolution must not create directories")

    def test_ready_project_uses_the_new_root(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_state(project / rlp.STORAGE_ROOT / "routes" / "A")
            report = rlp.runtime_status(project)
            self.assertEqual(report["status"], rlp.RUNTIME_STATUS_READY)
            resolved = rlp.resolve_runtime_root(project)
            self.assertEqual(resolved.root, project / rlp.STORAGE_ROOT)
            self.assertFalse(resolved.is_legacy)

    def test_legacy_only_project_requires_migration_and_writes_nothing(self):
        """旧项目：MIGRATION_REQUIRED 是工程控制平面状态，暂停正式运行。"""
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            report = rlp.runtime_status(project)
            self.assertEqual(report["status"], rlp.RUNTIME_STATUS_MIGRATION_REQUIRED)
            self.assertIn("migrate", report["reason"])
            with self.assertRaises(rlp.MigrationRequired):
                rlp.resolve_runtime_root(project)
            with self.assertRaises(rlp.MigrationRequired):
                rlp.default_state_path(project, "A")
            self.assertEqual(report["status"], rlp.MigrationRequired.STATUS)

    def test_both_roots_fail_closed_as_ambiguous(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            (project / rlp.STORAGE_ROOT / "routes" / "A").mkdir(parents=True)
            report = rlp.runtime_status(project)
            self.assertEqual(report["status"], rlp.RUNTIME_STATUS_AMBIGUOUS)
            with self.assertRaises(rlp.AmbiguousStorageRoot):
                rlp.resolve_runtime_root(project)
            checked = rlp.main(["check", "--project", str(project)])
            self.assertEqual(checked, rlp.EXIT_LAYOUT)

    def test_an_unrecognizable_new_root_fails_closed_as_invalid(self):
        """新目录存在但不完整 → INVALID_STORAGE_ROOT，禁止静默修复或重建。"""
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            (project / rlp.STORAGE_ROOT).mkdir()
            report = rlp.runtime_status(project)
            self.assertEqual(report["status"], rlp.RUNTIME_STATUS_INVALID)
            with self.assertRaises(rlp.InvalidStorageRoot):
                rlp.resolve_runtime_root(project)

    def test_the_new_root_is_the_only_runtime_default(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            path = rlp.default_state_path(project, "A")
            self.assertEqual(path,
                             project / rlp.STORAGE_ROOT / "routes" / "A" / STATE_NAME)

    def test_runtime_status_is_machine_readable_and_stable(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            report = rlp.runtime_status(project)
            for key in ("project_root", "new_root", "legacy_root",
                        "new_root_exists", "legacy_root_exists", "status", "reason"):
                self.assertIn(key, report)


class TestInspectionAPIs(unittest.TestCase):
    """Read-only inspection keeps working on legacy roots (migration / compat tools)."""

    def test_inspect_legacy_root_describes_the_legacy_root(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            self.assertIsNone(rlp.inspect_legacy_root(project))
            write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            legacy = rlp.inspect_legacy_root(project)
            self.assertIsNotNone(legacy)
            self.assertTrue(legacy.is_legacy)

    def test_project_root_from_state_accepts_both_layouts_and_plain_fixtures(self):
        for root_name in (rlp.STORAGE_ROOT, rlp.LEGACY_STORAGE_ROOT):
            with tempfile.TemporaryDirectory() as temp:
                project = pathlib.Path(temp)
                state = write_state(project / root_name / "routes" / "A")
                self.assertEqual(rlp.project_root_from_state(state), project.resolve())
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            plain = write_state(project / "route-fixture" / "A")
            self.assertEqual(rlp.project_root_from_state(plain), plain.parent.resolve())

    def test_ambiguity_is_reported_even_from_a_legacy_state_path(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            state = write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            (project / rlp.STORAGE_ROOT / "routes" / "A").mkdir(parents=True)
            with self.assertRaises(rlp.AmbiguousStorageRoot):
                rlp.project_root_from_state(state)

    def test_cli_resolve_reports_the_matrix(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            proc = run("rlp_paths.py", "resolve", "--project", str(project))
            self.assertEqual(proc.returncode, rlp.EXIT_LAYOUT, proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["runtime_status"], "MIGRATION_REQUIRED")
            self.assertEqual(payload["schema_namespace"], "research-idea-pipeline")
            self.assertTrue(payload["schema_namespace_frozen"])

    def test_cli_check_hints_at_the_migration_tool(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            proc = run("rlp_paths.py", "check", "--project", str(project))
            self.assertEqual(proc.returncode, rlp.EXIT_LAYOUT)
            self.assertIn("MIGRATION_REQUIRED", proc.stderr)
            self.assertIn("migrate_project_root.py", proc.stderr)


class TestLegacyReadonlyCompat(unittest.TestCase):
    """只读兼容检查仍然可用——但不等于旧根可以继续承担日常运行。"""

    def test_legacy_state_passes_the_state_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            state = write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            proc = run("state_check.py", "--check", str(state))
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_cognition_rebuild_modifies_only_derived_files(self):
        """派生投影重建：新根上正常工作且 canonical 逐字节不变；
        旧根项目按存储矩阵被暂停（派生写入也是运行时写入）。"""
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            route = project / rlp.STORAGE_ROOT / "routes" / "A"
            state = write_state(route)
            before = state.read_bytes()
            built = run("cognition.py", "build", "--state", str(state))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            checked = run("cognition.py", "check", "--state", str(state))
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertEqual(state.read_bytes(), before,
                             "canonical state must be byte-identical after projection rebuild")
            self.assertTrue((route / cg.COGNITION_DIRNAME / "index.json").is_file())

    def test_derived_writes_on_a_legacy_project_are_gated(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            route = project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A"
            state = write_state(route)
            built = run("cognition.py", "build", "--state", str(state))
            self.assertNotEqual(built.returncode, 0)
            self.assertIn("MIGRATION_REQUIRED", built.stderr)

    def test_legacy_handoff_detect_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            state = write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            before = state.read_bytes()
            proc = run("legacy_handoff.py", "detect", "--state", str(state))
            self.assertIn(proc.returncode, (0, 3), proc.stdout + proc.stderr)
            self.assertEqual(state.read_bytes(), before)

    def test_operational_reconcile_finds_the_project_root_behind_any_route(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            route = project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A"
            write_state(route)
            self.assertEqual(op._project_root(route), project.resolve())

    def test_the_reconciler_gates_a_legacy_only_project(self):
        """正式运行入口在旧根项目上必须给出迁移需求，而不是继续写旧根。"""
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            route = project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A"
            write_state(route)
            with self.assertRaises(rlp.MigrationRequired):
                op.reconcile(route / STATE_NAME)

    def test_the_state_ruleset_is_unchanged_by_the_rename(self):
        report = sc.check_state(lh._legacy_state())
        self.assertEqual(report.violations, [], f"unexpected violations: {report.violations}")
        self.assertEqual(report.shape, [])


if __name__ == "__main__":
    unittest.main()
