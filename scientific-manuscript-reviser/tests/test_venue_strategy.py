"""Adversarial tests for venue-aware strategy (venue_strategy.py).

Venue strategy may change framing, ordering and emphasis, never the science.
These tests attack the boundary:

  * an experiment is proposed to resolve a named logic gap, never because a
    venue prefers it,
  * every experiment request declares its identification contract up front, so
    a confounded budget/optimization comparison is refused,
  * a framing rests on a different scientific anchor and cannot foreground a
    contribution beyond its evidence-derived support,
  * a venue-neutral run claims no official requirement.

Known defect fixed by the Lead (regression covered below): the numeric guard used
to scan ``declaration['schema']`` and match the ``1`` in ``venue-strategy@1``.
It now scans only the authored fields, so an empty ``material_numbers`` is the
honest default and no schema-version workaround is needed.

Layering note: ``SemanticEvaluationTests`` use constructed correct/faulty pairs
to enforce the strategy protocol. They do not show that the skill can judge a
real experiment's scientific merit.
"""
import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import compare_invariants as ci
import venue_intelligence_core as vic
import venue_strategy as vs

MANUSCRIPT_DIGEST = 'c' * 64

POSITIONING = {'schema': 'contribution-positioning@1', 'manuscript_digest': MANUSCRIPT_DIGEST,
               'contributions': [{'id': 'C1', 'support_status': 'SUPPORTED',
                                  'claim': 'We present a method that reduces error.',
                                  'evidence_ids': ['E1'], 'claim_ids': ['C1']}],
               'errors': [], 'unresolved': []}

POSITIONING_PLANNED = {'schema': 'contribution-positioning@1',
                       'manuscript_digest': MANUSCRIPT_DIGEST,
                       'contributions': [{'id': 'C1', 'support_status': 'PLANNED',
                                          'claim': 'A planned method.',
                                          'evidence_ids': [], 'claim_ids': ['C1']}],
                       'errors': [], 'unresolved': []}


def blueprint(gap_ids=()):
    return {'schema': 'manuscript-blueprint@1', 'manuscript_digest': MANUSCRIPT_DIGEST,
            'claims': [{'id': 'CL1'}], 'sections': [{'id': 'SEC1', 'subsections': []}],
            'gaps': [{'finding_id': gid} for gid in gap_ids]}


BLUEPRINT = blueprint()
GAP_BLUEPRINT = blueprint(['G1'])

PROFILE = {'schema': 'venue-policy-profile@1', 'venue': 'NeurIPS', 'year': 2025,
           'track': 'main', 'contribution_types': [{'id': 'ct1', 'label': 'Methodological'}],
           'review_criteria': []}


def framing(**over):
    item = {'id': 'F1', 'central_scientific_anchor': 'Identification of the mechanism',
            'opening_move': 'Open with the unresolved identification gap',
            'emphasised_contribution_ids': ['C1'], 'advantage': 'A clear mechanism story',
            'sacrifice': 'Less benchmark breadth', 'best_when': 'The mechanism is the claim',
            'rhetorical_only': False}
    item.update(over)
    return item


def request(**over):
    item = {'id': 'R1', 'resolves_logic_gap': 'G1',
            'hypothesis': 'Capacity-matched training isolates the mechanism',
            'alternative_explanations': ['Optimization budget alone explains the gain',
                                         'Compute alone explains the gain'],
            'comparison_and_control': 'A capacity-matched control on the same split',
            'budget_and_data_parity': 'Identical data, schedule and compute budget',
            'observable': 'Held-out metric with the two factors separated',
            'identifiability': 'Capacity, optimization and compute are held fixed',
            'completion_condition': 'The control closes the gain gap',
            'supports_if': 'The gain persists under the control',
            'refutes_if': 'The gain disappears under the control',
            'justified_by': 'SCIENTIFIC_GAP'}
    item.update(over)
    return item


def declaration(bp=BLUEPRINT, framings=None, section_strategy=None, experiment_requests=None,
                alignment=None, missing_context=None):
    return {'schema': 'venue-strategy@1', 'blueprint_digest': ci.digest(bp),
            'positioning_digest': ci.digest(POSITIONING),
            'framings': [framing()] if framings is None else framings,
            'selected_framing_id': 'F1',
            'section_strategy': [{'section_id': 'SEC1', 'argument_job': 'State the method',
                                  'contribution_ids': ['C1'], 'claim_ids': ['CL1'],
                                  'proportion': 'dominant'}]
            if section_strategy is None else section_strategy,
            'experiment_requests': [] if experiment_requests is None else experiment_requests,
            'venue_alignment': {'contribution_type_ids': ['ct1'],
                                'fit_note': 'The method category matches the published types.'}
            if alignment is None else alignment,
            'missing_context': [] if missing_context is None else missing_context}


