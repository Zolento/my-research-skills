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

## 6c. Third fix round — Prediction Integrity / Evidence Qualification / Insight Certification

### Root causes

| # | Symptom | Root cause |
|---|---|---|
| P0-1 | A packet that declared `observed_outcome` **after** seeing the numbers had only the favourable branch adjudicated, and read as `PREDICTION_HELD` with qualified evidence | Branch mode was opened by the *packet*, not by the freeze; non-selected branches were never evaluated unless the packet volunteered them; exclusivity was inferred from a reported second branch instead of from the frozen criteria |
| P0-2 | A packet with a missing source, a wrong digest or an empty `location` was reported (`PC2`) and still came back `evidence_eligible: true` | Two independent opinions: `observation_errors()` reported, while `assess_experiment` decided eligibility from a disjoint chain of `if`s that never looked at the source result |
| P1 | A card reached `evidence_supported_insight` on the strength of "T2 evidence somewhere in the same experiment" plus "an assurance entry exists" | Certification was experiment-level, not prediction-level; the assurance's actual audit result was never read; direction, scope and cross-prediction binding were unchecked |
| same root cause (found by the chain audit) | A project holding insight cards or a `scheduler.json` was **refused** by Legacy Handoff with a false `LH12` index-drift finding | `build`/`check` rebuilt the projection with cards+scheduler+audits, while `legacy_handoff` rebuilt it with state+revisions only |

### Fixes (one mechanism each)

* `branch_rule_errors()` (`PC10`) + `criteria_mutually_exclusive()`: branch mode requires a frozen
  `outcome_mode: "branch"` with `branch_rule.{selector, quantity, branches}`; `branches` must be an
  exact partition of the frozen outcomes; all branches must share the observable and measurement
  basis; exclusivity is **computed** from the frozen criteria. Anything else falls back to
  completeness mode, which is also the default for a freeze that declares nothing.
* `_adjudicate_branch()`: exactly one raw observation, its `source.kind`/`location` must equal the
  frozen `selector`, and that one observation is evaluated against **every** frozen branch. The
  selected branch is derived; `observed_outcome` is only a claim that must agree. Non-selected
  branches land in `excluded_branches[]` with the verdict that excluded them.
* `freeze_digest()` now covers `outcome_mode` and `branch_rule`; the pre-round-3 payload is accepted
  only when the freeze declares neither, so old projects keep reading clean and a retro-fitted branch
  rule changes the digest.
* `qualify_evidence()` (schema `evidence-qualification@1`, sub-checks `PQ1`—`PQ8`) is the single
  authority. `assess_experiment` fills `evidence_class`/`evidence_eligible`/`scientific_status`/
  `provenance_gaps` from its block only; `evidence_transition_allowed` reads the block, refuses a
  block produced for another packet (`packet_digest`) and re-derives the state-only preconditions.
  Blocking failure → `INSUFFICIENT_PROVENANCE`/`NO_INFERENCE`; diagnostic failure →
  `DIAGNOSTIC_ONLY`; both are `evidence_eligible: false`.
* `_insight_certification()` (`IC1`—`IC6`, reported as `PC11`): explicit prediction/experiment
  binding, referenced claims valid and not contradicted, the card's **own** prediction–observation
  packet re-qualified and adjudicated `PREDICTION_HELD`, a consistent R9.O receipt in the supporting
  direction at `T2`+, canonical evidence bound to that experiment and mechanism with a matching
  direction, and an `assurance[]` entry whose `audit_ref` loads a SENA artifact that passes
  `structural_equivalence_check` with a non-equivalent verdict for the referenced candidate.
* `cognition.projection_inputs()`: one reader for the out-of-state projection inputs, used by
  `_load_inputs`, `legacy_handoff.compatibility_audit` (`LH12`) and `_take`.

### Authoritative call path for evidence qualification

```
observation packet ──► observation_errors()  (PC2, shape/provenance reporting)
                          │
packet + state + adjudication ──► qualify_evidence()  (PQ1—PQ8, the only eligibility decision)
                          │
                          ├─► assess_experiment(): evidence_class / evidence_eligible /
                          │     scientific_status / provenance_gaps / outcome_class slot
                          ├─► evidence_transition_allowed(): transition allowed? (re-derives state
                          │     preconditions, refuses a foreign or forged block)
                          ├─► op_compare --for-transition: exit code
                          ├─► research_replay decision + metrics
                          └─► classify_insight() → IC3 (the certified prediction's adjudication)
```
`check_freezes()` (`PC4`/`PC5`) and `branch_rule_errors()` (`PC10`) feed `PQ2`/`PQ8`; `cognition`
and `state_check` keep their own authority over claim status, verification tier and the R8 contract.

### Adversarial cases before/after

