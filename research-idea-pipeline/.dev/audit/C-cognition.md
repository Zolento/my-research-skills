# Audit C — Cognitive Intelligence Engine / Memory subsystem

Scope: `research-idea-pipeline/` (component root
`/home/lenovo/code/myproj/skills-dev/research-idea-pipeline/skill-rsi-dev/research-idea-pipeline`).
Read-only audit. Primary source `scripts/cognition.py` (2547 lines), plus
`references/cognitive-memory-policy.md`, `presets/memory-consolidation.md`,
`presets/research-loop.md`, `scripts/test_cognition.py`, and grep-level tracing of
`research_replay.py`, `preset_router.py`, `strategy_memory.py`, `prediction_compare.py`,
`legacy_handoff.py`, `release_check.py`, `docs/cognitive-insight-engine.md`.

All `file:line` references are relative to `research-idea-pipeline/`.

---

## 1. Artifact types / schemas and on-disk paths

### 1.1 Frozen constants (single source of truth)

| Constant | Value | Line |
|---|---|---|
| `SCHEMA_INDEX` | `research-idea-pipeline/cognitive-index@1` | `scripts/cognition.py:59` |
| `SCHEMA_REVISION` | `research-idea-pipeline/cognition-revision@1` | `scripts/cognition.py:60` |
| `COGNITION_DIRNAME` | `cognition` | `scripts/cognition.py:67` |
| `INDEX_NAME` | `index.json` | `scripts/cognition.py:68` |
| `REVISIONS_NAME` | `model-revisions.jsonl` | `scripts/cognition.py:69` |
| `INSIGHT_CARDS_NAME` | `insight-cards.jsonl` | `scripts/cognition.py:70` |
| `BRIEF_NAME` | `context-brief.md` | `scripts/cognition.py:71` |
| `STATE_NAME` | `research-state.json` | `scripts/cognition.py:73` |
| `SCHEDULER_NAME` | `scheduler.json` | `scripts/cognition.py:74` |

Two other schemas in the same control-plane directory, owned elsewhere:

* `research-idea-pipeline/recovery-log@1`, `cognition/recovery-log.jsonl`
  (`scripts/preset_router.py:60-62`, path helper `:1387-1388`).
* `research-idea-pipeline/strategy-decision@1`, stored **not** in `cognition/` but in
  `scheduler.json → strategy_decisions[]` (`scripts/strategy_memory.py:851`).
* Insight-card schema is owned by `prediction_compare` (`pc.SCHEMA_INSIGHT`), loaded through
  `load_insight_cards` (`scripts/cognition.py:315-322`).
* Legacy-handoff adds `cognition/handoff.json` (HANDOFF_NAME) and `cognition/handoff-report.md`
  (REPORT_NAME) as owned files (`scripts/legacy_handoff.py:66-67`).

### 1.2 Three-layer model — canonical vs derived projection

Documented identically in the module docstring (`scripts/cognition.py:11-19`), the policy
(`references/cognitive-memory-policy.md:13-20`), `SKILL.md:722-725`, and
`docs/cognitive-insight-engine.md:49-53`:

```
Canonical   .research-idea-pipeline/routes/<R>/research-state.json
            + experiments[].preregistration + raw evidence      ← sole authority
Event       .research-idea-pipeline/routes/<R>/cognition/model-revisions.jsonl
            structural assertions + canonical pointers          ← append-only, no epistemics
Derived     .research-idea-pipeline/routes/<R>/cognition/index.json
            .research-idea-pipeline/routes/<R>/cognition/context-brief.md
                                                                 ← rebuildable, never authority
```

* **Canonical** = `research-state.json` + frozen preregistration + raw evidence. The eight
  first-class arrays are `claims/evidence/assumptions/hypotheses/experiments/literature/
  failures/uncertainties` (`REF_KEYS`, `scripts/cognition.py:176-179`; id prefixes `:207-210`).
* **Event** = append-only `model-revisions.jsonl`. It carries structure + pointers, never
  epistemics.
* **Derived** = `index.json` + `context-brief.md`; "rebuildable from the two layers above …
  never authoritative" (`:17-19`). `build_index` is documented pure/no-I/O
  (`scripts/cognition.py:1425`).

Origin markers that make projection provenance explicit:

* `LEGACY_ORIGIN = "legacy_derivation"`, `REVISION_ORIGIN = "revision_log"`
  (`scripts/cognition.py:186-187`).
* Legacy id prefixes `LM-`, `LM-ALT-`, `LAN-`, `LCP-` (`scripts/cognition.py:189-192`).
* Every revision-derived entry may carry a `provenance`
  `{origin, retrospective, derived_from, missing}` block (`_projection`,
  `scripts/cognition.py:1020-1023`), and `index["provenance_mode"]` is one of
  `"legacy_derivation" | "mixed" | "revision_log"` (`:1463-1471`).
* `_origin_tag` prints `[RETROSPECTIVE]` in the brief (`:2072-2076`).

### 1.3 Index schema (`index.json`)