def run(audit=None, prof=PROFILE, bp=BLUEPRINT, pos=POSITIONING, numbers=None):
    if audit is None:
        audit = declaration(bp, alignment=None if prof is not None else
                            {'contribution_type_ids': [], 'fit_note': 'Venue-neutral run.'})
        if pos is not POSITIONING:
            audit['positioning_digest'] = ci.digest(pos)
    return vs.validate(bp, pos, audit, prof, set() if numbers is None else numbers)


class DeterministicTests(unittest.TestCase):
    def test_clean_strategy_reaches_pass_with_a_profile(self):
        result = run()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['selected_framing_id'], 'F1')
        self.assertEqual(result['framing_count'], 1)
        self.assertEqual(result['experiment_request_count'], 0)

    def test_theory_strategy_needs_no_experiment_request(self):
        result = run(pos=POSITIONING, bp=blueprint())
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['experiment_request_count'], 0)

    def test_venue_neutral_strategy_is_the_documented_needs_review(self):
        result = run(prof=None)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(any('venue-neutral strategy' in u for u in result['unresolved']))

    def test_blueprint_gap_findings_are_preserved_in_the_output(self):
        result = run(audit=declaration(GAP_BLUEPRINT), bp=GAP_BLUEPRINT)
        self.assertEqual(result['gap_findings_preserved'], ['G1'])

    def test_declared_check_dict_is_not_mutated(self):
        audit = declaration()
        snapshot = copy.deepcopy(audit)
        run(audit=audit)
        self.assertEqual(audit, snapshot)


class ContractTests(unittest.TestCase):
    def test_unknown_declaration_field_is_rejected(self):
        audit = declaration()
        audit['reviewer_persona'] = 'harsh'
        result = run(audit=audit)
        self.assertEqual(result['status'], 'FAIL')

    def test_stale_blueprint_binding_is_rejected(self):
        audit = declaration()
        audit['blueprint_digest'] = '0' * 64
        result = run(audit=audit)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('stale blueprint binding' in e for e in result['errors']))

    def test_unsupported_contribution_cannot_be_emphasised(self):
        audit = declaration(framings=[framing()])
        audit['positioning_digest'] = ci.digest(POSITIONING_PLANNED)
        result = run(audit=audit, pos=POSITIONING_PLANNED)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('cannot upgrade support' in e for e in result['errors']))

    def test_framing_cannot_emphasise_an_unknown_contribution(self):
        result = run(audit=declaration(framings=[framing(
            emphasised_contribution_ids=['C9'])]))
        self.assertEqual(result['status'], 'FAIL')

    def test_rhetorical_only_framing_is_rejected(self):
        result = run(audit=declaration(framings=[framing(rhetorical_only=True)]))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('rhetorical only' in e for e in result['errors']))

    def test_duplicate_scientific_anchor_is_rejected(self):
        second = framing(id='F2')
        result = run(audit=declaration(framings=[framing(), second]))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('repeats another framing anchor' in e for e in result['errors']))

    def test_selected_framing_must_be_declared(self):
        audit = declaration()
        audit['selected_framing_id'] = 'F9'
        result = run(audit=audit)
        self.assertEqual(result['status'], 'FAIL')

    def test_every_blueprint_section_needs_a_strategy_entry(self):
        result = run(audit=declaration(section_strategy=[]))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(any('has no venue strategy entry' in u for u in result['unresolved']))

    def test_unknown_section_is_rejected(self):
        result = run(audit=declaration(section_strategy=[
            {'section_id': 'SEC9', 'argument_job': 'x', 'contribution_ids': [],
             'claim_ids': [], 'proportion': 'dominant'}]))
        self.assertEqual(result['status'], 'FAIL')

    def test_venue_alignment_must_name_a_published_category(self):
        result = run(audit=declaration(alignment={
            'contribution_type_ids': ['ct9'], 'fit_note': 'n'}))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('does not publish' in e for e in result['errors']))

    def test_neutral_strategy_cannot_claim_official_categories(self):
        result = run(audit=declaration(), prof=None)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('venue-neutral strategy cannot claim' in e for e in result['errors']))

    def test_missing_context_forces_needs_review(self):
        result = run(audit=declaration(missing_context=['The blueprint gap list is partial.']))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_invented_number_is_rejected(self):
        # The schema version must not excuse a number that is not in the material.
        audit = declaration()
        audit['section_strategy'][0]['proportion'] = '1.5'
        result = run(audit=audit, numbers=set())
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('1.5' in e for e in result['errors']))

    def test_clean_strategy_passes_with_no_material_numbers(self):
        self.assertEqual(run(numbers=set())['status'], 'PASS')

    def test_material_numbers_are_accepted(self):
        audit = declaration()
        audit['section_strategy'][0]['proportion'] = '40 percent'
        result = run(audit=audit, numbers={'40'})
        self.assertEqual(result['status'], 'PASS')


