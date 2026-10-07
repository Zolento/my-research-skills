import pathlib
import unittest
import sys
import tempfile
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import release_check


class PackageTests(unittest.TestCase):
    def test_short_entrypoint_and_name(self):
        skill = (ROOT / 'SKILL.md').read_text()
        self.assertIn('name: ' + ROOT.name, skill)
        self.assertLess(len(skill.splitlines()), 120)

    def test_no_cross_skill_code_dependency(self):
        for path in (ROOT / 'scripts').glob('*.py'):
            text = path.read_text()
            self.assertNotIn('research-idea-pipeline/', text)
            self.assertNotIn('import state_check', text)

    def test_branch_notes_are_optional_for_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            scratch = root / '.dev' / 'nested'
            scratch.mkdir(parents=True)
            note = scratch / 'review.md'
            note.write_text('[Draft](missing.md)')
            with patch.object(release_check, 'ROOT', root):
                self.assertEqual(release_check.links(), [])
                note.unlink()
                self.assertEqual(release_check.links(), [])

    def test_formal_docs_cannot_require_branch_notes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            scratch = root / '.dev'
            scratch.mkdir()
            (scratch / 'plan.md').write_text('Branch-only plan')
            (root / 'README.md').write_text('[Required specification](.dev/plan.md)')
            with patch.object(release_check, 'ROOT', root):
                self.assertTrue(release_check.links())


if __name__ == '__main__':
    unittest.main()
