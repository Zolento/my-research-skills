#!/usr/bin/env python3
"""Source-bound suggestion contracts and optional, explicitly selected local edits.

Semantic quality is a separate supplied audit. Scripts never auto-choose scientific
changes, rewrite to meet quotas, or overwrite a manuscript.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from audit_coherence import REPAIRS, SCIENCE_CATEGORIES
from compare_invariants import digest, exact_span, nonempty

CATEGORIES = SCIENCE_CATEGORIES + ('narrative', 'paragraph', 'claims', 'language', 'references', 'defensive')
QUALITY_CHECKS = ('actionable', 'distinct_alternatives', 'not_synonym_only', 'not_quota_driven', 'calibrated_claim', 'preserves_voice')
SEVERITY = {'minor': 0, 'moderate': 1, 'major': 2, 'critical': 3}


def bank_digest(bank):
    return digest({k: v for k, v in bank.items() if k != 'quality_audit'})


def _validate(text, bank, coherence):
    required = {'schema', 'manuscript_digest', 'mode', 'coherence_digest', 'short_diagnosis',
                'reviewed_categories', 'suggestions', 'keep_as_is', 'quality_audit'}
    errors, unknown = [], []
    if not isinstance(bank, dict) or set(bank) != required:
        return {'status': 'FAIL', 'errors': ['invalid bank fields']}
    if bank['schema'] != 'manuscript-suggestions@1' or bank['manuscript_digest'] != digest(text) or bank['mode'] not in ('audit', 'suggest', 'architect', 'revise'):
        errors.append('invalid bank provenance/mode')
    if Counter(bank['reviewed_categories']) != Counter(CATEGORIES) or not nonempty(bank['short_diagnosis']):
        errors.append('bank must inspect all categories and give a short diagnosis')
    if coherence is None:
        unknown.append('scientific coherence audit is required before editorial decisions')
        origins = {}
    else:
        if bank['coherence_digest'] != digest(coherence):
            errors.append('stale coherence audit binding')
        origins = {f['id']: f for f in coherence.get('findings', [])}
    ids, duplicate = [], set()
    for s in bank['suggestions']:
        fields = {'id', 'category', 'severity', 'confidence', 'location', 'original_span',
                  'diagnosis', 'why_it_matters', 'scientific_risk', 'recommended_action',
                  'alternatives', 'rule_refs', 'apply_by_default', 'source_finding_ids'}
        if not isinstance(s, dict) or set(s) != fields:
            errors.append('invalid suggestion fields')
            continue
        if s['category'] not in CATEGORIES or s['severity'] not in SEVERITY or s['confidence'] not in ('high', 'medium', 'low') or s['scientific_risk'] not in ('low', 'medium', 'high') or type(s['apply_by_default']) is not bool:
            errors.append('invalid suggestion classification')
        if any(not nonempty(s[k]) for k in ('id', 'diagnosis', 'why_it_matters', 'recommended_action')) or not exact_span(text, s['location'], s['original_span']):
            errors.append('suggestion needs exact location and rationale')
        ids.append(s['id'])
        key = (s['location']['start'], s['location']['end'], s['diagnosis'].strip().lower())
        if key in duplicate:
            errors.append('duplicate suggestion for the same located problem')
        duplicate.add(key)
        if not s['rule_refs'] or any(not nonempty(r) for r in s['rule_refs']):
            errors.append('suggestion needs applicable rule references')
        if s['apply_by_default'] and (s['scientific_risk'] != 'low' or bank['mode'] != 'revise'):
            errors.append('high/medium risk or non-Revise changes cannot apply by default')
        scientific = s['category'] in SCIENCE_CATEGORIES
        if scientific and not s['source_finding_ids']:
            errors.append('scientific suggestion must trace to a coherence finding')
        for fid in s['source_finding_ids']:
            if fid not in origins:
                errors.append('suggestion cites an unknown scientific finding')
            elif SEVERITY.get(s['severity'], -1) < SEVERITY[origins[fid]['severity']]:
                errors.append('scientific severity cannot be laundered in the bank')
        options, directions, option_ids = [], [], []
        for option in s['alternatives']:
            fields = {'id', 'option', 'tradeoff', 'direction'} | ({'requires'} if scientific else set())
            if not isinstance(option, dict) or set(option) != fields or any(not nonempty(option[k]) for k in fields):
                errors.append('invalid alternative fields')
                continue
            if scientific and option['requires'] not in REPAIRS:
                errors.append('invalid scientific repair requirement')
            options.append(option['option'].strip().lower())
            directions.append(option['direction'].strip().lower())
            option_ids.append(option['id'])
        if len(option_ids) != len(set(option_ids)) or len(options) != len(set(options)):
            errors.append('duplicate editorial option')
        if s['severity'] in ('major', 'critical') and bank['mode'] != 'audit' and (not 2 <= len(options) <= 3 or len(set(directions)) != len(options)):
            errors.append('important editorial issue needs 2–3 distinct directions')
    if len(ids) != len(set(ids)):
        errors.append('duplicate suggestion identity')
    for kept in bank['keep_as_is']:
        if set(kept) != {'location', 'original_span', 'rationale'} or not exact_span(text, kept['location'], kept['original_span']) or not nonempty(kept['rationale']):
            errors.append('Keep as is needs exact source location and reason')
    quality = bank['quality_audit']
    if quality is None:
        unknown.append('independent editorial quality audit is required')
    elif set(quality) != {'manuscript_digest', 'bank_digest', 'findings'} or quality['manuscript_digest'] != digest(text) or quality['bank_digest'] != bank_digest(bank):
        errors.append('invalid/stale editorial quality audit')
    else:
        checked = []
        for finding in quality['findings']:
            if set(finding) != {'suggestion_id', 'checks'} or set(finding['checks']) != set(QUALITY_CHECKS):
                errors.append('incomplete editorial quality finding')
                continue
            checked.append(finding['suggestion_id'])
            for name, value in finding['checks'].items():
                if value == 'UNKNOWN':
                    unknown.append(name + ' requires semantic review')
                elif value != 'PASS':
                    errors.append('editorial quality failed ' + name)
        if Counter(checked) != Counter(ids):
            errors.append('editorial quality audit must cover each suggestion once')
    return {'status': 'FAIL' if errors else 'NEEDS_REVIEW' if unknown else 'PASS', 'errors': errors,
            'unresolved': unknown, 'scientific_status': coherence.get('status') if coherence else 'NEEDS_REVIEW',
            'revision_ready': not errors and not unknown and coherence is not None and coherence.get('status') == 'PASS'}


def validate(text, bank, coherence=None):
    try:
        return _validate(text, bank, coherence)
    except (TypeError, KeyError, ValueError, AttributeError, IndexError) as exc:
        return {'status': 'FAIL', 'errors': ['invalid suggestion artifact: ' + str(exc)], 'revision_ready': False}


def prepare_revision(text, bank, choices, coherence, authorized=False):
    """Return a proposed copy only. Post-revision semantic/style gates still follow."""
    checked = validate(text, bank, coherence)
    if not authorized or bank.get('mode') != 'revise' or not checked.get('revision_ready'):
        raise ValueError('explicit Revise authorization and complete pre-edit audits are required')
    by_id = {s['id']: s for s in bank['suggestions']}
    edits, selected = [], set()
    for choice in choices:
        if set(choice) != {'suggestion_id', 'option_id', 'replacement'} or choice['suggestion_id'] not in by_id or not isinstance(choice['replacement'], str):
            raise ValueError('invalid selected revision')
        s = by_id[choice['suggestion_id']]
        if s['id'] in selected or s['scientific_risk'] != 'low' or choice['option_id'] not in {o['id'] for o in s['alternatives']}:
            raise ValueError('duplicate choice, high/medium scientific risk or unknown option')
        selected.add(s['id'])
        a, b = s['location']['start'], s['location']['end']
        for kept in bank['keep_as_is']:
            k = kept['location']
            if a < k['end'] and b > k['start']:
                raise ValueError('selected edit touches protected Keep as is prose')
        edits.append((a, b, choice['replacement']))
    edits.sort()
    if any(b > c for (_, b, _), (c, _, _) in zip(edits, edits[1:])):
        raise ValueError('overlapping edits require an explicit combined proposal')
    proposed = text
    for a, b, replacement in reversed(edits):
        proposed = proposed[:a] + replacement + proposed[b:]
    return {'status': 'PROPOSED_NOT_AUDITED', 'revised_text': proposed, 'applied_ids': sorted(selected),
            'original_digest': digest(text), 'revised_digest': digest(proposed),
            'next': 'Re-extract facts, independent semantic audit, mechanical preservation and H1–H3 validation.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manuscript', type=Path)
    parser.add_argument('--bank', type=Path, required=True)
    parser.add_argument('--coherence', type=Path)
    parser.add_argument('--choices', type=Path)
    parser.add_argument('--revise-authorized', action='store_true')
    args = parser.parse_args()
    try:
        text = args.manuscript.read_text(encoding='utf-8')
        bank = json.loads(args.bank.read_text())
        coherence = json.loads(args.coherence.read_text()) if args.coherence else None
        result = prepare_revision(text, bank, json.loads(args.choices.read_text()), coherence, args.revise_authorized) if args.choices else validate(text, bank, coherence)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        result = {'status': 'INVALID', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] in ('PASS', 'PROPOSED_NOT_AUDITED') else 3 if result['status'] == 'FAIL' else 4


if __name__ == '__main__':
    raise SystemExit(main())
