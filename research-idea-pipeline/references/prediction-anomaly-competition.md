# Prediction, Anomaly and Mechanism Competition — R3—R6, R8, R9.O, R10

An agent that explains results after the fact has not tested anything. This capability
forces a mechanism model to exist *before* the observation, compares the two mechanically,
and refuses to let a rewording count as a competing explanation.

It is not a new stage and not a new state object. It reads and writes the carriers that
already exist: `hypotheses[]`, `claims[].contract`, `experiments[].preregistration`,
`evidence[]`, `failures[]` and the cognitive revision log. See
[cognitive-memory-policy.md](cognitive-memory-policy.md) for the memory layer and
[research-state-policy.md](research-state-policy.md) §3.5 for the frozen `criterion` slot.

## 1. Mechanistic world model

A mechanism recorded by the engine must be explicit about what it claims, and must not
silently promote an analogy into a proof:

| Field | Meaning |
|---|---|
| `core_variables` | the quantities the mechanism is about |
| `dependencies` | directed relations between them |
| `necessary_conditions` | what must hold for the mechanism to apply |
| `boundaries` | the regime inside which it is claimed |
| `invariants` | what should not change under the claimed operation |
| `counterexamples` | observed violations, with their canonical source |
| `pending_predictions` | frozen prediction references, `"<XID>:<OID>"` |

**Epistemic kinds must stay distinct.** A mechanism derived from a proof, a causal
hypothesis, an empirical correlation and a heuristic analogy are different claims, and the
engine must not present them with one voice. The discriminating rule that is enforced
mechanically is the support ladder (see the memory policy): the *level* of a mechanism comes
from canonical evidence, never from its prose. A remote analogy therefore lands at
`hypothesis` unless independent evidence raises it, and the four-dimensional correspondence
of `P4` remains a structural argument, not an isomorphism proof
([phase-r3-r6-discovery.md](phase-r3-r6-discovery.md)).

Not every question needs a causal graph. A mechanism with only a boundary and a falsifier is
legal; it simply produces no discriminating prediction, and the competition check will say so.

## 2. Prediction-first protocol

Every serious mechanism candidate should carry: its own prediction, at least one meaningful
rival, where the two differ, the intervention that separates them, and what either result
would mean. When no operational prediction can be produced, the candidate is marked
**exploratory** and may not be described as tested.

Predictions are frozen where the pipeline already freezes them — `preregistration.outcomes[]`
at `frozen_at_state_version`. No second prediction schema exists. What Phase 2 adds is the
ability to *decide* them:

```json
{"id": "O1", "observation": "解耦后落差下降 ≥ 0.5 dB",
 "criterion": {"kind": "quantitative", "quantity": "落差变化（dB）",
               "expected_range": [-3.0, -0.5], "tolerance": 0.1,
               "measurement": "cross-centre PSNR difference, mean over centres",
               "noise": 0.4, "sample_size": 9, "min_effect": 0.5,
               "rule": "给人读的说明；不参与判定"},
 "update": [{"target": "C1", "op": "strengthen"}]}
```

| `kind` | Observation supplies | Held when |
|---|---|---|
| `quantitative` | `value` | `value` inside `expected_range`; outside but within `tolerance` → `WITHIN_TOLERANCE`; beyond → `PREDICTION_DEVIATED` |
| `directional` | `direction`, or a signed `value` | the observed direction equals `direction`; for `no_change`, `abs(value) <= tolerance` |
| `discrete` | `label` | the label is in `held_labels`; in `failed_labels` → deviated; in neither → `UNTESTABLE` |

`rule` is documentation for humans and never influences the verdict. `measurement`, `noise`,
`sample_size` and `min_effect` are optional and have exactly one consumer: the
distinguishability analysis in §4. `expected_range` and `tolerance` answer *what counts as
held*; the statistical fields answer *whether a design can tell two mechanisms apart*. Mixing
the two is a category error.

### The frozen set is the complete decision set

