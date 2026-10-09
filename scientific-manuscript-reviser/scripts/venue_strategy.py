#!/usr/bin/env python3
"""Venue-aware paper strategy layered on the existing blueprint contract.

This is not a second blueprint. The scientific blueprint stays authoritative for
claims, evidence and gaps; this layer declares which framing and ordering to use
for a target venue and checks that the choice is honest.

Four rules are enforced here:
  * a framing must rest on an actually different scientific anchor, not a
    rephrasing of the same story,
  * a venue preference is never a reason to add an experiment: a proposed
    experiment must name a logic gap it resolves,
  * every scientific gap carried by the blueprint must remain visible,
  * a contribution may not be foregrounded beyond its evidence-derived support.

Without a venue profile the strategy is venue-neutral and exercises no
venue-specific requirement.
"""
import argparse
import json
from pathlib import Path

import architect as arch
import compare_invariants as ci
import venue_intelligence_core as vic

NOTE = ('Venue strategy selects framing, ordering and emphasis. It cannot create a '
        'contribution, add evidence, remove a scientific gap or change a support status. '
        'Experiments are proposed to resolve a named logic gap, never to match venue taste.')

AUTHORED_FIELDS = {'schema', 'blueprint_digest', 'positioning_digest', 'framings',
                   'selected_framing_id', 'section_strategy', 'experiment_requests',
                   'venue_alignment', 'missing_context'}
FRAMING_FIELDS = {'id', 'central_scientific_anchor', 'opening_move', 'emphasised_contribution_ids',
                  'advantage', 'sacrifice', 'best_when', 'rhetorical_only'}
SECTION_FIELDS = {'section_id', 'argument_job', 'contribution_ids', 'claim_ids', 'proportion'}


