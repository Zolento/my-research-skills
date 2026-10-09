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
| Prediction, anomaly, mechanism competition | frozen `criterion`, freeze digest, prediction–observation comparator, insight card, distinguishability test | R3—R6 candidate, R8 freeze, R9.O compare, R10 disposition |
| Scientific value and adaptive discovery | per-dimension value, taste memory, lexicographic menu ordering | R3—R6 plus the Meta-Controller; `scheduler.json` read-only |
| Legacy takeover | read-only audit `LH1`—`LH16`, legacy derivation, report, rollback | first `continue-research` on an initialized project |
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
| takeover | canonical state, scheduler, ledger, docs, code | `cognition/` derived layer only | state, scheduler, versions, ids, anchor, budget |
| replay | visible section of a replay case | — | nothing in the live route; runs on a synthetic tree |

### Rule namespaces

| Namespace | Owner | Meaning |
|---|---|---|
| `S1`—`S7`, `V1`—`V24` | `scripts/state_check.py` | shape gate and reference integrity of the canonical state |
| `EO1`, `EX1` | `evidence_outcome.py`, `execution_gate.py` | additive outcome and execution gates |
| `CM0`—`CM10` | `scripts/cognition.py` | cognitive projection, provenance, revision authority |
| `PC1`—`PC11` | `scripts/prediction_compare.py` | criteria, observation binding, freeze integrity, the frozen branch mode (`PC10`), evidence eligibility (`PC7`, sub-checks `PQ1`—`PQ8`), adjudication completeness (`PC8`), competition, insight cards and their per-prediction evidence binding (`PC11`) |
| `LH1`—`LH16` | `scripts/legacy_handoff.py` | takeover compatibility audit |
| `PR1`—`PR9` | `scripts/preset_router.py` | provided-registry ↔ protocol parity, intent routing (clause-scoped negation, ambiguity → least privilege), one-protocol loading, loop triggers, recovery guard, permission tiers |
| `SV1`—`SV8` | `scripts/strategy_memory.py` | value judgment, taste authority, anti-lock-in, isolation |
| `RP1`—`RP5` | `scripts/research_replay.py` | case schema, leak guard, decision schema, independent novelty |

No namespace collides with the canonical id prefixes `C` / `E` / `AS` / `H` / `X` / `LIT` /
`F` / `U`, with `S` / `V`, or with `DI` / `T` / `G` / `N` / `P`.

## 6. Design decisions and trade-offs

| Decision | Why | Alternative rejected |
|---|---|---|
| Separate CLI validator, not a new `V` rule | S1—S7 / V1—V24 keep their frozen identity; parity tests would break | editing `state_check.py` |
| No new state slot | migration would touch the template, the policy table and the validator in one round | adding `cognition` to the state |
| Support level computed from canonical facts | a self-declared level is exactly the failure mode being fixed | trusting the revision's own label |
| Revision log carries structure plus pointers only | prevents a second authoritative source | storing conclusions in the log |
| `cognition/` in the control plane | matches `populations/` and `assurance/`; keeps `docs/` flat and human | a route document per revision |
| Value judgements are per-dimension, never one score | the repository already refuses a third numeric scoring system | a composite "insight score" |
| Strategy priors stay out of `scheduler.json` | writing them back would change the scheduler's authority, which the phase forbids | extending telemetry into a decision store |
| Anomalies require a named prediction source | prevents an exploratory observation from being renamed a prediction failure | free-text anomalies |

## 7. Documents and commands

| Artifact | Purpose |
|---|---|
| [cognitive-memory-policy.md](../references/cognitive-memory-policy.md) | memory classes, layers, rules `CM1`—`CM10` (with the documented `hard` / `warning` severity table), lifecycle, write prohibitions |
| [prediction-anomaly-competition.md](../references/prediction-anomaly-competition.md) | frozen criteria, comparison classes, competition verdicts, behaviour switch, insight cards |
| [legacy-handoff.md](../references/legacy-handoff.md) | detection, audit `LH1`—`LH16`, reconstruction, retrospection rules, rollback |
| [scientific-value-adaptive-discovery.md](../references/scientific-value-adaptive-discovery.md) | value dimensions, taste memory, menu ordering, anti-lock-in rules, `P4` isolation |
| [discovery-replay.md](../references/discovery-replay.md) | replay cases, leak guard, metrics, ablation, what has not been verified |
| [scripts/cognition.py](../scripts/cognition.py) | builder, validator, recall and context brief |
| [scripts/prediction_compare.py](../scripts/prediction_compare.py) | comparator, competition and insight checks |
| [scripts/legacy_handoff.py](../scripts/legacy_handoff.py) | takeover, report and rollback |
| [scripts/strategy_memory.py](../scripts/strategy_memory.py) | value model, taste memory, operator priors, menu ordering |
| [scripts/research_replay.py](../scripts/research_replay.py) | replay harness, metrics, ablation, adversarial suite, smoke test |
| [scripts/test_cognition.py](../scripts/test_cognition.py) | offline tests |
| [scripts/test_prediction_compare.py](../scripts/test_prediction_compare.py), [scripts/test_legacy_handoff.py](../scripts/test_legacy_handoff.py), [scripts/test_strategy_memory.py](../scripts/test_strategy_memory.py), [scripts/test_research_replay.py](../scripts/test_research_replay.py) | offline tests |
| [examples/cognition/](../examples/cognition/README.md) | synthetic fixture |

```sh
python3 scripts/cognition.py build --state <state.json>
python3 scripts/cognition.py check --state <state.json>
python3 scripts/cognition.py brief --state <state.json> --budget 4000
python3 scripts/prediction_compare.py compare --state <state.json> --packet observation.json
python3 scripts/legacy_handoff.py take --state <state.json>
python3 scripts/strategy_memory.py recommend --state <state.json>
python3 scripts/research_replay.py suite --dir examples/replay/adversarial --runs 2
python3 scripts/release_check.py
```

