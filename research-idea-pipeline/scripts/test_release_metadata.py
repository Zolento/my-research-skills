#!/usr/bin/env python3
"""test_release_metadata.py — one release version, declared consistently everywhere.

The released version must be visible in the same place for the tag, the skill metadata, both
READMEs, the changelog and the release notes. This test exists because a previous cycle shipped a
tag whose SKILL.md and component README disagreed, and because a later fix changed behaviour
without changing the version, so `v2.3.3` and `main` claimed the same number for different code.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO = ROOT.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def declared_version() -> str:
    text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
    match = re.search(r'metadata:\s*\n(?:.*\n)*?\s*version:\s*"([^"]+)"', text)
    if not match:                                    # tolerate key order changes
        match = re.search(r'version:\s*"([^"]+)"', text)
    return match.group(1) if match else ''


class TestReleaseMetadata(unittest.TestCase):

    def test_the_skill_declares_a_semantic_version(self):
        version = declared_version()
        self.assertRegex(version, SEMVER)

    def test_both_readmes_agree_with_the_skill(self):
        version = declared_version()
        root_readme = (REPO / 'README.md').read_text(encoding='utf-8')
        component_readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn(f'当前为 **{version}**', root_readme)
        self.assertRegex(component_readme, rf'v?{re.escape(version)}')

    def test_the_changelog_and_release_notes_cover_the_version(self):
        version = declared_version()
        changelog = ROOT / 'CHANGELOG.md'
        notes = ROOT / 'docs' / 'releases' / f'v{version}.md'
        self.assertTrue(changelog.is_file(), 'CHANGELOG.md is required for a release')
        self.assertTrue(notes.is_file(), f'docs/releases/v{version}.md is required')
        self.assertIn(version, changelog.read_text(encoding='utf-8'))
        heading = notes.read_text(encoding='utf-8').splitlines()[0]
        self.assertIn(version, heading)

    def test_no_document_claims_a_different_current_version(self):
        version = declared_version()
        for path in (REPO / 'README.md', ROOT / 'README.md', ROOT / 'SKILL.md'):
            text = path.read_text(encoding='utf-8')
            for match in re.finditer(r'当前(?:正式)?版本[^\n]{0,40}', text):
                self.assertIn(version, match.group(0), f'{path.name}: {match.group(0)}')

    def test_a_registry_version_is_not_silently_invented(self):
        """Schema and protocol ids keep their own versioning and must not track the release."""
        registry = json.loads((ROOT / 'preset-registry.json').read_text(encoding='utf-8'))
        self.assertEqual(registry['schema_version'], '0.1')
        outcome = (ROOT / 'references' / 'evidence-outcome-contract.md').read_text(encoding='utf-8')
        self.assertIn('evidence-outcome-assurance@1', outcome)

    def test_a_released_version_is_tagged_at_or_before_head(self):
        """Before tagging this is vacuous by design; after tagging it must point at or behind HEAD."""
        version = declared_version()
        tag = f'research-idea-pipeline/v{version}'
        proc = subprocess.run(['git', 'tag', '-l', tag], cwd=str(REPO), capture_output=True,
                              text=True)
        if not proc.stdout.strip():
            self.skipTest(f'{tag} does not exist yet (release not tagged)')
        tagged = subprocess.run(['git', 'rev-parse', f'{tag}^{{}}'], cwd=str(REPO),
                                capture_output=True, text=True).stdout.strip()
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(REPO), capture_output=True,
                              text=True).stdout.strip()
        ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', tagged, head], cwd=str(REPO))
        self.assertEqual(ancestor.returncode, 0, f'{tag} must not point past HEAD')


if __name__ == '__main__':
    unittest.main()
