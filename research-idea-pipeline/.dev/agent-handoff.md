# CIE development handoff (branch-local)

Branch: `feat/cognitive-insight-engine`. Base: `main` @ `1157d28` (= `origin/main`).
Scope: `research-idea-pipeline/` only. No push, no merge, no PR.

## Phases

| Phase | Scope | Status |
|---|---|---|
| 1 | Persistent cognitive memory | done — commit 1 |
| 1b | Legacy Research Handoff (Phase 1 extension, requested mid-flight) | done — commit 2 |
| 2 | Prediction, anomaly, mechanism competition | done — commit 2 |
| 3 | Scientific value and adaptive discovery | done — commit 3 |
| 4 | Discovery replay and verification | done — commit 4 |

## Phase 1 record

New files

- `scripts/cognition.py` — builder, validator, recall, context brief, CLI, selftest.
- `scripts/test_cognition.py` — 67 offline tests.
- `references/cognitive-memory-policy.md` — memory classes, layers, `CM1`—`CM9`, lifecycle.
- `docs/cognitive-insight-engine.md` — architecture and R0—R14 interface map.
- `examples/cognition/{state.json,model-revisions.jsonl,README.md}` — synthetic fixture.
- `.dev/architecture.md`, `.dev/agent-handoff.md` — branch-local (must not merge).

Modified files

- `SKILL.md` — new §1.8 plus three rows in §2.
- `references/phase-r3-r6-discovery.md`, `phase-r8-evidence-contract.md`,
  `phase-r9-r11-experiment-loop.md` — CIE read/write touchpoints.
- `scripts/release_check.py` — step 11: fixture build/check/rebuild plus byte-identical state.
- `README.md` (component) and root `README.md` — capability description.

Deliberately unchanged: `state_check.py`, `research-state.template.json`,
`scheduler.template.json`, the four schemas, `evidence_outcome.py`, `execution_gate.py`,
`experiment_execute.py`, `structural_equivalence_check.py`.

Test results

- `python3 scripts/release_check.py` → `PASS`, 11 steps.
- `unittest discover -s scripts -p 'test_*.py'` → 919 tests, OK, 3 skipped (986 before Phase 4).
- `python3 scripts/cognition.py --selftest` → `selftest: PASS (0 failures)`.
- `python3 scripts/state_check.py --check examples/cognition/state.json` → exit 0.

Design decisions taken in Phase 1

1. Rule namespace `CM1`—`CM9`, not `C1`—`C9`: `C<n>` is the canonical claim id prefix and
   `V<n>` is taken. The first draft used `C1`—`C9` and was renamed.
2. Support level is derived, never declared. `declared_support` is accepted only so that it
   can be recorded as a `CM7` conflict.
3. `cognition/` sits in the route control plane beside `populations/` and `assurance/`,
   consistent with `project-layout.md` §11.2.
4. The shipped fixture stays a legacy project (no `contract.outcome_policy`), which is why it
   carries no `stop_rules` / `negative_knowledge`. Those paths are covered by unit tests that
   build their own state in memory.
5. `release_check.py` gained a step rather than `state_check.py` gaining a rule.

## Phase 1b / Phase 2 record

New files

- `scripts/prediction_compare.py` — comparator, competition verdicts, behaviour switch,
  insight-card validation and classification, CLI, selftest (`PC1`—`PC9`).
- `scripts/test_prediction_compare.py` — 79 offline tests.
- `scripts/legacy_handoff.py` — detection, audit `LH1`—`LH16`, takeover, report, rollback.
- `scripts/test_legacy_handoff.py` — 45 regression tests.
- `references/prediction-anomaly-competition.md`, `references/legacy-handoff.md`.
- `examples/cognition/prediction-observation.json`, `insight-cards.jsonl`.

Modified files

- `scripts/cognition.py` — legacy derivation (`LM-`/`LM-ALT-`/`LAN-`/`LCP-`), boundaries,
  `provenance_mode`, insight-card projection, per-kind revision payload contract
  (`PAYLOAD_KEYS`), `[RETROSPECTIVE]` brief markers.
- `references/research-state-policy.md` §3.5 — registers the additive
  `preregistration.outcomes[].criterion` slot and its dedicated-checker exception.
- `templates/research-state.template.json` — criteria on the sample preregistration.
- `references/invocation-prompts.md` §2 — handoff precondition, no fifth entry.
- `SKILL.md` §1.8/§1.9/§2, `README.md`, `docs/cognitive-insight-engine.md`.
- `scripts/release_check.py` — steps 12 and 13.
- `examples/cognition/*` — frozen criteria, `X2` discriminating experiment, freeze events,
  competition ownership, insight card.

Deliberate conservatism recorded in Phase 2

1. `claims[].known_flaws` is a V4 link, not a recorded refutation. The legacy derivation
   excludes failure anchors from support derivation (they would over-reach) while still
   citing them and surfacing them as `failed_repeat` boundaries. A revision event *may*
   assert the link, because then it has an author and a trigger.
