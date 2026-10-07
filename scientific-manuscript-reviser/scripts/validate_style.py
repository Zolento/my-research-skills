#!/usr/bin/env python3
"""Read-only mechanical H1 / obvious H2 checks, not a semantic style judge.

Exit 0 PASS, 3 FAIL, 4 NEEDS_REVIEW or invalid input. Offsets are Unicode characters.
"""
import argparse
import json
from pathlib import Path
import re


COMMAND = re.compile(r"\\(?:[A-Za-z@]+\*?|[^\s])")
REF = re.compile(r"\b(?:Figs?\.?|Figures?|Tables?|Secs?\.?|Sections?)\s*(?:\d+(?:\.\d+)*[a-z]?|\\(?:ref|autoref|cref|Cref)\{[^{}]+\})", re.I)
PROSE_COMMANDS = {'section', 'subsection', 'subsubsection', 'paragraph', 'caption',
                  'textbf', 'textit', 'textrm', 'text', 'emph', 'footnote', 'title',
                  'author', 'item', 'maketitle', 'noindent', 'par', 'newline',
                  'documentclass', 'usepackage', 'begin', 'end'}
TECH_COMMANDS = {'cite', 'citep', 'citet', 'citeauthor', 'citeyear', 'parencite',
                 'textcite', 'ref', 'eqref', 'autoref', 'cref', 'Cref', 'label',
                 'url', 'path', 'href', 'includegraphics', 'bibliography',
                 'bibliographystyle', 'newcommand', 'renewcommand', 'providecommand',
                 'def', 'frac', 'dfrac', 'tfrac', 'sqrt', 'SI', 'si', 'num'}
TECH_ENVS = {'equation', 'equation*', 'align', 'align*', 'aligned', 'gather', 'gather*',
             'displaymath', 'math', 'verbatim', 'lstlisting', 'thebibliography', 'tabular',
             'tabular*', 'array', 'matrix', 'bmatrix', 'pmatrix'}


def escaped(text, position):
    prefix = text[:position]
    return (len(prefix) - len(prefix.rstrip('\\'))) % 2 == 1


def balanced_end(text, start, opening='{', closing='}'):
    depth = 0
    for i in range(start, len(text)):
        if escaped(text, i):
            continue
        if text[i] == opening:
            depth += 1
        elif text[i] == closing:
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def location(text, start, end):
    return {'start': start, 'end': end, 'line': text.count('\n', 0, start) + 1,
            'column': start - text.rfind('\n', 0, start)}


def scan(text):
    """Conservative lexical partition. Unknown TeX produces review warnings."""
    mask = [False] * len(text)
    spans, warnings = [], []

    def protect(start, end, kind):
        mask[start:end] = [True] * (end - start)
        spans.append({'start': start, 'end': end, 'kind': kind})

    def warn(start, end, message):
        warnings.append({'rule': 'SPAN', 'severity': 'warning',
                         'location': location(text, start, end), 'message': message})

    # Block contexts before inline delimiters. Never expand TeX or execute macros.
    fence = re.compile(r'^\s*(`{3,}|~{3,})[^\n]*\n', re.M)
    for m in fence.finditer(text):
        if mask[m.start()]:
            continue
        end = re.search(r'^\s*' + re.escape(m[1][0]) + '{' + str(len(m[1])) + r',}\s*$', text[m.end():], re.M)
        stop = m.end() + end.end() if end else len(text)
        protect(m.start(), stop, 'code')
        if not end:
            warn(m.start(), stop, 'Unclosed code fence needs manual review.')
    for m in re.finditer(r'\\begin\{([^{}]+)\}', text):
        if mask[m.start()] or m[1] not in TECH_ENVS:
            continue
        end = text.find('\\end{' + m[1] + '}', m.end())
        stop = end + len('\\end{' + m[1] + '}') if end >= 0 else len(text)
        protect(m.start(), stop, 'technical environment')
        if end < 0:
            warn(m.start(), stop, 'Unclosed technical environment.')
    for m in re.finditer(r'^\s*\|.*\|\s*$|^\s*@\w+\s*\{|^\s*(?:-{3,}|\*{3,}|_{3,})\s*$', text, re.M):
        if mask[m.start()]:
            continue
        if '@' in m[0] and not m[0].lstrip().startswith('|'):
            stop = balanced_end(text, m.end() - 1)
            protect(m.start(), stop or len(text), 'bibliography')
            if stop is None:
                warn(m.start(), len(text), 'Unclosed bibliography entry.')
        else:
            protect(m.start(), m.end(), 'structured table')
    i = 0
    while i < len(text):
        if mask[i]:
            i += 1
            continue
        if text[i] == '%' and re.search(r'\\[A-Za-z]+', text) and not escaped(text, i) and not (i and text[i - 1].isdigit()):
            end = text.find('\n', i)
            protect(i, end if end >= 0 else len(text), 'TeX comment')
            i = end if end >= 0 else len(text)
            continue
        opener = next((x for x in ('$$', '\\[', '\\(', '$', '`') if text.startswith(x, i)), None)
        if opener:
            if opener == '`':
                opener = re.match(r'`+', text[i:])[0]
            closer = {'\\[': '\\]', '\\(': '\\)'}.get(opener, opener)
            end = i + len(opener)
            while True:
                end = text.find(closer, end)
                if end < 0 or not escaped(text, end):
                    break
                end += len(closer)
            stop = end + len(closer) if end >= 0 else len(text)
            protect(i, stop, 'inline code' if opener.startswith('`') else 'math')
            if end < 0:
                warn(i, stop, 'Unclosed inline delimiter or ambiguous currency notation.')
            i = stop
            continue
        url = re.match(r'(?:https?://|doi:)[^\s<>]+', text[i:])
        if url:
            stop = i + len(url[0].rstrip('.,;)'))
            protect(i, stop, 'URL')
            i = stop
            continue
        citation = re.match(r'\[@[^\]\n]+\]', text[i:])
        if citation:
            protect(i, i + len(citation[0]), 'citation notation')
            i += len(citation[0])
            continue
        notation = re.match(r'\d+(?:\.\d+)?\s*(?::|–|--)\s*\d+(?:\.\d+)?\b|[A-Za-z_]\w*::[A-Za-z_]\w*', text[i:])
        if notation and (i == 0 or not text[i - 1].isalnum()):
            protect(i, i + len(notation[0]), 'ratio/range/identifier')
            i += len(notation[0])
            continue
        command = COMMAND.match(text, i)
        if command:
            name = command[0][1:].rstrip('*')
            stop = command.end()
            protect(i, stop, 'LaTeX command')
            if name in TECH_COMMANDS or (len(name) > 1 and name not in PROSE_COMMANDS):
                pos = stop
                # Protected payloads, with optional arguments. href's visible text is prose.
                max_braces = (2 if name in {'frac', 'dfrac', 'tfrac', 'SI', 'newcommand', 'renewcommand', 'providecommand'}
                              else 1 if name in TECH_COMMANDS else 8)
                braces = 0
                while pos < len(text):
                    start = pos
                    while start < len(text) and text[start].isspace():
                        start += 1
                    if start >= len(text) or text[start] not in '[{':
                        break
                    opening = text[start]
                    if opening == '{' and braces >= max_braces:
                        break
                    end = balanced_end(text, start, opening, ']' if opening == '[' else '}')
                    if end is None:
                        warn(start, len(text), 'Unbalanced command argument.')
                        end = len(text)
                    protect(pos, end, 'technical command argument')
                    braces += opening == '{'
                    pos = end
                stop = pos
                if name not in TECH_COMMANDS:
                    warn(i, stop, 'Unknown macro context; inspect its arguments before accepting prose rules.')
            i = stop
            continue
        i += 1
    prose = ''.join('\n' if c == '\n' else ' ' if mask[j] else c for j, c in enumerate(text))
    return {'prose': prose, 'protected': spans, 'warnings': warnings}


