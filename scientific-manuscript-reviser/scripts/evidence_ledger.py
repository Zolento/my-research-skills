#!/usr/bin/env python3
"""Read-only gate for a claim <-> source artifact evidence ledger.

Validates `claim-evidence-ledger@1` provenance and declared states against a
manuscript and a located argument graph. It checks that every artifact reference
resolves and hashes to its declared digest, that a text artifact never carries a
verification act, that a verified claim has a verified headline record, that one
claim has at most one headline, and that contradiction outranks verification.

It performs no science, reads no model and writes nothing. A PASS means the
ledger is internally consistent and fully sourced. It does not mean any claim is
true. Exit 0 PASS, 3 FAIL, 4 NEEDS_REVIEW/INVALID.
"""
import argparse
import json
from pathlib import Path

import audit_coherence
from evidence_core import (ARTIFACT_TYPES, EVIDENCE_STATES, SCHEMAS, TEXT_TYPES,
                           VERIFICATION_METHODS, claim_state, evidence_state_rule,
                           exact_span, nonempty, source_digest)

ROOT = Path(__file__).resolve().parents[1]

LEDGER_FIELDS = {'schema', 'claims', 'artifacts', 'evidence', 'missing_context'}
CLAIM_FIELDS = {'id', 'statement', 'location', 'source_span', 'presented_as_established'}
ARTIFACT_FIELDS = {'id', 'type', 'reference', 'digest', 'origin', 'locator'}
EVIDENCE_FIELDS = {'id', 'claim_id', 'artifact_id', 'locator', 'statement', 'state',
                   'verification_method', 'headline', 'scope'}
EVIDENCE_OPTIONAL = {'conditions', 'note'}
NOTE = ('This layer validates provenance and declared states only. It is not scientific '
        'validation and does not certify any claim as true.')


def _read_graph(graph):
    """Minimal structural read: the ledger needs node identity, type and central claims."""
    if not isinstance(graph, dict):
        return None, ['invalid graph artifact: expected an object']
    nodes = graph.get('nodes')
    if not isinstance(nodes, list) or any(not isinstance(n, dict) or 'id' not in n or 'type' not in n
                                          for n in nodes):
        return None, ['invalid graph artifact: nodes must be typed objects with an id']
    central = graph.get('central_claim_ids', [])
    if not isinstance(central, list) or any(not nonempty(x) for x in central):
        return None, ['invalid graph artifact: central_claim_ids must be explicit ids']
    return {n['id']: n for n in nodes}, []


def _check_artifact(record, root, errors):
    if not isinstance(record, dict) or set(record) != ARTIFACT_FIELDS:
        errors.append('invalid artifact fields')
        return None
    aid = record['id']
    if not nonempty(aid):
        errors.append('invalid artifact identity')
        return None
    if record['type'] not in ARTIFACT_TYPES:
        errors.append('invalid artifact type for ' + aid)
    if not nonempty(record['origin']) or not nonempty(record['locator']):
        errors.append('artifact ' + aid + ' needs a declared origin and locator')
    if not nonempty(record['reference']):
        errors.append('artifact ' + aid + ' needs a reference path')
        return record
    path = (root / record['reference']).resolve()
    if not path.is_relative_to(root):
        errors.append('artifact ' + aid + ' reference escapes the skill directory')
    elif not path.is_file():
        errors.append('artifact ' + aid + ' reference does not resolve to a file: ' + record['reference'])
    elif record['digest'] != source_digest(path):
        errors.append('artifact ' + aid + ' digest does not match the referenced file')
    return record


