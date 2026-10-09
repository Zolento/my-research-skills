#!/usr/bin/env python3
"""Submission compliance for clearly checkable requirements.

Hard venue policy is reported separately from scientific quality. The gate only
verifies what is mechanically verifiable. Everything a machine cannot establish
stays NEEDS_REVIEW, because the safe failure of a compliance gate is "unknown",
never a false PASS.

Two rules deserve emphasis:
  * A page limit is judged on the compiled document. When no compiled file is
    supplied, the page count is UNKNOWN. A LaTeX source length is never a
    substitute, so this gate cannot claim compliance it did not measure.
  * AI-use disclosure is only cross-checked against records the author actually
    supplied. The gate never infers, guesses or reconstructs a usage history.
"""
import argparse
import json
from pathlib import Path
import re

import compare_invariants as ci
import venue_intelligence_core as vic

NOTE = ('Compliance is reported separately from scientific quality. Only stated, checkable '
        'requirements are verified; everything else stays NEEDS_REVIEW. This gate does not '
        'certify that a submission meets a venue policy it could not inspect.')

MANIFEST_FIELDS = {'schema', 'venue', 'year', 'track', 'source_path', 'compiled_path',
                   'declarations', 'ai_use_records'}
DECLARATION_STATES = ('PRESENT', 'ABSENT', 'NOT_APPLICABLE', 'UNKNOWN')
AI_USE_STATUS = ('DISCLOSED', 'NOT_DISCLOSED', 'NOT_USED', 'UNKNOWN')

# Declaration topics a profile may require, mapped to manifest declaration keys.
DECLARATION_TOPICS = ('anonymity', 'ai_use_disclosure', 'reproducibility', 'ethics',
                      'data_availability', 'code_release', 'authorship', 'conflict_of_interest',
                      'licensing', 'dual_submission')


def pdf_page_count(path):
    """Page count from a compiled PDF, using only the standard library.

    Reads the /Count of the largest page tree node, which is what a viewer
    reports. Returns None when the file is not a readable PDF, so the caller can
    report UNKNOWN instead of inventing a number.
    """
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    if not data.startswith(b'%PDF-'):
        return None
    counts = [int(m) for m in re.findall(rb'/Type\s*/Pages[^>]*?/Count\s+(\d+)', data, re.S)]
    if not counts:
        # Some writers place /Count before /Type.
        counts = [int(m) for m in re.findall(rb'/Count\s+(\d+)[^>]*?/Type\s*/Pages', data, re.S)]
    if counts:
        return max(counts)
    pages = len(re.findall(rb'/Type\s*/Page[^s]', data))
    return pages or None


