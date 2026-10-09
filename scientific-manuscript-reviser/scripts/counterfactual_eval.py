#!/usr/bin/env python3
"""Validate a paired counterfactual case set and a separately supplied detection.

This gate validates artifacts. It never runs, simulates or fabricates a detector,
never classifies a manuscript, and contains no keyword or regex rule that claims to
recognize faulty reasoning. It validates the case set structure, then reads an
independently produced `counterfactual-detection@1` artifact and reports detection
recall, clean-rejection accuracy, false positives, uncertainty and location overlap
as separate numbers.

A clean run means the case set and its reporting are well formed. It is not evidence
that this skill detects faulty reasoning. Exit 0 PASS, 3 FAIL, 4 NEEDS_REVIEW or
INVALID.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from evidence_core import (DEFECT_CLASSES, FAULTY_CLASSES, PAIR_OBSERVATIONS,
                           ROBUSTNESS_CLASSES, SCHEMAS, digest, exact_span, spans_overlap)

CASE_FIELDS = ('id', 'class', 'domain', 'correct', 'faulty', 'faulty_defect',
               'faulty_span', 'paraphrase')
EVALUATION_FIELDS = ('schema', 'cases', 'missing_context')
DETECTOR_FIELDS = ('name', 'kind', 'description')
DETECTION_FIELDS = ('schema', 'detector', 'evaluation_digest', 'results')
RESULT_REQUIRED_FIELDS = ('case_id', 'observed', 'detected_span')
RESULT_FIELDS = RESULT_REQUIRED_FIELDS + ('notes',)
ALL_CLASSES = tuple(dict.fromkeys(FAULTY_CLASSES + ROBUSTNESS_CLASSES))
# Robustness classes that carry no defect. Derived, never hardcoded.
CLEAN_CLASSES = tuple(c for c in ROBUSTNESS_CLASSES if c not in DEFECT_CLASSES)
EMPTY_SPAN = {'start': 0, 'end': 0}

LIMITATIONS = [
    'This gate validates a supplied detection artifact over the supplied case set. '
    'It runs no detector, simulates no detector and classifies no manuscript.',
    'Structural validity means the case set and its reporting are well formed. It is '
    'not evidence that this skill, or any skill, detects faulty reasoning.',
    'Measured counts describe the supplied detector on THIS case set only. They are '
    'not a benchmark and do not generalize to other manuscripts or case sets.',
    'Detection recall and clean-rejection accuracy are separate abilities and are '
    'reported as separate numbers. Neither is an overall score.',
    'A robustness_paraphrase case has no defect by construction, so a flag on either '
    'variant is a false positive and not a detection.',
]


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _is_empty_span(span):
    return isinstance(span, dict) and set(span) == {'start', 'end'} and span == EMPTY_SPAN


def validate_evaluation(artifact):
    """Structural validation of a case set. Returns (cases_by_id, errors).

    No scientific judgment is made here. The only semantic claim checked is that a
    defect class declares a real defect substring located by an exact span, while a
    clean robustness class declares no defect at all.
    """
    errors = []
    if not isinstance(artifact, dict):
        return {}, ['counterfactual-evaluation must be a JSON object']
    if set(artifact) != set(EVALUATION_FIELDS):
        return {}, ['evaluation must have exactly ' + ', '.join(EVALUATION_FIELDS)]
    if artifact['schema'] != SCHEMAS['evaluation']:
        errors.append('evaluation schema must be ' + SCHEMAS['evaluation'])
    missing = artifact['missing_context']
    if not isinstance(missing, list) or any(not nonempty(x) for x in missing):
        errors.append('missing_context must be a list of non-empty strings')
    cases = artifact['cases']
    if not isinstance(cases, list) or not cases:
        return {}, errors + ['cases must be a non-empty list']
    cases_by_id = {}
    for case in cases:
        if not isinstance(case, dict) or set(case) != set(CASE_FIELDS):
            errors.append('case must have exactly ' + ', '.join(CASE_FIELDS))
            continue
        cid = case['id']
        if not nonempty(cid):
            errors.append('case id must be a non-empty string')
            continue
        if not nonempty(case['domain']):
            errors.append(cid + ': domain must be a non-empty string')
        cls = case['class']
        if cls not in ALL_CLASSES:
            errors.append(cid + ': class must be one of ' + ', '.join(ALL_CLASSES))
        for field in ('correct', 'faulty', 'paraphrase'):
            if not nonempty(case[field]):
                errors.append(cid + ': ' + field + ' must be non-empty text')
        if cls in ALL_CLASSES:
            errors.extend(_validate_defect(cid, case, cls))
        if cid in cases_by_id:
            errors.append(cid + ': duplicate case id')
            continue
        cases_by_id[cid] = case
    return cases_by_id, errors


def _validate_defect(cid, case, cls):
    defect, span, faulty = case['faulty_defect'], case['faulty_span'], case['faulty']
    if cls in DEFECT_CLASSES:
        if not nonempty(defect):
            return [cid + ': a defect class must declare a non-empty faulty_defect']
        if isinstance(faulty, str) and defect not in faulty:
            return [cid + ': faulty_defect is not a real substring of faulty']
        if not exact_span(faulty, span, defect):
            return [cid + ': faulty_span does not locate faulty_defect in faulty']
        return []
    errors = []
    if defect != '':
        errors.append(cid + ': ' + cls + ' must declare an empty faulty_defect')
    if not _is_empty_span(span):
        errors.append(cid + ': ' + cls + ' must declare faulty_span {start: 0, end: 0}')
    return errors


def validate_detection(artifact, evaluation, cases_by_id):
    """Structural validation of a supplied detection artifact. Returns (errors, detector)."""
    errors = []
    detector = None
    if not isinstance(artifact, dict):
        return ['invalid counterfactual-detection artifact: ' + str(artifact)], None
    if set(artifact) != set(DETECTION_FIELDS):
        return ['detection must have exactly ' + ', '.join(DETECTION_FIELDS)], None
    if artifact['schema'] != SCHEMAS['detection']:
        errors.append('detection schema must be ' + SCHEMAS['detection'])
    detector = artifact['detector']
    if not isinstance(detector, dict) or set(detector) != set(DETECTOR_FIELDS) \
            or any(not nonempty(detector[f]) for f in DETECTOR_FIELDS):
        errors.append('detector must have non-empty name, kind and description')
        detector = None
    if artifact['evaluation_digest'] != digest(evaluation):
        errors.append('detection was produced for a different evaluation artifact')
    results = artifact['results']
    if not isinstance(results, list):
        return errors + ['results must be a list'], detector
    reported = []
    for result in results:
        if not isinstance(result, dict) or not set(result) <= set(RESULT_FIELDS) \
                or any(f not in result for f in RESULT_REQUIRED_FIELDS):
            errors.append('result must have case_id, observed, detected_span and optional notes')
            continue
        cid = result['case_id']
        if cid not in cases_by_id:
            errors.append('result names an unknown case_id: ' + str(cid))
            continue
        if result['observed'] not in PAIR_OBSERVATIONS:
            errors.append(cid + ': observed must be one of ' + ', '.join(PAIR_OBSERVATIONS))
            continue
        reported.append(cid)
        case = cases_by_id[cid]
        text = case['correct'] if result['observed'] == 'false_positive' else case['faulty']
        span = result['detected_span']
        if span is not None:
            if not isinstance(span, dict) or set(span) != {'start', 'end'} \
                    or type(span.get('start')) is not int or type(span.get('end')) is not int \
                    or not 0 <= span['start'] < span['end'] <= len(text):
                errors.append(cid + ': detected_span is not a valid span of the reported variant')
        if 'notes' in result and not isinstance(result['notes'], str):
            errors.append(cid + ': notes must be a string')
    counts = Counter(reported)
    for cid, count in counts.items():
        if count > 1:
            errors.append(cid + ': reported more than once; every case must be reported exactly once')
    for cid in cases_by_id:
        if cid not in counts:
            errors.append(cid + ': no detection result; every case must be reported exactly once')
    return errors, detector


def _outcome_for(case, result):
    """Map one observation to an outcome under the class's expected verdict.

    A defect class expects the faulty variant to be flagged and is scored for recall.
    A clean robustness class expects both variants to stay clean, so a flag is a
    false positive and no defect location is expected.
    """
    observed = result['observed']
    if case['class'] in DEFECT_CLASSES:
        if observed == 'correct':
            if result['detected_span'] is not None \
                    and spans_overlap(result['detected_span'], case['faulty_span']):
                return 'detected'
            return 'location_failure'
        if observed == 'miss':
            return 'missed'
        if observed == 'false_positive':
            return 'false_positive'
        return 'uncertain'
    if observed == 'miss':
        return 'clean_rejection'
    if observed in ('correct', 'false_positive'):
        return 'false_positive'
    return 'uncertain'


def _counts(values, clean=False):
    counts = Counter(values)
    recall_den = counts['detected'] + counts['missed'] + counts['location_failure']
    overlap_den = counts['detected'] + counts['location_failure']
    rejection_den = counts['clean_rejection'] + counts['false_positive'] if clean else 0
    return {'structural': 'PASS',
            'cases': len(values),
            'detected': counts['detected'],
            'missed': counts['missed'] + counts['location_failure'],
            'location_failures': counts['location_failure'],
            'false_positives': counts['false_positive'],
            'uncertain': counts['uncertain'],
            'clean_rejections': counts['clean_rejection'],
            'detection_recall': round(counts['detected'] / recall_den, 4) if recall_den else None,
            'clean_rejection_accuracy':
                round(counts['clean_rejection'] / rejection_den, 4) if rejection_den else None,
            'location_overlap_accuracy':
                round(counts['detected'] / overlap_den, 4) if overlap_den else None}


def _tally(cases_by_id, detection):
    """Count outcomes per class, per class group and overall. Returns (counts, metrics, per_class, outcomes)."""
    reported = {r['case_id']: r for r in detection['results']}
    outcomes = {cid: _outcome_for(case, reported[cid])
                for cid, case in cases_by_id.items()}
    per_class, class_values = {}, {}
    for cid, case in cases_by_id.items():
        class_values.setdefault(case['class'], []).append(outcomes[cid])
    for name, values in class_values.items():
        per_class[name] = _counts(values, clean=name in CLEAN_CLASSES)
    defect_values = [o for cid, o in outcomes.items() if cases_by_id[cid]['class'] in DEFECT_CLASSES]
    clean_values = [o for cid, o in outcomes.items() if cases_by_id[cid]['class'] in CLEAN_CLASSES]
    counts = _counts(list(outcomes.values()))
    metrics = {'defect_classes': dict(_counts(defect_values),
                                      classes=[c for c in ALL_CLASSES if c in DEFECT_CLASSES]),
               'robustness_paraphrase': dict(_counts(clean_values, clean=True),
                                             classes=[c for c in CLEAN_CLASSES])}
    return counts, metrics, per_class, outcomes


def _impl(evaluation, detection=None):
    cases_by_id, eval_errors = validate_evaluation(evaluation)
    missing = evaluation.get('missing_context', []) if isinstance(evaluation, dict) else []
    reported_schema = evaluation.get('schema') if isinstance(evaluation, dict) else None
    result = {'status': 'INVALID', 'schema': SCHEMAS['evaluation'], 'case_set_digest': None,
              'structural': {'evaluation': {'schema': reported_schema, 'case_count': len(cases_by_id),
                                            'missing_context': missing if isinstance(missing, list) else [],
                                            'status': 'FAIL' if eval_errors else 'PASS',
                                            'errors': eval_errors},
                             'detection': None},
              'counts': None, 'metrics': None, 'per_class': {}, 'errors': list(eval_errors),
              'outcomes': {}, 'notes': [], 'limitations': list(LIMITATIONS)}
    if eval_errors:
        result['notes'].append('The case set is structurally invalid; no detection '
                               'measurement is computed and no science is judged.')
        return result
    result['case_set_digest'] = digest(evaluation)
    if detection is None:
        result['status'] = 'NEEDS_REVIEW'
        result['structural']['detection'] = {'status': 'NOT_SUPPLIED', 'errors': []}
        result['notes'].append('No detection artifact was supplied. This run validated '
                               'structure only; every defect and robustness class is '
                               'structurally checked, but semantic detection ability '
                               'remains unvalidated.')
        return result
    det_errors, detector = validate_detection(detection, evaluation, cases_by_id)
    structural_detection = {'status': 'FAIL' if det_errors else 'PASS', 'errors': det_errors,
                            'detector': detector,
                            'evaluation_digest': detection.get('evaluation_digest')
                            if isinstance(detection, dict) else None}
    result['structural']['detection'] = structural_detection
    if det_errors:
        result['status'] = 'FAIL'
        result['errors'].extend(det_errors)
        result['notes'].append('The supplied detection artifact is structurally invalid. '
                               'No accuracy is credited and no science is judged.')
        return result
    counts, metrics, per_class, outcomes = _tally(cases_by_id, detection)
    result['status'] = 'FAIL' if counts['false_positives'] else \
        'NEEDS_REVIEW' if (counts['missed'] or counts['uncertain'] or counts['location_failures']
                           or missing) else 'PASS'
    result['counts'] = counts
    result['metrics'] = metrics
    result['per_class'] = per_class
    result['outcomes'] = outcomes
    if counts['false_positives']:
        result['notes'].append('Verified false positives: the detector flagged a variant whose '
                               'scientific content is unchanged or already correct.')
    if counts['location_failures']:
        result['notes'].append('Location failures: the detector reported a defect but '
                               'detected_span does not overlap faulty_span, so the flag did '
                               'not find the declared defect and is counted as a miss.')
    if counts['missed']:
        result['notes'].append('Misses remain on defect cases, including reworded defects; '
                               'the detector did not locate every declared defect.')
    if counts['uncertain']:
        result['notes'].append('Uncertain results remain and keep this run at review.')
    if missing:
        result['notes'].append('missing_context is non-empty, so this run stays at review '
                               'regardless of the supplied detection.')
    result['notes'].append('Detection recall over ' +
                           str(metrics['defect_classes']['cases']) + ' defect cases and '
                           'clean-rejection accuracy over ' +
                           str(metrics['robustness_paraphrase']['cases']) + ' clean '
                           'robustness_paraphrase cases are reported separately. They are '
                           'not combined into one score.')
    if result['status'] == 'PASS':
        result['notes'].append('Every case is reported once and no false positive remains. '
                               'Even so, this PASS measures the supplied detector on THIS '
                               'case set only. It is not evidence about this skill\'s '
                               'semantic detection ability.')
    return result


def evaluate(evaluation, detection=None):
    """Public entry point. Validates artifacts; never runs a detector."""
    try:
        return _impl(evaluation, detection)
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        return {'status': 'FAIL',
                'errors': ['invalid counterfactual artifact: ' + str(exc)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evaluation', type=Path)
    parser.add_argument('--detection', type=Path,
                        help='separately produced counterfactual-detection@1 artifact')
    args = parser.parse_args()
    evaluation, detection = None, None
    try:
        evaluation = json.loads(args.evaluation.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        result = {'status': 'INVALID',
                  'errors': ['invalid counterfactual-evaluation artifact: ' + str(exc)]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 4
    if args.detection:
        try:
            detection = json.loads(args.detection.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError) as exc:
            detection = 'unparseable counterfactual-detection artifact: ' + str(exc)
    result = evaluate(evaluation, detection)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {'PASS': 0, 'FAIL': 3}.get(result['status'], 4)


if __name__ == '__main__':
    raise SystemExit(main())
