"""Adversarial tests for the venue-aware audit (venue_audit.py).

The audit layers venue fit on top of a completed science audit. It must not be
able to change a scientific verdict, and a venue/authorship judgement must never
be able to launder a scientific defect. These tests attack that boundary:

  * a theory paper is not given a mechanical experiment requirement,
  * fit levels are exactly the declared criterion checks, never a performance
    or state-of-the-art claim,
  * a confounded capacity/mechanism claim stays reportable and cannot be closed
    by rewording,
  * an ablation that only shows a performance gain cannot be relabelled as a
    venue or presentation matter,
  * missing context or a venue-neutral run cannot produce a whole-paper PASS.

Layering note: ``SemanticEvaluationTests`` are constructed counter-examples used
to enforce the audit protocol. A PASS here does not establish that the skill can
judge real significance or fit.
"""
import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import compare_invariants as ci
import venue_audit as va
import venue_intelligence_core as vic

MANUSCRIPT_DIGEST = 'a' * 64


def positioning(claim='We present a method that reduces error.'):
    return {'schema': 'contribution-positioning@1', 'manuscript_digest': MANUSCRIPT_DIGEST,
            'contributions': [{'id': 'C1', 'role': 'primary', 'support_status': 'SUPPORTED',
                               'claim': claim, 'evidence_ids': ['E1'], 'claim_ids': ['C1']}],
            'errors': [], 'unresolved': []}


POSITIONING = positioning()


def profile(dimensions=('scope_fit', 'soundness', 'originality', 'significance',
                        'theoretical_adequacy', 'reproducibility', 'transparency',
                        'compliance')):
    criteria = []
    for index, dimension in enumerate(dimensions):
        criteria.append({'id': 'RC-%d' % index, 'name': 'Criterion ' + dimension,
                         'dimension': dimension, 'official_explanation': 'Official text',
                         'quote': 'quote text long enough', 'source_id': 's1'})
    return {'schema': 'venue-policy-profile@1', 'venue': 'NeurIPS', 'year': 2025,
            'track': 'main', 'review_criteria': criteria, 'contribution_types': [],
            'mandatory_policy': [], 'recommended_policy': [], 'sources': []}


PROFILE = profile()
SCOPE_ID = 'RC-0'


def checks(fit='ADEQUATE_FIT', scope_id=SCOPE_ID, extra=None):
    out = {}
    for name in vic.VENUE_CRITERIA:
        out[name] = {'fit': fit, 'why': 'Reason for ' + name,
                     'evidence_node_ids': ['N1'], 'official_criterion_id': None}
    if scope_id is not None:
        out['scope_fit']['official_criterion_id'] = scope_id
    if extra:
        out.update(extra)
    return out


def issue(issue_type='SCIENTIFIC_DEFECT', origin='scientific_core', iid='I1',
          criterion='experimental_or_theoretical_adequacy', findings=('F1',),
          repair_kind='NEW_EXPERIMENT', summary='Capacity and mechanism vary together',
          why='The gain cannot be attributed to the mechanism because model capacity, '
              'optimization budget and compute also changed.'):
    return {'id': iid, 'issue_type': issue_type, 'origin': origin, 'criterion': criterion,
            'source_finding_ids': list(findings), 'evidence_node_ids': ['N1'],
            'summary': summary, 'why': why,
            'repair': {'kind': repair_kind, 'what': 'Separate the two factors',
                       'completion_condition': 'A capacity-matched control isolates the mechanism'}}


def declaration(audit_checks=None, issues=None, carried=None, missing_context=None,
                manuscript_digest=MANUSCRIPT_DIGEST, positioning_digest=None):
    return {'schema': 'venue-aware-audit@1', 'manuscript_digest': manuscript_digest,
            'positioning_digest': ci.digest(POSITIONING) if positioning_digest is None
            else positioning_digest,
            'checks': checks() if audit_checks is None else audit_checks,
            'issues': [] if issues is None else issues,
            'carried_findings': [] if carried is None else carried,
            'missing_context': [] if missing_context is None else missing_context}


