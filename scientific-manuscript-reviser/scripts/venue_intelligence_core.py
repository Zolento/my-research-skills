#!/usr/bin/env python3
"""Shared vocabulary for venue-aware scientific contribution analysis.

The governing principle is one sentence: scientific validity is venue-independent,
while contribution positioning and submission requirements are venue-dependent.
This module therefore keeps two things strictly apart:

  * the support status of a contribution, which depends only on evidence, and
  * the venue fit of that contribution, which depends only on a policy profile.

Swapping the target venue may change the fit report. It can never change a
support status, a scientific finding or a critical gap. Nothing here predicts
acceptance, scores reviewer preference or simulates a reviewer.

Stdlib only, no network, no model. A venue profile is always optional: without
one the skill runs a venue-neutral science audit and says so.
"""
import argparse
import json

from compare_invariants import digest, nonempty

SCHEMAS = {
    'positioning': 'contribution-positioning@1',
    'venue_audit': 'venue-aware-audit@1',
    'venue_strategy': 'venue-strategy@1',
    'impact': 'venue-revision-impact@1',
    'compliance': 'submission-compliance@1',
    'readiness': 'venue-readiness@1',
}

# Internal contribution classes. These are deliberately the skill's own
# vocabulary, NOT official submission categories, and must never be presented
# as the venue's own labels.
INTERNAL_CONTRIBUTION_TYPES = (
    'algorithmic_methodological', 'theoretical_foundational', 'problem_formulation_conceptual',
    'empirical_discovery_analysis', 'dataset_benchmark_evaluation', 'applied_systems_translational',
    'negative_results_critical_findings', 'concept_feasibility',
)

# Evidence-derived support status. Venue-independent.
SUPPORT_STATUS = ('SUPPORTED', 'PARTIALLY_SUPPORTED', 'PLANNED', 'UNSUPPORTED', 'UNKNOWN')

# Whether this contribution is the paper's main scientific claim or a secondary one.
CONTRIBUTION_ROLE = ('primary', 'secondary', 'possible_alternative', 'not_a_contribution')

# Honest novelty status. A novelty claim requires checked prior work.
NOVELTY_STATUS = ('ESTABLISHED_BY_CHECKED_PRIOR_WORK', 'INCREMENTAL_DELTA', 'UNVERIFIED',
                  'CONTRADICTED_BY_PRIOR_WORK', 'NOT_CLAIMED')

# Issues are classified by what kind of problem they actually are. These are
# not severity levels and they are not interchangeable.
ISSUE_TYPES = ('SCIENTIFIC_DEFECT', 'CONTRIBUTION_GAP', 'VENUE_FIT_RISK',
               'PRESENTATION_ISSUE', 'COMPLIANCE_ISSUE')

# Every issue carries where it came from, so a venue concern can never be
# mistaken for a scientific defect and vice versa.
ISSUE_ORIGIN = ('scientific_core', 'venue_layer', 'compliance_layer')

VENUE_CRITERIA = ('scope_fit', 'contribution_type_fit', 'soundness_evidence_adequacy',
                  'originality_prior_work_delta', 'significance_knowledge_advancement',
                  'experimental_or_theoretical_adequacy', 'reproducibility_transparency',
                  'submission_compliance')

# Fit is judged against a venue profile. It is never a probability.
FIT_LEVELS = ('STRONG_FIT', 'ADEQUATE_FIT', 'MISMATCH', 'NOT_APPLICABLE', 'UNKNOWN')

# Namespace for a criterion finding that is missing its underlying scientific input.
UNRESOLVED_UNKNOWN = 'UNKNOWN'

# Problem states reused by the bounded revision loop, kept here so the venue
# layer and the loop cannot drift apart.
REPAIR_KINDS = ('TEXT_ONLY', 'EXISTING_DATA_REANALYSIS', 'NEW_EXPERIMENT', 'NEW_THEORY',
                'CLAIM_CALIBRATION', 'HUMAN_DECISION')
# Repairs that change what the paper establishes need the full audit.
SCIENCE_REPAIRS = ('EXISTING_DATA_REANALYSIS', 'NEW_EXPERIMENT', 'NEW_THEORY')

# Framework-free contribution-type mapping is declared, not inferred. The engine
# checks internal classes against official categories; it cannot discover them.
MAPPING_VERDICTS = ('DIRECT_MATCH', 'PARTIAL_MATCH', 'NO_MATCH', 'NOT_PUBLISHED', 'UNKNOWN')

