"""Adversarial end-to-end tests for the Venue Intelligence layer.

HONESTY STATEMENT
=================
These tests verify structural and protocol enforcement and constructed
scientific counter-examples. A PASS in this file does **not** demonstrate that
the skill can judge real scientific contribution quality. The gates check that
declared support, novelty, boundaries, framing and repair contracts obey the
rule system; they cannot detect a genuine scientific error that a human has not
declared. Prewritten validators and JSON schemas are not evidence of review
ability, and a green suite is not evidence that a real paper is sound.

Covered here:
  * venue-driven revision cannot strengthen support, introduce novelty or delete
    an evidence boundary (venue_revision_impact),
  * the readiness report has no acceptance probability and no weighted score,
    and never drops or demotes a blocker,
  * a met repair completion condition is represented as resolved by the bounded
    revision loop; an unmet one stays open,
  * rule conflicts from the registry are reported to the Lead separately and are
    pinned in tests/test_venue_registry.py.
"""
import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import compare_invariants as ci
import revision_loop as rl
import venue_intelligence_core as vic
import venue_readiness as vrd
import venue_revision_impact as vri

MANUSCRIPT_DIGEST = 'd' * 64


# --------------------------------------------------------------------------- #
# venue_revision_impact fixtures
# --------------------------------------------------------------------------- #
def rpos(support='PARTIALLY_SUPPORTED', novelty='NOT_CLAIMED', limits='Only on the tested X.',
         closest='Prior 2019'):
    return {'schema': 'contribution-positioning@1', 'manuscript_digest': MANUSCRIPT_DIGEST,
            'contributions': [{'id': 'C1', 'support_status': support, 'novelty': novelty,
                               'closest_prior_work': closest, 'evidence_limits': limits,
                               'claim': 'We report an effect on X.', 'claim_ids': ['C1']}],
            'errors': [], 'unresolved': []}


def redit(**over):
    item = {'id': 'E1', 'contribution_ids': ['C1'], 'change': 'Reworded the abstract.',
            'repair_kind': 'TEXT_ONLY', 'new_evidence_ids': [], 'new_prior_work': [],
            'presents_as': 'SAME_CLAIM'}
    item.update(over)
    return item


def rdecl(before, after, edits, strengthened=None, removed=None, missing_context=None):
    return {'schema': 'venue-revision-impact@1', 'manuscript_digest': MANUSCRIPT_DIGEST,
            'before_digest': ci.digest(before), 'after_digest': ci.digest(after),
            'edits': edits, 'strengthened_ids': [] if strengthened is None else strengthened,
            'removed_boundaries': [] if removed is None else removed,
            'missing_context': [] if missing_context is None else missing_context}


def impact(before, after, edits, **over):
    return vri.validate(before, after, rdecl(before, after, edits, **over))


# --------------------------------------------------------------------------- #
# venue_readiness fixtures
# --------------------------------------------------------------------------- #
def r_positioning(contributions=None, unresolved=None):
    if contributions is None:
        contributions = [{'id': 'C1', 'support_status': 'SUPPORTED',
                          'claim': 'We present a method.', 'evidence_ids': ['E1']}]
    return {'status': 'PASS', 'contributions': contributions,
            'unresolved': [] if unresolved is None else unresolved, 'errors': []}


def r_audit(status='PASS', issues=None, unresolved=None):
    return {'status': status, 'issues': [] if issues is None else issues,
            'unresolved': [] if unresolved is None else unresolved, 'errors': []}


def r_compliance(status='PASS', checks=None, unresolved=None):
    return {'status': status, 'checks': [] if checks is None else checks,
            'unresolved': [] if unresolved is None else unresolved, 'errors': []}


def r_coherence(well_supported=None, unresolved=None):
    return {'status': 'PASS', 'well_supported': [] if well_supported is None else well_supported,
            'unresolved': [] if unresolved is None else unresolved, 'errors': []}


def blocker_issue(iid='I1', repair_kind='NEW_EXPERIMENT',
                  completion='A capacity-matched control isolates the mechanism'):
    return {'id': iid, 'issue_type': 'SCIENTIFIC_DEFECT', 'origin': 'scientific_core',
            'criterion': 'experimental_or_theoretical_adequacy',
            'source_finding_ids': ['F1'], 'evidence_node_ids': ['N1'],
            'summary': 'Capacity and mechanism are confounded',
            'why': 'Model capacity, optimization budget and compute changed together.',
            'repair': {'kind': repair_kind, 'what': 'Separate the factors',
                       'completion_condition': completion}}