def _check_claim(record, text, nodes, errors):
    if not isinstance(record, dict) or set(record) != CLAIM_FIELDS:
        errors.append('invalid claim fields')
        return None
    cid = record['id']
    if not nonempty(cid) or not nonempty(record['statement']):
        errors.append('invalid claim identity or statement')
        return None
    if type(record['presented_as_established']) is not bool:
        errors.append('claim ' + cid + ' must declare presented_as_established explicitly')
        return None
    node = nodes.get(cid)
    if node is None or node.get('type') not in audit_coherence.CLAIM_TYPES:
        errors.append('claim ' + cid + ' is not a claim-bearing node in graph.json')
        return None
    if not exact_span(text, record['location'], record['source_span']):
        errors.append('claim ' + cid + ' location does not match the manuscript')
    return record


def _check_evidence(record, artifacts, claims, nodes, errors):
    if (not isinstance(record, dict) or not EVIDENCE_FIELDS <= set(record)
            or not set(record) <= EVIDENCE_FIELDS | EVIDENCE_OPTIONAL):
        errors.append('invalid evidence fields')
        return None
    eid = record['id']
    if not nonempty(eid):
        errors.append('invalid evidence identity')
        return None
    cid = record['claim_id']
    if not isinstance(cid, str) or cid not in nodes or nodes[cid].get('type') not in audit_coherence.CLAIM_TYPES:
        errors.append('evidence ' + eid + ' references an unknown claim node: ' + str(cid))
    elif cid not in claims:
        errors.append('evidence ' + eid + ' references an undeclared claim: ' + cid)
    aid = record['artifact_id']
    if not isinstance(aid, str) or aid not in artifacts:
        errors.append('evidence ' + eid + ' references an unknown artifact: ' + str(aid))
        artifact_type = None
    else:
        artifact_type = artifacts[aid]['type']
    if not nonempty(record['locator']) or not nonempty(record['statement']) or not nonempty(record['scope']):
        errors.append('evidence ' + eid + ' needs a locator, statement and scope')
    state, method = record['state'], record['verification_method']
    if state not in EVIDENCE_STATES:
        errors.append('invalid evidence state for ' + eid)
    if method not in VERIFICATION_METHODS:
        errors.append('invalid verification method for ' + eid)
    if type(record['headline']) is not bool:
        errors.append('evidence ' + eid + ' must declare headline explicitly')
    if 'conditions' in record and (not isinstance(record['conditions'], list)
                                   or any(not nonempty(x) for x in record['conditions'])):
        errors.append('evidence ' + eid + ' conditions must be explicit strings')
    if 'note' in record and not nonempty(record['note']):
        errors.append('evidence ' + eid + ' note must be a nonempty string')
    if artifact_type is not None:
        violation = evidence_state_rule(artifact_type, method, state)
        if violation:
            errors.append('evidence ' + eid + ' (' + str(aid) + '): ' + violation)
    return record


def _aggregate(declared, claims, records, errors):
    claim_states, no_evidence, unknown, contradicted, reported_established = {}, [], [], [], []
    escalations, unresolved = [], []
    for cid in declared:
        state = claim_state(records, cid)
        claim_states[cid] = state
        heads = [r for r in records if r.get('claim_id') == cid and r.get('headline') is True]
        if len(heads) > 1:
            errors.append('claim ' + cid + ' has more than one headline record')
        if state == 'verified' and not any(h.get('state') == 'verified' for h in heads):
            errors.append('claim ' + cid + ' aggregates to verified without a verified headline record')
        if state == 'no_evidence':
            no_evidence.append(cid)
            unresolved.append('claim ' + cid + ' has NO_EVIDENCE: no record was supplied; '
                              'this is missing evidence, not unresolved science')
        elif state == 'unknown':
            unknown.append(cid)
            unresolved.append('claim ' + cid + ' is UNKNOWN: evidence exists but was not resolved')
        elif state == 'contradicted':
            contradicted.append(cid)
            unresolved.append('claim ' + cid + ' is CONTRADICTED: located evidence goes against it')
            if any(h.get('state') == 'verified' for h in heads):
                escalations.append('CONTRADICTION_OVERRIDES_VERIFICATION for ' + cid
                                   + ': a verified headline exists but contradiction outranks it; '
                                   'the claim must not be presented as verified')
        elif state == 'reported' and claims[cid]['presented_as_established']:
            reported_established.append(cid)
            unresolved.append('claim ' + cid + ' is only REPORTED but the manuscript presents it as established')
    return claim_states, no_evidence, unknown, contradicted, reported_established, escalations, unresolved


