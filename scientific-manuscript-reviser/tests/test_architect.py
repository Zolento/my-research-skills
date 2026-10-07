import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import architect as ar
import audit_coherence as ac
from compare_invariants import digest
from test_coherence import logic_fixture, finding
from test_invariants import extracted, audit_for


def blueprint_fixture():
    text, graph, report = logic_fixture()
    material = ar.normalize([{'id': 'S', 'text': text}])
    for item in material['items']:
        item['type'] = 'experimental_result' if item['source_span'] == graph['nodes'][3]['source_span'] else 'established_fact'
    evidence_id = material['items'][3]['id']
    claims = [{'id': 'C', 'claim': graph['nodes'][-1]['label'], 'claim_type': 'empirical', 'importance': 'central',
               'evidence': [evidence_id], 'support_status': 'SUPPORTED', 'assumptions': [], 'scope': 'Under Y.',
               'risk_of_overclaim': 'low', 'used_in_sections': ['S1']}]
    p = {'id': 'P1', 'role': 'result', 'purpose': 'Report the bounded mean comparison.', 'claim_ids': ['C'],
         'evidence_ids': [evidence_id], 'logical_predecessor': [], 'logical_successor': [],
         'content_to_include': ['Bounded effect and comparator.'], 'content_to_avoid': ['Mechanism or generality.'],
         'reference_candidates': [], 'paragraph_sketch': 'X improves M by 0.8 under Y. The comparison uses matched compute.',
         'writing_instruction': 'State the bounded observation directly.', 'gap_marker': '', 'finding_ids': []}
    coherence = ac.audit(text, graph, report)
    blueprint = {'schema': 'manuscript-blueprint@1', 'material_digest': digest(material), 'graph_digest': digest(graph),
                 'coherence_digest': digest(coherence), 'depth': 'full', 'claims': claims,
                 'sufficiency': {'supported_claim_ids': ['C'], 'partially_supported_claim_ids': [],
                                 'unsupported_desired_claim_ids': [], 'missing_evidence': [], 'missing_theory': [],
                                 'missing_experiments': [], 'missing_literature_grounding': ['Novelty is not established.']},
                 'theses': [{'id': 'T1', 'text': 'X improves mean M under Y. Matched comparison supports this bounded claim.',
                             'central_claim_id': 'C', 'support_level': 'SUPPORTED', 'main_evidence': [evidence_id],
                             'novelty_delta': 'not established', 'novelty_evidence': [], 'strength': 'Bounded evidence.',
                             'risk': 'No mechanism evidence.', 'best_fit_venue': 'unknown'}],
                 'selected_thesis_id': 'T1',
                 'architectures': [{'id': 'A1', 'central_tension': 'Does X improve M under Y?', 'opening_anchor': 'Matched comparison.',
                                    'claim_order': ['C'], 'strongest_advantage': 'Direct evidence.', 'main_risk': 'Narrow scope.',
                                    'required_evidence': [evidence_id], 'recommended_when': 'Evidence is limited to Y.'}],
                 'recommended_architecture_id': 'A1',
                 'sections': [{'id': 'S1', 'title': 'Results', 'purpose': 'Answer the performance question.', 'claim_ids': ['C'],
                               'subsections': [{'id': 'SS1', 'title': 'Matched performance', 'purpose': 'Test the bounded hypothesis.',
                                                'claim_ids': ['C'], 'evidence_ids': [evidence_id], 'key_transition': 'Connect observation to bounded claim.',
                                                'paragraphs': [p], 'experiment_contract': None}]}],
                 'gaps': [], 'experiment_portfolio': [{'material_id': evidence_id, 'necessity': 'required', 'claim_ids': ['C'], 'logic_gap': ''}],
                 'literature_roles': [], 'outline_options': []}
    audit = outline_review(material, blueprint)
    return material, graph, report, blueprint, audit


def outline_review(material, blueprint):
    # Local structured audit fixture only; not an independent model execution.
    return {'schema': 'blueprint-audit@1', 'blueprint_digest': digest(blueprint), 'material_digest': digest(material),
            'paragraph_checks': [{'paragraph_id': p['id'], 'status': 'PASS', 'rationale': 'Source-bound protocol fixture sketch.'}
                                 for s in blueprint['sections'] for sub in s['subsections'] for p in sub['paragraphs']],
            'outline_checks': {k: {'status': 'PASS', 'rationale': 'Checked this bounded fixture plan.'} for k in ar.OUTLINE_CHECKS},
            'alignment_checks': [{'claim_id': c['id'], 'status': 'PASS', 'rationale': 'Local alignment reviewed.'}
                                 for c in blueprint['claims'] if c['claim_type'] == 'theoretical']}