_UNSET = object()


def readiness(priorities=_UNSET, pos=None, aud=None, comp=None, coh=None, missing_context=None):
    pos = r_positioning() if pos is None else pos
    aud = r_audit() if aud is None else aud
    comp = r_compliance() if comp is None else comp
    coh = r_coherence() if coh is None else coh
    declaration = {'schema': 'venue-readiness@1', 'manuscript_digest': MANUSCRIPT_DIGEST,
                   'coherence_digest': ci.digest(coh), 'positioning_digest': ci.digest(pos),
                   'venue_audit_digest': ci.digest(aud), 'compliance_digest': ci.digest(comp),
                   'priorities': [] if priorities is _UNSET else priorities,
                   'missing_context': [] if missing_context is None else missing_context}
    return vrd.aggregate(coh, pos, aud, comp, declaration)


def loop_artifact(completion_met=True, state='resolved', stop='completion_condition_met'):
    return {'goal': 'Repair the identifiability blocker',
            'completion_condition': 'A capacity-matched ablation isolates the mechanism',
            'completion_met': completion_met, 'new_evidence': True, 'stop_reason': stop,
            'problems': [{'id': 'P1', 'statement': 'Capacity confounds the mechanism',
                          'severity': 'major', 'state': state, 'iterations': ['I1'],
                          'resolution': 'Capacity-matched ablation added'
                          if state == 'resolved' else ''}],
            'iterations': [{'id': 'I1', 'problem_ids': ['P1'],
                            'target_change': 'Add a capacity-matched ablation',
                            'completion_criteria': 'Mechanism isolated under the control',
                            'scientific_disagreement': 'no', 'result': 'progress',
                            'new_evidence': True, 'resolves_problem_ids': ['P1']}]}


def accepting_keys(node, found=None):
    """Keys that could expose an acceptance probability or a weighted score."""
    found = set() if found is None else found
    if isinstance(node, dict):
        for key, value in node.items():
            lowered = key.lower()
            if ('accept' in lowered or lowered.endswith('score') or 'probability' in lowered) \
                    and value is not None and key != 'no_acceptance_probability':
                found.add(key)
            accepting_keys(value, found)
    elif isinstance(node, list):
        for value in node:
            accepting_keys(value, found)
    return found


class RevisionImpactDeterministicTests(unittest.TestCase):
    def test_clean_revision_reaches_pass(self):
        before = rpos()
        result = impact(before, copy.deepcopy(before), [])
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['errors'], [])

    def test_support_maps_are_reported_before_and_after(self):
        before = rpos()
        after = rpos(support='SUPPORTED')
        result = impact(before, after, [redit(new_evidence_ids=['E9'])])
        self.assertEqual(result['support_before'], {'C1': 'PARTIALLY_SUPPORTED'})
        self.assertEqual(result['support_after'], {'C1': 'SUPPORTED'})

    def test_a_venue_only_change_is_not_a_scientific_defect(self):
        before = {'contributions': [{'id': 'C1', 'support_status': 'SUPPORTED'}],
                  'issues': [{'id': 'V1', 'issue_type': 'VENUE_FIT_RISK'},
                             {'id': 'D1', 'issue_type': 'SCIENTIFIC_DEFECT'}]}
        after = {'contributions': [{'id': 'C1', 'support_status': 'SUPPORTED'}],
                 'issues': [{'id': 'D1', 'issue_type': 'SCIENTIFIC_DEFECT'}]}
        self.assertEqual(vic.venue_dependent_change_ok(before, after), [])

    def test_pure_wording_edit_is_not_a_violation(self):
        before = rpos(limits='Only on the tested X.')
        after = rpos(limits='Only on the tested X.')
        result = impact(before, after, [redit(change='Shortened a sentence.')])
        self.assertEqual(result['status'], 'PASS')

    def test_declared_strengthening_of_presentation_is_allowed(self):
        before = rpos()
        result = impact(before, copy.deepcopy(before),
                        [redit(presents_as='STRONGER_CLAIM')], strengthened=['E1'])
        self.assertEqual(result['status'], 'PASS')


