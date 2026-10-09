"""Adversarial tests for contribution positioning (contribution_positioning.py).

The positioning gate must keep two things apart: the support status of a
contribution, which is derived only from evidence, and the venue fit of that
contribution, which is venue-dependent. These tests attack that separation:

  * swapping the venue must not move any support status or scientific finding,
  * wording must never raise novelty or soundness without inspected prior work,
  * a negative result is evidence-derived and is never auto-foregrounded,
  * partial input can never yield a whole-paper PASS.

Layering note: ``SemanticEvaluationTests`` use explicitly constructed
correct/faulty argument pairs. They enforce the protocol (a novelty assertion
without prior work is rejected); they do not show that the skill detects real
scientific errors, and a PASS here says nothing about a real paper.
"""
import copy
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import audit_coherence as ac
import compare_invariants as ci
import contribution_positioning as cp
import venue_intelligence_core as vic

MANUSCRIPT_DIGEST = 'f' * 64


def graph_for(claim_ids=('C1',), central=('C1',)):
    return {'schema': 'scientific-argument-graph@1', 'manuscript_digest': MANUSCRIPT_DIGEST,
            'document_scope': 'whole_paper', 'missing_context': [],
            'nodes': [{'id': cid, 'type': 'Claim'} for cid in claim_ids],
            'edges': [], 'central_claim_ids': list(central), 'main_chain': list(central)}


GRAPH = graph_for()


def ledger_for(states):
    """states: {claim_id: ledger_state or None}. Missing/None means no record."""
    records = []
    for index, (cid, state) in enumerate(states.items()):
        if state is None:
            continue
        records.append({'id': 'E%d' % index, 'claim_id': cid, 'state': state,
                        'reference': 'record %d' % index})
    return {'schema': 'evidence-ledger@1', 'manuscript_digest': MANUSCRIPT_DIGEST,
            'evidence': records}


VERIFIED = ledger_for({'C1': 'verified'})
REPORTED = ledger_for({'C1': 'reported'})
UNKNOWN_EVIDENCE = ledger_for({'C1': 'unknown'})
CONTRADICTED = ledger_for({'C1': 'contradicted'})
NO_EVIDENCE = ledger_for({'C1': None})


def checked_prior(reference='Smith 2020', digest='sha256:' + 'b' * 16):
    return [{'status': 'CHECKED', 'reference': reference, 'digest': digest}]


def contribution(**over):
    item = {'id': 'C1', 'internal_type': 'algorithmic_methodological', 'role': 'primary',
            'claim': 'We present a method that reduces error.',
            'claim_ids': ['C1'], 'novelty': 'NOT_CLAIMED',
            'novelty_delta': 'A different combination of existing components.',
            'prior_work': [], 'closest_prior_work': None,
            'structural_equivalence': {'is_structurally_equivalent': False,
                                       'twin_reference': None,
                                       'distinguishing_property': None},
            'official_category': None, 'not_replaceable_by': None, 'evidence_limits': None}
    item.update(over)
    return item


def declaration(contributions=None, specified=False, venue=None, missing_context=None):
    target = {'venue': venue, 'year': 2025, 'track': 'main', 'specified': specified}
    return {'schema': 'contribution-positioning@1', 'manuscript_digest': MANUSCRIPT_DIGEST,
            'target_venue': target,
            'contributions': [contribution()] if contributions is None else contributions,
            'missing_context': [] if missing_context is None else missing_context}


def run(ledger=None, contributions=None, specified=False, venue=None, registry=None,
        missing_context=None, graph=GRAPH):
    return cp.validate(graph, None, ledger if ledger is not None else VERIFIED,
                       declaration(contributions, specified, venue, missing_context),
                       registry)


