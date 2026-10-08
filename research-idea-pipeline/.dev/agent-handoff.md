# CIE development handoff (branch-local)

Branch: `feat/cognitive-insight-engine`. Base: `main` @ `1157d28` (= `origin/main`).
Scope: `research-idea-pipeline/` only. No push, no merge, no PR.

## Phases

| Phase | Scope | Status |
|---|---|---|
| 1 | Persistent cognitive memory | done — commit 1 |
| 2 | Prediction, anomaly, mechanism competition | pending |
| 3 | Scientific value and adaptive discovery | pending |
| 4 | Discovery replay and verification | pending |

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

## Open items carried into Phase 2

- `pending_predictions` uses the `<XID>:<OID>` reference format; Phase 2 must resolve and
  validate it against `experiments[].preregistration.outcomes`.
- Anomaly records currently carry a descriptive `frozen_prediction`. Phase 2 replaces the
  free text with a comparator result and adds exploratory-anomaly handling.
- `competition_open` accepts `decidable`; Phase 2 must make distinguishability mechanical.
