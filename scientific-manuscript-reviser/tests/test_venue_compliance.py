"""Adversarial tests for submission compliance (submission_compliance.py).

Compliance is reported separately from science, and a check only fires for the
profile that actually states it. These tests attack that scoping and the
safe-failure rules:

  * a wrong venue/year/track profile never produces a compliance PASS,
  * a data/code-release requirement fires only for its own profile scope,
  * a LaTeX source length is never used as a page count,
  * AI-use disclosure is cross-checked against supplied records, never inferred.

Layering note: ``SemanticEvaluationTests`` use constructed correct/faulty
manifests to enforce the protocol. A PASS here means the stated, checkable
requirement was verified; it does not mean the submission is acceptable.
"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import submission_compliance as sc

DATA_CHECK = {'id': 'C-DATA', 'requirement': 'Release code and data artifacts',
              'mechanically_checkable': True, 'check_kind': 'declaration', 'source_id': 's1'}
PAGE_CHECK = {'id': 'C-PAGES', 'requirement': 'Main text is limited to 9 pages',
              'mechanically_checkable': True, 'check_kind': 'page_limit', 'source_id': 's1'}
AI_CHECK = {'id': 'C-AI', 'requirement': 'Disclose LLM use in the paper',
            'mechanically_checkable': True, 'check_kind': 'declaration', 'source_id': 's1'}


def pdf_bytes(pages):
    return ('%%PDF-1.4\n1 0 obj\n<</Type /Pages /Count %d>>\nendobj\n' % pages).encode('ascii')


def profile(venue='NeurIPS', year=2025, track='main', checks=(DATA_CHECK, PAGE_CHECK)):
    return {'schema': 'venue-policy-profile@1', 'profile_version': 1, 'venue': venue,
            'year': year, 'track': track, 'verification_date': '2025-05-01',
            'sources': [], 'contribution_types': [], 'review_criteria': [],
            'mandatory_policy': [], 'recommended_practice': [],
            'compliance_checks': list(checks), 'changes_from_prior_year': [],
            'unknown_policies': []}


class ComplianceTestBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        self.source = self.root / 'paper.tex'
        self.source.write_text('\\documentclass{article}\n', encoding='utf-8')
        self.pdf = self.root / 'paper.pdf'
        self.pdf.write_bytes(pdf_bytes(9))
        self.overlong_pdf = self.root / 'long.pdf'
        self.overlong_pdf.write_bytes(pdf_bytes(12))

    def manifest(self, venue='NeurIPS', year=2025, track='main', declarations=None,
                 compiled=None, source=None, records=None):
        return {'schema': 'submission-manifest@1', 'venue': venue, 'year': year, 'track': track,
                'source_path': str(self.source if source is None else source),
                'compiled_path': None if compiled is None else str(compiled),
                'declarations': {} if declarations is None else declarations,
                'ai_use_records': [] if records is None else records}


class DeterministicTests(ComplianceTestBase):
    def test_clean_declaration_compliance_reaches_pass(self):
        result = sc.check(self.manifest(declarations={'code_release': 'PRESENT',
                                                      'data_availability': 'PRESENT'},
                                        compiled=self.pdf),
                          profile(checks=(DATA_CHECK,)))
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['errors'], [])
        self.assertFalse(result['venue_neutral'])

    def test_page_limit_within_limit_passes(self):
        result = sc.check(self.manifest(compiled=self.pdf), profile(checks=(PAGE_CHECK,)))
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['checks'][0]['status'], 'PASS')
        self.assertEqual(result['page_count'], 9)

    def test_pdf_page_count_reads_the_page_tree(self):
        self.assertEqual(sc.pdf_page_count(self.pdf), 9)
        self.assertEqual(sc.pdf_page_count(self.overlong_pdf), 12)

    def test_venue_neutral_compliance_is_the_documented_needs_review(self):
        result = sc.check(self.manifest(), None)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(result['venue_neutral'])
        self.assertEqual(result['checks'], [])

    def test_manifest_json_round_trip_keeps_the_verdict(self):
        result = sc.check(self.manifest(compiled=self.pdf), profile(checks=(PAGE_CHECK,)))
        self.assertEqual(json.loads(json.dumps(result))['status'], 'PASS')


class ScopingTests(ComplianceTestBase):
    def test_code_release_requirement_only_fires_for_its_own_profile(self):
        with_requirement = sc.check(self.manifest(declarations={'code_release': 'PRESENT'}),
                                    profile(venue='NeurIPS', checks=(DATA_CHECK,)))
        self.assertIn('C-DATA', [c['id'] for c in with_requirement['checks']])
        self.assertEqual(with_requirement['status'], 'PASS')

        without_requirement = sc.check(self.manifest(declarations={'code_release': 'PRESENT'}),
                                       profile(venue='NeurIPS', checks=(PAGE_CHECK,)))
        self.assertNotIn('C-DATA', [c['id'] for c in without_requirement['checks']])

    def test_another_venues_requirement_never_appears(self):
        # Same venue/year/track as the manifest, but a profile that states no data rule.
        cvpr = sc.check(self.manifest(venue='CVPR', declarations={'code_release': 'ABSENT'}),
                        profile(venue='CVPR', checks=()))
        self.assertEqual(cvpr['status'], 'PASS')
        self.assertEqual(cvpr['checks'], [])

    def test_wrong_venue_profile_never_produces_a_pass(self):
        result = sc.check(self.manifest(venue='NeurIPS'),
                          profile(venue='ICML', checks=(DATA_CHECK,)))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('venue does not match the cited profile scope' in e
                            for e in result['errors']))

    def test_wrong_year_profile_never_produces_a_pass(self):
        result = sc.check(self.manifest(venue='NeurIPS', year=2025),
                          profile(venue='NeurIPS', year=2024, checks=(DATA_CHECK,)))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('year does not match the cited profile scope' in e
                            for e in result['errors']))

    def test_wrong_track_profile_never_produces_a_pass(self):
        result = sc.check(self.manifest(venue='NeurIPS', track='main'),
                          profile(venue='NeurIPS', track='workshop', checks=(DATA_CHECK,)))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('track does not match the cited profile scope' in e
                            for e in result['errors']))


class PageCountTests(ComplianceTestBase):
    def test_missing_compiled_document_stays_needs_review(self):
        result = sc.check(self.manifest(compiled=None), profile(checks=(PAGE_CHECK,)))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertIsNone(result['page_count'])
        entry = [c for c in result['checks'] if c['id'] == 'C-PAGES'][0]
        self.assertEqual(entry['status'], 'NEEDS_REVIEW')
        self.assertIsNone(entry['measured_pages'])
        self.assertTrue(any('no compiled document supplied' in u for u in result['unresolved']))

    def test_latex_source_is_not_a_page_count(self):
        result = sc.check(self.manifest(compiled=self.source), profile(checks=(PAGE_CHECK,)))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertIsNone(sc.pdf_page_count(self.source))

    def test_page_limit_violation_fails(self):
        result = sc.check(self.manifest(compiled=self.overlong_pdf), profile(checks=(PAGE_CHECK,)))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('limit is 9' in e for e in result['errors']))

    def test_unparseable_page_requirement_stays_needs_review(self):
        vague = dict(PAGE_CHECK, requirement='Respect the official main-text limit')
        result = sc.check(self.manifest(compiled=self.pdf), profile(checks=(vague,)))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(any('could not be parsed' in u for u in result['unresolved']))


class DeclarationTests(ComplianceTestBase):
    def test_absent_mechanically_checkable_declaration_fails(self):
        result = sc.check(self.manifest(declarations={'code_release': 'ABSENT'}),
                          profile(checks=(DATA_CHECK,)))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('required declaration is absent' in e for e in result['errors']))

    def test_unknown_declaration_stays_needs_review(self):
        result = sc.check(self.manifest(declarations={}), profile(checks=(DATA_CHECK,)))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(any('is not recorded' in u for u in result['unresolved']))

    def test_author_declared_not_applicable_passes_as_stated(self):
        # The gate reports the author's declaration; it does not verify the claim.
        result = sc.check(self.manifest(declarations={'code_release': 'NOT_APPLICABLE'}),
                          profile(checks=(DATA_CHECK,)))
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['checks'][0]['why'], 'declared not applicable by the author')

    def test_ai_use_disclosure_is_never_inferred(self):
        result = sc.check(self.manifest(declarations={'ai_use_disclosure': 'UNKNOWN'},
                                        compiled=self.pdf),
                          profile(checks=(AI_CHECK,)))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertNotEqual(result['status'], 'PASS')
        self.assertTrue(any('does not infer a usage history' in u for u in result['unresolved']))

    def test_not_disclosed_ai_record_fails(self):
        result = sc.check(self.manifest(declarations={'ai_use_disclosure': 'PRESENT'},
                                        compiled=self.pdf,
                                        records=[{'tool': 'assistant', 'purpose': 'drafting',
                                                  'status': 'NOT_DISCLOSED'}]),
                          profile(checks=(AI_CHECK,)))
        self.assertEqual(result['status'], 'FAIL')

    def test_disclosed_ai_record_passes(self):
        result = sc.check(self.manifest(declarations={'ai_use_disclosure': 'PRESENT'},
                                        compiled=self.pdf,
                                        records=[{'tool': 'assistant', 'purpose': 'drafting',
                                                  'status': 'DISCLOSED'}]),
                          profile(checks=(AI_CHECK,)))
        self.assertEqual(result['status'], 'PASS')


class ContractTests(ComplianceTestBase):
    def test_unknown_manifest_field_is_rejected(self):
        manifest = self.manifest()
        manifest['reviewer_score'] = 9
        result = sc.check(manifest, profile())
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('invalid compliance manifest fields' in e
                            for e in result['errors']))

    def test_unknown_declaration_topic_is_rejected(self):
        result = sc.check(self.manifest(declarations={'cover_letter': 'PRESENT'}),
                          profile(checks=()))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('unknown declaration topic' in e for e in result['errors']))

    def test_invalid_declaration_state_is_rejected(self):
        result = sc.check(self.manifest(declarations={'code_release': 'MAYBE'}),
                          profile(checks=()))
        self.assertEqual(result['status'], 'FAIL')

    def test_missing_source_path_is_rejected(self):
        result = sc.check(self.manifest(source=self.root / 'absent.tex'), profile(checks=()))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('does not resolve to a file' in e for e in result['errors']))

    def test_invalid_ai_record_is_rejected(self):
        result = sc.check(self.manifest(compiled=self.pdf,
                                        records=[{'tool': 'x', 'purpose': 'y',
                                                  'status': 'PROBABLY'}]),
                          profile(checks=()))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('invalid AI-use record' in e for e in result['errors']))


class EndToEndTests(ComplianceTestBase):
    def test_two_profiles_produce_independent_check_sets(self):
        neurips = sc.check(self.manifest(venue='NeurIPS', compiled=self.pdf,
                                         declarations={'code_release': 'PRESENT'}),
                           profile(venue='NeurIPS', checks=(DATA_CHECK, PAGE_CHECK)))
        cvpr = sc.check(self.manifest(venue='CVPR', compiled=self.overlong_pdf,
                                      declarations={}),
                        profile(venue='CVPR', checks=(PAGE_CHECK,)))
        self.assertEqual(neurips['status'], 'PASS')
        self.assertEqual(cvpr['status'], 'FAIL')
        self.assertEqual([c['id'] for c in cvpr['checks']], ['C-PAGES'])

    def test_scope_is_reported_in_the_result(self):
        result = sc.check(self.manifest(), profile())
        self.assertEqual(result['venue_scope'], {'venue': 'NeurIPS', 'year': 2025,
                                                 'track': 'main'})


if __name__ == '__main__':
    unittest.main()