2. `LH7` (terminal experiment without a preregistration) is blocking. `state_check` V21
   already rejects such a state, and inventing a frozen prediction to make it valid is
   exactly what the requirement forbids. The retrospective label is therefore reachable
   only for a frozen outcome without a criterion.
3. `criterion` extends an existing state slot rather than adding a parallel prediction
   schema; shape is enforced by `prediction_compare.py` under the §3.11 dedicated-checker
   exception, so `state_check.py` and S1—S7 / V1—V24 are untouched.

Test results

- `python3 scripts/release_check.py` → `PASS`, 13 steps.
- `unittest discover -s scripts -p 'test_*.py'` → 1043 tests, OK, 3 skipped.
- `prediction_compare.py --selftest` → PASS (0 failures).
- `legacy_handoff.py --selftest` → PASS (0 failures).

## Phase 3 record

New files

- `scripts/strategy_memory.py` — value model, taste memory, operator priors, menu ordering,
  `P4` context isolation, CLI, selftest (`SV1`—`SV8`).
- `scripts/test_strategy_memory.py` — 64 offline tests.
- `references/scientific-value-adaptive-discovery.md`.

Modified files

- `scripts/cognition.py` — `project_strategy`, optional `scheduler` in
  `build_index`/`full_index`/`validate_index`, `load_scheduler`, scheduler digest, brief
  strategy section.
- `SKILL.md` §1.8/§2, `README.md`, `docs/cognitive-insight-engine.md`, root `README.md`.
- `scripts/release_check.py` — step 14.

Decisions taken

1. `scheduler.json` stays read-only. Strategy decisions are recorded as `strategy_update`
   revision events in the cognitive layer, so telemetry never becomes a decision store and
   the eight-level ordering is untouched.
2. No aggregate anywhere. `SV1` rejects `score`/`total`/`overall`/`composite`/`weighted`/
   `aggregate`/`rating`; menu selection is lexicographic with no weights.
3. The exploration floor is mandatory and validated (`SV7`); a downgrade needs two
   independent failures, a scope and reactivation conditions (`SV5`).
4. `STRATEGY_MENUS` maps to *operator* names, not island names. The first draft used islands
   and the ranking silently treated every operator as neutral; an import-time assertion plus
   a selftest check now prevent that class of bug.
5. `P4` may read typed skeletons only; candidate content, domain terms and other islands'
   answers are refused (`SV6`).

Test results

- `python3 scripts/release_check.py` → `PASS`, 14 steps.
- `unittest discover -s scripts -p 'test_*.py'` → 1107 tests, OK, 3 skipped.
- `strategy_memory.py --selftest` → PASS (0 failures).

## Phase 4 record

New files

- `scripts/research_replay.py` — case schema, leak guard, offline runner, seven metrics,
  ablation, ten adversarial cases, end-to-end smoke, CLI, selftest (`RP1`—`RP5`).
- `scripts/test_research_replay.py` — 57 offline tests.
- `references/discovery-replay.md`, `examples/replay/README.md`,
  `examples/replay/adversarial/adv1..adv10.json`.

Modified files

- `SKILL.md` §1.8/§2, `README.md`, `docs/cognitive-insight-engine.md` (rule namespaces,
  interface map, verification status), root `README.md`.
- `scripts/release_check.py` — step 15.

Key findings worth carrying forward

1. `mechanistic_understanding` scored *higher* for the baseline than for the full arm on the
   first run, because the baseline dumped a whole claim statement while the runner articulated
   only the first hot mechanism's statement. The articulation basis was widened to every
   recalled mechanism's statement, conditions and boundaries, plus anomaly and boundary text.
   This is a recorded measurement artefact, not a tuned metric.
2. `memory_prediction` and `full_cie` are indistinguishable on all seven dimensions; the
   report lists them under `undifferentiated_arms` instead of implying the strategy layer was
   measured.
3. `expected_behaviour` labels were removed from the leak-marker set: they are evaluation
   instructions, not hidden research content. Cases that need extra markers list them in
   `must_not_appear`.
4. `load_cases` sorts by a natural key so `ADV2` precedes `ADV10`; the shipped fixtures and the
   in-code generator are asserted equal.

Test results

- `python3 scripts/release_check.py` → `PASS`, 15 steps.
- `unittest discover -s scripts -p 'test_*.py'` → 1164 tests, OK, 3 skipped.
- `research_replay.py --selftest` → PASS (0 failures).

## Open items carried into Phase 2

- (resolved in Phase 2) `<XID>:<OID>` references resolve and validate against
  `experiments[].preregistration.outcomes`; `frozen_prediction` is now accompanied by an
  `outcome_class` and an `experiment_id`; distinguishability is mechanical.
- (resolved in Phase 3) `boundaries` now exclude blocked menus; the strategy layer consumes
  `insights` classifications through the value/objection record.
- (resolved in Phase 4) replay harness, metrics, ablation, adversarial cases and the full
  regression record are shipped.
- Remaining debt is listed in `.dev/phase-report.md` §6; the durable parts are in
  `docs/cognitive-insight-engine.md` §8 and `references/discovery-replay.md` §8.
