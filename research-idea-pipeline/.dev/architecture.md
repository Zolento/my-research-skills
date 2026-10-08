# CIE Architecture Gap Analysis

Branch: `feat/cognitive-insight-engine`. Base: `main` @ `1157d28` (= `origin/main`).
Scope: `research-idea-pipeline/` only. No schema migration, no ninth first-class object,
no second authoritative state, no new R stage, no parallel scheduler.

## 1. Audit baseline — what already exists (do not rebuild)

| Capability | Existing carrier | Evidence |
|---|---|---|
| Persistent scientific facts | `research-state.json`, 8 first-class arrays | `references/research-state-policy.md` §3 |
| Fact invalidation + one-hop propagation | `validity{status,reason,since_state_version}` (V18), V19, R11 fixpoint | `scripts/state_check.py` |
| Frozen predictions | `experiments[].preregistration.outcomes` + `frozen_at_state_version` (V21) | S5/V21 |
| Evidence tiers + claim status authority | `verification_tier` T0—T5, `status` enum (S3), V20, V22 | S3/V20/V22 |
| Outcome analysis | R9.O five judgments, five outcome classes | `references/evidence-outcome-analysis.md` |
| Failure memory | `failures[]` + `negative_knowledge[]` + stop rules | `templates/research-state.template.json` |
| Search-operator meta-memory | `scheduler.json` → `operator_stats.by_operator`, `recurring_failure_patterns` | `references/scheduler-policy.md` §4.1 |
| EIG producer/consumer split | `predicted_information_gain`, `observed_delta`, `actual_information_gain` | scheduler-policy §6.1 |
| Cross-stage ordering | 8-level `next_action_policy.priority` | scheduler-policy §3 |
| Bounded diagnosis | PEIG/AALG, shared route `.execution` ledger, STOP_DIAGNOSIS | `references/execution-identifiability.md` |
| Exploration operators | `P1`—`P6` + `local`, 12 operators, QD archive | `references/phase-r3-r6-discovery.md` |
| Structural equivalence audit | `structural_equivalence_check.py`, `assurance[]` | `references/structural-equivalence-policy.md` |
| Human views | `STATUS.md` (rendered), `INDEX.md`, `routes/<R>/docs/` | `references/project-layout.md` |

**Design consequences.**
1. Prediction freezing already exists canonically. CIE must **read** it, not re-freeze it.
2. Operator statistics already exist in telemetry. CIE must **reuse** `operator_stats`, not add a third store.
3. Claim status changes are already gated by R8/R10. Cognitive memory must be **read-only** on `claims[].status` and `contract`.
4. Extras are tolerated: `state_check.py` ignores unknown top-level and object keys (strict only inside
   `structural_signature` and `claims[].contract`). New validators run as **separate CLIs**, the EO1/EX1 pattern.

## 2. The four missing capabilities

| # | Capability | Missing piece | Where it attaches |
|---|---|---|---|
| 1 | Persistent cognitive memory | No mechanism/anomaly/competition/value structure; no revision log; no cross-session context recovery | route control plane `cognition/`; entry precondition; R3 read, R6/R8/R9.O/R10/R11 write |
| 2 | Prediction-first + anomaly + competition | Frozen outcomes are never compared to observations mechanically; no insight card; no distinguishability test; no diagnosis→intervention switch | R3—R6 (candidate), R8 (freeze digest), R9.O (compare), R10 (disposition) |
| 3 | Scientific value + adaptive discovery | EIG-only ordering; no decision-value/discovery-potential separation; no calibrated preference memory | R3—R6 + Meta-Controller; `scheduler.json` reuse |
| 4 | Discovery replay + verification | No replay harness, no leak guard, no metrics, no ablation | offline tooling + `release_check.py` step |

## 3. Where each capability attaches

```
R0/R1  contract + world model      ── CIE reads only (anchor is human-owned)
R2/R5  retrieval                   ── reads cognition brief retrieval cues
R3—R6  discovery                   ── writes mechanism / competition revisions; reads strategy priors
R8     evidence contract           ── CIE records a freeze digest of preregistration.outcomes
R9     execution                   ── unchanged
R9.O   outcome analysis            ── CIE compares frozen prediction vs observation
R10/R11 state update               ── CIE appends model revisions after the state transaction
R12/R13 narrative + review         ── unchanged, read-only view
R14    decision                    ── reads cognition brief, does not write cognition
```

## 4. Derived index vs persistent event — the split

| Layer | Carrier | Authority |
|---|---|---|
| Canonical | `research-state.json` | sole authority for scientific facts |
| Event | `cognition/model-revisions.jsonl` | append-only structural assertions **plus pointers**; cannot set epistemic status |
| Derived | `cognition/index.json`, `cognition/context-brief.md` | rebuildable from canonical + events; never authoritative |
| Authored intermediate | `cognition/insight-cards.jsonl` | candidate structure; classification computed from canonical refs, never self-declared |

Rule: a revision event may name structure (variables, conditions, predictions, competition links)
and must cite canonical ids. Every support level shown in the index is **recomputed** from
`verification_tier` / `strength` / `validity` / `status`. An event that tries to assert
`epistemic_status`, `claims[].status`, or a contract change is rejected by the validator.

## 5. Compatibility risk register

| Risk | Mitigation |
|---|---|
| Breaks S1—S7 / V1—V24 | Nothing is added to `research-state.json`; state digests asserted unchanged after build |
| Breaks rule-table parity | `state_check.py` not modified |
| Breaks scheduler semantics | `scheduler.json` is read-only for CIE; priors live in the derived index |
| Breaks `.dev/` or packaged-link rules | cognition paths are inside the route control plane, which is not part of the skill package |
| Third numeric scoring system | no composite score; value judgments are per-dimension assessments with evidence refs and uncertainty |
| Infinite attribution | reuse PEIG/AALG limits; add a decision-value switch, not a new budget |
| Self-certified novelty | insight class depends on canonical evidence tier, structural-equivalence audit required for `evidence_supported` |
| Future-information leak in replay | replay loader strips hidden fields; leak guard is a test |

## 6. Minimal-change budget

New files only, plus four doc insertions (SKILL.md, README.md, phase-r3-r6, phase-r8, phase-r9-r11)
and one `release_check.py` step. No change to: `state_check.py`, `evidence_outcome.py`,
`execution_gate.py`, `experiment_execute.py`, `structural_equivalence_check.py`, the state template,
the scheduler template, and the four schemas.
