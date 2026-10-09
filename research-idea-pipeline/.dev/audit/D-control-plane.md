# D — Control Plane Audit: Router / Scheduler / State / Execution Gate / Release Check

Scope: `research-idea-pipeline/` at worktree `research-idea-pipeline/skill-rsi-dev`.
Read-only audit. No file was modified except this report.

Source roots referenced below are relative to
`research-idea-pipeline/skill-rsi-dev/research-idea-pipeline/` unless written in full.

---

## 1. Scheduler's EIGHT hard priority levels

Frozen ordering, ids exactly as stored in `next_action_policy.priority`:

| # | id | trigger condition | action family |
|---|---|---|---|
| 1 | `integrity_violation` | `S-Integrity` fail | stop affected execution + repair |
| 2 | `unresolved_critical_attack` | unresolved R7/R10 critical attack | R10 disposition |
| 3 | `invalidated_dependency` | invalidated evidence dependency | R11 propagation + downstream recheck |
| 4 | `high_information_gain_test` | low-cost / high-EIG experiment | R9 |
| 5 | `paradigm_escape_if_stagnant` | stagnation | R3 `P1`–`P6` |
| 6 | `literature_collision` | literature collision | R5 |
| 7 | `local_optimization` | local optimum | R3 `local` / R6 |
| 8 | `narrative_or_venue_work` | narrative / venue calibration | R12 / R13 |

- Authoritative table: `references/scheduler-policy.md:45-54`; semantic reading `:56-64`;
  re-affirmed in §7 `:292` and self-check §8 `:299`.
- Machine skeleton (`next_action_policy.priority[]`): `templates/scheduler.template.json:5-16`.
- Within-level ordering is `EIG ÷ cost`, not a second formula: `references/scheduler-policy.md:120-121`,
  `:289`.
- Priority 1 is scope-limited: only contaminated work stops; integrity block is the only global
  stop (`:47`, `:56-60`).
- Not a ninth state object and not a 16th stage: `references/scheduler-policy.md:6-7`, `:22-26`,
  `templates/scheduler.template.json:3`.

Scheduler telemetry file path: `.research-idea-pipeline/routes/<R>/scheduler.json`
(`references/scheduler-policy.md:19`).

---

## 2. Router dispatch

Module: `scripts/preset_router.py` (3445 lines).

### Entry points
- CLI: `preset_router.build_parser()` `scripts/preset_router.py:2909-2933`; `main()`
  `:3204-3231`. Commands: `list|resolve|inspect|check|trigger|run|record|load|authorize`
  (`:2912-2913`); op functions `op_list:2951`, `op_resolve:2967`, `op_inspect:2983`,
  `op_load:3117`, `op_check:3126`, `op_trigger:3149`, `op_run:3159`, `op_record:3175`,
  `op_authorize:3072`.
- Library entry points:
  - `resolve(text, *, state, index, scheduler, extra_triggers)` `:979-1091` — the intent router.
  - `trigger(state, *, index, scheduler, revisions, records, index_missing, projection)`
    `:1504-1590` — loop recovery trigger engine.
  - `project_context(state_path, cognition_dir)` `:1623-...` — reads state/revisions/cards/scheduler.
  - `run_preset(preset_id, state_path, cognition_dir, *, apply)` `:2864-2895` — dispatch to handler.
  - `load_preset_context(preset_id, root)` `:2992-3042` — loads shared contract + exactly one protocol.
  - `run_router_fixtures(...)` `:3045-...`; `selftest()` `:3288-...`.
- Dispatch table: `HANDLERS` `:2828-2845` (16 handlers). ID list: `PRESET_IDS` `:711`
  (derived from `PRESETS = _merge_registry(ENFORCEMENT)` `:709`).

### The four semantic entries
`ENTRIES` `scripts/preset_router.py:151`:
`("start-project", "continue-research", "explore", "audit")`.
A preset never introduces a fifth (`:150`); only 3 entries are actually used by the 16 presets
(no preset routes to `start-project`). Expert `phase=R<n>` form is handled separately:
`_has_phase_entry` `:959`, `_entry_from_text` `:971`, HOLD branch `:1075-1078`.

### Resolution precedence (frozen)
Documented `:987-1001`; implemented:
1. explicit preset id → `trigger="explicit"` `:1046-1048`
2. alias `:1064-1070` (via `_intent_candidates` `:907`)
3. intent phrase + named entry → `trigger="entry"` `:1065-1066`
4. intent phrase alone → `trigger="intent"` `:1066`
5. loop auto-suggestion only when nothing else matched → `trigger="auto"` `:1079-1088`
Negation (`intent_negated`) `:1071-1074`; expert phase `:1075-1078`; ambiguous exact tie →
least-privilege preset `:1053-1063`; otherwise `no_intent_matched` `:1089-1091`.
Safety: `next_action` `"diagnose"` vs `"execute"` `:1036-1043`; read-only never escalates
`:1040`; auto candidates require confirmation unless read-only `:1086-1087`.

