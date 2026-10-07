import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import diagnose_patterns as dp
import validate_suggestions as sb
from compare_invariants import digest


def bank_fixture(text='We measured error on Dataset A.', mode='suggest', category='narrative', severity='major'):
    coherence = {'status': 'PASS', 'findings': [], 'manuscript_digest': digest(text)}
    suggestion = {'id': 'S1', 'category': category, 'severity': severity, 'confidence': 'high',
                  'location': {'start': 0, 'end': len(text)}, 'original_span': text,
                  'diagnosis': 'Contribution visibility needs a real editorial choice.',
                  'why_it_matters': 'Readers should recover the supported contribution.',
                  'scientific_risk': 'low', 'recommended_action': 'Choose an information-order change.',
                  'alternatives': [{'id': 'A', 'option': 'Move the established problem constraint into the opening.',
                                    'tradeoff': 'Less space for background.', 'direction': 'move_constraint'},
                                   {'id': 'B', 'option': 'Keep the order and express tension in the final sentence.',
                                    'tradeoff': 'Contribution remains later.', 'direction': 'sharpen_tension'}],
                  'rule_refs': ['N1'], 'apply_by_default': False, 'source_finding_ids': []}
    bank = {'schema': 'manuscript-suggestions@1', 'manuscript_digest': digest(text), 'mode': mode,
            'coherence_digest': digest(coherence), 'short_diagnosis': 'Context-specific editorial diagnosis.',
            'reviewed_categories': list(sb.CATEGORIES), 'suggestions': [suggestion], 'keep_as_is': [],
            'quality_audit': None}
    refresh_quality(text, bank)
    return text, bank, coherence


def refresh_quality(text, bank):
    bank['quality_audit'] = {'manuscript_digest': digest(text), 'bank_digest': sb.bank_digest(bank),
                             'findings': [{'suggestion_id': s['id'], 'checks': {k: 'PASS' for k in sb.QUALITY_CHECKS}}
                                          for s in bank['suggestions']]}