The observation packet is evidence **about** the preregistration, not a list of things to
decide. `assess_experiment` walks `preregistration.outcomes[]` and looks each one up in the
packet:

| Situation | Result |
|---|---|
| A frozen outcome has no observation | verdict `UNTESTABLE`, reason `missing_observation`; the experiment cannot exceed `PARTIALLY_ASSESSED` |
| The same outcome id appears twice | that outcome is undecidable (`duplicate_observation`); the packet is not qualified |
| The packet carries an id that was never frozen | excluded from the verdict set, recorded in `unexpected_observations`, and the packet is not qualified |
| The criterion is absent or malformed | `UNTESTABLE`; no success or failure may be claimed |

Submitting only the favourable branch is therefore **not** a way to obtain
`PREDICTION_HELD`: an incomplete submission caps the result at `PARTIALLY_ASSESSED` and loses
evidence eligibility.

### Branch mode

A preregistration often enumerates *mutually exclusive branches* of one decision, not several
independent measurements. Branch mode exists for that case and **only** for that case, because
the same shape is also the easiest way to report one favourable result out of several
independent predictions. The difference must be frozen, not asserted, so branch mode is turned
on by the **preregistration**, never by the packet (`PC10`):

```json
{"frozen_at_state_version": 3,
 "outcome_mode": "branch",
 "branch_rule": {
   "selector": {"kind": "result",
                "location": "results/A/X1/summary.json#cross_centre_gap"},
   "quantity": "跨中心 PSNR 差（dB）",
   "branches": ["O1", "O2"]},
 "outcomes": [{"id": "O1", "criterion": {"...": "..."}},
              {"id": "O2", "criterion": {"...": "..."}}]}
```

| Field | Meaning |
|---|---|
| `outcome_mode` | `completeness` (default) or `branch`; a freeze without it is read as completeness |
| `branch_rule.selector` | the raw observation that decides the branch: `kind` + `location`, both known before the run |
| `branch_rule.quantity` | the observed variable; every branch criterion must be written against it |
| `branch_rule.branches` | an exact partition of the frozen outcome set — no omission, no extra |

What is **computed** rather than declared:

* each branch criterion must have a decidable shape, the same observable and the same declared
  measurement basis;
* the branches must be **provably mutually exclusive** from the frozen criteria alone
  (`criteria_mutually_exclusive`: disjoint effective ranges, disjoint held labels, or different
  directions). If they are not, branch mode is refused and the freeze is read as completeness;
* the packet must submit **exactly one** raw observation, its `source.kind`/`source.location`
  must equal the frozen `selector`, and that one observation is evaluated against **every**
  frozen branch. The branch that holds is the observed branch;
* the packet's `observed_outcome`, if present, is only a claim: it must equal the derived
  branch, and the observation's id must equal it too. A declaration that contradicts the raw
  observation is `PC10` and decides nothing (`branch_declaration_conflict`,
  `branch_id_conflict`, `selector_source_mismatch`, `branch_observation_count`,
  `no_branch_matched`).

A non-selected branch is **not** a failed prediction, and it is not silently ignored either: it
is recorded in `excluded_branches[]` with the verdict the same raw observation produced
(`excluded_verdict`) and the exclusion basis, and its id is listed in `not_selected[]`.
"Chose `O1`, therefore `O2` does not matter" is not available.

Without a frozen branch mode the comparator uses **completeness mode**: every frozen outcome is
an independent adjudication and all of them must be decided before `PREDICTION_HELD`. A packet
that declares `observed_outcome` on a completeness freeze is read as completeness and the
declaration is reported (`PC10`) — this is exactly the post-hoc selection the freeze prevents.

### Evidence eligibility

A comparison is always computed when it is possible; whether it may be used as science is a
separate field.