Top-level assembled at `scripts/cognition.py:1476-1513`:

```jsonc
{
  "_schema": "research-idea-pipeline/cognitive-index@1",
  "route": "<R>",
  "state_version": <int>,
  "provenance_mode": "legacy_derivation|mixed|revision_log",
  "digest": {"state","revisions","insight_cards","scheduler"},   // :1481-1487
  "mechanisms": [...], "anomalies": [...], "competitions": [...],
  "insights": [...], "boundaries": [...],
  "counts": {"mechanisms","legacy_mechanisms","anomalies","competitions",
             "boundaries","insights","evidence_supported_insights",
             "stale_mechanisms","refuted_mechanisms","discouraged_operators"},
  "diagnostics": [{"rule","path","detail"}],
  "strategy": {...}                                              // :1510-1513, optional
}
```

Entry schemas:

* **Mechanism** (`scripts/cognition.py:906-923`): `id, statement, scope, structure,
  support_level, support_reasons, status, stale, stale_reasons, missing_refs,
  canonical_refs, revision_ids, fingerprint, lost_competitions, won_competitions,
  declared_intents` (+ `provenance` for legacy, `:1097,1128-1130`). `structure` sub-keys:
  `core_variables, dependencies, necessary_conditions, boundaries, invariants,
  counterexamples, pending_predictions, competes_with` (`_empty_structure`, `:621-626`).
* **Anomaly** (`scripts/cognition.py:929-943`): `id, observation, frozen_prediction,
  reproduced, importance, exploratory, open_question, related_mechanisms, canonical_refs,
  revision_ids, stale, stale_reasons, missing_refs`.
* **Competition** (`scripts/cognition.py:954-979`): `id, mechanisms, shared_explanation,
  conflicting_predictions, predictions, discriminating_intervention, decision_impact,
  discrimination_rule, status, conclusion, decidable, canonical_refs, revision_ids, stale,
  stale_reasons, missing_refs, has_distinguishing_power,
  discrimination_rule_present` (+ `winner`).

Frozen vocabularies: `MEMORY_CLASSES = (mechanistic, anomaly, competition,
scientific_value)` (`scripts/cognition.py:82-84`); `SUPPORT_LEVELS = (speculative,
hypothesis, literature_supported, experiment_supported, refuted)` (`:123-126`);
`MECHANISM_STATUSES = (active, weakened, refuted, dormant, merged)` (`:131-133`);
`COMPETITION_STATUSES = (open, resolved, undecidable_recorded)` (`:135-137`);
`CONTEXT_TIERS = (hot, warm, cold)` (`:212`).

---

## 2. Scientific experience vs SYSTEM / decision experience

### 2.1 The four classes are scientific

`MEMORY_CLASSES` (`scripts/cognition.py:82-84`) maps 1:1 to policy §1
(`references/cognitive-memory-policy.md:33-40`):

| Class | Derived from | Never duplicates |
|---|---|---|
| `mechanistic` | `hypotheses[], assumptions[], claims[], evidence[], literature[]` | `claims[]` |
| `anomaly` | `experiments[].unexpected`, `preregistration.outcomes`, `evidence[].diagnostic_observation` | `uncertainties[]` |
| `competition` | `claims[].nearest_alternative`, `claims[].contract.minimal_discriminating_experiment`, `assurance[]` | `assurance[]` |
| `scientific_value` | `contract`, `uncertainties[].importance`, `repairs[]`, `scheduler.json` | scheduler `operator_stats` |

### 2.2 Decision experience is NOT a first-class record — it is mixed

There is **no** `decision` / `strategy` memory class and **no**
`experience_kind: decision` discriminator. Decision/system experience is spread across three
carriers:

1. **`strategy_update` revision kind** — one of the frozen `REVISION_KINDS`
   (`scripts/cognition.py:88-101`). It shares the *same* append-only
   `model-revisions.jsonl` file as scientific revisions, but cognition deliberately does
   **not** fold or project it: `_Builder.fold` handles only `mechanism_*`, `anomaly_record`,
   `competition_*`, and comments "prediction_* and strategy_update are folded by their own
   phases; they are accepted here so the log stays a single append-only file"
   (`scripts/cognition.py:715-722`). Validation of `strategy_update` lives in
   `strategy_memory.validate_strategy_revisions` under rules `SV1/SV3/SV5/SV6/SV8`
   (`scripts/strategy_memory.py:1171-1206`), not in `cognition.validate_revisions`.
2. **`scheduler.json → strategy_decisions[]`** telemetry — the Strategy Decision Adapter's
   record of advice/candidates/chosen/adopted/reason, capped at 20 entries
   (`scripts/strategy_memory.py:851-859`, `record_strategy_decision` `:1091-1122`,
   `latest_strategy_decision` `:1125-1130`).
3. **`cognition/recovery-log.jsonl`** — preset recovery bookkeeping
   (`scripts/preset_router.py:60-62,1387-1388,3190`).

