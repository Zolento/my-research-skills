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

With supplied source evidence, optional revision cycles run as evidence ledger → bounded
revision loop → revision impact analysis → pre-edit and post-edit gates → ledger update.
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
python3 scripts/evidence_ledger.py manuscript.md --ledger ledger.json --graph graph.json
python3 scripts/counterfactual_eval.py evaluation.json --detection detection.json
python3 scripts/revision_impact.py manuscript.md --before before.md \
  --original-facts before-facts.json --revised-facts after-facts.json --plan plan.json
python3 scripts/revision_loop.py loop.json
python3 scripts/evidence_core.py --self-check
python3 scripts/venue_registry.py venue-policies
python3 scripts/venue_registry.py venue-policies --venue CVPR --year 2027 --track main
python3 scripts/contribution_positioning.py --positioning p.json --ledger ledger.json \
  --registry venue-policies
python3 scripts/venue_audit.py --audit audit.json --positioning p.json --coherence report.json \
  --venue CVPR --year 2027 --track main --registry venue-policies
python3 scripts/venue_strategy.py --strategy s.json --blueprint b.json --positioning p.json \
  --material-numbers numbers.json --venue CVPR --year 2027 --track main --registry venue-policies
python3 scripts/venue_revision_impact.py --impact i.json --before p.json --after q.json
python3 scripts/submission_compliance.py --manifest m.json --venue CVPR --year 2027 \
  --track main --registry venue-policies
python3 scripts/venue_intelligence_core.py --self-check
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

## Evidence grounding

Version 0.2.0 adds four optional layers over the same scientific audit. Their contract is in
[evidence-grounding.md](references/evidence-grounding.md), and none of them replaces the
coherence audit or the semantic trust boundary.

- **Evidence Ledger** binds a claim to the source artifact that carries its evidence, with
  content location, state, applicability and a verifiable digest. Verified, reported,
  contradicted and unknown are different things, a cited paper cannot be `verified` by being
  read, and missing evidence stays distinct from unknown science.
- **Counterfactual Evaluation** validates paired correct/faulty cases across causal
  overreach, conclusion inflation, invalid controls, missing theoretical assumptions,
  unidentifiable experiments, evidence mismatch and cross-section contradiction, plus
  wording-only robustness cases. It scores a separately supplied detection result and never
  runs a detector, so detection and miss counts measure that artifact, not this skill.
- **Revision Impact Analysis** maps an edited location to the claims, evidence, theory,
  experiments and cross sections that depend on it. Language-layer edits take minimal
  sufficient verification, scientific edits take the full audit, and a lost limitation, a
  new unsupported assertion or an unverified inference raised to verified blocks acceptance.
- **Bounded Revision Loop** ties every round to a problem, a target change and completion
  criteria, does not re-propose resolved problems without new evidence, and distinguishes a
  met completion condition from a stop for no progress, disagreement or an iteration limit.

These layers bound the verification a change requires and surface what a human must decide.
They never certify a claim, promote an UNKNOWN to supported, or convert a disagreement into
a conclusion. Nothing here replaces scientific judgment with extra schemas.

## Venue intelligence

Version 0.3.0 adds a venue-aware layer over the same science. The governing rule is that
**scientific validity is venue-independent, while contribution positioning and submission
requirements are venue-dependent.** Changing the target venue may change framing, ordering
and which stated requirements apply. It may never change a support status, a scientific
finding or a critical gap. Contract: [venue-intelligence.md](references/venue-intelligence.md).

The venue layer is optional. With no venue, year and track the skill runs a venue-neutral
science audit, applies no mandatory rule, and never guesses the target from a manuscript's
topics.

- **Venue Policy Registry** (`venue-policies/`) is offline-first and source-bound. Each
  profile covers exactly one venue, year and track, and every rule quotes a saved official
  source verbatim, so a summary cannot masquerade as a published requirement. Rules are typed
  MANDATORY_POLICY, REVIEW_CRITERION, RECOMMENDED_PRACTICE, EMPIRICAL_CONVENTION or UNKNOWN.
  A rule is only in force for the year it was published for: a superseded policy is never
  inherited, and an unpublished policy stays UNKNOWN or PENDING. CVPR 2027 is the worked
  example, where its LLM policy is recorded as PENDING because the CFP says the guidelines
  are still being finalized.
- **Contribution Positioning** maps the skill's internal classes to a venue's official
  categories, which are never invented. Support status comes only from ledger evidence, and
  a novelty or priority claim requires an inspected prior-work record.
- **Venue-Aware Audit** evaluates eight criteria after the science audit and types every
  issue as SCIENTIFIC_DEFECT, CONTRIBUTION_GAP, VENUE_FIT_RISK, PRESENTATION_ISSUE or
  COMPLIANCE_ISSUE. Critical and major scientific findings must survive unchanged.
- **Venue Strategy** changes framing, ordering and emphasis. A framing needs a different
  scientific anchor, and an experiment needs a named logic gap, not a venue preference.
- **Submission Compliance** verifies only checkable requirements and reports hard policy
  separately from scientific quality. Page limits are judged on a compiled PDF; without one
  the count is UNKNOWN. AI-use disclosure is checked only against supplied records.
- **Venue Readiness** aggregates upstream verdicts with priorities and human decisions. It
  produces no acceptance probability and no weighted overall score.

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

Version 0.2.0 adds no scientific evaluator, and its limits are explicit.
The ledger gate verifies provenance, digests and declared states. It cannot decide whether
a source actually supports a claim, and it trusts the recorded state, so a mislabeled
verification stays mislabeled. The counterfactual harness is structurally tested, including
that it never runs a detector, but this skill's **semantic detection of faulty reasoning
remains unvalidated**: the bundled case set is author-constructed and the bundled detection
file is an illustrative placeholder, not a benchmark result. Impact analysis requires
declared edit metadata because a deterministic tool cannot infer that two differently
worded spans mean the same thing. The bounded loop enforces problem and stop bookkeeping,
not scientific progress; a loop can be well formed and still be scientifically wrong.

## Recommended next evaluation

Use held-out, consented manuscripts and expert-labeled faulty/valid reasoning pairs.
Measure localized errors, false positives, preserved strengths, source coverage,
author voice and post-edit fact drift. Compare separate-pass audits to holistic review
without using reviewer scores as an objective. Evaluate TeX constructs with compilation
and improve domain-specific proof verification only when actual evidence warrants it.
For the evidence layers, the next step is an independently produced detection artifact over
held-out cases, and a ledger built from real experiment data rather than a constructed
example, so the structural gates gain measured semantic backing.
