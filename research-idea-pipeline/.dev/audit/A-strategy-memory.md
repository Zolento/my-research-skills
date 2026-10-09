# Audit A — Strategy Memory + Strategy Decision Adapter

Read-only architecture audit. Worktree root: `/home/lenovo/code/myproj/skills-dev/research-idea-pipeline/skill-rsi-dev`.
Component: `research-idea-pipeline/`. All paths below are relative to that component.

Audit date: read-only pass over `scripts/strategy_memory.py` (1645 lines, full), the four
policy references, `scripts/preset_router.py` (targeted), `scripts/cognition.py` (supporting
constants + projection), `scripts/execution_gate.py:scheduler_check`, `schemas/scheduler.schema.json`,
`templates/scheduler.template.json`, `scripts/test_strategy_memory.py`, `scripts/test_preset_router.py`
(strategy section), `scripts/state_check.py` (grep only).

---

## 0. One-paragraph verdict

The subsystem is a **derived, read-only projection** over canonical state plus
`scheduler.json` telemetry, plus exactly **three writable surfaces**: (1) append-only
`cognition/model-revisions.jsonl` records of `kind: strategy_update`, (2) one open telemetry
key `scheduler.json.strategy_decisions[]`, and (3) `cognition/index.json` / `context-brief.md`
projections. The *"Strategy Decision Adapter"* is real code
(`strategy_memory.strategy_decision()`) and it does compute a with-memory / without-memory
reordering inside one `EIG ÷ cost` tier. But **nothing in production actually dispatches the
adapter's choice**: the only consumer (`preset_router._handle_research_loop`) concatenates the
chosen action into a human-readable `next_action` string, while `_loop_step()` keeps selecting
`scheduler.next_actions[0]` from the scheduler's own order. In addition, the persisted
`strategy_update` payload silently drops `menu`, so the adapter's own anti-stagnation branch
(`after.menu`) is dead in production. These two facts are the top blockers for any new
policy-candidate layer.

---

## 1. What the current Strategy Evolution can change

### 1.1 Pure derived outputs (no persistence, no write)

| Function | What it produces | Authority |
|---|---|---|
| `human_preferences(state)` :132 | `{goal, primary_anchor, constraints, resources, out_of_scope, provisional_anchor_rationale, authority:"user", mutable_by_agent:False}` read from `state.contract` | read-only; `SV3` forbids writing it back |
| `target_refs(state, index, target)` :179 | resolved canonical view (hypothesis/claim/experiments/uncertainties/competitions/repairs/assurance) | read-only |
| `value_assessment(state, index, target, scheduler=None)` :205 | per-dimension `decision_value` + `discovery_potential` + `considerations` + `objections` + `basis`; **no total** | read-only |
| `calibrated_preferences(state, index, scheduler=None)` :379 | `human_specified` / `evidence_calibrated[]` / `carried_experience` / `anchor_untouched:True` / `evidence_strength_hint` | read-only |
| `operator_priors(state, index, scheduler=None)` :473 | `by_operator{}` with `status`, `failures`, `successes`, `scope`, `reactivation_conditions`, plus `encouraged`, `discouraged`, `exploration_floor`, `min_independent_failures`, `recurring_failure_patterns` | read-only |
| `recommend_strategy(state, index, scheduler=None, revisions=None)` :666 | one chosen menu/operator/island/shift, lexicographic rank, `ordered_menus`, `alternatives`, `blocked_menus`, `exploration_floor`, `discouraged_but_admissible` | read-only |
| `strategy_decision(...)` :1016 | the adapter's with/without-memory decision | read-only; `record_strategy_decision` persists a copy |
| `p4_context(intermediates_dir)` :610 | de-domained P3 skeletons | read-only; **no production caller** |

### 1.2 The only writable structure produced here: `strategy_update` revision payload

`strategy_updates(state, index, scheduler=None)` :772 emits `updates[]` whose `after` block is:

```python
{"operator": <op>, "action": "discourage"|"encourage",
 "scope": [...], "reactivation_conditions": [...],
 "telemetry": {"source": ...}}
```
(`:795-798` for discourage, `:807-808` for encourage).

`revision_payload(update)` :1141 projects that into the **only** keys `cognition.PAYLOAD_KEYS["strategy_update"]`
accepts (`cognition.py:172-174`, `:203`):

```python
STRATEGY_FIELDS = ("note", "priors", "operator", "action", "evidence", "observations")
```

* `scope` / `reactivation_conditions` / `telemetry` are folded into free-form `priors` **and**
  mirrored into the human-readable `note` (truncated to `STRATEGY_NOTE_LIMIT = 400` :1138).
* `evidence` ← `refs.evidence`; `observations` ← `refs.hypotheses + refs.failures` (:1165-1166).
* Empty values (`None/[]/{}`) are dropped (:1168).

### 1.3 Forbidden fields (machine-enforced)

| Rule | Location | Forbids |
|---|---|---|
| `SV1` | :87-89, :339-343, :1182-1185 | `score`, `total`, `overall`, `composite`, `weighted`, `aggregate`, `rating` anywhere in a value assessment or a strategy update |
| `SV3` | :1186-1190 | `contract`, `primary_anchor`, `anchor`, `out_of_scope`, `research_goal` inside a strategy update |
| `SV5` | :1191-1194 | unknown `operator` (must be in `state_check.OPERATORS`, `state_check.py:191`) |
| `SV6` | :1195-1198 | `actor` outside `cognition.STRATEGY_REVISION_ACTORS` (`cognition.py:116`) |
| `SV8` | :1199-1205 | empty `refs`, or any dangling `refs[key][id]` |
| `CM1` | `cognition.py:1611-1633` | any payload key not in `STRATEGY_FIELDS` |
| `CM2` | `cognition.py:142-146`, `:1620-1623` | `epistemic_status`, `support_level`, `support`, `claim_status`, `claims_status`, `contract`, `anchor`, `research_goal`, `primary_anchor`, `out_of_scope`, `validity` |
| `CM3` | `cognition.py:1585-1610` | future `at_state_version`, empty `refs`, dangling refs, refs to `invalid`/`stale`/`pending` objects |

