#!/usr/bin/env python3
"""test_storage_spec.py — the legacy storage root must never become a runtime default.

v2.1.0 policy: `.research-lifecycle-protocol/` is the ONLY runtime control root; the
legacy `.research-idea-pipeline/` is a migration source. This static check keeps new
code from reintroducing the old root as a normal runtime path, while allowing the
legitimate historical uses (frozen protocol ids, the resolver, the migration tool,
read-only compat code, tests and historical documentation).
"""

from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

#: Modules allowed to mention the legacy storage root, with the reason.
LEGACY_ROOT_ALLOWED = {
    "rlp_paths.py": "the resolver defines both constants and the migration states",
    "migrate_project_root.py": "the migration tool is the legacy-root consumer",
    "legacy_handoff.py": "read-only compat inspection of legacy layouts",
    "structural_equivalence_check.py": "historical audit_ref pattern compatibility",
}

#: Files that must never mention the legacy root at all.
LEGACY_ROOT_FORBIDDEN = {
    "preset_router.py", "operational_reconcile.py", "render_status.py",
    "cognition.py", "evidence_outcome.py", "domain_profile.py", "domain_guard.py",
    "domain_mms.py", "strategy_memory.py", "experiment_execute.py",
    "state_check.py", "research_replay.py", "decision_trajectory.py",
    "research_summary.py", "policy_evolution.py", "policy_transfer.py",
    "insight_to_method.py", "prediction_compare.py", "execution_gate.py",
    "zotero_client.py", "zotero_fulltext.py", "refs_index.py",
    "domain_replay.py", "source_freeze.py",
}

#: Documentation that may discuss the legacy root only in a marked context.
LEGACY_DOC_MARKERS = re.compile(
    r"(legacy|migration|compat|historical|迁移|兼容|历史)", re.IGNORECASE)


class TestNoLegacyRuntimeDefaults(unittest.TestCase):

    def test_runtime_modules_do_not_mention_the_legacy_root(self):
        offenders = []
        for name in sorted(LEGACY_ROOT_FORBIDDEN):
            path = SCRIPTS / name
            if path.is_file() and ".research-idea-pipeline" in path.read_text(
                    encoding="utf-8"):
                offenders.append(name)
        self.assertEqual(offenders, [],
                         f"these runtime modules still reference the legacy root: "
                         f"{offenders}; route control-plane paths through "
                         f"rlp_paths.py instead")

    def test_allowed_modules_document_their_reason(self):
        for name, reason in LEGACY_ROOT_ALLOWED.items():
            self.assertTrue((SCRIPTS / name).is_file(), f"{name} missing")
            self.assertTrue(reason)          # the allowlist itself is reviewed

    def test_new_projects_bootstrap_documentation_uses_the_new_root(self):
        text = (ROOT / "references" / "project-layout.md").read_text(encoding="utf-8")
        self.assertIn(".research-lifecycle-protocol", text)
        self.assertIn("DI-3", text)
        self.assertIn("DI-7", text)
        # the canonical-state invariant names the new root, not the old one
        self.assertIn(".research-lifecycle-protocol/routes/<route>/", text)

    def test_identity_doc_defines_the_storage_policy(self):
        text = (ROOT / "references" / "identity-and-compatibility.md").read_text(
            encoding="utf-8")
        self.assertIn(".research-lifecycle-protocol", text)
        self.assertIn("MIGRATION_REQUIRED", text)
        self.assertIn("migrate_project_root.py", text)

    def test_install_command_still_uses_the_formal_skill_name(self):
        for doc in (ROOT / "README.md", ROOT.parent / "README.md"):
            if doc.is_file():
                text = doc.read_text(encoding="utf-8")
                if "npx skills add" in text:
                    self.assertIn("research-lifecycle-protocol", text)

    def test_domain_profile_docs_point_at_the_new_root(self):
        text = (ROOT / "domain-profiles" / "README.md").read_text(encoding="utf-8")
        self.assertIn(".research-lifecycle-protocol", text)


class TestLegacyDocContext(unittest.TestCase):
    """Docs may discuss the legacy root — but only in a marked migration/compat context."""

    def test_skill_md_mentions_the_legacy_root_only_in_marked_sections(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        if ".research-idea-pipeline" not in text:
            return
        for paragraph in text.split("\n\n"):
            if ".research-idea-pipeline" in paragraph:
                self.assertTrue(
                    LEGACY_DOC_MARKERS.search(paragraph),
                    f"SKILL.md mentions the legacy root outside a legacy/migration/"
                    f"compat context: {paragraph[:120]!r}")


if __name__ == "__main__":
    unittest.main()
