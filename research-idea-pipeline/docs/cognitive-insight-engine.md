# Cognitive Insight Engine — architecture and R0—R14 interface map

Branch `feat/cognitive-insight-engine`, base `main` @ `1157d28`. Component scope:
`research-idea-pipeline/` only.

## 1. Problem statement

The pipeline already executes research well: it expands candidates, attacks them, freezes
predictions, analyses outcomes and repairs the state. What it does not do is **accumulate
scientific understanding**. Four concrete symptoms motivated this work:

1. A new session rebuilds facts but not the mechanism model, the failed predictions, or the
   questions the previous session had decided were important.
2. The same explanation is proposed again in different words, because nothing computes that
   two mechanisms rest on the same evidence.
3. Anomalies are recorded as `unexpected` strings and then not used.
4. Ordering by `EIG ÷ cost` rewards cheap diagnostics that change no decision.

The remedy is **not** parameter-level continual learning. It is external persistent memory
plus evidence feedback plus an updated search policy.

## 2. Baseline audit — what already existed

| Capability | Existing carrier |
|---|---|
| Scientific facts, eight first-class objects | `research-state.json` |
| Invalidation, one-hop check plus R11 fixpoint | `validity`, V18/V19 |
| Frozen predictions | `experiments[].preregistration.outcomes`, V21 |
| Evidence tiers and claim-status authority | `verification_tier`, V20/V22 |
| Outcome classification | R9.O, [evidence-outcome-analysis.md](../references/evidence-outcome-analysis.md) |
| Failure memory | `failures[]`, `negative_knowledge`, `stop_rules` |
| Search-operator meta-memory | `scheduler.json` → `operator_stats` |
| EIG producer/consumer split | `predicted_information_gain` / `observed_delta` |
| Cross-stage ordering | eight-level `next_action_policy.priority` |
| Bounded diagnosis | PEIG/AALG route ledger |
| Exploration operators and QD archive | `P1`—`P6`, `local`, 12 operators |
| Structural equivalence audit | `structural_equivalence_check.py` |
| Human views | `STATUS.md`, `INDEX.md`, `routes/<R>/docs/` |

`state_check.py` ignores unknown top-level and object keys and is strict only inside
`structural_signature` and `claims[].contract`. New validators therefore ship as separate
CLIs, following the `experiment_execute.py scheduler-check` precedent, rather than by editing
the state checker.

**Nothing from this list was rebuilt.** The engine reads all of it.

## 3. Layer model

```
canonical     research-state.json + preregistration + raw evidence        authority
event         cognition/model-revisions.jsonl                             append-only
derived       cognition/index.json, cognition/context-brief.md            rebuildable
```

The `cognition/` directory sits in the route control plane, beside `populations/` and
`assurance/`. It is not part of the skill package and not a human document.

## 4. Four capabilities and where they attach

| Capability | Mechanism | Attachment |
|---|---|---|
| Persistent cognitive memory | four memory classes, derived support ladder, hot/warm/cold recall | session start; R3—R6 read; R6/R8/R9.O/R10/R11 write |
| Prediction, anomaly, mechanism competition | freeze digest, prediction–observation comparator, insight card, distinguishability test | R3—R6 candidate, R8 freeze, R9.O compare, R10 disposition |
| Scientific value and adaptive discovery | per-dimension value assessment, calibrated preference memory, strategy update | R3—R6 plus Meta-Controller; `scheduler.json` read-only |
| Discovery replay and verification | offline replay harness with a leak guard, metrics, ablation, adversarial cases | tooling plus a `release_check.py` step |

## 5. Interface map R0—R14

| Stage | Reads from the engine | Writes to the engine | Unchanged |
|---|---|---|---|
| R0 | — | — | `contract` is human-owned; the engine never edits it |
| R1 | context brief | — | eight first-class objects, S1—S7, V1—V24 |
| R2 / R5 | retrieval cues, known duplicates | — | literature policy |
| R3—R6 | strategy priors, existing mechanisms, competitions | `mechanism_*`, `competition_*` | `P1`—`P6`, QD archive, `P3` typed intermediate |
| R7 | mechanisms and competitions under attack | — | attack surfaces, `assurance` five-tuple |
| R8 | pending predictions | `prediction_freeze` | ten-key contract, single-direction upgrade |
| R9 | failure constraints | — | EIG, PEIG/AALG |
| R9.O | frozen predictions | `anomaly_record`, `prediction_assessment` | five outcome classes |
| R10 | refuted mechanisms | `mechanism_refute`, `mechanism_weaken`, `mechanism_reactivate` | five dispositions, two closures |
| R11 | rebuild trigger | `mechanism_merge`, `mechanism_revise` | `state_version` +1, invalidation fixpoint |
| R12 / R13 | read-only view | — | narrative and review stay state views |
| R14 | brief, strategy priors | — | `continue`/`pivot`/`archive`/`submit`; no claim status |

## 6. Design decisions and trade-offs

| Decision | Why | Alternative rejected |
|---|---|---|
| Separate CLI validator, not a new `V` rule | S1—S7 / V1—V24 keep their frozen identity; parity tests would break | editing `state_check.py` |
| No new state slot | migration would touch the template, the policy table and the validator in one round | adding `cognition` to the state |
| Support level computed from canonical facts | a self-declared level is exactly the failure mode being fixed | trusting the revision's own label |
| Revision log carries structure plus pointers only | prevents a second authoritative source | storing conclusions in the log |
| `cognition/` in the control plane | matches `populations/` and `assurance/`; keeps `docs/` flat and human | a route document per revision |
| Value judgements are per-dimension, never one score | the repository already refuses a third numeric scoring system | a composite "insight score" |
| Anomalies require a named prediction source | prevents an exploratory observation from being renamed a prediction failure | free-text anomalies |

## 7. Documents and commands

| Artifact | Purpose |
|---|---|
| [cognitive-memory-policy.md](../references/cognitive-memory-policy.md) | memory classes, layers, rules `CM1`—`CM9`, lifecycle, write prohibitions |
| [scripts/cognition.py](../scripts/cognition.py) | builder, validator, recall and context brief |
| [scripts/test_cognition.py](../scripts/test_cognition.py) | offline tests |
| [examples/cognition/](../examples/cognition/README.md) | synthetic fixture |

```sh
python3 scripts/cognition.py build --state <state.json>
python3 scripts/cognition.py check --state <state.json>
python3 scripts/cognition.py brief --state <state.json> --budget 4000
python3 scripts/release_check.py
```

## 8. Known limits

Structural checks establish provenance, determinism and authority boundaries. They do not
establish that a mechanism is true, that a competition is scientifically the most important
one, or that a recall selection is the most useful. Index entries are summaries of canonical
records; when they disagree with the state, the state wins and the index must be rebuilt.
