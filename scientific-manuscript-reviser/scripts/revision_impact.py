#!/usr/bin/env python3
"""Map each declared edit to the dependent scientific elements and its required check.

Read-only. This gate never rewrites prose and never judges scientific truth. It
bounds the verification a declared edit forces and surfaces the human decisions
that automatic acceptance would hide.

    python3 scripts/revision_impact.py manuscript.md --before before.md \
      --original-facts before-facts.json --revised-facts after-facts.json \
      --plan plan.json [--graph graph.json]

``manuscript.md`` is the revised text. ``--before`` is the text the plan's
``original_span`` values are located in. The argument graph, when supplied, must
be digest-bound to the before text, because that is where the edited offsets live.
Exit 0 PASS, 3 FAIL, 4 NEEDS_REVIEW or invalid input.
"""
import argparse
import json
from pathlib import Path

from audit_coherence import NODE_TYPES, REPAIRS, validate_graph
from compare_invariants import digest, exact_span, nonempty, validate_facts
from evidence_core import (DEFUSED_PUNCTUATION, DEPTHS, ELEMENT_KINDS, IMPACTS,
                           LIMITATION_GUARD, REQUIRED_AUDITS, SCHEMAS,
                           SCIENCE_DEPTH_REQUIREMENT, SCIENTIFIC_RISKS, spans_overlap)

SCHEMA = SCHEMAS['impact']

# Node type -> dependent element kind. Every node type in the graph contract maps
# to exactly one element kind, so no located node silently loses its impact.
KIND_BY_NODE = {
    'Problem': 'claim', 'Motivation': 'claim', 'Research gap': 'claim',
    'Research question': 'claim', 'Hypothesis': 'claim', 'Mechanism claim': 'claim',
    'Interpretation': 'claim', 'Claim': 'claim', 'Contribution': 'claim',
    'Limitation': 'claim', 'Boundary': 'claim', 'Conclusion': 'claim',
    'Assumption': 'theory', 'Definition': 'theory', 'Theoretical proposition': 'theory',
    'Lemma': 'theory', 'Theorem': 'theory',
    'Method component': 'experiment', 'Experimental design': 'experiment',
    'Control': 'experiment', 'Baseline': 'experiment', 'Metric': 'experiment',
    'Observation': 'evidence', 'Statistical result': 'evidence', 'Prior knowledge': 'evidence',
}
assert set(KIND_BY_NODE) == set(NODE_TYPES)

# A selected repair that needs new scientific work cannot be auto-accepted, and it
# forces the edit to scientific_content regardless of the declared depth.
FORCING_REPAIRS = {'requires_reanalysis': 'needs_reanalysis',
                   'requires_new_experiment': 'needs_new_experiment',
                   'requires_new_theory': 'needs_new_theory'}

NEW_ASSERTION_WITHOUT_ORIGINAL_FACT = 'new_assertion_without_original_fact'
CLAIM_RAISED_TO_VERIFIED = 'claim_state_raised_to_verified'
INTRODUCED_PUNCTUATION = 'prose_punctuation_introduced'
SCIENTIFIC_REPAIR_NEEDS_NEW_EVIDENCE = 'scientific_repair_requires_new_evidence'
NO_GRAPH_REASON = ('no argument graph supplied: dependent claim, evidence, theory, experiment '
                   'and cross-section elements cannot be located')

EDIT_REQUIRED = {'id', 'location', 'original_span', 'replacement', 'depth', 'scientific_risk'}
EDIT_OPTIONAL = {'selected_repair_requires', 'new_reference_ids', 'loses_limitation',
                 'raises_to_verified', 'auto_acceptable'}

NOTE = ('Declared plan, not inferred judgment: a deterministic tool can locate a dependent '
        'element, but it cannot decide that two differently worded spans mean the same thing, '
        'so new_reference_ids, loses_limitation and raises_to_verified stay declarations. '
        'Impact values are literal span relations. This layer bounds the required verification '
        'and surfaces human decisions; it does not judge scientific truth.')


