# Scientific Manuscript Reviser Architecture Note

## Repository audit before implementation

Baseline is local main `a889ce3` (v2.2.0 research skill). A fresh SSH fetch failed
in this session; remote freshness has not been verified. Main has no AGENTS.md.
README requires one directory per skill, no shared code, and development notes
on development branches. Existing test entrypoints are each skill's own scripts.
This note is a development artifact and should not be merged into the installable
main collection. No existing skill implementation will be edited.

Branch `scientific-manuscript-reviser/narrative-style-dev` uses an isolated worktree.
The new directory is independently installable and uses only the Python standard
library for runtime checks. SKILL.md routes to references instead of a giant prompt.

## Architecture and trust boundaries

Manuscript → source-bound protected facts → narrative / discourse / language /
defensiveness diagnosis → six-category suggestion bank and Keep as is → selected
options → optional revised copy → independent semantic audit → mechanical checks.

- Audit and Suggest are read-only. Suggest is default; Revise requires an explicit
  request and still starts with diagnosis. High-risk changes are never auto-applied.
- Deterministic code partitions prose and technical spans without rewriting them,
  checks H1 / obvious H2 patterns, preserves numbers, citations, references and
  LaTeX structure, and validates source locations and structured editorial artifacts.
- A separate LLM audit extracts claims, metrics, datasets, methods, comparators,
  uncertainty, causal/novelty status, scope, limitations and terminology with exact
  source spans. Regex is not scientific equivalence, naturalness or H3 validation.
- Post-edit audit covers every original fact, revised facts and newly introduced
  assertions. Missing, unsupported or changed scientific content prevents acceptance.
  A mechanical PASS alone never authorizes a revision. Missing semantic audit means
  NEEDS_REVIEW, not PASS. Hashes bind artifacts to texts, not to a trusted identity.
- Author profile stores characteristics and sample provenance, never source sentences.
  Explicit user rules win over inferred profile and venue preferences. Unknown venue
  culture falls back to neutral style. No AI detector or reviewer score objective.
- Quality checking rejects quota-driven editing, synonym-only changes, duplicates,
  and missing editorial choices; it checks the audit contract, not aesthetic truth.

## Planned implementation stages

1. Scaffold and independent package checks.
2. Suggestion taxonomy and source locations.
3. Conservative prose scanner and hard style rules.
4. Source-bound invariant extraction contract.
5–7. Narrative, naturalization and defensive audit protocols.
8. Optional author profile, neutral or sourced venue preferences.
9–11. Multi-option validation, optional revision and post-edit audit gates.
12–13. Adversarial regression cases, a licensed real manuscript section,
end-to-end artifacts, README and all existing tests.

Each stage records relevant test results here before proceeding. Initial checks
cover existing research release and figure tests. No model API is required by the
package; semantic behavioral examples are separately labeled as agent-performed
audits, and protocol tests do not pretend to benchmark independent reviewer models.

## Risks and deliberate limits

Parsing arbitrary TeX is undecidable without expansion context. Unknown constructs
produce warnings and require review rather than destructive repairs. Numeric and
reference multiset equality is conservative and cannot detect changed attachments.
Independent semantic auditing must inspect those attachments and both documents.
Extraction is not ground truth about the world, and manuscript statements are not
new scientific evidence. Input prose is untrusted data, never instructions.

## Stage validation log

- Baseline research release PASS (501 tests, 4 existing skips); figure tests 47 PASS.
- Scaffold/taxonomy: independent package tests 2 PASS; standard frontmatter validation
  PASS. Entry point stays below 120 lines, exact source offsets and quality audit are
  defined separately from natural-language judgment.