The explicit boundary rule is policy §1 rule 3: "Scheduler meta-memory stays in
`scheduler.json`. Cognitive memory reads `operator_stats` and `eig_calibration`; it does not
write them and never cites them as evidence" (`references/cognitive-memory-policy.md:48-50`).
`project_strategy` labels its output `"source": "derived from state + scheduler.json
(telemetry, never evidence)"` (`scripts/cognition.py:1410`) and the brief repeats
"Telemetry is labelled … never evidence" (`:1979`).

**Conclusion:** scientific experience (mechanisms/anomalies/competitions/insights/
boundaries) and system/decision experience are *not* separated by schema. They are separated
only by (a) the revision `kind`, (b) which module validates/folds them, and (c) the physical
file (cognition log vs scheduler telemetry). A decision-experience record exists only as the
`strategy_update` event and `strategy_decisions[]` telemetry; neither is projected into
`index.json`.

---

## 3. Revision logs (names, schema, ids, append-only guarantees)

### 3.1 `cognition/model-revisions.jsonl` (primary)

* One JSON object per line. Record shape enforced by `validate_revisions`
  (`scripts/cognition.py:1547-1634`):
  `_schema` (must equal `cognition-revision@1`, `:1558-1560`), `id` (unique non-empty string,
  `:1561-1567`), `seq` (positive int, **strictly increasing**, `:1568-1575`), `kind` (in
  `REVISION_KINDS`), `subject` (non-empty string, `:711-714`), `actor` (in
  `REVISION_ACTORS`), `at_state_version` (non-negative int ≤ current `state_version`,
  `:1585-1592`), `summary` (non-empty, `:1579-1580`), `trigger` (`{kind, ref?}`, `:1593-1596`),
  `refs` (non-empty, all eight `REF_KEYS`, `:1597-1610`), optional `before`/`after` payloads
  whose keys must be in `PAYLOAD_KEYS[kind]` (`:1611-1633`, table `:196-204`).
* `REVISION_ACTORS = (R3,R4,R5,R6,R7,R8,R9,R9.O,R10,R11,R14,CIE)`
  (`scripts/cognition.py:108-110`); R12/R13 are read-only and rejected
  (`test_cognition.py:469-473`).
* `STRATEGY_REVISION_ACTORS = (R3,R4,R5,R6,R11,CIE)` and
  `STRATEGY_UPDATE_ACTOR = "CIE"` (`scripts/cognition.py:116-119`) — one source consulted by
  both writer and validator.
* Fields allowed per kind: `MECHANISM_FIELDS` (`:149-153`), `ANOMALY_FIELDS` (`:159-162`),
  `COMPETITION_FIELDS` (`:163-167`), `PREDICTION_FIELDS` (`:168-171`), `STRATEGY_FIELDS`
  (`:172-174`). `declared_support` is accepted only to be recorded as a `CM7` conflict
  (`:196-204`, `:1624-1628`).
* Forbidden keys: `FORBIDDEN_REVISION_KEYS = (epistemic_status, support_level, support,
  claim_status, claims_status, contract, anchor, research_goal, primary_anchor,
  out_of_scope, validity)` (`:142-146`) — `CM2`.
* **Append-only guarantees:** malformed/torn lines are reported as `CM1` and skipped, not
  raised (`load_revisions`, `scripts/cognition.py:361-394`); `seq` monotonic and `id` unique;
  the module that owns cognition has **no** append function — `cognition.py` only reads the
  log (`_load_inputs` `:2164-2171`) and writes only `index.json`/`context-brief.md`
  (`op_build` `:2183-2187`). Revision ids are free-form (`REV1`…); *subject* ids carry the
  mechanism/competition/anomaly namespaces (`M…`, `CP…`, `AN…`, `X…`, plus legacy `LM-`,
  `LM-ALT-`, `LAN-`, `LCP-`).
* `python3 scripts/cognition.py --list-kinds` prints the frozen `REVISION_KINDS` in order
  (`:2513-2516`; asserted `test_cognition.py:1129-1133`).

### 3.2 `cognition/recovery-log.jsonl` (secondary, preset-owned)

Schema `research-idea-pipeline/recovery-log@1` (`scripts/preset_router.py:60`);
`ledger_path(cognition_dir) = cognition_dir / "recovery-log.jsonl"` (`:1387-1388`); entries
appended at `:3200`; validated under `PR7` (`:1403`). Referenced by presets
`memory-consolidation.md:96` and `research-loop.md:111`.

### 3.3 `scheduler.json → strategy_decisions[]` (telemetry, not a revision log)

Append via `record_strategy_decision`; `DECISION_LOG_LIMIT = 20` with
`history[-DECISION_LOG_LIMIT:]` (`scripts/strategy_memory.py:859,1118-1121`). Explicitly
"Telemetry, not history of record: the append-only cognition log remains the durable record"
(`scripts/strategy_memory.py:857-858`).

---

## 4. How memory is consumed later

### 4.1 Inside `cognition.py`

