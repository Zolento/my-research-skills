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
        """The repository root README is checked only when this copy sits inside the repository.

        An installed skill (e.g. `~/.agents/skills/research-idea-pipeline`) has no repository
        root, and a release check must not fail there.
        """
        version = declared_version()
        component_readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertRegex(component_readme, rf'v?{re.escape(version)}')
        root_readme = REPO / 'README.md'
        if root_readme.is_file():
            self.assertIn(f'当前为 **{version}**', root_readme.read_text(encoding='utf-8'))
        else:
            self.skipTest('installed copy: no repository root README to cross-check')

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
            if not path.is_file():
                continue
            text = path.read_text(encoding='utf-8')
            for match in re.finditer(r'当前(?:正式)?版本[^\n]{0,40}', text):
                self.assertIn(version, match.group(0), f'{path.name}: {match.group(0)}')

    def test_a_registry_version_is_not_silently_invented(self):
        """Schema and protocol ids keep their own versioning and must not track the release."""
        registry = json.loads((ROOT / 'preset-registry.json').read_text(encoding='utf-8'))
        self.assertEqual(registry['schema_version'], '0.1')
        outcome = (ROOT / 'references' / 'evidence-outcome-contract.md').read_text(encoding='utf-8')
        self.assertIn('evidence-outcome-assurance@1', outcome)

    def test_the_release_tag_points_exactly_at_the_verified_release_commit(self):
        """A released tag must point **at** the verified commit, not merely at an ancestor.

        `--is-ancestor` would also accept a tag left on some earlier commit of the same branch,
        which is precisely the "tag behind main" drift this check exists to prevent. Before the
        tag is created the check is reported as skipped; it activates by itself once the tag
        exists, so no test ever creates a tag.
        """
        version = declared_version()
        tag = f'research-idea-pipeline/v{version}'
        if not subprocess.run(['git', 'tag', '-l', tag], cwd=str(REPO), capture_output=True,
                              text=True).stdout.strip():
            self.skipTest(f'{tag} does not exist yet (release not tagged)')
        tagged = subprocess.run(['git', 'rev-parse', f'{tag}^{{}}'], cwd=str(REPO),
                                capture_output=True, text=True).stdout.strip()
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(REPO),
                              capture_output=True, text=True).stdout.strip()
        main = subprocess.run(['git', 'rev-parse', 'refs/heads/main'], cwd=str(REPO),
                              capture_output=True, text=True).stdout.strip()
        self.assertEqual(tagged, head,
                         f'{tag} must point at the verified release commit {head[:8]}, '
                         f'not {tagged[:8]}')
        if main:
            self.assertEqual(tagged, main, f'{tag} must be the main release commit')


if __name__ == '__main__':
    unittest.main()
