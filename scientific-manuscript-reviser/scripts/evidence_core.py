#!/usr/bin/env python3
"""Shared vocabulary for evidence-grounded revision artifacts.

This module is the single authority for the v0.2.0 artifact contracts. It defines
enums, shared helpers and the cross-artifact span rule. It implements no science
and calls no model. Four CLI gates build on it:

    evidence_ledger.py       claim <-> source artifact ledger
    counterfactual_eval.py   paired correct/faulty reasoning test harness
    revision_impact.py       edited location -> dependent scientific elements
    revision_loop.py         bounded problem-driven revision loop

Everything here is stdlib only. Digests follow compare_invariants.digest so that
provenance bindings stay compatible with the existing scientific artifacts.
"""
import argparse
import hashlib
from pathlib import Path

from compare_invariants import digest  # canonical JSON SHA256, re-exported

SCHEMAS = {
    'ledger': 'claim-evidence-ledger@1',
    'evaluation': 'counterfactual-evaluation@1',
    'detection': 'counterfactual-detection@1',
    'impact': 'revision-impact-analysis@1',
    'loop': 'bounded-revision-loop@1',
}

# --- Evidence Ledger -------------------------------------------------------

ARTIFACT_TYPES = ('experiment_data', 'run_log', 'config', 'code', 'figure', 'table',
                  'proof', 'literature', 'dataset_card', 'notebook', 'other')
# A text artifact reports; it cannot carry an independent verification act.
TEXT_TYPES = ('literature', 'other')
VERIFICATION_METHODS = ('recomputed', 'hash_match', 'test_suite', 'independent_replication',
                        'provenance_audit', 'source_inspection', 'unverified')
EVIDENCE_STATES = ('verified', 'reported', 'contradicted', 'unknown')
CLAIM_STATES = ('verified', 'reported', 'contradicted', 'unknown', 'no_evidence')

# --- Counterfactual Evaluation --------------------------------------------

# Negative classes describe a genuine defect in the "faulty" variant.
FAULTY_CLASSES = ('causal_overreach', 'conclusion_inflation', 'invalid_control',
                  'missing_theoretical_assumption', 'unidentifiable_experiment',
                  'evidence_mismatch', 'cross_section_contradiction')
# Robustness classes change wording while the scientific content is unchanged.
# The expected verdict for these is clean. They are not negative classes.
# Two different questions, so two different classes:
#   robustness_paraphrase         clean text, different wording -> must not be flagged
#   robustness_defect_rewording   the same genuine defect, different surrounding
#                                 wording -> the defect must still be located
ROBUSTNESS_CLASSES = ('robustness_paraphrase', 'robustness_defect_rewording')
# Classes whose `faulty` variant carries a genuine, locatable defect.
DEFECT_CLASSES = FAULTY_CLASSES + ('robustness_defect_rewording',)
VERDICTS = ('faulty', 'clean', 'uncertain')
# The harness validates an externally produced detection. It never runs a detector.
# Each case pair must report one observation so measured accuracy stays meaningful.
PAIR_OBSERVATIONS = ('correct', 'miss', 'false_positive', 'uncertain')

# --- Revision Impact -------------------------------------------------------

DEPTHS = ('language_layer', 'scientific_content')
ELEMENT_KINDS = ('claim', 'evidence', 'theory', 'experiment', 'cross_section')
IMPACTS = ('unchanged', 'reference_only', 'restated', 'changed', 'removed')
REQUIRED_AUDITS = ('minimal_sufficient_check', 'full_semantic_audit', 'needs_reanalysis',
                   'needs_new_experiment', 'needs_new_theory')
# A change whose ground truth is unknown, not merely a poorly phrased repair.
SCIENTIFIC_RISKS = ('low', 'medium', 'high')
SCIENCE_DEPTH_REQUIREMENT = {'low': 'minimal_sufficient_check',
                             'medium': 'full_semantic_audit',
                             'high': 'full_semantic_audit'}
# Deleting or weakening a limitation is not a text-only repair, even when no
# experiment would be required to re-establish it.
LIMITATION_GUARD = 'limitation_removed_or_weakened'
# Prose punctuation introduced by a replacement outside its own original span.
# Reuses the H1 set from validate_style so the two layers cannot drift.
DEFUSED_PUNCTUATION = (';', ':', '—', '–')

# --- Bounded Revision Loop -------------------------------------------------

PROBLEM_STATES = ('open', 'in_progress', 'resolved', 'blocked', 'withdrawn')
STOP_REASONS = ('completion_condition_met', 'no_substantive_progress',
                'scientific_disagreement', 'iteration_limit', 'user_stop')
LOOP_STATUS = ('in_progress', 'ready_to_accept', 'scientific_disagreement',
               'no_substantive_progress', 'iteration_limit')
AGREEMENTS = ('yes', 'no')
ESCALATION_STATUS = ('pending', 'resolved')
# A stop is only a success when the completion condition is genuinely met.
SUCCESSFUL_STOPS = ('completion_condition_met',)