def coherence(findings=None, diagnostics=None):
    return {'findings': [] if findings is None else findings,
            'structural_diagnostics': [] if diagnostics is None else diagnostics}


def finding(fid='F1', severity='major', code='MECHANISM_SUPPORT',
            why='The ablation reports a performance gain only; mechanism support is not '
                'established.'):
    return {'id': fid, 'code': code, 'severity': severity, 'why': why}


def carried(*ids):
    return [{'finding_id': fid, 'resolution': 'Kept visible in the venue-aware report'}
            for fid in ids]


NEUTRAL_CHECKS = checks(fit='NOT_APPLICABLE', scope_id=None)


def run(audit=None, prof=PROFILE, coh=None, pos=None):
    artifact = POSITIONING if pos is None else pos
    if audit is None:
        audit = declaration(positioning_digest=ci.digest(artifact))
    return va.validate(artifact, coherence() if coh is None else coh, audit, prof)


class DeterministicTests(unittest.TestCase):
    def test_clean_profile_bound_audit_reaches_pass(self):
        result = run()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['errors'], [])
        self.assertFalse(result['venue_neutral'])

    def test_fit_levels_are_exactly_the_declared_criterion_checks(self):
        declared = checks()
        declared['scope_fit']['fit'] = 'STRONG_FIT'
        declared['soundness_evidence_adequacy']['fit'] = 'MISMATCH'
        declared['originality_prior_work_delta']['fit'] = 'UNKNOWN'
        declared['submission_compliance']['fit'] = 'NOT_APPLICABLE'
        result = run(audit=declaration(audit_checks=declared))
        self.assertEqual(result['fit']['scope_fit'], 'STRONG_FIT')
        self.assertEqual(result['fit']['soundness_evidence_adequacy'], 'MISMATCH')
        self.assertEqual(result['fit']['originality_prior_work_delta'], 'UNKNOWN')
        self.assertEqual(result['fit']['submission_compliance'], 'NOT_APPLICABLE')
        self.assertEqual(result['fit'], {name: declared[name]['fit'] for name in vic.VENUE_CRITERIA})

    def test_theory_paper_is_not_required_to_add_experiments(self):
        theory_profile = profile(dimensions=('scope_fit', 'soundness', 'originality',
                                             'significance', 'theoretical_adequacy',
                                             'reproducibility', 'transparency', 'compliance'))
        self.assertNotIn('experimental_adequacy',
                         [c['dimension'] for c in theory_profile['review_criteria']])
        result = run(prof=theory_profile)
        self.assertEqual(result['status'], 'PASS')
        self.assertFalse(any('experiment' in e.lower() for e in result['errors']))
        self.assertFalse(any('experiment' in u.lower() for u in result['unresolved']))

    def test_audit_never_invents_an_issue(self):
        result = run()
        self.assertEqual(result['issues'], [])
        self.assertEqual(result['issue_counts']['SCIENTIFIC_DEFECT'], 0)

    def test_issue_classification_counts_are_separate(self):
        mech = issue()
        fit = issue(issue_type='VENUE_FIT_RISK', origin='venue_layer', iid='V1',
                    criterion='scope_fit', findings=(), repair_kind='TEXT_ONLY',
                    summary='Off-topic framing')
        result = run(audit=declaration(issues=[mech, fit], carried=carried('F1')),
                     coh=coherence([finding()]))
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['issue_counts']['SCIENTIFIC_DEFECT'], 1)
        self.assertEqual(result['issue_counts']['VENUE_FIT_RISK'], 1)

    def test_there_is_no_dedicated_mechanism_issue_type(self):
        # Honest boundary: a mechanism-support gap is classifiable only as a
        # SCIENTIFIC_DEFECT with the experimental/theoretical criterion and a carried
        # coherence finding. The layer has no separate MECHANISM_SUPPORT category, so
        # separation is enforced by type + origin + relabel rejection, not by a type.
        self.assertNotIn('MECHANISM_SUPPORT', vic.ISSUE_TYPES)
        self.assertIn('SCIENTIFIC_DEFECT', vic.ISSUE_TYPES)


