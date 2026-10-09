#!/usr/bin/env python3
"""Explainable venue readiness report.

This is the single reporting authority. It aggregates the upstream gates and
never recomputes their judgements, so an issue cannot be softened by being
summarised twice.

It deliberately does NOT produce:
  * an acceptance probability of any kind,
  * an arbitrary weighted overall score,
  * a reviewer-preference simulation.

The overall verdict is the worst verdict of its inputs, with an explicit list of
the reasons for it.
"""
import argparse
import json
from pathlib import Path

import compare_invariants as ci
import venue_intelligence_core as vic

NOTE = ('Readiness aggregates upstream verdicts and never restates them more favourably. '
        'There is no acceptance probability and no weighted score. A blocker is a statement '
        'about evidence and stated requirements, not about the eventual decision.')

# Deterministic worst-case ordering. PASS is only reached when everything passes.
VERDICT_ORDER = {'FAIL': 0, 'MISSING': 1, 'NEEDS_REVIEW': 2, 'PASS': 3, 'NOT_APPLICABLE': 4}

PRIORITY_ORDER = ('BLOCKER', 'HIGH', 'MEDIUM', 'LOW')

INPUTS = ('coherence', 'positioning', 'venue_audit', 'compliance')


def _priority_for(issue_type, repair_kind, status):
    """Priority comes from the nature of the problem, not from a numeric weight."""
    if repair_kind in vic.SCIENCE_REPAIRS and issue_type in ('SCIENTIFIC_DEFECT', 'CONTRIBUTION_GAP'):
        return 'BLOCKER'
    if issue_type == 'SCIENTIFIC_DEFECT':
        return 'HIGH'
    if status == 'FAIL' and issue_type == 'COMPLIANCE_ISSUE':
        return 'BLOCKER'
    if issue_type in ('CONTRIBUTION_GAP', 'COMPLIANCE_ISSUE'):
        return 'HIGH'
    if issue_type == 'VENUE_FIT_RISK':
        return 'MEDIUM'
    return 'LOW'


