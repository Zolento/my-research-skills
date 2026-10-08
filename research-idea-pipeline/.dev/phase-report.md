# CIE phase report — branch-local development record

Branch `feat/cognitive-insight-engine`, base `main` @ `1157d28` (= `origin/main` at start).
Scope: `research-idea-pipeline/` only. Nothing pushed, merged, tagged or released.

## 1. Commits

| # | Commit | Content |
|---|---|---|
| 1 | `c6c446b` | Phase 1 — persistent cognitive memory |
| 2 | `a411ebd` | Phase 2 — prediction / anomaly / mechanism competition, plus the Legacy Research Handoff (Phase 1 extension requested mid-flight) |
| 3 | `3433687` | Phase 3 — scientific value and adaptive discovery |
| 4 | (this commit) | Phase 4 — historical replay, metrics, ablation, adversarial cases, full verification |

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
| `python3 -m unittest discover -s scripts -p 'test_*.py'` | **1164 tests, OK, 3 skipped** (baseline before this branch: 919 tests, 3 skipped) |
| `cognition.py --selftest` | PASS (0 failures) |
| `prediction_compare.py --selftest` | PASS (0 failures) |
| `legacy_handoff.py --selftest` | PASS (0 failures) |
| `strategy_memory.py --selftest` | PASS (0 failures) |
| `research_replay.py --selftest` | PASS (0 failures) |
| `state_check.py --check examples/cognition/state.json` | exit 0 |
| `state_check.py --check templates/research-state.template.json` | exit 0 |

New tests by file: `test_cognition.py` 67, `test_prediction_compare.py` 79,
`test_legacy_handoff.py` 45, `test_strategy_memory.py` 64, `test_research_replay.py` 57 —
312 new tests, all offline, no GPU, no network, no model call.

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