class SemanticEvaluationTests(unittest.TestCase):
    """Constructed correct/faulty pairs: protocol enforcement, not review ability."""

    def test_confounded_capacity_and_mechanism_is_reportable(self):
        audit = declaration(issues=[issue(repair_kind='NEW_EXPERIMENT')],
                            carried=carried('F1'))
        result = run(audit=audit, coh=coherence([finding()]))
        self.assertEqual(result['status'], 'PASS')
        reported = result['issues'][0]
        self.assertEqual(reported['issue_type'], 'SCIENTIFIC_DEFECT')
        self.assertEqual(reported['repair']['kind'], 'NEW_EXPERIMENT')
        self.assertEqual(reported['criterion'], 'experimental_or_theoretical_adequacy')
        self.assertIn('capacity', reported['why'].lower())

    def test_confounded_claim_cannot_be_closed_by_rewording(self):
        for repair_kind in ('TEXT_ONLY', 'CLAIM_CALIBRATION'):
            with self.subTest(repair_kind=repair_kind):
                audit = declaration(issues=[issue(repair_kind=repair_kind)],
                                    carried=carried('F1'))
                result = run(audit=audit, coh=coherence([finding()]))
                self.assertEqual(result['status'], 'FAIL')
                self.assertTrue(any('cannot be closed by' in e for e in result['errors']))

    def test_effect_only_ablation_cannot_become_a_venue_fit_risk(self):
        relabelled = issue(issue_type='VENUE_FIT_RISK', origin='venue_layer',
                           findings=['F1'], repair_kind='TEXT_ONLY')
        result = run(audit=declaration(issues=[relabelled], carried=carried('F1')),
                     coh=coherence([finding()]))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('must not re-label a scientific finding' in e
                            for e in result['errors']))

    def test_mechanism_gap_cannot_be_relabelled_as_a_presentation_issue(self):
        relabelled = issue(issue_type='PRESENTATION_ISSUE', origin='venue_layer',
                           findings=['F1'], repair_kind='TEXT_ONLY')
        result = run(audit=declaration(issues=[relabelled], carried=carried('F1')),
                     coh=coherence([finding()]))
        self.assertEqual(result['status'], 'FAIL')

    def test_critical_mechanism_finding_must_be_carried_through(self):
        audit = declaration(issues=[], carried=[])
        result = run(audit=audit, coh=coherence([finding('F1', 'critical')]))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('were dropped by the venue layer' in e for e in result['errors']))

    def test_scientific_defect_must_cite_a_real_coherence_finding(self):
        audit = declaration(issues=[issue(findings=('F9',))], carried=carried('F9'))
        result = run(audit=audit, coh=coherence([finding()]))
        self.assertEqual(result['status'], 'FAIL')

    def test_scientific_defect_cannot_originate_in_the_venue_layer(self):
        audit = declaration(issues=[issue(origin='venue_layer')], carried=carried('F1'))
        result = run(audit=audit, coh=coherence([finding()]))
        self.assertEqual(result['status'], 'FAIL')

    def test_fit_cannot_be_derived_from_a_performance_claim(self):
        claim = ('Our method is not state of the art on the benchmark, but its '
                 'construction is different.')
        pos = positioning(claim)
        strong = {name: 'STRONG_FIT' for name in vic.VENUE_CRITERIA}
        declared = checks()
        for name in vic.VENUE_CRITERIA:
            declared[name]['fit'] = strong[name]
        result = run(audit=declaration(audit_checks=declared,
                                       positioning_digest=ci.digest(pos)), pos=pos)
        self.assertEqual(result['status'], 'PASS')
        self.assertTrue(all(value == 'STRONG_FIT' for value in result['fit'].values()))