| Field | Values | Meaning |
|---|---|---|
| `outcome_class` | the scientific verdict slot | carries `PREDICTION_HELD` / `PREDICTION_DEVIATED` / `WITHIN_TOLERANCE` **only** on qualified evidence |
| `diagnostic_outcome_class` | any class | the comparison result, always available for the researcher |
| `evidence_class` | `QUALIFIED_EVIDENCE` / `DIAGNOSTIC_ONLY` / `INSUFFICIENT_PROVENANCE` | what the result is worth |
| `evidence_eligible` | boolean | shorthand for `QUALIFIED_EVIDENCE` |
| `scientific_status` | `MAY_INFORM_TRANSITION` / `DIAGNOSTIC_ONLY` / `NO_INFERENCE` | what a consumer may do with it |
| `outcome_class_downgraded_from` | class or absent | set when a world-claiming result was demoted to `UNTESTABLE` |

### One gate, fail closed

Eligibility is decided by exactly one function, `qualify_evidence` (schema
`research-idea-pipeline/evidence-qualification@1`). `assess_experiment`,
`evidence_transition_allowed`, the `--for-transition` exit code, the replay metrics and the
insight certification all read its block; none of them re-derives eligibility from a subset of
fields. The block lists every sub-check with its verdict:

| Check | Question | On failure |
|---|---|---|
| `PQ1` | did the execution carry a usable validity verdict? | `INVALID` → blocking, `UNKNOWN` → diagnostic |
| `PQ2` | is there a frozen, well-formed preregistration (criteria + branch rule + no post-hoc amendment)? | blocking |
| `PQ3` | is the frozen set completely adjudicated, or legitimately branch-mode? | blocking |
| `PQ4` | is every submitted observation bound to exactly `{kind, location, content, digest}` with `digest == digest(content)`? | blocking |
| `PQ5` | does the branch selection trace to the frozen raw observation? | blocking |
| `PQ6` | is the packet bound to an existing experiment? | blocking |
| `PQ7` | are the execution and the experiment receipt terminal (`completed`/`failed`, `done`/`failed`, `result_at_state_version` present)? | diagnostic |
| `PQ8` | does the freeze precede the result, with no post-hoc amendment? | diagnostic (blocking for a post-hoc amendment) |

A **blocking** failure yields `INSUFFICIENT_PROVENANCE` / `NO_INFERENCE`; a **diagnostic**
failure yields `DIAGNOSTIC_ONLY` / `DIAGNOSTIC_ONLY`. Either way `evidence_eligible` is
`false`, no world claim may occupy `outcome_class`, and no mechanism may be supported or
refuted. A missing source is not a warning: it is a blocking failure of `PQ4`. That is the
defect this gate removes — the schema checker reported the broken source while an independent
chain of `if`s still declared `QUALIFIED_EVIDENCE`.

Every failure is emitted as a `PC7` diagnostic that names the check, its severity and the JSON
path, and the failed checks are also listed in `provenance_gaps`.

* `execution.validity == "INVALID"` → `INVALID_EXECUTION`, no comparison, `NO_INFERENCE`.
* `execution.validity == "UNKNOWN"` → the comparison is kept, but a world claim may not occupy
  `outcome_class`: it is downgraded to `UNTESTABLE` and recorded in
  `diagnostic_outcome_class`.
* `PARTIALLY_ASSESSED` and `UNTESTABLE` are statements about the *adjudication*, not about the
  world, so they remain in the scientific slot even when the evidence is not qualified: "we
  could not finish evaluating" is itself the correct conclusion.
* `evidence_transition_allowed` returns `false` when the block is missing or was produced for a
  different packet (`packet_digest`), and re-checks the state-only preconditions. A
  hand-written `evidence_eligible: true` grants nothing.

```sh
python3 scripts/prediction_compare.py compare --state S --packet P --for-transition
```

exits 3 and prints the blockers unless `evidence_transition_allowed` is true. That is the
comparator-side precondition only: the authority for a claim-status change remains R8's
single-direction upgrade or R10, enforced by `evidence_outcome.py` and `state_check.py`.

## 3. Anomaly detection

After execution, the observation packet
(`research-idea-pipeline/prediction-observation@1`) is compared with the freeze:

```json
{"schema": "research-idea-pipeline/prediction-observation@1",
 "experiment_id": "X1",
 "execution": {"status": "completed", "validity": "VALID"},
 "outcomes": [{"id": "O1", "value": 0.8,
               "source": {"kind": "result", "location": "results/A/X1/summary.json",
                          "content": "落差 0.8 dB", "digest": "<sha256 of content>"}}]}
```

Every observation must be **source-bound**: exactly `{kind, location, content, digest}` with
`kind` in `log` / `metric` / `result` and `digest == digest(content)` (`PC2`). The rule is the
same one `execution_gate` applies to `evidence[].diagnostic_observation`.

| Class | Meaning |
|---|---|
| `PREDICTION_HELD` | every frozen prediction held |
| `PREDICTION_DEVIATED` | at least one prediction failed its criterion |
| `WITHIN_TOLERANCE` | no failure, but at least one result sits outside its range within tolerance |
| `PARTIALLY_ASSESSED` | some frozen predictions were decided and others were not; never reported as "all held" |
| `EXPLORATORY_ANOMALY` | there was no frozen preregistration: the observation is recorded, and may **not** be called a prediction success or failure |
| `INVALID_EXECUTION` | execution, protocol, measurement or evaluation cannot support inference — this is R9.O's `INVALID_EXPERIMENT`, not an anomaly |
| `UNTESTABLE` | a criterion is missing or the observation cannot decide it |

The result feeds R9.O; it does not replace it. R9.O still owns the five outcome classes, the
per-claim scoped assessment and the decision gate. An invalid run never becomes a mechanism
refutation, and an exploratory observation never becomes a confirmed prediction.

## 4. Mechanism competition

Two mechanisms are in competition only when the record says what each one predicts. A flat
list of possible causes is not a competition.

```json
{"mechanisms": ["M1", "M2"],
 "shared_explanation": "两者都能解释 X1 在数据集 A 上的落差",
 "conflicting_predictions": ["X2:O1", "X2:O3"],
 "predictions": [{"mechanism": "M1", "ref": "X2:O1"},
                 {"mechanism": "M2", "ref": "X2:O3"}],
 "discriminating_intervention": "X2",
 "decision_impact": "method_decision_differs"}
```

`distinguishability` runs four operational checks, in this order, on **every pair** of
mechanisms. With more than two mechanisms the experiment must separate all of them, so the
overall verdict is the weakest pair verdict and the weakest pair is reported as the witness.

| # | Check | Failure verdict and reason |
|---|---|---|
| 1 | **Comparability** — same observed variable, and the same declared measurement basis | `INSUFFICIENT_INFORMATION` / `different_observables`, `different_measurement` |
| 2 | **Conflict** — the declared ranges (or directions, or label sets) cannot both be satisfied by one observation | `NOT_DISTINGUISHABLE` / `identical_criteria`, `overlapping_intervals`, `non_conflicting_predictions` |
| 3 | **Resolution** — the ranges, widened by `tolerance + noise / sqrt(sample_size)`, stay disjoint, and the raw gap meets the declared `min_separation` | `NOT_DISTINGUISHABLE` / `within_uncertainty`, `below_declared_min_separation` |
| 4 | **Pre-declared rule** — a `discrimination_rule` fixes the threshold before the run | `CONDITIONALLY_DISTINGUISHABLE` / `no_discrimination_rule` |

| Verdict | Meaning |
|---|---|
| `DISTINGUISHABLE` | comparable, conflicting, resolvable, and the decision rule was declared in advance |
| `CONDITIONALLY_DISTINGUISHABLE` | the predictions do conflict, but the decision rule is missing; declaring it is the single remaining step |
| `NOT_DISTINGUISHABLE` | on the declared design the two mechanisms cannot be separated; another run of the same design will not change that |
| `INSUFFICIENT_INFORMATION` | the comparison is not even defined: different observables, no ownership, no usable intervention |

```json
{"discrimination_rule": {"statistic": "difference_of_means",
                         "min_separation": 0.2, "alpha": 0.05,
                         "requires": "fixed-centre ablation"}}
```

