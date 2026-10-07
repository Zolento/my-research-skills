#!/usr/bin/env python3
"""Validate a located argument graph and separate scientific audit passes.

Topology checks are structural diagnostics. Entailment/theory/fairness verdicts
come from local semantic audits, not regex or fluent prose. Read-only CLI.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from compare_invariants import digest, exact_span, nonempty

NODE_TYPES = ('Problem', 'Motivation', 'Prior knowledge', 'Research gap', 'Research question',
              'Hypothesis', 'Assumption', 'Definition', 'Method component',
              'Theoretical proposition', 'Lemma', 'Theorem', 'Mechanism claim',
              'Experimental design', 'Control', 'Baseline', 'Metric', 'Observation',
              'Statistical result', 'Interpretation', 'Claim', 'Contribution',
              'Limitation', 'Boundary', 'Conclusion')
EDGE_TYPES = ('motivates', 'assumes', 'defines', 'derives', 'predicts', 'tests',
              'controls_for', 'compares_against', 'measures', 'supports', 'partially_supports',
              'contradicts', 'qualifies', 'generalizes', 'explains', 'depends_on')
REASONING = ('deductive', 'inductive', 'abductive', 'causal', 'statistical', 'analogical',
             'mechanistic', 'empirical generalization', 'mathematical derivation')
EDGE_VERDICTS = ('supported', 'partially_supported', 'unsupported', 'contradicted', 'underdetermined', 'unclear')
VERDICTS = ('SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNDERDETERMINED', 'UNSUPPORTED', 'CONTRADICTED')
PASSES = ('claim_evidence', 'theory', 'experiments', 'entailment', 'cross_section', 'counterfactual')
SCORECARD = ('Research question coherence', 'Claim evidence alignment', 'Theory completeness',
             'Proof reliability', 'Theory method alignment', 'Experimental identification',
             'Baseline fairness', 'Metric validity', 'Ablation informativeness',
             'Statistical support', 'Mechanism support', 'Conclusion calibration', 'Cross section consistency')
REPAIRS = ('requires_text_change_only', 'requires_reanalysis', 'requires_new_experiment', 'requires_new_theory')
SCIENCE_CATEGORIES = ('scientific_logic', 'theory', 'experimental_design', 'conclusion_validity')
THEORY_TYPES = {'Theoretical proposition', 'Lemma', 'Theorem'}
CLAIM_TYPES = {'Claim', 'Mechanism claim', 'Theoretical proposition', 'Theorem', 'Contribution', 'Conclusion'}
EVIDENCE_TYPES = {'Observation', 'Statistical result', 'Theorem', 'Lemma', 'Theoretical proposition', 'Prior knowledge'}


def validate_graph(text, graph):
    required = {'schema', 'manuscript_digest', 'document_scope', 'missing_context',
                'nodes', 'edges', 'central_claim_ids', 'main_chain'}
    if not isinstance(graph, dict) or set(graph) != required:
        return ['invalid graph fields']
    errors = []
    if graph['schema'] != 'scientific-argument-graph@1' or graph['manuscript_digest'] != digest(text):
        errors.append('stale graph provenance or schema')
    if graph['document_scope'] not in ('whole_paper', 'section', 'research_materials'):
        errors.append('invalid document scope')
    if not isinstance(graph['missing_context'], list) or any(not nonempty(x) for x in graph['missing_context']):
        errors.append('missing context must be explicit')
    if not isinstance(graph['nodes'], list) or not graph['nodes'] or not isinstance(graph['edges'], list):
        return errors + ['graph requires source-bound nodes and edges']
    ids, edge_ids = [], []
    for node in graph['nodes']:
        if not isinstance(node, dict) or set(node) != {'id', 'type', 'label', 'location', 'source_span', 'context'}:
            errors.append('invalid node fields')
            continue
        if not nonempty(node['id']) or node['type'] not in NODE_TYPES or not nonempty(node['label']) or not nonempty(node['context']):
            errors.append('invalid typed/located node')
            continue
        if not exact_span(text, node['location'], node['source_span']):
            errors.append('node location does not match source')
        ids.append(node['id'])
    if len(ids) != len(set(ids)):
        errors.append('duplicate node identity')
    nodes = {n['id']: n for n in graph['nodes'] if isinstance(n, dict) and 'id' in n}
    for edge in graph['edges']:
        if not isinstance(edge, dict) or set(edge) != {'id', 'source', 'target', 'type', 'reasoning_type', 'location', 'source_span'}:
            errors.append('invalid edge fields')
            continue
        if not nonempty(edge['id']) or edge['source'] not in nodes or edge['target'] not in nodes or edge['type'] not in EDGE_TYPES or edge['reasoning_type'] not in REASONING:
            errors.append('invalid typed edge/reference')
            continue
        if not exact_span(text, edge['location'], edge['source_span']):
            errors.append('edge source location mismatch')
        edge_ids.append(edge['id'])
    if len(edge_ids) != len(set(edge_ids)):
        errors.append('duplicate edge identity')
    for key in ('central_claim_ids', 'main_chain'):
        values = graph[key]
        if not isinstance(values, list) or any(x not in nodes for x in values) or len(values) != len(set(values)):
            errors.append('invalid ' + key)
    if not errors and any(nodes[x]['type'] not in CLAIM_TYPES for x in graph['central_claim_ids']):
        errors.append('central claim must have a claim-bearing type')
    return errors


def topology(graph):
    """Graph connectivity/cycle candidates, never inferred scientific truth."""
    nodes = {n['id']: n for n in graph['nodes']}
    predecessors, adjacency = defaultdict(set), defaultdict(set)
    findings = []
    for e in graph['edges']:
        if e['type'] in ('supports', 'partially_supports', 'derives', 'explains', 'depends_on'):
            src, dst = (e['target'], e['source']) if e['type'] == 'depends_on' else (e['source'], e['target'])
            predecessors[dst].add(src)
            adjacency[src].add(dst)

    def ancestors(nid):
        seen, todo = set(), list(predecessors[nid])
        while todo:
            item = todo.pop()
            if item in seen:
                continue
            seen.add(item)
            todo.extend(predecessors[item] - seen)
        return seen

    for cid in graph['central_claim_ids']:
        if not any(nodes[x]['type'] in EVIDENCE_TYPES for x in ancestors(cid) if x != cid):
            findings.append({'code': 'ORPHAN_CLAIM', 'node_ids': [cid], 'severity': 'major',
                             'why': 'No located evidence/theory predecessor in the extracted graph.'})
    for node in graph['nodes']:
        nid = node['id']
        if nid in ancestors(nid):
            findings.append({'code': 'CIRCULAR_ARGUMENT', 'node_ids': [nid], 'severity': 'major',
                             'why': 'A justification path returns to its own premise.'})
        if node['type'] == 'Experimental design' and not any(e['type'] == 'tests' and nid in (e['source'], e['target']) for e in graph['edges']):
            findings.append({'code': 'ORPHAN_EXPERIMENT', 'node_ids': [nid], 'severity': 'moderate',
                             'why': 'No located hypothesis/question testing relation.'})
        if node['type'] == 'Hypothesis' and not any(e['type'] == 'tests' and nid in (e['source'], e['target']) and nodes[e['target'] if e['source'] == nid else e['source']]['type'] == 'Experimental design' for e in graph['edges']):
            findings.append({'code': 'UNTESTED_HYPOTHESIS', 'node_ids': [nid], 'severity': 'major',
                             'why': 'No experiment testing this extracted hypothesis.'})
    for a, b in zip(graph['main_chain'], graph['main_chain'][1:]):
        if not any({e['source'], e['target']} == {a, b} for e in graph['edges']):
            findings.append({'code': 'MISSING_LINK', 'node_ids': [a, b], 'severity': 'major',
                             'why': 'Adjacent main-chain nodes have no located relation.'})
    for f in findings:
        f['id'] = 'D-' + f['code'] + '-' + '-'.join(f['node_ids'])
    return findings


def _audit(text, graph, report):
    errors = validate_graph(text, graph)
    if errors:
        return {'status': 'FAIL', 'errors': errors, 'findings': [], 'structural_diagnostics': []}
    structural = topology(graph)
    unknown = list(graph['missing_context'])
    if graph['document_scope'] != 'whole_paper':
        unknown.append('Limited input cannot certify whole-paper scientific coherence.')
    if report is None:
        return {'status': 'NEEDS_REVIEW', 'errors': [], 'findings': [],
                'structural_diagnostics': structural, 'unresolved': unknown + ['Separate local scientific audit passes are required.']}
    required = {'schema', 'manuscript_digest', 'graph_digest', 'passes', 'edge_checks',
                'rq_matrix', 'proof_steps', 'counterfactuals', 'scorecard', 'well_supported', 'aggregation'}
    if not isinstance(report, dict) or set(report) != required:
        return {'status': 'FAIL', 'errors': ['invalid coherence report contract'], 'findings': [], 'structural_diagnostics': structural}
    if report['schema'] != 'scientific-coherence-audit@1' or report['manuscript_digest'] != digest(text) or report['graph_digest'] != digest(graph):
        errors.append('stale scientific audit provenance')
    nodes, edges = {n['id']: n for n in graph['nodes']}, {e['id']: e for e in graph['edges']}
    theory_ids = {i for i, n in nodes.items() if n['type'] in THEORY_TYPES}
    experiment_ids = {i for i, n in nodes.items() if n['type'] == 'Experimental design'}
    all_findings, failures = [], []
    if set(report['passes']) != set(PASSES):
        errors.append('all scoped scientific passes are required')
    for name, stage in report['passes'].items():
        if name not in PASSES or set(stage) != {'status', 'examined_node_ids', 'findings'}:
            errors.append('invalid scientific pass')
            continue
        if stage['status'] not in ('COMPLETE', 'NOT_APPLICABLE', 'NOT_VERIFIED', 'NEEDS_EXTERNAL_VERIFICATION'):
            errors.append('invalid pass status')
        if stage['status'] in ('NOT_VERIFIED', 'NEEDS_EXTERNAL_VERIFICATION'):
            unknown.append(name + ' ' + stage['status'])
        if any(x not in nodes for x in stage['examined_node_ids']) or len(stage['examined_node_ids']) != len(set(stage['examined_node_ids'])):
            errors.append('invalid pass node coverage')
        expected = theory_ids if name == 'theory' else experiment_ids if name == 'experiments' else set(nodes)
        if stage['status'] == 'NOT_APPLICABLE' and (name not in ('theory', 'experiments') or expected):
            errors.append('applicable scientific pass cannot be skipped')
        if stage['status'] == 'COMPLETE' and not expected <= set(stage['examined_node_ids']):
            errors.append('incomplete scientific pass coverage ' + name)
        for finding in stage['findings']:
            fields = {'id', 'code', 'category', 'severity', 'confidence', 'evidence_node_ids',
                      'reasoning_type', 'verdict', 'why', 'alternative_interpretation',
                      'verification_needed', 'verification_status', 'basis', 'external_sources', 'repairs'}
            if not isinstance(finding, dict) or set(finding) != fields:
                errors.append('invalid scientific finding')
                continue
            if not all(nonempty(finding[k]) for k in ('id', 'code', 'why', 'alternative_interpretation', 'verification_needed')) or finding['category'] not in SCIENCE_CATEGORIES or finding['severity'] not in ('critical', 'major', 'moderate', 'minor') or finding['confidence'] not in ('high', 'medium', 'low') or finding['reasoning_type'] not in REASONING or finding['verdict'] not in VERDICTS:
                errors.append('invalid scientific finding classification')
            if not finding['evidence_node_ids'] or any(x not in nodes for x in finding['evidence_node_ids']):
                errors.append('scientific finding lacks located evidence')
            if finding['verification_status'] not in ('INTERNAL_CHECKED', 'NOT_VERIFIED', 'NEEDS_EXTERNAL_VERIFICATION') or finding['basis'] not in ('INTERNAL INCONSISTENCY', 'EXTERNAL SCIENTIFIC CONCERN'):
                errors.append('invalid epistemic status')
            if finding['basis'] == 'EXTERNAL SCIENTIFIC CONCERN' and not finding['external_sources'] and finding['verification_status'] != 'NEEDS_EXTERNAL_VERIFICATION':
                errors.append('external concern needs inspected sources or external verification')
            if any(not nonempty(s) for s in finding['external_sources']):
                errors.append('invalid external sources')
            if finding['verification_status'] != 'INTERNAL_CHECKED':
                unknown.append(finding['id'] + ' ' + finding['verification_status'])
            elif finding['verdict'] in ('UNSUPPORTED', 'CONTRADICTED') or finding['severity'] in ('critical', 'major'):
                failures.append(finding['id'])
            elif finding['verdict'] in ('UNDERDETERMINED', 'PARTIALLY_SUPPORTED'):
                unknown.append(finding['id'] + ' ' + finding['verdict'])
            if finding['code'] == 'DATA_LEAKAGE' and finding['severity'] != 'critical':
                errors.append('central-result data leakage must be Critical')
            repairs = finding['repairs']
            if any(set(r) != {'id', 'option', 'requires'} or r['requires'] not in REPAIRS or not nonempty(r['option']) for r in repairs):
                errors.append('invalid scientific repair path')
            if finding['severity'] in ('critical', 'major') and len({r['option'] for r in repairs}) < 2:
                errors.append('important scientific issue needs genuine alternative repairs')
            all_findings.append(finding)
    check_ids = []
    for check in report['edge_checks']:
        if set(check) != {'edge_id', 'reasoning_type', 'verdict', 'why'} or check['edge_id'] not in edges or check['reasoning_type'] != edges[check['edge_id']]['reasoning_type'] or check['verdict'] not in EDGE_VERDICTS or not nonempty(check['why']):
            errors.append('invalid local edge audit')
            continue
        check_ids.append(check['edge_id'])
        if check['verdict'] in ('unsupported', 'contradicted'):
            failures.append('edge ' + check['edge_id'])
        elif check['verdict'] in ('underdetermined', 'unclear', 'partially_supported'):
            unknown.append('edge ' + check['edge_id'] + ' ' + check['verdict'])
    if Counter(check_ids) != Counter(edges.keys()):
        errors.append('every inference edge needs one local audit')
    rq_ids = {i for i, n in nodes.items() if n['type'] == 'Research question'}
    rows = []
    for row in report['rq_matrix']:
        if set(row) != {'rq_id', 'hypothesis_ids', 'experiment_ids', 'result_ids', 'claim_ids', 'identifiable', 'testable', 'support_condition', 'refute_condition', 'permitted_conclusion'}:
            errors.append('invalid research question matrix')
            continue
        rows.append(row['rq_id'])
        for key, types in (('hypothesis_ids', {'Hypothesis'}), ('experiment_ids', {'Experimental design'}),
                           ('result_ids', {'Observation', 'Statistical result'}), ('claim_ids', CLAIM_TYPES)):
            if any(i not in nodes or nodes[i]['type'] not in types for i in row[key]):
                errors.append('invalid RQ chain node ' + key)
        if row['identifiable'] not in ('PASS', 'FAIL', 'UNKNOWN') or row['testable'] not in ('PASS', 'FAIL', 'UNKNOWN') or any(not nonempty(row[k]) for k in ('support_condition', 'refute_condition', 'permitted_conclusion')):
            errors.append('incomplete RQ conditions')
        if 'FAIL' in (row['identifiable'], row['testable']):
            failures.append('research question ' + row['rq_id'] + ' lacks identification/testability')
        elif 'UNKNOWN' in (row['identifiable'], row['testable']):
            unknown.append('research question ' + row['rq_id'] + ' needs verification')
        if not row['experiment_ids'] and row['hypothesis_ids']:
            unknown.append('UNTESTED_HYPOTHESIS for ' + row['rq_id'])
    if Counter(rows) != Counter(rq_ids):
        errors.append('research question matrix coverage incomplete')
    proof_ids, steps = [], set()
    for step in report['proof_steps']:
        if set(step) != {'id', 'proposition_id', 'location', 'source_span', 'dependencies', 'verdict', 'why'} or step['proposition_id'] not in theory_ids or not exact_span(text, step['location'], step['source_span']) or not nonempty(step['why']):
            errors.append('invalid proof step/source')
            continue
        if not step['dependencies'] or any(set(d) != {'kind', 'id'} or d['kind'] not in ('previous_step', 'definition', 'assumption', 'lemma', 'known_theorem', 'external_citation', 'algebraic_identity') or d['id'] not in (steps if d['kind'] == 'previous_step' else nodes) for d in step['dependencies']):
            errors.append('proof dependencies must be traced before use')
        else:
            kinds = {'definition': {'Definition'}, 'assumption': {'Assumption'}, 'lemma': {'Lemma'},
                     'known_theorem': {'Theorem', 'Prior knowledge'}, 'external_citation': {'Prior knowledge'},
                     'algebraic_identity': {'Definition', 'Prior knowledge'}}
            if any(d['kind'] != 'previous_step' and (d['id'] == step['proposition_id'] or nodes[d['id']]['type'] not in kinds[d['kind']]) for d in step['dependencies']):
                errors.append('proof dependency role mismatch or circular premise')
        if step['verdict'] == 'FAIL':
            failures.append('proof ' + step['id'])
        elif step['verdict'] == 'NOT_VERIFIED':
            unknown.append('proof ' + step['id'] + ' NOT_VERIFIED')
        elif step['verdict'] != 'VERIFIED_LOCALLY':
            errors.append('invalid proof verification status')
        if step['id'] in steps:
            errors.append('duplicate proof step')
        steps.add(step['id'])
        proof_ids.append(step['proposition_id'])
    if not theory_ids <= set(proof_ids):
        unknown.append('NOT_VERIFIED theoretical proposition without checked proof steps')
    counter_ids = []
    for counter in report['counterfactuals']:
        if set(counter) != {'claim_id', 'question', 'alternative_explanations', 'discriminating_evidence_ids', 'verdict', 'why'} or not nonempty(counter['question']) or not nonempty(counter['why']) or counter['verdict'] not in VERDICTS or any(i not in nodes for i in counter['discriminating_evidence_ids']):
            errors.append('invalid counterfactual audit')
            continue
        counter_ids.append(counter['claim_id'])
        causal = any(e['target'] == counter['claim_id'] and e['reasoning_type'] == 'causal' for e in edges.values())
        if (nodes.get(counter['claim_id'], {}).get('type') == 'Mechanism claim' or causal) and not counter['alternative_explanations']:
            errors.append('mechanistic/causal claim requires competing explanations')
        if any(not nonempty(x) for x in counter['alternative_explanations']):
            errors.append('alternative explanations must be explicit')
        if counter['verdict'] in ('UNSUPPORTED', 'CONTRADICTED'):
            failures.append('counterfactual ' + counter['claim_id'])
        elif counter['verdict'] in ('UNDERDETERMINED', 'PARTIALLY_SUPPORTED'):
            unknown.append('ALTERNATIVE_EXPLANATION_NOT_RULED_OUT for ' + counter['claim_id'])
    if Counter(counter_ids) != Counter(graph['central_claim_ids']):
        errors.append('every central claim needs counterfactual interrogation')
    finding_ids = [f['id'] for f in all_findings]
    if len(set(finding_ids)) != len(finding_ids) or Counter(report['aggregation']) != Counter(finding_ids):
        errors.append('aggregation may only rank existing findings once')
    if set(report['scorecard']) != set(SCORECARD):
        errors.append('incomplete structured scientific scorecard')
    for name, item in report['scorecard'].items():
        if set(item) != {'level', 'evidence_node_ids', 'finding_ids', 'why'} or item['level'] not in ('strong', 'adequate', 'needs attention', 'serious issue', 'not applicable') or not nonempty(item['why']) or any(x not in nodes for x in item['evidence_node_ids']) or any(x not in finding_ids for x in item['finding_ids']):
            errors.append('invalid scientific profile entry')
        elif item['level'] != 'not applicable' and not item['evidence_node_ids']:
            errors.append('scorecard judgment needs located evidence')
        elif item['level'] in ('needs attention', 'serious issue') and not item['finding_ids']:
            errors.append('scorecard concern must trace to an existing finding')
        if name in ('Theory completeness', 'Proof reliability', 'Theory method alignment') and not theory_ids and item['level'] != 'not applicable':
            errors.append('absent theory cannot be rated verified or adequate')
    for strength in report['well_supported']:
        if set(strength) != {'node_ids', 'edge_ids', 'why'} or not nonempty(strength['why']) or not strength['node_ids'] or any(x not in nodes for x in strength['node_ids']) or any(x not in edges for x in strength['edge_ids']):
            errors.append('invalid Well Supported source trace')
        elif any(c['edge_id'] in strength['edge_ids'] and c['verdict'] not in ('supported', 'partially_supported') for c in report['edge_checks']):
            errors.append('Well Supported cannot cite unsupported or unverified links')
    if structural:
        unknown.extend(f['code'] for f in structural)
    status = 'FAIL' if errors or failures else 'NEEDS_REVIEW' if unknown else 'PASS'
    return {'status': status, 'errors': errors, 'failed_links': failures, 'unresolved': unknown,
            'manuscript_digest': digest(text), 'graph_digest': digest(graph),
            'findings': sorted(all_findings, key=lambda f: report['aggregation'].index(f['id'])) if not errors else all_findings,
            'structural_diagnostics': structural, 'well_supported': report['well_supported'],
            'scorecard': report['scorecard'], 'note': 'Local semantic judgments are not formal proof verification or scientific ground truth.'}


def audit(text, graph, report=None):
    try:
        return _audit(text, graph, report)
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid scientific artifact: ' + str(exc)],
                'findings': [], 'structural_diagnostics': []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manuscript', type=Path)
    parser.add_argument('--graph', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.manuscript.read_text(encoding='utf-8'), json.loads(args.graph.read_text()),
                       json.loads(args.report.read_text()) if args.report else None)
    except (OSError, UnicodeError, ValueError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {'PASS': 0, 'FAIL': 3}.get(result['status'], 4)


if __name__ == '__main__':
    raise SystemExit(main())
