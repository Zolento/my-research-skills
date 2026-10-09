# v0.2.0 Evidence-Grounded Manuscript Revision — development plan

Branch: `scientific-manuscript-reviser/evidence-grounding-dev`
Worktree: `skills-dev/scientific-manuscript-reviser/evidence-grounding-dev`
Base: `ea0214e` (main), skill version 0.1.0
Scope: `scientific-manuscript-reviser/` only. No other skill is touched.

## Baseline (recorded before any edit)

- Regression: `python3 -m unittest discover -s tests -p 'test_*.py'` in the skill dir
  → **108 tests, OK**.
- `python3 scripts/release_check.py` → **PASS** (Regression tests / reference links / examples).
- Note: running discovery from the repository root instead of the skill dir collects fewer
  tests. The canonical invocation is from the skill directory. Do not "fix" this by adding
  `__init__.py`; it is existing behaviour.

## Objective

Add four capabilities without weakening the three existing modes or any existing
scientific invariant:

1. **Evidence Ledger** — optional source-artifact record per claim.
2. **Counterfactual Evaluation** — paired correct/faulty reasoning harness with
   separately measured detection accuracy.
3. **Revision Impact Analysis** — edited location → dependent scientific elements.
4. **Bounded Revision Loop** — problem-driven iteration with explicit stop conditions.

## Design decisions (rationale)

D1. **`scripts/evidence_core.py` is the single contract authority.** It re-exports
    `compare_invariants.digest` and `validate_style` enums rather than defining parallel
    vocabulary. Existing scripts are **not** refactored: zero regression risk, and the
    v0.1.0 scientific layer stays byte-identical.

D2. **v0.2.0 is additive.** No existing artifact schema, enum or gate changes. New
    artifacts are separate, so old examples and installed copies keep passing.

D3. **A text artifact can never be `verified`.** Reading a paper is source inspection of
    a *report*, not verification of a scientific claim. This is the concrete reading of
    "不得将文本引用自动视为科学验证" and it is enforced mechanically, not by prose.

D4. **The harness never runs a detector.** `counterfactual_eval.py` validates a supplied
    detection artifact. Structural checks (schema, coverage, pairing) and measured
    semantic accuracy are reported as **separate** trust boundaries, so a passing harness
    cannot be reported as evidence of semantic detection ability.

D5. **`no_evidence` is distinct from `unknown`.** Missing evidence is not unresolved
    science, and it must not read as one.

D6. **Language-layer edits get minimal sufficient verification; scientific edits get the
    full audit.** Deleting or weakening a limitation is not text-only. A repair whose
    `requires` is reanalysis/new experiment/new theory forces `scientific_content`.

D7. **No new schema where an existing one fits.** The ledger reuses the argument-graph
    node ids for claims instead of inventing a claim registry.

D8. **Not bundling a scientific evaluator.** No model API is added or simulated. Every
    new gate is deterministic verification of structure, provenance and declared
    judgments, matching the v0.1.0 trust boundary.

## Workstreams (disjoint write scopes)

| WS | Owner | Files |
|---|---|---|
| W0 | Lead | `scripts/evidence_core.py`, `references/evidence-grounding.md`, `.dev/plan.md` |
| W1 | ledger-dev | `scripts/evidence_ledger.py`, `tests/test_ledger.py`, `examples/evidence-ledger/*`, `references/evidence-ledger.md`, `templates/evidence-ledger.md` |
| W2 | counterfactual-dev | `scripts/counterfactual_eval.py`, `tests/test_counterfactual.py`, `examples/counterfactual/*`, `references/counterfactual-evaluation.md` |
| W3 | impact-dev | `scripts/revision_impact.py`, `scripts/revision_loop.py`, `tests/test_impact.py`, `tests/test_revision_loop.py`, `examples/revision-impact/*`, `references/revision-impact.md`, `references/bounded-revision-loop.md` |
| W4 | Lead | `SKILL.md`, `README.md`, `references/` routing lines, `scripts/release_check.py`, `tests/test_package.py`, `tests/test_v020_package.py` |

## Stop conditions

Do not push, merge, tag or publish. Do not modify `research-idea-pipeline/` or
`academic-figure-draft-architect/`. Stop for human review after local commits and
verification.