class RevisionImpactContractTests(unittest.TestCase):
    def test_unknown_edit_field_is_rejected(self):
        item = redit()
        item['reviewer_expected'] = True
        before = rpos()
        result = impact(before, copy.deepcopy(before), [item])
        self.assertEqual(result['status'], 'FAIL')

    def test_stale_before_binding_is_rejected(self):
        before = rpos()
        declaration = rdecl(before, before, [])
        declaration['before_digest'] = '0' * 64
        result = vri.validate(before, before, declaration)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('stale before positioning binding' in e for e in result['errors']))

    def test_strengthened_id_must_name_a_known_edit(self):
        before = rpos()
        result = impact(before, copy.deepcopy(before), [], strengthened=['E9'])
        self.assertEqual(result['status'], 'FAIL')

    def test_removed_boundaries_must_name_a_known_contribution(self):
        before = rpos()
        result = impact(before, copy.deepcopy(before), [], removed=['C9'])
        self.assertEqual(result['status'], 'FAIL')

    def test_missing_context_forces_needs_review(self):
        before = rpos()
        result = impact(before, copy.deepcopy(before), [],
                        missing_context=['The after-positioning is provisional.'])
        self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_missing_positioning_schema_is_rejected(self):
        result = vri.validate({'contributions': []}, {'contributions': []},
                              rdecl(rpos(), rpos(), []))
        self.assertEqual(result['status'], 'FAIL')


class RevisionImpactSemanticTests(unittest.TestCase):
    """Constructed correct/faulty pairs: protocol enforcement, not detection ability."""

    def test_support_raised_without_new_evidence_fails(self):
        before, after = rpos(), rpos(support='SUPPORTED')
        result = impact(before, after, [redit()])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('without new evidence' in e for e in result['errors']))

    def test_support_raised_with_new_evidence_needs_review_not_pass(self):
        before, after = rpos(), rpos(support='SUPPORTED')
        result = impact(before, after, [redit(new_evidence_ids=['E9'])])
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(any('re-audit is required' in u for u in result['unresolved']))

    def test_novelty_introduced_without_prior_work_fails(self):
        before = rpos(novelty='NOT_CLAIMED')
        after = rpos(novelty='INCREMENTAL_DELTA')
        result = impact(before, after, [redit()])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('without inspected prior work' in e for e in result['errors']))

    def test_novelty_established_without_closest_prior_work_fails(self):
        before = rpos(novelty='NOT_CLAIMED')
        after = rpos(novelty='ESTABLISHED_BY_CHECKED_PRIOR_WORK', closest='')
        result = impact(before, after, [redit(new_prior_work=[{'id': 'P1'}])])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('without naming closest prior work' in e
                            for e in result['errors']))

    def test_removed_evidence_limit_labelled_text_only_fails(self):
        before = rpos(limits='Only on the tested X.')
        after = rpos(limits=None)
        result = impact(before, after, [redit(repair_kind='TEXT_ONLY')])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('deleted limitation is not a presentation change' in e
                            for e in result['errors']))

    def test_removed_limit_labelled_claim_calibration_also_fails(self):
        before = rpos(limits='Only on the tested X.')
        after = rpos(limits=None)
        result = impact(before, after, [redit(repair_kind='CLAIM_CALIBRATION')])
        self.assertEqual(result['status'], 'FAIL')

    def test_removed_limit_with_reanalysis_needs_review_not_pass(self):
        before = rpos(limits='Only on the tested X.')
        after = rpos(limits=None)
        result = impact(before, after, [redit(repair_kind='EXISTING_DATA_REANALYSIS')])
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(any('lost its evidence boundary' in u for u in result['unresolved']))

    def test_undeclared_stronger_presentation_fails(self):
        before = rpos()
        result = impact(before, copy.deepcopy(before),
                        [redit(presents_as='HIGHER_SUPPORT')])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('was not declared' in e for e in result['errors']))

    def test_correct_and_faulty_support_pair(self):
        # CORRECT: no support movement -> clean.
        before = rpos()
        correct = impact(before, copy.deepcopy(before), [])
        self.assertEqual(correct['status'], 'PASS')
        # FAULTY: identical edits, silently raised support.
        faulty = impact(before, rpos(support='SUPPORTED'), [redit()])
        self.assertEqual(faulty['status'], 'FAIL')