`recall` (`scripts/cognition.py:1751-1812`), `focus_ids` (`:1716-1743`),
`failure_constraints` (`:1826-1872`), `open_obligations` (`:1875-1888`),
`render_brief` (`:1891-2052`), `next_action_hint` (`:2055-2069`). `recall` builds
hot/warm/cold from `index["mechanisms"/"anomalies"/"competitions"]`, adds
`failure_constraints`, `open_obligations`, `boundaries` (`:1803-1812`).

### 4.2 Cross-module readers (import `cognition as cg`)

| Module | What it reads / does |
|---|---|
| `scripts/prediction_compare.py:47` | `CanonicalView`, `digest_of`, `normalize_refs`, `tier_at_least`, `_dedupe`, `is_warning`, `REVISIONS_NAME`; supplies `classify_insight`, `insight_card_errors`, `load_audits` back to cognition via local import (`scripts/cognition.py:321-322,2156-2161`) |
| `scripts/strategy_memory.py:45` | reads revision log + insight cards, calls `cg.full_index` (`:1227`); uses `STRATEGY_REVISION_ACTORS`, `normalize_refs`, `iter_refs`, `REF_KEYS`, `cognition_dir_for` |
| `scripts/preset_router.py:50` | `project_context` loads revisions + `index.json` + recovery ledger (`:1623-1641`); loop/recovery handlers call `cg.op_build` (`:2246,2463,2639,3378`); presets declare `requires=("research-state.json","contract","scheduler","cognition/index.json")` (`:276`) |
| `scripts/legacy_handoff.py:48` | `_cognition_findings` raises `LH12` on index drift (`:309-339`); rebuild writes index/brief/handoff (`:657-716`); rollback (`:740-774`); action comes from `cg.next_action_hint` (`:534-535`) |
| `scripts/research_replay.py:48` | builds memory in the smoke test (`:1183-1229`), `project_insights` (`:324`), `digest_of` |
| `scripts/release_check.py:598,674` | release gate: build → check → rebuild must be byte-identical; LH12 warning behaviour |

### 4.3 Who acts on it (stage agents)

The interface map (`docs/cognitive-insight-engine.md:69-86`) and policy §8 assign reads/writes
per R stage. Operationally:

* `presets/research-loop.md:78` step 1 `Recall` = `cognition.py recall`; step 8 `Consolidate`
  = `cognition.py build`.
* `presets/memory-consolidation.md:71-73` = `build` → `check` → `state_check`.
* `legacy_handoff` reads `cognition/context-brief.md` before the next stage
  (`scripts/legacy_handoff.py:633-635`).
* `next_action_hint` steers the handoff action (`scripts/legacy_handoff.py:534-535`).

---

## 5. Does cognition measure "value of a decision" / "policy effect"?

**No — `cognition.py` contains no measurement.** It only carries `decision_impact` as an
unvalidated passthrough string on competition payloads and entries
(`scripts/cognition.py:165,828,853-854,961,1144`) and computes
`has_distinguishing_power` structurally (`:974-978`); nothing derives or scores
`decision_impact`.

The real measurements live outside `cognition.py`:

* **Per-dimension decision value** — `strategy_memory.value_assessment`
  (`scripts/strategy_memory.py:205-331`) computes `decision_value` over five dimensions:
  `changes_method_choice`, `changes_experiment_design`, `changes_resource_allocation`,
  `changes_route`, `changes_important_conclusion` (`:226-253`), each with `basis` and
  assessment. A composite is explicitly forbidden (`:328-330`), enforced by
  `validate_value` (`SV1/SV2`, `:334-359`).
* **Policy effect / counterfactual** — `strategy_memory.strategy_decision`
  (`scripts/strategy_memory.py:1016-1088`) compares `with_memory` vs `without_memory`
  ordering over the *same* legal action set (`:1033-1034`), yielding `adopted`,
  `strategy_applied`, `decision_changed`, and a `reason_if_not`
  (`single_candidate_in_tier` / `no_aligned_candidate_in_tier` /
  `advice_agrees_with_existing_order`, `:1039-1052`). It is persisted to
  `scheduler.strategy_decisions[]` by `record_strategy_decision` (`:1091-1122`).
* **Replay-level effect** — `research_replay` ablation arms
  `ABLATION_ARMS = ("baseline","memory_only","memory_prediction","full_cie")`
  (`scripts/research_replay.py:63`), per-case metrics `evaluate` (`:418+`),
  `intervention_quality_signals` sourced from `decision_value.changes_experiment_design`
  (`:334-338`), and the forbidden behaviour
  `continue_attribution_without_decision_value` (`:90`).

So the "value of a decision" concept exists and is well-developed, but it is **not part of the
cognitive-memory artifact**; a new decision-experience layer would have to bridge into
`strategy_memory`/`research_replay` rather than extend `cognition.py`.

---

## 6. Existing suppression of meaningless attribution / pseudo-progress

