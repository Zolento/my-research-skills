#!/usr/bin/env python3
"""Validate a declared contribution positioning against evidence and venue policy.

This gate cannot discover what a paper contributes. Establishing a contribution,
its closest prior work and its knowledge increment is scientific judgment. The
engine therefore validates a declared positioning and enforces the rules that
keep a positioning honest:

  * support status comes only from evidence, never from wording,
  * a novelty or priority assertion requires an inspected prior-work record,
  * a claimed structural equivalence must name its distinguishing property,
  * an official contribution category must exist in the cited venue profile,
  * internal classes are never presented as the venue's own labels.

Read-only, stdlib only, no network. Without a venue profile the run stays
venue-neutral and reports the official-category mapping as NOT_PUBLISHED.
"""
import argparse
import json
from pathlib import Path

import audit_coherence as ac
import compare_invariants as ci
import venue_intelligence_core as vic
import venue_registry

NOTE = ('Declared positioning, evidence-derived support status, venue-dependent fit. '
        'This layer does not judge novelty, significance or soundness itself, and no '
        'probability of acceptance is estimated or implied.')


def _claim_support(claim_ids, ledger):
    """Support status derived only from ledger evidence states.

    A claim with no ledger record is UNKNOWN, never SUPPORTED. Missing evidence is
    not evidence of support, and a reported-only claim never becomes established.
    """
    if ledger is None:
        return 'UNKNOWN', []
    records = ledger.get('evidence', [])
    if not any(r.get('claim_id') == cid for cid in claim_ids for r in records):
        # No evidence at all is 'no_evidence', which this layer reports as UNKNOWN:
        # missing evidence must never read as a refuted claim.
        return 'UNKNOWN', []
    states, used = [], []
    for cid in claim_ids:
        relevant = [r for r in records if r.get('claim_id') == cid]
        used.extend(r.get('id') for r in relevant)
        states.append(vic_claim_state(relevant))
    if not states:
        return 'UNKNOWN', used
    if any(s == 'contradicted' for s in states):
        return 'UNSUPPORTED', used
    if all(s == 'verified' for s in states):
        return 'SUPPORTED', used
    if any(s in ('verified', 'reported') for s in states):
        return 'PARTIALLY_SUPPORTED', used
    if any(s == 'unknown' for s in states):
        return 'UNKNOWN', used
    return 'UNSUPPORTED', used


def vic_claim_state(records):
    """A claim's evidence state, using the ledger's own aggregation rule."""
    if not records:
        return 'no_evidence'
    states = {r.get('state') for r in records}
    for candidate in ('contradicted', 'unknown', 'reported', 'verified'):
        if candidate in states:
            return candidate
    return 'unknown'


def _prior_work_ok(records):
    """At least one inspected, source-bound prior-work record."""
    for record in records or []:
        if record.get('status') == 'CHECKED' and ci.nonempty(record.get('reference')) \
                and ci.nonempty(record.get('digest')):
            return True
    return False


def _has_novelty_assertion(text):
    lowered = (text or '').lower()
    return any(marker in lowered for marker in vic.NOVELTY_ASSERTION_MARKERS)