class ReadinessDeterministicTests(unittest.TestCase):
    def test_no_acceptance_probability_and_no_weighted_score(self):
        result = readiness()
        self.assertIsNone(result['weighted_score'])
        self.assertIs(result['no_acceptance_probability'], True)

    def test_no_output_field_exposes_an_opaque_acceptance_number(self):
        result = readiness(aud=r_audit(issues=[blocker_issue()]),
                           priorities=[{'item_id': 'I1', 'priority': 'BLOCKER', 'order': 1}])
        self.assertEqual(accepting_keys(result), set())
        self.assertIsNone(result['weighted_score'])
        self.assertIs(result['no_acceptance_probability'], True)

    def test_no_secondary_output_exposes_an_acceptance_estimate(self):
        outputs = {
            'readiness': readiness(),
            'revision_impact': impact(rpos(), rpos(), []),
            'revision_loop': rl.evaluate(loop_artifact()),
        }
        for name, output in outputs.items():
            with self.subTest(output=name):
                self.assertEqual(accepting_keys(output), set())

    def test_clean_paper_is_not_flagged(self):
        result = readiness()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['items'], [])
        self.assertEqual(result['errors'], [])
        self.assertEqual([s['id'] for s in result['strengths']], ['C1'])
        self.assertEqual(result['priority_counts'],
                         {'BLOCKER': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0})
        self.assertEqual(result['human_decisions'], {'state': 'NONE', 'items': []})

    def test_undeclared_priority_plan_is_review_not_a_silent_pass(self):
        # Regression for the Lead's fix: a null priority plan must be visible.
        result = readiness(priorities=None)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['human_decisions']['state'], 'NEEDS_REVIEW')
        self.assertTrue(any('priorit' in item.lower()
                            for item in result['human_decisions']['items']))

    def test_strengths_only_include_supported_contributions(self):
        pos = r_positioning(contributions=[
            {'id': 'C1', 'support_status': 'SUPPORTED', 'claim': 'Supported.',
             'evidence_ids': ['E1']},
            {'id': 'C2', 'support_status': 'PARTIALLY_SUPPORTED', 'claim': 'Partial.',
             'evidence_ids': ['E2']}])
        result = readiness(pos=pos, coh=r_coherence(well_supported=[
            {'why': 'A well supported argument.', 'node_ids': ['N1']}]))
        kinds = {s['kind'] for s in result['strengths']}
        ids = {s['id'] for s in result['strengths'] if s['id']}
        self.assertEqual(ids, {'C1'})
        self.assertEqual(kinds, {'supported_contribution', 'well_supported_argument'})

    def test_negative_result_is_never_a_strength(self):
        pos = r_positioning(contributions=[
            {'id': 'C1', 'support_status': 'UNSUPPORTED',
             'claim': 'An important negative result.', 'evidence_ids': []},
            {'id': 'C2', 'support_status': 'PARTIALLY_SUPPORTED',
             'claim': 'Partial negative result.', 'evidence_ids': []}])
        result = readiness(pos=pos)
        self.assertEqual([s['id'] for s in result['strengths']], [])

    def test_readiness_never_restates_a_failed_input_as_pass(self):
        result = readiness(aud=r_audit(status='FAIL'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('venue_audit is FAIL', result['verdict_reasons'])

    def test_missing_upstream_input_is_reported(self):
        declaration = {'schema': 'venue-readiness@1', 'manuscript_digest': MANUSCRIPT_DIGEST,
                       'coherence_digest': 'x', 'positioning_digest': ci.digest(r_positioning()),
                       'venue_audit_digest': ci.digest(r_audit()),
                       'compliance_digest': ci.digest(r_compliance()),
                       'priorities': [], 'missing_context': []}
        result = vrd.aggregate(r_coherence(), None, r_audit(), r_compliance(), declaration)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('requires a positioning result' in e for e in result['errors']))


class ReadinessBlockerTests(unittest.TestCase):
    def test_blocker_omitted_from_the_priority_plan_is_an_error(self):
        result = readiness(aud=r_audit(issues=[blocker_issue()]))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('blocker I1 was omitted' in e for e in result['errors']))

    def test_blocker_cannot_be_demoted(self):
        result = readiness(aud=r_audit(issues=[blocker_issue()]),
                           priorities=[{'item_id': 'I1', 'priority': 'HIGH', 'order': 1}])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('was demoted below BLOCKER' in e for e in result['errors']))

    def test_declared_blocker_is_preserved_with_its_completion_condition(self):
        issue = blocker_issue(completion='A capacity-matched control isolates the mechanism')
        result = readiness(aud=r_audit(issues=[issue]),
                           priorities=[{'item_id': 'I1', 'priority': 'BLOCKER', 'order': 1}])
        self.assertEqual(result['status'], 'PASS')
        item = result['items'][0]
        self.assertEqual(item['priority'], 'BLOCKER')
        self.assertEqual(item['completion_condition'],
                         'A capacity-matched control isolates the mechanism')

    def test_compliance_failure_becomes_a_blocker(self):
        result = readiness(comp=r_compliance(status='FAIL', checks=[
            {'id': 'C1', 'status': 'FAIL', 'why': 'Compiled document exceeds the page limit'}]))
        self.assertEqual(result['priority_counts']['BLOCKER'], 1)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('blocker C1 was omitted' in e for e in result['errors']))

    def test_reported_blocker_must_match_the_declared_priority(self):
        result = readiness(aud=r_audit(issues=[blocker_issue()]),
                           priorities=[{'item_id': 'I1', 'priority': 'BLOCKER', 'order': 1}])
        self.assertEqual(result['items'][0]['priority'], 'BLOCKER')
        self.assertEqual(result['errors'], [])

    def test_priority_cannot_name_an_unknown_item(self):
        result = readiness(priorities=[{'item_id': 'X9', 'priority': 'HIGH', 'order': 1}])
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('unknown item' in e for e in result['errors']))


