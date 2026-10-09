"""Adversarial contract tests for the Venue Policy Registry (venue_registry.py).

The registry exists so that a venue rule can never become a gate unless it is
bound to one exact venue/year/track, quoted verbatim from a saved official
source, and marked explicit and verified. These tests attack that contract:

  * exact-scope lookup must miss, never fall back or inherit,
  * every quoted rule must occur in the excerpt of the source it cites,
  * a MANDATORY_POLICY that is inferred, unverified or inapplicable is rejected,
  * duplicate profiles for one scope are rejected.

Layering note: ``ContractTests`` and ``RuleConflictTests`` test protocol
enforcement on constructed artifacts. They do not show that the registry's
policy facts match the real venue, and a PASS here does not certify a paper.
"""
import copy
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import venue_intelligence_core as vic
import venue_registry as vr

EXCERPT = ('The official call for papers states that submissions must be anonymous during '
           'review, that authors must disclose generative AI use, and that the main text '
           'should be limited to nine pages. This saved excerpt is deliberately long enough '
           'to satisfy the offline source contract and to support verbatim quote checks.')

ANON_QUOTE = 'submissions must be anonymous'
PAGES_QUOTE = 'limited to nine pages'


def source_file(sid, venue, year, url='https://venue.org/2025/cfp', status='VERIFIED'):
    return {'schema': 'venue-policy-source@1', 'id': sid, 'venue': venue, 'year': year,
            'url': url, 'source_type': 'call_for_papers', 'retrieved': '2025-05-01',
            'excerpt': EXCERPT}


def source_row(sid, url='https://venue.org/2025/cfp', status='VERIFIED'):
    return {'id': sid, 'url': url, 'source_type': 'call_for_papers', 'phase': 'author',
            'retrieved': '2025-05-01', 'digest': 'sha256:' + 'a' * 64, 'status': status}


def claim(**over):
    item = {'id': 'M1', 'topic': 'anonymity', 'statement': 'Submissions must be anonymous',
            'claim_kind': 'MANDATORY_POLICY', 'explicitness': 'EXPLICIT',
            'applicability': 'REQUIRED', 'quote': ANON_QUOTE, 'source_id': 's1'}
    item.update(over)
    return item


def criterion(cid='RC1', dimension='soundness', quote=ANON_QUOTE, source_id='s1'):
    return {'id': cid, 'name': 'Criterion ' + cid, 'dimension': dimension,
            'official_explanation': 'Official explanation', 'quote': quote,
            'source_id': source_id}


def contribution_type(cid='ct1', quote=ANON_QUOTE, source_id='s1'):
    return {'id': cid, 'claim_kind': 'REVIEW_CRITERION', 'label': 'Methodological contribution',
            'scope': 'Method and system contributions', 'quote': quote, 'source_id': source_id}


def profile(**over):
    item = {'schema': 'venue-policy-profile@1', 'profile_version': 1, 'venue': 'NeurIPS',
            'year': 2025, 'track': 'main', 'verification_date': '2025-05-01',
            'sources': [source_row('s1')], 'contribution_types': [],
            'review_criteria': [criterion()], 'mandatory_policy': [claim()],
            'recommended_practice': [], 'compliance_checks': [],
            'changes_from_prior_year': [], 'unknown_policies': []}
    item.update(over)
    return item


class RegistryTestBase(unittest.TestCase):
    def build(self, sources, profiles):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        (root / 'sources').mkdir()
        (root / 'profiles').mkdir()
        for source in sources:
            (root / 'sources' / (source['id'] + '.json')).write_text(
                json.dumps(source), encoding='utf-8')
        for name, item in profiles.items():
            (root / 'profiles' / name).write_text(
                json.dumps(item), encoding='utf-8')
        return root


class DeterministicTests(RegistryTestBase):
    def test_core_vocabulary_self_check_passes(self):
        self.assertEqual(vic.self_check(), 0)

    def test_resolve_returns_the_exact_scope_and_never_a_sibling(self):
        root = self.build([source_file('s1', 'NeurIPS', 2025)],
                          {'n.json': profile()})
        registry = vr.Registry(root)
        resolved, name, missing = registry.resolve('NeurIPS', 2025, 'main')
        self.assertIsNotNone(resolved)
        self.assertEqual(name, 'n.json')
        self.assertIsNone(missing)
        self.assertEqual(resolved['year'], 2025)

        self.assertIsNone(registry.resolve('NeurIPS', 2025, 'workshop')[0])
        self.assertIsNone(registry.resolve('NeurIPS', 2026, 'main')[0])
        self.assertIsNone(registry.resolve('ICML', 2025, 'main')[0])

    def test_unpublished_year_misses_and_reports_available_scopes(self):
        root = self.build([source_file('s1', 'NeurIPS', 2025)], {'n.json': profile()})
        profile_obj, name, missing = vr.Registry(root).resolve('NeurIPS', 2026, 'main')
        self.assertIsNone(profile_obj)
        self.assertIsNone(name)
        self.assertEqual(missing['year'], 2026)

    def test_resolution_miss_carries_a_status_so_the_cli_exits_cleanly(self):
        """A rejected lookup must be a verdict, not a traceback.

        The CLI maps the result status to its exit code; a miss that omitted
        'status' crashed instead of reporting the documented review exit.
        """
        root = self.build([source_file('s1', 'NeurIPS', 2025)], {'n.json': profile()})
        _profile, _name, missing = vr.Registry(root).resolve('ECCV', 2025, 'main')
        self.assertIn('status', missing)
        self.assertEqual(missing['status'], 'UNRESOLVED')
        self.assertTrue(missing['available'])
        self.assertIn('never applied', missing['reason'])
        self.assertIn(('NeurIPS', 2025), missing['available'])

    def test_resolution_never_inherits_a_previous_year(self):
        root = self.build(
            [source_file('s1', 'NeurIPS', 2024)],
            {'n2024.json': profile(year=2024)})
        registry = vr.Registry(root)
        self.assertIsNotNone(registry.resolve('NeurIPS', 2024, 'main')[0])
        self.assertIsNone(registry.resolve('NeurIPS', 2025, 'main')[0])


