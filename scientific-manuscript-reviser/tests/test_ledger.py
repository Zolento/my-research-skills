import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import evidence_core
import evidence_ledger as el

EXAMPLE = ROOT / 'examples' / 'evidence-ledger'
MANUSCRIPT = ('The detector reaches precision 0.91. Every run used one configuration. '
              'A prior study reported 0.89. The drift is stationary across all sensor families.')


def span(text, anchor):
    start = text.index(anchor)
    return {'location': {'start': start, 'end': start + len(anchor)}, 'source_span': anchor}


def graph_for(central=('C1', 'C2')):
    ids = {'C1', 'C2', 'C3', 'C4'}
    return {'nodes': [{'id': i, 'type': 'Claim'} for i in sorted(ids)],
            'central_claim_ids': list(central)}


def fixture(tmp, text=MANUSCRIPT):
    """A minimal, internally consistent ledger whose artifact files exist on disk."""
    root = pathlib.Path(tmp)
    (root / 'data.json').write_text('{"precision": 0.91}\n', encoding='utf-8')
    (root / 'notes.md').write_text('The prior study reports precision 0.89.\n', encoding='utf-8')
    ledger = {
        'schema': 'claim-evidence-ledger@1',
        'claims': [
            {'id': 'C1', 'statement': 'Held-out precision is 0.91.',
             'presented_as_established': True, **span(text, 'The detector reaches precision 0.91.')},
            {'id': 'C2', 'statement': 'A prior study reported 0.89.',
             'presented_as_established': False, **span(text, 'A prior study reported 0.89.')},
        ],
        'artifacts': [
            {'id': 'A1', 'type': 'experiment_data', 'reference': 'data.json',
             'digest': evidence_core.source_digest(root / 'data.json'),
             'origin': 'recomputed from the held-out split', 'locator': 'field precision'},
            {'id': 'A2', 'type': 'literature', 'reference': 'notes.md',
             'digest': evidence_core.source_digest(root / 'notes.md'),
             'origin': 'reading notes', 'locator': 'paragraph 1'},
        ],
        'evidence': [
            {'id': 'E1', 'claim_id': 'C1', 'artifact_id': 'A1', 'locator': 'field precision',
             'statement': 'Precision was recomputed from the held-out split.', 'state': 'verified',
             'verification_method': 'recomputed', 'headline': True, 'scope': 'held-out split'},
            {'id': 'E2', 'claim_id': 'C2', 'artifact_id': 'A2', 'locator': 'paragraph 1',
             'statement': 'The prior study reports 0.89.', 'state': 'reported',
             'verification_method': 'unverified', 'headline': True, 'scope': 'one prior study'},
        ],
        'missing_context': [],
    }
    return ledger, graph_for(), root


def run(ledger, root, graph=None, text=MANUSCRIPT):
    return el.ledger(text, ledger, graph if graph is not None else graph_for(), root)