### Where a preset's allowed actions come from
Two layers, merged:
- **Enforcement table** (`ENFORCEMENT`, entries built by `_preset(...)` `:245-253`, with the
  default `"allowed": ()` / `"forbidden": ()` at `:249`; per-preset definitions `:265-592`).
  This is what the repository requires: aliases, signals, priority, guard params, `reuses`,
  `writes`, `allowed`, `forbidden`, `outputs`, `stops`.
- **Provided registry** `preset-registry.json` overlays id/entry/title/`execution_scope`/path/
  trigger/intent_examples via `_merge_registry()` `:658-...`.
- Merge product: `PRESETS` `:709`, `PRESET_IDS` `:711`, `presets_by_id()` `:721`.
- Validity of `allowed`/`forbidden` (must be non-empty tuples) enforced by `registry_errors()`
  `:734-876`, specifically `:773-775` (`PR2`).
- Execution authority is not `allowed` but the frozen privilege map: `EXECUTION_SCOPES` `:82-86`,
  `SCOPE_PRIVILEGE` `:92-108`, `PRIVILEGE_RANK` `:111-112`, `SCOPE_CANONICAL` `:116-128`.
- Handler output is gated by privilege: `run_preset` compares canonical digests and marks a
  read-only preset that wrote state as `BLOCKED` + `PR9` `:2885-2888`.

Preset → entry/scope mapping table: `references/preset-policy.md:27-44`; registry:
`preset-registry.json:4-213`.

---

## 3. Canonical Research State

### The eight canonical object classes
`state_check.OBJECT_KEYS` `scripts/state_check.py:143-152`:

| key | id prefix |
|---|---|
| `claims` | `C` |
| `evidence` | `E` |
| `assumptions` | `AS` |
| `hypotheses` | `H` |
| `experiments` | `X` |
| `literature` | `LIT` |
| `failures` | `F` |
| `uncertainties` | `U` |

Plus two spec-required non-first-class carriers `EXTRA_KEYS = ("assurance", "repairs")`
`:154`; `CHECKED_KEYS` `:155`; `FIRST_CLASS_KEYS` `:205`.

### Exact top-level keys
From `templates/research-state.template.json` (order preserved):
`_schema` (`research-idea-pipeline/research-state@1`), `state_version`, `_usage`,
`contract`, then the eight arrays, then `assurance`, `repairs`, `narrative_view`, `reviews`,
`decision`, `_outcome_usage`, `_execution_usage`.
`_Context` mirrors the checked set: `scripts/state_check.py:750-797`.
Top-level wrapping is tolerated (single key `world_model` / `research_state` / `state`) via
`WRAPPER_KEYS` `:158` and `_unwrap()` `:537-547`. A canonical implementation uses no wrapper
(`templates/research-state.template.json` `_usage`).

### Where schema is defined / validated
- Shape gate S1—S7: `SHAPES` `scripts/state_check.py:319-328`, implemented `shape_errors()`
  `:560-688`; runs before V-rules (short-circuit) `check_state():1732-1752`.
- Reference integrity V1—V24: `RULES` `:278-303`, `RULE_ORDER:304`; `CHECKS` dispatch
  `check_state():1756-1757`.
- Structural precondition (exit 4): `structure_error()` `:691-727`; entry `check_state()`
  `:1732`, file wrapper `check_file()` `:1796-1816`.
- Additive extensions checked inside state: `EO1` (`evidence_outcome.state_errors`) and `EX1`
  (`execution_gate.state_errors`) `:1759-1771`.
- Authoritative prose: `references/research-state-policy.md` §3 (fields) / §4.0 (S1—S7) /
  §4.1 (V1—V24). Parity is machine-enforced by release step 4 (`release_check.py:108-128`).
- CLI: positional `<state.json>` plus `--check|--json|--quiet|--selftest|--list-rules`
  (`build_parser` `:1832-1846`; there are **no subcommands**).

---

## 4. Strategy memory / strategy revisions read paths + insertion point

### Where the router/adapter read strategy memory
- `strategy_memory.strategy_decision(state, index, scheduler, revisions)` `scripts/strategy_memory.py:1016-1088`
  calls `recommend_strategy()` `:666` and `_legal_actions()` `:985` →
  `scheduler_verdict()` `:920-982` → `execution_gate.scheduler_check()`.
- `strategy_memory.scheduler_verdict()` pass/fail is the whole-scheduler verdict; no English
  error-string parsing `:930-937`.