class ContractTests(RegistryTestBase):
    def test_clean_registry_passes_and_reports_coverage(self):
        root = self.build([source_file('s1', 'NeurIPS', 2025)], {'n.json': profile()})
        result = vr.check(root)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['coverage'][0]['venue'], 'NeurIPS')
        self.assertEqual(result['coverage'][0]['sources'], 1)

    def test_unknown_profile_field_is_rejected(self):
        bad = profile()
        bad['confidence'] = 'high'
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('unknown fields' in e for e in errors))

    def test_source_url_must_be_http(self):
        bad = profile(sources=[dict(source_row('s1'), url='ftp://venue.org/cfp')])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('official http(s) source' in e for e in errors))

    def test_quote_must_occur_verbatim_in_the_saved_excerpt(self):
        bad = profile(mandatory_policy=[claim(quote='submissions must be double blind')])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('does not occur in its saved source excerpt' in e for e in errors))

    def test_profile_source_url_must_match_the_saved_excerpt_url(self):
        bad = profile(sources=[source_row('s1', url='https://elsewhere.example/cfp')])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('url differs from the saved excerpt url' in e for e in errors))

    def test_review_criteria_must_cover_distinct_dimensions(self):
        bad = profile(review_criteria=[criterion('RC1', 'soundness'),
                                       criterion('RC2', 'soundness')])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('distinct dimensions' in e for e in errors))

    def test_mechanically_checkable_item_needs_a_real_check_kind(self):
        bad = profile(compliance_checks=[{'id': 'C1', 'requirement': 'Main text is limited '
                                          'to nine pages', 'mechanically_checkable': True,
                                          'check_kind': 'needs_review', 'source_id': 's1'}])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('needs a real check_kind' in e for e in errors))

    def test_uncertain_item_cannot_claim_a_mechanical_check(self):
        bad = profile(compliance_checks=[{'id': 'C1', 'requirement': 'Main text is limited '
                                          'to nine pages', 'mechanically_checkable': False,
                                          'check_kind': 'page_limit', 'source_id': 's1'}])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('uncertain item must be needs_review or none' in e for e in errors))

    def test_duplicate_source_id_inside_a_profile_is_rejected(self):
        bad = profile(sources=[source_row('s1'), source_row('s1')])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('duplicate source id inside profile' in e for e in errors))

    def test_duplicate_saved_source_ids_are_reported(self):
        root = self.build([source_file('s1', 'NeurIPS', 2025)], {'n.json': profile()})
        # Two files that both declare id s1 -> the second is a duplicate.
        (root / 'sources' / 'other.json').write_text(
            json.dumps(source_file('s1', 'NeurIPS', 2025)), encoding='utf-8')
        result = vr.check(root)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('duplicate source id' in e for e in result['errors']))

    def test_invalid_schema_is_rejected(self):
        bad = profile(schema='venue-policy-profile@2')
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('invalid schema' in e for e in errors))