class SuggestionTests(unittest.TestCase):
    def test_major_issue_has_two_distinct_options(self):
        args = bank_fixture()
        self.assertEqual(sb.validate(*args)['status'], 'PASS')
        args[1]['suggestions'][0]['alternatives'].pop()
        refresh_quality(args[0], args[1])
        self.assertEqual(sb.validate(*args)['status'], 'FAIL')

    def test_bank_needs_location_and_rationale(self):
        args = bank_fixture()
        args[1]['suggestions'][0]['why_it_matters'] = ''
        self.assertEqual(sb.validate(*args)['status'], 'FAIL')

    def test_high_risk_never_default_applies(self):
        args = bank_fixture(mode='revise')
        args[1]['suggestions'][0].update(scientific_risk='high', apply_by_default=True)
        refresh_quality(args[0], args[1])
        self.assertEqual(sb.validate(*args)['status'], 'FAIL')

    def test_good_prose_empty_bank_and_keep_as_is(self):
        text, bank, coherence = bank_fixture()
        bank['suggestions'] = []
        bank['keep_as_is'] = [{'location': {'start': 0, 'end': len(text)}, 'original_span': text,
                              'rationale': 'Already concrete, natural and scientifically accurate.'}]
        refresh_quality(text, bank)
        self.assertEqual(sb.validate(text, bank, coherence)['status'], 'PASS')
        self.assertFalse(dp.candidates(text)['candidates'])

    def test_synonym_and_quota_driven_edits_fail_quality_audit(self):
        for check in ('not_synonym_only', 'not_quota_driven'):
            text, bank, coherence = bank_fixture()
            bank['quality_audit']['findings'][0]['checks'][check] = 'FAIL'
            self.assertEqual(sb.validate(text, bank, coherence)['status'], 'FAIL')

    def test_identical_options_not_real_alternatives(self):
        text, bank, coherence = bank_fixture()
        bank['suggestions'][0]['alternatives'][1] = copy.deepcopy(bank['suggestions'][0]['alternatives'][0])
        refresh_quality(text, bank)
        self.assertEqual(sb.validate(text, bank, coherence)['status'], 'FAIL')

    def test_lexical_inflation_requires_contextual_suggestion(self):
        text = 'The utilization of this methodology facilitates enhancement.'
        _, bank, coherence = bank_fixture(text=text, category='language', severity='moderate')
        bank['suggestions'][0].update(diagnosis='Avoidable nominalization obscures the operation.',
                                     recommended_action='State the actual operation using its existing verb.', rule_refs=['L1', 'L6'])
        refresh_quality(text, bank)
        self.assertEqual(sb.validate(text, bank, coherence)['status'], 'PASS')
        self.assertEqual(dp.candidates('This novel method measures error.')['candidates'], [])

    def test_repeated_transition_is_weak_candidate(self):
        text = 'Furthermore, X is measured. Furthermore, Y is measured. Furthermore, Z is measured.'
        result = dp.candidates(text)
        self.assertIn('REPEATED_OPENING', [x['code'] for x in result['candidates']])
        self.assertTrue(all(x['requires_semantic_review'] for x in result['candidates']))

    def test_uniform_paragraphs_need_role_audit(self):
        text = '\n\n'.join('We measured the effect under this protocol. We interpreted the result within the stated scope.' for _ in range(4))
        self.assertIn('PARAGRAPH_SYMMETRY', [x['code'] for x in dp.candidates(text)['candidates']])

    def test_defensive_prose_functional_audit_preserves_limitation(self):
        for diagnosis in ('necessary calibration', 'optional hedge', 'redundant defensive language',
                          'claim weakening without evidence basis'):
            text, bank, coherence = bank_fixture(text='Replication remains untested.', category='defensive', severity='moderate')
            bank['suggestions'][0].update(diagnosis=diagnosis, scientific_risk='high', rule_refs=['H3'])
            refresh_quality(text, bank)
            self.assertEqual(sb.validate(text, bank, coherence)['status'], 'PASS')
            bank['mode'] = 'revise'
            refresh_quality(text, bank)
            with self.assertRaises(ValueError):
                sb.prepare_revision(text, bank, [{'suggestion_id': 'S1', 'option_id': 'A', 'replacement': ''}], coherence, True)

    def test_supported_result_not_auto_weakened_and_overclaim_rejected(self):
        for category in ('claims', 'defensive'):
            text, bank, coherence = bank_fixture(category=category)
            bank['quality_audit']['findings'][0]['checks']['calibrated_claim'] = 'FAIL'
            self.assertEqual(sb.validate(text, bank, coherence)['status'], 'FAIL')

    def test_author_profile_no_copied_sentences_and_explicit_rules_win(self):
        sample = 'We measured error. Replication remains untested.'
        result = dp.author_profile([sample], ['No prose colon.'])
        self.assertNotIn(sample, str(result))
        self.assertEqual(result['sample_digests'], [digest(sample)])
        self.assertIn('explicit user rules', result['rule_precedence'])
        self.assertEqual(dp.author_profile([])['profile_status'], 'unknown_without_samples')

    def test_optional_revision_requires_authorization_and_final_audit(self):
        text, bank, coherence = bank_fixture(text='It is important to note that we measured error.', mode='revise', category='language', severity='minor')
        choice = [{'suggestion_id': 'S1', 'option_id': 'A', 'replacement': 'We measured error.'}]
        with self.assertRaises(ValueError):
            sb.prepare_revision(text, bank, choice, coherence)
        result = sb.prepare_revision(text, bank, choice, coherence, authorized=True)
        self.assertEqual(result['status'], 'PROPOSED_NOT_AUDITED')
        self.assertEqual(result['revised_text'], 'We measured error.')
        self.assertEqual(text, 'It is important to note that we measured error.')

    def test_keep_as_is_cannot_be_touched(self):
        text, bank, coherence = bank_fixture(mode='revise')
        bank['keep_as_is'] = [{'location': {'start': 0, 'end': len(text)}, 'original_span': text, 'rationale': 'Good prose.'}]
        refresh_quality(text, bank)
        with self.assertRaisesRegex(ValueError, 'Keep as is'):
            sb.prepare_revision(text, bank, [{'suggestion_id': 'S1', 'option_id': 'A', 'replacement': 'Changed.'}], coherence, True)

    def test_unknown_quality_and_missing_coherence_needs_review(self):
        text, bank, coherence = bank_fixture()
        bank['quality_audit']['findings'][0]['checks']['preserves_voice'] = 'UNKNOWN'
        self.assertEqual(sb.validate(text, bank, coherence)['status'], 'NEEDS_REVIEW')
        self.assertEqual(sb.validate(text, bank)['status'], 'NEEDS_REVIEW')


if __name__ == '__main__':
    unittest.main()