- Decision record writer/reader: `record_strategy_decision()` `:1091-1122` (writes only
  `scheduler.strategy_decisions[]`, capped by `DECISION_LOG_LIMIT` `:1121`);
  `latest_strategy_decision()` `:1125-1130`.
- Schema constant: `SCHEMA_STRATEGY_DECISION = "research-idea-pipeline/strategy-decision@1"`
  `strategy_memory.py:851`.
- Router consumers:
  - `_handle_strategy_evolution()` `preset_router.py:2689-2760` — advice → decision → dispatch;
    calls `sm.strategy_decision` `:2698`, `sm.strategy_updates` `:2700`,
    `sm.record_strategy_decision` `:2720`, writes `scheduler.json` `:2721-2724`.
  - `_handle_hypothesis_rebalance()` `:2763-2797`.
  - `_handle_research_loop()` `:2055-2118` reads `sm.latest_strategy_decision(ctx["scheduler"])`
    `:2060`, marks `stale` when `state_version` changed `:2071`, and prefers the recorded
    dispatch action while legal `:2095-2098`.
  - `_strategy_updates()` wrapper `:1359-1373`; revision records `_strategy_revision_records()`
    `:2316-2338`; append `_append_strategy_revisions()` `:2341-2364`; identity/idempotency
    `_revision_identity()` `:2309-2313`.
- Revision validation: `sm.validate_strategy_revisions()` `strategy_memory.py:1171-1206`
  (`SV1/SV3/SV5/SV6/SV8`); payload projection `sm.revision_payload()` `:1141-1168`.
- Actor authority: `cognition.STRATEGY_REVISION_ACTORS` `cognition.py:116`,
  `STRATEGY_UPDATE_ACTOR = "CIE"` `cognition.py:119`.
- Strategy revision file: `<route>/cognition/model-revisions.jsonl`
  (`cognition.REVISIONS_NAME` `cognition.py:69`; loader `load_revisions():361`).
- Boundary rules: `references/preset-policy.md:199-225`; telemetry schema
  `references/scheduler-policy.md:125-158`.

### Minimum-change insertion point for a new policy-candidate layer
Best fit is a **new preset + handler**, not a new state class:
1. Add one entry to `ENFORCEMENT` in `preset_router.py` (`:265-592`) with
   `group="evolution"`, `entry="continue-research"` or `"audit"`,
   `execution_scope="strategy_update"` or `"decision_only"`, and `reuses=("strategy_memory",
   "cognition", ...)`.
2. Register it in `HANDLERS` `:2828-2845` and in `preset-registry.json` (`:4-213`); update the
   provider id list so `registry_errors` `:838-855` (exactly 16) stays green — this is the one
   hard coupling: the current check freezes `len(PRESETS) == 16` (`:841`) and
   `release_check.step_preset_library` (`release_check.py:790-791`).
3. Reuse `sm.strategy_decision` / `sm.record_strategy_decision` for ranking, and
   `_append_strategy_revisions` for the candidate ledger, so AALG/priority/EIG tiers stay
   untouched (`references/preset-policy.md:205-218`).
4. If it needs new telemetry, add a key beside `strategy_decisions[]` in `scheduler.json`
   (telemetry is out of state by the partition rule, `references/scheduler-policy.md:24-26`),
   and add a `release_check` step.
Alternative narrow seam (no preset count change): extend `sm.strategy_decision()` `:1016` with
a candidate source that only reorders within the top tier, and surface it through the existing
`strategy_decisions[]` record. `_loop_step()` `preset_router.py:1940-2053` already consumes
`ctx["scheduler"].next_actions` and `latest_strategy_decision`, so a new layer that emits
admissible actions needs no loop change.

Do **not** add a ninth state class (forbidden by `SE2`
`references/structural-equivalence-policy.md:46`, partition rule
`references/scheduler-policy.md:24-26`).

---

## 5. execution_gate / experiment_execute

### execution_gate.py (384 lines) — additive PEIG/AALG contract checks
- Constants: `MODES` `:12`, `DEFAULT_POLICY` `:13-14` (`max_preflight_revisions=3`,
  `max_equivalent_diagnostics=2`, `max_pilot_runs=1`, `max_pilot_hours=2`,
  `receipt_ttl_seconds=900`), `FAIR` `:15`, `CAPACITY` `:16`, `OPTIMIZATION` `:17`.
- Schema validator: `schema_errors(value, name)` `:20-52` (reads `schemas/<name>`).
- `source_observation(e)` `:62-66`; `evidence_snapshot(state)` `:69-80`;
  `target_lineage` `:83-92`; `target_roots` `:95-97`; `risks` `:100-110`.