Also structurally frozen and not changeable by this subsystem: the eight-level
`next_action_policy.priority`, `EIG ÷ cost`, AALG/PEIG budgets, `evidence[]`, `failures[]`,
`claims[].status`, `validity`.

### 1.4 Critical gap in "what it can change"

`recommend_strategy` reads the anti-stagnation signal from **`record["after"]["menu"]`**
(:681-684), and `STAGNANT_MENU_RUN = 2` (:125). But `strategy_updates()` never puts `menu`
into `after`, and `revision_payload()` (:1161-1167) would strip it even if it did. Real
committed revisions therefore produce `recent_menus == []` and the "a menu repeated twice
forces divergence" branch (:703) **cannot fire in production** (it is exercised only by the
selftest hand-built fixtures at :1487-1502).

---

## 2. Where the Strategy Decision Adapter is implemented, and the exact call path

### 2.1 Implementation

File: `scripts/strategy_memory.py`, section header at `:830-849`.

| Function | Line | Purpose |
|---|---|---|
| `SCHEMA_STRATEGY_DECISION = "research-idea-pipeline/strategy-decision@1"` | :851 | in-memory decision schema id |
| `action_tier(action) -> Dict` | :862 | scheduler's own `EIG ÷ cost` tier label + rank, using `EIG_WEIGHT`/`COST_WEIGHT` (:854-855) |
| `_action_target_kind(action, state) -> Dict` | :874 | what an action targets, read from canonical objects only |
| `action_affinity(action, state, advice) -> Dict` | :891 | two declared affinity routes only (below) |
| `scheduler_verdict(state, scheduler) -> Dict` | :920 | fail-closed overall verdict + structural per-action legality |
| `_legal_actions(state, scheduler)` | :985 | `(legal_actions, blocked_actions, verdict)` |
| `_order_actions(state, actions, advice)` | :994 | tier first, then advice, then declaration order |
| **`strategy_decision(state, index, scheduler=None, revisions=None) -> Dict`** | **:1016** | **the adapter** |
| `record_strategy_decision(scheduler, decision, dispatch_result=None) -> Dict` | :1091 | deep-copy + append to `strategy_decisions[]`, keep last 20 |
| `latest_strategy_decision(scheduler) -> Optional[Dict]` | :1125 | last recorded decision |

Adapter mechanics:

* advice = `recommend_strategy(state, index, scheduler, revisions)` (:1031).
* legality = `scheduler_verdict` → `execution_gate.scheduler_check(state, scheduler)` (:930).
  **Authorization is decided by the overall `status == "PASS"`**, never by parsing an English
  error string (:934-937; preset-policy §5.3).
* Per-action recheck when the action id is a `state.experiments[]` id (:952-977):
  `status == "planned"`, `evidence_outcome._check_plan(...)["status"] == "PASS"`,
  `execution_blocked_by` empty, and `execution_gate.peig(state, id)["status"] != "HOLD"`.
  Non-experiment actions (`H<n>`/`P<n>`/`R<n>`/…) are legal without an execution check (:957-960).
* `without = _order_actions(state, legal, None)`, `with_memory = _order_actions(state, legal, advice)` (:1033-1034).
* `adopted` iff the first action id differs (:1039-1040).
* `reason_if_not` (:1041-1052) — see §6.4 for enum drift.
* Affinity routes (:900-911): (a) `hypotheses[target].operator == advice.operator` or
  `hypotheses[target].island == advice.island`; (b) `uncertainties[target].cheapest_discriminating_test == action.action`.
  Anything else is `unaligned` and keeps original order.

Returned decision keys (:1055-1088): `schema, state_version, advice{menu,operator,island,shift,basis,reason},
discovery_operator, hard_gates{scheduler_check,scheduler_status,global_errors,blocked_actions,switch_action},
candidates_before[], candidates_after[], chosen_without_memory, chosen, chosen_detail,
adopted, strategy_applied, decision_changed, reason_if_not, dispatch{action,type,target}, note`.

### 2.2 Exact call path — CLI

```
python3 scripts/strategy_memory.py decide --state S [--scheduler S.json] [--record] [--dispatch-result STR]
  → strategy_memory.main()                                   :1577
  → build_parser()  choices=[value,taste,operators,recommend,decide,apply,validate]   :1562-1564
  → _context(state_path, cognition_dir, scheduler_path)      :1223  (loads state + revisions + index + scheduler)
  → strategy_decision(state, index, scheduler, revisions)    :1613
      → recommend_strategy(...)                             :1031  → operator_priors :675, calibrated_preferences :676,
                                                                    prediction_compare.diagnosis_switch :677
      → _legal_actions → scheduler_verdict → execution_gate.scheduler_check   :930
      → _order_actions (twice)                              :1033-1034
  → if --record:  record_strategy_decision(scheduler or {}, decision, ...)   :1616-1617
  → writes  Path(--scheduler)  or  <state_dir>/scheduler.json               :1618-1623
  → _emit(decision, diagnostics)                            :1625
```

`apply` explicitly writes nothing: `payload["writes"] = []` (:1630) plus a note steering the
caller to `decide` (:1628-1629).

### 2.3 Exact call path — Preset / router

```
preset_router.py run --preset strategy-evolution --state S [--apply]
  → HANDLERS["strategy-evolution"] = _handle_strategy_evolution     :2842, def :2689
  → sm.strategy_decision(ctx["state"], ctx["index"], ctx["scheduler"], ctx["revisions"])   :2698
  → sm.strategy_updates(ctx["state"], ctx["index"], ctx["scheduler"])                      :2700
  → if apply:
       _append_strategy_revisions(ctx, updates)      :2709  → def :2341
           _strategy_revision_records(ctx, updates)  :2347  → def :2316
           sm.revision_payload(update)               :2336
           sm.validate_strategy_revisions(state, records)   :2348  (all-or-nothing)
           idempotency by _revision_identity(record)        :2309-2313, :2354-2358
           append → <cognition_dir>/model-revisions.jsonl   :2359-2363
       sm.record_strategy_decision(ctx["scheduler"], recorded)   :2720
           → write <route_dir>/scheduler.json                   :2721-2724
```

Other strategy consumers in the router:

* `_recommend(ctx, revisions=None)` :1669 → `sm.recommend_strategy` — used by
  `_handle_scientific_replanning` :2278/:2283 and `_handle_hypothesis_rebalance` :2766.
* `signal_snapshot` `evolution_due` :1342-1347 ← `_strategy_updates` :1359-1373 ←
  `sm.strategy_updates` (wrapped in a bare `except Exception` that degrades to `[]` :1370-1371).
* `_handle_research_loop` :2055 → `sm.latest_strategy_decision(ctx["scheduler"])` :2060 →
  `guidance` :2062-2072 → appended to `next_action` text :2095-2098.
* `HANDLERS["hypothesis-rebalance"]` :2842 also calls `strategy_decision` :2766.

### 2.4 Exact call path — Cognition projection

```
cognition.project_strategy(state, index, scheduler, revisions)     :1398-1414
  → sm.operator_priors :1408, sm.calibrated_preferences :1412, sm.recommend_strategy :1413
  → index["strategy"] = {...}                                    :1510-1513
  → digest["scheduler"] = digest_of(scheduler)                   :1486  (scheduler change invalidates index)
```

Brief rendering: `cognition.py:1959-1976` (source labelled `telemetry, never evidence` :1410).

---

## 3. Strategy effects that already have real execution evidence

"Real" = exercised end-to-end on the real CLI with real `scheduler.json` / `cognition/` files.

| Effect | Evidence | Verdict |
|---|---|---|
| Menu/operator ordering changes when `scheduler.operator_stats`/`hypotheses[].status` history changes | `strategy_memory.py:1526-1543`; `test_strategy_memory.py:328-351` | **real (derived)** |
| Adapter reorders and reports `strategy_applied=True`, `decision_changed=True`, `dispatch.action=<cheapest aligned>` | `test_preset_router.py:730-743` (`run_preset("strategy-evolution", ...)`) | **real (in-process), L2 synthetic** |
| `strategy_update` revision actually appended to `cognition/model-revisions.jsonl` | `preset_router.py:2341-2364`; emitted as `applied_revisions` :2740 | **real write** |
| `scheduler.json.strategy_decisions[]` actually written | `preset_router.py:2720-2724`; `test_preset_router.py:712-728` | **real write** |
| `record_strategy_decision` leaves every other scheduler key byte-identical | `test_preset_router.py:724-726`; `strategy_memory.py:1098-1122` | **real invariant** |
| Next round consumes the last decision | `test_preset_router.py:745-765`, stale variant :767-786 | **real, but only as a guidance string (see below)** |
| **An actually dispatched experiment being changed** | none | ❌ **not evidenced** |

The last row is the important one. The adapter's `dispatch` object is **never executed**:

* `_loop_step` still chooses `(ctx["scheduler"]["next_actions"] or [])[0]` — the scheduler's own
  order (`preset_router.py:2042-2049`), not `with_memory[0]`.
* `_handle_research_loop` only appends text:
  `next_action = f"{step['action']}；上一轮策略决策：{guidance['dispatch']['action']}…"` (:2095-2098).
* No module reads `strategy_decisions[-1].dispatch.action` for an execution or PEIG call.
* `dispatch_result` is a caller-supplied free string (`strategy_memory.py:1094`, CLI
  `:1570`, `:1617`); nothing validates that any action was dispatched.

Additionally, the appended `strategy_update` revisions have **no feedback effect**:
`operator_priors` re-derives from `scheduler.operator_stats` + `hypotheses[].status`
(`:484-508`), never from `after.priors`; and the only revision-consuming branch (`after.menu`)
is unreachable (see §1.4). So the durable strategy memory is, today, write-only.

---

## 4. Recommendation-only features with NO real consumer

| Feature | Where produced | Consumer status |
|---|---|---|
| `value_assessment()` / `value` CLI | :205, CLI :1598-1603 | Only `research_replay.py:335` and `release_check.py:678` (evaluation tooling). Not in `index["strategy"]` (`cognition.py:1409-1414`), not in `decide`. |
| `p4_context()` / `validate_p4_context()` | :610, :649 | **No production caller at all.** No CLI subcommand; used only by selftest/tests. Its `SV6` rule is enforced nowhere in a real flow. |
| `calibrated_preferences()` full body (`carried_experience`, preference statements, confidence, counterexamples) | :379-466 | Projected into `index["strategy"]["taste"]` and the brief; `recommend_strategy` uses only the **id list** `taste_preferences` (:743). No behavioural effect. |
| `recommendation.expected_decision`, `blocked_menus`, `alternatives`, `ordered_menus`, `exploration_floor`, `discouraged_but_admissible` | :733-745 | Validated/reported; no consumer acts on them. |
| `strategy_updates().applied_taste`, `.note`, `.recommendation` | :810-816 | Reported only (`apply` :1626-1631). |
| `revision_payload` `priors` + `note` | :1159-1167 | Written to disk, **never read back** by any module. |
| `after.menu` | read at :681-684 | **Never written** — dead in production (§1.4). |
| `SCHEMA_STRATEGY_DECISION` (`"…strategy-decision@1"`) | :851, :1056 | Present in the live decision JSON but **dropped by `record_strategy_decision`** (:1104-1117). No persisted schema tag. |
| `latest_strategy_decision()` `adopted` / `decision_changed` | :2067-2068 | Copied into `guidance` but used to gate nothing; only `dispatch.action` and `state_version` matter. |
| `record_strategy_decision` `dispatch_result` | :1116 | Free text, never validated or consumed beyond the test. |
| `EIG_WEIGHT`/`COST_WEIGHT` | :854-855 | Consumed by `action_tier` — genuinely used. |
| `SCHEDULER_GLOBAL_ERRORS` | :917 | Used by `scheduler_verdict` — genuinely used. |

---

## 5. On-disk layout of strategy memory / strategy revision records

### 5.1 Placement (no new state object, no new file)