class ArchitectTests(unittest.TestCase):
    def mutate(self, change, semantic_failure=None):
        args = list(blueprint_fixture())
        change(args)
        args[3]['material_digest'] = digest(args[0])
        args[3]['graph_digest'] = digest(args[1])
        args[2]['graph_digest'] = digest(args[1])
        args[3]['coherence_digest'] = digest(ac.audit(ar.corpus(args[0]), args[1], args[2]))
        args[4] = outline_review(args[0], args[3])
        if semantic_failure:
            args[4]['outline_checks']['no_unsupported_leap'].update(status='FAIL', rationale=semantic_failure)
        return ar.validate_blueprint(*args)

    def test_complete_source_bound_blueprint(self):
        self.assertEqual(ar.validate_blueprint(*blueprint_fixture())['status'], 'PASS')

    def test_normalizer_starts_unknown_not_completed(self):
        m = ar.normalize([{'id': 'S', 'text': 'We plan an experiment. We hypothesize a mechanism.'}])
        self.assertEqual({i['type'] for i in m['items']}, {'unknown'})

    def test_planned_experiment_cannot_establish_result(self):
        result = self.mutate(lambda a: a[0]['items'][3].update(type='planned_experiment'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('planned' in e for e in result['errors']))

    def test_hypothesis_cannot_establish_conclusion(self):
        self.assertEqual(self.mutate(lambda a: a[0]['items'][3].update(type='hypothesis'))['status'], 'FAIL')

    def test_unsupported_desired_claim_is_explicit(self):
        def change(a):
            a[3]['claims'][0]['support_status'] = 'UNSUPPORTED'
            a[3]['sufficiency']['supported_claim_ids'] = []
            a[3]['sufficiency']['unsupported_desired_claim_ids'] = ['C']
            a[3]['theses'][0]['support_level'] = 'UNSUPPORTED'
            p = a[3]['sections'][0]['subsections'][0]['paragraphs'][0]
            p['gap_marker'] = 'SCIENTIFIC GAP TO RESOLVE'
            p['paragraph_sketch'] = 'The desired claim remains untested. Resolve the scientific gap before asserting it.'
        result = self.mutate(change)
        self.assertNotEqual(result['status'], 'FAIL')

    def test_incomplete_material_can_make_bounded_outline(self):
        result = self.mutate(lambda a: a[0]['missing_context'].append('External replication is missing.'))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(result['bounded_outline'])
        self.assertFalse(result['draft_ready'])

    def test_thesis_duplicates_are_not_scientific_alternatives(self):
        def change(a):
            thesis = copy.deepcopy(a[3]['theses'][0])
            thesis.update(id='T2', text='Matched computation makes X convincing under Y.')
            a[3]['theses'].append(thesis)
        self.assertEqual(self.mutate(change)['status'], 'FAIL')

    def test_selected_thesis_cannot_launder_support(self):
        self.assertEqual(self.mutate(lambda a: a[3]['theses'][0].update(support_level='PARTIALLY_SUPPORTED'))['status'], 'FAIL')

    def test_central_thesis_requires_actual_evidence(self):
        self.assertEqual(self.mutate(lambda a: a[3]['theses'][0].update(main_evidence=[]))['status'], 'FAIL')

    def test_every_section_has_purpose(self):
        self.assertEqual(self.mutate(lambda a: a[3]['sections'][0].update(purpose=''))['status'], 'FAIL')

    def test_orphan_subsection(self):
        self.assertEqual(self.mutate(lambda a: a[3]['sections'][0]['subsections'][0].update(claim_ids=[]))['status'], 'FAIL')

    def test_duplicate_result_discussion_fails_semantic_outline_audit(self):
        args = list(blueprint_fixture())
        args[4]['outline_checks']['no_duplicated_role'].update(status='FAIL', rationale='Discussion merely duplicates Results.')
        self.assertEqual(ar.validate_blueprint(*args)['status'], 'FAIL')

    def test_sketch_hard_style_rules(self):
        for punctuation in (';', ':', '—', '–'):
            with self.subTest(punctuation=punctuation):
                result = self.mutate(lambda a: a[3]['sections'][0]['subsections'][0]['paragraphs'][0].update(paragraph_sketch='X improves M' + punctuation + ' the scope is Y.'))
                self.assertEqual(result['status'], 'FAIL')

    def test_sketch_cannot_invent_numeric_result(self):
        result = self.mutate(lambda a: a[3]['sections'][0]['subsections'][0]['paragraphs'][0].update(paragraph_sketch='X improves M by 99.9 under Y.'))
        self.assertEqual(result['status'], 'FAIL')

    def test_theory_alignment_cannot_be_skipped(self):
        args = list(blueprint_fixture())
        args[3]['claims'][0]['claim_type'] = 'theoretical'
        args[4]['blueprint_digest'] = digest(args[3])
        self.assertEqual(ar.validate_blueprint(*args)['status'], 'FAIL')

    def test_theory_assumption_scope_and_decorative_theory_fail_local_audit(self):
        for why in ('Theory exceeds its assumptions.', 'The theorem does not constrain the deployed method.', 'Theory is decorative and unrelated to measurements.'):
            self.assertEqual(self.mutate(lambda a: None, semantic_failure=why)['status'], 'FAIL')

    def test_performance_does_not_support_mechanism(self):
        self.assertEqual(self.mutate(lambda a: None, semantic_failure='Mean performance does not identify the claimed mechanism.')['status'], 'FAIL')

    def test_proposed_experiment_needs_named_gap(self):
        def change(a):
            a[0]['items'][0]['type'] = 'planned_experiment'
            a[3]['experiment_portfolio'].append({'material_id': a[0]['items'][0]['id'], 'necessity': 'required', 'claim_ids': ['C'], 'logic_gap': ''})
        self.assertEqual(self.mutate(change)['status'], 'FAIL')

    def test_redundant_experiment_is_classified(self):
        result = self.mutate(lambda a: a[3]['experiment_portfolio'][0].update(necessity='redundant', logic_gap='No new discrimination beyond the existing comparison.'))
        self.assertEqual(result['status'], 'PASS')

    def test_missing_control_major_finding_cannot_be_hidden(self):
        def change(a):
            a[2]['passes']['experiments']['findings'] = [finding('MISSING_ESSENTIAL_CONTROL')]
            a[2]['aggregation'] = ['I1']
        result = self.mutate(change)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('critical/major scientific issue hidden in the outline', result['errors'])

    def test_literature_role_needs_real_literature(self):
        def change(a):
            a[3]['literature_roles'].append({'material_id': a[0]['items'][3]['id'], 'role': 'closest_prior_method', 'claim_ids': ['C']})
        self.assertEqual(self.mutate(change)['status'], 'FAIL')

    def test_citation_meaning_requires_separate_semantic_check(self):
        self.assertEqual(self.mutate(lambda a: None, semantic_failure='Citation does not establish the attached claim.')['status'], 'FAIL')

    def test_closest_prior_delta_needs_evidence(self):
        self.assertEqual(self.mutate(lambda a: a[3]['theses'][0].update(novelty_delta='We are the first.'))['status'], 'FAIL')

    def test_draft_requires_approval_and_all_generation_gates(self):
        material, graph, report, blue, audit = blueprint_fixture()
        self.assertEqual(ar.validate_section_draft(blue, {'approved': False}, 'S1', 'X.', {})['status'], 'FAIL')

    def test_draft_hierarchy_frozen_and_section_invariance_passes(self):
        material, graph, report, blue, audit = blueprint_fixture()
        draft = blue['sections'][0]['subsections'][0]['paragraphs'][0]['paragraph_sketch']
        facts = extracted(draft, [('claims', draft)])
        contract = {'blueprint_digest': digest(blue), 'section_id': 'S1', 'claim_order': ['C'],
                    'evidence_ids': blue['claims'][0]['evidence'], 'original_facts': facts,
                    'revised_facts': facts, 'semantic_audit': audit_for(draft, draft, facts, facts)}
        approval = {'blueprint_digest': digest(blue), 'approved': True, 'section_ids': ['S1']}
        kwargs = {'material': material, 'graph': graph, 'report': report, 'outline_audit': audit}
        self.assertEqual(ar.validate_section_draft(blue, approval, 'S1', draft, contract, **kwargs)['status'], 'PASS')
        contract['claim_order'] = ['a stronger claim']
        self.assertEqual(ar.validate_section_draft(blue, approval, 'S1', draft, contract, **kwargs)['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