- `design_projection(protocol)` `:113-122` (strips labels/seed/narrative);
  `review_digest(protocol)` `:125-126`; `family_key(state, experiment)` `:129-135`.
- `peig(state, experiment_id)` `:166-248` — the hard gate. Statuses
  `PASS | PILOT_ONLY | HOLD`. Key hard errors:
  `MISSING_PROTOCOL`, `MISSING_PREREGISTRATION`, `OUTCOME_POLICY_REQUIRED`, `STOP_RULE`,
  `STAGE_PERMISSION`, `TARGET_MISMATCH`, `COMPETITOR_BINDING_MISMATCH`,
  `OUTCOME_PREREGISTRATION_MISMATCH`, `MISSING_COMPETITOR`, `EVALUATION_MISMATCH`,
  `DUPLICATE_DESIGN_ID`, `MISSING_IDENTIFYING_COMPARISON`, `MISSING_VALID_COMPARATOR`,
  `UNFAIR_BUDGET`, `UNFROZEN_DOSE`, `DUPLICATE_SEEDS`, `BUDGET_MISMATCH`,
  `ARM_PROTOCOL_MISMATCH`, `UNTYPED_R7_RISK`, `RISK_TRACEABILITY`,
  `UNREGISTERED_CAPACITY_RISK`, `INVALID_SCOPE_LIMIT`, `MISSING_RISK_CONTROL`,
  `INEFFECTIVE_RISK_CONTROL`, `SCIENTIFIC_REVIEW`, `UNIDENTIFIABLE`, `HUMAN_EXCEPTION`,
  `PILOT_NO_DECISION_VALUE` `:168-248`. Frozen budget key `budget_hours` `:246`.
- `diagnostic_digest` `:251-259`; `diagnostic_check(state, d, history, policy)` `:262-306`
  (AALG: `max_equivalent_diagnostics`, `STOP_DIAGNOSIS`/T8, `PIVOT_RECOMMENDED`).
- `state_errors(state)` `:309-336` — `EX1` extension checks: execution record shape,
  receipt binding, dry-run is telemetry, protocol immutability.
- `actual_eig(receipt)` `:339-356` — recomputes `observed_delta` + rating
  `high|medium|low|zero` from the immutable transaction.
- `scheduler_check(state, scheduler)` `:359-384` — schema + `state_check` + `STALE_SCHEDULER`
  + EIG records (`FABRICATED_EIG`, `MISSING_EIG`) + `BLOCKED_SCHEDULED_EXPERIMENT`,
  `PEIG_HOLD`.

### experiment_execute.py (311 lines) — managed execution
- `write_new(path, value)` `:26-27` (exclusive create).
- `class Ledger` `:30-78` — `locked()` context manager with `fcntl.flock(LOCK_EX)` `:37-63`,
  HMAC `seal()` `:65-66`, `append()` `:68-78` (fsync + `.head.pending` → `os.replace`);
  policy frozen at first event `:56-62`; tamper/truncation fail-closed `:54-55`.
- `config_binding(protocol)` `:81-82`; `manifest_binding(state, experiment, manifest)`
  `:85-116` — binds state/protocol/preregistration/manifest digests, code/config/split/
  preregistration file bytes, engine source digests. Errors: `INVALID_MANIFEST`,
  `EXECUTION_CWD_MISSING`, `DUPLICATE_MANIFEST_FILE`, `CONFIG_PROTOCOL_MISMATCH`,
  `SPLIT_PROTOCOL_MISMATCH`, `PREREGISTRATION_FILE_MISMATCH`, `MISSING_CONTENT_BINDING`,
  `GPU_MASK_MISMATCH`, `UNBOUND_EXECUTABLE`, `UNBOUND_COMMAND_FILE`.
- `execution_review_digest(...)` `:119-127` (must equal
  `execution_protocol.scientific_review.execution_digest`).
- `diagnose(...)` `:130-136`; `diagnostic_for(...)` `:139-151` (AALG seal, single-use);
- `issue(...)` `:154-200` — hard gates: `PREFLIGHT_REVISION_LIMIT`,
  `STATE_INVALID`, `SCHEDULER_GATE`, `POST_EXECUTION_PREREGISTRATION`,
  `REQUESTED_BUDGET_EXCEEDS_PROTOCOL`, `PILOT_BUDGET_EXHAUSTED`,
  `FORMAL_BUDGET_EXHAUSTED`, `EXPIRED_OR_OUT_OF_SCOPE_HUMAN_EXCEPTION`,
  `EXECUTION_REVIEW_MISMATCH`. Receipt keys `:194-197`: `binding, issued_at, expires_at,
  permission, family, requested_hours, peig, human_exception, scheduler_digest, seal`.