```
<route>/
├── research-state.json                     canonical; NEVER written by this subsystem
├── scheduler.json                          telemetry; holds operator_stats, eig_calibration,
│                                           next_actions, next_action_policy, strategy_decisions[]
├── cognition/
│   ├── model-revisions.jsonl               append-only; the durable strategy memory
│   ├── index.json                          derived projection (index["strategy"])
│   ├── context-brief.md                    derived projection
│   └── insight-cards.jsonl
└── .execution/policy.json                  AALG budget; never touched on the decision path
```

Path constants: `cognition.COGNITION_DIRNAME="cognition"` :67, `REVISIONS_NAME="model-revisions.jsonl"`
:69, `INDEX_NAME="index.json"` :68, `BRIEF_NAME="context-brief.md"` :71, `STATE_NAME="research-state.json"`
:73, `SCHEDULER_NAME="scheduler.json"` :74; `cognition_dir_for(state_path, override=None)`
`cognition.py:397-400`.

There is **no** `strategy-memory.json`, no strategy DB, no `strategy_decisions` JSONL, and no
per-payload schema version for strategy content.

### 5.2 Revision record schema (one JSON object per line)

Built by `preset_router._strategy_revision_records` :2316-2338:

```jsonc
{"_schema": "research-idea-pipeline/cognition-revision@1",   // SCHEMA_REVISION, cognition.py:60
 "id": "REV<next_seq>",                                      // :2324
 "seq": <int >= 1, strictly increasing>,                     // CM1 cognition.py:1568-1575
 "kind": "strategy_update",                                  // REVISION_KINDS, cognition.py:100
 "subject": "<operator>",                                    // update["subject"]
 "actor": "CIE",                                             // STRATEGY_UPDATE_ACTOR, cognition.py:119
 "at_state_version": <int, <= state.state_version>,          // CM1/CM3
 "summary": "<text, non-empty>",
 "trigger": {"kind": "strategy_update", "ref": "<operator>"},// CM3 requires trigger.kind
 "refs": {"claims":[],"evidence":[],...},                    // must be non-empty (CM3/SV8)
 "after": {"note": "...", "priors": {...} | absent,
           "operator": "...", "action": "encourage"|"discourage",
           "evidence": [...], "observations": [...]}}
```

* Ids: `REV<N>` where `N = max(existing seq)+1` (`preset_router.py:2320-2325`).
* Status enums that participate: `kind ∈ REVISION_KINDS` (`cognition.py:88-101`),
  `actor ∈ REVISION_ACTORS` (`cognition.py:108-110`) and, for `strategy_update`,
  `actor ∈ STRATEGY_REVISION_ACTORS = ("R3","R4","R5","R6","R11","CIE")` (`cognition.py:116`,
  enforced by `SV6` `strategy_memory.py:1195-1198`).
* `after.action ∈ {"encourage","discourage"}` (`strategy_memory.py:795`, `:807`).
* Idempotency key = `digest_of({kind, subject, at_state_version, after})`
  (`preset_router.py:2309-2313`); duplicates are skipped, not rewritten.
* Validation is **all-or-nothing per group** before the append (`preset_router.py:2348-2351`).

### 5.3 `scheduler.json` telemetry keys

* `strategy_decisions[]` — see §6.
* `operator_stats.by_operator[<operator>] = {generations, viable, killed, dormant}` +
  `recurring_failure_patterns[]` — read at `strategy_memory.py:159-163`, `:484`, `:556`;
  documented `scheduler-policy.md:160-195`.
* `eig_calibration.records[] = {experiment, predicted_information_gain, observed_delta{...},
  actual_information_gain}` — read at `:151-156`, `:392-396`.
* Written by R9/R11/Meta-Controller flows elsewhere — **not** by this subsystem.

### 5.4 Cooldowns / budgets / limits

| Limit | Value | Where | Scope |
|---|---|---|---|
| `DECISION_LOG_LIMIT` | 20 | `strategy_memory.py:859`, applied `:1121` | recent-only ring for `strategy_decisions[]` |
| `MIN_INDEPENDENT_FAILURES` | 2 | `:122`, used `:519`, `:582-586` | minimum independent failures before `discouraged` |
| `STAGNANT_MENU_RUN` | 2 | `:125`, used `:684`, `:703` | consecutive same-menu updates before divergence (dead in production, §1.4) |
| `STRATEGY_NOTE_LIMIT` | 400 | `:1138`, `:1162` | `note` truncation |
| `exploration_rounds_delta` | must equal 0 | `:755-758` (`SV7`) | no unconditional extra exploration rounds |
| Preset cooldown | 1 round | `presets/strategy-evolution.md:28`, `preset_router.py:586` | auto-trigger `evolution_due`, `requires: strategy_revision_pending` |
| Preset attempt cap | 2 per fingerprint | `presets/strategy-evolution.md:28` | anti-recursion guard in `preset_router` |
| AALG/PEIG attempt caps | 3 / 2 (project policy) | `scheduler-policy.md:305-315` | explicitly **not** refreshed by a strategy decision |

Schema note: `schemas/scheduler.schema.json` declares only `_schema`, `state_version`,
`next_actions`, `eig_calibration` and has **no `additionalProperties: false`**. Neither
`strategy_decisions` nor `operator_stats` is declared there, so both pass validation as
unconstrained extras. `execution_gate.scheduler_check` (`execution_gate.py:359-384`) validates
the schema, state integrity, `state_version` freshness, EIG receipts and blocked experiments —
it does **not** inspect `strategy_decisions`.

---

## 6. `scheduler.strategy_decisions[]` — write, read, bounds, schema, consumer

### 6.1 Writers

Single writer: `strategy_memory.record_strategy_decision(scheduler, decision, dispatch_result=None)`
`:1091-1122`. It `copy.deepcopy`s the scheduler and touches only `strategy_decisions`
(`:1103`, `:1118-1121`). Callers:

1. CLI `decide --record` → `strategy_memory.main` `:1615-1624`;
   target path = `--scheduler` if given, else `<state_dir>/scheduler.json` (`:1618-1622`).
2. Preset `strategy-evolution --apply` → `preset_router._handle_strategy_evolution` `:2714-2724`;
   target path = `<route_dir>/scheduler.json` (`:2721`).
   Note: when `apply` is set **and** `ctx["scheduler"]` is truthy, a decision is recorded even
   when `decision_changed == False` (`:2714`); the preset then reports `NO_CHANGE` (`:2727`).