def _check(manifest, profile, profiles_present):
    errors, review, results = [], [], []
    if profile is None:
        return {'status': 'NEEDS_REVIEW',
                'errors': [], 'unresolved': ['no policy profile: no mandatory requirement applies '
                                             'and no compliance claim is made'],
                'checks': [], 'venue_neutral': True, 'note': NOTE}
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS:
        return {'status': 'FAIL', 'errors': ['invalid compliance manifest fields'], 'checks': []}
    if manifest['schema'] != 'submission-manifest@1':
        errors.append('invalid manifest schema')
    scope = vic.profile_scope(profile)
    for key in ('venue', 'year', 'track'):
        if manifest[key] != scope[key]:
            errors.append('manifest ' + key + ' does not match the cited profile scope')
    source = Path(manifest['source_path'])
    if not source.is_file():
        errors.append('source_path does not resolve to a file')
    declarations = manifest['declarations']
    if not isinstance(declarations, dict):
        errors.append('declarations must be an object')
        declarations = {}
    for key, value in declarations.items():
        if key not in DECLARATION_TOPICS:
            errors.append('unknown declaration topic: ' + str(key))
        elif value not in DECLARATION_STATES:
            errors.append('invalid declaration state for ' + key)

    # Page limit: compiled document only.
    page_limits = [c for c in profile.get('compliance_checks', [])
                   if c.get('check_kind') == 'page_limit']
    measured = pdf_page_count(manifest['compiled_path']) if manifest['compiled_path'] else None
    for check in page_limits:
        limit = _limit_from(check.get('requirement', ''))
        if limit is None:
            review.append(check['id'] + ': page limit could not be parsed from the requirement')
            results.append({'id': check['id'], 'status': 'NEEDS_REVIEW',
                            'why': 'page limit is not expressible as a number'})
            continue
        if measured is None:
            review.append(check['id'] + ': no compiled document supplied, so the page count is '
                                        'UNKNOWN; a LaTeX source length is not a page count')
            results.append({'id': check['id'], 'status': 'NEEDS_REVIEW', 'measured_pages': None,
                            'limit': limit, 'why': 'page count requires a compiled PDF'})
        elif measured > limit:
            errors.append(check['id'] + ': compiled document has ' + str(measured)
                          + ' pages, limit is ' + str(limit))
            results.append({'id': check['id'], 'status': 'FAIL', 'measured_pages': measured,
                            'limit': limit})
        else:
            results.append({'id': check['id'], 'status': 'PASS', 'measured_pages': measured,
                            'limit': limit, 'source': manifest['compiled_path']})

    # Required declarations.
    for check in profile.get('compliance_checks', []):
        kind = check.get('check_kind')
        if kind not in ('declaration', 'anonymization', 'structure', 'template', 'citation'):
            continue
        topic = check.get('topic') or _topic_from_text(check.get('requirement', ''))
        state = declarations.get(topic, 'UNKNOWN') if topic else 'UNKNOWN'
        if topic is None:
            review.append(check['id'] + ': requirement text does not map to a declaration topic')
            results.append({'id': check['id'], 'status': 'NEEDS_REVIEW'})
        elif state == 'ABSENT':
            if check.get('mechanically_checkable'):
                errors.append(check['id'] + ': required declaration is absent: ' + str(topic))
                results.append({'id': check['id'], 'status': 'FAIL', 'topic': topic})
            else:
                review.append(check['id'] + ': declaration ' + str(topic) + ' is absent')
                results.append({'id': check['id'], 'status': 'NEEDS_REVIEW', 'topic': topic})
        elif state == 'UNKNOWN':
            review.append(check['id'] + ': declaration ' + str(topic) + ' is not recorded')
            results.append({'id': check['id'], 'status': 'NEEDS_REVIEW', 'topic': topic})
        elif state == 'NOT_APPLICABLE':
            results.append({'id': check['id'], 'status': 'PASS', 'topic': topic,
                            'why': 'declared not applicable by the author'})
        else:
            results.append({'id': check['id'], 'status': 'PASS', 'topic': topic})

    # AI-use disclosure: verify only against supplied records.
    ai_required = any(_topic_from_text(c.get('requirement', '')) == 'ai_use_disclosure'
                      for c in profile.get('compliance_checks', []))
    records = manifest['ai_use_records']
    if not isinstance(records, list):
        errors.append('ai_use_records must be a list')
        records = []
    for record in records:
        if not isinstance(record, dict) or set(record) != {'tool', 'purpose', 'status'} or \
                not ci.nonempty(record['tool']) or not ci.nonempty(record['purpose']) or \
                record['status'] not in AI_USE_STATUS:
            errors.append('invalid AI-use record')
    declared_ai = declarations.get('ai_use_disclosure', 'UNKNOWN')
    used = [r for r in records if isinstance(r, dict) and r.get('status') in ('DISCLOSED', 'NOT_DISCLOSED')]
    if ai_required:
        if declared_ai == 'UNKNOWN':
            review.append('AI-use policy applies but no disclosure state was recorded; '
                          'the gate does not infer a usage history')
        elif used and any(r['status'] == 'NOT_DISCLOSED' for r in used):
            errors.append('an AI-use record is marked NOT_DISCLOSED while the policy requires disclosure')
        elif not records and declared_ai == 'ABSENT':
            review.append('AI-use disclosure is recorded absent; confirm no tool use required disclosure')

    unresolved = list(review)
    return {'status': 'FAIL' if errors else 'NEEDS_REVIEW' if unresolved else 'PASS',
            'schema': vic.SCHEMAS['compliance'], 'venue_scope': scope,
            'checks': results, 'page_count': measured,
            'errors': errors, 'unresolved': unresolved, 'venue_neutral': False, 'note': NOTE}


def _limit_from(text):
    match = re.search(r'(\d+)\s*pages?', str(text), re.I)
    return int(match.group(1)) if match else None


def _topic_from_text(text):
    lowered = str(text).lower()
    mapping = (('anonym', 'anonymity'), ('llm', 'ai_use_disclosure'), ('large language', 'ai_use_disclosure'),
               ('generative ai', 'ai_use_disclosure'), ('reproducib', 'reproducibility'),
               ('code', 'code_release'), ('data', 'data_availability'), ('ethic', 'ethics'),
               ('conflict', 'conflict_of_interest'), ('licens', 'licensing'),
               ('dual submission', 'dual_submission'), ('authorship', 'authorship'))
    for needle, topic in mapping:
        if needle in lowered:
            return topic
    return None


def check(manifest, profile):
    try:
        return _check(manifest, profile, profile is not None)
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid compliance artifact: ' + str(exc)], 'checks': []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--venue', required=True)
    parser.add_argument('--year', type=int, required=True)
    parser.add_argument('--track', required=True)
    parser.add_argument('--registry', type=Path, required=True)
    args = parser.parse_args()
    try:
        import venue_registry
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        profile, _name, _missing = venue_registry.Registry(args.registry).resolve(
            args.venue, args.year, args.track)
        result = check(manifest, profile)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 3 if result['status'] == 'FAIL' else 4


if __name__ == '__main__':
    raise SystemExit(main())
