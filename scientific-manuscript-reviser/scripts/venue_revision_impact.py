#!/usr/bin/env python3
"""Check that a venue-aware revision did not strengthen science or hide a boundary.

A venue-driven revision may change how a contribution is presented, ordered and
phrased. It may not change what the paper establishes. This gate enforces that:

  * a contribution's support status never rises without new evidence,
  * a novelty or priority claim is not newly introduced without inspected prior work,
  * a limitation or evidence boundary is not removed to reduce perceived review risk,
  * a deleted limitation is not relabelled as a presentational edit.

Editing prose to hide a weakness is a scientific change wearing a presentation
label, and this gate reports it as one.
"""
import argparse
import json
from pathlib import Path

import compare_invariants as ci
import venue_intelligence_core as vic

NOTE = ('Venue-aware revision check. It compares declared positioning before and after the '
        'revision and blocks strengthening that no new evidence supports. It does not decide '
        'whether the remaining science is correct.')

RANK = {'UNSUPPORTED': 0, 'UNKNOWN': 0, 'PLANNED': 1, 'PARTIALLY_SUPPORTED': 2, 'SUPPORTED': 3}


def _impact(before, after, declaration):
    errors, unknown = [], []
    required = {'schema', 'manuscript_digest', 'before_digest', 'after_digest', 'edits',
                'strengthened_ids', 'removed_boundaries', 'missing_context'}
    if not isinstance(declaration, dict) or set(declaration) != required:
        return {'status': 'FAIL', 'errors': ['invalid venue revision impact fields']}
    if declaration['schema'] != 'venue-revision-impact@1':
        errors.append('invalid venue revision impact schema')
    for key, artifact in (('before', before), ('after', after)):
        if not isinstance(artifact, dict) or artifact.get('schema') != vic.SCHEMAS['positioning']:
            errors.append('a validated ' + key + ' positioning is required')
            return {'status': 'FAIL', 'errors': errors}
        if declaration[key + '_digest'] != ci.digest(artifact):
            errors.append('stale ' + key + ' positioning binding')
    if not isinstance(declaration['missing_context'], list) or \
            any(not ci.nonempty(x) for x in declaration['missing_context']):
        errors.append('missing_context must be explicit strings')

    old = {c['id']: c for c in before.get('contributions', [])}
    new = {c['id']: c for c in after.get('contributions', [])}
    edits = declaration['edits']
    if not isinstance(edits, list):
        return {'status': 'FAIL', 'errors': errors + ['edits must be a list']}

    edit_ids = []
    for i, edit in enumerate(edits):
        label = 'edits[' + str(i) + ']'
        fields = {'id', 'contribution_ids', 'change', 'repair_kind', 'new_evidence_ids',
                  'new_prior_work', 'presents_as'}
        if not isinstance(edit, dict) or set(edit) != fields:
            errors.append(label + ' has invalid or missing fields')
            continue
        if not ci.nonempty(edit['id']) or edit['repair_kind'] not in vic.REPAIR_KINDS \
                or not ci.nonempty(edit['change']):
            errors.append(label + ' has an invalid id, repair kind or change description')
            continue
        edit_ids.append(edit['id'])
        if not isinstance(edit['new_evidence_ids'], list) or \
                any(not ci.nonempty(x) for x in edit['new_evidence_ids']):
            errors.append(label + ' new_evidence_ids must be explicit ids')
        if not isinstance(edit['new_prior_work'], list):
            errors.append(label + ' new_prior_work must be a list')
        for cid in edit['contribution_ids']:
            if cid not in new:
                errors.append(label + ' names a contribution absent from the revised positioning')
                continue
            old_c, new_c = old.get(cid), new[cid]
            if old_c is None:
                unknown.append('contribution ' + cid + ' is new in this revision')
                continue
            # Support status is evidence-derived and venue-independent.
            if RANK.get(new_c.get('support_status'), 0) > RANK.get(old_c.get('support_status'), 0):
                if not edit['new_evidence_ids']:
                    errors.append(label + ' raises the support status of ' + cid + ' from '
                                  + str(old_c.get('support_status')) + ' to '
                                  + str(new_c.get('support_status')) + ' without new evidence')
                else:
                    unknown.append('contribution ' + cid + ' support rose with new evidence '
                                   + ', '.join(edit['new_evidence_ids']) + '; re-audit is required')
            # Novelty cannot be manufactured by rewording.
            was_claimed = old_c.get('novelty') not in (None, 'NOT_CLAIMED', 'UNVERIFIED')
            now_claimed = new_c.get('novelty') not in (None, 'NOT_CLAIMED', 'UNVERIFIED')
            if now_claimed and not was_claimed and not edit['new_prior_work']:
                errors.append(label + ' introduces a novelty claim for ' + cid
                              + ' without inspected prior work')
            if new_c.get('novelty') == 'ESTABLISHED_BY_CHECKED_PRIOR_WORK' \
                    and not new_c.get('closest_prior_work'):
                errors.append(label + ' establishes novelty for ' + cid + ' without naming closest prior work')

            # Boundaries are part of the science, not of the presentation.
            old_limit, new_limit = old_c.get('evidence_limits'), new_c.get('evidence_limits')
            if ci.nonempty(old_limit) and not ci.nonempty(new_limit):
                if edit['repair_kind'] in ('TEXT_ONLY', 'CLAIM_CALIBRATION'):
                    errors.append(label + ' removes the evidence boundary of ' + cid
                                  + ' while labelled ' + edit['repair_kind']
                                  + '; a deleted limitation is not a presentation change')
                else:
                    unknown.append('contribution ' + cid + ' lost its evidence boundary; human review required')
    if len(edit_ids) != len(set(edit_ids)):
        errors.append('duplicate edit id')

    declared_strengthened = declaration['strengthened_ids']
    if not isinstance(declared_strengthened, list):
        errors.append('strengthened_ids must be a list')
    measured = [e['id'] for e in edits if isinstance(e, dict)
                and e.get('presents_as') in ('STRONGER_CLAIM', 'HIGHER_SUPPORT')]
    for item in declared_strengthened:
        if item not in edit_ids:
            errors.append('strengthened_ids names an unknown edit: ' + str(item))
    for edit_id in measured:
        if edit_id not in declared_strengthened:
            errors.append('edit ' + edit_id + ' presents a stronger claim but was not declared')
    removed = declaration['removed_boundaries']
    if not isinstance(removed, list) or any(not ci.nonempty(x) for x in removed):
        errors.append('removed_boundaries must be explicit contribution ids')
    for cid in removed:
        if cid not in new:
            errors.append('removed_boundaries names an unknown contribution: ' + str(cid))

    unresolved = list(declaration['missing_context']) + unknown
    return {'status': 'FAIL' if errors else 'NEEDS_REVIEW' if unresolved else 'PASS',
            'schema': vic.SCHEMAS['impact'], 'digest': ci.digest(declaration),
            'support_before': {c['id']: old[c['id']].get('support_status') for c in before.get('contributions', [])
                               if c['id'] in old},
            'support_after': {c['id']: new[c['id']].get('support_status') for c in after.get('contributions', [])
                              if c['id'] in new},
            'strengthened_edits': measured, 'removed_boundaries': removed,
            'errors': errors, 'unresolved': unresolved, 'note': NOTE}


def validate(before, after, declaration):
    try:
        return _impact(before, after, declaration)
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid venue revision impact artifact: ' + str(exc)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--impact', type=Path, required=True)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    args = parser.parse_args()
    try:
        read = lambda p: json.loads(p.read_text(encoding='utf-8'))
        result = validate(read(args.before), read(args.after), read(args.impact))
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 3 if result['status'] == 'FAIL' else 4


if __name__ == '__main__':
    raise SystemExit(main())
