#!/usr/bin/env python3
"""Research-material and blueprint gates sharing the scientific audit standards.

The agent generates argument/outline content. These helpers never invent results,
judge a proof through regex, or draft without explicit blueprint approval.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

import audit_coherence as ac
import compare_invariants as ci
import validate_style as style

MATERIAL_TYPES = ('established_fact', 'experimental_result', 'theoretical_result', 'hypothesis',
                  'interpretation', 'planned_experiment', 'planned_analysis', 'unsupported_idea',
                  'literature_evidence', 'known_limitation', 'unknown')
ESTABLISHED = {'established_fact', 'experimental_result', 'theoretical_result', 'literature_evidence', 'known_limitation'}
SUPPORT = {'UNSUPPORTED': 0, 'PLANNED': 1, 'PARTIALLY_SUPPORTED': 2, 'SUPPORTED': 3}
ROLE_TYPES = ('context', 'problem', 'tension', 'gap', 'research_question', 'hypothesis', 'contribution',
              'method_motivation', 'method_definition', 'theory_setup', 'proof_intuition',
              'experimental_question', 'protocol', 'result', 'interpretation', 'mechanism',
              'comparison', 'robustness', 'failure_analysis', 'limitation', 'discussion',
              'takeaway', 'transition')
OUTLINE_CHECKS = ('central_thesis_visible', 'sections_serve_thesis', 'central_claim_evidence',
                  'experiment_purpose', 'theory_experiment_connection', 'conclusion_entailment',
                  'no_unsupported_leap', 'no_duplicated_role', 'contribution_visible', 'boundary_proportionate')


def corpus(material):
    return '\n\n'.join(s['text'] for s in material['sources'])


def normalize(sources):
    """Unclassified input starts unknown, never established by a heuristic."""
    material = {'schema': 'research-material-map@1', 'sources': sources, 'items': [], 'missing_context': []}
    for source in sources:
        for match in re.finditer(r'\S[^\n]*(?:\n(?!\s*\n)[^\n]*)*', source['text']):
            material['items'].append({'id': source['id'] + '-I' + str(len(material['items']) + 1),
                                      'type': 'unknown', 'statement': match[0], 'source_id': source['id'],
                                      'location': {'start': match.start(), 'end': match.end()}, 'source_span': match[0]})
    return material


def validate_material(material):
    errors = []
    if not isinstance(material, dict) or set(material) != {'schema', 'sources', 'items', 'missing_context'} or material['schema'] != 'research-material-map@1':
        return ['invalid material map']
    sources = {}
    for source in material['sources']:
        if set(source) != {'id', 'text'} or not ci.nonempty(source['id']) or not ci.nonempty(source['text']) or source['id'] in sources:
            errors.append('invalid or duplicate material source')
        else:
            sources[source['id']] = source['text']
    ids = []
    if not sources:
        errors.append('material needs at least one actual source')
    for item in material['items']:
        if set(item) != {'id', 'type', 'statement', 'source_id', 'location', 'source_span'} or not ci.nonempty(item['id']) or item['type'] not in MATERIAL_TYPES or not ci.nonempty(item['statement']) or item['source_id'] not in sources or not ci.exact_span(sources[item['source_id']], item['location'], item['source_span']):
            errors.append('material item must retain epistemic type and exact source')
        else:
            ids.append(item['id'])
    if len(ids) != len(set(ids)) or any(not ci.nonempty(x) for x in material['missing_context']):
        errors.append('duplicate item or invalid missing-context description')
    return errors


def _blueprint(material, graph, report, blueprint, outline_audit):
    errors, unresolved = validate_material(material), []
    if errors:
        return {'status': 'FAIL', 'errors': errors, 'draft_ready': False}
    text = corpus(material)
    coherence = ac.audit(text, graph, report)
    required = {'schema', 'material_digest', 'graph_digest', 'coherence_digest', 'depth', 'claims',
                'sufficiency', 'theses', 'selected_thesis_id', 'architectures', 'recommended_architecture_id',
                'sections', 'gaps', 'experiment_portfolio', 'literature_roles', 'outline_options'}
    if not isinstance(blueprint, dict) or set(blueprint) != required:
        return {'status': 'FAIL', 'errors': ['invalid blueprint fields'], 'draft_ready': False}
    if blueprint['schema'] != 'manuscript-blueprint@1' or blueprint['material_digest'] != ci.digest(material) or blueprint['graph_digest'] != ci.digest(graph) or blueprint['coherence_digest'] != ci.digest(coherence) or blueprint['depth'] not in ('compact', 'full'):
        errors.append('invalid blueprint provenance or depth')
    if coherence['errors']:
        errors.extend(coherence['errors'])
    items = {i['id']: i for i in material['items']}
    established = {i for i, x in items.items() if x['type'] in ESTABLISHED}
    claims = {}
    for claim in blueprint['claims']:
        fields = {'id', 'claim', 'claim_type', 'importance', 'evidence', 'support_status',
                  'assumptions', 'scope', 'risk_of_overclaim', 'used_in_sections'}
        if set(claim) != fields or not ci.nonempty(claim['id']) or claim['id'] in claims or not all(ci.nonempty(claim[k]) for k in ('claim', 'claim_type', 'scope')) or claim['support_status'] not in SUPPORT or claim['importance'] not in ('central', 'major', 'supporting', 'boundary') or claim['risk_of_overclaim'] not in ('low', 'medium', 'high'):
            errors.append('invalid claim hierarchy')
            continue
        if any(x not in items for x in claim['evidence'] + claim['assumptions']):
            errors.append('claim has nonexistent evidence/assumptions')
        graph_nodes = {n['id']: n for n in graph['nodes']}
        if claim['id'] not in graph_nodes or claim['claim'] != graph_nodes[claim['id']]['label']:
            errors.append('blueprint claim must preserve its audited argument-node identity and statement')
        if claim['support_status'] in ('SUPPORTED', 'PARTIALLY_SUPPORTED') and (not claim['evidence'] or not set(claim['evidence']) <= established):
            errors.append('planned/hypothesized/interpretive evidence cannot establish a claim')
        claims[claim['id']] = claim
    if not claims:
        errors.append('bounded blueprint needs an explicit claim or research-target hierarchy')
    sufficiency = blueprint['sufficiency']
    fields = {'supported_claim_ids', 'partially_supported_claim_ids', 'unsupported_desired_claim_ids',
              'missing_evidence', 'missing_theory', 'missing_experiments', 'missing_literature_grounding'}
    if set(sufficiency) != fields:
        errors.append('incomplete material sufficiency report')
    else:
        for key, statuses in (('supported_claim_ids', {'SUPPORTED'}),
                              ('partially_supported_claim_ids', {'PARTIALLY_SUPPORTED'}),
                              ('unsupported_desired_claim_ids', {'UNSUPPORTED', 'PLANNED'})):
            if Counter(sufficiency[key]) != Counter(i for i, c in claims.items() if c['support_status'] in statuses):
                errors.append('sufficiency misrepresents claim support')
        for key in fields - {'supported_claim_ids', 'partially_supported_claim_ids', 'unsupported_desired_claim_ids'}:
            if any(not ci.nonempty(x) for x in sufficiency[key]):
                errors.append('missing research work must be explicit')
    theses = {}
    anchors = []
    for thesis in blueprint['theses']:
        fields = {'id', 'text', 'central_claim_id', 'support_level', 'main_evidence', 'novelty_delta',
                  'novelty_evidence', 'strength', 'risk', 'best_fit_venue'}
        if set(thesis) != fields or thesis['id'] in theses or thesis['central_claim_id'] not in claims or not all(ci.nonempty(thesis[k]) for k in ('text', 'novelty_delta', 'strength', 'risk', 'best_fit_venue')):
            errors.append('invalid paper thesis')
            continue
        c = claims[thesis['central_claim_id']]
        if thesis['support_level'] != c['support_status'] or not set(thesis['main_evidence']) <= set(c['evidence']) or not thesis['main_evidence'] and thesis['support_level'] in ('SUPPORTED', 'PARTIALLY_SUPPORTED'):
            errors.append('thesis support/evidence differs from its frozen claim')
        if any(x not in items or items[x]['type'] != 'literature_evidence' for x in thesis['novelty_evidence']):
            errors.append('novelty must trace to inspected literature')
        if not thesis['novelty_evidence'] and thesis['novelty_delta'].strip().lower() not in ('unknown', 'not established'):
            errors.append('unsupported novelty delta')
        if style.validate(thesis['text'])['status'] != 'PASS':
            errors.append('thesis prose must pass hard style rules')
        anchors.append(thesis['central_claim_id'])
        theses[thesis['id']] = thesis
    if not 1 <= len(theses) <= 4 or len(anchors) != len(set(anchors)):
        errors.append('theses need distinct scientific anchors, not rhetorical duplicates')
    selected = theses.get(blueprint['selected_thesis_id'])
    if selected is None or SUPPORT[selected['support_level']] < max((SUPPORT[t['support_level']] for t in theses.values()), default=0):
        errors.append('recommendation must prefer strongest available scientific support')
    architectures, orders = {}, set()
    for architecture in blueprint['architectures']:
        fields = {'id', 'central_tension', 'opening_anchor', 'claim_order', 'strongest_advantage',
                  'main_risk', 'required_evidence', 'recommended_when'}
        if set(architecture) != fields or architecture['id'] in architectures or any(x not in claims for x in architecture['claim_order']) or any(x not in items for x in architecture['required_evidence']) or not architecture['claim_order'] or any(not ci.nonempty(architecture[k]) for k in ('central_tension', 'opening_anchor', 'strongest_advantage', 'main_risk', 'recommended_when')):
            errors.append('invalid narrative architecture')
            continue
        signature = (architecture['opening_anchor'], tuple(architecture['claim_order']))
        if signature in orders:
            errors.append('architecture alternatives are duplicates')
        orders.add(signature)
        architectures[architecture['id']] = architecture
    if not 1 <= len(architectures) <= 4 or blueprint['recommended_architecture_id'] not in architectures:
        errors.append('missing architecture recommendation')
    paragraphs, sections, subsections = {}, {}, set()
    material_numbers = set(ci.NUMBER.findall(text))
    for section in blueprint['sections']:
        if set(section) != {'id', 'title', 'purpose', 'claim_ids', 'subsections'} or section['id'] in sections or not ci.nonempty(section['title']) or not ci.nonempty(section['purpose']) or not section['subsections'] or any(x not in claims for x in section['claim_ids']):
            errors.append('major section needs a scientific purpose and claims')
            continue
        sections[section['id']] = section
        for subsection in section['subsections']:
            fields = {'id', 'title', 'purpose', 'claim_ids', 'evidence_ids', 'key_transition', 'paragraphs', 'experiment_contract'}
            if set(subsection) != fields or subsection['id'] in subsections or not all(ci.nonempty(subsection[k]) for k in ('title', 'purpose', 'key_transition')) or not subsection['paragraphs'] or not subsection['claim_ids'] or any(x not in claims for x in subsection['claim_ids']) or any(x not in items for x in subsection['evidence_ids']):
                errors.append('orphan/invalid subsection')
                continue
            subsections.add(subsection['id'])
            if subsection['experiment_contract'] is not None:
                contract = subsection['experiment_contract']
                fields = {'scientific_question', 'hypothesis', 'comparison', 'control', 'metric',
                          'expected_interpretation', 'actual_result', 'allowed_conclusion', 'forbidden_overinterpretation'}
                if set(contract) != fields or any(not ci.nonempty(x) for x in contract.values()):
                    errors.append('experimental subsection needs question/design/result/calibration contract')
            for p in subsection['paragraphs']:
                fields = {'id', 'role', 'purpose', 'claim_ids', 'evidence_ids', 'logical_predecessor', 'logical_successor',
                          'content_to_include', 'content_to_avoid', 'reference_candidates', 'paragraph_sketch',
                          'writing_instruction', 'gap_marker', 'finding_ids'}
                if set(p) != fields or p['id'] in paragraphs or p['role'] not in ROLE_TYPES or not all(ci.nonempty(p[k]) for k in ('purpose', 'paragraph_sketch', 'writing_instruction')) or any(x not in claims for x in p['claim_ids']) or any(x not in items for x in p['evidence_ids'] + p['reference_candidates']) or p['gap_marker'] not in ('', 'SCIENTIFIC GAP TO RESOLVE'):
                    errors.append('invalid paragraph scientific role/contract')
                    continue
                if not p['claim_ids']:
                    errors.append('paragraph is disconnected from the argument hierarchy')
                if style.validate(p['paragraph_sketch'])['status'] != 'PASS':
                    errors.append('paragraph sketch violates hard style rules or has unresolved technical spans')
                if not set(ci.NUMBER.findall(p['paragraph_sketch'])) <= material_numbers:
                    errors.append('paragraph sketch invents numeric evidence')
                unsupported = any(claims[c]['support_status'] in ('PLANNED', 'UNSUPPORTED') for c in p['claim_ids'])
                if unsupported and not p['gap_marker'] and p['role'] not in ('hypothesis', 'research_question', 'gap', 'protocol', 'experimental_question'):
                    errors.append('planned/unsupported claim presented as an established result/contribution')
                if p['role'] in ('result', 'contribution', 'mechanism', 'robustness', 'takeaway') and not p['gap_marker'] and not set(p['evidence_ids']) <= established:
                    errors.append('paragraph upgrades planned evidence')
                paragraphs[p['id']] = p
    if not sections or not paragraphs:
        errors.append('blueprint requires a bounded section/subsection/paragraph plan')
    for c in claims.values():
        if not c['used_in_sections'] or any(x not in sections for x in c['used_in_sections']):
            errors.append('claim section placement missing')
    for p in paragraphs.values():
        if any(x not in paragraphs or x == p['id'] for x in p['logical_predecessor'] + p['logical_successor']):
            errors.append('paragraph logic reference missing or circular')
    findings = {f['id']: f for f in coherence.get('findings', [])}
    gap_ids = []
    for gap in blueprint['gaps']:
        if set(gap) != {'finding_id', 'paragraph_ids', 'requires'} or gap['finding_id'] not in findings or gap['requires'] not in ac.REPAIRS or not gap['paragraph_ids'] or any(x not in paragraphs or paragraphs[x]['gap_marker'] != 'SCIENTIFIC GAP TO RESOLVE' or gap['finding_id'] not in paragraphs[x]['finding_ids'] for x in gap['paragraph_ids']):
            errors.append('scientific gap must remain visible at its blueprint location')
        gap_ids.append(gap['finding_id'])
    if not {i for i, f in findings.items() if f['severity'] in ('critical', 'major')} <= set(gap_ids):
        errors.append('critical/major scientific issue hidden in the outline')
    for p in paragraphs.values():
        if any(i not in findings for i in p['finding_ids']):
            errors.append('paragraph refers to invented scientific criticism')
    for entry in blueprint['experiment_portfolio']:
        if set(entry) != {'material_id', 'necessity', 'claim_ids', 'logic_gap'} or entry['material_id'] not in items or items[entry['material_id']]['type'] not in ('experimental_result', 'planned_experiment', 'planned_analysis') or entry['necessity'] not in ('required', 'strongly_recommended', 'optional', 'redundant', 'orphan') or any(x not in claims for x in entry['claim_ids']):
            errors.append('invalid experiment portfolio')
        elif items[entry['material_id']]['type'] in ('planned_experiment', 'planned_analysis') and not ci.nonempty(entry['logic_gap']):
            errors.append('proposed experiment must resolve an explicit logic gap')
    for entry in blueprint['literature_roles']:
        if set(entry) != {'material_id', 'role', 'claim_ids'} or entry['material_id'] not in items or items[entry['material_id']]['type'] != 'literature_evidence' or entry['role'] not in ('problem_importance', 'closest_prior_method', 'theoretical_foundation', 'competing_explanation', 'baseline_justification') or not entry['claim_ids'] or any(x not in claims for x in entry['claim_ids']):
            errors.append('invalid literature role/source')
    for option in blueprint['outline_options']:
        if set(option) != {'area', 'option', 'advantage', 'risk', 'best_when'} or any(not ci.nonempty(x) for x in option.values()):
            errors.append('outline option needs an actual editorial tradeoff')
    if outline_audit is None:
        unresolved.append('independent outline and alignment audit required')
    else:
        fields = {'schema', 'blueprint_digest', 'material_digest', 'paragraph_checks', 'outline_checks', 'alignment_checks'}
        if set(outline_audit) != fields or outline_audit['schema'] != 'blueprint-audit@1' or outline_audit['blueprint_digest'] != ci.digest(blueprint) or outline_audit['material_digest'] != ci.digest(material):
            errors.append('stale/invalid blueprint audit')
        else:
            def verdict(check):
                if not ci.nonempty(check['rationale']) or check['status'] not in ('PASS', 'FAIL', 'UNKNOWN'):
                    errors.append('invalid independent outline judgment')
                elif check['status'] == 'FAIL':
                    errors.append(check['rationale'])
                elif check['status'] == 'UNKNOWN':
                    unresolved.append(check['rationale'])
            checked = []
            for check in outline_audit['paragraph_checks']:
                if set(check) != {'paragraph_id', 'status', 'rationale'}:
                    errors.append('invalid paragraph audit')
                else:
                    checked.append(check['paragraph_id'])
                    verdict(check)
            if Counter(checked) != Counter(paragraphs.keys()):
                errors.append('each paragraph sketch needs semantic audit')
            if set(outline_audit['outline_checks']) != set(OUTLINE_CHECKS):
                errors.append('incomplete outline quality checks')
            for check in outline_audit['outline_checks'].values():
                if set(check) != {'status', 'rationale'}:
                    errors.append('invalid outline check')
                else:
                    verdict(check)
            theory_claims = {i for i, c in claims.items() if c['claim_type'] == 'theoretical'}
            aligned = []
            for check in outline_audit['alignment_checks']:
                if set(check) != {'claim_id', 'status', 'rationale'}:
                    errors.append('invalid theory experiment alignment')
                else:
                    aligned.append(check['claim_id'])
                    verdict(check)
            if Counter(aligned) != Counter(theory_claims):
                errors.append('every theoretical claim needs method/experiment alignment')
    scientific_gaps = coherence['status'] != 'PASS' or material['missing_context']
    if scientific_gaps:
        unresolved.append('Scientific context or verified gaps remain. This is a bounded plan, not an accepted scientific argument.')
    return {'status': 'FAIL' if errors else 'NEEDS_REVIEW' if unresolved else 'PASS', 'errors': errors,
            'unresolved': unresolved, 'scientific_status': coherence['status'],
            'bounded_outline': not errors, 'draft_ready': not errors and not unresolved,
            'coherence': coherence, 'paragraph_count': len(paragraphs)}


def validate_blueprint(material, graph, report, blueprint, outline_audit=None):
    try:
        return _blueprint(material, graph, report, blueprint, outline_audit)
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid blueprint artifact: ' + str(exc)], 'draft_ready': False}


def validate_section_draft(blueprint, approval, section_id, draft, contract, *, material=None, graph=None, report=None, outline_audit=None):
    """Approved section sketches are the fixed expression baseline, not new evidence."""
    try:
        gate = validate_blueprint(material, graph, report, blueprint, outline_audit)
        if not gate.get('draft_ready'):
            raise ValueError('the same scientific and outline gates must pass before drafting')
        if set(approval) != {'blueprint_digest', 'approved', 'section_ids'} or approval['approved'] is not True or approval['blueprint_digest'] != ci.digest(blueprint) or section_id not in approval['section_ids']:
            raise ValueError('explicit blueprint approval for this section is required')
        fields = {'blueprint_digest', 'section_id', 'claim_order', 'evidence_ids', 'original_facts', 'revised_facts', 'semantic_audit'}
        if set(contract) != fields or contract['blueprint_digest'] != ci.digest(blueprint) or contract['section_id'] != section_id:
            raise ValueError('stale section contract')
        section = next(s for s in blueprint['sections'] if s['id'] == section_id)
        paragraphs = [p for sub in section['subsections'] for p in sub['paragraphs']]
        if any(p['gap_marker'] or p['finding_ids'] for p in paragraphs):
            raise ValueError('unresolved scientific gaps cannot become a completed section')
        if contract['claim_order'] != list(dict.fromkeys(c for p in paragraphs for c in p['claim_ids'])) or Counter(contract['evidence_ids']) != Counter(set(e for p in paragraphs for e in p['evidence_ids'])):
            raise ValueError('draft claim hierarchy or evidence differs from approved blueprint')
        before = '\n\n'.join(p['paragraph_sketch'] for p in paragraphs)
        invariance = ci.compare(before, draft, contract['original_facts'], contract['revised_facts'], contract['semantic_audit'])
        style_result = style.validate(draft)
        status = 'FAIL' if 'FAIL' in (invariance['status'], style_result['status']) else 'NEEDS_REVIEW' if 'NEEDS_REVIEW' in (invariance['status'], style_result['status']) else 'PASS'
        return {'status': status, 'invariance': invariance, 'style': style_result, 'section_id': section_id}
    except (TypeError, ValueError, KeyError, StopIteration) as exc:
        return {'status': 'FAIL', 'errors': [str(exc)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('normalize')
    p.add_argument('--sources', type=Path, required=True)
    p = sub.add_parser('check')
    for name in ('material', 'graph', 'report', 'blueprint'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--audit', type=Path)
    args = parser.parse_args()
    try:
        read = lambda p: json.loads(p.read_text(encoding='utf-8')) if p else None
        result = normalize(read(args.sources)) if args.command == 'normalize' else validate_blueprint(read(args.material), read(args.graph), read(args.report), read(args.blueprint), read(args.audit))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 3 if result.get('status') == 'FAIL' else 4 if result.get('status') in ('NEEDS_REVIEW', 'INVALID') else 0


if __name__ == '__main__':
    raise SystemExit(main())