## 8. Verification status

Verified offline and mechanically, by the sixteen-step release gate and 1347 unit tests:

* the canonical state, scheduler template and the four schemas are unchanged, and
  `state_check.py` still enforces the same `S1`—`S7` / `V1`—`V24`;
* a cognitive build never writes the state, and the index rebuilds to identical bytes;
* support levels come from canonical facts, and a self-declared level is recorded as a
  conflict instead of being adopted;
* a rewritten frozen criterion is detected, and an amendment after the result is rejected;
* an invalid execution is never a prediction verdict and never a mechanism refutation;
* the frozen preregistration is the complete decision set, so a partial submission yields
  `PARTIALLY_ASSESSED` with `evidence_eligible: false` and never `PREDICTION_HELD`;
* branch mode is opened by a frozen rule, not by the packet: the selected branch is derived
  from the raw observation the freeze named, the other branches are excluded by a recorded,
  checkable condition, and a post-hoc `observed_outcome` is read as completeness;
* exactly one function decides evidence eligibility (`qualify_evidence`, `PQ1`—`PQ8`), a
  missing source or a digest mismatch is a blocking failure rather than a warning, and a
  hand-written `evidence_eligible: true` grants no transition;
* an insight reaches `evidence_supported_insight` only with a qualified adjudication of *its
  own* prediction, an R9.O receipt in the supporting direction, evidence bound to that
  prediction and mechanism, and an audit whose actual verdict is loaded from the artifact its
  owner validates;
* the observation validator is the gate: `PQ4` consumes its complete result, so a wrong
  `schema` id, a missing required field, an illegal field type or an illegal
  `observed_outcome` type closes the gate instead of qualifying the packet; a declared
  `observed_outcome` that is not a frozen outcome is a decision-set defect (`PQ3`), and an
  unverifiable freeze (`PC5`) blocks it too, while informational extra keys keep qualifying;
* prediction identity is explicit: evidence carries `prediction_ref`, and the only other
  admissible route is a freeze with exactly one outcome. "Same experiment", "same claim" and
  "same mechanism" are refused, and old evidence is never retro-fitted with a binding;
* applicability is not word similarity: scope coverage is exact normalized equality for
  legacy string scopes, or constrained-subset coverage for structured
  `evidence[].scope_region` / card `scope_boundary_region`. `"MRI"` does not cover
  `"MRI-3D"`, and a single-centre evidence scope no longer generalises to the whole dataset;
* an `UNKNOWN` execution keeps its diagnostic comparison but cannot occupy the scientific
  verdict slot, and `evidence_transition_allowed` blocks the transition;
* distinguishability requires a comparable observable, a conflicting prediction, enough
  resolution against `tolerance + noise/√n`, and a pre-declared `discrimination_rule`; free
  text and self-ratings cannot move the verdict;
* a takeover leaves the state, scheduler and execution ledger byte-identical, and repeating it
  is idempotent even when the rebuild reports `warning`-severity CM diagnostics — the severity
  table is enforced, so a legacy note never flips an exit code or blocks a takeover;
* no value judgment or strategy update contains an aggregate score, and no operator is banned;
* the provided `router-fixtures.json` passes 53/53 (48 positive + 5 guarded), every protocol file is
  independent, and one call loads the shared contract plus exactly one protocol;
* the sixteen presets resolve from Chinese, English, aliases, ids and the registry's intent examples; a negated request and an
  ambiguous request cannot start an execution; a descriptive report starts read-only; the loop
  trigger selects at most one recovery per `(state_version, preset, signal)` and ends in `HOLD`
  instead of repeating; an engineering failure never changes `claims[]`/`hypotheses[]`;
* strategy advice reaches the real action selection through the Strategy Decision Adapter, which
  may only reorder inside one `EIG ÷ cost` tier among actions that already pass the hard gates,
  records candidates/adoption/reason in `scheduler.strategy_decisions[]`, and reports
  `strategy_applied: false` with a reason when nothing can change;
* the offline ablation reproduces the capability ladder, and the fourteen adversarial cases are
  satisfied by the full arm and not by the baseline.

**Not verified:** real Agent A/B discovery performance, and a real (non-synthetic) prediction–
observation packet. Every certification fixture is synthetic and marked as such; the positive
certification path is exercised offline against in-memory SENA artifacts, not against a real
audit produced by a human reviewer.

**Not verified:** real Agent A/B discovery performance. No model was called and no real
literature library was used. Every fixture is synthetic and marked as such. The ablation
deltas are properties of the offline runner, and two arms are indistinguishable on all seven
dimensions — the report says so rather than implying the extra capability was measured.

## 9. Known limits

Structural checks establish provenance, determinism and authority boundaries. They do not
establish that a mechanism is true, that a competition is scientifically the most important
one, or that a recall selection is the most useful. Index entries are summaries of canonical
records; when they disagree with the state, the state wins and the index must be rebuilt.

Branch selection remains a human judgement in one respect: the comparator can prove that a
freeze is a partition, that the rule is frozen and that the observation is traceable, but it
cannot prove that the frozen branches are the scientifically right ones.

The freeze digest protects a branch declaration only when the cognitive revision log recorded
one; a project that never ran `cognition build` has no recorded digest, so a post-hoc
`branch_rule` added to the state is caught by `PC10` shape and exclusivity checks but not by
`PC4`. Canonical writes remain governed by R13's Integrity Gate.

A reconstructed legacy mechanism is a projection of canonical state, not a recovered memory
of what the previous session thought. The takeover cannot recover a judgement the state never
recorded, which is why those items are reported as `unknown` or `retrospective` instead of
being filled in.
