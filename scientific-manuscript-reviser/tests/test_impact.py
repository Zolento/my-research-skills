import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import revision_impact as ri
from compare_invariants import CATEGORIES, digest

BEFORE = ('# Abstract\n\nWe report that X improves Y.\n\n'
          '# Results\n\nUnder protocol Z, X improves Y by 0.8 dB.\n\n'
          '# Limitations\n\nThis applies only to the tested protocol.\n')
AFTER = ('# Abstract\n\nWe report X improves Y.\n\n'
         '# Results\n\nUnder protocol Z, the gain in Y is 0.8 dB.\n\n'
         '# Limitations\n\nThis applies to the tested protocol.\n')
CLAIM, OBSERVATION, LIMITATION = ('We report that X improves Y.',
                                  'Under protocol Z, X improves Y by 0.8 dB.',
                                  'This applies only to the tested protocol.')


def facts(text, statements):
    out = []
    for index, (category, span) in enumerate(statements):
        start = text.index(span)
        out.append({'id': 'F%d' % index, 'category': category, 'statement': span,
                    'location': {'start': start, 'end': start + len(span)}, 'source_span': span})
    return {'schema': 'manuscript-invariants@1', 'manuscript_digest': digest(text),
            'covered_categories': list(CATEGORIES),
            'absent_categories': sorted(set(CATEGORIES) - {f['category'] for f in out}),
            'facts': out, 'unresolved': []}


BEFORE_FACTS = facts(BEFORE, [('claims', CLAIM), ('metrics', OBSERVATION), ('limitations', LIMITATION)])
AFTER_FACTS = facts(AFTER, [('claims', 'We report X improves Y.'),
                            ('metrics', 'Under protocol Z, the gain in Y is 0.8 dB.'),
                            ('limitations', 'This applies to the tested protocol.')])


def node(nid, ntype, span, context):
    return {'id': nid, 'type': ntype, 'label': span, 'source_span': span,
            'location': {'start': BEFORE.index(span), 'end': BEFORE.index(span) + len(span)},
            'context': context}


def graph_for(text):
    nodes = [node('C', 'Claim', CLAIM, 'Abstract'), node('O', 'Observation', OBSERVATION, 'Results'),
             node('L', 'Limitation', LIMITATION, 'Limitations')]
    edges = [{'id': 'G1', 'source': 'O', 'target': 'C', 'type': 'supports',
              'reasoning_type': 'statistical', 'location': copy.deepcopy(nodes[0]['location']),
              'source_span': CLAIM},
             {'id': 'G2', 'source': 'L', 'target': 'C', 'type': 'qualifies',
              'reasoning_type': 'statistical', 'location': copy.deepcopy(nodes[2]['location']),
              'source_span': LIMITATION}]
    return {'schema': 'scientific-argument-graph@1', 'manuscript_digest': digest(text),
            'document_scope': 'whole_paper', 'missing_context': [], 'nodes': nodes, 'edges': edges,
            'central_claim_ids': ['C'], 'main_chain': ['C']}


GRAPH = graph_for(BEFORE)


def edit(eid, span, replacement, depth='language_layer', risk='low', **extra):
    start = BEFORE.index(span)
    item = {'id': eid, 'location': {'start': start, 'end': start + len(span)}, 'original_span': span,
            'replacement': replacement, 'depth': depth, 'scientific_risk': risk}
    item.update(extra)
    return item


LANG = edit('E1', 'We report that', 'We report')
SCI = edit('E2', OBSERVATION, 'Under protocol Z, the gain in Y is 0.8 dB.',
           depth='scientific_content', risk='medium')
LIMIT = edit('E3', LIMITATION, 'This applies to the tested protocol.',
             depth='scientific_content', risk='medium', loses_limitation=True)


def run(plan, graph=GRAPH, before_facts=BEFORE_FACTS, after_facts=AFTER_FACTS, manuscript=AFTER):
    return ri.analyze(manuscript, BEFORE, before_facts, after_facts, plan, graph)