def _ledger(text, artifact, graph, root):
    if not isinstance(artifact, dict) or set(artifact) != LEDGER_FIELDS:
        return {'status': 'FAIL', 'errors': ['invalid ledger fields'], 'note': NOTE}
    errors = []
    if artifact['schema'] != SCHEMAS['ledger']:
        errors.append('invalid ledger schema')
    nodes, graph_errors = _read_graph(graph)
    errors.extend(graph_errors)
    if nodes is None:
        return {'status': 'FAIL', 'errors': errors, 'note': NOTE}
    for key in ('claims', 'artifacts', 'evidence', 'missing_context'):
        if not isinstance(artifact[key], list):
            errors.append('invalid ledger field: ' + key + ' must be a list')
    if errors:
        return {'status': 'FAIL', 'errors': errors, 'note': NOTE}
    root = Path(root).resolve()

    artifacts, claims, declared = {}, {}, []
    for record in artifact['artifacts']:
        checked = _check_artifact(record, root, errors)
        if checked is None:
            continue
        aid = checked['id']
        if aid in artifacts:
            errors.append('duplicate artifact identity: ' + aid)
            continue
        artifacts[aid] = checked
    for record in artifact['claims']:
        checked = _check_claim(record, text, nodes, errors)
        if checked is None:
            continue
        cid = checked['id']
        if cid in claims:
            errors.append('duplicate claim identity: ' + cid)
            continue
        claims[cid] = checked
        declared.append(cid)
    records, seen = [], []
    for record in artifact['evidence']:
        checked = _check_evidence(record, artifacts, claims, nodes, errors)
        if checked is None:
            continue
        eid = checked['id']
        if eid in seen:
            errors.append('duplicate evidence identity: ' + eid)
            continue
        seen.append(eid)
        records.append(checked)

    claim_states, no_evidence, unknown, contradicted, reported_established, escalations, unresolved = (
        _aggregate(declared, claims, records, errors))

    missing_context = artifact['missing_context']
    if any(not nonempty(x) for x in missing_context):
        errors.append('missing_context must be explicit strings')
    unresolved.extend('missing_context: ' + x for x in missing_context if nonempty(x))
    gaps = [cid for cid in dict.fromkeys(graph['central_claim_ids']) if cid not in claims]
    if gaps:
        unresolved.append('incomplete coverage: graph central claims not declared in the ledger: '
                          + ', '.join(gaps))

    status = 'FAIL' if errors else 'NEEDS_REVIEW' if unresolved else 'PASS'
    return {'status': status, 'errors': errors, 'claim_states': claim_states,
            'no_evidence_claims': no_evidence, 'unknown_claims': unknown,
            'contradicted_claims': contradicted, 'reported_but_established': reported_established,
            'coverage_gaps': gaps, 'escalations': escalations, 'unresolved': unresolved,
            'missing_context': missing_context, 'note': NOTE}


def ledger(text, ledger_artifact, graph, root=None):
    try:
        return _ledger(text, ledger_artifact, graph, ROOT if root is None else root)
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid ledger artifact: ' + str(exc)], 'note': NOTE}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manuscript', type=Path)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--graph', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=ROOT,
                        help='base directory that artifact references resolve against')
    args = parser.parse_args()
    try:
        result = ledger(args.manuscript.read_text(encoding='utf-8'),
                        json.loads(args.ledger.read_text(encoding='utf-8')),
                        json.loads(args.graph.read_text(encoding='utf-8')),
                        args.root)
    except (OSError, UnicodeError, ValueError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {'PASS': 0, 'FAIL': 3}.get(result['status'], 4)


if __name__ == '__main__':
    raise SystemExit(main())
