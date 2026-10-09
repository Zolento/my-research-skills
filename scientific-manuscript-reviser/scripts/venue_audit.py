#!/usr/bin/env python3
"""Venue-aware evaluation layered on top of the venue-independent science audit.

The order is fixed and non-negotiable: the Scientific Coherence Audit runs first,
then this layer evaluates the same paper against a venue profile. That ordering is
enforced structurally. A scientific defect is never re-labelled as a venue risk,
and a venue fit judgement never changes a scientific verdict.

The layer reports eight criteria, classifies every issue by what kind of problem
it actually is, and carries each scientific finding through to the output. If a
profile is absent the run stays venue-neutral.
"""
import argparse
import json
from pathlib import Path

import audit_coherence as ac
import compare_invariants as ci
import venue_intelligence_core as vic
import venue_registry

NOTE = ('Venue-aware evaluation of a completed scientific audit. The venue layer cannot '
        'change a scientific verdict, raise a support status or hide a scientific finding. '
        'Fit is a qualitative judgement against a cited profile, not an acceptance probability.')


def _criteria(profile):
    """The eight criteria, annotated with the official criterion each one traces to."""
    by_dimension = {}
    for criterion in (profile or {}).get('review_criteria', []):
        by_dimension.setdefault(criterion.get('dimension'), criterion)
    return by_dimension


def _audit(positioning, coherence, declaration, profile, manuscript_digest):
    errors, unknown = [], []
    required = {'schema', 'manuscript_digest', 'positioning_digest', 'checks', 'issues',
                'carried_findings', 'missing_context'}
    if not isinstance(declaration, dict) or set(declaration) != required:
        return {'status': 'FAIL', 'errors': ['invalid venue-aware audit fields']}
    if declaration['schema'] != 'venue-aware-audit@1':
        errors.append('invalid venue-aware audit schema')
    if declaration['manuscript_digest'] != manuscript_digest:
        errors.append('venue-aware audit belongs to a different manuscript')
    if not isinstance(positioning, dict) or positioning.get('schema') != vic.SCHEMAS['positioning']:
        errors.append('a validated contribution positioning is required before venue evaluation')
        positioning = {'contributions': [], 'errors': []}
    if declaration['positioning_digest'] != ci.digest(positioning):
        errors.append('stale positioning binding')
    if not isinstance(declaration['missing_context'], list) or \
            any(not ci.nonempty(x) for x in declaration['missing_context']):
        errors.append('missing_context must be explicit strings')

    official = _criteria(profile)
    checks = declaration['checks']
    if not isinstance(checks, dict) or set(checks) != set(vic.VENUE_CRITERIA):
        return {'status': 'FAIL', 'errors': errors + ['all eight venue criteria must be inspected']}
    fit_values = {}
    for name, check in checks.items():
        if not isinstance(check, dict) or set(check) != {'fit', 'why', 'evidence_node_ids',
                                                         'official_criterion_id'}:
            errors.append('invalid criterion check: ' + name)
            continue
        if check['fit'] not in vic.FIT_LEVELS:
            errors.append('invalid fit level for ' + name)
        if not ci.nonempty(check['why']):
            errors.append('a criterion check needs a rationale: ' + name)
        if not isinstance(check['evidence_node_ids'], list) or \
                any(not ci.nonempty(x) for x in check['evidence_node_ids']):
            errors.append('criterion evidence must be explicit node ids: ' + name)
        fit_values[name] = check['fit']
        # An official criterion id must exist in the profile when a profile is present.
        if profile is not None:
            published = {c.get('id') for c in profile.get('review_criteria', [])}
            if check['official_criterion_id'] is not None and check['official_criterion_id'] not in published:
                errors.append(name + ' names an official criterion the profile does not publish')
            if name in official and check['official_criterion_id'] is None:
                unknown.append(name + ' has a published official criterion that was not cited')
        if profile is None and check['fit'] not in ('NOT_APPLICABLE', 'UNKNOWN'):
            # Without a profile there is no standard to compare against.
            errors.append(name + ' cannot claim a fit level without a venue profile')

    # Carry every scientific finding through. Dropping one is an error, because
    # that is exactly how a venue concern would erase a scientific defect.
    coherent = (coherence or {}).get('findings', []) + (coherence or {}).get('structural_diagnostics', [])
    by_id = {f.get('id'): f for f in coherent}
    carried = []
    for item in declaration['carried_findings']:
        if not isinstance(item, dict) or set(item) != {'finding_id', 'resolution'} or \
                not ci.nonempty(item['finding_id']) or not ci.nonempty(item['resolution']):
            errors.append('invalid carried finding entry')
            continue
        if item['finding_id'] not in by_id:
            errors.append('carried finding does not exist in the coherence audit: ' + item['finding_id'])
        carried.append(item['finding_id'])
    if len(carried) != len(set(carried)):
        errors.append('duplicate carried finding')
    serious = {fid for fid, f in by_id.items() if f.get('severity') in ('critical', 'major')}
    missing = serious - set(carried)
    if missing:
        errors.append('critical/major scientific findings were dropped by the venue layer: '
                      + ', '.join(sorted(missing)))

    ids, issue_types = [], []
    for i, issue in enumerate(declaration['issues']):
        label = 'issues[' + str(i) + ']'
        fields = {'id', 'issue_type', 'origin', 'criterion', 'source_finding_ids',
                  'evidence_node_ids', 'summary', 'why', 'repair'}
        if not isinstance(issue, dict) or set(issue) != fields:
            errors.append(label + ' has invalid or missing fields')
            continue
        if not ci.nonempty(issue['id']) or issue['issue_type'] not in vic.ISSUE_TYPES \
                or issue['origin'] not in vic.ISSUE_ORIGIN:
            errors.append(label + ' has an invalid id, issue type or origin')
            continue
        ids.append(issue['id'])
        issue_types.append(issue['issue_type'])
        if issue['criterion'] is not None and issue['criterion'] not in vic.VENUE_CRITERIA:
            errors.append(label + ' names an unknown venue criterion')
        if not ci.nonempty(issue['summary']) or not ci.nonempty(issue['why']):
            errors.append(label + ' needs a summary and a rationale')
        repair = issue['repair']
        if not isinstance(repair, dict) or set(repair) != {'kind', 'what', 'completion_condition'} or \
                repair['kind'] not in vic.REPAIR_KINDS or not ci.nonempty(repair['what']) or \
                not ci.nonempty(repair['completion_condition']):
            errors.append(label + ' needs a repair kind, an action and a completion condition')

        # Type and provenance must agree. A venue fit risk is never a scientific
        # defect, and a scientific defect must trace to a real finding.
        if issue['issue_type'] == 'SCIENTIFIC_DEFECT':
            if issue['origin'] != 'scientific_core':
                errors.append(label + ' a scientific defect must originate in the scientific core')
            if not issue['source_finding_ids']:
                errors.append(label + ' a scientific defect must cite the coherence finding it came from')
            for fid in issue['source_finding_ids']:
                if fid not in by_id:
                    errors.append(label + ' cites a nonexistent coherence finding')
        elif issue['issue_type'] == 'VENUE_FIT_RISK':
            if issue['origin'] != 'venue_layer':
                errors.append(label + ' a venue fit risk must originate in the venue layer')
            if profile is None:
                errors.append(label + ' cannot report a venue fit risk without a venue profile')
        elif issue['issue_type'] == 'CONTRIBUTION_GAP':
            if issue['origin'] not in ('scientific_core', 'venue_layer'):
                errors.append(label + ' a contribution gap must originate in the science or venue layer')
        elif issue['issue_type'] == 'COMPLIANCE_ISSUE':
            if issue['origin'] != 'compliance_layer':
                errors.append(label + ' a compliance issue must originate in the compliance layer')
        if issue['issue_type'] in ('VENUE_FIT_RISK', 'PRESENTATION_ISSUE') and issue['source_finding_ids']:
            errors.append(label + ' a venue or presentation issue must not re-label a scientific finding')

        # A serious scientific issue may not be repaired by wording alone.
        for fid in issue['source_finding_ids']:
            finding = by_id.get(fid)
            if finding and finding.get('severity') in ('critical', 'major') and \
                    repair['kind'] in ('TEXT_ONLY', 'CLAIM_CALIBRATION') and \
                    issue['issue_type'] == 'SCIENTIFIC_DEFECT':
                errors.append(label + ' a critical/major scientific defect cannot be closed by '
                              + repair['kind'])
    if len(ids) != len(set(ids)):
        errors.append('duplicate issue id')

    # Positioning must stay consistent with the venue layer.
    for contribution in positioning.get('contributions', []):
        if contribution.get('role') == 'primary' and contribution.get('support_status') \
                in ('UNSUPPORTED', 'UNKNOWN'):
            unknown.append('primary contribution ' + str(contribution.get('id')) + ' remains '
                           + str(contribution.get('support_status')))
    unresolved = list(declaration['missing_context']) + unknown
    if profile is None:
        unresolved.append('venue-neutral run: no policy profile, so venue fit remains unknown')
    return {'status': 'FAIL' if errors else 'NEEDS_REVIEW' if unresolved else 'PASS',
            'schema': vic.SCHEMAS['venue_audit'], 'digest': ci.digest(declaration),
            'fit': fit_values, 'issues': declaration['issues'],
            'issue_counts': {t: issue_types.count(t) for t in vic.ISSUE_TYPES},
            'carried_findings': sorted(carried, key=str),
            'venue_neutral': profile is None,
            'errors': errors, 'unresolved': unresolved, 'note': NOTE}


