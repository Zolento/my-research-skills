# Cognitive memory fixtures

These files are a **synthetic fixture**. They are not results from a real study and must
never be cited as scientific evidence. They exist so the cognitive layer can be exercised
offline, through the same gates as the ordinary pipeline.

| File | Role |
|---|---|
| [state.json](state.json) | A canonical Research State that passes S1—S7 and V1—V24 |
| [model-revisions.jsonl](model-revisions.jsonl) | The append-only cognitive revision log for that state |
| [prediction-observation.json](prediction-observation.json) | A source-bound observation packet for `X1` |
| [insight-cards.jsonl](insight-cards.jsonl) | One insight card, whose class is derived rather than declared |

The state is a legacy project: it carries **no** `contract.outcome_policy`, so it also
carries no outcome-policy records. That is deliberate — it demonstrates that the cognitive
layer works on an existing project without a schema migration. Failure memory with explicit
`stop_rules` and `negative_knowledge` requires a frozen outcome policy, so that path is
exercised by `scripts/test_cognition.py` instead of by this fixture.

## Run it

```sh
mkdir -p /tmp/cie && cp examples/cognition/state.json /tmp/cie/research-state.json
mkdir -p /tmp/cie/cognition && cp examples/cognition/model-revisions.jsonl /tmp/cie/cognition/
python3 scripts/cognition.py build --state /tmp/cie/research-state.json
python3 scripts/cognition.py check --state /tmp/cie/research-state.json
```

`build` writes `cognition/index.json` and `cognition/context-brief.md` next to the state.
`check` rebuilds both in memory and fails when they drift. Neither command writes the state.

The prediction comparator, the competition check and the insight classification run against
the same fixture:

```sh
cp examples/cognition/insight-cards.jsonl /tmp/cie/cognition/
python3 scripts/prediction_compare.py compare --state /tmp/cie/research-state.json \
  --packet examples/cognition/prediction-observation.json
python3 scripts/prediction_compare.py compete --state /tmp/cie/research-state.json \
  --cognition /tmp/cie/cognition --competition CP1
python3 scripts/prediction_compare.py insight --state /tmp/cie/research-state.json \
  --cognition /tmp/cie/cognition
```

The same fixture without its revision log is also a legacy project: deleting
`model-revisions.jsonl` and `insight-cards.jsonl` leaves a state that
`scripts/legacy_handoff.py take` reconstructs from canonical evidence alone.

## What it demonstrates

| Situation in the fixture | Expected cognitive result |
|---|---|
| `M1` is anchored to `E1`, a strong `T2` experiment evidence supporting a `partially-supported` claim | support level `experiment_supported` |
| `M2` is anchored only to a candidate and an assumption | support level `hypothesis` |
| `M3` is anchored to `F2`, a `failed-to-reproduce` failure | support level `refuted`, lifecycle `refuted` |
| `CP1` names two mechanisms with conflicting predictions and intervention `X2` | an open competition with distinguishing power |
| `AN1` records a direction reversal against a frozen prediction, `reproduced: false` | a high-importance, non-reproduced anomaly |
| `F2` is a repeat-blocking failure kind | failure memory shown with `retry=blocked` and a `failed_repeat` boundary |
| No revision declares its own support level | the brief labels every mechanism from canonical facts |
| `X1:O1` is frozen with a quantitative criterion, `X2` carries M1's and M2's predictions, and `CP1` declares a `discrimination_rule` | `CP1` is `DISTINGUISHABLE` (`discrimination_rule_satisfied`); the packet gives `PREDICTION_HELD` on qualified evidence |
| `X1` freezes two mutually exclusive branches `O1`/`O2` **with** `outcome_mode: "branch"` and a `branch_rule` | the selected branch is derived from the frozen `selector` plus the raw observation; `O2` is excluded by a recorded condition; `observed_outcome` only has to agree |
| The same packet without the frozen branch declaration | completeness mode: the one submitted observation leaves `O2` unobserved, so the result is `PARTIALLY_ASSESSED` with `evidence_eligible: false` (`PC10`) |
| `A1` declares a structural-equivalence attack but has no `audit_ref` | the audit's result is unknown, so no card can be certified as `evidence_supported_insight`; `insight` reports it under `audit_problems` |
| `X2:O2` restates `X2:O1` with the same criterion | swapping it in makes the competition `NOT_DISTINGUISHABLE` (`identical_criteria`) |
| Only `O1` is submitted without a branch selection | the result is `PARTIALLY_ASSESSED` with `evidence_eligible: false` — never `PREDICTION_HELD` |
| `IC1` declares `predictive_insight_candidate` and has a real intervention | the index derives the same class; declaring `evidence_supported_insight` would raise `PC7` |
| A card that claims evidence support without the prediction-level packet, the R9.O receipt, bound evidence and a *passed* audit | stays at the lower class and names each missing ingredient (`PC11`); `scripts/test_prediction_compare.py` builds both the full and the failing bindings in memory |

## Negative examples, not shipped here

The unit tests build the failing cases in memory rather than shipping them, so that a
broken artifact can never be mistaken for a supported one. They cover: a revision that
declares `epistemic_status`; a revision that touches `contract`; a self-declared support
level; a dangling reference; a reference to a future `state_version`; a revision with no
trigger; a competition with fewer than two mechanisms; a competition with no prediction gap;
two mechanisms with an identical anchor set; and an invalidated evidence source that must
push its derived memory out of hot recall.

See [cognitive-memory-policy.md](../../references/cognitive-memory-policy.md) for the rules
and [the architecture note](../../docs/cognitive-insight-engine.md) for the interface map.
