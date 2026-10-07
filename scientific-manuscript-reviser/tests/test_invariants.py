import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import compare_invariants as ci


def extracted(text, statements):
    facts = []
    for i, (category, span) in enumerate(statements):
        start = text.index(span)
        facts.append({'id': 'F' + str(i), 'category': category, 'statement': span,
                      'location': {'start': start, 'end': start + len(span)}, 'source_span': span})
    return {'schema': 'manuscript-invariants@1', 'manuscript_digest': ci.digest(text),
            'covered_categories': list(ci.CATEGORIES), 'absent_categories': sorted(set(ci.CATEGORIES) - {f['category'] for f in facts}),
            'facts': facts, 'unresolved': []}


def audit_for(before, after, old, new):
    """Protocol fixture, not an invocation or simulation of an independent judge."""
    return {'schema': 'manuscript-semantic-audit@1', 'original_digest': ci.digest(before),
            'revised_digest': ci.digest(after), 'original_facts_digest': ci.digest(old),
            'revised_facts_digest': ci.digest(new),
            'fact_checks': [{'original_id': f['id'], 'revised_ids': [n['id']], 'status': 'PASS', 'rationale': 'Reviewed mapped source spans.'}
                            for f, n in zip(old['facts'], new['facts'])],
            'new_assertion_checks': [{'revised_id': n['id'], 'original_ids': [f['id']], 'status': 'PASS', 'rationale': 'Source mapping retained.'}
                                    for f, n in zip(old['facts'], new['facts'])],
            'global_checks': {k: {'status': 'PASS', 'rationale': 'Reviewed both full texts.'} for k in ci.GLOBAL_CHECKS}}


class InvariantTests(unittest.TestCase):
    def test_number_change_fails_without_semantic_audit(self):
        self.assertEqual(ci.compare('The mean is 0.8 dB.', 'The mean is 8 dB.')['status'], 'FAIL')

    def test_same_numeric_multiset_needs_semantic_review(self):
        a, b = 'A scores 10 and B scores 5.', 'A scores 5 and B scores 10.'
        result = ci.compare(a, b)
        self.assertEqual(result['mechanical_status'], 'PASS')
        self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_citation_keys_preserved(self):
        self.assertEqual(ci.compare(r'We follow \cite{p:2020}.', r'We follow \cite{q:2020}.')['status'], 'FAIL')

    def test_reference_number_preserved(self):
        self.assertEqual(ci.compare('The mean falls (Fig. 2).', 'The mean falls (Fig. 3).')['status'], 'FAIL')

    def test_latex_command_and_payload_preserved(self):
        for a, b in ((r'Use \ref{fig:x}.', r'Use \ref{fig:y}.'),
                     (r'\textbf{We use X.}', 'We use X.'),
                     (r'$a:b$', r'$b:a$')):
            self.assertEqual(ci.compare(a, b)['status'], 'FAIL')

    def test_accidental_corruption(self):
        for text in ('', 'Bad\x00text', r'\textbf{bad', r'\begin{figure}x\end{table}'):
            self.assertEqual(ci.compare('Good text.', text)['status'], 'FAIL')

    def test_fact_span_digest_and_category_coverage(self):
        text = 'The mean is 0.8 dB.'
        facts = extracted(text, [('claims', text)])
        self.assertEqual(ci.validate_facts(text, facts), [])
        for mutate in (lambda f: f.update(manuscript_digest='wrong'),
                       lambda f: f['facts'][0]['location'].update(start=1),
                       lambda f: f['covered_categories'].pop(),
                       lambda f: f.update(absent_categories=[])):
            bad = copy.deepcopy(facts)
            mutate(bad)
            self.assertTrue(ci.validate_facts(text, bad))

    def test_unchanged_content_with_full_audit_passes(self):
        text = 'The mean is 0.8 dB.'
        facts = extracted(text, [('claims', text)])
        self.assertEqual(ci.compare(text, text, facts, facts, audit_for(text, text, facts, facts))['status'], 'PASS')

    def test_semantic_failures_are_honored(self):
        cases = [
            ('baselines', 'We compare against P.', 'We compare against Q.'),
            ('statistical_statements', 'Significance is untested.', 'The result is statistically significant.'),
            ('causal_status', 'X is associated with Y.', 'X causes Y.'),
            ('scope', 'The effect holds on Dataset A.', 'The effect holds universally.'),
            ('limitations', 'External validity is untested.', 'External validity is established.'),
            ('technical_terminology', 'We use generalized estimating equations.', 'We use generalized estimated equilibria.'),
            ('novelty', 'We study X.', 'We are the first to study X.'),
            ('claims', 'The supported effect is clear.', 'The effect may or may not exist.'),
        ]
        for category, before, after in cases:
            with self.subTest(category=category):
                old, new = extracted(before, [(category, before)]), extracted(after, [(category, after)])
                audit = audit_for(before, after, old, new)
                audit['fact_checks'][0].update(status='FAIL', rationale='Meaning changed in mapped source spans.')
                self.assertEqual(ci.compare(before, after, old, new, audit)['status'], 'FAIL')

    def test_limitation_deletion_cannot_be_declared_pass(self):
        before, after = 'The effect is bounded. Replication is untested.', 'The effect is bounded.'
        old = extracted(before, [('claims', 'The effect is bounded.'), ('limitations', 'Replication is untested.')])
        new = extracted(after, [('claims', after)])
        audit = audit_for(before, after, old, new)
        self.assertEqual(ci.compare(before, after, old, new, audit)['status'], 'FAIL')
        audit['fact_checks'].append({'original_id': 'F1', 'revised_ids': [], 'status': 'PASS', 'rationale': 'Deleted.'})
        self.assertEqual(ci.compare(before, after, old, new, audit)['status'], 'FAIL')

    def test_new_assertion_and_global_audit_coverage(self):
        before, after = 'We study X.', 'We study X. This is universally effective.'
        old = extracted(before, [('claims', before)])
        new = extracted(after, [('claims', before), ('claims', 'This is universally effective.')])
        audit = audit_for(before, after, old, new)
        self.assertEqual(ci.compare(before, after, old, new, audit)['status'], 'FAIL')

    def test_stale_audit_missing_global_and_unknown_fail_closed(self):
        text = 'We study X.'
        facts = extracted(text, [('claims', text)])
        audit = audit_for(text, text, facts, facts)
        audit['revised_digest'] = 'stale'
        self.assertEqual(ci.compare(text, text, facts, facts, audit)['status'], 'FAIL')
        audit = audit_for(text, text, facts, facts)
        audit['global_checks'].pop('citation_meaning')
        self.assertEqual(ci.compare(text, text, facts, facts, audit)['status'], 'FAIL')
        audit = audit_for(text, text, facts, facts)
        audit['global_checks']['scope_and_boundary'].update(status='UNKNOWN', rationale='Missing context.')
        self.assertEqual(ci.compare(text, text, facts, facts, audit)['status'], 'NEEDS_REVIEW')


if __name__ == '__main__':
    unittest.main()