class RegistryMixin:
    """A registry with two different venues for the same paper year and track."""

    OFFICIAL_LABEL = 'Methodological contribution'

    def two_venue_registry(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        (root / 'sources').mkdir()
        (root / 'profiles').mkdir()
        for venue in ('NeurIPS', 'ICML'):
            (root / 'profiles' / (venue + '.json')).write_text(
                json.dumps({'schema': 'venue-policy-profile@1', 'profile_version': 1,
                            'venue': venue, 'year': 2025, 'track': 'main',
                            'verification_date': '2025-05-01', 'sources': [],
                            'contribution_types': [{'id': 'ct1',
                                                    'claim_kind': 'REVIEW_CRITERION',
                                                    'label': self.OFFICIAL_LABEL,
                                                    'scope': 'Method contributions',
                                                    'quote': 'quote text long enough',
                                                    'source_id': 's1'}],
                            'review_criteria': [],
                            'mandatory_policy': [], 'recommended_practice': [],
                            'compliance_checks': [], 'changes_from_prior_year': [],
                            'unknown_policies': []}), encoding='utf-8')
        return root


class DeterministicTests(unittest.TestCase):
    def test_clean_positioning_reaches_pass(self):
        result = run()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['support_status_values'], {'C1': 'SUPPORTED'})
        self.assertEqual(result['primary_contribution_ids'], ['C1'])
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['unresolved'], [])
        # No profile -> the official category mapping is explicitly unavailable.
        self.assertEqual(result['contributions'][0]['mapping_verdict'], 'NOT_PUBLISHED')

    def test_checked_prior_work_allows_a_declared_incremental_delta(self):
        item = contribution(novelty='INCREMENTAL_DELTA', prior_work=checked_prior(),
                            closest_prior_work='Smith 2020')
        result = run(contributions=[item])
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['contributions'][0]['novelty'], 'INCREMENTAL_DELTA')

    def test_every_ledger_state_maps_to_its_own_support_status(self):
        expected = [(VERIFIED, 'SUPPORTED'), (REPORTED, 'PARTIALLY_SUPPORTED'),
                    (UNKNOWN_EVIDENCE, 'UNKNOWN'), (CONTRADICTED, 'UNSUPPORTED')]
        for ledger, status in expected:
            with self.subTest(status=status):
                result = run(ledger=ledger)
                self.assertEqual(result['support_status_values']['C1'], status)

    def test_support_status_is_derived_from_evidence_not_prose(self):
        strong_prose = contribution(claim='Our results definitively prove the mechanism.')
        weak = run(ledger=REPORTED, contributions=[strong_prose])
        strong = run(ledger=VERIFIED, contributions=[strong_prose])
        self.assertEqual(weak['support_status_values']['C1'], 'PARTIALLY_SUPPORTED')
        self.assertEqual(strong['support_status_values']['C1'], 'SUPPORTED')

    def test_no_ledger_record_is_unknown_not_refuted(self):
        # Missing evidence is not a refuted claim: no record at all -> UNKNOWN.
        result = run(ledger=NO_EVIDENCE)
        self.assertEqual(result['support_status_values']['C1'], 'UNKNOWN')
        self.assertNotIn(result['support_status_values']['C1'],
                         ('SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED'))
        self.assertNotEqual(result['status'], 'PASS')

    def test_contradicted_record_is_unsupported(self):
        # A located record that goes against the claim is the only UNSUPPORTED branch.
        result = run(ledger=CONTRADICTED)
        self.assertEqual(result['support_status_values']['C1'], 'UNSUPPORTED')

    def test_unresolved_record_state_is_unknown(self):
        result = run(ledger=UNKNOWN_EVIDENCE)
        self.assertEqual(result['support_status_values']['C1'], 'UNKNOWN')

    def test_venue_dependent_change_ok_is_clean_for_an_identical_paper(self):
        before = {'contributions': [{'id': 'C1', 'support_status': 'SUPPORTED'}],
                  'issues': [{'id': 'D1', 'issue_type': 'SCIENTIFIC_DEFECT'}]}
        self.assertEqual(vic.venue_dependent_change_ok(before, copy.deepcopy(before)), [])

    def test_venue_dependent_change_ok_detects_a_moved_support_status(self):
        before = {'contributions': [{'id': 'C1', 'support_status': 'SUPPORTED'}], 'issues': []}
        after = {'contributions': [{'id': 'C1', 'support_status': 'PARTIALLY_SUPPORTED'}],
                 'issues': []}
        violations = vic.venue_dependent_change_ok(before, after)
        self.assertEqual(len(violations), 1)
        self.assertIn('support status of C1 changed', violations[0])

    def test_venue_dependent_change_ok_detects_a_dropped_scientific_defect(self):
        before = {'contributions': [], 'issues': [{'id': 'D1', 'issue_type': 'SCIENTIFIC_DEFECT'}]}
        after = {'contributions': [], 'issues': []}
        violations = vic.venue_dependent_change_ok(before, after)
        self.assertTrue(any('scientific defect D1 disappeared' in v for v in violations))

    def test_venue_dependent_change_ok_ignores_a_venue_fit_change(self):
        before = {'contributions': [{'id': 'C1', 'support_status': 'SUPPORTED'}],
                  'issues': [{'id': 'D1', 'issue_type': 'SCIENTIFIC_DEFECT'},
                             {'id': 'V1', 'issue_type': 'VENUE_FIT_RISK'}]}
        after = {'contributions': [{'id': 'C1', 'support_status': 'SUPPORTED'}],
                 'issues': [{'id': 'D1', 'issue_type': 'SCIENTIFIC_DEFECT'}]}
        self.assertEqual(vic.venue_dependent_change_ok(before, after), [])