| Mechanism | Where |
|---|---|
| **CM9 anchor-set equivalence** — `stagnation_fingerprint` digests the sorted canonical anchor set (`scripts/cognition.py:604-614`); duplicate fingerprints raise CM9 "实质等价的解释不得当作独立进展" (`:1453-1461`) |
| **CM8 distinguishing power** — an open competition without conflicting predictions + a real discriminating intervention + a pre-declared `discrimination_rule` is flagged (`:974-986`); `prediction_compare.distinguishability` owns the scientific verdict (`:971-973`) |
| **CM7 self-certification** — `_conflict` records declared-vs-derived disagreement, never adopts it (`:596-601,903`); `declared_support` is only accepted to be reported (`:1624-1628`); derived support never reads a revision-declared level (`:505`) |
| **CM10 legacy undecidable** — no machine-decidable criterion → reported, compares as UNTESTABLE, no retrospective verdict (`:1156-1160`) |
| **Next-action anti-proliferation** — `next_action_hint` says "不要继续增加解释" when a competition lacks distinguishing power (`:2056-2061`) |
| **Legacy reconstruction guards** — no competition manufactured from `nearest_alternative` unless a real experiment exists (`:1100-1107`); `known_flaws` is not read as refutation (`:1064-1068`); no preregistration → exploratory anomaly, no prediction success/failure (`:1228-1239`) |
| **Failure/staleness filtering** — `_resolve` marks stale/missing (`:653-671`); stale entries never enter hot memory (`:1787-1796`); `CM3` |
| **Repetition escape (strategy)** — `STAGNANT_MENU_RUN` detects a repeated recent menu and ranks `divergent` first (`scripts/strategy_memory.py:681-684,703,716-724`); lexicographic rank, no weights |
| **No self-rated novelty** — `research_replay.decision_errors` rejects `novelty_self_rating` (`RP5`, `scripts/research_replay.py:392-395`) |
| **Derived-only updates cannot inflate metrics** — `presets/memory-consolidation.md:65`: rebuilding a projection must not raise Claim / Insight / Scheduler success metrics |

---

## 7. Public API and CLI of `cognition.py`

### 7.1 Module constants that are de-facto public contract

`SCHEMA_INDEX`, `SCHEMA_REVISION` (`:59-60`); `COGNITION_DIRNAME`, `INDEX_NAME`,
`REVISIONS_NAME`, `INSIGHT_CARDS_NAME`, `BRIEF_NAME`, `STATE_NAME`, `SCHEDULER_NAME`
(`:67-74`); `MEMORY_CLASSES` (`:82`); `REVISION_KINDS` (`:88`), `MECHANISM_KINDS` (`:103`),
`REVISION_ACTORS` (`:108`), `STRATEGY_REVISION_ACTORS` (`:116`), `STRATEGY_UPDATE_ACTOR`
(`:119`); `SUPPORT_LEVELS` (`:123`), `MECHANISM_STATUSES` (`:131`),
`COMPETITION_STATUSES` (`:135`), `FORBIDDEN_REVISION_KEYS` (`:142`), `MECHANISM_FIELDS`
(`:149`), `ANOMALY_FIELDS`/`COMPETITION_FIELDS`/`PREDICTION_FIELDS`/`STRATEGY_FIELDS`
(`:159-174`), `REF_KEYS` (`:176`), `PAYLOAD_KEYS` (`:196`), `ID_PREFIX` (`:207`),
`CONTEXT_TIERS` (`:212`), `WARNING_RULES` (`:229`), `DEFAULT_BUDGET=6000` (`:248`),
`REPEAT_BLOCKING_KINDS` (`:1823`), `LEGACY_ORIGIN`/`REVISION_ORIGIN` (`:186-187`),
`LEGACY_*_PREFIX` (`:189-192`), `TIER_ORDER` (`:483`), `REFUTING_FAILURE_KINDS` (`:486`),
exit codes `EXIT_OK/ERROR/HARD/ENV` (`:62-65`).

### 7.2 Public functions (non-underscore) and classes