def _plan_edits(plan, before):
    """Validate the declared plan. The caller declares; this tool does not infer it."""
    if isinstance(plan, dict):
        unknown = set(plan) - {'schema', 'edits'}
        if unknown:
            return [], ['plan has unknown fields: ' + ', '.join(sorted(unknown))]
        if 'edits' not in plan:
            return [], ['plan must contain an edits list']
        raw = plan['edits']
    elif isinstance(plan, list):
        raw = plan
    else:
        return [], ['plan must be a list of edits or an object with an edits list']
    if not isinstance(raw, list):
        return [], ['plan edits must be a list']
    clean, errors, seen = [], [], set()
    for index, item in enumerate(raw):
        label = (item.get('id') if isinstance(item, dict) and nonempty(item.get('id'))
                 else 'plan edit #%d' % index)
        if not isinstance(item, dict):
            errors.append('invalid plan edit: ' + label)
            continue
        unknown = set(item) - EDIT_REQUIRED - EDIT_OPTIONAL
        missing = EDIT_REQUIRED - set(item)
        if unknown or missing:
            parts = []
            if missing:
                parts.append('missing fields: ' + ', '.join(sorted(missing)))
            if unknown:
                parts.append('unknown fields: ' + ', '.join(sorted(unknown)))
            errors.append(label + ': ' + '; '.join(parts))
            continue
        checks = [
            (nonempty(item['id']), 'id must be a non-empty string'),
            (item['depth'] in DEPTHS, 'invalid depth'),
            (item['scientific_risk'] in SCIENTIFIC_RISKS, 'invalid scientific_risk'),
            (isinstance(item['replacement'], str), 'replacement must be a string'),
            (exact_span(before, item['location'], item['original_span']),
             'original_span is not an exact span of the before text'),
        ]
        repair = item.get('selected_repair_requires')
        if repair is not None and repair not in REPAIRS:
            checks.append((False, 'invalid selected_repair_requires'))
        refs = item.get('new_reference_ids', [])
        if not isinstance(refs, list) or any(not nonempty(x) for x in refs):
            checks.append((False, 'new_reference_ids must be a list of non-empty strings'))
        for key in ('loses_limitation', 'raises_to_verified', 'auto_acceptable'):
            if key in item and type(item[key]) is not bool:
                checks.append((False, key + ' must be boolean'))
        bad = [message for ok, message in checks if not ok]
        if bad:
            errors.append(label + ': ' + '; '.join(bad))
            continue
        if item['id'] in seen:
            errors.append('duplicate plan edit id: ' + item['id'])
            continue
        seen.add(item['id'])
        clean.append({'id': item['id'], 'location': dict(item['location']),
                      'original_span': item['original_span'], 'replacement': item['replacement'],
                      'depth': item['depth'], 'scientific_risk': item['scientific_risk'],
                      'selected_repair_requires': repair, 'new_reference_ids': list(refs),
                      'loses_limitation': item.get('loses_limitation', False),
                      'raises_to_verified': item.get('raises_to_verified', False),
                      'declared_auto_acceptable': item.get('auto_acceptable')})
    return clean, errors


def _classify(node, original_span, replacement, manuscript):
    """Literal span relation only. Semantic equivalence is a separate audit."""
    span = node['source_span']
    if span == original_span:
        return 'changed', 'the edited span and this located element are the same text; its wording changed'
    if original_span in span:
        return 'changed', 'the edit sits inside this located element, so its wording changed'
    if span in original_span:
        if span in replacement:
            return 'unchanged', ('the element literal survives inside the replacement; this is a '
                                 'literal relation, not a semantic equivalence judgment')
        if span in manuscript:
            return 'changed', ('the element literal no longer sits at the edited location but still '
                               'appears in the revised text; equivalence is not decided here')
        return 'removed', 'the element literal is absent from the replacement and from the revised text'
    return 'changed', 'the edit overlaps this located element without containing it, so its wording changed'


def _impacts(graph, manuscript, item):
    """Locate dependent elements by overlap and record cross-section divergence."""
    location = item['location']
    touched = [n for n in graph['nodes'] if spans_overlap(n['location'], location)]
    impacts = []
    for node in touched:
        impact, rationale = _classify(node, item['original_span'], item['replacement'], manuscript)
        impacts.append({'element_id': node['id'], 'kind': KIND_BY_NODE[node['type']],
                        'impact': impact, 'rationale': rationale})
    touched_ids = {n['id'] for n in touched}
    touched_contexts = {n['context'] for n in touched}
    by_id = {n['id']: n for n in graph['nodes']}
    neighbours, seen = [], set()
    for edge in graph['edges']:
        for source, target in ((edge['source'], edge['target']), (edge['target'], edge['source'])):
            if source in touched_ids and target not in touched_ids and target not in seen:
                seen.add(target)
                neighbours.append(target)
    divergent = [nid for nid in neighbours if by_id[nid]['context'] not in touched_contexts]
    contexts = {by_id[nid]['context'] for nid in divergent}
    if len(divergent) >= 2 and len(contexts) >= 2:
        for nid in divergent:
            impacts.append({'element_id': nid, 'kind': 'cross_section', 'impact': 'changed',
                            'rationale': ('section %r depends on the edited location in section(s) %s; '
                                          'the sections can diverge after this change and cannot '
                                          'silently become inconsistent'
                                          % (by_id[nid]['context'], ', '.join(sorted(touched_contexts))))})
    return impacts