def _entry(positioning=None, coherence=None, declaration=None, profile=None, manuscript_digest=None):
    try:
        return _audit(positioning, coherence, declaration, profile, manuscript_digest)
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid venue-aware audit artifact: ' + str(exc)]}


def validate(positioning, coherence, declaration, profile=None, manuscript_digest=None):
    if manuscript_digest is None and isinstance(positioning, dict):
        manuscript_digest = positioning.get('manuscript_digest')
    return _entry(positioning, coherence, declaration, profile, manuscript_digest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--positioning', type=Path)
    parser.add_argument('--coherence', type=Path)
    parser.add_argument('--venue', help='venue name, with --year and --track')
    parser.add_argument('--year', type=int)
    parser.add_argument('--track')
    parser.add_argument('--registry', type=Path)
    args = parser.parse_args()
    try:
        read = lambda p: json.loads(p.read_text(encoding='utf-8')) if p else None
        profile = None
        if args.venue:
            if args.year is None or not args.track or not args.registry:
                raise ValueError('--venue requires --year, --track and --registry')
            profile, _name, _missing = venue_registry.Registry(args.registry).resolve(
                args.venue, args.year, args.track)
        result = validate(read(args.positioning), read(args.coherence), read(args.audit), profile)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 3 if result['status'] == 'FAIL' else 4


if __name__ == '__main__':
    raise SystemExit(main())
