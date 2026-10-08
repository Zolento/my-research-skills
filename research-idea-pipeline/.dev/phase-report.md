# CIE phase report — branch-local development record

Branch `feat/cognitive-insight-engine`, base `main` @ `1157d28` (= `origin/main` at start).
Scope: `research-idea-pipeline/` only. Nothing pushed, merged, tagged or released.

## 1. Commits

| # | Commit | Content |
|---|---|---|
| 1 | `c6c446b` | Phase 1 — persistent cognitive memory |
| 2 | `a411ebd` | Phase 2 — prediction / anomaly / mechanism competition, plus the Legacy Research Handoff (Phase 1 extension requested mid-flight) |
| 3 | `3433687` | Phase 3 — scientific value and adaptive discovery |
| 4 | `80fc873` | Phase 4 — historical replay, metrics, ablation, adversarial cases, full verification |
| 5 | (this commit) | Scientific-correctness fixes: P0-1 adjudication completeness, P0-2 evidence eligibility, P0-3 real distinguishability |

## 2. Files changed relative to `1157d28`

New

```
research-idea-pipeline/scripts/cognition.py
research-idea-pipeline/scripts/prediction_compare.py
research-idea-pipeline/scripts/legacy_handoff.py
research-idea-pipeline/scripts/strategy_memory.py
research-idea-pipeline/scripts/research_replay.py
research-idea-pipeline/scripts/test_cognition.py
research-idea-pipeline/scripts/test_prediction_compare.py
research-idea-pipeline/scripts/test_legacy_handoff.py
research-idea-pipeline/scripts/test_strategy_memory.py
research-idea-pipeline/scripts/test_research_replay.py
research-idea-pipeline/references/cognitive-memory-policy.md
research-idea-pipeline/references/prediction-anomaly-competition.md
research-idea-pipeline/references/legacy-handoff.md
research-idea-pipeline/references/scientific-value-adaptive-discovery.md
research-idea-pipeline/references/discovery-replay.md
research-idea-pipeline/docs/cognitive-insight-engine.md
research-idea-pipeline/examples/cognition/{README.md,state.json,model-revisions.jsonl,
                                             prediction-observation.json,insight-cards.jsonl}
research-idea-pipeline/examples/replay/README.md
research-idea-pipeline/examples/replay/adversarial/adv1..adv10.json
research-idea-pipeline/.dev/{architecture.md,agent-handoff.md,phase-report.md}   (branch-local)
```

Modified

```
research-idea-pipeline/SKILL.md                          §1.8, §1.9, §2 rows
research-idea-pipeline/README.md                         capability sections
research-idea-pipeline/references/invocation-prompts.md  §2 handoff precondition
research-idea-pipeline/references/research-state-policy.md §3.5 additive criterion slot
research-idea-pipeline/references/phase-r3-r6-discovery.md   CIE touchpoints
research-idea-pipeline/references/phase-r8-evidence-contract.md   freeze registration
research-idea-pipeline/references/phase-r9-r11-experiment-loop.md anomaly/revision writing
research-idea-pipeline/templates/research-state.template.json  sample criteria
research-idea-pipeline/scripts/release_check.py          steps 11—15
README.md                                                component description
```

**Deliberately unchanged:** `scripts/state_check.py`, `scripts/evidence_outcome.py`,
`scripts/execution_gate.py`, `scripts/experiment_execute.py`,
`scripts/structural_equivalence_check.py`, `scripts/render_status.py`,
`templates/scheduler.template.json`, and the four JSON schemas. S1—S7 and V1—V24 keep their
exact identity, and the release gate still proves the rule tables are verbatim identical.

## 3. Test results

| Gate | Result |
|---|---|
| `python3 scripts/release_check.py` | **PASS**, 15 steps |
| `python3 -m unittest discover -s scripts -p 'test_*.py'` | **1193 tests, OK, 3 skipped** (baseline before this branch: 919 tests, 3 skipped) |
| `cognition.py --selftest` | PASS (0 failures) |
| `prediction_compare.py --selftest` | PASS (0 failures) |
| `legacy_handoff.py --selftest` | PASS (0 failures) |
| `strategy_memory.py --selftest` | PASS (0 failures) |
| `research_replay.py --selftest` | PASS (0 failures) |
| `state_check.py --check examples/cognition/state.json` | exit 0 |
| `state_check.py --check templates/research-state.template.json` | exit 0 |