def validate(text):
    parsed = scan(text)
    findings = list(parsed['warnings'])
    for m in re.finditer(r'[;:—–]|(?<!-)-{2,3}(?!-)', parsed['prose']):
        findings.append({'rule': 'H1', 'severity': 'error',
                         'location': location(text, m.start(), m.end()),
                         'message': 'Prohibited punctuation in a prose span.'})
    # Cross-reference numbers and TeX ref arguments are protected; examine original
    # prose context, retaining technical references but excluding math/code blocks.
    blocked = [s for s in parsed['protected'] if s['kind'] in
               ('code', 'inline code', 'math', 'technical environment', 'bibliography', 'structured table', 'TeX comment')]
    refs = [m for m in REF.finditer(text) if not any(s['start'] <= m.start() < s['end'] for s in blocked)]
    for a, b in zip(refs, refs[1:]):
        between = text[a.end():b.start()]
        if re.fullmatch(r'[\s,]*(?:(?:and|or|&)\s*)?', between, re.I):
            findings.append({'rule': 'H2', 'severity': 'error',
                             'location': location(text, a.start(), b.end()),
                             'message': 'Chained figure/table/section references; restructure prose, retain identifiers.'})
        elif re.fullmatch(r'[^.!?]*[.!?]\s*', between) and re.search(r'(?:^|[.!?]\s*)$', text[:a.start()]) and re.match(r'\s+(?:shows?|presents?|discusses?)\b', text[b.end():], re.I):
            findings.append({'rule': 'H2', 'severity': 'error',
                             'location': location(text, a.start(), b.end()),
                             'message': 'Adjacent sentences repeatedly start with references.'})
    for m in refs:
        trailing = re.match(r'\s*(?:,\s*|(?:and|or)\s+)\d+(?:\.\d+)*\b', text[m.end():], re.I)
        if trailing:
            findings.append({'rule': 'H2', 'severity': 'error', 'location': location(text, m.start(), m.end() + trailing.end()),
                             'message': 'Multiple figure/table/section numbers in a stacked reference phrase.'})
    for m in re.finditer(r'\\(?:ref|cref|Cref|autoref)\{([^{}]+)\}', text):
        if any(s['start'] <= m.start() < s['end'] for s in blocked):
            continue
        keys = [k.strip() for k in m[1].split(',')]
        if len(keys) > 1 and all(re.match(r'(?:fig|tab|table|sec|section)[:_-]', k, re.I) for k in keys):
            findings.append({'rule': 'H2', 'severity': 'error', 'location': location(text, m.start(), m.end()),
                             'message': 'A cross-reference command stacks figure/table/section identifiers.'})
    status = 'FAIL' if any(f['severity'] == 'error' for f in findings) else 'NEEDS_REVIEW' if findings else 'PASS'
    return {'status': status, 'findings': findings,
            'note': 'Mechanical candidates only. H2 meaning, H3 calibration and naturalness require semantic audit.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manuscript', type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.manuscript.read_text(encoding='utf-8'))
    except (OSError, UnicodeError) as exc:
        result = {'status': 'INVALID', 'error': str(exc)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return {'PASS': 0, 'FAIL': 3}.get(result['status'], 4)


if __name__ == '__main__':
    raise SystemExit(main())