def _strategy(blueprint, positioning, declaration, profile, material_numbers):
    errors, unknown = [], []
    if not isinstance(blueprint, dict) or blueprint.get('schema') != 'manuscript-blueprint@1':
        return {'status': 'FAIL', 'errors': ['a manuscript-blueprint@1 is required before venue strategy']}
    if not isinstance(positioning, dict) or positioning.get('schema') != vic.SCHEMAS['positioning']:
        return {'status': 'FAIL', 'errors': ['a validated contribution positioning is required']}
    if not isinstance(declaration, dict) or set(declaration) != AUTHORED_FIELDS:
        return {'status': 'FAIL', 'errors': ['invalid venue strategy fields']}
    if declaration['schema'] != 'venue-strategy@1':
        errors.append('invalid venue strategy schema')
    if declaration['blueprint_digest'] != ci.digest(blueprint):
        errors.append('stale blueprint binding')
    if declaration['positioning_digest'] != ci.digest(positioning):
        errors.append('stale positioning binding')
    if not isinstance(declaration['missing_context'], list) or \
            any(not ci.nonempty(x) for x in declaration['missing_context']):
        errors.append('missing_context must be explicit strings')

    contributions = {c['id']: c for c in positioning.get('contributions', [])}
    supported = {cid for cid, c in contributions.items()
                 if vic.contribution_supported_by_evidence(c.get('support_status'))}
    claims = {c['id']: c for c in blueprint.get('claims', [])}
    sections = {s['id']: s for s in blueprint.get('sections', [])}
    paragraphs = {p['id']: p for s in blueprint.get('sections', [])
                  for sub in s.get('subsections', []) for p in sub.get('paragraphs', [])}
    # Scientific gaps are structural facts of the blueprint, not presentation. They
    # must survive the venue layer unchanged.
    blueprint_gap_findings = {g['finding_id'] for g in blueprint.get('gaps', [])}
    for paragraph in paragraphs.values():
        if paragraph.get('gap_marker'):
            blueprint_gap_findings.update(paragraph.get('finding_ids', []))

    framings = declaration['framings']
    if not isinstance(framings, list) or not framings:
        return {'status': 'FAIL', 'errors': errors + ['venue strategy needs at least one framing']}
    anchors, signatures, framing_ids = set(), set(), []
    for i, framing in enumerate(framings):
        label = 'framings[' + str(i) + ']'
        if not isinstance(framing, dict) or set(framing) != FRAMING_FIELDS:
            errors.append(label + ' has invalid or missing fields')
            continue
        if not ci.nonempty(framing['id']) or not ci.nonempty(framing['central_scientific_anchor']) \
                or not all(ci.nonempty(framing[k]) for k in ('opening_move', 'advantage', 'sacrifice', 'best_when')):
            errors.append(label + ' needs an id, a scientific anchor and all framing fields')
            continue
        framing_ids.append(framing['id'])
        if type(framing['rhetorical_only']) is not bool:
            errors.append(label + ' rhetorical_only must be a boolean')
        if framing['rhetorical_only']:
            errors.append(label + ' is marked rhetorical only; a venue framing must rest on a '
                          'different scientific anchor, not a rephrasing')
        anchor = framing['central_scientific_anchor'].strip().lower()
        if anchor in anchors:
            errors.append(label + ' repeats another framing anchor; alternatives must be '
                          'scientifically different')
        anchors.add(anchor)
        signature = (anchor, tuple(sorted(framing['emphasised_contribution_ids'])))
        if signature in signatures:
            errors.append(label + ' duplicates another framing')
        signatures.add(signature)
        for cid in framing['emphasised_contribution_ids']:
            if cid not in contributions:
                errors.append(label + ' emphasises an unknown contribution: ' + str(cid))
            elif cid not in supported:
                errors.append(label + ' emphasises contribution ' + str(cid)
                              + ' whose support status is ' + str(contributions[cid].get('support_status'))
                              + '; framing cannot upgrade support')
    if len(framing_ids) != len(set(framing_ids)):
        errors.append('duplicate framing id')
    selected = declaration['selected_framing_id']
    if selected not in framing_ids:
        errors.append('selected_framing_id must name a declared framing')

    # Section strategy: each major section states its argument job and which
    # contribution it serves, so venue emphasis stays traceable to the science.
    seen_sections, section_ids = [], []
    for i, item in enumerate(declaration['section_strategy']):
        label = 'section_strategy[' + str(i) + ']'
        if not isinstance(item, dict) or set(item) != SECTION_FIELDS:
            errors.append(label + ' has invalid or missing fields')
            continue
        if item['section_id'] not in sections:
            errors.append(label + ' names an unknown blueprint section: ' + str(item['section_id']))
            continue
        if not ci.nonempty(item['argument_job']) or not ci.nonempty(item['proportion']):
            errors.append(label + ' needs an argument job and a proportion')
        if any(x not in contributions for x in item['contribution_ids']):
            errors.append(label + ' names an unknown contribution')
        if any(x not in claims for x in item['claim_ids']):
            errors.append(label + ' names an unknown claim')
        seen_sections.append(item['section_id'])
        section_ids.append(item['section_id'])
    if len(section_ids) != len(set(section_ids)):
        errors.append('duplicate section strategy entry')
    for sid in sections:
        if sid not in seen_sections:
            unknown.append('blueprint section ' + sid + ' has no venue strategy entry')

    # A venue preference never justifies an experiment. Each request must resolve
    # a named logic gap and declare its identification conditions up front.
    requests = declaration['experiment_requests']
    request_ids = []
    required_req = {'id', 'resolves_logic_gap', 'hypothesis', 'alternative_explanations',
                    'comparison_and_control', 'budget_and_data_parity', 'observable',
                    'identifiability', 'completion_condition', 'supports_if', 'refutes_if',
                    'justified_by'}
    for i, request in enumerate(requests):
        label = 'experiment_requests[' + str(i) + ']'
        if not isinstance(request, dict) or set(request) != required_req:
            errors.append(label + ' must declare the full identification contract')
            continue
        request_ids.append(request['id'])
        for key in required_req - {'id', 'alternative_explanations'}:
            if not ci.nonempty(request[key]):
                errors.append(label + ' needs a nonempty ' + key)
        if not isinstance(request['alternative_explanations'], list) or \
                not request['alternative_explanations'] or \
                any(not ci.nonempty(x) for x in request['alternative_explanations']):
            errors.append(label + ' must name the alternative explanations it rules out')
        if request['justified_by'] not in ('SCIENTIFIC_GAP', 'IDENTIFIABILITY'):
            errors.append(label + ' must be justified by a scientific gap or an identifiability '
                          'problem, not by venue preference')
        if request['resolves_logic_gap'] not in blueprint_gap_findings:
            errors.append(label + ' does not resolve a logic gap recorded in the blueprint')
    if len(request_ids) != len(set(request_ids)):
        errors.append('duplicate experiment request id')

    # Venue alignment, when a profile is present.
    alignment = declaration['venue_alignment']
    if not isinstance(alignment, dict) or set(alignment) != {'contribution_type_ids', 'fit_note'}:
        errors.append('venue_alignment must declare contribution type ids and a fit note')
    else:
        if any(not ci.nonempty(x) for x in alignment['contribution_type_ids']):
            errors.append('venue alignment ids must be explicit')
        if not ci.nonempty(alignment['fit_note']):
            errors.append('venue alignment needs a fit note')
        if profile is None and alignment['contribution_type_ids']:
            errors.append('a venue-neutral strategy cannot claim official contribution categories')
        if profile is not None:
            published = {t['id'] for t in profile.get('contribution_types', [])}
            for item in alignment['contribution_type_ids']:
                if item not in published:
                    errors.append('venue alignment names a category the profile does not publish: ' + item)
    if profile is None:
        unknown.append('venue-neutral strategy: no policy profile, so no official requirement applies')

    # Scan only the authored content for numbers, never the schema version string
    # (the "1" in venue-strategy@1 is not a scientific value).
    scanned = {k: v for k, v in declaration.items() if k != 'schema'}
    for number in ci.NUMBER.findall(json.dumps(scanned, ensure_ascii=False)):
        if number not in material_numbers:
            errors.append('strategy invents a numeric value not present in the material: ' + number)
    unresolved = list(declaration['missing_context']) + unknown
    return {'status': 'FAIL' if errors else 'NEEDS_REVIEW' if unresolved else 'PASS',
            'schema': vic.SCHEMAS['venue_strategy'], 'digest': ci.digest(declaration),
            'selected_framing_id': selected, 'framing_count': len(framing_ids),
            'emphasised_contribution_ids': sorted({c for f in framings if isinstance(f, dict)
                                                   for c in f.get('emphasised_contribution_ids', [])}),
            'gap_findings_preserved': sorted(blueprint_gap_findings),
            'experiment_request_count': len(request_ids),
            'errors': errors, 'unresolved': unresolved, 'note': NOTE}