def _aggregate(coherence, positioning, venue_audit, compliance, declaration):
    errors, unknown = [], []
    required = {'schema', 'manuscript_digest', 'coherence_digest', 'positioning_digest',
                'venue_audit_digest', 'compliance_digest', 'priorities', 'missing_context'}
    if not isinstance(declaration, dict) or set(declaration) != required:
        return {'status': 'FAIL', 'errors': ['invalid readiness report fields']}
    if declaration['schema'] != 'venue-readiness@1':
        errors.append('invalid readiness schema')
    if not isinstance(declaration['missing_context'], list) or \
            any(not ci.nonempty(x) for x in declaration['missing_context']):
        errors.append('missing_context must be explicit strings')
    if declaration['priorities'] is not None and not isinstance(declaration['priorities'], list):
        errors.append('priorities must be null or a list')
    for key, artifact in (('positioning', positioning), ('venue_audit', venue_audit),
                          ('compliance', compliance)):
        if artifact is None:
            errors.append('a readiness report requires a ' + key + ' result')
            continue
        if declaration[key + '_digest'] != ci.digest(artifact):
            errors.append('stale ' + key + ' binding')
    if coherence is not None and declaration['coherence_digest'] != ci.digest(coherence):
        errors.append('stale coherence binding')

    inputs = {}
    for key, artifact in (('coherence', coherence), ('positioning', positioning),
                          ('venue_audit', venue_audit), ('compliance', compliance)):
        if artifact is None:
            inputs[key] = 'MISSING'
        else:
            inputs[key] = artifact.get('status', 'MISSING')
    verdict = max(inputs.values(), key=lambda v: -VERDICT_ORDER.get(v, 0))

    # Strengths: supported contributions only. Wording never creates one.
    strengths = []
    for contribution in (positioning or {}).get('contributions', []):
        if contribution.get('support_status') == 'SUPPORTED':
            strengths.append({'kind': 'supported_contribution', 'id': contribution['id'],
                              'statement': contribution['claim'],
                              'evidence_ids': contribution.get('evidence_ids', [])})
    for finding in (coherence or {}).get('well_supported', []) or []:
        strengths.append({'kind': 'well_supported_argument', 'id': None,
                          'statement': finding.get('why', ''),
                          'evidence_ids': finding.get('node_ids', [])})

    # Defects and gaps, carrying the upstream classification unchanged.
    items = []
    for issue in (venue_audit or {}).get('issues', []):
        repair = issue.get('repair', {})
        priority = _priority_for(issue.get('issue_type'), repair.get('kind'),
                                 'FAIL' if issue.get('issue_type') == 'SCIENTIFIC_DEFECT' else 'PASS')
        items.append({'id': issue.get('id'), 'issue_type': issue.get('issue_type'),
                      'origin': issue.get('origin'), 'summary': issue.get('summary'),
                      'priority': priority, 'repair_kind': repair.get('kind'),
                      'repair_what': repair.get('what'),
                      'completion_condition': repair.get('completion_condition'),
                      'source_finding_ids': issue.get('source_finding_ids', [])})
    for check in (compliance or {}).get('checks', []):
        if check.get('status') in ('FAIL', 'NEEDS_REVIEW'):
            items.append({'id': check.get('id'), 'issue_type': 'COMPLIANCE_ISSUE',
                          'origin': 'compliance_layer',
                          'summary': 'submission requirement ' + str(check.get('id')),
                          'priority': 'BLOCKER' if check.get('status') == 'FAIL' else 'HIGH',
                          'repair_kind': 'TEXT_ONLY' if check.get('status') == 'FAIL' else 'HUMAN_DECISION',
                          'repair_what': check.get('why', 'resolve the stated requirement'),
                          'completion_condition': check.get('why', 'requirement is satisfied'),
                          'source_finding_ids': []})

    # Blockers must survive into the report. Losing one is an error.
    declared = declaration['priorities']
    if declared is None:
        unknown.append('repair priorities were not declared')
    else:
        declared_ids = []
        for entry in declared:
            if not isinstance(entry, dict) or set(entry) != {'item_id', 'priority', 'order'} or \
                    entry['priority'] not in PRIORITY_ORDER or type(entry['order']) is not int:
                errors.append('invalid priority entry')
                continue
            declared_ids.append(entry['item_id'])
            if entry['item_id'] not in {i['id'] for i in items}:
                errors.append('priority refers to an unknown item: ' + str(entry['item_id']))
        if len(declared_ids) != len(set(declared_ids)):
            errors.append('duplicate priority entry')
        computed = {i['id']: i['priority'] for i in items}
        for item in items:
            if computed[item['id']] == 'BLOCKER' and item['id'] not in declared_ids:
                errors.append('blocker ' + str(item['id']) + ' was omitted from the priority plan')
        for entry in declared:
            if isinstance(entry, dict) and entry.get('item_id') in computed and \
                    PRIORITY_ORDER.index(entry['priority']) > PRIORITY_ORDER.index(computed[entry['item_id']]):
                errors.append('priority for ' + str(entry['item_id']) + ' was demoted below ' + computed[entry['item_id']])

    # Mandatory requirements are reported separately from scientific quality.
    human = list((venue_audit or {}).get('unresolved', [])) + list((compliance or {}).get('unresolved', [])) \
        + list((positioning or {}).get('unresolved', []))
    # `unknown` holds readiness-level observations (for example an undeclared priority
    # plan). Emit them, so a clean-looking report cannot hide a review item.
    human.extend(unknown)
    human.extend(x for x in declaration['missing_context'])
    resolved = {'state': 'NEEDS_REVIEW' if human else 'NONE', 'items': sorted(set(human))}
    counts = {p: sum(1 for i in items if i['priority'] == p) for p in PRIORITY_ORDER}
    status = 'FAIL' if errors else 'NEEDS_REVIEW' if human else verdict
    return {'status': status,
            'schema': vic.SCHEMAS['readiness'], 'input_statuses': inputs,
            'verdict_reasons': [k + ' is ' + v for k, v in sorted(inputs.items())
                                if v != 'PASS' and v != 'NOT_APPLICABLE'],
            'strengths': strengths, 'items': items, 'priority_counts': counts,
            'human_decisions': resolved,
            'no_acceptance_probability': True, 'weighted_score': None,
            'errors': errors, 'note': NOTE}


def aggregate(coherence=None, positioning=None, venue_audit=None, compliance=None, declaration=None):
    try:
        return _aggregate(coherence, positioning, venue_audit, compliance, declaration)
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid readiness artifact: ' + str(exc)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    for name in INPUTS:
        parser.add_argument('--' + name.replace('_', '-'), dest=name, type=Path)
    args = parser.parse_args()
    try:
        read = lambda p: json.loads(p.read_text(encoding='utf-8')) if p else None
        result = aggregate(read(args.coherence), read(args.positioning), read(args.venue_audit),
                           read(args.compliance), read(args.report))
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 3 if result['status'] == 'FAIL' else 4


if __name__ == '__main__':
    raise SystemExit(main())