| Line | Signature | Purpose |
|---|---|---|
| 232 | `is_warning(rule) -> bool` | whether a rule id has `warning` severity |
| 237 | `hard_only(diagnostics) -> List[Diagnostic]` | blocking diagnostics only |
| 242 | `warnings_only(diagnostics) -> List[Diagnostic]` | advisory diagnostics only |
| 257 | `class Diagnostic` | `{rule, path, detail}`, `render()`, `as_dict()` |
| 282 | `class CognitionError(Exception)` | environment-level failure (exit 4) |
| 290 | `canonical_json(value) -> str` | stable serialization for digests |
| 295 | `digest_of(value) -> str` | `sha256:` digest of canonical JSON |
| 299 | `digest_of_lines(records) -> str` | digest of a record list |
| 303 | `load_state(path) -> Dict` | load + validate canonical state (raises `CognitionError`) |
| 315 | `load_insight_cards(path) -> (List[Dict], List[Diagnostic])` | delegate to `prediction_compare.load_cards` |
| 325 | `project_insights(state, cards, audits=None) -> Dict` | classify insight cards from canonical facts, never their label |
| 361 | `load_revisions(path) -> (List[Dict], List[Diagnostic])` | read JSONL; malformed lines → CM1, never raise |
| 397 | `cognition_dir_for(state_path, override=None) -> Path` | default `<state dir>/cognition` |
| 403 | `route_of(state_path) -> str` | route letter = owning directory name |
| 412 | `class CanonicalView` | read-only index over the eight arrays; `get/contains/validity_of` |
| 452 | `normalize_refs(raw) -> Dict[str, List[str]]` | coerce `refs` into the eight arrays |
| 464 | `iter_refs(refs)` | yield `(key, id)` pairs in canonical order |
| 470 | `merge_refs(target, extra) -> Dict` | union of ref maps |
| 489 | `tier_at_least(tier, floor) -> bool` | `verification_tier` comparison |
| 495 | `derive_support(view, refs, declared=None) -> (level, reasons, conflicts)` | **anti-self-certification core**; pure function of canonical facts |
| 604 | `stagnation_fingerprint(view, refs) -> str` | stable identity of an anchor set (CM9) |
| 1026 | `derive_legacy_structures(view, covered_claims, covered_hypotheses, covered_experiments) -> Dict` | reconstruct mechanisms/competitions/anomalies/boundaries from canonical state for legacy takeover |
| 1398 | `project_strategy(state, index, scheduler, revisions) -> Optional[Dict]` | derived scientific-value/strategy view (telemetry-labelled) |
| 1417 | `build_index(state, revisions, route="", insight_cards=None, scheduler=None, audits=None) -> (Dict, List[Diagnostic])` | pure index builder |
| 1521 | `full_index(...)` | index + complete diagnostic set; single entry point for build/validate/check/brief/recall |
| 1547 | `validate_revisions(state, revisions) -> List[Diagnostic]` | CM1/CM2/CM3/CM7 revision-log validation |
| 1637 | `validate_index(state, revisions, index, insight_cards=None, scheduler=None, audits=None) -> List[Diagnostic]` | recompute + compare; drift is CM3 |
| 1716 | `focus_ids(view) -> List[str]` | hot-memory seed from canonical focus set |
| 1751 | `recall(index, state, budget=DEFAULT_BUDGET) -> Dict` | bounded hot/warm/cold selection + failure constraints + obligations |
| 1815 | `reuse_overlap(mechanism, focus) -> bool` | whether a mechanism's refs intersect the focus set |
| 1826 | `failure_constraints(state) -> List[Dict]` | failure memory with repeat prohibitions |
| 1875 | `open_obligations(state) -> List[Dict]` | accepted limitations / unfinished obligations |
| 1891 | `render_brief(index, state, budget=DEFAULT_BUDGET) -> str` | render `context-brief.md` |
| 2055 | `next_action_hint(view, index) -> str` | next-action pointer from undecided competitions/uncertainties |
| 2118 | `state_fingerprint(path) -> str` | sha256 of state bytes (CM0 guard) |
| 2128 | `load_scheduler(path) -> Optional[Dict]` | read optional scheduler telemetry |
| 2141 | `projection_inputs(state, route_dir) -> (cards, scheduler, audits)` | one-way read of out-of-state index inputs |
| 2174 | `op_build(state_path, cognition_dir) -> int` | build + write index/brief; CM0 byte guard |
| 2201 | `op_validate(state_path, cognition_dir) -> int` | validate log + index; prints `[advisory]` for warnings |
| 2228 | `op_brief(state_path, cognition_dir, out, budget) -> int` | write brief |
| 2239 | `op_recall(state_path, cognition_dir, budget) -> int` | print recall JSON |
| 2246 | `op_check(state_path, cognition_dir) -> int` | rebuild + compare stored index/brief; CM0 guard |
| 2375 | `selftest() -> int` | built-in `--selftest` suite |
| 2494 | `build_parser() -> argparse.ArgumentParser` | CLI parser |
| 2509 | `main(argv=None) -> int` | entry point |

### 7.3 CLI

```
python3 cognition.py build    --state <state.json> [--cognition DIR]
python3 cognition.py validate --state <state.json> [--cognition DIR]
python3 cognition.py brief    --state <state.json> [--cognition DIR] [--out FILE] [--budget N]
python3 cognition.py check    --state <state.json> [--cognition DIR]
python3 cognition.py recall   --state <state.json> [--cognition DIR] [--budget N]
python3 cognition.py --selftest
python3 cognition.py --list-kinds
```

Parser `:2494-2506`, dispatch `:2509-2543`. `--json` is declared (`:2503`) but not consumed.
Exit codes: `0` pass, `1` argument error, `3` hard violation, `4` environment not satisfied
(`:42-46,62-65,2527-2543`). Note: the policy §9 example also lists `recall`
(`references/cognitive-memory-policy.md:215`), which the CLI supports.

---

## 8. Backward-compatibility constraints and invariants for new code

Must-respect list, each with its enforcement point:

1. **CM0 — canonical state is byte-unchanged.** `op_build` fingerprints before/after and
   aborts with exit 3 (`scripts/cognition.py:2174-2198`); `op_check` appends a CM0 diagnostic
   on change (`:2274-2275`). Tested byte-for-byte (`test_cognition.py:1088-1102`).
2. **No new state slot; S1—S7 / V1—V24 and `state_check.py` unchanged**
   (`references/cognitive-memory-policy.md:28-31`; `docs/cognitive-insight-engine.md:104-115`,
   §8 :150-151). Cognition enforces its own `CM0`—`CM10` namespace only (`:29-31`).
3. **Derived layer is rebuildable and non-authoritative.** `validate_index` recomputes and
   requires canonical-JSON equality of the projection (`:1670-1678`); digests for
   state/revisions/insight_cards/scheduler must match (`:1655-1669`). "When they disagree
   with the state, the state wins and the index must be rebuilt"
   (`docs/cognitive-insight-engine.md:217-218`).
4. **Determinism / identical bytes.** `build_index` is pure (`:1425`);
   `test_build_is_reproducible`, `test_build_twice_writes_identical_bytes`,
   `test_index_is_rebuildable_from_canonical_state_alone` (`test_cognition.py:254-286`).
5. **Frozen schema ids.** `SCHEMA_INDEX`/`SCHEMA_REVISION` asserted
   (`test_cognition.py:243-245,1558-1560`).
6. **Nothing written outside `cognition/`.** `test_cognition_writes_nothing_outside_its_own_directory`
   (`test_cognition.py:1104-1111`).
7. **Warning severity table is contract.** `WARNING_RULES = ("CM7","CM8","CM9","CM10")`
   (`:229`); a warning must not flip an exit code and a rebuild warning is not index drift
   (`:1697-1701`); consumers read the table instead of re-deciding
   (`references/cognitive-memory-policy.md:70-79`;
   `test_cognition.py:1029-1079`; `scripts/legacy_handoff.py:331-339`).
8. **Legacy readability.** A shipped template with no revision log must build/check with zero
   diagnostics and every projected entry `origin=legacy_derivation, retrospective=true,
   revision_ids=[]` (`test_cognition.py:203-234`).
9. **Single-source actor lists.** `REVISION_ACTORS` / `STRATEGY_REVISION_ACTORS`
   (`:108-119`) — writer and validator must consult the same tuple.
10. **Payload shape is per-kind.** A new key on `after`/`before` not in
    `PAYLOAD_KEYS[kind]` is `CM1`, not a silently ignored extra (`:1611-1633,155-158`).
11. **Support level cannot be self-declared.** `CM7` records a conflict; `derive_support`
    never reads the declared value (`:502-505,596-601`).
12. **Provenance is mandatory.** `trigger` + non-empty `refs`, all refs existing, none to a
    future `state_version`, none to a stale/invalid/pending object (`CM3`, `:1593-1610`).
13. **Stable serialization.** `canonical_json` (sorted keys, `ensure_ascii=False`,
    no spaces) is the digest basis (`:290-292`).
14. **No second authority.** No strategy DB, no second scheduler
    (`docs/cognitive-insight-engine.md:106-114`;
    `scripts/strategy_memory.py:830-849`).

---

## 9. Where memory resides relative to project route dirs

```
<project root>/
└── .research-idea-pipeline/
    └── routes/<R>/
        ├── research-state.json              # canonical authority
        ├── scheduler.json                   # telemetry (read-only for cognition)
        ├── populations/                     # sibling control-plane dir
        ├── assurance/{structural-equivalence/}
        ├── repairs/  reviews/
        ├── experiments/<XID>/{preregistration.json,...}
        └── cognition/                       # ← cognitive memory (control plane)
            ├── model-revisions.jsonl        #   event layer, append-only
            ├── index.json                   #   derived projection
            ├── context-brief.md             #   derived projection (recall)
            ├── insight-cards.jsonl          #   input, owned by prediction_compare
            ├── recovery-log.jsonl           #   preset recovery ledger (preset_router)
            └── handoff.json / handoff-report.md   # legacy takeover (legacy_handoff)
```

* `cognition/` "sits inside the route control plane, beside `populations/` and `assurance/`"
  and "is not a human document and is not placed under `routes/<R>/docs/`"
  (`references/cognitive-memory-policy.md:22-26`; `docs/cognitive-insight-engine.md:55-56`).
* Default resolution: `cognition_dir_for` returns `state_path.parent / "cognition"`
  (`scripts/cognition.py:397-400`); `route_of` returns the parent directory name (`:403-405`).
  CLI `--cognition` overrides the location (`:2499,2525-2526`).
* Control-plane contract: "clear schema / stable ids / mutation safety / validator
  friendliness / append-only provenance", because the directory is machine-only
  (`references/project-layout.md:972-977`; the route tree at `:118-130`).
* Cognition never lives in the skill package, nor in `routes/<R>/docs/`, nor in
  `.research-idea-pipeline/meta/`.

---

## 10. Tests a new decision-experience layer must keep passing