Measured with `.dev/adversarial-probe.py`, which loads the previous module (`5279b1f`) from git and
runs both versions on the same inputs:

| Case | Before (`5279b1f`) | After |
|---|---|---|
| 2 independent predictions, only `O1` submitted, `observed_outcome` declared | `PREDICTION_HELD`, eligible, transition allowed | `PARTIALLY_ASSESSED`, not eligible |
| legitimately frozen branch, one raw observation | `PREDICTION_HELD`, eligible | `PREDICTION_HELD`, eligible, `O2` excluded by a recorded condition |
| branch declared, rule never frozen | `PREDICTION_HELD`, eligible | completeness mode, not eligible (`PC10`) |
| declaration contradicts the raw observation | `PREDICTION_DEVIATED`, eligible | `UNTESTABLE`, not eligible |
| branches not mutually exclusive | `PREDICTION_HELD`, eligible | refused, completeness mode |
| observation source missing | `PREDICTION_HELD`, eligible | `UNTESTABLE`, not eligible (`PQ4`) |
| source digest mismatch | `PREDICTION_HELD`, eligible | `UNTESTABLE`, not eligible (`PQ4`) |
| branch basis outside the frozen selector | `PREDICTION_HELD`, eligible | `UNTESTABLE`, not eligible (`PQ5`) |
| hand-written `evidence_eligible: true` | transition allowed | transition refused |
| `T2` evidence bound to another prediction of the same experiment | certified | lower class (`IC5`) |
| assurance present, audit result unknown | certified | lower class (`IC6`) |
| audit entry with `discriminating_test: "TBD"` | certified | lower class (`IC6`) |
| audit verdict `equivalent` | certified | lower class (`IC6`) |
| prediction not held | certified | lower class (`IC3`) |
| fully bound card (positive path) | certified | certified |

### Files changed in this round

Code: `scripts/prediction_compare.py`, `scripts/cognition.py`, `scripts/legacy_handoff.py`,
`scripts/release_check.py`, `scripts/research_replay.py`.
Tests: `scripts/test_prediction_compare.py` (+45), `scripts/test_cognition.py` (+9),
`scripts/test_legacy_handoff.py` (+2), `scripts/test_research_replay.py`.
Fixtures: `examples/cognition/state.json` (frozen branch declaration),
`examples/cognition/model-revisions.jsonl` (freeze digest + mode), `examples/replay/adversarial/`
(14 cases, `adv13`/`adv14` new).
Docs: `references/prediction-anomaly-competition.md`, `references/research-state-policy.md` §3.5,
`references/cognitive-memory-policy.md`, `references/discovery-replay.md`,
`docs/cognitive-insight-engine.md`, `SKILL.md`, root `README.md`, both fixture READMEs.
Unchanged: `state_check.py`, `evidence_outcome.py`, `execution_gate.py`, `experiment_execute.py`,
`structural_equivalence_check.py`, `render_status.py`, both templates, the four schemas.

### Remaining risk

* No real Agent A/B and no real prediction–observation packet; the positive certification path is
  exercised against in-memory SENA artifacts.
* The freeze digest protects a branch declaration only when the revision log recorded one; a project
  that never ran `cognition build` has no digest, so a post-hoc `branch_rule` is caught by the shape
  and exclusivity checks (`PC10`) but not by `PC4`.
* Branch selection remains a human judgement about *which* branches are the right ones; the
  comparator proves partition, freeze and traceability only.
* `load_audits` resolves `audit_ref` as `route_dir / assurance/structural-equivalence/<basename>`,
  mirroring `structural_equivalence_check`; an artifact stored elsewhere is not found (fail closed).


## 6d. Final round — observation schema gate, prediction-level binding, scope coverage

### Root causes (all reproduced before the fix)

| # | Symptom | Root cause |
|---|---|---|
| P0 | A packet with a wrong/missing `schema` id was reported as `PC2` and still returned `evidence_eligible: true` (also: illegal `observed_outcome` type; an `observed_outcome` naming a non-existent outcome was silently ignored) | `qualify_evidence`'s `PQ4` only consumed the *source* half of the observation validator; the rest of the schema report never reached eligibility |
| P1a | One evidence object (no `prediction_ref`) certified **both** `X1:O1` and `X1:O2` cards | `_evidence_prediction_point` returned "no finding" when `prediction_ref` was absent, so "same experiment + same claim + same mechanism + same metric" stood in for prediction identity |
| P1b | `_scope_within` was `left in right or right in left`: `"brain"` matched `"brain-shifted"`, `"MRI"` matched `"MRI-3D"`, and a single-centre evidence scope (`"数据集 A / 中心 C"`) was treated as covering the whole dataset | substring containment is not a scope relation, and it was symmetric, so it could not even express direction |
| same class | A `prediction_freeze` record with no `freeze_digest`, or registered in a different round (`PC5`), was reported hard and did not block the gate | `PQ8` took only `PC4` from `check_freezes` |

