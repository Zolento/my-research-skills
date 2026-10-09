import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import counterfactual_eval as cf
import evidence_core as core


def make_case(cid, cls, faulty, defect, correct=None, domain='test domain', paraphrase=None):
    correct = correct if correct is not None else 'A clean baseline statement for ' + cid + '.'
    paraphrase = paraphrase if paraphrase is not None else \
        'A wording-only variant of the baseline statement for ' + cid + '.'
    start = faulty.index(defect)
    return {'id': cid, 'class': cls, 'domain': domain, 'correct': correct, 'faulty': faulty,
            'faulty_defect': defect, 'faulty_span': {'start': start, 'end': start + len(defect)},
            'paraphrase': paraphrase}


def clean_case(cid, correct=None, faulty=None, paraphrase=None, domain='test domain'):
    correct = correct if correct is not None else 'The model achieved 0.86 AUC on the test set.'
    faulty = faulty if faulty is not None else 'On the test set the model achieved 0.86 AUC.'
    paraphrase = paraphrase if paraphrase is not None else \
        'On the test set, the model achieved an AUC of 0.86.'
    return {'id': cid, 'class': 'robustness_paraphrase', 'domain': domain, 'correct': correct,
            'faulty': faulty, 'faulty_defect': '', 'faulty_span': {'start': 0, 'end': 0},
            'paraphrase': paraphrase}


def evaluation(cases, missing_context=None):
    return {'schema': core.SCHEMAS['evaluation'], 'cases': cases,
            'missing_context': missing_context or []}


def base_cases():
    return [make_case('d1', 'causal_overreach', 'The treatment causes the outcome.',
                      'causes the outcome'),
            make_case('d2', 'evidence_mismatch', 'The table reports a different cohort.',
                      'different cohort'),
            make_case('rdr1', 'robustness_defect_rewording',
                      'Reworded sentence: the treatment causes the outcome.',
                      'causes the outcome'),
            clean_case('rp1')]


def detection_for(ev, results, detector=None):
    return {'schema': core.SCHEMAS['detection'],
            'detector': detector or {'name': 'test-detector', 'kind': 'fixture',
                                     'description': 'Test fixture only.'},
            'evaluation_digest': core.digest(ev), 'results': results}


def perfect_detection(ev):
    results = []
    for case in ev['cases']:
        if case['class'] in core.DEFECT_CLASSES:
            results.append({'case_id': case['id'], 'observed': 'correct',
                            'detected_span': dict(case['faulty_span'])})
        else:
            results.append({'case_id': case['id'], 'observed': 'miss', 'detected_span': None})
    return detection_for(ev, results)


def set_result(det, cid, **changes):
    for result in det['results']:
        if result['case_id'] == cid:
            result.update(changes)
            return det
    raise AssertionError('no result for ' + cid)