### 6.2 Persisted entry schema (`strategy_memory.py:1104-1117`)

```jsonc
{"state_version": <int>,                     // copied from decision.state_version
 "advice": {"menu","operator","island","shift","basis","reason"} | null,
 "discovery_operator": "reframe",
 "candidates_before": [{"action","type","target","tier","tier_rank","aligned","affinity_basis","declared_order"}],
 "chosen": "H2",
 "adopted": true,
 "strategy_applied": true,
 "decision_changed": true,
 "reason_if_not": null,
 "hard_gates": {"scheduler_check","scheduler_status","global_errors","blocked_actions","switch_action"},
 "dispatch": {"action","type","target"},
 "dispatch_result": "<free text>" | null}
```

Dropped relative to the live decision: `schema`, `candidates_after`, `chosen_without_memory`,
`chosen_detail`, `note`. The documented example `scheduler-policy.md:131-143` matches the
persisted subset.

### 6.3 Readers

* `strategy_memory.latest_strategy_decision(scheduler)` `:1125-1130` → `history[-1]`.
* `preset_router._handle_research_loop` `:2060-2072`: builds `guidance` and computes
  `stale = recorded["state_version"] != ctx["state"]["state_version"]` (`:2071`).
  Used at `:2095-2098` only to append a hint to `next_action`, and at `:2105` to set
  `decision.consumes_previous_decision`.
* Tests: `test_preset_router.py:712-728`, `:745-765`, `:767-786`.

### 6.4 Bounded / recent-only

Yes: `updated["strategy_decisions"] = history[-DECISION_LOG_LIMIT:]` with
`DECISION_LOG_LIMIT = 20` (`:859`, `:1121`). The code comment claims "the append-only cognition
log remains the durable record" (`:857-859`), but `record_strategy_decision` writes **only** to
`strategy_decisions[]`; no mirror of decisions (adoption, `dispatch`, `dispatch_result`) goes to
`model-revisions.jsonl` or any JSONL. History beyond 20 decisions — including every
`dispatch_result` — is destroyed.

### 6.5 `reason_if_not` enum drift

Code (`:1041-1052`) can emit **five** values:
`scheduler_check_failed`, `no_legal_action`, `single_candidate_in_tier`,
`no_aligned_candidate_in_tier`, `advice_agrees_with_existing_order`.
Documented enum has **four** — `scheduler_check_failed` is missing from
`scheduler-policy.md:153-154` and `preset-policy.md:213-215`.

### 6.6 Schema validation

None. `strategy_decisions` is absent from `schemas/scheduler.schema.json`; the persisted entry
carries no `_schema` tag even though `SCHEMA_STRATEGY_DECISION` exists in memory. A consumer
cannot distinguish a v1 entry from a future one.

---

## 7. Write-authority / revision-authority rules

| Surface | Who may write | Enforced by |
|---|---|---|
| `cognition/model-revisions.jsonl` `strategy_update` | `actor ∈ ("R3","R4","R5","R6","R11","CIE")` | `cognition.STRATEGY_REVISION_ACTORS` `cognition.py:116`; `SV6` `strategy_memory.py:1195-1198`; test `test_strategy_memory.py:411-415` rejects R7/R12/R13/R14 |
| Actor actually stamped by the preset channel | `cognition.STRATEGY_UPDATE_ACTOR = "CIE"` | `cognition.py:119`; `preset_router.py:2329` |
| R14 | **proposes only**, never writes cognition | `cognition.py:112-115`; `presets/strategy-evolution.md:9`, `:97-99` |
| Canonical `research-state.json` | nobody in this subsystem | `preset_router.SCOPE_CANONICAL["strategy_update"] = "不写 canonical（只写策略记忆）"` `:125`; `presets/strategy-evolution.md:98`; byte-compare `PR9` `preset-policy.md:19`, `:59-60` |
| `scheduler.json` `strategy_decisions[]` | `record_strategy_decision`, reached only from `decide --record` and `strategy-evolution --apply` | `strategy_memory.py:1091`; `preset_router.py:2720` |
| `scheduler.json` other keys | unchanged on the decision path | `:1098-1122`; `test_preset_router.py:724-726`; `scheduler-policy.md:150-152` |
| Preset privilege layer | `strategy_update`/`portfolio` → layer `strategy`; auto-trigger needs `scheduler.autonomous_loop` | `preset_router.py:105-106`, `:112`, `:699`, `:1203-1204`; `preset-policy.md:56`, §5.1 |
| AALG/PEIG budgets, priority rule, evidence gates, anchors | nobody | `SV3` `:1186`; `SV7` `:755-764`; `scheduler-policy.md:145-152`; `preset-policy.md:10-19` |

Authority gaps:

* The **CLI** `decide --record` path has no actor/authorization field and no
  `SCOPE_CANONICAL` check — any process that can run the CLI can append a `strategy_decision`.
* `record_strategy_decision` does not assert `decision["state_version"] == scheduler["state_version"]`,
  so a stale decision can be recorded against a fresher scheduler (the consumer then marks it
  `stale`, but the bad record stays in the ring).
* `_append_strategy_revisions` is the *only* place that stamps and validates an actor; a
  hand-authored revision is checked by `validate_strategy_revisions` but nothing prevents a
  caller from bypassing `revision_payload` (though `CM1` would then reject unknown keys).

---

## 8. Extension points for new strategy-candidate data (without touching canonical Research State)

Ordered from safest to most invasive. **None of these requires a new Research State object or a
`state_check.py` change.**

1. **`after.priors` free-form bag** — `revision_payload` already routes structured extras into
   `priors` (`strategy_memory.py:1159-1164`), and `cognition.PAYLOAD_KEYS["strategy_update"]`
   accepts `priors` as an opaque value (`cognition.py:172-174`, `:203`). A new candidate payload
   can live here with **zero** schema/validator change. Trade-off: nothing reads it back today
   (§4) — a new layer must add its own reader.
2. **New top-level telemetry key in `scheduler.json`** — the schema is open
   (`schemas/scheduler.schema.json`, no `additionalProperties: false`), and
   `operator_stats`/`strategy_decisions` are already undeclared precedents. Prefer extending
   `strategy_decisions[]` or adding a sibling key there over touching `next_actions`.
