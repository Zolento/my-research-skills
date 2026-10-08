# Cognitive memory fixtures

These files are a **synthetic fixture**. They are not results from a real study and must
never be cited as scientific evidence. They exist so the cognitive layer can be exercised
offline, through the same gates as the ordinary pipeline.

| File | Role |
|---|---|
| [state.json](state.json) | A canonical Research State that passes S1—S7 and V1—V24 |
| [model-revisions.jsonl](model-revisions.jsonl) | The append-only cognitive revision log for that state |

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

## What it demonstrates

| Situation in the fixture | Expected cognitive result |
|---|---|
| `M1` is anchored to `E1`, a strong `T2` experiment evidence supporting a `partially-supported` claim | support level `experiment_supported` |
| `M2` is anchored only to a candidate and an assumption | support level `hypothesis` |
| `M3` is anchored to `F2`, a `failed-to-reproduce` failure | support level `refuted`, lifecycle `refuted` |
| `CP1` names two mechanisms with conflicting predictions and intervention `X2` | an open competition with distinguishing power |
| `AN1` records a direction reversal against a frozen prediction, `reproduced: false` | a high-importance, non-reproduced anomaly |
| `F2` is a repeat-blocking failure kind | failure memory shown with `retry=blocked` |
| No revision declares its own support level | the brief labels every mechanism from canonical facts |

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