class ImpactTests(unittest.TestCase):
    def test_language_layer_edit_kept_at_minimal_sufficient_check(self):
        result = run([LANG])
        edit_result = result['edits'][0]
        self.assertEqual(edit_result['depth'], 'language_layer')
        self.assertEqual(edit_result['required_audits'], ['minimal_sufficient_check'])
        self.assertTrue(edit_result['auto_acceptable'])
        self.assertEqual(edit_result['decision'], 'auto_acceptable')
        self.assertEqual(result['status'], 'PASS')
        self.assertTrue(result['auto_acceptable'])
        self.assertEqual(result['blocked'], [])

    def test_language_layer_above_low_risk_needs_full_audit(self):
        result = run([edit('E1', 'We report that', 'We report', risk='medium')])
        self.assertEqual(result['edits'][0]['required_audits'], ['full_semantic_audit'])
        self.assertEqual(result['status'], 'PASS')

    def test_scientific_content_always_needs_full_audit(self):
        result = run([SCI])
        edit_result = result['edits'][0]
        self.assertEqual(edit_result['depth'], 'scientific_content')
        self.assertEqual(edit_result['required_audits'], ['full_semantic_audit'])
        self.assertTrue(edit_result['auto_acceptable'])
        self.assertEqual(result['status'], 'PASS')

    def test_repair_requires_reanalysis_forces_scientific_depth(self):
        result = run([edit('E1', 'We report that', 'We report',
                           selected_repair_requires='requires_reanalysis')])
        edit_result = result['edits'][0]
        self.assertEqual(edit_result['depth'], 'scientific_content')
        self.assertEqual(edit_result['required_audits'],
                         ['full_semantic_audit', 'needs_reanalysis'])
        self.assertFalse(edit_result['auto_acceptable'])
        self.assertEqual(edit_result['decision'], 'blocked')
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertFalse(result['auto_acceptable'])
        self.assertIn('E1', result['blocked'])
        self.assertEqual(result['escalations'][0]['issue'], ri.SCIENTIFIC_REPAIR_NEEDS_NEW_EVIDENCE)

    def test_new_experiment_and_theory_repairs_force_their_audits(self):
        for repair, audit in (('requires_new_experiment', 'needs_new_experiment'),
                              ('requires_new_theory', 'needs_new_theory')):
            result = run([edit('E1', 'We report that', 'We report', selected_repair_requires=repair)])
            self.assertIn(audit, result['edits'][0]['required_audits'])

    def test_text_change_only_does_not_force_depth(self):
        result = run([edit('E1', 'We report that', 'We report',
                           selected_repair_requires='requires_text_change_only')])
        edit_result = result['edits'][0]
        self.assertEqual(edit_result['depth'], 'language_layer')
        self.assertEqual(edit_result['required_audits'], ['minimal_sufficient_check'])
        self.assertTrue(edit_result['auto_acceptable'])
        self.assertEqual(result['status'], 'PASS')

    def test_lost_limitation_blocks_auto_acceptance(self):
        result = run([LIMIT])
        edit_result = result['edits'][0]
        self.assertFalse(edit_result['auto_acceptable'])
        self.assertEqual(edit_result['decision'], 'blocked')
        self.assertFalse(result['auto_acceptable'])
        self.assertEqual(result['blocked'], ['E3'])
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['escalations'][0]['issue'], ri.LIMITATION_GUARD)
        self.assertEqual(result['escalations'][0]['status'], 'pending')

    def test_new_reference_without_original_fact_blocks(self):
        result = run([edit('E1', 'We report that', 'We report', new_reference_ids=['F99'])])
        self.assertFalse(result['auto_acceptable'])
        self.assertEqual(result['escalations'][0]['issue'], ri.NEW_ASSERTION_WITHOUT_ORIGINAL_FACT)

    def test_reference_to_an_original_fact_is_allowed(self):
        result = run([edit('E1', 'We report that', 'We report', new_reference_ids=['F0'])])
        self.assertTrue(result['edits'][0]['auto_acceptable'])
        self.assertEqual(result['status'], 'PASS')

    def test_claimed_raise_to_verified_blocks_and_forces_content(self):
        result = run([edit('E1', 'We report that', 'We report', raises_to_verified=True)])
        edit_result = result['edits'][0]
        self.assertEqual(edit_result['depth'], 'scientific_content')
        self.assertFalse(edit_result['auto_acceptable'])
        self.assertEqual(result['escalations'][0]['issue'], ri.CLAIM_RAISED_TO_VERIFIED)

    def test_declared_auto_acceptance_on_a_blocked_edit_fails(self):
        result = run([edit('E3', LIMITATION, 'This applies to the tested protocol.',
                           depth='scientific_content', risk='medium', loses_limitation=True,
                           auto_acceptable=True)])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('declares auto-acceptance' in e for e in result['errors']))

    def test_introduced_punctuation_is_reported_and_not_rewritten(self):
        result = run([edit('E1', 'We report that', 'We report; the gain follows')])
        edit_result = result['edits'][0]
        self.assertEqual(edit_result['introduced_punctuation'], [';'])
        self.assertEqual(edit_result['replacement'], 'We report; the gain follows')
        self.assertFalse(edit_result['auto_acceptable'])
        self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_introduced_punctuation_is_listed_once_per_character(self):
        result = run([edit('E1', 'We report that', 'We report; that;')])
        self.assertEqual(result['edits'][0]['introduced_punctuation'], [';'])

    def test_edit_without_new_punctuation_reports_none(self):
        result = run([edit('E1', 'We report that', 'We report')])
        self.assertEqual(result['edits'][0]['introduced_punctuation'], [])

    def test_original_span_must_be_exact(self):
        bad = edit('E1', 'We report that', 'We report')
        bad['location'] = {'start': 1, 'end': 15}
        result = run([bad])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('exact span' in e for e in result['errors']))

    def test_unknown_plan_field_is_rejected(self):
        result = run([edit('E1', 'We report that', 'We report', inferred_from_prose=True)])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('unknown fields' in e for e in result['errors']))

    def test_missing_graph_stays_needs_review_without_impacts(self):
        result = run([LANG], graph=None)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['edits'][0]['impacts'], [])
        self.assertEqual(result['edits'][0]['decision'], 'requires_review')
        self.assertTrue(result['unresolved'])
        self.assertFalse(result['auto_acceptable'])

    def test_cross_section_divergence_is_reported(self):
        result = run([LANG])
        impacts = result['edits'][0]['impacts']
        kinds = {(i['element_id'], i['kind']) for i in impacts}
        self.assertIn(('C', 'claim'), kinds)
        self.assertIn(('O', 'cross_section'), kinds)
        self.assertIn(('L', 'cross_section'), kinds)

    def test_dependent_element_kinds_follow_the_graph_contract(self):
        result = run([SCI])
        impacts = result['edits'][0]['impacts']
        self.assertEqual([(i['element_id'], i['kind']) for i in impacts], [('O', 'evidence')])

    def test_invalid_facts_fail(self):
        bad = copy.deepcopy(AFTER_FACTS)
        bad['manuscript_digest'] = 'wrong'
        result = run([LANG], after_facts=bad)
        self.assertEqual(result['status'], 'FAIL')

    def test_empty_plan_is_needs_review(self):
        result = run([])
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(result['unresolved'])

    def test_note_states_declared_judgment_boundary(self):
        result = run([LANG])
        self.assertIn('declarations', result['note'])
        self.assertIn('does not judge scientific truth', result['note'])

    def test_bundled_example_runs_and_keeps_depths_separate(self):
        root = pathlib.Path(__file__).resolve().parents[1] / 'examples' / 'revision-impact'
        read = lambda name: (root / name).read_text(encoding='utf-8')
        load = lambda name: json.loads(read(name))
        result = ri.analyze(read('after.md'), read('before.md'), load('before-facts.json'),
                            load('after-facts.json'), load('plan.json'), load('graph.json'))
        self.assertEqual(result['status'], 'PASS')
        depths = {e['id']: e['required_audits'] for e in result['edits']}
        self.assertEqual(depths['E1'], ['minimal_sufficient_check'])
        self.assertEqual(depths['E2'], ['full_semantic_audit'])
        self.assertTrue(any(i['kind'] == 'cross_section' for i in result['edits'][0]['impacts']))


if __name__ == '__main__':
    unittest.main()