def analyze(manuscript, before, original_facts, revised_facts, plan, graph=None):
    errors, unresolved, escalations, report_edits = [], [], [], []
    original_ids = set()
    if not isinstance(original_facts, dict) or not isinstance(revised_facts, dict):
        errors.append('original and revised fact artifacts are required')
    else:
        errors.extend('original facts: ' + e for e in validate_facts(before, original_facts))
        errors.extend('revised facts: ' + e for e in validate_facts(manuscript, revised_facts))
        original_ids = {f.get('id') for f in original_facts.get('facts', []) if isinstance(f, dict)}
    graph_ok, graph_errors = False, []
    if graph is None:
        unresolved.append(NO_GRAPH_REASON)
    else:
        graph_errors = validate_graph(before, graph)
        errors.extend('graph: ' + e for e in graph_errors)
        graph_ok = not graph_errors
    plan_edits, plan_errors = _plan_edits(plan, before)
    errors.extend(plan_errors)
    if not plan_edits and not plan_errors:
        unresolved.append('plan declares no edits')
    for item in plan_edits:
        edit_id = item['id']
        issues = []
        for ref in item['new_reference_ids']:
            if ref not in original_ids:
                issues.append((NEW_ASSERTION_WITHOUT_ORIGINAL_FACT,
                               'new_reference_ids entry %r has no matching original fact id in the '
                               'original-facts artifact' % ref))
        if item['loses_limitation']:
            issues.append((LIMITATION_GUARD,
                           'the edit loses or weakens a limitation; a limited scope is not a '
                           'text-only repair'))
        if item['raises_to_verified']:
            issues.append((CLAIM_RAISED_TO_VERIFIED,
                           'the edit raises a reported or unknown claim to verified; verification '
                           'is a separate resolved act'))
        introduced = [c for c in DEFUSED_PUNCTUATION
                      if item['replacement'].count(c) > item['original_span'].count(c)]
        if introduced:
            issues.append((INTRODUCED_PUNCTUATION,
                           'the replacement introduces prose punctuation '
                           + ', '.join(repr(c) for c in introduced)
                           + '; the skill reports it and never rewrites prose'))
        repair = item['selected_repair_requires']
        if repair in FORCING_REPAIRS:
            issues.append((SCIENTIFIC_REPAIR_NEEDS_NEW_EVIDENCE,
                           'the selected repair %s needs %s, so the change cannot be auto-accepted'
                           % (repair, FORCING_REPAIRS[repair])))
        depth = item['depth']
        if repair in FORCING_REPAIRS or item['raises_to_verified']:
            depth = 'scientific_content'
        required = ([SCIENCE_DEPTH_REQUIREMENT[item['scientific_risk']]]
                    if depth == 'language_layer' else ['full_semantic_audit'])
        if repair in FORCING_REPAIRS:
            required.append(FORCING_REPAIRS[repair])
        if item['declared_auto_acceptable'] is True and issues:
            errors.append('edit %s declares auto-acceptance but impact analysis blocks it' % edit_id)
        auto = not issues
        decision = ('blocked' if issues else
                    'requires_review' if not graph_ok else 'auto_acceptable')
        for issue, detail in issues:
            escalations.append({'edit_id': edit_id, 'issue': issue, 'status': 'pending',
                                'detail': detail})
        impacts = _impacts(graph, manuscript, item) if graph_ok else []
        report_edits.append({'id': edit_id, 'location': dict(item['location']),
                             'original_span': item['original_span'],
                             'replacement': item['replacement'], 'depth': depth,
                             'impacts': impacts, 'new_reference_ids': list(item['new_reference_ids']),
                             'loses_limitation': item['loses_limitation'],
                             'introduced_punctuation': introduced,
                             'required_audits': required,
                             'scientific_risk': item['scientific_risk'],
                             'auto_acceptable': auto, 'decision': decision})
    pending = [e for e in escalations if e['status'] == 'pending']
    blocked = [e['id'] for e in report_edits if not e['auto_acceptable']]
    auto_acceptable = (not errors and not pending and not unresolved
                       and all(e['auto_acceptable'] for e in report_edits))
    if errors:
        status = 'FAIL'
    elif pending or unresolved or any(e['decision'] != 'auto_acceptable' for e in report_edits):
        status = 'NEEDS_REVIEW'
    else:
        status = 'PASS'
    return {'schema': SCHEMA, 'manuscript_digest': digest(manuscript), 'edits': report_edits,
            'escalations': escalations, 'auto_acceptable': auto_acceptable, 'blocked': blocked,
            'status': status, 'errors': errors, 'unresolved': unresolved, 'note': NOTE}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manuscript', type=Path, help='revised text')
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--original-facts', type=Path, required=True)
    parser.add_argument('--revised-facts', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--graph', type=Path)
    args = parser.parse_args()
    try:
        read = lambda path: json.loads(path.read_text(encoding='utf-8')) if path else None
        result = analyze(args.manuscript.read_text(encoding='utf-8'),
                         args.before.read_text(encoding='utf-8'),
                         read(args.original_facts), read(args.revised_facts), read(args.plan),
                         read(args.graph))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {'PASS': 0, 'FAIL': 3}.get(result.get('status'), 4)


if __name__ == '__main__':
    raise SystemExit(main())
