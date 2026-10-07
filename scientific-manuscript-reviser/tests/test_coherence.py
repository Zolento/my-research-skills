import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import audit_coherence as ac
from compare_invariants import digest


def logic_fixture(theory=False):
    records = [('Q', 'Research question', 'Does X improve M under protocol Y?'),
               ('H', 'Hypothesis', 'X improves M under protocol Y.'),
               ('E', 'Experimental design', 'We compare X and P with matched compute under Y.'),
               ('O', 'Observation', 'X improves M by 0.8 under Y.'),
               ('C', 'Claim', 'X improves mean M under Y.')]
    if theory:
        records.extend([('D', 'Definition', 'Let x be in the bounded domain.'),
                        ('T', 'Theorem', 'The bound holds in the bounded domain.')])
    text = '\n\n'.join(x[2] for x in records)
    nodes = [{'id': i, 'type': typ, 'label': span, 'source_span': span,
              'location': {'start': text.index(span), 'end': text.index(span) + len(span)},
              'context': 'Toy fixture paragraph ' + str(j + 1)} for j, (i, typ, span) in enumerate(records)]
    links = [('E1', 'E', 'H', 'tests'), ('E2', 'Q', 'H', 'motivates'),
             ('E3', 'E', 'O', 'measures'), ('E4', 'O', 'C', 'supports')]
    if theory:
        links.extend([('E5', 'D', 'T', 'derives'), ('E6', 'T', 'C', 'supports')])
    edges = [{'id': i, 'source': s, 'target': t, 'type': typ, 'reasoning_type': 'statistical',
              'location': copy.deepcopy(nodes[0]['location']), 'source_span': nodes[0]['source_span']}
             for i, s, t, typ in links]
    graph = {'schema': 'scientific-argument-graph@1', 'manuscript_digest': digest(text),
             'document_scope': 'whole_paper', 'missing_context': [], 'nodes': nodes,
             'edges': edges, 'central_claim_ids': ['C'], 'main_chain': ['Q', 'H', 'E', 'O', 'C']}
    report = {'schema': 'scientific-coherence-audit@1', 'manuscript_digest': digest(text),
              'graph_digest': digest(graph),
              'passes': {p: {'status': 'NOT_APPLICABLE' if p == 'theory' and not theory else 'COMPLETE',
                             'examined_node_ids': [n['id'] for n in nodes], 'findings': []} for p in ac.PASSES},
              'edge_checks': [{'edge_id': e['id'], 'reasoning_type': e['reasoning_type'], 'verdict': 'supported',
                               'why': 'Located relation checked for this protocol fixture.'} for e in edges],
              'rq_matrix': [{'rq_id': 'Q', 'hypothesis_ids': ['H'], 'experiment_ids': ['E'], 'result_ids': ['O'],
                             'claim_ids': ['C'], 'identifiable': 'PASS', 'testable': 'PASS',
                             'support_condition': 'Higher M under Y.', 'refute_condition': 'No higher M under Y.',
                             'permitted_conclusion': 'Bounded mean performance comparison.'}],
              'proof_steps': [{'id': 'S1', 'proposition_id': 'T', 'location': nodes[-1]['location'],
                               'source_span': nodes[-1]['source_span'], 'dependencies': [{'kind': 'definition', 'id': 'D'}],
                               'verdict': 'VERIFIED_LOCALLY', 'why': 'Protocol coverage example, not a proof benchmark.'}] if theory else [],
              'counterfactuals': [{'claim_id': 'C', 'question': 'Could the comparison persist without a mechanism?',
                                   'alternative_explanations': ['Optimization may explain it; no mechanism asserted.'],
                                   'discriminating_evidence_ids': ['O'], 'verdict': 'SUPPORTED',
                                   'why': 'Claim only concerns matched mean comparison.'}],
              'scorecard': {s: {'level': 'adequate', 'evidence_node_ids': ['O'], 'finding_ids': [],
                               'why': 'Protocol fixture judgment, not measured model performance.'} for s in ac.SCORECARD},
              'well_supported': [{'node_ids': ['C'], 'edge_ids': ['E4'], 'why': 'Located bounded comparison.'}],
              'aggregation': []}
    return text, graph, report


def finding(code, severity='major', verdict='UNSUPPORTED', category='scientific_logic'):
    return {'id': 'I1', 'code': code, 'category': category, 'severity': severity, 'confidence': 'high',
            'evidence_node_ids': ['C', 'O'], 'reasoning_type': 'statistical', 'verdict': verdict,
            'why': 'Locally checked counterexample from supplied manuscript spans.',
            'alternative_interpretation': 'The narrower comparison may still hold.',
            'verification_needed': 'Resolve the missing identification or derivation before acceptance.',
            'verification_status': 'INTERNAL_CHECKED', 'basis': 'INTERNAL INCONSISTENCY', 'external_sources': [],
            'repairs': [{'id': 'A', 'option': 'Calibrate the asserted claim after author resolution.', 'requires': 'requires_text_change_only'},
                        {'id': 'B', 'option': 'Obtain evidence distinguishing the alternative.', 'requires': 'requires_new_experiment'}]}


