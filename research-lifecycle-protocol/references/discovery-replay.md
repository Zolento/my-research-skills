# Discovery Replay and Verification — proving the engine helped

Adding memory, prediction and strategy layers is easy to claim and hard to demonstrate. This
capability is the demonstration: replay a decision with only the information available at the
time, score it against an answer the system never saw, and compare configurations that differ
only in which capabilities are enabled.

It is offline tooling. It does not call a model, and it does not run a GPU.

## 1. Replay cases

```json
{
  "_schema": "research-idea-pipeline/replay-case@1",
  "id": "ADV4",
  "question": "是否应重新提出已被否证的机制？",
  "visible": {
    "state": { "...": "the canonical state as it was" },
    "revisions": [],
    "scheduler": null,
    "observation_packet": { "...": "source-bound observation, if any" },
    "available_literature": ["[Synthetic, Fixture/2024]"],
    "known_conditions": ["single centre training", "one acceleration"]
  },
  "hidden": {
    "later_results": ["..."],
    "answer": {
      "mechanism_terms": ["..."], "assumption_terms": ["..."], "boundary_terms": ["..."],
      "true_outcome_class": "PREDICTION_HELD",
      "discriminating_intervention": "X2",
      "required_controls": ["same training budget"],
      "novelty_neighbours": ["LIT1"],
      "human_novelty_label": "not_novel"
    }
  },
  "evaluation_only": {
    "expected_behaviour": "stop_attribution",
    "expected_decision_changed": true,
    "forbidden_behaviours": ["propose_again_refuted_mechanism"],
    "must_not_appear": []
  }
}
```

`visible` is everything the runner receives. `hidden` and `evaluation_only` never reach it.

## 2. The leak guard (`RP2`)

`visible_view` strips the hidden and evaluation sections, and then the strip is **verified**:
`leak_scan` searches the resulting payload for every hidden string of twelve characters or
more. A case whose visible section contains a hidden result refuses to run at all.

This matters because the substitute failure mode is subtle. A case that leaks its own answer
still produces a passing result — the runner simply repeats the future it was shown. The
offline runner goes through the same `run_case` path, so the same guard applies.

`scientific_novelty` is scored only from an independent source: `human_novelty_label` or
`novelty_neighbours`. A case that carries only a numeric `novelty_rating` is rejected
(`RP5`), and a decision carrying `novelty_self_rating` is rejected outright.

## 3. Evaluation metrics

Seven dimensions, each scored independently. There is **no total**: a weighted average would
let a good prediction compensate for an uncontrolled confound.

| Dimension | Scored from |
|---|---|
| `mechanistic_understanding` | how much of the reference mechanism, assumption and boundary vocabulary the decision can articulate |
| `prediction_quality` | the frozen-prediction class versus `true_outcome_class`, and **only** for a qualified assessment; a diagnostic comparison is reported as unratable rather than scored |
| `intervention_quality` | whether the chosen intervention is the discriminating one, plus identification-control coverage |
| `scientific_novelty` | the independent label or literature neighbours only |
| `search_efficiency` | effective outputs (a prediction class plus a decision change) relative to the baseline arm |
| `stagnation_recovery` | whether repeated failure produced a stop or a redesign rather than another explanation |
| `memory_accumulation` | whether a second session recalled prior cognition instead of inheriting an unverified inference |

`null` means **not assessable** in that case, and it is never treated as zero. A case with no
baseline has no `search_efficiency`; a first-session case has no `memory_accumulation`.

## 4. Ablation

Four arms, cumulative capabilities:

| Arm | Capabilities |
|---|---|
| `baseline` | none — the raw state only |
| `memory_only` | cognitive memory |
| `memory_prediction` | memory + the prediction comparator |
| `full_cie` | memory + comparator + strategy memory |

`run_suite` reports per-arm dimension means, `min`, `max`, the observable case count, the
violation list and a pass rate. Differences are reported per dimension; nothing is summed.

**Honest reporting rules:**

* With fewer than three cases or fewer than two runs, the report sets
  `sufficient_sample: false` and states that no improvement may be claimed.
* Two arms that are indistinguishable on every dimension are listed under
  `undifferentiated_arms`, together with the warning that the extra capability was not
  measured. In the shipped suite, `memory_prediction` and `full_cie` are identical on all
  seven dimensions, because none of them isolates the strategy layer.
* Every report carries its limitations, including that the fixtures are synthetic and no
  real model or literature library was used.

## 5. Adversarial suite

Fourteen cases, one per failure mode the specification names, all shipped under
`examples/replay/adversarial/`:

| Case | Situation | Expected behaviour |
|---|---|---|
| `ADV1` | the mechanism explains history but fails on the future | design the intervention, do not retrofit an explanation |
| `ADV2` | two mechanisms are equivalent on existing data | design the intervention that separates them |
| `ADV3` | an apparent anomaly is an implementation error | keep `INVALID_EXECUTION`; never a refutation |
| `ADV4` | a refuted mechanism is proposed again | stop; the stopped protocol stays stopped |
| `ADV5` | an important finding has no short-term EIG | keep it admissible; low EIG is not a rejection |
| `ADV6` | a cross-domain analogy is only superficially similar | no self-certified novelty |
| `ADV7` | a key evidence source is invalidated | downstream cognition goes stale; no verdict without a criterion |
| `ADV8` | a new session resumes the previous round | recall cognition; do not inherit an unverified inference |
| `ADV9` | the result exists and the expectation is edited | reject the post-hoc rewrite |
| `ADV10` | several diagnostic rounds produce nothing new | change the question, do not keep diagnosing |
| `ADV11` | two frozen predictions, only one submitted | `PARTIALLY_ASSESSED`, never `PREDICTION_HELD` |
| `ADV12` | execution validity unknown | keep the diagnostic comparison, refuse the scientific claim |
| `ADV13` | branch selection declared after the fact | no frozen rule means completeness mode; the selection is refused |
| `ADV14` | the source digest does not match its content | the observation is not bound, so it is not evidence |

The suite deliberately rewards **correct stopping**, **preserved unknowns** and **changed
direction**, not "more output". `ADV4` scores `intervention_quality = 1.0` for choosing no
experiment at all, because stopping is the right answer there.

`ADV11`—`ADV14` guard the failure modes that would otherwise turn the comparator into a
false-positive generator: reporting a partial submission as "all predictions held", spending an
unqualified comparison as evidence, opening branch mode without a frozen rule, and accepting an
observation whose source digest does not match its content. They are enforced by
`report_unqualified_result_as_held` — a decision may only claim `PREDICTION_HELD` when its own
assessment is evidence-eligible.

The runner also projects the insight classes of any cards the case carries, so
`certify_insight_from_unqualified_evidence` is a checkable tripwire: a card may only reach
`evidence_supported_insight` while the upstream comparison was qualified evidence.

## 6. End-to-end smoke test

`smoke` runs the whole loop on a synthetic route: initialise a state, build the memory, freeze
a prediction, inject a synthetic observation, classify it, choose the next action, then
simulate a restart and confirm that Bootstrap is refused and the recovered brief carries the
mechanism and its boundaries. The canonical state is byte-compared before and after.

Every synthetic value is tagged `SYNTHETIC FIXTURE`. **None of it is scientific evidence.**

## 7. Commands

```sh
python3 scripts/research_replay.py validate    --case examples/replay/adversarial/adv1.json
python3 scripts/research_replay.py show        --case examples/replay/adversarial/adv1.json
python3 scripts/research_replay.py run         --case examples/replay/adversarial/adv1.json --arm full_cie
python3 scripts/research_replay.py suite       --dir examples/replay/adversarial --runs 2
python3 scripts/research_replay.py ablate      --dir examples/replay/adversarial --runs 2
python3 scripts/research_replay.py smoke       --work /tmp/cie-smoke
python3 scripts/research_replay.py adversarial --write examples/replay/adversarial
python3 scripts/research_replay.py --selftest
```

A different runner can be plugged in with `--runner module:function`; it receives the visible
view and the arm name, and must return a `replay-decision@1` object.

## 8. What has and has not been verified

**Verified offline, mechanically:** leak prevention, metric independence from the agent's
self-assessment, the ablation ladder on synthetic cases, the fourteen adversarial situations, and
the end-to-end state → prediction → revision → restart loop.

**Not verified:** real Agent A/B performance. No model was called, no real literature library
was used, and the fixtures are synthetic. The deltas in the ablation report are properties of
the offline runner and the fixtures, not measurements of scientific discovery ability. Any
claim of improvement requires a real runner, real cases with genuinely hidden outcomes, and
repeated blind evaluation.

## 9. Self-check

- [ ] No hidden string is reachable from the visible payload (`RP2`).
- [ ] An agent novelty rating is refused (`RP5`).
- [ ] No dimension is summed into a total.
- [ ] An unassessable dimension is `null`, not zero.
- [ ] An undersized sample reports `insufficient_sample` and claims nothing.
- [ ] Indistinguishable arms are reported as indistinguishable.
- [ ] Every adversarial case rewards correct stopping as much as correct continuing.
- [ ] Synthetic values are tagged and never enter real evidence.
- [ ] The smoke test leaves the canonical state byte-identical.
