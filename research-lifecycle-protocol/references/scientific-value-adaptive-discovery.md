# Scientific Value and Adaptive Discovery — Decision Value, Taste Memory, Strategy

The scheduler already orders actions by `EIG ÷ cost`. That ordering is necessary and not
sufficient: it rewards cheap diagnostics that change no decision, and it cannot tell whether
a finding changes a method or merely adds a sentence. This capability adds a value judgment
and a search-strategy memory **without** replacing the scheduler and **without** introducing
a new total score.

It reuses `P1`—`P6`, `local`, the QD archive, `scheduler.json`'s `operator_stats` and the
existing eight-level `next_action_policy`. No new Exploration Agent, no new operator, no new
budget rule.

## 1. Scientific value model

Two judgments, deliberately separate, each derived per dimension with a canonical source:

**Decision value** — would this finding change a choice? `changes_method_choice`,
`changes_experiment_design`, `changes_resource_allocation`, `changes_route`,
`changes_important_conclusion`.

**Discovery potential** — if it holds, what would it open? `reveals_new_structure`,
`overturns_important_assumption`, `builds_cross_domain_link`, `raises_new_question`.

Each dimension carries `assessment` (`yes` / `likely` / `unclear` / `no`), `basis` (canonical
ids) and `uncertainty`. `considerations` adds `contract_relation`, `extrapolation_range`,
`nearest_prior_delta`, `falsification_difficulty`, `identification_difficulty`,
`experiment_cost`, `evidence_strength`, `long_term_value`, and `objections` must name the
strongest counter-argument — including the explicit admission that no objection has been
recorded yet, which is a gap rather than evidence of value.

**There is no composite score.** `SV1` rejects `score` / `total` / `overall` / `composite` /
`weighted` / `aggregate` / `rating` anywhere in a value judgment or a strategy update. The
reason is not stylistic: a single number is exactly what makes "the agent rated it 0.8"
indistinguishable from evidence, and [scoring-policy.md](scoring-policy.md) already refuses a
third numeric system inside this repository.

**A dimension without a source is rejected** (`SV2`). An indicator with no `basis` is a
self-rating, and a self-rating may not declare high value.

## 2. Taste memory

Two parts with different authority:

| Part | Source | Who may change it |
|---|---|---|
| **Human-specified preferences** | `contract` (`goal`, `primary_anchor`, `constraints`, `resources`, `out_of_scope`) | the user only; the agent reads it |
| **Evidence-calibrated preferences** | outcomes: `scheduler.json` `eig_calibration` and `operator_stats`, `hypotheses[].status`, `failures[]`, `index` mechanisms | the system, subject to the rules below |

`SV3` rejects any strategy update that targets `contract`, `primary_anchor`, `anchor`,
`out_of_scope` or `research_goal`. Automatic learning changes **exploration advice only**; it
never substitutes for the Research Contract, an Anchor Change Order, or an authorization
boundary.

Calibrated preferences are the lessons the loop actually learns:

| Situation | Learned preference |
|---|---|
| Diagnostics rated `zero` / `low` | diagnostics that change no candidate, intervention or resource decision repeat themselves |
| Interventions that moved a claim status | only interventions that change a claim or close an uncertainty advance the work |
| Refuted / weakened mechanisms | they must not be re-proposed as-is; only outside their recorded boundary |
| `P4` candidates with no `pending_predictions` | a cross-domain analogy without a structural correspondence and a testable prediction is surface similarity |
| Mechanisms sharing a canonical anchor set | a rewording is not a new candidate |
| Dormant operators | wipe-out is a result about this round, not a permanent verdict |

Every preference carries `basis`, `confidence`, `scope`, `counterexamples` and
`revisit_conditions`, so a later piece of evidence can revise it. A preference without those
fields is rejected.

## 3. Adaptive discovery strategy

The eight discovery moves from the specification map onto operators that already exist:

| Menu | Operator | Structural axis |
|---|---|---|
| `invert_hidden_assumption` | `assumption_breaker` | `assumption-shift` |
| `replace_problem_representation` | `reframe` | `representation-shift` |
| `change_research_scale` | `theory_lens` | `theory-shift` |
| `cross_domain_isomorphism` | `remote_analogy` | `mechanism-shift` |
| `construct_counterexample` | `counterexample` | `boundary-shift` |
| `redefine_from_objective_or_metric` | `reframe` | `evaluation-shift` |
| `probe_structure_by_minimal_intervention` | `local` | `mechanism-shift` |
| `abandon_attribution_direction` | `local` | `boundary-shift` |

