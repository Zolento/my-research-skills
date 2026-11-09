#!/usr/bin/env python3
"""test_identity_compat.py — the rename boundary must stay real and testable.

The skill was renamed to `research-lifecycle-protocol`. Three things must never drift:

1. the frontmatter/install identity uses the new name only;
2. the machine protocol namespace stays `research-idea-pipeline/...@1`, because existing
   canonical states, ledgers and replay fixtures carry those ids;
3. a legacy project (`.research-idea-pipeline/`) still loads without migration, and a
   project with two runtime roots fails closed instead of silently choosing one.

These tests use the real CLI entry points where a runtime consumer exists, not just the
helper functions.
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


class TestStorageRootResolution(unittest.TestCase):

    def test_new_project_uses_the_new_root_without_creating_it(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            resolved = rlp.resolve_storage_root(project)
            self.assertEqual(resolved.kind, "new")
            self.assertEqual(resolved.root.name, rlp.STORAGE_ROOT)
            self.assertFalse(resolved.root.exists(), "resolution must not create directories")

    def test_current_root_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            (project / rlp.STORAGE_ROOT).mkdir()
            resolved = rlp.resolve_storage_root(project)
            self.assertEqual(resolved.kind, "current")
            self.assertFalse(resolved.is_legacy)

    def test_legacy_project_keeps_its_root_and_gains_no_new_one(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            resolved = rlp.resolve_storage_root(project)
            self.assertEqual(resolved.kind, "legacy")
            self.assertTrue(resolved.is_legacy)
            self.assertFalse((project / rlp.STORAGE_ROOT).exists(),
                             "a legacy project must not sprout a second root")

    def test_both_roots_fail_closed_instead_of_picking_one(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            (project / rlp.STORAGE_ROOT / "routes" / "A").mkdir(parents=True)
            with self.assertRaises(rlp.AmbiguousStorageRoot):
                rlp.resolve_storage_root(project)
            report = rlp.inspect_project(project)
            self.assertEqual(report["storage_kind"], "ambiguous")
            self.assertIsNone(report["storage_root"])
            self.assertIn("two canonical storage roots", report["ambiguous_reason"])
            checked = rlp.main(["check", "--project", str(project)])
            self.assertEqual(checked, rlp.EXIT_LAYOUT)

    def test_default_state_path_honours_the_existing_root(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            path = rlp.default_state_path(project, "A")
            self.assertEqual(path, project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A" / STATE_NAME)
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            path = rlp.default_state_path(project, "A")
            self.assertEqual(path, project / rlp.STORAGE_ROOT / "routes" / "A" / STATE_NAME)

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

    def test_project_root_from_state_rejects_an_unknown_control_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            state = write_state(pathlib.Path(temp) / ".wrong-root" / "routes" / "A")
            with self.assertRaises(rlp.LayoutError):
                rlp.project_root_from_state(state)

    def test_cli_resolve_reports_the_frozen_protocol_namespace(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            proc = run("rlp_paths.py", "resolve", "--project", str(project))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["skill_name"], rlp.SKILL_NAME)
            self.assertEqual(report["storage_kind"], "legacy")
            self.assertEqual(report["schema_namespace"], "research-idea-pipeline")
            self.assertTrue(report["schema_namespace_frozen"])


class TestLegacyProjectStillRuns(unittest.TestCase):

    def test_legacy_state_passes_the_state_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            state = write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            proc = run("state_check.py", "--check", str(state))
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_new_root_state_passes_the_same_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            state = write_state(project / rlp.STORAGE_ROOT / "routes" / "A")
            proc = run("state_check.py", "--check", str(state))
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_cognition_rebuild_modifies_only_derived_files(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            route = project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A"
            state = write_state(route)
            before = state.read_bytes()
            built = run("cognition.py", "build", "--state", str(state))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            checked = run("cognition.py", "check", "--state", str(state))
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertEqual(state.read_bytes(), before,
                             "canonical state must be byte-identical after projection rebuild")
            self.assertTrue((route / cg.COGNITION_DIRNAME / "index.json").is_file())
            self.assertFalse((project / rlp.STORAGE_ROOT).exists())

    def test_render_status_resolves_the_legacy_root_from_the_project_root(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            out = project / "routes" / "A" / "STATUS.md"
            out.parent.mkdir(parents=True)
            proc = run("render_status.py", "--root", str(project), "--route", "A",
                       "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("STATUS", out.read_text(encoding="utf-8") + "STATUS")

    def test_legacy_handoff_detect_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            state = write_state(project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A")
            before = state.read_bytes()
            proc = run("legacy_handoff.py", "detect", "--state", str(state))
            self.assertIn(proc.returncode, (0, 3), proc.stdout + proc.stderr)
            self.assertEqual(state.read_bytes(), before)
            self.assertFalse((project / rlp.STORAGE_ROOT).exists())

    def test_operational_reconcile_finds_the_project_root_behind_a_legacy_route(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            route = project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A"
            write_state(route)
            self.assertEqual(op._project_root(route), project.resolve())

    def test_ambiguity_is_not_hidden_by_the_reconciler(self):
        with tempfile.TemporaryDirectory() as temp:
            project = pathlib.Path(temp)
            route = project / rlp.LEGACY_STORAGE_ROOT / "routes" / "A"
            write_state(route)
            (project / rlp.STORAGE_ROOT / "routes" / "A").mkdir(parents=True)
            self.assertRaises(rlp.AmbiguousStorageRoot, op._project_root, route)


class TestStateGateStillSeesTheFrozenNamespace(unittest.TestCase):

    def test_the_ruleset_is_unchanged_by_the_rename(self):
        report = sc.check_state(lh._legacy_state())
        self.assertEqual(report.violations, [], f"unexpected violations: {report.violations}")
        self.assertEqual(report.shape, [])


if __name__ == "__main__":
    unittest.main()