Primary: `scripts/test_cognition.py` (1218 lines). Classes and what they pin:

| Class | Line | Pins |
|---|---|---|
| `TestBackwardCompatibility` | 200 | shipped template builds with zero diagnostics; legacy origin/retrospective; schema id stability; state shape unmodified by validation |
| `TestRebuildability` | 252 | deterministic projection; identical bytes on rebuild; derived layer delete-rebuild; index drift detection; stale index after state change |
| `TestDerivedSupport` | 310 | the five-level ladder and every evidence condition; refutation outranks positives; frozen `SUPPORT_LEVELS` |
| `TestRevisionAuthority` | 389 | CM2 forbidden keys; CM7 self-rating not adopted; CM3 dangling/future/empty refs; CM1 seq/ids/kind/actors; R12/R13 cannot write; CM6/CM8/CM9; torn JSONL is non-fatal |
| `TestMemoryLifecycle` | 511 | invalidation → stale; stale leaves hot memory; invalidation reaches anomalies + competitions; failure memory + stop rules; obligations; budget; deterministic ordering |
| `TestContextBrief` | 596 | brief declares it is not evidence; every mechanism line carries `[support/status]`; speculation stays labelled; refuted/open competition/failure constraints recovered; intervention preferred over more explanations |
| `TestCrossSessionAvoidsRefutedMechanism` | 676 | restart recovers refuted mechanism in warm memory, repeat prohibition, CM9 re-proposal flag, next-action does not revive it |
| `TestInsightCertificationChain` | 843 | frozen prediction → observation → gate → insight → memory → scheduler; deleting the audit downgrades the rebuilt index and raises `PC7`; comparator never writes state |
| `TestLegacyWarningsDoNotBlock` | 1029 | `WARNING_RULES` table; CM10 advisory does not make `check` red nor count as drift; hard violation still red |
| `TestNoCanonicalMutation` | 1086 | build/validate/check/brief never write the state; cognition writes nothing outside its dir |
| `TestCLI` | 1118 | selftest, `--list-kinds` = `REVISION_KINDS`, exit codes 4/1/3, build→check round-trip, recall JSON |
| `TestShippedFixture` | 1186 | `examples/cognition/` round-trips; fixture passes `state_check`; fixture marked synthetic |

Adjacent suites that import cognition and would break on schema/exit-code changes:

* `scripts/test_legacy_handoff.py:24` — LH12 drift, takeover byte-identity, rollback,
  warning-vs-blocking.
* `scripts/test_preset_router.py:35` — `memory-consolidation` handler, recovery ledger,
  drift recovery, `strategy_decisions[]` only-key assertion (`:724`).
* `scripts/test_strategy_memory.py:21` — value dimensions, no composite, `strategy_update`
  payload projection.
* `scripts/test_prediction_compare.py:21`, `scripts/test_research_replay.py:22`,
  `scripts/test_loop_runtime_correctness.py:34`.

Release gate: `scripts/release_check.py` runs `cognition build` → `check` → rebuild and
requires byte-identical `index.json` (`:273-295`), the LH12 warning behaviour (`:637-665`),
and legacy-fixture `CM10` advisory output (`:641-658`).

A new decision-experience layer must therefore also keep passing the `--list-kinds` frozen
enum, `PAYLOAD_KEYS` per-kind shape checks, and the `examples/cognition/` fixture round-trip.

---

## Top gaps for a decision-experience layer (summary)

1. **No first-class decision-experience record and no projection of it.** `strategy_update`
   shares `model-revisions.jsonl` but `_Builder.fold` deliberately skips it
   (`scripts/cognition.py:715-722`); there is no `decision`/`strategy` value in
   `MEMORY_CLASSES` (`:82-84`) and no `index.json` section for decisions.
2. **No decision-value / policy-effect measurement in `cognition.py`.** `decision_impact` is
   an unvalidated passthrough string (`:165,828,853-854`); the only real measurements are
   `strategy_memory.value_assessment` (`:205-331`), the `with_memory` vs `without_memory`
   counterfactual in `strategy_decision` (`:1016-1088`), and `research_replay` ablation.
3. **Scientific vs system memory are not typed apart.** Separation relies on `kind` +
   consumer convention; there is no `experience_class`/`domain` discriminator on revision
   events or index entries.
4. **`strategy_update` is validated by a different module (`SV*`, not `CM*`)** and its
   payload is only loosely shaped (`STRATEGY_FIELDS`, `scripts/cognition.py:172-174`).
5. **Three un-reconciled decision carriers**: the append-only revision log, the 20-entry
   `scheduler.strategy_decisions[]` (`DECISION_LOG_LIMIT`, `scripts/strategy_memory.py:859`),
   and `cognition/recovery-log.jsonl` (`scripts/preset_router.py:60-62`).
6. **No legacy/retrospective handling for decision experience.** `derive_legacy_structures`
   reconstructs only mechanisms/competitions/anomalies/boundaries; `strategy_update` has no
   `provenance`/`retrospective` path.
