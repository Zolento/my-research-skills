"""v0.2.0 package integration: version, new gates, and contract consistency.

These tests check deterministic invariants of the evidence-grounding layer. They do
not measure semantic detection ability and do not certify any scientific claim.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

NEW_SCRIPTS = ('evidence_core.py', 'evidence_ledger.py', 'counterfactual_eval.py',
               'revision_impact.py', 'revision_loop.py')
NEW_REFERENCES = ('evidence-grounding.md', 'evidence-ledger.md', 'counterfactual-evaluation.md',
                  'revision-impact.md', 'bounded-revision-loop.md')


class VersionTests(unittest.TestCase):
    def test_skill_declares_v020(self):
        skill = (ROOT / 'SKILL.md').read_text()
        self.assertIn('version: "0.2.0"', skill)

    def test_skill_still_under_display_ceiling(self):
        self.assertLess(len((ROOT / 'SKILL.md').read_text().splitlines()), 120)


class ContractTests(unittest.TestCase):
    def test_evidence_core_self_check(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'evidence_core.py'), '--self-check'],
                                capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout), (0, ''))

    def test_vocabularies_are_disjoint_and_closed(self):
        import evidence_core as ec
        self.assertTrue(set(ec.FAULTY_CLASSES).isdisjoint(ec.ROBUSTNESS_CLASSES))
        self.assertTrue(set(ec.SUCCESSFUL_STOPS) <= set(ec.STOP_REASONS))
        self.assertEqual(set(ec.SCIENCE_DEPTH_REQUIREMENT), set(ec.SCIENTIFIC_RISKS))
        self.assertTrue(set(ec.SCIENCE_DEPTH_REQUIREMENT.values()) <= set(ec.REQUIRED_AUDITS))
        self.assertTrue(set(ec.FAULTY_CLASSES) <= set(ec.DEFECT_CLASSES))
        self.assertIn('robustness_defect_rewording', ec.DEFECT_CLASSES)
        self.assertNotIn('robustness_paraphrase', ec.DEFECT_CLASSES)
        for name, schema in ec.SCHEMAS.items():
            self.assertTrue(schema.endswith('@1'), name)
        self.assertEqual(len(set(ec.SCHEMAS.values())), len(ec.SCHEMAS))

    def test_robustness_classes_ask_different_questions(self):
        """Clean-rejection and detection-after-rewording must stay distinguishable."""
        import evidence_core as ec
        self.assertEqual(len(ec.ROBUSTNESS_CLASSES), 2)
        self.assertIn('robustness_paraphrase', ec.ROBUSTNESS_CLASSES)
        self.assertIn('robustness_defect_rewording', ec.ROBUSTNESS_CLASSES)
        self.assertTrue(set(ec.FAULTY_CLASSES).isdisjoint({'robustness_defect_rewording'}))

    def test_text_evidence_cannot_be_verified(self):
        import evidence_core as ec
        for method in ec.VERIFICATION_METHODS:
            if method == 'unverified':
                continue
            self.assertFalse(ec.defensible_verification('literature', method), method)
            self.assertFalse(ec.defensible_verification('other', method), method)
        self.assertTrue(ec.defensible_verification('run_log', 'hash_match'))
        self.assertTrue(ec.defensible_verification('code', 'test_suite'))

    def test_missing_evidence_is_not_unknown_science(self):
        import evidence_core as ec
        self.assertEqual(ec.claim_state([], 'C1'), 'no_evidence')
        self.assertEqual(ec.claim_state([{'claim_id': 'C1', 'state': 'unknown'}], 'C1'), 'unknown')
        self.assertNotEqual(ec.claim_state([], 'C1'), ec.claim_state([{'claim_id': 'C1', 'state': 'unknown'}], 'C1'))

    def test_contradiction_outranks_verification(self):
        import evidence_core as ec
        self.assertEqual(ec.claim_state([{'claim_id': 'C', 'state': 'verified'},
                                         {'claim_id': 'C', 'state': 'contradicted'}], 'C'), 'contradicted')


class DeliverableTests(unittest.TestCase):
    def test_new_scripts_and_references_exist(self):
        for name in NEW_SCRIPTS:
            self.assertTrue((ROOT / 'scripts' / name).is_file(), name)
        for name in NEW_REFERENCES:
            self.assertTrue((ROOT / 'references' / name).is_file(), name)

    def test_documented_cli_paths_match_contract(self):
        contract = (ROOT / 'references' / 'evidence-grounding.md').read_text()
        for name in NEW_SCRIPTS:
            self.assertIn('scripts/' + name, contract)
        self.assertIn('Exit 0 means the applicable gate passed', contract)

    def test_new_gates_are_standalone_stdlib_only(self):
        for name in NEW_SCRIPTS:
            text = (ROOT / 'scripts' / name).read_text()
            self.assertNotIn('research-idea-pipeline', text)
            self.assertNotIn('import yaml', text)
            self.assertNotIn('import numpy', text)

    def test_every_new_reference_is_linked_from_formal_docs(self):
        linked = (ROOT / 'SKILL.md').read_text() + (ROOT / 'README.md').read_text()
        self.assertIn('references/evidence-grounding.md', linked)
        for name in NEW_REFERENCES:
            self.assertTrue((ROOT / 'references' / name).is_file(), name)


class ExampleGateTests(unittest.TestCase):
    """Deterministic structural checks over the bundled v0.2.0 examples."""

    def run_cli(self, script, *args):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *args],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.stderr, '', script + ' wrote to stderr')
        return result.returncode, json.loads(result.stdout)

    def test_ledger_example_binds_real_artifacts(self):
        folder = ROOT / 'examples' / 'evidence-ledger'
        ledger = json.loads((folder / 'ledger.json').read_text())
        self.assertEqual(ledger['schema'], 'claim-evidence-ledger@1')
        digests = {a['id']: a['digest'] for a in ledger['artifacts']}
        self.assertTrue(digests)
        result = self.run_cli('evidence_ledger.py', str(folder / 'manuscript.md'),
                              '--ledger', str(folder / 'ledger.json'),
                              '--graph', str(folder / 'graph.json'))
        self.assertIn(result[1]['status'], ('PASS', 'NEEDS_REVIEW'))

    def test_counterfactual_harness_takes_a_supplied_detector(self):
        folder = ROOT / 'examples' / 'counterfactual'
        code, output = self.run_cli('counterfactual_eval.py', str(folder / 'evaluation.json'))
        self.assertIn(output['status'], ('NEEDS_REVIEW', 'PASS'))
        self.assertIn('detect', json.dumps(output).lower())

    def test_revision_loop_example_is_bounded(self):
        folder = ROOT / 'examples' / 'revision-impact'
        code, output = self.run_cli('revision_loop.py', str(folder / 'loop.json'))
        self.assertIn(output['status'], ('PASS', 'NEEDS_REVIEW', 'FAIL'))
        self.assertTrue(output.get('stop_reason'), 'the loop must report how it stopped')
        if output['status'] == 'PASS':
            self.assertTrue(output.get('completion_met'),
                            'only a met completion condition may pass')


if __name__ == '__main__':
    unittest.main()