### Fixes

* `PQ4` = the complete `observation_errors()` result (`observation_schema_and_sources`). The
  invariant is structural: whatever the validator refuses, the gate refuses. Informational
  extra keys are not schema errors and keep qualifying; the diagnostic comparison is still
  computed into `diagnostic_outcome_class`.
* `PQ3` also fails when a declared `observed_outcome` is not one of the frozen outcomes.
* `PQ8` consumes every non-warning `check_freezes` finding (`PC4` rewrite **and** `PC5`
  unverifiable freeze).
* `_evidence_prediction_point(evidence, experiment_id, outcome_id, uniquely_determined)`:
  an explicit `prediction_ref` must match exactly; the only other route is a freeze with
  exactly one outcome. No retro-fitting of legacy evidence.
* `scope_covers()` + `normalize_scope()` + `normalize_region()` replace `_scope_within`:
  structured regions decide constrained-subset coverage (extra evidence constraint →
  `region_narrower`; conflicting axis → `region_conflict`), legacy strings require normalized
  exact equality, mixed/unknown shapes are `unknown_scope_shape` and refused.
  `evidence[].scope_region` is registered as an optional additive slot
  (`research-state-policy.md` §3.2 + template).

### Before/after (`.dev` probe, same inputs)

| Case | Before | After |
|---|---|---|
| wrong `schema` id | `evidence_eligible: true`, transition allowed | `PQ4` failed, not eligible |
| missing `schema` | eligible | `PQ4` failed |
| illegal `observed_outcome` type | eligible | `PQ4` failed |
| `observed_outcome` not frozen | eligible, no diagnostic | `PQ3` failed |
| evidence without `prediction_ref`, 2-outcome freeze | certified `X1:O1` **and** `X1:O2` | both stay `predictive_insight_candidate` |
| `"brain"` vs `"brain-shifted"` | covered | `not_equal` |
| `"MRI"` vs `"MRI-3D"` | covered | `not_equal` |
| `"数据集 A / 中心 C"` vs `"数据集 A"` | covered (generalised) | `not_equal` |
| structured evidence narrower than claim | n/a | `region_narrower` |
| structured evidence broader than claim | n/a | `region_covers` |
| freeze digest not recorded (`PC5`) | eligible | `PQ8` failed |

### Compatibility

* Old string scopes still read and still certify on exact match; old evidence without a
  binding keeps the lower class (no auto-fill).
* `evidence[].scope_region` is optional; the template entry is `null` and `state_check`
  ignores it, so S1—S7 / V1—V24 are untouched.
* The real legacy project (`3D_ZS_SSL`, 26 experiments, no `criterion`) still re-reads,
  `audit blocking = 0`, `check` exit 0, `take` idempotent, canonical byte-identical.

### Remaining, not fixed in this round

* `PC5` only reaches the gate when the caller supplies the revision log (`op_compare` does,
  the library call `assess_experiment(state, packet)` does not). Documented, low severity.
* `min_separation` remains meaningful only for quantitative criteria; `measurement` remains a
  declared-string equality check.
* No real Agent A/B, no real observation packet: the positive certification path is exercised
  against in-memory synthetic SENA artifacts.


## 9. v2.3.1 — Research Preset Library, Intent Router, Loop Recovery, Self-Evolution

### Reuse inventory (audited before writing code)

| Existing capability | Reused as |
|---|---|
| `state_check.py` (`S1`—`S7`/`V1`—`V24`) | preset/trigger hard gate (`PR1`, `PR4`) |
| `cognition.py` (`CM0`—`CM10`, `projection_inputs`) | drift/memory signals, projection rebuild |
| `prediction_compare.py` (`PQ1`—`PQ8`, `diagnosis_switch`, `trailing_zero_streak`) | stagnation/conflict signals, behaviour switch |
| `strategy_memory.py` (`recommend_strategy`, `operator_priors`, `strategy_updates`) | self-evolution |
| `research_replay.py` | `discovery-replay` preset |
| `legacy_handoff.py` | `research-recovery` preset |
| `execution_gate.py` / `experiment_execute.py` | action legality, PEIG/AALG in recovery plans |
| `evidence_outcome.py` | R9.O/R10/R11 routing for failure and conflict repair |

### Gap found by the audit

`recommend_strategy()` produced menu/operator/shift but **nothing consumed them**; the scheduler
ordered `next_actions[]` by its own `EIG ÷ cost` rule; `strategy_memory.py apply` only printed
suggestions. The loop was therefore open: a strategy update could not reach a dispatch.

### Added

