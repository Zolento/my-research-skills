# Evidence Outcome Analysis architecture

## Repository audit and constraints

Baseline is main 1ea0af1. The research pipeline release gate passes 501 tests with
four existing skips. R9 executes X1–X6 experiments and records provenance. R8 freezes
preregistration. R10 alone handles scientific claim downgrades and refutations;
R11 merges evidence, updates uncertainty and propagates invalidation. R14 uses
continue/pivot/archive/submit. Failure Memory already preserves failures through V4
and V12. V20 enforces evidence tiers and V21 preregistration timing. Narrative R12
is a state view. Its scientific inputs must never be repaired by writing agents.

Two requested shapes conflict with current invariants. Adding top-level negative
knowledge as a ninth first-class object would violate the scientific/control-plane
partition. Replacing existing claim/QD/decision enums would break consumers. The
minimal solution is additive fields on the existing objects, with a new internal
R9.O capability between result collection and R10/R11; R0–R14 are not renumbered.

## Proposed architecture

R8 freezes experimental protocol and project replication criteria. R9 collects a
source-bound result packet. R9.O generates an analysis proposal and an independent
local audit; it does not edit state. Validation separates execution validity,
identification, scientific outcome, scoped claim/hypothesis effects and attribution.
R10/R11 apply the accepted proposal to a copy, record exact before/after provenance,
append evidence/failure/uncertainty objects, enforce existing gates, then persist.
A separate Assurance verdict gates CONTINUE/RETRY/REDESIGN/PIVOT/STOP/HOLD before
any next execution. Per-target mixed decisions never collapse into route success.

- experiments[].outcome_analysis stores packet, analysis, audit, state delta and
  history. New outputs retain exact result sources and hashes, not only a summary.
- claims/hypotheses[].scoped_outcomes and outcome_status separate scientific support
  from the existing claim and QD lifecycle enums. Local refutation stays local.
- failures[].negative_knowledge stores ruled-out and surviving explanations, retry
  and revisit conditions. failures[].stop_rules blocks recurring scoped protocols.
- uncertainties[] remains the open-question carrier. R14's enum remains unchanged;
  experiment decisions are scientific recommendations, not route-anchor authorization.
- contract.outcome_policy explicitly enables strict terminal-result coverage and
  freezes replication criteria. Legacy states remain readable; adoption never invents
  historical analyses. Unanalysed historical results must be processed before strict
  mode can accept the state. New R0 states enable this policy with empty arrays.

The scripts mechanically validate citations, transitions, replication references,
stop-rule applicability, provenance and transaction integrity. They do not infer
validity, causal attribution or scope equivalence from arbitrary prose or logs.
Those require a separate source-bound semantic audit with PASS/FAIL/UNKNOWN. Missing
or unknown audits block application. No invalid experiment falsifies a proposition.
A central experimental hypothesis cannot be automatically falsified by one run.

## Implementation and verification plan

1. Define schemas, routing and additive policy, preserving all frozen enums.
2. Build read-only validation, scoped analysis and transactional state update helpers.
3. Integrate mandatory outcome coverage with state_check and planning constraints.
4. Cover the eighteen requested counterexamples plus attacks against source binding,
   local scope, stop-rule release, repeated results and assurance decisions.
5. Add positive, negative, invalid and pivot executable examples to the release gate.
6. Run original and new tests, independent bounded forward test and final review.

Development notes remain at branch root docs and are excluded from any future main
merge. Runtime references contain only skill guidance and relevant examples.

## Implementation review

The first transition suite passed 31 tests. A second review added refusal of
stopped executions, stale-decision HOLD, policy-removal detection, alternative
assessment binding, explicit cleared holds and no-overwrite output. The expanded
suite passes 38 tests. A mixed source packet now separately records performance,
mechanism and stress outcomes rather than changing only metadata verdicts.

Pending results stay in running pipeline lifecycle with result_pending until the
receipt and terminal state can be recorded atomically. Invalid attempts preserve
previous scientific support; uncertainty and local evidence receive provenance.
Historical adoption returns an unaccepted backfill snapshot until coverage is
complete. Flat validation contexts avoid recursively expanding source histories.

An independent forward test used only a source state, raw numeric packet and the
skill instructions. It preserved uncertain validity, accepted a bounded unresolved
receipt and returned HOLD without Assurance. Exact scope binding required a label
correction; the limitation is documented. Its observation that the legacy experiment
interpretation remained stale led to synchronizing the audited scientific summary.
This was an isolated same-model protocol exercise, not an independent model benchmark.

A further compatibility conflict is V3: an ungrounded claim cannot have any E adjacency,
even negative adjacency. WEAKENED now preserves its ungrounded lifecycle, records the
scientific outcome independently, and links negative E via claim_target, receipt and
Failure Memory. Supported claims can downgrade to partially-supported; FALSIFIED
claims can become contradicted through the existing R10 disposition. No original
rule is relaxed and no negative result manufactures positive support.

## Final validation

The final Evidence Outcome suite passes 47 tests, including all eighteen requested
counterexamples and source/history/planning/decision mutations. The complete pipeline
release passes 548 tests with four unchanged baseline skips, original S1–S7/V1–V24
parity, read/write parity, Structural Equivalence, Rhetorical Realization and all
five shipped outcome transactions. The unchanged manuscript reviser release passes
106 tests and the figure architect passes 47 tests. git diff --check is clean.

The generic system skill validator rejects the pre-existing argument-hint frontmatter
on both main and this branch. That existing interface was preserved. The repository's
release validator and its frontmatter/link/package checks pass. This is not described
as a new runtime error or as an all-model scientific accuracy guarantee.

Followups remain plans. apply does not execute them or write scheduler telemetry;
the R11 caller retains its original EIG and scheduling responsibilities. The independent
review's conservative unknown-validity path is compatible with that division.
