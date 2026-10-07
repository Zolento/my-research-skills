# Scientific Manuscript Reviser

A scientific manuscript architecture, auditing and revision skill. Its core object
is the scientific argument. Manuscript prose is one expression of that argument.

| Mode | Input | Output |
|---|---|---|
| Audit | Existing manuscript | Scientific/writing diagnosis, Well Supported, suggestions and Keep as is |
| Architect | Research materials, including incomplete notes | Supported theses, claim/evidence map, Compact or Full paragraph blueprint |
| Revise | Existing manuscript and explicitly resolved new narrative/evidence | Diagnosed, selected revision with invariance/style audit |

Suggest remains the default Audit presentation. Analysis-only requests do not edit.
Approved blueprints can guide one section at a time; whole-paper drafting is optional.

## Workflow

Existing text → protected facts → Scientific Coherence Audit → narrative diagnosis
→ language/style diagnosis → suggestion bank → optional revision → semantic
invariance audit → style validation.

Materials → normalization and sufficiency → the same scientific audit → supported
thesis/hierarchy → architecture alternatives → paragraph blueprint → independent
outline/alignment audit → explicit approval → section drafting and post-edit gates.

Scientific coherence uses a located typed graph and separate evidence, theory,
experiment, entailment, cross-section and counterfactual passes. Aggregation only
combines existing findings. No scientific validity is inferred from fluent prose.
Critical/major gaps remain visible; a plan cannot supply missing results.

## Core principles

The bank inspects ten categories, led by Scientific logic, Theory/proof, Experimental
design and Claim/conclusion validity, followed by Narrative, Paragraph structure,
Claims/evidence, Language/naturalness, References/presentation and Defensive language.
Important issues get different editorial or scientific repair paths with locations,
reasons, confidence, risk and work required. Do not invent suggestions for a quota.

Keep clear simple wording and author variation. Weak repetition/length/lexical cues
are candidates for contextual reading, not AI-authorship judgments. No fixed word
blacklist, synonym replacement program, randomization or AI detector objective.
Author samples produce descriptive characteristics, never copied sentences. Explicit
rules override inferred style and venue preferences. Unknown venue uses neutral style.

H1 forbids prose semicolon, colon, em dash and punctuation en dash, with technical
exemptions. H2 avoids stacked figure/table/section narration while retaining identifiers.
H3 retains genuine uncertainty and rejects unsupported confidence or self-diminishment.

## Mechanical helpers and semantic trust boundary

Install the skill with

```sh
npx skills add Zolento/my-research-skills -g -s scientific-manuscript-reviser -y
```

Python 3.9 or newer, with only standard-library runtime dependencies. From this directory

```sh
python3 scripts/validate_style.py manuscript.tex
python3 scripts/diagnose_patterns.py manuscript.tex
python3 scripts/audit_coherence.py manuscript.md --graph graph.json --report report.json
python3 scripts/validate_suggestions.py manuscript.md --bank bank.json --coherence coherence.json
python3 scripts/compare_invariants.py before.tex after.tex \
  --original-facts before-facts.json --revised-facts after-facts.json --audit audit.json
python3 scripts/architect.py check --material materials.json --graph graph.json \
  --report report.json --blueprint blueprint.json --audit outline-audit.json
python3 scripts/release_check.py
```

All helpers read inputs and print artifacts; no manuscript is overwritten. Mechanical
checks cover prose spans, obvious reference stacking, literal numbers, citations,
LaTeX structure and artifact/source integrity. Scientific meaning, naturalness,
defensiveness, proofs and experimental identification require structured local LLM
audits. Semantic FAIL is honored, missing/unknown audits remain NEEDS_REVIEW.
Digests prevent stale artifacts but do not authenticate or certify an evaluator.
No model API is called or simulated by the bundled helpers.

Exit 0 means the applicable gate passed, 3 means failed, 4 means review/input error.
Pattern candidates and proposed revisions are explicitly labeled as non-verdicts.
Release check exits 0 only when all package checks pass. A clean release tests the
software/protocol, not scientific correctness of every future paper.

## Examples

- [Real manuscript section](examples/real-section/README.md) has source attribution,
  a ten-category bank, limited-context scientific audit, minimal proposed revision
  and post-edit artifacts. It does not certify the full article.
- [Bounded Architect example](examples/architect-bounded/README.md) shows an argument
  matrix, paragraph roles, architecture choices and a complete synthetic protocol case.
- [Suggestion example](examples/suggestion-example.md) shows genuinely different repair paths.

## Known limits

The scanner is a lexical TeX subset, not expansion/compilation. Unknown constructs
need review. Token multisets cannot prove changed attachments are equivalent; the
independent semantic pass must check them. Theory audits are not formal verification.
Partial manuscripts cannot establish whole-paper coherence. Semantic contract tests
verify coverage and verdict handling, not automatic detection accuracy. No benchmark
against independent reviewer models, AI detectors or human editors is claimed.

## Recommended next evaluation

Use held-out, consented manuscripts and expert-labeled faulty/valid reasoning pairs.
Measure localized errors, false positives, preserved strengths, source coverage,
author voice and post-edit fact drift. Compare separate-pass audits to holistic review
without using reviewer scores as an objective. Evaluate TeX constructs with compilation
and improve domain-specific proof verification only when actual evidence warrants it.