def validate(blueprint, positioning, declaration, profile=None, material_numbers=None):
    try:
        if material_numbers is None:
            material_numbers = set()
        return _strategy(blueprint, positioning, declaration, profile, material_numbers)
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid venue strategy artifact: ' + str(exc)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strategy', type=Path, required=True)
    parser.add_argument('--blueprint', type=Path, required=True)
    parser.add_argument('--positioning', type=Path, required=True)
    parser.add_argument('--material-numbers', type=Path,
                        help='JSON list of numeric strings present in the research material')
    parser.add_argument('--venue')
    parser.add_argument('--year', type=int)
    parser.add_argument('--track')
    parser.add_argument('--registry', type=Path)
    args = parser.parse_args()
    try:
        import venue_registry
        read = lambda p: json.loads(p.read_text(encoding='utf-8')) if p else None
        profile = None
        if args.venue:
            if args.year is None or not args.track or not args.registry:
                raise ValueError('--venue requires --year, --track and --registry')
            profile, _n, _m = venue_registry.Registry(args.registry).resolve(args.venue, args.year, args.track)
        numbers = set(read(args.material_numbers) or [])
        result = validate(read(args.blueprint), read(args.positioning), read(args.strategy), profile, numbers)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 3 if result['status'] == 'FAIL' else 4


if __name__ == '__main__':
    raise SystemExit(main())
