#!/usr/bin/env python3
"""Load, scope and validate the Venue Policy Registry.

Offline by default. A profile is a source-bound record for one venue, year and
track. This module enforces three things that matter scientifically:

1. Policy scope is exact. A profile only applies to its own venue, year and
   track, so a historical or sibling policy can never become a current mandate.
2. Every claim is traceable. Each quoted excerpt must occur verbatim in the
   saved excerpt of the source it cites, so a summary cannot masquerade as a
   published rule.
3. Uncertainty stays visible. UNKNOWN and PENDING survive loading; they are
   never filled from another year or promoted to VERIFIED.

It performs no science, calls no model and requires no network.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

SCHEMA = 'venue-policy-profile@1'
POLICY_KINDS = ('MANDATORY_POLICY', 'REVIEW_CRITERION', 'RECOMMENDED_PRACTICE',
                'EMPIRICAL_CONVENTION', 'UNKNOWN')
SOURCE_STATUS = ('VERIFIED', 'PARTIAL', 'UNREACHABLE')
CHANGE_STATUS = ('CONFIRMED_CHANGE', 'PENDING', 'UNKNOWN')
EXPLICITNESS = ('EXPLICIT', 'INFERRED', 'UNKNOWN')
APPLICABILITY = ('REQUIRED', 'CONDITIONAL', 'OPTIONAL', 'NOT_APPLICABLE')
SOURCE_TYPES = ('author_guidelines', 'reviewer_guidelines', 'review_form', 'call_for_papers',
                'ethics_policy', 'reproducibility_guidelines', 'submission_requirements',
                'code_of_conduct', 'official_faq')
PHASES = ('author', 'reviewer', 'both')
TOPICS = ('anonymity', 'dual_submission', 'ai_use_disclosure', 'reproducibility', 'ethics',
          'data_availability', 'code_release', 'page_limit', 'supplementary', 'review_process',
          'author_response', 'authorship', 'conflict_of_interest', 'licensing', 'other')
DIMENSIONS = ('scope_fit', 'contribution_fit', 'soundness', 'originality', 'significance',
              'experimental_adequacy', 'theoretical_adequacy', 'reproducibility',
              'transparency', 'compliance', 'ethics', 'other')
CHECK_KINDS = ('structure', 'declaration', 'template', 'citation', 'anonymization',
               'page_limit', 'needs_review', 'none')
VENUES = ('NeurIPS', 'ICML', 'ICLR', 'CVPR', 'ICCV', 'ECCV', 'MICCAI', 'ACL', 'ARR', 'AAAI')

PROFILE_FIELDS = {'schema', 'profile_version', 'venue', 'year', 'track', 'verification_date',
                  'sources', 'contribution_types', 'review_criteria', 'mandatory_policy',
                  'recommended_practice', 'compliance_checks', 'changes_from_prior_year',
                  'unknown_policies'}
SOURCE_FIELDS = {'id', 'url', 'source_type', 'phase', 'retrieved', 'digest', 'status'}
SOURCE_OPTIONAL = {'note'}
CONTRIBUTION_FIELDS = {'id', 'claim_kind', 'label', 'scope', 'quote', 'source_id'}
CRITERION_FIELDS = {'id', 'name', 'dimension', 'official_explanation', 'quote', 'source_id'}
CLAIM_FIELDS = {'id', 'topic', 'statement', 'claim_kind', 'explicitness', 'applicability',
                'quote', 'source_id'}
CLAIM_OPTIONAL = {'conditions'}
COMPLIANCE_FIELDS = {'id', 'requirement', 'mechanically_checkable', 'check_kind', 'source_id'}
CHANGE_FIELDS = {'id', 'change', 'status'}
CHANGE_OPTIONAL = {'source_id'}
UNKNOWN_FIELDS = {'id', 'question', 'reason'}
UNKNOWN_OPTIONAL = {'source_id'}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def normalize(text):
    """Whitespace-insensitive text for quote containment."""
    return re.sub(r'\s+', ' ', text).strip()


def digest_of(text):
    return 'sha256:' + hashlib.sha256(text.encode('utf-8')).hexdigest()


class Registry:
    """A directory of policy profiles plus their source excerpt files."""

    def __init__(self, root):
        self.root = Path(root)

    def profile_paths(self):
        return sorted((self.root / 'profiles').glob('*.json'))

    def source_paths(self):
        return sorted((self.root / 'sources').glob('*.json'))

    def load_excerpts(self):
        excerpts, errors = {}, []
        for path in self.source_paths():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                errors.append(path.name + ': unreadable source file: ' + str(exc))
                continue
            if not isinstance(data, dict) or data.get('schema') != 'venue-policy-source@1':
                errors.append(path.name + ': invalid source schema')
                continue
            if not nonempty(data.get('id')):
                errors.append(path.name + ': source needs an id')
                continue
            validate_excerpt_source(data, 'source file ' + path.name, errors)
            if data['id'] in excerpts:
                errors.append('duplicate source id: ' + data['id'])
            excerpts[data['id']] = data
        return excerpts, errors

    def profiles(self):
        return [json.loads(p.read_text(encoding='utf-8')) for p in self.profile_paths()]

    def resolve(self, venue, year, track):
        """Exact-scope lookup. Never falls back to another year or track."""
        for path in self.profile_paths():
            profile = json.loads(path.read_text(encoding='utf-8'))
            if profile.get('venue') == venue and profile.get('year') == year and profile.get('track') == track:
                return profile, path.name, None
        available = sorted({(p['venue'], p['year']) for p in self.profiles()
                            if 'venue' in p and 'year' in p})
        return None, None, {'status': 'UNRESOLVED', 'venue': venue, 'year': year, 'track': track,
                            'available': available,
                            'reason': 'no policy profile for this exact venue, year and track; '
                                      'a policy from another year or track is never applied'}


def _check_fields(obj, required, optional, label, errors):
    if not isinstance(obj, dict):
        errors.append(label + ' must be an object')
        return False
    missing = required - set(obj)
    extra = set(obj) - required - optional
    if missing:
        errors.append(label + ' missing fields: ' + ', '.join(sorted(missing)))
    if extra:
        errors.append(label + ' unknown fields: ' + ', '.join(sorted(extra)))
    return not missing and not extra


def _check_enum(obj, field, allowed, label, errors):
    if obj.get(field) not in allowed:
        errors.append(label + '.' + field + ' must be one of ' + ', '.join(allowed))


def validate_source(source, label, errors):
    if not _check_fields(source, SOURCE_FIELDS, SOURCE_OPTIONAL, label, errors):
        return
    if not nonempty(source['id']) or not nonempty(source['url']) or not nonempty(source['digest']):
        errors.append(label + ' must carry a nonempty id, url and digest')
    if not re.match(r'^https?://', str(source['url'])):
        errors.append(label + ' url must be an official http(s) source')
    _check_enum(source, 'source_type', SOURCE_TYPES, label, errors)
    _check_enum(source, 'phase', PHASES, label, errors)
    _check_enum(source, 'status', SOURCE_STATUS, label, errors)
    for field in ('retrieved',):
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(source[field])):
            errors.append(label + '.' + field + ' must be an ISO date')
    if not re.match(r'^sha256:[0-9a-f]{16,64}$', str(source['digest'])):
        errors.append(label + '.digest must be a sha256 digest')


def validate_excerpt_source(source, label, errors):
    """Validate a venue-policy-source@1 excerpt file, not a profile source entry."""
    fields = {'schema', 'id', 'venue', 'year', 'url', 'source_type', 'retrieved', 'excerpt'}
    optional = {'note'}
    if not _check_fields(source, fields, optional, label, errors):
        return
    if not nonempty(source['id']) or not nonempty(source['venue']):
        errors.append(label + ' needs a nonempty id and venue')
    if type(source['year']) is not int or source['year'] < 2024:
        errors.append(label + '.year must be an integer of at least 2024')
    if not re.match(r'^https?://', str(source['url'])):
        errors.append(label + '.url must be an official http(s) source')
    _check_enum(source, 'source_type', SOURCE_TYPES, label, errors)
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(source['retrieved'])):
        errors.append(label + '.retrieved must be an ISO date')
    if not isinstance(source['excerpt'], str) or len(source['excerpt']) < 200:
        errors.append(label + '.excerpt must be at least 200 characters of verbatim source text')


def validate_profile(profile, excerpts, filename='profile'):
    """Structural plus provenance validation. Returns a list of error strings."""
    errors = []
    if not _check_fields(profile, PROFILE_FIELDS, set(), filename, errors):
        return errors
    if profile['schema'] != SCHEMA:
        errors.append('invalid schema: ' + str(profile['schema']))
    _check_enum(profile, 'venue', VENUES, filename, errors)
    if type(profile['year']) is not int or profile['year'] < 2024:
        errors.append('year must be an integer of at least 2024')
    if not nonempty(profile['track']):
        errors.append('track must be nonempty')
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(profile['verification_date'])):
        errors.append('verification_date must be an ISO date')
    if type(profile['profile_version']) is not int or profile['profile_version'] < 1:
        errors.append('profile_version must be a positive integer')

    for i, source in enumerate(profile['sources']):
        validate_source(source, 'source[' + str(i) + ']', errors)
    ids = [s.get('id') for s in profile['sources'] if isinstance(s, dict)]
    if len(ids) != len(set(ids)):
        errors.append('duplicate source id inside profile')
    by_id = {s['id']: s for s in profile['sources'] if isinstance(s, dict) and 'id' in s}

    def check_source_ref(label, source_id, require_verified=False):
        if source_id not in by_id:
            errors.append(label + ' cites unknown source: ' + str(source_id))
            return
        if source_id not in excerpts:
            errors.append(label + ' cites a source with no saved excerpt: ' + str(source_id))
            return
        excerpt = excerpts[source_id]
        if excerpt.get('url') != by_id[source_id]['url']:
            errors.append(label + ' source url differs from the saved excerpt url')
        if require_verified and by_id[source_id]['status'] == 'UNREACHABLE':
            errors.append(label + ' relies on an unreachable source')

    def check_quote(label, claim, source_id):
        if not nonempty(claim.get('quote')):
            errors.append(label + ' must carry a verbatim quote')
            return 'missing'
        if source_id not in excerpts:
            return 'unresolved'
        haystack = normalize(excerpts[source_id].get('excerpt', ''))
        if normalize(claim['quote']) not in haystack:
            errors.append(label + ' quote does not occur in its saved source excerpt')
            return 'absent'
        return 'ok'

    # Contribution types: internal kinds must not be presented as official names
    seen = []
    for i, item in enumerate(profile['contribution_types']):
        label = 'contribution_types[' + str(i) + ']'
        if not _check_fields(item, CONTRIBUTION_FIELDS, set(), label, errors):
            continue
        _check_enum(item, 'claim_kind', POLICY_KINDS, label, errors)
        if not all(nonempty(item[k]) for k in ('id', 'label', 'scope')):
            errors.append(label + ' needs nonempty id, label and scope')
        check_source_ref(label, item.get('source_id'))
        check_quote(label, item, item.get('source_id'))
        seen.append(item.get('id'))
    if len(seen) != len(set(seen)):
        errors.append('duplicate contribution type id')

    dimensions = []
    criteria_ids = []
    for i, item in enumerate(profile['review_criteria']):
        label = 'review_criteria[' + str(i) + ']'
        if not _check_fields(item, CRITERION_FIELDS, set(), label, errors):
            continue
        _check_enum(item, 'dimension', DIMENSIONS, label, errors)
        if not all(nonempty(item[k]) for k in ('id', 'name', 'official_explanation')):
            errors.append(label + ' needs nonempty id, name and official_explanation')
        check_source_ref(label, item.get('source_id'))
        check_quote(label, item, item.get('source_id'))
        dimensions.append(item.get('dimension'))
        criteria_ids.append(item.get('id'))
    if len(criteria_ids) != len(set(criteria_ids)):
        errors.append('duplicate review criterion id')
    if len(dimensions) != len(set(dimensions)):
        errors.append('review criteria must cover distinct dimensions')

    def check_claims(items, kind_section, require_kind=None):
        claim_ids = []
        for i, item in enumerate(items):
            label = kind_section + '[' + str(i) + ']'
            if not _check_fields(item, CLAIM_FIELDS, CLAIM_OPTIONAL, label, errors):
                continue
            _check_enum(item, 'topic', TOPICS, label, errors)
            _check_enum(item, 'claim_kind', POLICY_KINDS, label, errors)
            _check_enum(item, 'explicitness', EXPLICITNESS, label, errors)
            _check_enum(item, 'applicability', APPLICABILITY, label, errors)
            if not all(nonempty(item[k]) for k in ('id', 'statement')):
                errors.append(label + ' needs nonempty id and statement')
            check_source_ref(label, item.get('source_id'))
            result = check_quote(label, item, item.get('source_id'))
            # A mandatory requirement cannot rest on an unreachable source or an
            # inferred reading. That is how an unverified rule would become a gate.
            if item.get('claim_kind') == 'MANDATORY_POLICY':
                if item.get('explicitness') != 'EXPLICIT':
                    errors.append(label + ' mandatory policy must be EXPLICIT, not ' + str(item.get('explicitness')))
                source = by_id.get(item.get('source_id'))
                if source and source.get('status') != 'VERIFIED':
                    errors.append(label + ' mandatory policy needs a VERIFIED source, not ' + str(source.get('status')))
                if result in ('absent', 'missing', 'unresolved'):
                    errors.append(label + ' mandatory policy is not source-verified')
                if item.get('applicability') not in ('REQUIRED', 'CONDITIONAL'):
                    errors.append(label + ' mandatory policy applicability must be REQUIRED or CONDITIONAL')
            if item.get('applicability') == 'REQUIRED' and item.get('claim_kind') != 'MANDATORY_POLICY':
                errors.append(label + ' a REQUIRED item must be a MANDATORY_POLICY')
            if item.get('claim_kind') == 'UNKNOWN' and item.get('explicitness') != 'UNKNOWN':
                errors.append(label + ' UNKNOWN claim kind needs explicitness UNKNOWN')
            claim_ids.append(item.get('id'))
        if len(claim_ids) != len(set(claim_ids)):
            errors.append('duplicate id in ' + kind_section)
        return claim_ids

    check_claims(profile['mandatory_policy'], 'mandatory_policy')
    check_claims(profile['recommended_practice'], 'recommended_practice')

    check_ids = []
    for i, item in enumerate(profile['compliance_checks']):
        label = 'compliance_checks[' + str(i) + ']'
        if not _check_fields(item, COMPLIANCE_FIELDS, set(), label, errors):
            continue
        _check_enum(item, 'check_kind', CHECK_KINDS, label, errors)
        if not nonempty(item['id']) or not nonempty(item['requirement']):
            errors.append(label + ' needs nonempty id and requirement')
        if type(item['mechanically_checkable']) is not bool:
            errors.append(label + '.mechanically_checkable must be a boolean')
        if item['mechanically_checkable'] and item['check_kind'] in ('needs_review', 'none'):
            errors.append(label + ' a mechanically checkable item needs a real check_kind')
        if not item['mechanically_checkable'] and item['check_kind'] not in ('needs_review', 'none'):
            errors.append(label + ' an uncertain item must be needs_review or none')
        check_source_ref(label, item.get('source_id'))
        check_ids.append(item['id'])
    if len(check_ids) != len(set(check_ids)):
        errors.append('duplicate compliance check id')

    change_ids = []
    for i, item in enumerate(profile['changes_from_prior_year']):
        label = 'changes_from_prior_year[' + str(i) + ']'
        if not _check_fields(item, CHANGE_FIELDS, CHANGE_OPTIONAL, label, errors):
            continue
        _check_enum(item, 'status', CHANGE_STATUS, label, errors)
        if not nonempty(item['id']) or not nonempty(item['change']):
            errors.append(label + ' needs nonempty id and change')
        if item['status'] == 'CONFIRMED_CHANGE' and not nonempty(item.get('source_id')):
            errors.append(label + ' a confirmed change needs a source')
        if nonempty(item.get('source_id')):
            check_source_ref(label, item['source_id'])
        change_ids.append(item['id'])
    if len(change_ids) != len(set(change_ids)):
        errors.append('duplicate change id')

    unknown_ids = []
    for i, item in enumerate(profile['unknown_policies']):
        label = 'unknown_policies[' + str(i) + ']'
        if not _check_fields(item, UNKNOWN_FIELDS, UNKNOWN_OPTIONAL, label, errors):
            continue
        if not all(nonempty(item[k]) for k in ('id', 'question', 'reason')):
            errors.append(label + ' needs nonempty id, question and reason')
        if nonempty(item.get('source_id')):
            check_source_ref(label, item['source_id'])
        unknown_ids.append(item['id'])
    if len(unknown_ids) != len(set(unknown_ids)):
        errors.append('duplicate unknown policy id')
    return errors


def invalid_inheritance(profile, excerpts):
    """Report sources that do not belong to this profile's own venue and year.

    A rule is only in force for the year it was published for. A profile that
    cites another year's document would silently inherit a superseded mandate,
    which is exactly the error the registry exists to prevent.
    """
    errors = []
    for source in profile.get('sources', []):
        excerpt = excerpts.get(source.get('id'))
        if not excerpt:
            continue
        if excerpt.get('venue') != profile.get('venue') or excerpt.get('year') != profile.get('year'):
            errors.append('source ' + str(source.get('id')) + ' belongs to '
                          + str(excerpt.get('venue')) + ' ' + str(excerpt.get('year'))
                          + ' but the profile is ' + str(profile.get('venue')) + ' '
                          + str(profile.get('year')))
    return errors


def coverage(registry):
    rows = []
    for path in registry.profile_paths():
        try:
            profile = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        rows.append({'file': path.name, 'venue': profile.get('venue'), 'year': profile.get('year'),
                     'track': profile.get('track'),
                     'mandatory': len(profile.get('mandatory_policy', [])),
                     'criteria': len(profile.get('review_criteria', [])),
                     'unknown': len(profile.get('unknown_policies', [])),
                     'changes': len(profile.get('changes_from_prior_year', [])),
                     'sources': len(profile.get('sources', []))})
    return rows


def check(registry_path):
    """Validate every profile in a registry directory."""
    registry = Registry(registry_path)
    excerpts, errors = registry.load_excerpts()
    rows = coverage(registry)
    for path in registry.profile_paths():
        try:
            profile = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            errors.append(path.name + ': unreadable profile: ' + str(exc))
            continue
        errors.extend(path.name + ': ' + e for e in validate_profile(profile, excerpts, path.name))
    # cross-profile checks
    keys = Counter()
    for path in registry.profile_paths():
        try:
            profile = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        key = (profile.get('venue'), profile.get('year'), profile.get('track'))
        keys[key] += 1
        errors.extend(path.name + ': ' + e for e in invalid_inheritance(profile, excerpts))
    for key, count in keys.items():
        if count > 1:
            errors.append('duplicate profile for ' + ' '.join(str(x) for x in key))
    return {'status': 'FAIL' if errors else 'PASS', 'errors': errors, 'coverage': rows,
            'sources_checked': len(excerpts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('registry', type=Path)
    parser.add_argument('--venue')
    parser.add_argument('--year', type=int)
    parser.add_argument('--track')
    args = parser.parse_args()
    registry = Registry(args.registry)
    if args.venue:
        if args.year is None or not args.track:
            result = {'status': 'INVALID', 'errors': ['--venue requires --year and --track for exact-scope lookup']}
        else:
            profile, name, missing = registry.resolve(args.venue, args.year, args.track)
            result = (missing if profile is None
                      else {'status': 'RESOLVED', 'file': name, 'profile': profile})
    else:
        result = check(args.registry)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] in ('PASS', 'RESOLVED') else 3 if result['status'] == 'FAIL' else 4


if __name__ == '__main__':
    raise SystemExit(main())