New tests by file (after the fix round): `test_cognition.py` 72,
`test_prediction_compare.py` 98, `test_legacy_handoff.py` 45,
`test_strategy_memory.py` 64, `test_research_replay.py` 61, plus the extended release-gate
step — all offline, no GPU, no network, no model call.

### Existing-test compatibility

All 919 pre-existing tests still pass unmodified except three assertions that asserted the
*absence* of a capability:

* `test_shipped_template_state_builds_with_zero_diagnostics` and
  `test_state_without_a_cognition_directory_is_readable` asserted "0 mechanisms" for a state
  with no revision log. A legacy project legitimately projects mechanisms now, so they assert
  zero diagnostics plus `origin: legacy_derivation` / `retrospective: true` instead — a
  stronger check than before.
* `test_broken_jsonl_line_is_reported_not_fatal` was updated for the loader's additional
  return value.

No parity, linter, link, deprecated-term or schema test was relaxed.

## 4. Phase-by-phase acceptance

**Phase 1 — persistent cognitive memory.** Old states stay compatible (the shipped template
builds with zero diagnostics). The index rebuilds to identical bytes from canonical state plus
the log. Support levels are derived, and a self-declared level becomes a `CM7` conflict.
Invalidated sources push derived memory out of hot recall. Failure memory is recovered with
its stop rules and retry conditions. Missing references, stale versions and wrong sources are
reported (`CM3`). Memory cannot write a claim status or an anchor (`CM2`), and the build is
byte-compared (`CM0`).

**Phase 2 — prediction, anomaly, competition.** A prediction is decidable only through a
frozen `criterion`; without one the verdict is `UNTESTABLE` and no success or failure may be
claimed. A silent rewrite of a frozen criterion is `PC4`; an amendment recorded after the
result is post-hoc and rejected. An invalid execution is `INVALID_EXECUTION`, never an
anomaly or a refutation. An observation with no preregistration is `EXPLORATORY_ANOMALY`. A
competition needs per-mechanism ownership and differing criteria — a rewording has no
distinguishing power. Repeated empty diagnosis changes behaviour instead of producing another
explanation. An insight card cannot certify its own evidence support (`PC7`).

**Phase 3 — value and adaptive discovery.** Decision value and discovery potential are judged
per dimension with sources and no total (`SV1`, `SV2`). Human preferences are read-only
(`SV3`). No operator is banned permanently; a downgrade needs two independent failures, a
scope and reactivation conditions (`SV5`); the exploration floor is mandatory (`SV7`). `P4`
receives typed skeletons only (`SV6`). `scheduler.json` is byte-identical after learning, and
one traceable chain runs from telemetry to a changed menu ordering.

**Phase 4 — replay and verification.** Ten adversarial cases are leak-checked before running;
a case that leaks refuses to run. Seven dimensions are scored independently with `null` for
unassessable. The ablation reproduces the capability ladder — baseline 0% vs full 100% on the
adversarial suite, with prediction quality `null` for arms lacking the comparator. An
undersized sample reports `insufficient_sample` and claims nothing. The end-to-end smoke test
runs state → hypothesis → frozen prediction → synthetic observation → revision → restart and
leaves the canonical state intact.

**Legacy Research Handoff (Phase 1 extension).** Detection refuses a fresh Bootstrap on an
initialized project. The audit is read-only and blocking errors write nothing. State,
scheduler and the `.execution` ledger are byte-identical. Cognitive memory is reconstructed
from canonical evidence and every entry is marked retrospective. No prediction is invented for
an experiment that never froze one. A second takeover is byte-identical; rollback removes only
what the handoff created.

## 5. Real versus synthetic

| Verified offline | Not verified |
|---|---|
| Structure, provenance, authority boundaries, determinism | real Agent A/B discovery performance |
| The comparator on synthetic source-bound observation packets | accuracy of the criteria on real measurements |
| The takeover on a real gate-passing state (`examples/cognition/state.json`) | a real multi-year legacy project |
| The ablation on ten synthetic cases | any claim about discovery ability |
| The adversarial suite against the offline runner | the same suite against a model-driven runner |

No model was called. No GPU was used. Every fixture carries a `SYNTHETIC FIXTURE` marker.
`research_replay` reports `undifferentiated_arms: [memory_prediction, full_cie]` — the two
arms are identical on all seven dimensions, and the report says so instead of implying that
the strategy layer was measured.

## 6. Failure scenarios and unresolved technical debt

1. **No real Agent A/B.** The framework is ready and pluggable (`--runner module:function`),
   but no model-driven runner exists. The README and the reference both say so.