def canonical(value):
    """Alias kept explicit so this module reads as the v0.2.0 authority."""
    import json
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def exact_span(text, loc, span):
    if not isinstance(loc, dict) or set(loc) != {'start', 'end'}:
        return False
    start, end = loc['start'], loc['end']
    return (type(start) is int and type(end) is int and 0 <= start < end <= len(text)
            and isinstance(span, str) and text[start:end] == span)


def spans_overlap(first, second):
    """True when two {start,end} spans share at least one character offset."""
    for item in (first, second):
        if not isinstance(item, dict) or set(item) != {'start', 'end'}:
            return False
    return first['start'] < second['end'] and second['start'] < first['end']


def source_digest(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def claim_state(records, claim_id):
    """Aggregate one claim's evidence without inventing support.

    Contradiction outranks verification. Nothing at all is 'no_evidence', which
    is distinct from 'unknown': absent evidence must not read as unresolved science.
    """
    relevant = [r for r in records if r.get('claim_id') == claim_id]
    if not relevant:
        return 'no_evidence'
    states = {r.get('state') for r in relevant}
    if 'contradicted' in states:
        return 'contradicted'
    if 'unknown' in states:
        return 'unknown'
    if 'reported' in states:
        return 'reported'
    if 'verified' in states:
        return 'verified'
    return 'unknown'


def defensible_verification(artifact_type, method, state=None):
    """A text artifact cannot be independently verified inside this run.

    Reading a paper is source inspection of a report. A paper can report something and
    can contain content that contradicts a claim, so both states are recordable, but
    neither is verification of a claim. Text evidence therefore never carries a
    verification act and never reaches 'verified'.
    """
    return evidence_state_rule(artifact_type, method, state) is None


# The single authority for which (artifact type, state, method) combinations are
# honest. Message is a complete explanation for the first violated rule.
def evidence_state_rule(artifact_type, method, state):
    if state == 'verified':
        if artifact_type in TEXT_TYPES:
            return 'text artifact can never be verified: reading a source is not verification of a claim'
        if method == 'unverified':
            return 'state verified with verification_method unverified declares no verification act'
        return None
    if artifact_type in TEXT_TYPES:
        if method != 'unverified':
            return 'a text artifact carries no verification act, so method must be unverified'
        if state not in ('reported', 'contradicted'):
            return 'a text artifact is reported or contradicted and cannot be ' + str(state)
    return None


def loop_progress(before, after):
    """Substantive progress means new evidence or a newly resolved problem."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return False
    evidence = after.get('problem_states', set()) if isinstance(after.get('problem_states'), set) else set(after.get('resolved_problem_ids', []))
    previously = set(before.get('resolved_problem_ids', [])) if isinstance(before.get('resolved_problem_ids'), list) else set()
    if evidence - previously:
        return True
    return bool(after.get('new_evidence')) and after.get('new_evidence') != before.get('new_evidence')


def self_check():
    """Contract invariants asserted without any external state."""
    assert canonical({'b': 1, 'a': 2}) == '{"a":2,"b":1}'
    assert digest({'a': 1}) == digest({'a': 1})
    assert nonempty(' x ') and not nonempty('  ')
    assert exact_span('abcdef', {'start': 1, 'end': 3}, 'bc')
    assert not exact_span('abcdef', {'start': 1, 'end': 3}, 'bd')
    assert spans_overlap({'start': 0, 'end': 5}, {'start': 4, 'end': 9})
    assert not spans_overlap({'start': 0, 'end': 5}, {'start': 5, 'end': 9})
    assert claim_state([], 'C1') == 'no_evidence'
    assert claim_state([{'claim_id': 'C1', 'state': 'verified'},
                        {'claim_id': 'C1', 'state': 'contradicted'}], 'C1') == 'contradicted'
    assert claim_state([{'claim_id': 'C1', 'state': 'reported'},
                        {'claim_id': 'C1', 'state': 'verified'}], 'C1') == 'reported'
    assert not defensible_verification('literature', 'source_inspection')
    assert not defensible_verification('literature', 'unverified', 'verified')
    assert defensible_verification('code', 'hash_match', 'verified')
    assert defensible_verification('literature', 'unverified', 'reported')
    assert defensible_verification('literature', 'unverified', 'contradicted')
    assert not defensible_verification('literature', 'source_inspection', 'contradicted')
    assert set(FAULTY_CLASSES).isdisjoint(ROBUSTNESS_CLASSES)
    assert set(FAULTY_CLASSES) <= set(DEFECT_CLASSES)
    assert 'robustness_defect_rewording' in DEFECT_CLASSES
    assert 'robustness_paraphrase' not in DEFECT_CLASSES
    assert set(SUCCESSFUL_STOPS) <= set(STOP_REASONS)
    for name in ('ledger', 'evaluation', 'detection', 'impact', 'loop'):
        assert SCHEMAS[name].endswith('@1')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true', help='assert contract invariants')
    args = parser.parse_args()
    if args.self_check:
        return self_check()
    print('schemas: ' + ', '.join(SCHEMAS[k] for k in sorted(SCHEMAS)))
    print('faulty classes: ' + ', '.join(FAULTY_CLASSES))
    print('robustness classes: ' + ', '.join(ROBUSTNESS_CLASSES))
    print('claim states: ' + ', '.join(CLAIM_STATES))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