3. **New field inside the existing decision entry** — extend the dict at
   `strategy_memory.py:1104-1117` and the schema docs. Watch the 20-entry bound (`:1121`); if the
   new data must survive, mirror it to a new append-only JSONL instead of the ring.
4. **New menu entry** — append to `STRATEGY_MENUS` (`:93-110`). Hard constraint: `operator` must
   already be in `state_check.OPERATORS` (`state_check.py:191`) and `island` in
   `state_check.ISLANDS` (`state_check.py:186`), asserted at import (`:114-116`). Adding an
   entirely new *operator* means editing the frozen `state_check` vocabulary — that is a
   canonical-checker change and should be avoided.
5. **New persisted payload key** — add to `cognition.STRATEGY_FIELDS` (`cognition.py:172-174`)
   and it flows through `PAYLOAD_KEYS` (`:196-204`). Must not intersect
   `FORBIDDEN_REVISION_KEYS` (`:142-146`) or `BANNED_AGGREGATE_KEYS`
   (`strategy_memory.py:87-89`). This is the only change that touches the cognitive validator.
6. **New validation rule namespace** — `SV*` (`strategy_memory.py`), `CM*` (`cognition.py`),
   `PR*` (`preset_router.py`) are disjoint. A new policy layer should take a new prefix and add
   its rule ids to `cognition.WARNING_RULES` (`:229`) only if they are advisory (that table
   controls blocking vs. warning).
7. **New CLI subcommand** — add to the `choices` list `strategy_memory.py:1562-1564`; dispatch in
   `main` `:1598-1636`. `p4_context` is the obvious orphan to surface here (§4).
8. **New index projection section** — extend `cognition.project_strategy` (`:1398-1414`) and the
   brief renderer (`:1959-1976`). Bump nothing: the index digest already covers `scheduler`, so a
   new scheduler-resident policy key invalidates the projection correctly (`:1486`, `:1667-1669`).
9. **New preset handler** — `preset_router.HANDLERS` (`:2842`) plus the registry entry in
   `PRESETS` (`:530-561`). The `strategy` privilege layer already exists (`:105-106`).

Explicit anti-patterns the existing rules forbid: a ninth first-class Research State object
(`scheduler-policy.md:22-27`), a composite score (`SV1`), a new exploration operator
(`SV5`/`test_strategy_memory.py:183-187`), a permanent operator ban (`SV5`/`SV7`), a second
scheduler or a new scheduler priority formula (`:853-855`, `test_strategy_memory.py:443-448`),
and putting system statistics into `evidence[]`/narrative (`cognitive-memory-policy.md:44-52`).

---

## 9. Full CLI + public Python surface of `strategy_memory.py`

### 9.1 CLI

`build_parser()` `:1560-1574`; `main(argv=None)` `:1577`; exit codes `0/1/3/4`
(`EXIT_OK/EXIT_ERROR/EXIT_HARD/EXIT_ENV` aliased from `cognition` `:51-54`).

| Command / flag | Line | One-line purpose |
|---|---|---|
| `value --state S --target H1` | `:1598-1603` | per-dimension scientific value for one hypothesis/claim; no total |
| `taste --state S [--scheduler S.json] [--cognition DIR]` | `:1604-1605` | print human-specified vs evidence-calibrated taste memory |
| `operators --state S [--scheduler S.json]` | `:1606-1608` | print per-operator priors + exploration floor |
| `recommend --state S [--scheduler S.json]` | `:1609-1611` | pick one discovery menu by lexicographic rules |
| `decide --state S [--scheduler S.json] [--record] [--dispatch-result STR]` | `:1612-1625` | run the Strategy Decision Adapter; `--record` appends to `strategy_decisions[]` and writes `scheduler.json` |
| `apply --state S [--scheduler S.json]` | `:1626-1631` | print pending `strategy_update` suggestions; **writes nothing** (`writes: []`) |
| `validate --state S [--cognition DIR]` | `:1632-1636` | validate committed `strategy_update` revisions (`SV1/SV3/SV5/SV6/SV8`) |
| `--selftest` | `:1579-1580` | run the built-in fixture checks |
| `--list-menus` | `:1581-1584` | print `menu\toperator\tshift` for all 8 menus |

Note: the module docstring usage block `:23-31` omits `decide` and `--list-menus` — stale
documentation.

### 9.2 Public Python functions

| Signature | Line | One-line purpose |
|---|---|---|
| `human_preferences(state) -> Dict` | :132 | the read-only, user-owned part of taste memory from `state.contract` |
| `target_refs(state, index, target) -> Dict` | :179 | resolve everything the value model may look at for one target |
| `value_assessment(state, index, target, scheduler=None) -> Dict` | :205 | per-dimension value/decision judgment; raises `CognitionError` if target is neither hypothesis nor claim |
| `validate_value(assessment, path="value") -> List[Diagnostic]` | :334 | reject an aggregate (`SV1`) and a dimension without a canonical source (`SV2`) |
| `calibrated_preferences(state, index, scheduler=None) -> Dict` | :379 | derive evidence-calibrated taste preferences + carried experience |
| `operator_priors(state, index, scheduler=None) -> Dict` | :473 | per-operator status scoped to problem structure, with reactivation conditions |
| `validate_priors(priors, path="operators") -> List[Diagnostic]` | :562 | `SV5`/`SV7`: no permanent ban, scoped downgrade, ≥2 failures, non-empty exploration floor |
| `p4_context(intermediates_dir: Path) -> Dict` | :610 | build the de-domained typed-skeleton context P4 is allowed to see |
| `validate_p4_context(payload, path="p4_context") -> List[Diagnostic]` | :649 | `SV6`: skeletons may carry only the five P3 slots |
| `recommend_strategy(state, index, scheduler=None, revisions=None) -> Dict` | :666 | choose one discovery menu by explicit lexicographic rules |
| `validate_recommendation(recommendation, path="recommendation") -> List[Diagnostic]` | :749 | `SV7`: known menu, `exploration_rounds_delta == 0`, exploration floor present |
| `strategy_updates(state, index, scheduler=None) -> Dict` | :772 | emit suggested `strategy_update` records (encourage/discourage) |
| `action_tier(action) -> Dict` | :862 | an action's tier under the scheduler's own `EIG ÷ cost` rule |
| `action_affinity(action, state, advice) -> Dict` | :891 | whether the advice prefers this action, from declared fields only |
| `scheduler_verdict(state, scheduler) -> Dict` | :920 | fail-closed overall scheduler verdict + per-action legality |
| `strategy_decision(state, index, scheduler=None, revisions=None) -> Dict` | :1016 | **the adapter**: with-memory vs without-memory choice inside one tier |
| `record_strategy_decision(scheduler, decision, dispatch_result=None) -> Dict` | :1091 | append the decision to `strategy_decisions[]`, keep the last 20 |
| `latest_strategy_decision(scheduler) -> Optional[Dict]` | :1125 | the decision the next round reads |
| `revision_payload(update) -> Dict` | :1141 | project a rich update into the CM1-allowed `strategy_update` payload |
| `validate_strategy_revisions(state, revisions) -> List[Diagnostic]` | :1171 | `SV1/SV3/SV5/SV6/SV8` over committed strategy revisions |
| `build_parser() -> argparse.ArgumentParser` | :1560 | construct the CLI parser |
| `main(argv: Optional[Sequence[str]] = None) -> int` | :1577 | CLI entry point |
| `selftest() -> int` | :1380 | in-process fixture checks |

