#!/usr/bin/env python3
"""Mechanical preservation plus source-bound, separately supplied semantic audit.

Never extracts scientific meaning with regex. Without semantic artifacts, a clean
mechanical comparison is NEEDS_REVIEW. Exit 0 PASS, 3 FAIL, 4 review/input error.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from validate_style import COMMAND, REF, balanced_end, scan

CATEGORIES = ('claims', 'numbers', 'metrics', 'datasets', 'methods', 'baselines',
              'comparators', 'statistical_statements', 'causal_status', 'novelty',
              'scope', 'assumptions', 'limitations', 'uncertainty', 'figure_references',
              'table_references', 'section_references', 'citation_keys',
              'equation_references', 'technical_terminology')
GLOBAL_CHECKS = ('claim_strength', 'claim_evidence_alignment', 'citation_meaning',
                 'reference_claim_alignment', 'technical_meaning', 'scope_and_boundary',
                 'no_new_scientific_content', 'no_unsupported_weakening')
NUMBER = re.compile(r'(?<![\w])[-+−]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?(?!\w)')
CITATION = re.compile(r'\\(?:cite(?:p|t|author|year)?|parencite|textcite)\*?(?:\[[^\]]*\])*\{([^{}]*)\}|\[@([^\]]+)\]')
LABEL_REF = re.compile(r'\\(?:ref|eqref|autoref|cref|Cref|label)\{([^{}]+)\}')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def exact_span(text, loc, span):
    if not isinstance(loc, dict) or set(loc) != {'start', 'end'}:
        return False
    start, end = loc['start'], loc['end']
    return (type(start) is int and type(end) is int and 0 <= start < end <= len(text)
            and isinstance(span, str) and text[start:end] == span)


def validate_facts(text, artifact):
    """Validate extraction provenance and explicit category coverage, not truth."""
    errors = []
    required = {'schema', 'manuscript_digest', 'covered_categories', 'absent_categories', 'facts', 'unresolved'}
    if not isinstance(artifact, dict) or set(artifact) != required:
        return ['invalid extraction contract']
    if artifact['schema'] != 'manuscript-invariants@1' or artifact['manuscript_digest'] != digest(text):
        errors.append('extraction belongs to a different text or schema')
    covered = artifact['covered_categories']
    absent = artifact['absent_categories']
    if not isinstance(covered, list) or Counter(covered) != Counter(CATEGORIES):
        errors.append('extraction must explicitly inspect all protected categories')
    if not isinstance(absent, list) or any(x not in CATEGORIES for x in absent) or len(absent) != len(set(absent)):
        errors.append('invalid absent categories')
    if not isinstance(artifact['unresolved'], list) or any(not nonempty(x) for x in artifact['unresolved']):
        errors.append('unresolved questions must be explicit strings')
    facts = artifact['facts']
    if not isinstance(facts, list):
        return errors + ['facts must be a list']
    ids, categories = [], set()
    for fact in facts:
        if not isinstance(fact, dict) or set(fact) != {'id', 'category', 'statement', 'location', 'source_span'}:
            errors.append('invalid fact fields')
            continue
        if not nonempty(fact['id']) or not nonempty(fact['statement']) or fact['category'] not in CATEGORIES:
            errors.append('invalid fact identity/category/statement')
            continue
        if not exact_span(text, fact['location'], fact['source_span']):
            errors.append('fact source does not match exact manuscript span')
        ids.append(fact['id'])
        categories.add(fact['category'])
    if len(ids) != len(set(ids)):
        errors.append('duplicate fact identity')
    if not errors and set(absent) != set(CATEGORIES) - categories:
        errors.append('every category must have facts or an explicit absent declaration')
    return errors


def mechanical_extract(text):
    """Preserve literal tokens. Their scientific attachment needs semantic review."""
    parsed = scan(text)
    citations = []
    for m in CITATION.finditer(text):
        citations.extend(k.strip().lstrip('@') for k in re.split(r'[,;]', m[1] or m[2]) if k.strip())
    protected = Counter(text[s['start']:s['end']] for s in parsed['protected']
                        if s['kind'] in {'math', 'technical environment', 'technical command argument',
                                         'code', 'inline code', 'bibliography', 'structured table'})
    return {'numbers': Counter(NUMBER.findall(text)), 'citation_keys': Counter(citations),
            'latex_commands': Counter(COMMAND.findall(text)),
            'reference_identifiers': Counter(m[1] for m in LABEL_REF.finditer(text)),
            'reference_numbers': Counter(m[0] for m in REF.finditer(text)),
            'protected_technical_content': protected, 'warnings': parsed['warnings']}


def corruption(text):
    errors = []
    if not text.strip() or '\x00' in text or '\ufffd' in text:
        errors.append('empty or corrupted manuscript encoding')
    parsed = scan(text)
    # Check braces outside inline code and URLs, retaining TeX arguments/math.
    ignore = [s for s in parsed['protected'] if s['kind'] in
              {'code', 'inline code', 'URL', 'bibliography', 'TeX comment'}]
    depth, envs = 0, []
    for i, char in enumerate(text):
        if any(s['start'] <= i < s['end'] for s in ignore) or (i and text[i - 1] == '\\'):
            continue
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth < 0:
                errors.append('unbalanced braces')
                break
    if depth:
        errors.append('unbalanced braces')
    for m in re.finditer(r'\\(begin|end)\{([^{}]+)\}', text):
        if any(s['start'] <= m.start() < s['end'] for s in ignore):
            continue
        if m[1] == 'begin':
            envs.append(m[2])
        elif not envs or envs.pop() != m[2]:
            errors.append('unbalanced LaTeX environments')
    if envs:
        errors.append('unclosed LaTeX environments')
    return list(dict.fromkeys(errors))


def compare(original, revised, original_facts=None, revised_facts=None, audit=None):
    errors, warnings = [], []
    before, after = mechanical_extract(original), mechanical_extract(revised)
    for key in before:
        if key == 'warnings':
            warnings.extend(before[key] + after[key])
        elif before[key] != after[key]:
            errors.append(key + ' changed')
    errors.extend(corruption(revised))
    mechanical_status = 'FAIL' if errors else 'NEEDS_REVIEW' if warnings else 'PASS'
    semantic_errors, semantic_unknown = [], []
    if original_facts is None or revised_facts is None or audit is None:
        semantic_unknown.append('complete independent extraction and semantic audit are required')
    else:
        try:
            semantic_errors, semantic_unknown = semantic_gate(original, revised, original_facts, revised_facts, audit)
        except (TypeError, KeyError, ValueError, AttributeError) as exc:
            semantic_errors.append('invalid semantic artifact: ' + str(exc))
    status = 'FAIL' if errors or semantic_errors else 'NEEDS_REVIEW' if warnings or semantic_unknown else 'PASS'
    return {'status': status, 'mechanical_status': mechanical_status,
            'semantic_status': 'FAIL' if semantic_errors else 'NEEDS_REVIEW' if semantic_unknown else 'PASS',
            'errors': errors + semantic_errors, 'warnings': warnings + semantic_unknown,
            'note': 'A supplied audit is a trust boundary. Token equality and hashes do not prove scientific equivalence.'}


def semantic_gate(original, revised, original_facts, revised_facts, audit):
    # Implemented separately from extraction. No regex judgments of scientific meaning.
    errors = validate_facts(original, original_facts) + validate_facts(revised, revised_facts)
    if errors:
        return errors, []
    unknown = list(original_facts['unresolved']) + list(revised_facts['unresolved'])
    required = {'schema', 'original_digest', 'revised_digest', 'original_facts_digest',
                'revised_facts_digest', 'fact_checks', 'new_assertion_checks', 'global_checks'}
    if not isinstance(audit, dict) or set(audit) != required or audit['schema'] != 'manuscript-semantic-audit@1':
        return ['invalid semantic audit contract'], unknown
    for key, value in (('original_digest', digest(original)), ('revised_digest', digest(revised)),
                       ('original_facts_digest', digest(original_facts)), ('revised_facts_digest', digest(revised_facts))):
        if audit[key] != value:
            errors.append('stale audit provenance ' + key)
    old = {f['id']: f for f in original_facts['facts']}
    new = {f['id']: f for f in revised_facts['facts']}
    edges = set()

    def verdict(check):
        if check['status'] not in ('PASS', 'FAIL', 'UNKNOWN') or not nonempty(check['rationale']):
            errors.append('missing semantic verdict/rationale')
        elif check['status'] == 'FAIL':
            errors.append(check['rationale'])
        elif check['status'] == 'UNKNOWN':
            unknown.append(check['rationale'])

    for key, ids, identity, link, targets in (
            ('fact_checks', old, 'original_id', 'revised_ids', new),
            ('new_assertion_checks', new, 'revised_id', 'original_ids', old)):
        checks = audit[key]
        if not isinstance(checks, list):
            errors.append('missing fact coverage ' + key)
            continue
        seen = []
        for check in checks:
            if not isinstance(check, dict) or set(check) != {identity, link, 'status', 'rationale'}:
                errors.append('invalid semantic fact check')
                continue
            cid, links = check[identity], check[link]
            if cid not in ids or not isinstance(links, list) or any(x not in targets for x in links) or len(links) != len(set(links)):
                errors.append('invalid fact mapping')
                continue
            seen.append(cid)
            if check['status'] == 'PASS' and not links:
                errors.append('PASS cannot omit a fact or introduce an unsupported assertion')
            if any(ids[cid]['category'] != targets[x]['category'] for x in links):
                errors.append('mapped fact categories differ')
            verdict(check)
            for item in links:
                pair = (cid, item) if key == 'fact_checks' else (item, cid)
                if key == 'fact_checks':
                    edges.add(pair)
                elif pair not in edges:
                    errors.append('nonreciprocal fact mapping')
        if Counter(seen) != Counter(ids.keys()):
            errors.append('incomplete or duplicated semantic coverage ' + key)
    reverse = {(x['original_ids'][i], x['revised_id']) for x in audit['new_assertion_checks']
               if isinstance(x, dict) and isinstance(x.get('original_ids'), list)
               for i in range(len(x['original_ids']))}
    if reverse != edges:
        errors.append('fact mapping coverage is not reciprocal')
    globals_ = audit['global_checks']
    if not isinstance(globals_, dict) or set(globals_) != set(GLOBAL_CHECKS):
        errors.append('incomplete global semantic audit')
    else:
        for check in globals_.values():
            if not isinstance(check, dict) or set(check) != {'status', 'rationale'}:
                errors.append('invalid global semantic check')
            else:
                verdict(check)
    return errors, unknown


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('revised', type=Path)
    for arg in ('original-facts', 'revised-facts', 'audit'):
        parser.add_argument('--' + arg, type=Path)
    args = parser.parse_args()
    try:
        read_json = lambda p: json.loads(p.read_text(encoding='utf-8')) if p else None
        result = compare(args.original.read_text(encoding='utf-8'), args.revised.read_text(encoding='utf-8'),
                         read_json(args.original_facts), read_json(args.revised_facts), read_json(args.audit))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {'PASS': 0, 'FAIL': 3}.get(result['status'], 4)


if __name__ == '__main__':
    raise SystemExit(main())