class CounterfactualTests(unittest.TestCase):
    def test_valid_evaluation_without_detection_needs_review(self):
        ev = evaluation(base_cases())
        result = cf.evaluate(ev)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['structural']['evaluation']['status'], 'PASS')
        self.assertEqual(result['structural']['evaluation']['case_count'], 4)
        self.assertEqual(result['structural']['detection']['status'], 'NOT_SUPPLIED')
        self.assertIsNone(result['counts'])
        self.assertIn('semantic detection ability remains unvalidated', ' '.join(result['notes']))

    def test_fully_correct_detection_passes(self):
        ev = evaluation(base_cases())
        result = cf.evaluate(ev, perfect_detection(ev))
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['structural']['detection']['status'], 'PASS')
        self.assertEqual(result['counts']['detected'], 3)
        self.assertEqual(result['counts']['missed'], 0)
        self.assertEqual(result['counts']['false_positives'], 0)
        self.assertEqual(result['counts']['clean_rejections'], 1)

    def test_missing_context_forces_review_even_with_perfect_detection(self):
        ev = evaluation(base_cases(), missing_context=['ethics approval record not supplied'])
        result = cf.evaluate(ev, perfect_detection(ev))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertIn('missing_context is non-empty', ' '.join(result['notes']))

    def test_miss_keeps_review(self):
        ev = evaluation(base_cases())
        det = set_result(perfect_detection(ev), 'd1', observed='miss', detected_span=None)
        result = cf.evaluate(ev, det)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['counts']['missed'], 1)
        self.assertEqual(result['counts']['detected'], 2)

    def test_false_positive_fails(self):
        ev = evaluation(base_cases())
        det = set_result(perfect_detection(ev), 'd2', observed='false_positive',
                         detected_span={'start': 0, 'end': 3})
        result = cf.evaluate(ev, det)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['counts']['false_positives'], 1)

    def test_robustness_paraphrase_flag_is_a_false_positive(self):
        ev = evaluation(base_cases())
        det = set_result(perfect_detection(ev), 'rp1', observed='correct',
                         detected_span={'start': 0, 'end': 3})
        result = cf.evaluate(ev, det)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['outcomes']['rp1'], 'false_positive')
        self.assertEqual(result['metrics']['robustness_paraphrase']['clean_rejection_accuracy'], 0.0)

    def test_nonoverlapping_span_is_counted_as_a_miss(self):
        ev = evaluation(base_cases())
        det = set_result(perfect_detection(ev), 'd1', observed='correct',
                         detected_span={'start': 0, 'end': 2})
        result = cf.evaluate(ev, det)
        self.assertEqual(result['outcomes']['d1'], 'location_failure')
        self.assertEqual(result['counts']['location_failures'], 1)
        self.assertEqual(result['counts']['missed'], 1)
        self.assertEqual(result['counts']['detected'], 2)
        self.assertEqual(result['per_class']['causal_overreach']['location_overlap_accuracy'], 0.0)
        self.assertEqual(result['counts']['detection_recall'], round(2 / 3, 4))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_duplicate_and_missing_coverage_are_errors(self):
        ev = evaluation(base_cases())
        det = perfect_detection(ev)
        det['results'].append(copy.deepcopy(det['results'][0]))
        result = cf.evaluate(ev, det)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('reported more than once', ' '.join(result['errors']))
        det = perfect_detection(ev)
        det['results'] = det['results'][:-1]
        result = cf.evaluate(ev, det)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('no detection result', ' '.join(result['errors']))

    def test_unknown_case_id_is_an_error(self):
        ev = evaluation(base_cases())
        det = perfect_detection(ev)
        det['results'].append({'case_id': 'ghost', 'observed': 'correct',
                               'detected_span': {'start': 0, 'end': 1}})
        result = cf.evaluate(ev, det)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('unknown case_id', ' '.join(result['errors']))

    def test_stale_evaluation_digest_fails(self):
        ev = evaluation(base_cases())
        det = perfect_detection(ev)
        det['evaluation_digest'] = 'deadbeef'
        result = cf.evaluate(ev, det)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('different evaluation artifact', ' '.join(result['errors']))

    def test_robustness_defect_rewording_is_scored_for_detection(self):
        self.assertIn('robustness_defect_rewording', core.DEFECT_CLASSES)
        ev = evaluation(base_cases())
        det = set_result(perfect_detection(ev), 'rdr1', observed='miss', detected_span=None)
        result = cf.evaluate(ev, det)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['outcomes']['rdr1'], 'missed')
        self.assertEqual(result['counts']['missed'], 1)
        self.assertEqual(result['metrics']['defect_classes']['cases'], 3)
        self.assertEqual(result['metrics']['defect_classes']['detection_recall'], round(2 / 3, 4))

    def test_robustness_defect_rewording_pairing_holds(self):
        clean = 'On the held-out split, the augmentation is associated with a 3 point gain.'
        case = make_case('rdr', 'robustness_defect_rewording',
                         'In a differently worded sentence, the augmentation improves quality by 3 points.',
                         'improves quality by 3 points', correct=clean, paraphrase=clean)
        self.assertEqual(case['paraphrase'], case['correct'])
        self.assertIn(case['faulty_defect'], case['faulty'])
        start, end = case['faulty_span']['start'], case['faulty_span']['end']
        self.assertEqual(case['faulty'][start:end], case['faulty_defect'])
        self.assertGreater(end, start)
        self.assertIn(case['class'], core.DEFECT_CLASSES)

    def test_robustness_paraphrase_empty_defect_validates(self):
        ev = evaluation([clean_case('rp1')])
        result = cf.evaluate(ev)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['structural']['evaluation']['status'], 'PASS')
        case = ev['cases'][0]
        self.assertEqual(case['faulty_defect'], '')
        self.assertEqual(case['faulty_span'], {'start': 0, 'end': 0})

    def test_nonempty_defect_on_robustness_paraphrase_is_rejected(self):
        bad = clean_case('rp1')
        bad['faulty_defect'] = '0.86'
        bad['faulty_span'] = {'start': bad['faulty'].index('0.86'),
                              'end': bad['faulty'].index('0.86') + len('0.86')}
        result = cf.evaluate(evaluation([bad]))
        self.assertEqual(result['status'], 'INVALID')
        self.assertIn('must declare an empty faulty_defect', ' '.join(result['errors']))

    def test_nonzero_span_on_robustness_paraphrase_is_rejected(self):
        bad = clean_case('rp1')
        bad['faulty_span'] = {'start': 0, 'end': 4}
        result = cf.evaluate(evaluation([bad]))
        self.assertEqual(result['status'], 'INVALID')
        self.assertIn('faulty_span {start: 0, end: 0}', ' '.join(result['errors']))

    def test_clean_robustness_class_with_matching_texts_still_valid(self):
        ev = evaluation([clean_case('rp1', faulty='The test set gave 0.86 AUC.',
                                    paraphrase='The test set gave 0.86 AUC.')])
        self.assertEqual(cf.evaluate(ev)['structural']['evaluation']['status'], 'PASS')

    def test_defect_classes_require_a_real_defect(self):
        for cls in ('causal_overreach', 'robustness_defect_rewording'):
            with self.subTest(cls=cls):
                bad = make_case('x', cls, 'A plainly clean sentence.', 'clean sentence')
                bad.update(faulty_defect='', faulty_span={'start': 0, 'end': 0})
                result = cf.evaluate(evaluation([bad]))
                self.assertEqual(result['status'], 'INVALID')
                self.assertIn('non-empty faulty_defect', ' '.join(result['errors']))

    def test_faulty_defect_must_be_a_real_substring(self):
        cases = base_cases()
        cases[0]['faulty_defect'] = 'causes a different outcome'
        result = cf.evaluate(evaluation(cases))
        self.assertEqual(result['status'], 'INVALID')
        self.assertIn('not a real substring of faulty', ' '.join(result['errors']))

    def test_faulty_span_must_locate_the_defect(self):
        cases = base_cases()
        cases[0]['faulty_span'] = {'start': 0, 'end': 3}
        result = cf.evaluate(evaluation(cases))
        self.assertEqual(result['status'], 'INVALID')
        self.assertIn('does not locate faulty_defect', ' '.join(result['errors']))

    def test_invalid_class_enum_and_empty_domain_are_invalid(self):
        cases = base_cases()
        cases[0]['class'] = 'wordiness'
        result = cf.evaluate(evaluation(cases))
        self.assertEqual(result['status'], 'INVALID')
        self.assertIn('class must be one of', ' '.join(result['errors']))
        cases = base_cases()
        cases[0]['domain'] = '   '
        result = cf.evaluate(evaluation(cases))
        self.assertEqual(result['status'], 'INVALID')
        self.assertIn('domain must be a non-empty string', ' '.join(result['errors']))

    def test_duplicate_case_id_is_invalid(self):
        cases = base_cases()
        cases.append(copy.deepcopy(cases[0]))
        result = cf.evaluate(evaluation(cases))
        self.assertEqual(result['status'], 'INVALID')
        self.assertIn('duplicate case id', ' '.join(result['errors']))

    def test_metrics_are_reported_separately(self):
        ev = evaluation(base_cases())
        result = cf.evaluate(ev, perfect_detection(ev))
        self.assertEqual(set(result['metrics']), {'defect_classes', 'robustness_paraphrase'})
        defect = result['metrics']['defect_classes']
        clean = result['metrics']['robustness_paraphrase']
        self.assertEqual(defect['detection_recall'], 1.0)
        self.assertIsNone(defect['clean_rejection_accuracy'])
        self.assertIsNone(clean['detection_recall'])
        self.assertEqual(clean['clean_rejection_accuracy'], 1.0)
        self.assertIn('robustness_defect_rewording', defect['classes'])
        self.assertNotIn('robustness_paraphrase', defect['classes'])
        for merged in ('correct_rejections', 'accuracy', 'overall_accuracy', 'score'):
            self.assertNotIn(merged, result['counts'])
        self.assertNotIn('correct_rejections', result['metrics']['robustness_paraphrase'])
        self.assertIn('clean_rejections', result['counts'])

    def test_invalid_detection_structure_fails(self):
        ev = evaluation(base_cases())
        for mutate in (lambda d: d.pop('schema'),
                       lambda d: d.update(schema='counterfactual-detection@9'),
                       lambda d: d.update(detector={'name': 'x'}),
                       lambda d: d.update(results='not-a-list')):
            det = perfect_detection(ev)
            mutate(det)
            with self.subTest(mutation=str(mutate)):
                self.assertEqual(cf.evaluate(ev, det)['status'], 'FAIL')

    def test_optimistic_all_correct_artifact_is_not_clean(self):
        ev = json.loads((ROOT / 'examples/counterfactual/evaluation.json').read_text())
        optimistic = json.loads((ROOT / 'examples/counterfactual/optimistic-detection.json').read_text())
        result = cf.evaluate(ev, optimistic)
        defect_cases = sum(c['class'] in core.DEFECT_CLASSES for c in ev['cases'])
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['counts']['detected'], 0)
        self.assertEqual(result['counts']['location_failures'], defect_cases)
        self.assertEqual(result['metrics']['defect_classes']['location_overlap_accuracy'], 0.0)
        self.assertEqual(result['metrics']['defect_classes']['detection_recall'], 0.0)
        self.assertEqual(result['metrics']['robustness_paraphrase']['clean_rejection_accuracy'], 0.0)
        # Even restricted to defect cases, a wrong span never yields a clean recall.
        defect_only = evaluation([c for c in ev['cases'] if c['class'] in core.DEFECT_CLASSES])
        det = [{'case_id': c['id'], 'observed': 'correct', 'detected_span': {'start': 0, 'end': 1}}
               for c in defect_only['cases']]
        result = cf.evaluate(defect_only, detection_for(defect_only, det))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['metrics']['defect_classes']['detection_recall'], 0.0)
        self.assertEqual(result['counts']['detected'], 0)

    def test_bundled_example_without_detection(self):
        ev = json.loads((ROOT / 'examples/counterfactual/evaluation.json').read_text())
        result = cf.evaluate(ev)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['structural']['evaluation']['status'], 'PASS')
        self.assertEqual(result['structural']['evaluation']['case_count'], 11)

    def test_bundled_example_with_illustrative_detection(self):
        ev = json.loads((ROOT / 'examples/counterfactual/evaluation.json').read_text())
        det = json.loads((ROOT / 'examples/counterfactual/detection.json').read_text())
        self.assertEqual(det['evaluation_digest'], core.digest(ev))
        result = cf.evaluate(ev, det)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        counts = result['counts']
        self.assertEqual((counts['detected'], counts['missed'], counts['location_failures'],
                          counts['false_positives'], counts['uncertain'],
                          counts['clean_rejections']), (7, 2, 1, 0, 0, 2))
        self.assertEqual(result['metrics']['defect_classes']['detection_recall'], round(7 / 9, 4))
        self.assertEqual(result['metrics']['robustness_paraphrase']['clean_rejection_accuracy'], 1.0)
        self.assertEqual(result['per_class']['robustness_defect_rewording']['detected'], 2)
        self.assertEqual(result['per_class']['robustness_paraphrase']['clean_rejections'], 2)
        self.assertEqual(result['per_class']['robustness_paraphrase']['false_positives'], 0)

    def test_example_covers_all_classes_and_variant_rules(self):
        ev = json.loads((ROOT / 'examples/counterfactual/evaluation.json').read_text())
        classes = {c['class'] for c in ev['cases']}
        for cls in core.FAULTY_CLASSES:
            self.assertIn(cls, classes)
        self.assertGreaterEqual(sum(c['class'] == 'robustness_paraphrase' for c in ev['cases']), 2)
        self.assertGreaterEqual(sum(c['class'] == 'robustness_defect_rewording' for c in ev['cases']), 2)
        for case in ev['cases']:
            if case['class'] in core.DEFECT_CLASSES:
                self.assertIn(case['faulty_defect'], case['faulty'])
                self.assertEqual(
                    case['faulty'][case['faulty_span']['start']:case['faulty_span']['end']],
                    case['faulty_defect'])
                self.assertGreater(case['faulty_span']['end'], case['faulty_span']['start'])
            else:
                self.assertEqual(case['faulty_defect'], '')
                self.assertEqual(case['faulty_span'], {'start': 0, 'end': 0})
            self.assertNotEqual(case['correct'], case['faulty'])
        for cid in ('rdr-mechanism-10', 'rdr-generalization-11'):
            case = next(c for c in ev['cases'] if c['id'] == cid)
            self.assertIn(case['class'], core.DEFECT_CLASSES)
            self.assertEqual(case['paraphrase'], case['correct'])

    def test_module_exposes_no_auto_detection_entry_point(self):
        public = {name for name in dir(cf) if not name.startswith('_')
                  and callable(getattr(cf, name)) and getattr(cf, name).__module__ == cf.__name__}
        self.assertEqual(public, {'nonempty', 'validate_evaluation', 'validate_detection',
                                  'evaluate', 'main'})
        banned = {'detect', 'classify', 'predict', 'run_detector', 'score_manuscript',
                  'detect_defect', 'classify_manuscript'}
        self.assertEqual(banned & {name.lower() for name in dir(cf)}, set())
        source = (ROOT / 'scripts/counterfactual_eval.py').read_text()
        for word in ('import re', 're.compile', 're.search', 're.finditer'):
            self.assertNotIn(word, source)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = pathlib.Path(self.temp.name)

    def write(self, name, value):
        path = self.dir / name
        path.write_text(value if isinstance(value, str) else json.dumps(value))
        return str(path)

    def run_cli(self, *args):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'counterfactual_eval.py'), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.stderr, '')
        return result.returncode, json.loads(result.stdout)

    def test_exit_codes_for_pass_fail_review_and_invalid(self):
        ev = evaluation(base_cases())
        ev_path = self.write('evaluation.json', ev)
        code, output = self.run_cli(ev_path)
        self.assertEqual((code, output['status']), (4, 'NEEDS_REVIEW'))
        perfect = self.write('perfect.json', perfect_detection(ev))
        code, output = self.run_cli(ev_path, '--detection', perfect)
        self.assertEqual((code, output['status']), (0, 'PASS'))
        fp = perfect_detection(ev)
        set_result(fp, 'd1', observed='false_positive', detected_span={'start': 0, 'end': 3})
        code, output = self.run_cli(ev_path, '--detection', self.write('fp.json', fp))
        self.assertEqual((code, output['status']), (3, 'FAIL'))
        code, output = self.run_cli(self.write('broken.json', '{'))
        self.assertEqual((code, output['status']), (4, 'INVALID'))

    def test_malformed_detection_file_fails_not_certifies(self):
        ev = evaluation(base_cases())
        ev_path = self.write('evaluation.json', ev)
        code, output = self.run_cli(ev_path, '--detection', self.write('bad-detection.json', '{'))
        self.assertEqual((code, output['status']), (3, 'FAIL'))
        self.assertIn('invalid counterfactual-detection artifact', ' '.join(output['errors']))


if __name__ == '__main__':
    unittest.main()