2. **Legacy-mechanism reconstruction is conservative.** It cites `claims[].known_flaws` but
   does not derive `refuted` from them, because a V4 link is not a recorded refutation. A
   project that lost its revision log therefore shows fewer refutations than it may deserve;
   recording a revision event restores it.
3. **`criterion` coverage is not retroactive.** A legacy project whose frozen outcomes carry
   only prose compares as `UNTESTABLE`. The comparator refuses to invent a criterion, and the
   takeover reports it as `retrospective`.
4. **`LH7` blocks a state that `state_check` already rejects.** A terminal experiment with no
   preregistration cannot be taken over. This is deliberate — inventing a frozen prediction
   would be the exact fabrication the requirement forbids — but it means such a project needs
   a stage with R8/R10 authority before it can use the cognitive layer.
5. **The value indicators are structural, not semantic.** They read canonical relations
   (planned experiments, open uncertainties, repairs, evidence tiers), not the meaning of a
   sentence. A well-formed but scientifically weak candidate can still score `yes` on
   `changes_experiment_design`. The `objections` field and the R7/R13 attack surfaces remain
   the semantic check.
6. **`mechanistic_understanding` is vocabulary matching.** It is a proxy for what the system
   can articulate, not an expert judgement, and the offline runner's articulation basis was
   widened once already after the baseline scored higher than the full arm on it.
7. **Strategy-layer effect is unmeasured.** No metric separates `memory_prediction` from
   `full_cie`. Isolating the strategy layer needs a case family where the menu ordering is the
   only difference.
8. **`strategy_update` events are suggestions.** Nothing appends them automatically; a
   Discovery stage or the Meta-Controller must, with a real trigger. Until then the derived
   priors still change the recommendation, but the recorded history stays thin.

## 6b. Scientific-correctness fix round (P0-1 / P0-2 / P0-3)

### Root causes

| # | Problem | Root cause |
|---|---|---|
| **P0-1** | A partial submission could read as `PREDICTION_HELD` | `assess_experiment` iterated the **packet** (`packet["outcomes"]`) instead of the **frozen preregistration**. The submitted subset silently became the decision set, so selective submission manufactured support. |
| **P0-2** | `execution.validity = UNKNOWN` upgraded evidence | Only `INVALID` short-circuited. `UNKNOWN` fell through to the same code path as `VALID`, and the computed class occupied the single `outcome_class` field, so a downstream consumer could not tell a diagnostic comparison from qualified evidence. |
| **P0-3** | Differing signatures were treated as separating power | `distinguishability` compared criterion **digests** only. It never checked that the two predictions concerned the same observable, the same measurement basis, actually conflicting ranges, or whether the design could resolve the difference — and it never required a pre-declared decision rule. |

### Design decisions

1. **The frozen set is the complete decision set.** Adjudication walks
   `preregistration.outcomes[]` and looks each one up in the packet. Missing → `UNTESTABLE`
   (`missing_observation`); duplicate → that outcome is undecidable; extra → excluded and
   recorded in `unexpected_observations`. New class `PARTIALLY_ASSESSED` names "some decided,
   some not"; `PREDICTION_HELD` requires every adjudicated outcome decided and held.
2. **Branch mode is explicit, not implicit.** `observed_outcome` selects one frozen branch of
   a mutually exclusive preregistration. Non-selected branches are `not_selected`, not failed
   predictions; a second branch that also holds makes the freeze `UNTESTABLE`
   (`ambiguous_preregistration`, `PC8`). Without the selector, completeness mode applies.
3. **Two output slots, not one.** `outcome_class` is the *scientific verdict slot*;
   `diagnostic_outcome_class` carries the comparison. A world-claiming class
   (`PREDICTION_HELD` / `PREDICTION_DEVIATED` / `WITHIN_TOLERANCE`) may occupy the scientific
   slot only on `QUALIFIED_EVIDENCE`. `PARTIALLY_ASSESSED` and `UNTESTABLE` describe the
   adjudication, so they stay in the scientific slot even when the evidence is not qualified.
4. **Evidence eligibility is a first-class field.** `evidence_class`
   (`QUALIFIED_EVIDENCE` / `DIAGNOSTIC_ONLY` / `INSUFFICIENT_PROVENANCE`), `evidence_eligible`,
   `scientific_status`, `provenance_gaps` and `outcome_class_downgraded_from`.
   `evidence_transition_allowed()` is the comparator-side precondition; `compare
   --for-transition` exits 3 with blockers. R8/R10 and `evidence_outcome.py` /
   `state_check.py` keep their authority.