* `scripts/preset_router.py` — 16-preset registry, intent resolver (explicit/alias/intent/entry/auto,
  negation, exact-tie least privilege, expert `phase=` passthrough, read-only safety, descriptive →
  diagnose + confirm), 11 machine signals, recovery guard + ledger, 16 handlers, CLI
  (`list`/`resolve`/`inspect`/`check`/`trigger`/`run`/`record`), selftest.
* `presets/*.md` — 9 files, 16 protocols, nine fixed sections; §6 is generated from what the handler
  actually returns, and `test_preset_router` asserts the parity.
* Strategy Decision Adapter in `strategy_memory.py`: `strategy_decision()`,
  `record_strategy_decision()`, `latest_strategy_decision()`, CLI `decide [--record]`; `apply` is now
  explicitly recommendation-only (`writes: []` + note).
* `references/preset-policy.md` (`PR1`—`PR9`), `scheduler-policy.md` §4.2, `SKILL.md` §1.10,
  component README, root README, `invocation-prompts.md` §0.1.
* `scripts/test_preset_router.py` — 53 tests in four groups.
* `release_check.py` step 16.

### Bugs found and fixed while building

1. Generator wrote the throwaway fixture path into shipped protocol files → templated `<state>`.
2. `context_drift` could never fire (the context used the in-memory rebuild *as* the stored index) →
   the adapter now separates the on-disk index (drift) from the projection (content).
3. `paradigm-escape` returned fixed prose → now derived from the project's claim/mechanism/unknowns/
   recommended shift, and flagged `candidate_is_a_scaffold`.
4. Ambiguity threshold was too loose (0.5 score gap) → exact ties only.
5. The first demo fixtures were invalid states; the trigger correctly refused them (V4/V21) — kept as
   evidence that recovery refuses to run on a broken canonical state.

### Verification levels

* **L1** ✅ static review + 53 unit tests + selftest (≈120 checks) + registry/protocol parity.
* **L2** ✅ synthetic end-to-end on the real CLI/interfaces: trigger → select → guard → record;
  adapter with/without memory; telemetry record; next-round consumption; cross-session replay.
* **L3** ❌ **not performed**: no real research A/B; adoption ≠ capability.

### `.dev/` disposition

`plan.md`, `architecture.md`, `agent-handoff.md`, `phase-report.md`, `adversarial-probe.py`,
`gen_presets.py` → `KEEP_BRANCH_ONLY` (no runtime dependency; the protocol files were generated once
and are asserted by tests, so deleting `.dev/` cannot break the build).


## 10. v2.3.1 integration of the provided CIE Preset Library

### What was integrated as data (not pasted as prose)

| Provided file | Placement | Authority |
|---|---|---|
| `shared-contract.md` | skill root | common execution/evidence/memory contract loaded before any preset |
| `preset-registry.json` | skill root | source of truth for ids, entries, triggers, scopes, protocol paths, 16×3 intent examples |
| `presets/<id>.md` (16) | `presets/` | protocol prose kept **verbatim**, re-hosted inside the repo's nine machine-checked sections |
| `router-fixtures.json` | skill root | intent base test: 48 positive + 5 guarded cases |
| `ALL-PRESETS.md`, `INTEGRATION.md` | `.dev/provided/` | branch-local reference (a combined 16-in-one file would invite bulk injection) |

### What was kept from this repository (stricter, not replaced)

privilege tiers over the provider's scope labels, clause-scoped negation, ambiguity → least
privilege, one-protocol loading, machine signals + cooldown/attempt guard + ledger, engineering-
failure-never-science, the Strategy Decision Adapter, `PR1`—`PR9` checks and the release gate step.

### Defects found and fixed during integration

1. **Negation leaked across clauses** ("不要审查，我只想知道下一步方案" was refused entirely) →
   negation is decided inside one clause.
2. **Duplicate `scope_rank`** (the older one referenced the removed `SCOPE_RANK`) → single definition.
3. **Signal firing ignored registry-declared signals** (paradigm-escape could never be recommended) →
   firing follows the preset's declared signals; `AUTO_SIGNAL_MAP` is a parity anchor only.
4. **Confirmation rule used the raw scope** (`execute` only) → now privilege-based, so repair
   protocols also ask before acting on a symptom-only report.
5. **User presets would have auto-executed** if the registry trigger were honoured naively → a
   user preset can only be `recommended_only`.

### Verification levels

* **L1** ✅ 63 router tests (intent/registry/loop/scientific/adapter/integration) + selftest.
* **L2** ✅ synthetic end-to-end through the real CLI: 53/53 provided fixtures, one-protocol load,
  trigger → guard → record, adapter with/without memory, telemetry, cross-session replay.
* **L3** ❌ not performed (no real research A/B).