class ContractTests(unittest.TestCase):
    def test_missing_criterion_is_rejected(self):
        incomplete = checks()
        incomplete.pop('significance_knowledge_advancement')
        result = run(audit=declaration(audit_checks=incomplete))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('all eight venue criteria' in e for e in result['errors']))

    def test_unknown_fit_level_is_rejected(self):
        bad = checks()
        bad['scope_fit']['fit'] = 'LIKELY_ACCEPT'
        result = run(audit=declaration(audit_checks=bad))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('invalid fit level' in e for e in result['errors']))

    def test_performance_or_sota_fields_are_not_part_of_the_contract(self):
        bad = checks()
        bad['scope_fit']['is_sota'] = True
        result = run(audit=declaration(audit_checks=bad))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('invalid criterion check' in e for e in result['errors']))

    def test_stale_positioning_binding_is_rejected(self):
        result = run(audit=declaration(positioning_digest='0' * 64))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('stale positioning binding' in e for e in result['errors']))

    def test_audit_for_a_different_manuscript_is_rejected(self):
        result = run(audit=declaration(manuscript_digest='b' * 64))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('different manuscript' in e for e in result['errors']))

    def test_duplicate_carried_finding_is_rejected(self):
        audit = declaration(carried=carried('F1') + carried('F1'))
        result = run(audit=audit, coh=coherence([finding('F1', 'critical')]))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('duplicate carried finding' in e for e in result['errors']))

    def test_unknown_official_criterion_id_is_rejected(self):
        bad = checks(scope_id='RC-NOT-PUBLISHED')
        result = run(audit=declaration(audit_checks=bad))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('does not publish' in e for e in result['errors']))


class PartialInputTests(unittest.TestCase):
    def test_missing_context_forces_needs_review(self):
        result = run(audit=declaration(missing_context=['No coherence audit was supplied.']))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertNotEqual(result['status'], 'PASS')

    def test_venue_neutral_audit_is_the_documented_needs_review(self):
        result = run(audit=declaration(audit_checks=NEUTRAL_CHECKS), prof=None)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(result['venue_neutral'])
        self.assertTrue(any('venue-neutral run' in u for u in result['unresolved']))

    def test_fit_cannot_be_claimed_without_a_profile(self):
        result = run(audit=declaration(audit_checks=checks()), prof=None)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('cannot claim a fit level without a venue profile' in e
                            for e in result['errors']))

    def test_venue_fit_risk_without_a_profile_is_rejected(self):
        audit = declaration(audit_checks=NEUTRAL_CHECKS,
                            issues=[issue(issue_type='VENUE_FIT_RISK', origin='venue_layer',
                                          findings=())])
        result = run(audit=audit, prof=None)
        self.assertEqual(result['status'], 'FAIL')

    def test_primary_unsupported_contribution_keeps_review_visible(self):
        weak = positioning()
        weak['contributions'][0]['support_status'] = 'UNSUPPORTED'
        result = run(pos=weak)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(any('remains UNSUPPORTED' in u for u in result['unresolved']))


class EndToEndTests(unittest.TestCase):
    def test_declared_check_dict_is_not_mutated(self):
        declared = checks()
        snapshot = copy.deepcopy(declared)
        run(audit=declaration(audit_checks=declared))
        self.assertEqual(declared, snapshot)

    def test_audit_reports_carried_findings_sorted(self):
        audit = declaration(carried=carried('F2', 'F1'))
        result = run(audit=audit, coh=coherence([finding('F1', 'critical'),
                                                 finding('F2', 'major')]))
        self.assertEqual(result['carried_findings'], ['F1', 'F2'])

    def test_bundled_profile_shape_round_trips(self):
        result = run()
        encoded = json.loads(json.dumps(result))
        self.assertEqual(encoded['status'], 'PASS')
        self.assertEqual(encoded['schema'], 'venue-aware-audit@1')


if __name__ == '__main__':
    unittest.main()