Private helpers (not API): `_records` :151, `_operator_stats` :159, `_hypothesis_table` :166,
`_indicator` :175, `_refs_for` :819, `_action_target_kind` :874, `_legal_actions` :985,
`_order_actions` :994, `_load_scheduler` :1213, `_context` :1223, `_emit` :1231,
`_fixture` :1242, `_Parser` :1553.

Module constants worth reusing: `VALUE_DIMENSIONS` :60, `POTENTIAL_DIMENSIONS` :68,
`ASSESSMENTS` :76, `CONSIDERATIONS` :78, `OPERATOR_STATUSES` :84, `BANNED_AGGREGATE_KEYS` :87,
`STRATEGY_MENUS` :93, `MENU_BY_NAME` :118, `MIN_INDEPENDENT_FAILURES` :122,
`STAGNANT_MENU_RUN` :125, `P3_SKELETON_SLOTS` :599, `CANDIDATE_LEAK_KEYS` :604,
`SCHEMA_STRATEGY_DECISION` :851, `EIG_WEIGHT` :854, `COST_WEIGHT` :855,
`DECISION_LOG_LIMIT` :859, `SCHEDULER_GLOBAL_ERRORS` :917, `STRATEGY_NOTE_LIMIT` :1138.

---

## 10. Invariants / tests a new policy-candidate layer must keep passing

### 10.1 `scripts/test_strategy_memory.py` (574 lines, 9 test classes)

**Value model — `TestValueModel` :55-118**
* the two judgment groups are exactly `VALUE_DIMENSIONS` / `POTENTIAL_DIMENSIONS` (:57-60);
* `validate_value(assessment) == []` and no `BANNED_AGGREGATE_KEYS` in output (:62-69);
* `score/overall/composite` injected ⇒ `SV1` (:71-76);
* every dimension has a non-empty `basis` and a valid `assessment` (:78-83);
* empty `basis` ⇒ `SV2`; deleted dimension ⇒ `SV2` (:85-95);
* contract relation cites `contract:primary_anchor` (:97-101);
* strongest objection present, including "no objection recorded" for a hypothesis (:103-108);
* unknown target ⇒ `CognitionError` (:110-112);
* `experiment_cost` comes from the scheduler when present (:114-118).

**Taste memory — `TestTasteMemory` :125-169**
* `authority == "user"`, `mutable_by_agent is False`, anchor copied from contract (:127-133);
* `anchor_untouched is True` (:135-138);
* every preference has `basis` + `revisit_conditions` and `kind == "evidence_calibrated"` (:140-146);
* `TP-DIAG` and `TP-INTERV` appear; `TP-DORMANT` states it is not a permanent verdict (:148-158);
* changing telemetry changes `carried_experience` (:160-163);
* serialized taste contains no banned aggregate key (:165-169).

**Adaptive discovery — `TestAdaptiveDiscovery` :176-270**
* every menu reuses a frozen operator and island (:178-181);
* no new operator and no `class ExplorationAgent` in the source (:183-187);
* `validate_priors == []`; status ∈ `OPERATOR_STATUSES`; no `forbidden/banned/disabled`;
  discouraged/dormant carry reactivation conditions (:189-196);
* one failure ⇒ `SV5`; missing scope ⇒ `SV5`; empty exploration floor ⇒ `SV7`
  (:198-216, and `strategy_memory.py:1437-1446`);
* exploration floor never empty for `None`/full/quiet scheduler (:218-221);
* discouraged operators stay admissible menus; `ordered_menus` covers all 8 (:223-228);
* deprioritising one operator does not remove the others (:230-234);
* recommendation validates and contains no aggregate key (:236-242);
* `exploration_rounds_delta == 0`; setting it to 2 ⇒ `SV7` (:244-250);
* `independent_exploration_allowed` true; false ⇒ `SV7` (:252-258);
* a stop rule (`failures[]`) blocks the matching menu (:260-270).

**P4 isolation — `TestCrossDomainIsolation` :277-319**
* clean 5-slot skeleton crosses; each `CANDIDATE_LEAK_KEYS` entry is refused;
  missing slot refused; missing directory reported (`SV6`); polluted context ⇒ `SV6`.

**Learning loop — `TestLearningLoop` :326-380**
* telemetry history changes `ordered_menus`; the no-output operator is deprioritised;
  the full trace telemetry → prior → menu ordering holds (:341-351);
* a menu repeated `STAGNANT_MENU_RUN` times forces divergence (:353-366);
* loop updates are all sourced and `action ∈ {encourage,discourage}` (:368-374);
* `strategy_updates` + `recommend_strategy` leave `cg.canonical_json(state)` unchanged (:376-380).