# Phrases that assert a novelty or priority claim outright. Used only to require
# that such a claim carries checked prior work; the phrase alone decides nothing
# about whether the claim is true.
NOVELTY_ASSERTION_MARKERS = (
    'first to', 'the first', 'we are the first', 'first-ever', 'first ever',
    'no prior work', 'no existing work', 'none of the existing', 'unprecedented',
    'no previous', 'for the first time',
)

# A prior-work record is only usable for a novelty claim when it was actually
# inspected and is source-bound.
PRIOR_WORK_STATUS = ('CHECKED', 'CITED_ONLY', 'UNVERIFIED')


def valid_support_status(value):
    return value in SUPPORT_STATUS


def venue_dependent_change_ok(before, after):
    """A venue switch may not change any support status or scientific finding.

    Returns the list of violations: any contribution whose support status moved,
    and any science-derived issue that disappeared.
    """
    violations = []
    support_before = {c['id']: c['support_status'] for c in before.get('contributions', [])}
    support_after = {c['id']: c['support_status'] for c in after.get('contributions', [])}
    for cid, status in support_before.items():
        if support_after.get(cid) != status:
            violations.append('support status of ' + cid + ' changed from ' + status
                              + ' to ' + str(support_after.get(cid)) + ' because the venue changed')
    science_before = {i['id'] for i in before.get('issues', [])
                      if i.get('issue_type') == 'SCIENTIFIC_DEFECT'}
    science_after = {i['id'] for i in after.get('issues', [])
                     if i.get('issue_type') == 'SCIENTIFIC_DEFECT'}
    for missing in sorted(science_before - science_after):
        violations.append('scientific defect ' + missing + ' disappeared after the venue changed')
    return violations


def contribution_supported_by_evidence(support_status):
    """Only evidence-derived statuses may present a contribution as achieved."""
    return support_status in ('SUPPORTED', 'PARTIALLY_SUPPORTED')


def profile_scope(profile):
    """The exact scope a profile is valid for. Never a range."""
    return {'venue': profile.get('venue'), 'year': profile.get('year'), 'track': profile.get('track')}


def self_check():
    assert set(INTERNAL_CONTRIBUTION_TYPES).isdisjoint({'research_track', 'poster'})
    assert set(SCIENCE_REPAIRS) <= set(REPAIR_KINDS)
    assert set(SUPPORT_STATUS).isdisjoint(ISSUE_TYPES)
    assert 'SCIENTIFIC_DEFECT' in ISSUE_TYPES and 'VENUE_FIT_RISK' in ISSUE_TYPES
    before = {'contributions': [{'id': 'C1', 'support_status': 'SUPPORTED'}],
              'issues': [{'id': 'D1', 'issue_type': 'SCIENTIFIC_DEFECT'}]}
    after = {'contributions': [{'id': 'C1', 'support_status': 'SUPPORTED'}],
             'issues': [{'id': 'D1', 'issue_type': 'SCIENTIFIC_DEFECT'}]}
    assert venue_dependent_change_ok(before, after) == []
    weakened = {'contributions': [{'id': 'C1', 'support_status': 'PARTIALLY_SUPPORTED'}],
                'issues': [{'id': 'D1', 'issue_type': 'SCIENTIFIC_DEFECT'}]}
    assert venue_dependent_change_ok(before, weakened)
    dropped = {'contributions': before['contributions'], 'issues': []}
    assert venue_dependent_change_ok(before, dropped)
    assert not contribution_supported_by_evidence('PLANNED')
    assert contribution_supported_by_evidence('SUPPORTED')
    assert nonempty('x') and digest({'a': 1}) == digest({'a': 1})
    for name in ('positioning', 'venue_audit', 'venue_strategy', 'impact', 'compliance', 'readiness'):
        assert SCHEMAS[name].endswith('@1')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        return self_check()
    print(json.dumps({'schemas': SCHEMAS, 'internal_contribution_types': INTERNAL_CONTRIBUTION_TYPES,
                      'support_status': SUPPORT_STATUS, 'issue_types': ISSUE_TYPES,
                      'venue_criteria': VENUE_CRITERIA, 'repair_kinds': REPAIR_KINDS}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
