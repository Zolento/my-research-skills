import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import validate_style as vs


class StyleTests(unittest.TestCase):
    def test_prose_semicolon(self):
        self.assertEqual(vs.validate('The effect increased; the scope is unchanged.')['status'], 'FAIL')

    def test_prose_colon(self):
        self.assertEqual(vs.validate('We report one result: a bounded effect.')['status'], 'FAIL')

    def test_prose_em_dash(self):
        self.assertEqual(vs.validate('The effect—within this dataset—is positive.')['status'], 'FAIL')

    def test_prose_en_dash(self):
        self.assertEqual(vs.validate('The effect – within this dataset – is positive.')['status'], 'FAIL')

    def test_ratio_not_punctuation(self):
        self.assertEqual(vs.validate('We use a ratio of 1:4 and seeds 1–5.')['status'], 'PASS')

    def test_formula_punctuation(self):
        self.assertEqual(vs.validate(r'We set $f(x;y):=x+y$ and \(a:b\).')['status'], 'PASS')

    def test_latex_command_not_changed(self):
        text = r'Use \cite{smith:2020} and \ref{fig:a}. Let $a\;b$ vary.'
        before = str(text)
        self.assertEqual(vs.validate(text)['status'], 'PASS')
        self.assertEqual(text, before)

    def test_url_colon(self):
        self.assertEqual(vs.validate('Data are at https://example.org/a:b?q=1:4.')['status'], 'PASS')

    def test_stacked_refs(self):
        for text in ('As shown in Fig. 2, Table 3, and Sec. 4, the error falls.',
                     r'Fig. \ref{f:a} and Table \ref{t:b} show the effect.'):
            self.assertTrue(any(f['rule'] == 'H2' for f in vs.validate(text)['findings']))

    def test_single_natural_reference(self):
        self.assertEqual(vs.validate('The error falls under the matched protocol (Fig. 2).')['status'], 'PASS')

    def test_equation_references(self):
        self.assertEqual(vs.validate(r'Eqs. (1) and (2), or \eqref{eq:one} and \eqref{eq:two}, define the loss.')['status'], 'PASS')

    def test_adjacent_reference_subjects(self):
        self.assertTrue(any(f['rule'] == 'H2' for f in vs.validate('Fig. 2 shows the error. Table 3 shows the variance.')['findings']))

    def test_formatting_macro_prose_is_checked(self):
        self.assertEqual(vs.validate(r'\textbf{Our result: a bounded effect.}')['status'], 'FAIL')

    def test_href_visible_text_is_prose(self):
        self.assertEqual(vs.validate(r'\href{https://example.org/a:b}{Result: bounded effect}')['status'], 'FAIL')

    def test_unknown_macro_warns_instead_of_corrupting(self):
        self.assertEqual(vs.validate(r'\customformula{x:y;z}')['status'], 'NEEDS_REVIEW')

    def test_unclosed_technical_spans_need_review(self):
        for text in ('Value $a:b', '```python\nx: int = 1', r'\begin{equation}x:y'):
            self.assertEqual(vs.validate(text)['status'], 'NEEDS_REVIEW')

    def test_code_tables_and_bibliography(self):
        text = '```python\nx: int = 1; print(x)\n```\n| a:b | c;d |\n@article{k, title={a:b}}'
        self.assertEqual(vs.validate(text)['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