class CoherenceTests(unittest.TestCase):
    def test_valid_claim_evidence_chain(self):
        self.assertEqual(ac.audit(*logic_fixture())['status'], 'PASS')

    def test_valid_dependency_chain(self):
        self.assertEqual(ac.audit(*logic_fixture(theory=True))['status'], 'PASS')

    def test_unsupported_central_edge(self):
        text, graph, report = logic_fixture()
        report['edge_checks'][-1].update(verdict='unsupported', why='Result does not establish this claim.')
        self.assertEqual(ac.audit(text, graph, report)['status'], 'FAIL')

    def test_orphan_claim(self):
        text, graph, _ = logic_fixture()
        graph['edges'] = [e for e in graph['edges'] if e['type'] != 'supports']
        self.assertIn('ORPHAN_CLAIM', [f['code'] for f in ac.audit(text, graph)['structural_diagnostics']])

    def test_orphan_experiment(self):
        _, graph, _ = logic_fixture()
        graph['edges'] = [e for e in graph['edges'] if e['type'] != 'tests']
        self.assertIn('ORPHAN_EXPERIMENT', [f['code'] for f in ac.topology(graph)])

    def test_circular_justification(self):
        _, graph, _ = logic_fixture()
        edge = copy.deepcopy(graph['edges'][-1])
        edge.update(id='E5', source='C', target='O')
        graph['edges'].append(edge)
        self.assertIn('CIRCULAR_ARGUMENT', [f['code'] for f in ac.topology(graph)])

    def test_untested_hypothesis(self):
        _, graph, _ = logic_fixture()
        graph['edges'] = [e for e in graph['edges'] if e['type'] != 'tests']
        self.assertIn('UNTESTED_HYPOTHESIS', [f['code'] for f in ac.topology(graph)])

    def test_local_semantic_counterexample_contracts(self):
        # These are local-judge verdict fixtures, not regex detection or an LLM benchmark.
        cases = ('SCOPE_DRIFT', 'HIDDEN_ASSUMPTION', 'THEOREM_SCOPE_INFLATION',
                 'LOCAL_TO_GLOBAL_LEAP', 'ASYMPTOTIC_TO_FINITE_SAMPLE_LEAP', 'THEORY_METHOD_GAP',
                 'UNFAIR_COMPUTE_BASELINE', 'MISSING_ESSENTIAL_CONTROL', 'CONFOUNDED_ABLATION',
                 'ROBUSTNESS_SCOPE_INFLATION', 'CORRELATION_TO_CAUSATION', 'PERFORMANCE_TO_MECHANISM',
                 'MEAN_GAIN_TO_ROBUSTNESS', 'NON_SIGNIFICANCE_TO_EQUIVALENCE', 'LIMITED_TO_UNIVERSAL',
                 'ABSTRACT_RESULTS_MISMATCH', 'NEW_CONCLUSION_CLAIM', 'UNEVALUATED_CONTRIBUTION',
                 'NUMERICAL_INCONSISTENCY', 'ASSUMPTION_DRIFT')
        for code in cases:
            with self.subTest(code=code):
                text, graph, report = logic_fixture()
                report['passes']['entailment']['findings'] = [finding(code)]
                report['aggregation'] = ['I1']
                result = ac.audit(text, graph, report)
                self.assertEqual(result['status'], 'FAIL')
                self.assertEqual(result['findings'][0]['code'], code)

    def test_data_leakage_critical(self):
        text, graph, report = logic_fixture()
        report['passes']['experiments']['findings'] = [finding('DATA_LEAKAGE', severity='critical')]
        report['aggregation'] = ['I1']
        result = ac.audit(text, graph, report)
        self.assertEqual(result['findings'][0]['severity'], 'critical')
        self.assertEqual(result['status'], 'FAIL')
        report['passes']['experiments']['findings'][0]['severity'] = 'minor'
        self.assertIn('central-result data leakage must be Critical', ac.audit(text, graph, report)['errors'])

    def test_isolated_ablation_and_calibrated_claim_well_supported(self):
        result = ac.audit(*logic_fixture())
        self.assertEqual(result['status'], 'PASS')
        self.assertTrue(result['well_supported'])

    def test_unnecessary_self_weakening_underclaim(self):
        text, graph, report = logic_fixture()
        report['passes']['entailment']['findings'] = [finding('UNDERCLAIM', severity='moderate')]
        report['aggregation'] = ['I1']
        self.assertEqual(ac.audit(text, graph, report)['findings'][0]['code'], 'UNDERCLAIM')

    def test_unknown_proof_not_verified(self):
        text, graph, report = logic_fixture(theory=True)
        report['proof_steps'][0]['verdict'] = 'NOT_VERIFIED'
        self.assertEqual(ac.audit(text, graph, report)['status'], 'NEEDS_REVIEW')

    def test_missing_local_pass_or_edge_coverage_fails(self):
        for mutate in (lambda r: r['passes'].pop('counterfactual'), lambda r: r['edge_checks'].pop(),
                       lambda r: r['passes']['cross_section']['examined_node_ids'].clear()):
            text, graph, report = logic_fixture()
            mutate(report)
            self.assertEqual(ac.audit(text, graph, report)['status'], 'FAIL')

    def test_aggregator_cannot_create_criticism(self):
        text, graph, report = logic_fixture()
        report['aggregation'] = ['Invented criticism']
        self.assertEqual(ac.audit(text, graph, report)['status'], 'FAIL')

    def test_partial_section_never_certifies_whole_paper(self):
        text, graph, report = logic_fixture()
        graph['document_scope'] = 'section'
        report['graph_digest'] = digest(graph)
        self.assertEqual(ac.audit(text, graph, report)['status'], 'NEEDS_REVIEW')

    def test_external_concern_requires_external_verification(self):
        text, graph, report = logic_fixture()
        f = finding('MISSING_BASELINE')
        f.update(basis='EXTERNAL SCIENTIFIC CONCERN', verification_status='NEEDS_EXTERNAL_VERIFICATION')
        report['passes']['experiments']['findings'] = [f]
        report['aggregation'] = ['I1']
        self.assertEqual(ac.audit(text, graph, report)['status'], 'NEEDS_REVIEW')


if __name__ == '__main__':
    unittest.main()