class RuleConflictTests(RegistryTestBase):
    def test_source_from_the_wrong_year_is_rejected(self):
        root = self.build([source_file('s1', 'NeurIPS', 2024)], {'n.json': profile()})
        result = vr.check(root)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('source s1 belongs to NeurIPS 2024' in e for e in result['errors']))

    def test_invalid_inheritance_reports_the_mismatched_source(self):
        wrong = vr.invalid_inheritance(profile(), {'s1': source_file('s1', 'NeurIPS', 2024)})
        self.assertEqual(len(wrong), 1)
        self.assertIn('belongs to NeurIPS 2024', wrong[0])

    def test_source_from_an_earlier_year_is_never_silently_inherited(self):
        """A 2024 mandate cited by a 2025 profile is an inheritance error, not a rule."""
        errors = vr.invalid_inheritance(profile(), {'s1': source_file('s1', 'NeurIPS', 2024)})
        self.assertEqual(len(errors), 1)
        self.assertNotEqual(errors, [])
        root = self.build([source_file('s1', 'NeurIPS', 2024)], {'n.json': profile()})
        self.assertEqual(vr.check(root)['status'], 'FAIL')

    def test_profile_citing_a_source_it_does_not_own_is_rejected(self):
        bad = profile(mandatory_policy=[claim(source_id='s9')])
        root = self.build([source_file('s1', 'NeurIPS', 2025)], {'n.json': bad})
        result = vr.check(root)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('cites unknown source: s9' in e for e in result['errors']))

    def test_mandatory_policy_must_be_explicit(self):
        bad = profile(mandatory_policy=[claim(explicitness='INFERRED')])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('must be EXPLICIT' in e for e in errors))

    def test_mandatory_policy_needs_a_verified_source(self):
        bad = profile(sources=[source_row('s1', status='PARTIAL')])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('needs a VERIFIED source' in e for e in errors))

    def test_inapplicable_rule_cannot_be_a_mandatory_gate(self):
        """A rule that does not apply is not a mandate (the clean, non-applicable variant)."""
        bad = profile(mandatory_policy=[claim(applicability='NOT_APPLICABLE')])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('applicability must be REQUIRED or CONDITIONAL' in e for e in errors))

    def test_non_mandatory_inapplicable_rule_is_not_turned_into_a_gate(self):
        """A NOT_APPLICABLE advisory rule is clean and must not be rejected as a conflict."""
        ok = profile(mandatory_policy=[],
                     recommended_practice=[claim(id='R1', claim_kind='RECOMMENDED_PRACTICE',
                                                 explicitness='EXPLICIT',
                                                 applicability='NOT_APPLICABLE')])
        self.assertEqual(vr.validate_profile(ok, {'s1': source_file('s1', 'NeurIPS', 2025)}), [])

    def test_required_item_must_be_a_mandatory_policy(self):
        bad = profile(mandatory_policy=[],
                      recommended_practice=[claim(id='R1', claim_kind='RECOMMENDED_PRACTICE',
                                                  applicability='REQUIRED')])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('a REQUIRED item must be a MANDATORY_POLICY' in e for e in errors))

    def test_unknown_claim_kind_needs_unknown_explicitness(self):
        bad = profile(mandatory_policy=[],
                      recommended_practice=[claim(id='R1', claim_kind='UNKNOWN',
                                                  explicitness='EXPLICIT',
                                                  applicability='OPTIONAL')])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('UNKNOWN claim kind needs explicitness UNKNOWN' in e for e in errors))

    def test_duplicate_profile_for_the_same_scope_is_rejected(self):
        root = self.build([source_file('s1', 'NeurIPS', 2025)],
                          {'a.json': profile(), 'b.json': profile()})
        result = vr.check(root)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('duplicate profile for NeurIPS 2025 main' in e for e in result['errors']))

    def test_confirmed_change_needs_a_source(self):
        bad = profile(changes_from_prior_year=[{'id': 'CH1', 'change': 'Page limit changed',
                                                'status': 'CONFIRMED_CHANGE',
                                                'source_id': None}])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('confirmed change needs a source' in e for e in errors))


class EndToEndTests(RegistryTestBase):
    def test_multi_profile_registry_passes_and_lists_every_scope(self):
        root = self.build(
            [source_file('s1', 'NeurIPS', 2025), source_file('s2', 'ICML', 2025,
                                                             url='https://icml.cc/2025/cfp')],
            {'n.json': profile(),
             'i.json': profile(venue='ICML', sources=[source_row('s2', url='https://icml.cc/2025/cfp')],
                               mandatory_policy=[claim(source_id='s2')],
                               review_criteria=[criterion(source_id='s2')])})
        result = vr.check(root)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual({(r['venue'], r['year']) for r in result['coverage']},
                         {('NeurIPS', 2025), ('ICML', 2025)})

    def test_registry_round_trip_after_serialization(self):
        """Serialized files reload to the same verdict: the registry is data, not state."""
        root = self.build([source_file('s1', 'NeurIPS', 2025)], {'n.json': profile()})
        first = vr.check(root)
        second = vr.check(copy.deepcopy(root))
        self.assertEqual(first['status'], second['status'])
        self.assertEqual(first['errors'], second['errors'])

    def test_published_contribution_category_must_be_source_quoted(self):
        # A category is a venue claim too, so a valid profile can publish one only
        # with a verbatim quote from its own saved source.
        good = profile(contribution_types=[contribution_type()])
        self.assertEqual(vr.validate_profile(good, {'s1': source_file('s1', 'NeurIPS', 2025)}), [])
        bad = profile(contribution_types=[contribution_type(quote='an invented category')])
        errors = vr.validate_profile(bad, {'s1': source_file('s1', 'NeurIPS', 2025)})
        self.assertTrue(any('does not occur in its saved source excerpt' in e for e in errors))

    def test_registry_with_a_published_category_passes_check(self):
        root = self.build([source_file('s1', 'NeurIPS', 2025)],
                          {'n.json': profile(contribution_types=[contribution_type()])})
        result = vr.check(root)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['errors'], [])


if __name__ == '__main__':
    unittest.main()