Selection is **lexicographic**, with no weights: stop rules exclude a menu first, then the
behaviour switch from `prediction_compare.diagnosis_switch` picks the family, then operator
history, then whether the menu has been repeated, then the menu name. Nothing is traded
against anything else, so a high "value" can never buy off an active stop rule.

### Anti-lock-in rules (`SV5`, `SV7`)

1. **No permanent ban.** The status vocabulary is `encouraged` / `neutral` / `discouraged` /
   `dormant`. There is no forbidden value, and an unknown one is rejected.
2. **A discouraged or dormant operator must carry reactivation conditions**, and its
   discouragement must be scoped to the problem structure where it failed. A scoped failure
   is not a class verdict.
3. **At least two independent failures** are required before an operator is deprioritised
   (`MIN_INDEPENDENT_FAILURES`). A few failures never condemn a whole mechanism class.
4. **Exploration floor.** The prior block always keeps an admissible long-shot set, so low
   historical EIG cannot permanently exclude a high-potential exploration.
5. **Divergence.** Two consecutive strategy updates on the same menu force the ordering to
   prefer a different one.
6. **No unconditional extra rounds.** `exploration_rounds_delta` must be 0; a round count can
   only be justified by the decision it resolves.
7. **Independent exploration is never globally blocked.** Ordinary unknowns, unverified
   mechanisms and the mere existence of candidates are not blockers
   ([scheduler-policy.md](scheduler-policy.md) §3.1).

### `P4` context isolation (`SV6`)

An analogy may read the **typed intermediate** representation and nothing else. `p4_context`
accepts only skeletons carrying the five slots `object` / `relation` / `constraint` /
`failure_mode` / `core_unknown`, and refuses any file containing candidate content,
candidate domain terms, another island's answer, a method name or a conclusion. Otherwise
two islands would "independently" find the same thing, and the diversity the QD archive
exists to protect would be fabricated.

## 4. Self-improvement from outcomes

The loop is `prediction → experiment → outcome → model revision → strategy update`. Only the
last step lives here, and it produces **suggestions to append** as `strategy_update`
revision events with a real trigger and canonical references; the Discovery stages and the
Meta-Controller own the append.

```
scheduler.json eig_calibration + operator_stats   →  operator priors
hypotheses[].status, failures[], index mechanisms →  calibrated preferences
both                                              →  menu ordering for the next round
```

`SV8` requires every strategy update to cite canonical objects: an experience with no source
is a self-rating. `SV6` restricts the writing stages to Discovery and the Meta-Controller —
R7, R12, R13 and R14 do not write the cognitive layer. The loop converges because a prior
that the canonical state already reflects produces no further update.

`scheduler.json` is **read-only** for this layer. Writing strategy priors back into telemetry
would change the scheduler's authority, which the phase explicitly forbids; recording
decisions in the cognitive layer keeps telemetry as telemetry and keeps the eight-level
ordering untouched.

## 5. Commands

```sh
python3 scripts/strategy_memory.py value     --state <state.json> --target H1
python3 scripts/strategy_memory.py taste     --state <state.json>
python3 scripts/strategy_memory.py operators --state <state.json> --scheduler scheduler.json
python3 scripts/strategy_memory.py recommend --state <state.json> --scheduler scheduler.json
python3 scripts/strategy_memory.py apply     --state <state.json> --scheduler scheduler.json
python3 scripts/strategy_memory.py validate  --state <state.json>
python3 scripts/strategy_memory.py --selftest
```

`cognition.py build` also projects the strategy section into `index.json` and the context
brief whenever `scheduler.json` is present; the index digest includes the scheduler, so a
telemetry change invalidates the projection instead of drifting silently.

## 6. Self-check

- [ ] No value judgment or strategy update contains an aggregate score (`SV1`).
- [ ] Every value dimension and every preference cites canonical evidence (`SV2`).
- [ ] The anchor, the contract and `out_of_scope` are byte-identical after learning (`SV3`).
- [ ] Preferences and priors carry scope, counterexamples and revisit conditions.
- [ ] No operator status is a permanent ban, and every downgrade is scoped and reversible.
- [ ] At least two independent failures were needed before a deprioritisation (`SV5`).
- [ ] The exploration floor is never empty and low EIG never removes a menu (`SV7`).
- [ ] `P4` received typed skeletons only (`SV6`).
- [ ] `scheduler.json` is unchanged and no priority level was redefined.
- [ ] One traceable chain exists from an outcome to a changed menu ordering.