class SemanticEvaluationTests(unittest.TestCase):
    """Constructed correct/faulty pairs: protocol enforcement, not merit judgement."""

    def test_experiment_request_requires_a_named_blueprint_gap(self):
        # CORRECT: the request resolves a gap recorded in the blueprint.
        correct = run(audit=declaration(GAP_BLUEPRINT, experiment_requests=[request()]),
                      bp=GAP_BLUEPRINT)
        self.assertEqual(correct['status'], 'PASS')

        # FAULTY: same request, but it resolves no recorded logic gap.
        faulty = run(audit=declaration(GAP_BLUEPRINT,
                                       experiment_requests=[request(resolves_logic_gap='GX')]),
                     bp=GAP_BLUEPRINT)
        self.assertEqual(faulty['status'], 'FAIL')
        self.assertTrue(any('does not resolve a logic gap' in e for e in faulty['errors']))

    def test_experiment_request_cannot_be_justified_by_venue_preference(self):
        for justification in ('VENUE_PREFERENCE', 'REVIEWER_EXPECTATION', 'SOTA_COMPARISON'):
            with self.subTest(justification=justification):
                result = run(audit=declaration(
                    GAP_BLUEPRINT, experiment_requests=[request(justified_by=justification)]),
                    bp=GAP_BLUEPRINT)
                self.assertEqual(result['status'], 'FAIL')
                self.assertTrue(any('not by venue preference' in e for e in result['errors']))

    def test_scientific_gap_and_identifiability_are_the_only_justifications(self):
        for justification in ('SCIENTIFIC_GAP', 'IDENTIFIABILITY'):
            with self.subTest(justification=justification):
                result = run(audit=declaration(
                    GAP_BLUEPRINT, experiment_requests=[request(justified_by=justification)]),
                    bp=GAP_BLUEPRINT)
                self.assertEqual(result['status'], 'PASS')
                self.assertEqual(result['experiment_request_count'], 1)

    def test_confounded_experiment_requires_budget_and_data_parity(self):
        result = run(audit=declaration(
            GAP_BLUEPRINT, experiment_requests=[request(budget_and_data_parity='')]),
            bp=GAP_BLUEPRINT)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('needs a nonempty budget_and_data_parity' in e
                            for e in result['errors']))

    def test_confounded_experiment_requires_a_control_comparison(self):
        result = run(audit=declaration(
            GAP_BLUEPRINT, experiment_requests=[request(comparison_and_control='')]),
            bp=GAP_BLUEPRINT)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('comparison_and_control' in e for e in result['errors']))

    def test_confounded_experiment_must_name_alternative_explanations(self):
        result = run(audit=declaration(
            GAP_BLUEPRINT, experiment_requests=[request(alternative_explanations=[])]),
            bp=GAP_BLUEPRINT)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('alternative explanations' in e for e in result['errors']))

    def test_experiment_request_needs_a_completion_condition(self):
        result = run(audit=declaration(
            GAP_BLUEPRINT, experiment_requests=[request(completion_condition='')]),
            bp=GAP_BLUEPRINT)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('completion_condition' in e for e in result['errors']))

    def test_incomplete_identification_contract_is_rejected(self):
        incomplete = request()
        del incomplete['identifiability']
        result = run(audit=declaration(GAP_BLUEPRINT, experiment_requests=[incomplete]),
                     bp=GAP_BLUEPRINT)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('full identification contract' in e for e in result['errors']))


class EndToEndTests(unittest.TestCase):
    def test_request_ids_must_be_unique(self):
        result = run(audit=declaration(GAP_BLUEPRINT,
                                       experiment_requests=[request(), request()]),
                     bp=GAP_BLUEPRINT)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('duplicate experiment request id' in e for e in result['errors']))

    def test_authoritative_blueprint_is_not_replaced(self):
        result = run()
        self.assertEqual(result['schema'], 'venue-strategy@1')
        self.assertEqual(result['gap_findings_preserved'], [])

    def test_strategy_json_round_trip_keeps_the_verdict(self):
        result = run()
        self.assertEqual(json.loads(json.dumps(result))['status'], 'PASS')

    def test_core_repair_kinds_are_the_shared_vocabulary(self):
        self.assertIn('NEW_EXPERIMENT', vic.REPAIR_KINDS)
        self.assertIn('TEXT_ONLY', vic.REPAIR_KINDS)


if __name__ == '__main__':
    unittest.main()
