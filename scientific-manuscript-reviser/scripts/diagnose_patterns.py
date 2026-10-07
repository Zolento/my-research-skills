#!/usr/bin/env python3
"""Weak surface candidates and sample statistics, never an AI-authorship detector."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import statistics

from compare_invariants import digest
from validate_style import scan, location

WARNING_LEXICON = {'remarkable', 'groundbreaking', 'unprecedented', 'notably', 'interestingly',
                   'delve', 'leverage', 'utilization', 'facilitate', 'robust', 'novel'}


def sentences(text):
    prose = scan(text)['prose']
    return [m for m in re.finditer(r'[^.!?]+(?:[.!?](?=\s|$)|$)', prose) if m[0].strip()]


def words(text):
    return re.findall(r"\b[A-Za-z]+(?:['-][A-Za-z]+)*\b", text)


def candidates(text):
    spans = sentences(text)
    lengths = [len(words(m[0])) for m in spans]
    result = []

    def add(code, start, end, rationale, frequency):
        result.append({'code': code, 'location': location(text, start, end),
                       'rationale': rationale, 'frequency': frequency, 'confidence': 'low',
                       'requires_semantic_review': True})

    if len(lengths) >= 6 and statistics.mean(lengths) >= 6 and statistics.pstdev(lengths) / statistics.mean(lengths) < .12:
        add('UNIFORM_SENTENCE_LENGTH', spans[0].start(), spans[-1].end(),
            'Repeated lengths may be functional. Inspect rhythm before suggesting any change.', len(spans))
    starts = Counter(words(m[0])[0].lower() for m in spans if words(m[0]))
    for opening, count in starts.items():
        if count >= 3:
            matched = [m for m in spans if words(m[0]) and words(m[0])[0].lower() == opening]
            add('REPEATED_OPENING', matched[0].start(), matched[-1].end(),
                'Repeated opening ' + opening + ' is a weak discourse candidate, not a banned phrase.', count)
    paragraphs = [m for m in re.finditer(r'\S[^\n]*(?:\n(?!\s*\n)[^\n]*)*', scan(text)['prose'])]
    sizes = [len(words(m[0])) for m in paragraphs]
    if len(sizes) >= 4 and min(sizes) >= 12 and statistics.pstdev(sizes) / statistics.mean(sizes) < .12:
        add('PARAGRAPH_SYMMETRY', paragraphs[0].start(), paragraphs[-1].end(),
            'Similar paragraph lengths require a role/template audit, not automatic asymmetry.', len(sizes))
    tokens = [w.lower() for w in words(scan(text)['prose'])]
    density = sum(w in WARNING_LEXICON for w in tokens)
    if len(tokens) >= 40 and density >= 3 and density / len(tokens) >= .05:
        add('CONTEXTUAL_LEXICAL_DENSITY', 0, len(text),
            'Several evaluative/formulaic terms occur together. Verify context and established terminology; no synonym replacement.', density)
    return {'status': 'CANDIDATES_ONLY', 'candidates': result,
            'note': 'Not a naturalness verdict. No AI detector score or obligatory edit follows these weak signals.'}


def author_profile(samples, explicit_user_rules=None):
    if not samples:
        return {'profile_status': 'unknown_without_samples', 'style': 'conservative scientific',
                'sample_digests': [], 'explicit_user_rules': explicit_user_rules or []}
    counts = [len(words(m[0])) for text in samples for m in sentences(text)]
    text = '\n\n'.join(samples)
    return {'profile_status': 'descriptive_samples_only', 'sample_digests': [digest(s) for s in samples],
            'sentence_length': statistics.mean(counts) if counts else None,
            'sentence_length_variance': statistics.pvariance(counts) if counts else None,
            'paragraph_density': 'estimate_requires_paragraph_role_context',
            'claim_directness': 'requires_semantic_profile', 'hedging_level': 'requires_semantic_profile',
            'first_person_usage': len(re.findall(r'\b(?:we|our|us|I)\b', text, re.I)),
            'passive_voice_usage': 'requires_semantic_profile',
            'explicit_user_rules': explicit_user_rules or [],
            'rule_precedence': 'explicit user rules > inferred author profile > venue preferences',
            'note': 'No source sentences stored. Complete qualitative fields with contextual review, not copied prose.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manuscript', type=Path)
    args = parser.parse_args()
    try:
        result = candidates(args.manuscript.read_text(encoding='utf-8'))
    except (OSError, UnicodeError) as exc:
        result = {'status': 'INVALID', 'error': str(exc)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 4 if result['status'] == 'INVALID' else 0


if __name__ == '__main__':
    raise SystemExit(main())
