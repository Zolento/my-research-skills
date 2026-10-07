import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import audit_coherence as ac
import architect as ar
import validate_style as vs
from compare_invariants import digest
from test_coherence import logic_fixture, finding
from test_architect import blueprint_fixture, outline_review
from test_suggestions import bank_fixture, refresh_quality
import validate_suggestions as sb


class ReviewRegressionTests(unittest.TestCase):
    def test_known_macro_cannot_swallow_unrelated_prose(self):
        self.assertEqual(vs.validate(r'\ref{fig:a} {The result: a bounded effect.}')['status'], 'FAIL')

    def test_tex_dash_punctuation_and_range_exemption(self):
        self.assertEqual(vs.validate('The result---within Y---holds.')['status'], 'FAIL')
        self.assertEqual(vs.validate('Seeds 1--5 were tested.\n\n---\n')['status'], 'PASS')

    def test_markdown_citation_payload_is_technical(self):
        self.assertEqual(vs.validate('The result follows prior work [@p:2020; @q:2021].')['status'], 'PASS')

    def test_multi_backtick_code_is_protected(self):
        self.assertEqual(vs.validate('The code is ``x: int; `literal` ``.')['status'], 'PASS')

    def test_plural_reference_and_cref_stack(self):
        for text in ('Figs. 2 and 3 show the comparison.', r'Results agree (\cref{fig:a,tab:b}).'):
            self.assertTrue(any(f['rule'] == 'H2' for f in vs.validate(text)['findings']))
        self.assertEqual(vs.validate(r'The identity uses \cref{eq:a,eq:b}.')['status'], 'PASS')

    def test_failed_counterfactual_cannot_be_ignored(self):
        text, graph, report = logic_fixture()
        report['counterfactuals'][0]['verdict'] = 'CONTRADICTED'
        self.assertEqual(ac.audit(text, graph, report)['status'], 'FAIL')

    def test_untestable_research_question_cannot_pass(self):
        text, graph, report = logic_fixture()
        report['rq_matrix'][0]['testable'] = 'FAIL'
        self.assertEqual(ac.audit(text, graph, report)['status'], 'FAIL')

    def test_dependency_role_and_self_premise(self):
        for dependency in ({'kind': 'definition', 'id': 'C'}, {'kind': 'known_theorem', 'id': 'T'}):
            text, graph, report = logic_fixture(theory=True)
            report['proof_steps'][0]['dependencies'] = [dependency]
            self.assertEqual(ac.audit(text, graph, report)['status'], 'FAIL')

    def test_no_theory_does_not_mean_adequate_proof(self):
        text, graph, report = logic_fixture()
        report['scorecard']['Proof reliability']['level'] = 'strong'
        self.assertEqual(ac.audit(text, graph, report)['status'], 'FAIL')

    def test_well_supported_cannot_hide_failed_edge(self):
        text, graph, report = logic_fixture()
        report['edge_checks'][-1]['verdict'] = 'unclear'
        self.assertIn('Well Supported cannot cite unsupported or unverified links', ac.audit(text, graph, report)['errors'])

    def test_blueprint_cannot_change_audited_claim_identity(self):
        material, graph, report, blue, audit = blueprint_fixture()
        blue['claims'][0]['claim'] = 'X causes universal improvement.'
        audit['blueprint_digest'] = digest(blue)
        self.assertEqual(ar.validate_blueprint(material, graph, report, blue, audit)['status'], 'FAIL')

    def test_stale_coherence_cannot_enable_revision(self):
        text, bank, coherence = bank_fixture(mode='revise')
        coherence['manuscript_digest'] = 'a different manuscript'
        bank['coherence_digest'] = digest(coherence)
        refresh_quality(text, bank)
        self.assertEqual(sb.validate(text, bank, coherence)['status'], 'FAIL')

    def test_missing_blueprint_gates_cannot_be_skipped_by_approval(self):
        _, _, _, blue, _ = blueprint_fixture()
        approval = {'blueprint_digest': digest(blue), 'approved': True, 'section_ids': ['S1']}
        self.assertEqual(ar.validate_section_draft(blue, approval, 'S1', 'X.', {})['status'], 'FAIL')

    def test_moderate_underdetermined_finding_blocks_drafting(self):
        material, graph, report, blue, audit = blueprint_fixture()
        report['passes']['experiments']['findings'] = [finding('UNCERTAIN_STATISTICS', severity='moderate', verdict='UNDERDETERMINED')]
        report['aggregation'] = ['I1']
        report['scorecard']['Statistical support'].update(level='needs attention', finding_ids=['I1'])
        coherence = ac.audit(ar.corpus(material), graph, report)
        self.assertEqual(coherence['status'], 'NEEDS_REVIEW')
        blue['coherence_digest'] = digest(coherence)
        result = ar.validate_blueprint(material, graph, report, blue, outline_review(material, blue))
        self.assertFalse(result['draft_ready'])

    def test_graph_theorem_requires_alignment_regardless_of_label(self):
        material, graph, report, blue, audit = blueprint_fixture()
        graph['nodes'][-1]['type'] = 'Theorem'
        report['graph_digest'] = digest(graph)
        report['passes']['theory']['status'] = 'COMPLETE'
        for label in ('theorem', 'empirical', 'proposition'):
            blue['claims'][0]['claim_type'] = label
            blue['graph_digest'] = digest(graph)
            blue['coherence_digest'] = digest(ac.audit(ar.corpus(material), graph, report))
            result = ar.validate_blueprint(material, graph, report, blue, outline_review(material, blue))
            self.assertIn('every theoretical claim needs method/experiment alignment', result['errors'])

    def test_major_structural_candidate_cannot_disappear_from_bank(self):
        text, bank, coherence = bank_fixture()
        coherence['structural_diagnostics'] = [{'id': 'D1', 'severity': 'major', 'code': 'ORPHAN_CLAIM', 'node_ids': ['C']}]
        bank['coherence_digest'] = digest(coherence)
        refresh_quality(text, bank)
        self.assertIn('critical/major scientific issue hidden in the suggestion bank', sb.validate(text, bank, coherence)['errors'])


if __name__ == '__main__':
    unittest.main()
