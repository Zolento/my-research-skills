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

Manuscript → source-bound protected facts → Scientific Coherence Audit → narrative / discourse / language /
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

## Added high-priority scientific coherence layer

The user added this requirement during implementation. Preserve all original editing
requirements and keep three layers independent: scientific reasoning, narrative,
language. Scientific coherence now precedes all rhetorical editing. It reconstructs
a typed, located argument graph, then separately audits evidence links, theory,
experiments, entailment, cross-section consistency and counterfactuals. Aggregation
may only rank/merge existing findings. It cannot invent criticisms.

Graph topology can mechanically reveal cycles and disconnected claims/experiments;
valid topology cannot prove support. Local entailment, hidden assumptions, fairness,
mechanistic identification and underclaim require scoped semantic passes. Unknown
theory is NOT_VERIFIED, external concerns require NEEDS_EXTERNAL_VERIFICATION.
No opaque score and no inference from prose fluency. A partial section cannot certify
whole-paper coherence. Original unsupported claims remain protected until the author
explicitly resolves a scientific change and establishes a new baseline.

The suggestion bank expands to ten categories with Scientific logic, Theory and
proof, Experimental design, Claim and conclusion validity first. Scientific repair
options name text-only/reanalysis/new-experiment/new-theory requirements. No agent
performs a scientific correction merely to make an invariance check pass.

## Architect mode steering

The user subsequently expanded the core object to Scientific Argument. Three core
modes are Audit, Architect and Revise; Suggest remains the default editorial output
within Audit, and an explicit analysis-only request stays analysis-only. Architect
normalizes source materials with epistemic types, checks sufficiency, searches
supported theses/hierarchies, then creates Compact or Full paragraph blueprints.
The same graph and local scientific audits run before generation and on the resulting
plan. Planned or hypothesized evidence never counts as an established result.
Incomplete materials permit bounded plans with SCIENTIFIC GAP TO RESOLVE markers.

Research-material map, blueprint, outline audit and section-draft audit are separate
source-bound artifacts. The software checks references/statuses/coverage and honors
semantic verdicts, rather than claiming regex can generate or certify an argument.
Scientific critical/major findings must propagate to blueprint gaps. Blueprint
approval is explicit before optional section-by-section drafting. New evidence in
Revise establishes a versioned baseline with author resolution, not permission to
silently change original claims under an “equivalent” label.

## Stage validation log

- Baseline research release PASS (501 tests, 4 existing skips); figure tests 47 PASS.
- Scaffold/taxonomy: independent package tests 2 PASS; standard frontmatter validation
  PASS. Entry point stays below 120 lines, exact source offsets and quality audit are
  defined separately from natural-language judgment.
- Hard style rules: 19 tests PASS, including prose punctuation, technical exemptions,
  format-macro prose, unknown/unclosed TeX warnings and reference stacking. Checks
  are read-only and retain offsets for human review.
- Invariant extraction and post-edit contract: 31 tests PASS. Mechanical token
  preservation is separate from complete original/revised fact coverage and global
  semantic judgments. Missing audit is NEEDS_REVIEW; failed semantic verdicts are
  honored. Behavioral scientific judgments are not claimed as regex detections.
- Scientific coherence: 47 tests PASS, including located graph/provenance,
  structural orphan/cycle/untested diagnostics, local verdict fixtures for twenty
  scientific counterexamples, Critical leakage, proof unknowns and aggregation
  provenance. These test audit contracts, not autonomous LLM error-detection accuracy.
- Narrative/naturalization/defensiveness/profile and suggestions: 62 tests PASS.
  Weak pattern candidates stay separate from contextual quality judgments. Explicit
  author rules override descriptive sample statistics; high-risk edits cannot apply.
- Architect: 87 tests PASS. Material epistemic types, audited graph claim identity,
  sufficiency, thesis/evidence/novelty, paragraph purpose/style, scientific gap placement,
  portfolio/literature and approved section drafting share the scientific gates.

- Final independent forward test: realistic incomplete materials produce a source-bound
  Compact plan with NEEDS_REVIEW, bounded_outline=true, draft_ready=false. Desired
  mechanism and generalization remain unsupported; planned experiments stay planned.
- Review repaired unresolved moderate scientific findings being discarded, theorem
  alignment bypass through claim labels, hidden structural diagnostics, stale source
  bindings, proof dependency roles, counterfactual verdict handling, and technical
  macro/dash/cross-reference scanner cases. Each correction has a regression case.
- Real attributed manuscript excerpt keeps its true selection limitation and expected
  benefit status. Missing full-paper evidence is NOT_VERIFIED rather than rated adequate.
  Independent closeout confirms no remaining scoped blocking findings.
- Final package gate PASS: 106 tests, self-contained links, authentic section and
  synthetic Architect artifacts. Installed-folder CLI tests execute copies without
  sibling skills. Original pipeline 501 tests PASS (4 existing skips), figure 47 PASS.
  These are mechanical/protocol tests plus bounded agent forward testing, not an
  accuracy benchmark or proof of every future scientific judgment.
- Root README indexes modes, triggers, installation and independent packaging. Skill
  documentation contains only runtime guidance, contracts and relevant examples.
  This root development note must remain on the development branch and be excluded
  from the final main tree.