- `run(...)` `:203-264` — `FORGED_RECEIPT`, `UNKNOWN_OR_USED_RECEIPT`, `EXPIRED_RECEIPT`,
  `SCHEDULER_RECEIPT_MISMATCH`, `PREFLIGHT_REVISION_LIMIT`, `STOP_DIAGNOSIS`,
  `RECEIPT_CONTENT_MISMATCH`, `GATE_CHANGED`, budget re-check under one lock, then
  **atomic consume before launch** `:252-255`; preview is zero-side-effect `:240-251`.
  `CUDA_VISIBLE_DEVICES` forced `:259`; timeout `hours*3600/len(gpu_devices)` `:261`.
- `verify_result_execution(state, ledger)` `:267-279`.
- CLI subcommands: `issue|run|diagnose|scheduler-check` `:283-291`.

GPU authorization summary: no legacy GPU launcher; all managed execution goes through
`experiment_execute.py`; a forced mask binds listed GPUs; direct `torchrun`/SSH/sbatch/
detached jobs are explicitly outside interception (`references/execution-identifiability.md:103-137`,
esp. `:125`, `:132-137`; preview semantics `:168-177`).

---

## 6. Project route directory conventions

- Control plane root: `.research-idea-pipeline/` (`references/project-layout.md:118`).
  It is the machine control plane and must be *ignorable* by human readers (`:967-970`);
  internally it optimizes schema clarity / stable IDs / mutation safety / append-only
  provenance (`:972-977`).
- Layout (`references/project-layout.md:118-128`):
  - `.research-idea-pipeline/project/{contract.json, route-registry.json, constraints.json}`
  - `.research-idea-pipeline/routes/<R>/research-state.json`
  - `.research-idea-pipeline/routes/<R>/history/`, `actions/`,
    `populations/{archive,intermediates,fingerprints}/`,
    `assurance/{structural-equivalence}/`, `repairs/`, `reviews/`,
    `experiments/<XID>/{preregistration.json,state-delta.json}`
  - `.research-idea-pipeline/meta/{operator-stats.json, eig-calibration.json,
    recurring-failures.json, scheduler-history.jsonl}`
  - `.research-idea-pipeline/cache/{literature,retrieval,embeddings}/`
  - `.research-idea-pipeline/runtime/{locks,tmp,tool-output}/`
- Runtime state actually written by the audited modules:
  - canonical state: `<route>/research-state.json` (`cognition.STATE_NAME` `cognition.py:73`).
  - scheduler telemetry: `<route>/scheduler.json` (`cognition.SCHEDULER_NAME` `cognition.py:74`;
    `strategy_memory._load_scheduler` `strategy_memory.py:1213-1214`;
    `references/scheduler-policy.md:19`).
  - cognition projection + strategy revisions: `<route>/cognition/`
    (`cognition.COGNITION_DIRNAME` `:67`) with `model-revisions.jsonl` (`REVISIONS_NAME` `:69`).
  - recovery ledger for the trigger engine: `<route>/cognition/recovery-log.jsonl`
    (`preset_router.RECOVERY_LOG_NAME` `preset_router.py:62`; `ledger_path():1387-1388`;
    `references/preset-policy.md:131`).
  - execution ledger: `<route>/.execution/` with `lock`, `key`, `events.jsonl`, `head`
    (`experiment_execute.py:298` default `args.state.parent/'.execution'`; `Ledger` `:30-78`).
  - outcome assurance artifacts: `<route>/assurance/outcome/<analysis_id>.json` plus `.lock`
    (`evidence_outcome.store_assurance` `evidence_outcome.py:876-915`;
    `references/preset-policy.md:183-184`).
  - cross-route read-only roll-up: `.research-idea-pipeline/meta/operator-stats.json`
    (`references/scheduler-policy.md:192-194`, `references/project-layout.md:124-132`).
- **Route id**: the route *letter* `<R>` (e.g. `A`, `B`, `T`), not the R stage number
  (`references/project-layout.md:88`, `:162-164`, `:226-229`). Programmatically it is the
  directory that owns the canonical state: `cognition.route_of(state_path)` returns
  `state_path.parent.name` (`cognition.py:403-405`). Route management metadata lives in
  `.research-idea-pipeline/project/route-registry.json`, one record
  `{name, path, status, primary, parent, forked_from}` per route, `status` ∈ frozen six values
  `candidate|active|supporting|dormant|archived|merged` (`references/project-layout.md:900-918`).
- Git boundary: `.research-idea-pipeline/**/research-state.json`, `history/*`,
  `experiments/*/preregistration.json`, `meta/*` are versioned; `cache/` and `runtime/` are not
  (`references/project-layout.md:936-948`). Stage names never become directories (DI-1 `:45`).
  Single-writer rule for canonical state `:685`.

---