class ContractTests(unittest.TestCase):
    def test_unknown_declaration_field_is_rejected(self):
        bad = declaration()
        bad['acceptance_estimate'] = 0.7
        result = cp.validate(GRAPH, None, VERIFIED, bad)
        self.assertEqual(result['status'], 'FAIL')

    def test_unknown_contribution_field_is_rejected(self):
        item = contribution()
        item['predicted_reviewer_score'] = 8
        result = run(contributions=[item])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('invalid or missing fields' in e for e in result['errors']))

    def test_invalid_internal_type_is_rejected(self):
        result = run(contributions=[contribution(internal_type='research_track')])
        self.assertEqual(result['status'], 'FAIL')

    def test_claim_id_must_exist_in_the_argument_graph(self):
        result = run(contributions=[contribution(claim_ids=['C9'])])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('not in the argument graph' in e for e in result['errors']))

    def test_more_than_one_primary_contribution_is_rejected(self):
        first = contribution()
        second = contribution(id='C2', claim_ids=['C2'])
        result = run(contributions=[first, second], graph=graph_for(('C1', 'C2'), central=('C1',)))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('more than one primary' in e for e in result['errors']))

    def test_non_contribution_cannot_foreground_claims(self):
        result = run(contributions=[contribution(role='not_a_contribution')])
        self.assertEqual(result['status'], 'FAIL')

    def test_evidence_limits_must_be_a_statement_or_null(self):
        result = run(contributions=[contribution(evidence_limits='   ')])
        self.assertEqual(result['status'], 'FAIL')