5. **Discrimination is arithmetic, not wording.** Four checks — comparability, conflict,
   resolution (`tolerance + noise/sqrt(n)`), pre-declared rule — over **every pair**, with the
   weakest pair as the witness. Four verdicts and 19 machine-readable reasons. The
   intervention must be actionable (`planned` / `running`). Free text and self-ratings are
   proven inert by test.
6. **Enum migration was checked first.** Verdict strings are consumed by
   `diagnosis_switch`, `prediction_compare`'s own CLI/selftest, docs and tests only;
   `cognition.py` keeps a deliberately *structural* `has_distinguishing_power` and now also
   exposes `discrimination_rule_present`. `OUTCOME_CLASSES` gained one value.

### Before / after, measured on the same inputs

The pre-fix module was loaded from `80fc873` and run against the post-fix fixtures:

| Scenario | Before | After |
|---|---|---|
| 2 frozen predictions, 1 submitted | `PREDICTION_HELD` | `PARTIALLY_ASSESSED`, `evidence_eligible: false` |
| `execution.validity = UNKNOWN` | `PREDICTION_DEVIATED` (scientific slot) | `UNTESTABLE` + `diagnostic_outcome_class: PREDICTION_DEVIATED`, not eligible |
| Two mechanisms on different metrics | `DISTINGUISHABLE` | `INSUFFICIENT_INFORMATION` / `different_observables` |
| Partially overlapping ranges | `DISTINGUISHABLE` | `NOT_DISTINGUISHABLE` / `overlapping_intervals` |
| `noise/sqrt(n)` swallows the gap | `DISTINGUISHABLE` | `NOT_DISTINGUISHABLE` / `within_uncertainty` |
| Conflicting ranges, no declared rule | `DISTINGUISHABLE` | `CONDITIONALLY_DISTINGUISHABLE` / `no_discrimination_rule` |
| Conflicting ranges + declared rule | `DISTINGUISHABLE` | `DISTINGUISHABLE` / `discrimination_rule_satisfied` |

### New tests and fixtures

* `test_prediction_compare.py`: 89 → 98+ tests covering partial submission, duplicates, extras,
  branch selection, exclusive-branch detection, `UNKNOWN`, incomplete provenance, time leak,
  the transition gate, different observables, different measurement bases, overlapping ranges,
  statistical uncertainty, `min_separation`, non-actionable interventions, prose inertness and
  the three-mechanism pairwise rule.
* `test_cognition.py`: cross-session refutation (5 tests) and invalidation reaching anomalies
  and competitions.
* `research_replay.py`: `ADV11` (partial submission) and `ADV12` (unknown validity) — the
  suite is now 12 cases; `prediction_quality` is unratable for a diagnostic comparison;
  `report_unqualified_result_as_held` is the new enforced invariant.
* `release_check.py` step 12 now injects: a one-of-two submission, a branch selection, a
  non-exclusive freeze, an unfrozen extra outcome, an `UNKNOWN` execution, and the four
  discrimination mutations.

### Unverified risks (this round)

1. **No real Agent A/B.** Unchanged: the fixes are verified offline; no model was called.
2. **Branch vs measurement selection is a judgement.** The comparator can prove a freeze is
   *not* exclusive; it cannot prove the analyst chose the right branch. A wrong but
   self-consistent selection is still possible.
3. **`provenance_gaps` is comparator-local.** It checks the fields the comparison depends on;
   it is not a substitute for the R9.O audit, and it deliberately does not re-implement it.
4. **`min_separation` is only meaningful for quantitative criteria.** For discrete label
   pairs the rule is not applied, because a label read has no threshold; directional pairs
   remain `CONDITIONALLY_DISTINGUISHABLE` because no effect size is declared.
5. **`measurement` is a free-text basis comparison.** It is an equality check on a declared
   string, not a semantic unit analysis.

## 7. `.dev/` disposition

| File | Disposition |
|---|---|
| `.dev/architecture.md` | `KEEP_BRANCH_ONLY` — the gap analysis was promoted into `docs/cognitive-insight-engine.md`; the working draft stays on the branch |
| `.dev/agent-handoff.md` | `KEEP_BRANCH_ONLY` |
| `.dev/phase-report.md` | `KEEP_BRANCH_ONLY` — the durable facts are in the architecture note and the reference documents |

Nothing under `.dev/` is required at runtime; deleting the directory leaves the release gate
green.

## 8. Final state

`git status` on the branch is clean after this commit. The branch is local and awaits review.
No push, no merge to `main`, no PR, no tag, no release.