**Revision validation — `TestStrategyRevisionValidation` :387-425**
* valid update passes; every anchor key ⇒ `SV3`; every banned aggregate key ⇒ `SV1`;
  invented operator ⇒ `SV5`; `actor` R7/R12/R13/R14 ⇒ `SV6`; empty refs ⇒ `SV8`;
  dangling refs ⇒ `SV8`.

**Scheduler boundary — `TestSchedulerBoundary` :432-458**
* the four read functions leave `canonical_json(scheduler)` unchanged (:434-441);
* `recommendation` contains no `next_action_policy`, and the module source contains no
  `"priority":` literal (:443-448);
* `index["strategy"]["source"]` contains `telemetry` and `never evidence` (:450-453);
* `operator_stats` is the history source (`status == "dormant"`, `telemetry_dormant`) (:455-458).

**Index integration — `TestIndexIntegration` :465-502**
* `index["strategy"]` has `recommendation` and `operators`;
  `counts.discouraged_operators == len(index["strategy"]["operators"]["discouraged"])` (:467-473);
* the strategy layer is omitted when there is no scheduler telemetry (:475-477);
* changing `operator_stats` makes `cg.op_check` exit `EXIT_HARD` (index invalidation) (:479-495);
* the context brief contains `## Scientific value and adaptive discovery`, `Telemetry is labelled`,
  `exploration floor` (:497-502).

**CLI — `TestCLI` :509-570**
* `--selftest` exits 0 and prints `selftest: PASS`;
* `--list-menus` prints exactly `len(STRATEGY_MENUS)` lines;
* `value/operators/recommend/apply/taste` exit 0 and print truthy JSON;
* missing state ⇒ `EXIT_ENV`; broken `scheduler.json` ⇒ `EXIT_ENV`; no command ⇒ `EXIT_ERROR`.

### 10.2 `scripts/test_preset_router.py` (strategy section)

* recording touches only the `strategy_decisions` key, all other keys byte-identical (:712-728);
* `run_preset("strategy-evolution")` reports `strategy_applied`, `changed_decision`, and
  `dispatch.action == CHEAPEST_XID` (:730-743);
* the next `research-loop` round consumes the recorded decision
  (`guidance.stale == False`, `consumes_previous_decision == True`) (:745-765);
* a decision whose `state_version` is older is **not** consumed (:767-786);
* a single legal candidate in the best tier ⇒ `strategy_applied False` and
  `reason_if_not == "single_candidate_in_tier"` (:690-698);
* two unaligned candidates ⇒ `no_aligned_candidate_in_tier` (:700-710).

### 10.3 Cross-cutting invariants from policy (not only tests)

* `CM0` — a cognition build/check must not modify `research-state.json` byte-wise
  (`cognitive-memory-policy.md:58`, `cognition.py:2275`).
* `CM1`–`CM10` revision-log shape, provenance and warning/blocking severity
  (`cognitive-memory-policy.md:54-79`; `cognition.WARNING_RULES` :229).
* `SV1`–`SV8` above; `PR1`–`PR9` router/preset invariants (`presets/strategy-evolution.md:55`).
* The preset document's §6 command table must match the router's returned steps
  (`presets/strategy-evolution.md:78`, asserted by `test_preset_router`).
* `state_check.py` is unchanged by this layer — grep for `strategy`/`scheduler` in
  `scripts/state_check.py` returns **zero** matches; `OPERATORS` :191 and `ISLANDS` :186 are
  consumed read-only.
* Exit-code convention `0/1/3/4`; a hard rule violation must exit 3, an environment failure 4.
* A new layer must not add a composite score, a new operator, a permanent ban, a second
  scheduler, or a ninth canonical object.

---

## 11. Ranked blockers and gaps

| # | Blocker / gap | Evidence | Impact on a new policy-candidate layer |
|---|---|---|---|
| B1 | The adapter's `dispatch` is never executed; `_loop_step` still uses `next_actions[0]` | `preset_router.py:2042-2049` vs `:2060-2098` | "L2 actual dispatch change" cannot be claimed in production; only a hint string changes |
| B2 | `after.menu` is never persisted, so menu-stagnation divergence is dead | read `strategy_memory.py:681-684`; `revision_payload` :1161-1167; `strategy_updates` :795-808 | Any candidate that depends on prior-menu memory must add its own persisted field (e.g. under `priors`) |
| B3 | `strategy_decisions[]` persisted entry drops `schema`, `candidates_after`, `chosen_without_memory` | `:1104-1117` vs `:1055-1088` | with/without-memory evidence is not durably auditable; no version tag |
| B4 | `strategy_decisions[]` is a 20-entry ring with **no** append-only mirror despite the code comment | `:857-859`, `:1121` | long-horizon policy evaluation needs a new JSONL |
| B5 | `reason_if_not` emits `scheduler_check_failed`, absent from both documented enums | `:1041-1042` vs `scheduler-policy.md:153-154`, `preset-policy.md:213-215` | a strict new consumer would reject real records |
| B6 | `strategy_decisions` / `operator_stats` are not in `schemas/scheduler.schema.json` (open object) | `schemas/scheduler.schema.json`; `execution_gate.py:359-362` | no machine-checked contract for the new data |
| B7 | `p4_context` / `validate_p4_context` have no production caller, and `value` is only used by replay/release tooling | `:610`, `:649`; `research_replay.py:335`; `release_check.py:678` | `SV6` and the value model are effectively policy-without-enforcement |
| B8 | CLI `decide --record` writes `scheduler.json` with no actor/authorization check and no `state_version` match assertion | `:1615-1624`; `:1091-1122` | write-authority is enforced only on the preset path |
| B9 | Affinity has only two declared routes; claim/assumption-targeted actions can never be "aligned" | `:900-911` | adoption rate is structurally low; many decisions end `no_aligned_candidate_in_tier` |
| B10 | Appended `strategy_update` revisions are never read back | `operator_priors` :484-508; no consumer of `after.priors` | the durable strategy memory is write-only today |
| B11 | Dead branch in `calibrated_preferences` | `:404-405` (`if False else []`) | hygiene only |
| B12 | Module docstring usage omits `decide` | `:23-31` vs parser `:1562-1564` | doc/code drift |