class SemanticEvaluationTests(unittest.TestCase):
    """Constructed correct/faulty pairs: protocol enforcement, not detection ability."""

    def test_correct_positioning_passes_and_the_faulty_twin_fails(self):
        # CORRECT: no novelty is asserted, so no prior-work record is required.
        correct = declaration([contribution(claim='We present a method that reduces error.')])
        correct_result = cp.validate(GRAPH, None, VERIFIED, correct)
        self.assertEqual(correct_result['status'], 'PASS')

        # FAULTY: identical evidence, but the wording asserts priority.
        faulty = declaration([contribution(claim='We are the first to reduce this error.')])
        faulty_result = cp.validate(GRAPH, None, VERIFIED, faulty)
        self.assertEqual(faulty_result['status'], 'FAIL')
        self.assertTrue(any('asserts novelty or priority' in e for e in faulty_result['errors']))

    def test_novelty_assertion_in_the_claim_requires_prior_work(self):
        result = run(contributions=[contribution(claim='This is the first scalable solution.')])
        self.assertEqual(result['status'], 'FAIL')

    def test_novelty_assertion_in_the_delta_requires_prior_work(self):
        result = run(contributions=[contribution(
            novelty_delta='No prior work addresses this configuration.')])
        self.assertEqual(result['status'], 'FAIL')

    def test_declared_novelty_status_requires_checked_prior_work(self):
        result = run(contributions=[contribution(
            novelty='ESTABLISHED_BY_CHECKED_PRIOR_WORK', closest_prior_work='Smith 2020')])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('requires checked prior work' in e for e in result['errors']))

    def test_cited_only_prior_work_does_not_count_as_inspected(self):
        result = run(contributions=[contribution(
            novelty='ESTABLISHED_BY_CHECKED_PRIOR_WORK',
            prior_work=[{'status': 'CITED_ONLY', 'reference': 'Smith 2020',
                         'digest': 'sha256:' + 'b' * 16}],
            closest_prior_work='Smith 2020')])
        self.assertEqual(result['status'], 'FAIL')

    def test_prior_work_without_a_provenance_digest_does_not_count(self):
        result = run(contributions=[contribution(
            novelty='ESTABLISHED_BY_CHECKED_PRIOR_WORK',
            prior_work=[{'status': 'CHECKED', 'reference': 'Smith 2020', 'digest': ''}],
            closest_prior_work='Smith 2020')])
        self.assertEqual(result['status'], 'FAIL')

    def test_structural_equivalence_without_a_distinguishing_property_fails(self):
        result = run(contributions=[contribution(
            structural_equivalence={'is_structurally_equivalent': True,
                                    'twin_reference': 'Twin 2019',
                                    'distinguishing_property': None})])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('distinguishing property' in e for e in result['errors']))

    def test_reworded_strength_cannot_raise_a_support_status(self):
        wording = [contribution(claim='The experiment proves X beyond doubt.'),
                   contribution(claim='The experiment establishes X.')]
        statuses = {run(ledger=REPORTED, contributions=[item])['support_status_values']['C1']
                    for item in wording}
        self.assertEqual(statuses, {'PARTIALLY_SUPPORTED'})


class NegativeResultsTests(unittest.TestCase):
    def test_contradicted_negative_result_is_unsupported(self):
        item = contribution(internal_type='negative_results_critical_findings',
                            claim='The intervention did not improve the outcome; we report '
                                  'this negative result.')
        result = run(ledger=CONTRADICTED, contributions=[item])
        self.assertEqual(result['support_status_values']['C1'], 'UNSUPPORTED')

    def test_negative_result_never_reaches_supported_from_reporting_alone(self):
        item = contribution(internal_type='negative_results_critical_findings')
        result = run(ledger=REPORTED, contributions=[item])
        self.assertEqual(result['support_status_values']['C1'], 'PARTIALLY_SUPPORTED')
        self.assertNotIn(result['support_status_values']['C1'], ('SUPPORTED',))

    def test_negative_result_primary_cannot_be_presented_as_established(self):
        item = contribution(internal_type='negative_results_critical_findings', role='primary',
                            claim='This important negative result refutes the hypothesis.')
        result = run(ledger=CONTRADICTED, contributions=[item])
        self.assertEqual(result['support_status_values']['C1'], 'UNSUPPORTED')
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(any('cannot be presented as established' in u for u in result['unresolved']))

    def test_negative_result_is_not_auto_foregrounded(self):
        item = contribution(internal_type='negative_results_critical_findings', role='secondary',
                            claim='A secondary negative finding is reported.')
        result = run(ledger=CONTRADICTED, contributions=[item])
        self.assertEqual(result['primary_contribution_ids'], [])
        self.assertEqual(result['contributions'][0]['role'], 'secondary')

    def test_negative_result_support_follows_the_ledger(self):
        item = contribution(internal_type='negative_results_critical_findings')
        for ledger, status in ((VERIFIED, 'SUPPORTED'), (REPORTED, 'PARTIALLY_SUPPORTED'),
                               (UNKNOWN_EVIDENCE, 'UNKNOWN'), (CONTRADICTED, 'UNSUPPORTED')):
            with self.subTest(status=status):
                self.assertEqual(run(ledger=ledger, contributions=[item])
                                 ['support_status_values']['C1'], status)