class RepairCompletionTests(unittest.TestCase):
    def test_met_repair_completion_condition_is_represented_as_resolved(self):
        result = rl.evaluate(loop_artifact())
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['loop_status'], 'ready_to_accept')
        self.assertEqual(result['open_problems'], [])
        self.assertEqual(result['errors'], [])

    def test_unmet_completion_condition_stays_open(self):
        artifact = loop_artifact(completion_met=False, state='in_progress',
                                 stop='no_substantive_progress')
        result = rl.evaluate(artifact)
        self.assertNotEqual(result['status'], 'PASS')
        self.assertEqual(result['open_problems'], ['P1'])

    def test_resolved_problem_needs_an_explicit_resolution(self):
        artifact = loop_artifact()
        artifact['problems'][0]['resolution'] = ''
        result = rl.evaluate(artifact)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('needs a non-empty resolution' in e for e in result['errors']))

    def test_venue_readiness_carries_the_condition_but_not_the_resolution(self):
        # Honest boundary: readiness exposes the completion condition so a human or
        # the bounded loop can judge it, but it keeps no resolved/not-resolved state
        # of its own. Resolution is owned by revision_loop (asserted above).
        result = readiness(aud=r_audit(issues=[blocker_issue()]),
                           priorities=[{'item_id': 'I1', 'priority': 'BLOCKER', 'order': 1}])
        item = result['items'][0]
        self.assertIn('completion_condition', item)
        self.assertNotIn('resolved', item)


class EndToEndTests(unittest.TestCase):
    def test_venue_switch_does_not_move_readiness_strengths(self):
        before = readiness()
        after = readiness()
        self.assertEqual([s['id'] for s in before['strengths']],
                         [s['id'] for s in after['strengths']])
        self.assertEqual(vic.venue_dependent_change_ok(before, after), [])

    def test_readiness_json_round_trip_keeps_the_verdict(self):
        result = readiness(aud=r_audit(issues=[blocker_issue()]),
                           priorities=[{'item_id': 'I1', 'priority': 'BLOCKER', 'order': 1}])
        self.assertEqual(json.loads(json.dumps(result))['status'], 'PASS')

    def test_a_stale_upstream_binding_is_rejected(self):
        declaration = {'schema': 'venue-readiness@1', 'manuscript_digest': MANUSCRIPT_DIGEST,
                       'coherence_digest': ci.digest(r_coherence()),
                       'positioning_digest': 'stale', 'venue_audit_digest': ci.digest(r_audit()),
                       'compliance_digest': ci.digest(r_compliance()),
                       'priorities': [], 'missing_context': []}
        result = vrd.aggregate(r_coherence(), r_positioning(), r_audit(), r_compliance(),
                               declaration)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('stale positioning binding' in e for e in result['errors']))

    def test_repair_kinds_are_the_shared_vocabulary(self):
        self.assertEqual(set(vic.SCIENCE_REPAIRS) <= set(vic.REPAIR_KINDS), True)


if __name__ == '__main__':
    unittest.main()