## 7. release_check.py — every step and its fixture/test

Gate contract in the module docstring `release_check.py:1-55`. `_run()` executes with
`cwd=str(ROOT)` and merges stderr into stdout `:72-81`. Verdict is the last printed line
(`PASS`/`FAIL`) and exit code `:895-907`. The `STEPS` tuple `:875-892` is the real order
(docstring numbering 1–17 is out of sequence).

| # | step fn | title | fixture / test |
|---|---|---|---|
| 1 | `step_tests` `:88-91` | offline suite | `python -m unittest discover -s scripts -p test_*.py` |
| 2 | `step_selftest` `:94-99` | `state_check --selftest` | `scripts/state_check.py --selftest` |
| 3 | `step_template` `:102-105` | template validates | `scripts/state_check.py --check templates/research-state.template.json` |
| 4 | `step_rule_table_parity` `:108-128` | S1—S7 / V1—V24 verbatim | `--list-rules` vs `references/research-state-policy.md` (§4.0 `形状`, §4.1 `硬`) |
| 5 | `step_readwrite_parity` `:131-178` | read/write table parity | `SKILL.md` §0 table vs policy §5 vs each `references/phase-*.md` (needs ≥20 rows) |
| 6 | `step_referenced_scripts_exist` `:181-194` | doc-referenced scripts exist | scans `*.md` for `scripts/<name>.py` (skips `docs/`, `.git`, `.dev/`) |
| 7 | `step_structural_equivalence` `:197-215` | EQ1—EQ13 + NN1—NN14 | `scripts/structural_equivalence_check.py --selftest`; `templates/structural-equivalence-audit.template.json`; `examples/structural-equivalence/*.json` (≥5 artifacts) |
| 8 | `step_rhetorical_realization` `:218-236` | RE1–RE5 | `scripts/rhetorical_realization.py generate` on `examples/narrative-realization/{source-state.json,manifest.json}`; re-validates each variant with `validate_rhetorical_variant.validate` + `registry()` |
| 9 | `step_evidence_outcome` `:239-262` | source/state/Assurance/decision | `examples/evidence-outcome/{positive,valid-negative,invalid-experiment,pivot,mixed}.json` (exact stem set); `eo.validate/apply/decision_gate`; `sc.check_state` |
| 10 | `step_execution_identifiability` `:758-773` | PEIG/AALG schemas + CT→MRI mutation | `examples/preflight-identifiability/ct-mri.json` (`schema == preflight-e2e@1`); `eg.peig`; `templates/{preflight-protocol,diagnostic-protocol,execution-manifest}.template.json` + their schemas; `templates/scheduler.template.json` + `scheduler.schema.json`; capacity mutation must flip to `HOLD` |
| 11 | `step_cognitive_memory` `:265-301` | CIE fixture | `examples/cognition/{state.json,model-revisions.jsonl}` copied into temp `<route>/cognition/`; `cognition.py build` → assert canonical state byte-identical → `check` → `build` reproducible; no diagnostics |
| 12 | `step_prediction_comparator` `:312-593` | criteria/freeze/discrimination/source binding | `examples/cognition/{state.json,prediction-observation.json,INSIGHT_CARDS_NAME}`; `prediction_compare.assess_experiment/criterion_errors/evidence_transition_allowed/distinguishability/scope_covers/classify_insight/insight_card_errors`; many mutation negatives |
| 13 | `step_legacy_handoff` `:596-669` | lossless takeover / idempotence | `examples/cognition/state.json` + synthetic `scheduler.json` in temp `.research-idea-pipeline/routes/A/`; `legacy_handoff.detect/take`; `cognition.STATE_NAME/COGNITION_DIRNAME`, `lh.OWNED_FILES`; second pass uses `test_cognition.legacy_project_state()` |
| 14 | `step_scientific_value` `:672-710` | no aggregate, read-only anchor, no operator ban | `strategy_memory._fixture()`, `cognition.full_index`, `sm.value_assessment/validate_value/operator_priors/validate_priors/recommend_strategy`; `sm.BANNED_AGGREGATE_KEYS`; rules SV1/SV2/SV5/SV7 |
| 15 | `step_discovery_replay` `:713-755` | adversarial replay / leak guard / ablation / smoke | `research_replay.load_cases(ROOT/"examples/replay/adversarial")` vs `rr.adversarial_cases()`; `visible_view/leak_scan/case_errors/run_case/run_suite/smoke` |
| 16 | `step_preset_library` `:776-827` | 16 presets / router / triggers / adapter | `preset_router.registry_errors`, `run_router_fixtures()` (`router-fixtures.json`, expects 53/53), `load_preset_context("research-review")` (`not_loaded == 15`), `PRESETS`==16 and `HANDLERS`==`PRESET_IDS`, per-preset resolve, negation/read-only/descriptive negatives, `preset_router._fixture`, `sm.SCHEMA_STRATEGY_DECISION` |
| 17 | `step_release_metadata` `:830-872` | version consistency | `SKILL.md` `metadata.version`; root + component `README.md`; `CHANGELOG.md`; `docs/releases/v<version>.md`; `preset-registry.json` `schema_version == 0.1`; git tag `research-idea-pipeline/v<version>` must equal HEAD if it exists; runs `scripts/test_release_metadata.py` |