class PartialInputTests(unittest.TestCase):
    def test_missing_context_forces_needs_review_not_pass(self):
        result = run(missing_context=['The ledger does not cover the second experiment.'])
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertNotEqual(result['status'], 'PASS')

    def test_primary_claim_without_evidence_cannot_pass(self):
        result = run(ledger=NO_EVIDENCE)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(any('cannot be presented as established' in u for u in result['unresolved']))

    def test_unknown_evidence_record_forces_review(self):
        result = run(ledger=UNKNOWN_EVIDENCE)
        self.assertEqual(result['support_status_values']['C1'], 'UNKNOWN')
        self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_planned_work_is_reported_as_unresolved(self):
        planned = ledger_for({'C1': 'no_evidence'})
        planned['evidence'] = [{'id': 'E1', 'claim_id': 'C1', 'state': 'planned'}]
        result = run(ledger=planned)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_central_claim_not_mapped_is_unresolved(self):
        result = cp.validate(GRAPH, {'findings': []}, VERIFIED,
                             declaration([contribution(claim_ids=['C1'])], specified=False))
        self.assertEqual(result['status'], 'PASS')
        # A central claim present in the graph but absent from every contribution is flagged.
        graph = graph_for(('C1', 'C2'), central=('C1', 'C2'))
        result = cp.validate(graph, {'findings': []}, VERIFIED,
                             declaration([contribution(claim_ids=['C1'])]))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(any('central claim C2' in u for u in result['unresolved']))


class EndToEndTests(RegistryMixin, unittest.TestCase):
    def test_specified_target_resolves_a_profile_and_maps_an_official_category(self):
        # Regression for the Lead's fix: an integer year must resolve a profile.
        registry = self.two_venue_registry()
        item = contribution(official_category=self.OFFICIAL_LABEL)
        result = run(contributions=[item], specified=True, venue='NeurIPS',
                     registry=(str(registry),))
        self.assertIsNone(result['venue_profile'])
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['contributions'][0]['mapping_verdict'], 'DIRECT_MATCH')

    def test_specified_target_still_requires_a_concrete_scope(self):
        registry = self.two_venue_registry()
        missing = declaration([contribution()], specified=True, venue='NeurIPS')
        missing['target_venue']['track'] = None
        result = cp.validate(GRAPH, None, VERIFIED, missing, (str(registry),))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('needs a concrete venue, year and track' in e
                            for e in result['errors']))

    def test_a_string_year_does_not_silently_match_an_integer_year(self):
        registry = self.two_venue_registry()
        mixed = declaration([contribution()], specified=True, venue='NeurIPS')
        mixed['target_venue']['year'] = '2025'
        result = cp.validate(GRAPH, None, VERIFIED, mixed, (str(registry),))
        self.assertEqual(result['status'], 'FAIL')

    def test_venue_switch_does_not_change_support_status(self):
        registry = self.two_venue_registry()
        neutral = run(specified=False)
        first = run(specified=True, venue='NeurIPS', registry=(str(registry),))
        second = run(specified=True, venue='ICML', registry=(str(registry),))

        self.assertEqual(neutral['support_status_values'], {'C1': 'SUPPORTED'})
        self.assertEqual(neutral['support_status_values'], first['support_status_values'])
        self.assertEqual(first['support_status_values'], second['support_status_values'])
        self.assertEqual(vic.venue_dependent_change_ok(neutral, first), [])
        self.assertEqual(vic.venue_dependent_change_ok(first, second), [])

    def test_venue_switch_keeps_scientific_errors_identical(self):
        registry = self.two_venue_registry()
        faulty = [contribution(claim='We are the first to solve this.')]
        neutral = run(contributions=faulty, specified=False)
        venue_run = run(contributions=faulty, specified=True, venue='NeurIPS',
                        registry=(str(registry),))
        self.assertEqual(neutral['support_status_values'], venue_run['support_status_values'])
        self.assertEqual(neutral['errors'] == [], venue_run['errors'] == [])

    def test_ac_graph_claim_types_are_the_contract_used_here(self):
        # Guards the fixture: the module rejects graph nodes that are not claim-bearing.
        self.assertIn('Claim', ac.CLAIM_TYPES)
        self.assertEqual(ci.digest({'a': 1}), ci.digest({'a': 1}))


if __name__ == '__main__':
    unittest.main()