class LedgerGateTests(unittest.TestCase):
    def test_bundled_example_passes(self):
        text = (EXAMPLE / 'manuscript.md').read_text(encoding='utf-8')
        ledger = json.loads((EXAMPLE / 'ledger.json').read_text(encoding='utf-8'))
        graph = json.loads((EXAMPLE / 'graph.json').read_text(encoding='utf-8'))
        result = el.ledger(text, ledger, graph, ROOT)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['claim_states'], {'C1': 'verified', 'C2': 'verified', 'C3': 'reported'})

    def test_valid_ledger_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'PASS')
            self.assertEqual(result['unresolved'], [])

    def test_text_artifact_can_never_be_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['evidence'][1].update(state='verified', verification_method='source_inspection')
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertIn('can never be verified', ' '.join(result['errors']))

    def test_text_artifact_cannot_carry_a_verification_act(self):
        """A contradicting paper is recordable, but never as a verification act."""
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['evidence'][1].update(state='contradicted', verification_method='source_inspection')
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertIn('carries no verification act', ' '.join(result['errors']))

    def test_text_artifact_can_report_a_contradiction(self):
        """The gap ledger-dev flagged: a cited paper may refute a claim without verifying it."""
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['evidence'][1].update(state='contradicted', verification_method='unverified')
            result = run(ledger, root, graph)
            self.assertNotIn('carries no verification act', ' '.join(result.get('errors', [])))
            self.assertIn(result['status'], ('FAIL', 'NEEDS_REVIEW'))

    def test_literature_verified_with_unverified_method_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['evidence'][1].update(state='verified', verification_method='unverified')
            self.assertEqual(run(ledger, root, graph)['status'], 'FAIL')

    def test_verified_requires_a_real_verification_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['evidence'][0]['verification_method'] = 'unverified'
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any('verified' in e and 'unverified' in e for e in result['errors']))

    def test_digest_mismatch_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['artifacts'][0]['digest'] = '0' * 64
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any('digest does not match' in e for e in result['errors']))

    def test_missing_artifact_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['artifacts'][0]['reference'] = 'missing.json'
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any('does not resolve to a file' in e for e in result['errors']))

    def test_reference_may_not_escape_the_skill_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['artifacts'][0]['reference'] = '../outside.json'
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any('escapes the skill directory' in e for e in result['errors']))

    def test_verified_claim_needs_a_verified_headline(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['evidence'][0]['headline'] = False
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any('without a verified headline' in e for e in result['errors']))

    def test_at_most_one_headline_per_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            extra = copy.deepcopy(ledger['evidence'][0])
            extra.update(id='E3', headline=True, state='reported', verification_method='unverified')
            ledger['evidence'].append(extra)
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any('more than one headline' in e for e in result['errors']))

    def test_contradiction_outranks_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            contradicting = copy.deepcopy(ledger['evidence'][0])
            contradicting.update(id='E3', state='contradicted', headline=False)
            ledger['evidence'].append(contradicting)
            result = run(ledger, root, graph)
            self.assertEqual(result['claim_states']['C1'], 'contradicted')
            self.assertEqual(result['status'], 'NEEDS_REVIEW')
            self.assertTrue(any('CONTRADICTION_OVERRIDES_VERIFICATION' in e for e in result['escalations']))
            self.assertTrue(any('CONTRADICTED' in u for u in result['unresolved']))

    def test_no_evidence_and_unknown_are_distinct_review_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['claims'].append({'id': 'C3', 'statement': 'One configuration.',
                                     'presented_as_established': True,
                                     **span(MANUSCRIPT, 'Every run used one configuration.')})
            ledger['claims'].append({'id': 'C4', 'statement': 'Drift is stationary.',
                                     'presented_as_established': True,
                                     **span(MANUSCRIPT, 'The drift is stationary across all sensor families.')})
            ledger['evidence'].append({'id': 'E4', 'claim_id': 'C4', 'artifact_id': 'A1',
                                       'locator': 'field precision', 'statement': 'Not resolved.',
                                       'state': 'unknown', 'verification_method': 'unverified',
                                       'headline': True, 'scope': 'unresolved'})
            result = run(ledger, root, graph_for(('C1', 'C2', 'C3', 'C4')))
            self.assertEqual(result['status'], 'NEEDS_REVIEW')
            self.assertEqual(result['no_evidence_claims'], ['C3'])
            self.assertEqual(result['unknown_claims'], ['C4'])
            message = ' '.join(result['unresolved'])
            self.assertIn('NO_EVIDENCE', message)
            self.assertIn('missing evidence', message)
            self.assertIn('UNKNOWN', message)
            self.assertIn('not resolved', message)
            self.assertNotEqual(result['no_evidence_claims'], result['unknown_claims'])

    def test_unknown_claim_id_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['evidence'][0]['claim_id'] = 'C9'
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any('unknown claim node' in e for e in result['errors']))

    def test_evidence_for_undeclared_claim_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['evidence'][0]['claim_id'] = 'C3'
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any('undeclared claim' in e for e in result['errors']))

    def test_incomplete_graph_coverage_needs_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            graph['central_claim_ids'] = ['C1', 'C2', 'C4']
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'NEEDS_REVIEW')
            self.assertEqual(result['coverage_gaps'], ['C4'])
            self.assertTrue(any('incomplete coverage' in u for u in result['unresolved']))

    def test_missing_context_needs_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['missing_context'] = ['author statement of statistical uncertainty']
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'NEEDS_REVIEW')
            self.assertEqual(result['missing_context'], ['author statement of statistical uncertainty'])
            self.assertTrue(any('missing_context' in u for u in result['unresolved']))

    def test_reported_claim_presented_as_established_needs_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['claims'][1]['presented_as_established'] = True
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'NEEDS_REVIEW')
            self.assertEqual(result['reported_but_established'], ['C2'])

    def test_claim_span_must_match_the_manuscript(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            ledger['claims'][0]['location']['start'] += 1
            result = run(ledger, root, graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any('location does not match' in e for e in result['errors']))

    def test_invalid_enums_and_flag_types_are_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            base = copy.deepcopy(ledger)
            for mutate, fragment in (
                    (lambda a: a['evidence'][0].update(state='probably'), 'invalid evidence state'),
                    (lambda a: a['evidence'][0].update(verification_method='vibes'), 'invalid verification method'),
                    (lambda a: a['evidence'][0].update(headline='yes'), 'headline explicitly'),
                    (lambda a: a['evidence'][0].update(conditions=['']), 'conditions')):
                bad = copy.deepcopy(base)
                mutate(bad)
                with self.subTest(fragment=fragment):
                    result = run(bad, root, graph)
                    self.assertEqual(result['status'], 'FAIL')
                    self.assertTrue(any(fragment in e for e in result['errors']))

    def test_malformed_ledger_contracts_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            for broken in ({}, ['not', 'an', 'object'], None):
                with self.subTest(broken=type(broken).__name__):
                    self.assertEqual(run(broken, root, graph)['status'], 'FAIL')
            missing = copy.deepcopy(ledger)
            del missing['evidence']
            result = run(missing, root, graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any('invalid ledger fields' in e for e in result['errors']))
            wrong_list = copy.deepcopy(ledger)
            wrong_list['claims'] = None
            self.assertEqual(run(wrong_list, root, graph)['status'], 'FAIL')
            bad_graph = {'nodes': [{'id': ['unhashable'], 'type': 'Claim'}], 'central_claim_ids': []}
            result = run(ledger, root, bad_graph)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any('invalid ledger artifact' in e for e in result['errors']))

    def test_output_has_no_confidence_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, graph, root = fixture(tmp)
            payload = json.dumps(run(ledger, root, graph))
            self.assertNotIn('confidence', payload)
            self.assertIn('does not certify any claim as true', payload)


class LedgerCliTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'scripts' / 'evidence_ledger.py'), *args],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def test_exit_code_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'manuscript.md').write_text(MANUSCRIPT, encoding='utf-8')
            (root / 'graph.json').write_text(json.dumps(graph_for()), encoding='utf-8')
            ledger, _, _ = fixture(tmp)
            (root / 'ledger.json').write_text(json.dumps(ledger), encoding='utf-8')
            passed = self.cli(str(root / 'manuscript.md'), '--ledger', str(root / 'ledger.json'),
                              '--graph', str(root / 'graph.json'), '--root', str(root))
            self.assertEqual(passed.returncode, 0, passed.stdout)
            self.assertEqual(json.loads(passed.stdout)['status'], 'PASS')

            broken = copy.deepcopy(ledger)
            broken['artifacts'][0]['digest'] = '0' * 64
            (root / 'broken.json').write_text(json.dumps(broken), encoding='utf-8')
            failed = self.cli(str(root / 'manuscript.md'), '--ledger', str(root / 'broken.json'),
                              '--graph', str(root / 'graph.json'), '--root', str(root))
            self.assertEqual(failed.returncode, 3, failed.stdout)
            self.assertEqual(json.loads(failed.stdout)['status'], 'FAIL')

            review = copy.deepcopy(ledger)
            review['missing_context'] = ['author statement of uncertainty']
            (root / 'review.json').write_text(json.dumps(review), encoding='utf-8')
            reviewed = self.cli(str(root / 'manuscript.md'), '--ledger', str(root / 'review.json'),
                                '--graph', str(root / 'graph.json'), '--root', str(root))
            self.assertEqual(reviewed.returncode, 4, reviewed.stdout)
            self.assertEqual(json.loads(reviewed.stdout)['status'], 'NEEDS_REVIEW')

            (root / 'invalid.json').write_text('not json', encoding='utf-8')
            invalid = self.cli(str(root / 'manuscript.md'), '--ledger', str(root / 'invalid.json'),
                               '--graph', str(root / 'graph.json'), '--root', str(root))
            self.assertEqual(invalid.returncode, 4, invalid.stdout)
            self.assertEqual(json.loads(invalid.stdout)['status'], 'INVALID')

    def test_cli_is_read_only(self):
        watched = [EXAMPLE / 'manuscript.md', EXAMPLE / 'ledger.json', EXAMPLE / 'graph.json']
        watched += [EXAMPLE / p for p in ('data/metrics.json', 'logs/run-2024-05-01.log',
                                          'config/run-config.json', 'scripts/reproduce_metrics.py',
                                          'notes/prior-study.md')]
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in watched}
        listing = sorted(x.name for x in EXAMPLE.iterdir())
        result = self.cli(str(EXAMPLE / 'manuscript.md'), '--ledger', str(EXAMPLE / 'ledger.json'),
                          '--graph', str(EXAMPLE / 'graph.json'))
        self.assertEqual(result.returncode, 0, result.stdout)
        for path, snapshot in before.items():
            with self.subTest(path=path.name):
                self.assertEqual(path.read_bytes(), snapshot[0])
                self.assertEqual(path.stat().st_mtime_ns, snapshot[1])
        self.assertEqual(sorted(x.name for x in EXAMPLE.iterdir()), listing)


if __name__ == '__main__':
    unittest.main()