def _positioning(graph, coherence, ledger, declaration, profile):
    errors, unknown = [], []
    required = {'schema', 'manuscript_digest', 'target_venue', 'contributions', 'missing_context'}
    if not isinstance(declaration, dict) or set(declaration) != required:
        return {'status': 'FAIL', 'errors': ['invalid positioning declaration fields']}
    if declaration['schema'] != 'contribution-positioning@1':
        errors.append('invalid positioning schema')
    target = declaration['target_venue']
    if not isinstance(target, dict) or set(target) != {'venue', 'year', 'track', 'specified'}:
        errors.append('target_venue must carry venue, year, track and specified')
        target = {'specified': False}
    if not isinstance(declaration['missing_context'], list) or \
            any(not ci.nonempty(x) for x in declaration['missing_context']):
        errors.append('missing_context must be explicit strings')
    if declaration['contributions'] is None or not isinstance(declaration['contributions'], list):
        errors.append('contributions must be a list')
        return {'status': 'FAIL', 'errors': errors}

    # Resolve the venue profile by exact scope only. No fallback, no inheritance.
    profile_obj, profile_note = None, None
    if target.get('specified'):
        # `year` is an integer by contract, so validate it by type, not with the
        # string-only nonempty() helper.
        if not ci.nonempty(target.get('venue')) or type(target.get('year')) is not int \
                or not ci.nonempty(target.get('track')):
            errors.append('a specified target needs a concrete venue, year and track')
        else:
            registry = venue_registry.Registry(profile[0]) if profile else None
            if registry is None:
                profile_note = 'no policy registry supplied; official category mapping unavailable'
                unknown.append(profile_note)
            else:
                resolved, filename, missing = registry.resolve(target['venue'], target['year'], target['track'])
                if resolved is None:
                    profile_note = ('no policy profile for the requested scope; '
                                    'venue fit is UNKNOWN and no mandatory rule applies')
                    unknown.append(profile_note)
                else:
                    profile_obj = resolved
    else:
        profile_note = 'venue-neutral run: no target venue was specified'

    nodes = {n['id']: n for n in graph['nodes']} if isinstance(graph, dict) else {}
    official = {t.get('label'): t for t in (profile_obj or {}).get('contribution_types', [])}

    results, support_seen = [], {}
    ids = []
    for i, item in enumerate(declaration['contributions']):
        label = 'contributions[' + str(i) + ']'
        fields = {'id', 'internal_type', 'role', 'claim', 'claim_ids', 'novelty',
                  'novelty_delta', 'prior_work', 'closest_prior_work', 'structural_equivalence',
                  'official_category', 'not_replaceable_by', 'evidence_limits'}
        if not isinstance(item, dict) or set(item) != fields:
            errors.append(label + ' has invalid or missing fields')
            continue
        if not ci.nonempty(item['id']) or item['internal_type'] not in vic.INTERNAL_CONTRIBUTION_TYPES \
                or item['role'] not in vic.CONTRIBUTION_ROLE or not ci.nonempty(item['claim']):
            errors.append(label + ' has an invalid id, internal type, role or claim statement')
            continue
        ids.append(item['id'])
        if item['novelty'] not in vic.NOVELTY_STATUS:
            errors.append(label + ' has an invalid novelty status')
        if not isinstance(item['claim_ids'], list) or any(x not in nodes for x in item['claim_ids']):
            errors.append(label + ' cites a claim id that is not in the argument graph')
        else:
            for cid in item['claim_ids']:
                if nodes[cid].get('type') not in ac.CLAIM_TYPES:
                    errors.append(label + ' cites a graph node that is not a claim-bearing type')
        if item['role'] == 'not_a_contribution' and item['claim_ids']:
            errors.append(label + ' a non-contribution cannot foreground claims')
        if item['role'] in ('primary', 'secondary') and not item['claim_ids']:
            errors.append(label + ' a presented contribution needs a source-bound claim')

        support, evidence_ids = _claim_support(item['claim_ids'], ledger)
        support_seen[item['id']] = support

        # Novelty assertions must rest on inspected prior work. Wording cannot
        # establish priority, and an unverifiable claim stays UNVERIFIED.
        asserts_novelty = _has_novelty_assertion(item['claim']) or _has_novelty_assertion(item['novelty_delta'])
        prior_checked = _prior_work_ok(item['prior_work'])
        if asserts_novelty and not prior_checked:
            errors.append(label + ' asserts novelty or priority without an inspected '
                          'source-bound prior-work record')
        if item['novelty'] in ('ESTABLISHED_BY_CHECKED_PRIOR_WORK', 'INCREMENTAL_DELTA',
                               'CONTRADICTED_BY_PRIOR_WORK') and not prior_checked:
            errors.append(label + ' declares a novelty status that requires checked prior work')
        if not prior_checked and item['novelty'] != 'NOT_CLAIMED' \
                and item['novelty'] == 'ESTABLISHED_BY_CHECKED_PRIOR_WORK':
            errors.append(label + ' cannot establish novelty without checked prior work')

        # Structural equivalence: naming a twin is a claim about the science, so
        # the distinguishing property must be stated explicitly.
        equivalence = item['structural_equivalence']
        if not isinstance(equivalence, dict) or set(equivalence) != {'is_structurally_equivalent',
                                                                    'twin_reference', 'distinguishing_property'}:
            errors.append(label + ' structural_equivalence must state the flag, the twin and the difference')
        else:
            if equivalence['is_structurally_equivalent'] is True \
                    and not ci.nonempty(equivalence['distinguishing_property']):
                errors.append(label + ' claims structural equivalence without naming a '
                              'distinguishing property, so it may be prior work reworded')
            if equivalence['is_structurally_equivalent'] is True \
                    and not ci.nonempty(equivalence['twin_reference']):
                errors.append(label + ' claims structural equivalence without naming the twin')

        # Official category mapping is declared and checked against the profile.
        mapping = 'UNKNOWN'
        if item['official_category'] is None:
            mapping = 'NOT_PUBLISHED' if profile_obj is None else 'UNKNOWN'
            if profile_obj is not None and not official:
                mapping = 'NOT_PUBLISHED'
        elif official and item['official_category'] in official:
            mapping = 'DIRECT_MATCH'
        elif official:
            errors.append(label + ' names an official category not published by the cited profile: '
                          + str(item['official_category']))
            mapping = 'NO_MATCH'
        else:
            unknown.append(label + ' official category cannot be checked without a venue profile')
        if item['not_replaceable_by'] is not None and not ci.nonempty(item['not_replaceable_by']):
            errors.append(label + ' not_replaceable_by must be a non-empty statement or null')
        if item['evidence_limits'] is not None and not ci.nonempty(item['evidence_limits']):
            errors.append(label + ' evidence_limits must be a non-empty statement or null')

        results.append({'id': item['id'], 'internal_type': item['internal_type'], 'role': item['role'],
                        'claim': item['claim'], 'claim_ids': list(item['claim_ids']),
                        'evidence_ids': evidence_ids, 'support_status': support,
                        'novelty': item['novelty'] if prior_checked or item['novelty'] == 'NOT_CLAIMED'
                                   else 'UNVERIFIED',
                        'closest_prior_work': item['closest_prior_work'],
                        'structural_equivalence': equivalence,
                        'official_category': item['official_category'], 'mapping_verdict': mapping,
                        'not_replaceable_by': item['not_replaceable_by'],
                        'evidence_limits': item['evidence_limits']})

    if len(ids) != len(set(ids)):
        errors.append('duplicate contribution id')
    primaries = [r for r in results if r['role'] == 'primary']
    if len(primaries) > 1:
        errors.append('a paper cannot carry more than one primary contribution')
    if results and not primaries and not any(r['role'] == 'not_a_contribution' for r in results):
        unknown.append('no contribution is presented as primary')
    for r in results:
        if r['role'] == 'primary' and r['support_status'] in ('UNSUPPORTED', 'UNKNOWN'):
            unknown.append('primary contribution ' + r['id'] + ' is ' + r['support_status']
                           + '; it cannot be presented as established')
        if r['support_status'] == 'PLANNED':
            unknown.append('contribution ' + r['id'] + ' rests on planned work')

    if coherence is not None and isinstance(coherence, dict):
        central = set((graph or {}).get('central_claim_ids', []))
        covered = {cid for r in results for cid in r['claim_ids']}
        for cid in sorted(central - covered):
            unknown.append('central claim ' + cid + ' is not mapped to any declared contribution')

    unresolved = list(declaration['missing_context']) + unknown
    return {'status': 'FAIL' if errors else 'NEEDS_REVIEW' if unresolved else 'PASS',
            'schema': vic.SCHEMAS['positioning'], 'digest': ci.digest(declaration),
            'manuscript_digest': declaration.get('manuscript_digest'),
            'target_venue': target, 'venue_profile': profile_note,
            'contributions': results,
            'primary_contribution_ids': [r['id'] for r in primaries],
            'support_status_values': support_seen,
            'errors': errors, 'unresolved': unresolved, 'note': NOTE}


def _positioning_entry(graph=None, coherence=None, ledger=None, declaration=None, registry=None):
    try:
        return _positioning(graph, coherence, ledger, declaration, registry)
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid positioning artifact: ' + str(exc)]}


def validate(graph, coherence, ledger, declaration, registry=None):
    return _positioning_entry(graph, coherence, ledger, declaration, registry)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--positioning', type=Path, required=True)
    parser.add_argument('--graph', type=Path)
    parser.add_argument('--coherence', type=Path)
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--registry', type=Path)
    args = parser.parse_args()
    try:
        read = lambda p: json.loads(p.read_text(encoding='utf-8')) if p else None
        result = validate(read(args.graph), read(args.coherence), read(args.ledger),
                          read(args.positioning), (args.registry,) if args.registry else None)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 3 if result['status'] == 'FAIL' else 4


if __name__ == '__main__':
    raise SystemExit(main())
