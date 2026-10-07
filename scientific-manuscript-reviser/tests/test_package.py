import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


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


if __name__ == '__main__':
    unittest.main()