The intervention must also be **actionable**: `planned` or `running`. A finished experiment
cannot separate mechanisms, so it yields `INSUFFICIENT_INFORMATION` /
`intervention_not_actionable`.

**No prose and no self-rating enters.** Adding a `note`, a `similarity` value or a
`confidence` to a competition changes nothing; the inputs are frozen numbers, label sets and
declared design parameters. The `discrimination_rule_satisfied` and
`labels_mutually_exclusive` reasons are the only two ways to reach `DISTINGUISHABLE`, and a
test asserts that free text cannot move the verdict.

**Ownership is required.** Predictions come from the competition's `predictions[]`, falling
back to each mechanism's `structure.pending_predictions`. A prediction that cannot be
attributed to a mechanism is `INSUFFICIENT_INFORMATION` / `no_ownership`, not a distinction.
Rewording a prediction is not a new prediction: `criterion_signature` compares the decidable
content, so `rule` text, `measurement` and the statistical fields are deliberately excluded
from it and handled by checks 1 and 3 instead.

Keeping a declared-but-undecidable competition is legal. Generating new explanations to save
an old mechanism is not: `CM8` reports an open competition with no distinguishing power, and
`CM9` reports two mechanisms resting on the same canonical anchors.

## 5. Diagnosis to intervention

`diagnosis_switch` turns the state of attribution into a behaviour change. It does not add a
budget rule; it routes into the dispositions that already exist.

| Action | When |
|---|---|
| `CONTINUE_ATTRIBUTION` | every open competition is distinguishable |
| `FIND_DISCRIMINATING_INTERVENTION` | a competition is design-fixable (`no_intervention`, `no_prediction_gap`, `no_ownership`, `insufficient_predictions`, `predictions_on_other_experiments`, `intervention_not_actionable`) or only `CONDITIONALLY_DISTINGUISHABLE` (`no_discrimination_rule`) — complete the design before running anything |
| `RECORD_BOUNDARY_AND_STOP` | the mechanisms are structurally indistinguishable (`overlapping_intervals`, `identical_criteria`, `within_uncertainty`, `different_observables`, …) *and* the choice does not change the method decision; record the unresolved boundary and stop attributing |
| `REDESIGN_QUESTION` | consecutive diagnostics rated `actual_information_gain: zero` reached the threshold and nothing above applies — route through T8, then R5.1 and R3/R6 |
| `EXPLORE_METHOD_UNDER_UNCERTAINTY` | complete attribution is not needed for the method decision: keep the mechanism as a hypothesis and test mechanism and benefit with one intervention |

The `zero_streak` is read from `scheduler.json`'s `eig_calibration.records`; it never rewrites
a historical prediction. The result always carries
`independent_exploration_allowed: true`, because ordinary unknowns, unverified mechanisms and
the existence of candidates are not global blockers
([scheduler-policy.md](scheduler-policy.md) §3.1). Pre-execution capacity, intervention
strength, identifiability and resource checks are unchanged.

## 6. Insight card

A card is an intermediate product, **not** a first-class state object. It lives in
`cognition/insight-cards.jsonl` and must carry: `observation`, `existing_mechanism`,
`challenged_assumption`, `proposed_mechanism`, `explanatory_gain`, `competing_mechanism`,
`novel_prediction` (`{ref, statement}`), `discriminating_intervention`, `scope_boundary`,
`scientific_implication`, `refs` and `declared_class`.

The class shown in the index is **derived**:

| Derived class | Condition |
|---|---|
| `explanatory_hypothesis` | it explains something already observed, and has no decidable independent prediction |
| `predictive_insight_candidate` | it has a frozen prediction *and* a real discriminating intervention |
| `evidence_supported_insight` | all six certification checks below pass |

The top rung is a **binding** claim, not "this experiment produced T2 evidence somewhere". Each
check names the single missing step (`PC11`):

