"""Exercise installed-folder CLIs without any sibling skill or repository files."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StandaloneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / ROOT.name
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))

    def run_cli(self, script, *args):
        result = subprocess.run([sys.executable, str(self.root / 'scripts' / script), *args],
                                cwd=self.temp.name, capture_output=True, text=True)
        self.assertEqual(result.stderr, '')
        return result.returncode, json.loads(result.stdout)

    def test_style_cli_exit_codes_and_no_input_mutation(self):
        path = Path(self.temp.name) / 'manuscript.tex'
        for text, exit_code, status in [('A measured difference.', 0, 'PASS'),
                                         ('A result; bounded by Y.', 3, 'FAIL'),
                                         (r'\unknownmacro{opaque}', 4, 'NEEDS_REVIEW')]:
            path.write_text(text)
            code, output = self.run_cli('validate_style.py', str(path))
            self.assertEqual((code, output['status']), (exit_code, status))
            self.assertEqual(path.read_text(), text)

    def test_independent_examples_and_missing_semantic_audit(self):
        d = self.root / 'examples' / 'real-section'
        args = [str(d / 'input.txt'), str(d / 'proposed-revision.txt'),
                '--original-facts', str(d / 'before-facts.json'),
                '--revised-facts', str(d / 'after-facts.json')]
        code, output = self.run_cli('compare_invariants.py', *args)
        self.assertEqual((code, output['status']), (4, 'NEEDS_REVIEW'))
        code, output = self.run_cli('compare_invariants.py', *args, '--audit', str(d / 'semantic-audit.json'))
        self.assertEqual((code, output['status']), (0, 'PASS'))
        d = self.root / 'examples' / 'architect-bounded'
        args = ['check']
        for flag, filename in [('material','materials.json'),('graph','graph.json'),('report','coherence-report.json'),('blueprint','blueprint.json'),('audit','outline-audit.json')]:
            args.extend(['--' + flag, str(d / filename)])
        code, output = self.run_cli('architect.py', *args)
        self.assertEqual((code, output['status']), (0, 'PASS'))

    def test_malformed_audit_cli_does_not_certify(self):
        d = self.root / 'examples' / 'real-section'
        malformed = Path(self.temp.name) / 'invalid.json'
        malformed.write_text('{')
        code, output = self.run_cli('audit_coherence.py', str(d / 'input.txt'), '--graph', str(malformed))
        self.assertEqual((code, output['status']), (4, 'INVALID'))


if __name__ == '__main__':
    unittest.main()