**To add a new module to the gate**: add one `step_<name>() -> (bool, str)` function and one
tuple entry in `STEPS` `:875-892`. It will automatically be counted as a failure if it raises
`:900-901`. Follow the existing pattern of using a real shipped fixture and at least one
mutation negative (see `release_check.py:197-215` and `:312-345` for the "a gate that cannot be
made red is not a gate" convention). A new script referenced from any `*.md` is automatically
covered by step 6 `:181-194`; if service is required for the new module, it must be documented
there to stay visible.

---

## 8. Idempotency / atomic-write / file-lock helpers to reuse

Reuse, do not reinvent:

- **Digests / canonical JSON**: `cognition.digest_of(value)` `cognition.py:295-296`;
  `cognition.digest_of_lines()` `:299-300`; `evidence_outcome.digest()` (used by gate/router).
- **Atomic replace under lock**: `evidence_outcome.store_assurance()` `evidence_outcome.py:841-915`
  — `fcntl.flock(lock, LOCK_EX)` on `path.with_suffix('.lock')` `:877-880`, write
  `<name>.pending`, then `os.replace(pending, path)` `:906-915`. This is the canonical
  "validate → bind → lock → replace" pattern and already encodes overwrite rules
  (`already_stored` / `replaced_stale` / `replaced_forced` / `current_review_kept`).
- **Authenticated append-only ledger**: `experiment_execute.Ledger` `experiment_execute.py:30-78`
  — `locked()` `:37-63`, `seal()` `:65-66`, `append()` `:68-78` (fsync + `.head.pending` →
  `os.replace`), `write_new()` `:26-27`. Use for any new append-only, tamper-evident telemetry.
- **Append-only JSONL with idempotency by event identity**: `preset_router._revision_identity()`
  `preset_router.py:2309-2313`, `_strategy_revision_records()` `:2316-2338`,
  `_append_strategy_revisions()` `:2341-2364` (validate whole set first; skip already-seen
  identities; append only if fresh).
- **Read-tolerant JSONL loaders**: `cognition.load_revisions()` `cognition.py:361-394` (torn
  last line becomes a diagnostic, not a crash); `preset_router.load_ledger()` `:1391-1409`.
- **Guarded output paths**: `evidence_outcome._assurance_output()` `evidence_outcome.py:820-831`
  refuses writes outside the state route.
- **Exclusive-create outputs**: `write_new()` `experiment_execute.py:26-27`;
  `op_authorize` receipt path refusal `preset_router.py:301`.
- **Whole-scheduler verdict before dispatch**: `strategy_memory.scheduler_verdict()`
  `strategy_memory.py:920-982`; `_legal_actions()` `:985-991`.
- **Anti-recursion guard / cooldown / attempt cap**: `preset_router.recovery_guard()`
  `:1412-1449`, `_guard_candidate()` `:1458-...`, `signal_fingerprint()` `:1376-1380`.

Note: there is **no** generic `atomic_write_json()` helper today; the pattern is inlined in
`evidence_outcome.py` and `experiment_execute.py`. A new module should copy the
locked-pending-`os.replace` idiom rather than add `write_text` of a state/scheduler file
(compare the direct `path.write_text(json.dumps(...))` calls at `preset_router.py:2721-2723`,
`:3108`, `strategy_memory.py:1622`).

---

## 9. Exact test invocation convention

- Full suite, from `research-idea-pipeline/` (the package root; `ROOT` in `release_check.py:68`):
  `python3 -m unittest discover -s scripts -p "test_*.py"`
  (`SKILL.md:1476`, `docs/releases/v1.0.0.md:194`, `release_check.py:89`
  `["-m","unittest","discover","-s","scripts","-p","test_*.py"]`).
- Single module: `python3 -m unittest discover -s scripts -p 'test_rhetorical_realization.py'`
  (`SKILL.md:1511`).
- `subprocess` cwd for every gate check is `ROOT` = the component root
  `research-idea-pipeline/` (`release_check.py:68`, `:80`), i.e. run from there.
- Long-form gate: `python3 scripts/release_check.py`; verdict = last line / exit code
  (`release_check.py:12-16`, `:895-907`). Per-item `[ok]/[FAIL]` lines are diagnostic only.
- Test files are `scripts/test_*.py` (`glob` inventory: 29 test modules).

---

## 10. Constraints a new module must respect

1. **No new canonical state.** Only the eight object classes plus `assurance`/`repairs`
   (`state_check.OBJECT_KEYS:143-152`, `EXTRA_KEYS:154`). Mechanism that must live "in state"
   must be a field on an existing class; system self-description must leave state
   (`references/scheduler-policy.md:24-26`; `SE2`
   `references/structural-equivalence-policy.md:46`). No S/V rule beyond the frozen namespaces
   (`state_check.py:106-110`).
2. **No harness changes.** `preset_router.py:20-23` ("No second research pipeline"); every
   preset only *calls* existing gates. The scheduler may only order, never change standards,
   never write `research-state.json`, never become evidence
   (`references/scheduler-policy.md:208-214`). Router adds no online model
   (`references/preset-policy.md:77`).
3. **No source self-modification at runtime.** The control plane only writes telemetry /
   derived projections / append-only ledgers. The repository's own boundaries encode this:
   read-only presets that write canonical are `BLOCKED` + `PR9` (`preset_router.py:2885-2888`);
   `cognition` aborts if a build touched canonical (`cognition.py:2188-2192`); the execution
   ledger seals engine source digests but never rewrites them
   (`experiment_execute.py:109-111`). A new module must write only under the route's
   `.research-idea-pipeline/` control-plane paths, never into `scripts/`, `schemas/`,
   `templates/`, or another route.
4. **AALG budgets are frozen and must not be refreshed.** Defaults
   `execution_gate.DEFAULT_POLICY:13-14`; server-side frozen at first operation
   `experiment_execute.py:56-62`; strategy decisions touch only `strategy_decisions[]`
   (`strategy_memory.py:1096-1102`; `references/preset-policy.md:131-132`, `:218`).
5. **Read-only never escalates** (`preset_router.py:1040`, `SCOPE_PRIVILEGE:92-108`,
   `SCOPE_CANONICAL:116-128`; `references/preset-policy.md:19`).
6. **Evidence gate cannot be bypassed** — R8/R9.O/R10/R11, `PQ1`–`PQ8`, `IC1`–`IC6`,
   PEIG/AALG stay authoritative (`references/preset-policy.md:15-16`).
7. **Engineering failure ≠ scientific refutation**
   (`preset_router.ENGINEERING_FAILURE_KINDS:198-202`,
   `SCIENTIFIC_FAILURE_KINDS:205-207`; `references/preset-policy.md:18`).
8. **Route isolation.** Cross-route imports are forbidden; shared logic sinks to the canonical
   implementation (`references/project-layout.md:183`). One canonical state per route
   (DI-3 `:47`).
9. **Release gate must stay green.** Any new documented script must exist (step 6), any change
   to rules tables must be mirrored (steps 4/5), and a new behavior should ship with a
   mutation-negative step (steps 7–17 pattern).

---

## Gaps and risks observed (read-only)

- `state_check.py --selftest` help text says "S1—S8" (`state_check.py:1844-1845`) while the
  implemented shape namespace is S1—S7 (`SHAPES:319-328`). Cosmetic drift, but release step 4
  only compares S/V rules (`release_check.py:119-124`), so an S8 mention is unchecked.
- `release_check.py` docstring numbering 1–17 disagrees with the executable `STEPS` order
  (`:875-892`), which lists execution-identifiability (10) and cognitive-memory (11) before
  prediction-comparator (12), and release-metadata (17) before preset-library (16). Only the
  tuple matters; the docstring is misleading for anyone adding a step.
- Preset count is hard-frozen at 16 in two places (`preset_router.registry_errors:841`,
  `release_check.py:790-791`), so adding an RSI/policy-candidate preset requires editing both
  and the registry id-order check `:854`.
- Scheduler telemetry writes in `preset_router.py:2721-2723` and `strategy_memory.py:1622` are
  plain `write_text` (no lock/temp-replace), unlike `evidence_outcome.store_assurance`. A new
  module that also writes `scheduler.json` should use the locked-replace idiom to avoid torn
  writes.
- Priority semantics are documented and schema-shaped but **not enforced** by
  `scheduler_check()`: it validates schema, state version, EIG records and per-action legality,
  not that `next_actions[]` follows the eight-level order or `EIG ÷ cost`
  (`execution_gate.py:359-384`). Ordering is advisory in `strategy_memory.strategy_decision`.
- `_loop_step()` consumes `scheduler.next_actions[0]` without re-deriving its priority tier
  (`preset_router.py:2042-2049`); it trusts the producer, consistent with "telemetry is not
  evidence" but worth knowing when adding a policy layer.
