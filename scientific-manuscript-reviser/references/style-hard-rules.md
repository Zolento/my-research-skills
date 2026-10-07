# Personal hard style rules

Explicit user rules override an inferred profile or venue convention. H1–H3 apply
to revised manuscript prose, not to diagnostic JSON, code or schema punctuation.

## H1 Prose punctuation

Ordinary prose cannot contain semicolon, colon, em dash or an en dash used as
punctuation. A hyphen within a word is allowed. Split sentences or state the
relation explicitly without replacing scientific qualifiers.

Technical environments may contain those marks when necessary. Examples include
math, ratios such as 1:4, numeric ranges, identifiers, code, URLs, LaTeX commands,
bibliography entries and structured table syntax. Text inside a formatting macro
such as `\textbf{...}` or a caption remains prose. Formula environments and reference
command arguments are protected. `\href{URL}{visible prose}` protects the URL only.
Unknown macros, unmatched delimiters and ambiguous notation require a warning
and manual review. The scanner never modifies text or expands TeX. It is a limited
lexical parser; warnings must not be suppressed to make the output “pass”.

## H2 Cross-reference narration

Do not chain Fig., Table or Sec. references in a single short phrase. Do not let
adjacent sentences repeatedly use a figure/table/section as their subject. Put the
observation first and its reference naturally after it. Keep all numbers, citation
keys and necessary references. Equations and necessary mathematical references
are exempt from simple counting limits.

If multiple references are necessary, restructure the prose without mechanically
deleting them. A deterministic stacked-reference candidate does not establish a
semantic mismatch. A separate audit checks what each reference actually supports,
including caption/body agreement and citations attached to their original assertions.

## H3 Calibrated confidence

No anticipatory apology or unsupported self-downgrading. Retain genuine uncertainty,
experimental boundaries, known limitations and statistically justified caution.
Evidence supports the claim strength in both directions. Unsupported confidence
and unsupported weakening are both problems. See defensive-language.md for the
functional categories. Regex never decides which caution is scientifically needed.

## Commands and acceptance

`python3 scripts/validate_style.py manuscript.tex` reads only. Status PASS means no
mechanical candidates, FAIL means an obvious violation, NEEDS_REVIEW means ambiguous
spans. Return codes are 0/3/4. Run after revision and inspect warnings. Preservation
checks use compare_invariants.py separately. No style preference permits changing
a technical token just to satisfy H1.