| Check | Requirement |
|---|---|
| `IC1` | an explicit `novel_prediction.experiment_ref` equal to the experiment of `ref`, `refs.experiments` containing it, and at least one claim/hypothesis reference |
| `IC2` | the referenced claim is not `contradicted`/`killed` and every referenced object is `valid` — the display class cannot outrun `claims[].status` or `validity` |
| `IC3` | the card carries the prediction–observation packet for **that** prediction with a matching `observation_digest`, and the unified gate qualifies it with verdict `PREDICTION_HELD` (in branch mode, on the selected branch) |
| `IC4` | a consistent R9.O receipt for the same experiment: `POSITIVE_EVIDENCE`, `verification_tier ≥ T2`, and a `positive` + `identification: PASS` update for one of the referenced targets |
| `IC5` | canonical evidence at `T2` or above, `Observed`/`Supported`, `valid`, inside the claimed boundary, bound to that experiment, `supports` one of the referenced mechanisms, contradicts none, and (when an explicit `prediction_ref` is present) bound to **that** prediction |
| `IC6` | an `assurance[]` entry with `attack_type: structural-equivalence`, tier ≥ `T1`, a real `discriminating_test`, a valid `validity`, whose `audit_ref` resolves to a SENA artifact that passes `structural_equivalence_check` and whose `verdict` is neither `equivalent`/`subsumed-by-prior`/`reframing-only`/`uncertain` nor about a different candidate |

Consequences worth stating explicitly:

* "same experiment" is not "same prediction": two cards sharing one experiment are certified
  separately, and an evidence object bound to another prediction of the same experiment is
  refused;
* an audit that merely **exists** is not an audit that **passed**: its actual verdict is loaded
  from the artifact its owner validates, so `assurance[]` without `audit_ref` keeps the card at
  the lower class;
* a card without fine-grained references keeps the lower class and says what is missing —
  provenance is reported, never guessed.

Declaring `evidence_supported_insight` without those canonical facts is a hard violation
(`PC7`) — self-certified novelty is exactly what the pipeline is built to prevent. A mismatch
between the declared and derived class is reported (`PC9`) and the derived class wins. These
classes are display and cognitive-index labels; they never replace `claims[].status`,
`verification_tier` or the R8 evidence contract.

## 7. Commands

```sh
python3 scripts/prediction_compare.py freeze  --state <state.json> --experiment X1
python3 scripts/prediction_compare.py compare --state <state.json> --packet observation.json
python3 scripts/prediction_compare.py compete --state <state.json> --competition CP1
python3 scripts/prediction_compare.py switch  --state <state.json> --scheduler scheduler.json
python3 scripts/prediction_compare.py insight --state <state.json> --card card.json
python3 scripts/prediction_compare.py --selftest
```

Exit codes: `0` pass, `1` argument error, `3` hard violation, `4` environment.

## 8. Self-check

- [ ] Every serious mechanism has a rival and a stated difference, or is marked exploratory.
- [ ] No prediction is called held or failed without a frozen `criterion` (`PC1`).
- [ ] A rewrite of a frozen criterion is detected (`PC4`), and an amendment after the result
      is rejected as post-hoc.
- [ ] An invalid run produced `INVALID_EXECUTION`, not a mechanism refutation.
- [ ] An observation without a preregistration is recorded as `EXPLORATORY_ANOMALY`.
- [ ] Every competition prediction is attributed to a mechanism, and the criteria differ.
- [ ] Branch mode is frozen (`outcome_mode` + `branch_rule`) before the run, the branches are
      provably exclusive, and the selected branch is derived from the raw observation.
- [ ] A missing source, a digest mismatch or an unfrozen branch selection leaves
      `evidence_eligible: false` (`PQ1`—`PQ8`), not merely a diagnostic.
- [ ] An insight is certified only with a qualified adjudication of *its own* prediction, an
      R9.O receipt in the supporting direction, bound evidence and an audit whose result is
      known.
- [ ] Repeated empty diagnosis changed the behaviour instead of producing another explanation.
- [ ] No insight card certifies its own novelty or evidence support.
- [ ] `V1`—`V24` and the R10/R14 enums are unchanged.
