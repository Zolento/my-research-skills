# Audit B — Discovery Replay / Research Replay subsystem

Scope: `research-idea-pipeline/scripts/research_replay.py` (1446 lines, full read),
`references/discovery-replay.md`, `presets/discovery-replay.md`, `scripts/test_research_replay.py`,
`prediction_compare.py` (grepped), `preset_router.py` (targeted), `release_check.py` (targeted),
`examples/replay/**`. Read-only audit; no source file modified.

Component root (relative to worktree `research-idea-pipeline/skill-rsi-dev/`): `research-idea-pipeline/`.

---

## 1. Exact data model

### 1.1 Case input — schema `research-idea-pipeline/replay-case@1`

Declared at `scripts/research_replay.py:54` (`SCHEMA_CASE`), validated by `case_errors`
(`research_replay.py:109-158`). Shipped examples: `examples/replay/adversarial/adv1.json` … `adv14.json`.

Top-level keys (validator + generator `_case` at `research_replay.py:881-905`):

| Key | Required | Type | Validator |
|---|---|---|---|
| `_schema` | yes | `"research-idea-pipeline/replay-case@1"` | `:113-114` |
| `id` | yes | non-empty str | `:115-116` |
| `question` | yes | non-empty str | `:117-118` |
| `title` | by generator only | str | not validated |
| `visible` | yes | dict | `:119-127` |
| `hidden.answer` | yes | dict | `:128-138` |
| `evaluation_only` | yes | dict | `:144-157` |

`visible` sub-keys (`:119-127`, `visible_view` `:174-190`):
- `state` — **required**, dict (the canonical research state as it was; shape mirrors
  `research-state.json`: `state_version`, `contract`, `claims`, `evidence`, `assumptions`,
  `hypotheses`, `experiments`, `literature`, `failures`, `uncertainties`, `assurance`, `repairs`).
  Fixture at `research_replay.py:737-801`.
- `revisions` — optional list; must be list if present (`:125-127`). Records validated only as
  dicts and stripped of `HIDDEN_KEYS` (`:181-183`); revision schema is
  `research-idea-pipeline/cognition-revision@1` (`cognition.py:60`, example `research_replay.py:1061-1066`).
- `available_literature` — optional list (`:125-127`).
- `known_conditions` — optional list (`:125-127`).
- `insight_cards` — optional list (`:125-127`); consumed by `cg.project_insights` (`:324-326`).
- `scheduler` — optional, passed opaquely to `cg.full_index(..., scheduler=...)` (`:276-277`).
  Shape used in ADV10: `{state_version, next_actions, eig_calibration.records[],
  operator_stats{by_operator, recurring_failure_patterns}}` (`:1076-1085`).
- `observation_packet` — optional dict; must satisfy `pc.SCHEMA_OBSERVATION`
  (`research-idea-pipeline/prediction-observation@1`), with `experiment_id`,
  `execution.{status,validity}`, `outcomes[].{id,value,source{kind,location,content,digest}}`
  (`_packet` `:804-816`).

`hidden` — never reaches the runner:
- `later_results` — list[str] (`:207`), leak markers.
- `answer` — **required dict** (`:128-133`), the evaluation ground truth:

| `hidden.answer` key | Type | Used at |
|---|---|---|
| `mechanism_terms` | list[str] | `:425`, `:510` |
| `assumption_terms` | list[str] | `:426`, `:510` |
| `boundary_terms` | list[str] | `:427` |
| `true_outcome_class` | one of `pc.OUTCOME_CLASSES` | `:135-138`, `:431` |
| `discriminating_intervention` | str, or absent→`None` | `:446-455` |
| `required_controls` | list[str] | `:456-458`, `:517` |
| `human_novelty_label` | `novel`/`not_novel`/`unknown` | `:460-469` |
| `novelty_neighbours` | list[str] | `:461-469` |
| `novelty_rating` | numeric — **rejected as sole novelty source** (`RP5`) | `:139-143` |
| `reference_reasoning`, `stopped_protocol` | list/str | `:210`, `:568` |
| `mechanism_terms`×, `assumption_terms`×, `boundary_terms`×, `required_controls`× also feed `forbidden_strings` | | `:209-211` |

`evaluation_only` sub-keys (`:144-157`):
- `must_not_appear` — list[str], extra leak markers (`:148-152`, `:217-218`).
- `forbidden_behaviours` — subset of `FORBIDDEN_BEHAVIOURS` (`:88-99`, `:153-157`).
- `expected_behaviour` — `stop_attribution` | `design_intervention` (`:453`, `:486-496`).
- `expected_decision_changed` — bool (`:534`).
- `open_second_session` — bool (`:499`).
- `reference_mechanism` — str, extra leak marker (`:214-216`).

### 1.2 Decision output — schema `research-idea-pipeline/replay-decision@1`

`SCHEMA_DECISION` at `research_replay.py:55`; required fields enforced by `decision_errors`
(`:382-398`): `_schema`, and **`arm`, `mechanism_terms`, `used_memory`** (`:389-391`);
`arm ∈ ABLATION_ARMS` (`:396-397`); `novelty_self_rating` must be `None` (`:392-395`, `RP5`).

Full decision shape emitted by `cie_offline_runner` (`:244-339`): `_schema`, `case_id`, `arm`,
`capabilities`, `used_memory`, `mechanism_terms`, `predicted_outcome_class`,
`diagnostic_outcome_class`, `anomaly_class`, `evidence_class`, `evidence_eligible`,
`scientific_status`, `provenance_gaps`, `chosen_intervention`, `identification_controls`,
`representation_changed`, `repeated_prior_error`, `novelty_self_rating`, `decision_changed`,
`insight_classes`, plus capability-conditional `repeat_blocked` (`:303`), `transition_allowed`
(`:320`), `switch_action` (`:329`), `independent_exploration_allowed` (`:332`),
`intervention_quality_signals` and `objections` (`:336-338`).

### 1.3 Run / evaluation / ablation verdict fields

- `run_case` result (`:610-617`): `{case_id, arm, decision, evaluation, diagnostics, leak_checked}`.
- `evaluate` result (`:539-547`): `{case_id, arm, metrics{7 dims}, violations[...], passed:bool, note}`.
  Each metric: `_metric(value, basis, reason)` → `{"value","basis","reason"}` (`:414-415`).
- `run_suite` result (`:705-730`), schema `research-idea-pipeline/replay-ablation@1`:
  `schema, cases, runs_per_case, arms, sample_size, sufficient_sample, per_arm, delta_vs_baseline,
  claim, runner, undifferentiated_arms, limitations`.
  `per_arm[arm]` (`:670-681`): `capabilities, runs, cases, observations, dimensions,
  violations, pass_rate, results`.
  `dimensions[dim]` (`_dimension_means` `:638-652`): `observable_cases, total_cases, mean, min, max`.
- `smoke` result (`:1232-1239`), schema `research-idea-pipeline/replay-smoke@1`:
  `{schema, steps[], passed, canonical_untouched, fixture_marking}`.
- There is **no `verdict` key** anywhere in this module. The closest verdict equivalents are
  `evaluation.passed`, `run_suite.sample_size`/`sufficient_sample`, and `decision.scientific_status`.
- Exit codes: `0` OK, `1` argument error, `3` hard violation, `4` environment (`:57-60`, `:36`).

---

## 2. RP2 anti-leakage mechanism — exact coverage and gaps

### What it checks today

1. **Structural strip** — `visible_view` (`:174-190`) rebuilds the payload from an allowlist of
   `visible.*` keys and recursively drops `HIDDEN_KEYS = ("hidden","evaluation_only","reference",
   "answer","later_results","future")` from `state` and each `revisions` record
   (`_strip_hidden_keys` `:193-199`). `hidden` and `evaluation_only` are never forwarded.
2. **String-content verification** — `forbidden_strings` (`:202-220`) collects:
   `hidden.later_results`, `answer.{mechanism_terms, assumption_terms, boundary_terms,
   required_controls, reference_reasoning}`, `evaluation_only.reference_mechanism`, and
   `evaluation_only.must_not_appear`; then keeps only strings with `len(text.strip()) >= 12`
   (`:220`).
3. **Scan + hard refusal** — `leak_scan` (`:223-225`) JSON-dumps the visible payload and returns
   every forbidden string found in it. `run_case` (`:600-604`) raises `cg.CognitionError
   ("future-information leak: ...")` before calling the runner.
4. **Answer-path one-wayness test** — `test_evaluation_never_reads_the_decision_for_the_answer`
   (`test_research_replay.py:204-217`) mutates the hidden answer and asserts the decision is
   byte-identical while the metric changes.
5. `RP5` novelty independence (`:139-143`, `:392-395`) is enforced inside the same case/decision
   validators.

### What it does NOT check

- **Only exact substring match, and only strings ≥12 chars.** Any leak shorter than 12 chars,
  paraphrased, re-ordered, translated, tokenised, or present only as a *derived* fact is invisible
  (`:220`; test at `test_research_replay.py:111-118` asserts short strings are *not* markers).
- **Only string-typed fields are scanned.** Numeric hidden facts (e.g. the true delta magnitude
  `-2.0`, a `novelty_rating`) are never leak markers. `answer.novelty_rating` is validated for
  provenance but never checked for leakage.
- **No per-field path awareness.** `leak_scan` flattens to one JSON blob (`:224`); it cannot say
  *which* visible field leaked, and cannot distinguish a legitimate overlap between visible
  `known_conditions` and a hidden term.
- **`HIDDEN_KEYS` is key-name based only.** A hidden fact placed under a differently-named key
  inside `~visible~` is not stripped; the strip is not schema-validated.
- **`visible.state` is not validated against the canonical state schema.** `case_errors` only
  checks that `visible.state` is a dict (`:123-124`). A hand-written case may carry a state that no
  real pipeline reprised, and replay will happily run it.
- **No check that the visible view is temporally consistent** with `hidden.later_results` — e.g.
  that the visible `state_version`/`revisions` predate the future outcome.
- **No cross-case leakage check** across a directory; `load_cases` (`:620-628`) loads each case
  independently.
- **`show`/`validate`/`suite` never verify the leak guard for externally supplied runners** beyond
  `run_case`'s own call (`:600`), which is reused — but a runner reading the case file directly from
  disk bypasses the guarantee entirely.
- **Leak guard is not applied to `hidden` content that the *generator* invents at runtime** beyond
  the `SYNTHETIC FIXTURE` tag convention.

---

## 3. The four ablation arms — verbatim ids and definitions

`ABLATION_ARMS` at `research_replay.py:63`; `ARM_CAPABILITIES` at `:65-70`.

| arm id (verbatim) | capabilities (verbatim) | what varies | what is held constant |
|---|---|---|---|
| `baseline` | `()` | nothing: raw state only (`:267-274`) | state, revisions, scheduler, packet, runner code path, leak guard |
| `memory_only` | `("cognitive_memory",)` | `cg.full_index` + `cg.recall` enabled (`:276-303`) | comparator and strategy-memory disabled (`:305-308`, `:334`) |
| `memory_prediction` | `("cognitive_memory","prediction_comparator")` | adds `pc.assess_experiment`, `pc.evidence_transition_allowed`, `cg.project_insights`, `pc.diagnosis_switch` (`:310-332`) | `strategy_memory` off (`:334`) |
| `full_cie` | `("cognitive_memory","prediction_comparator","strategy_memory")` | adds `sm.value_assessment`; emits `intervention_quality_signals`, `objections` (`:334-338`) | everything above |

Capabilities are cumulative and asserted monotone (`test_research_replay.py:234-239`).
`search_efficiency` is always computed against a fresh `baseline` run inside `run_case`
(`research_replay.py:607-614`). Note: every non-baseline arm runs the baseline **twice** (once for
its own `run_case`, once when `arm=="baseline"` is itself evaluated), which is observed by the
`undifferentiated_arms` logic.

---

## 4. The seven evaluation dimensions — verbatim names and computation

`METRIC_DIMENSIONS` at `research_replay.py:73-81`; computed in `evaluate` (`:418-528`).

1. **`mechanistic_understanding`** (`:425-429`, `:508-512`)
   `_contains_all(text, answer[field])` over `text = " ".join(decision["mechanism_terms"])` for
   `mechanism_terms`, `assumption_terms`, `boundary_terms`; value =
   `_rate(mech_hits+assump_hits+bound_hits, mech_total+assump_total+bound_total)` (`_rate` `:410-411`).
   `basis` = mechanism + assumption terms (boundary terms omitted from `basis` — a display gap).
2. **`prediction_quality`** (`:431-444`, `:513-514`)
   `1.0` iff `decision["predicted_outcome_class"] == answer["true_outcome_class"]`; `None` if the
   runner emitted no class; **`None` if `decision["evidence_eligible"]` is false** (diagnostic
   comparison is unratable, not zero).
3. **`intervention_quality`** (`:446-458`, `:515-519`)
   If `answer.required_controls` non-empty → value = `_rate(control_hits, control_total)` over
   `decision["identification_controls"]` (the discriminating-intervention match is **discarded**).
   Else → `1.0`/`0.0` for `decision["chosen_intervention"] == answer["discriminating_intervention"]`,
   with the override that `stop_attribution` + empty choice scores `1.0` (`:453-454`). `None` when
   the case names no expected intervention.
4. **`scientific_novelty`** (`:460-472`, `:520`)
   Only from `answer.human_novelty_label` (`novel`→1.0, `not_novel`→0.0, `unknown`→`None`) or the
   presence of `answer.novelty_neighbours` (→`None`, reason lists neighbours). Otherwise `None`
   with reason "没有独立 novelty 证据…agent 自评被拒绝".
5. **`search_efficiency`** (`:474-484`, `:521-522`)
   `None` without a baseline decision. Else `effective(d) = (1 if d["predicted_outcome_class"] in
   pc.WORLD_CLAIMING_CLASSES and d["evidence_eligible"] else 0) + (1 if d["decision_changed"] else 0)`;
   value = `effective(decision) - effective(baseline)`.
6. **`stagnation_recovery`** (`:486-496`, `:523-525`)
   `stop_attribution` → `1.0` if `decision["switch_action"] ∈ {RECORD_BOUNDARY_AND_STOP,
   REDESIGN_QUESTION, FIND_DISCRIMINATING_INTERVENTION}` else `0.0`. `design_intervention` → `1.0`
   iff `chosen_intervention` truthy. Otherwise `None`.
7. **`memory_accumulation`** (`:498-505`, `:526-527`)
   Only when `evaluation_only.open_second_session` is true: `1.0` iff `decision["used_memory"]`
   non-empty, else `0.0`. Otherwise `None`.

No dimension is summed; `note` at `:545-546` states this, and tests forbid
`total`/`overall`/`score`/`weighted` keys (`test_research_replay.py:141-144`).

---

## 5. Selection/policy effect vs outcome correlation

**It measures outcome correlation and proxy deltas, not the effect of strategy *selection*.**

Evidence:

- The runner is a single deterministic pipeline per arm, not a policy that ranks a candidate set:
  `cie_offline_runner(visible, arm)` (`:232-339`) always has exactly one `chosen_intervention`,
  produced by `_intervention_for` (`:351-364`) — the first open competition's
  `discriminating_intervention`, else the first `planned` experiment. There is **no candidate
  list, no ranking, no selected-vs-rejected comparison**.
- `intervention_quality` is a point match against one expected string (`:452`), not a selection
  metric; and when `required_controls` exist it stops scoring the intervention at all (`:456-458`,
  `:515-519`).
- `search_efficiency` is a hand-rolled count difference against baseline (`:478-484`), not an
  off-policy/selection estimator; its second term `decision_changed` is set *inside the runner*
  (`:331`: `switch["action"] != "CONTINUE_ATTRIBUTION" or bool(hot)`), so it is a self-reported
  flag, not an observed policy improvement.
- `decision_changed` and `expected_decision_changed` (`:534-535`) only test whether the flag flipped
  — no notion of a better *choice among alternatives*.
- `run_suite` reports per-dimension deltas vs baseline (`:683-692`), i.e. capability→outcome
  correlation on synthetic fixtures.
- The design admits the gap explicitly: `discovery-replay.md:99-100` and the selftest expectation
  (`:1326-1328`) state that `memory_prediction` and `full_cie` are identical on all seven
  dimensions because **none of them isolates the strategy layer**; `undifferentiated_arms`
  (`:696-701`) exists precisely to avoid implying a policy gain.
- `research_replay.py:7-8` frames the question as "did the cognitive layer improve discovery",
  and `:14-17`/`:721-728` state gains may not be claimed; nothing in the module estimates a
  selection policy's counterfactual effect.

**Conclusion:** no policy-effect measurement exists. All seven dimensions are outcome/behaviour
correlations or proxies thereof.

---

## 6. Evaluability and "actions never executed in history"

### How a case becomes evaluable

- `case_errors` (`:109-158`) gates the *case*: `_schema`, non-empty `id`/`question`, dict
  `visible.state`, and a `hidden.answer` whose `true_outcome_class ∈ pc.OUTCOME_CLASSES`
  (`:135-138`). Without `hidden.answer` the case is rejected outright (`:128-133`).
- `run_case` (`:592-617`) gates the *run*: leak scan, then `decision_errors` (`:382-398`); a
  malformed decision yields `RP3` diagnostics recorded in `result["diagnostics"]`
  (`:615`) but does **not** abort the run (only `run` CLI returns `EXIT_HARD` on `passed`).
- Per-dimension evaluability is decided inside `evaluate` and expressed as `value: null` plus a
  human-readable `reason` (`:434-436`, `:448-450`, `:470-472`, `:474-476`, `:494-496`, `:503-505`).
  `null` is documented as "not assessable", never 0 (`:545-546`).

### Actions never executed in history

There is **no execution-history notion at all**. The runner never inspects whether an experiment
was executed; it reads `state.experiments[].status` only to pick a `planned` experiment id
(`:361-363`). Consequences:

- `intervention_quality` scores a *proposed* intervention (`chosen_intervention`) against an
  expected id; it never verifies the action was or could be run.
- `required_controls` coverage (`:456-458`) is scored from `decision["identification_controls"]`,
  which `cie_offline_runner` **never populates** (declared `[]` at `:259`, never assigned), so any
  case with `required_controls` scores `0.0` regardless of the decision — a silent floor.
- `stagnation_recovery` for `design_intervention` scores `bool(chosen)` (`:492`) — mere presence of
  a string, not executability.
- `smoke` (`:1162-1239`) executes a synthetic route but never replays a real historical execution.

### Is there a `NO_SUPPORT` concept already?

**No.** Grep across the component finds no `NO_SUPPORT`, `REPLAY_SUPPORTED`, or `OBSERVED`
(only `execution_gate.py:276`'s unrelated `NO_OBSERVED_EVIDENCE` string and `evidence_outcome`'s
`epistemic_status` values `Observed`/`Supported`). The nearest existing analogues, none of which is
counterfactual-support tagging:

- `metric["value"] is None` + `reason` — "this dimension cannot be assessed in this case"
  (`:434-436` etc.), and `discovery-replay.md:76-77`.
- `decision["scientific_status"] = "NO_INFERENCE"` (`:256`) and
  `pc.SCIENTIFIC_STATUSES = ("MAY_INFORM_TRANSITION","DIAGNOSTIC_ONLY","NO_INFERENCE")`
  (`prediction_compare.py:110-113`).
- `pc.EVIDENCE_CLASSES = ("QUALIFIED_EVIDENCE","DIAGNOSTIC_ONLY","INSUFFICIENT_PROVENANCE")`
  (`prediction_compare.py:89-93`), carried on the decision as `evidence_class`
  (`research_replay.py:316`) and rendered in `prediction-anomaly-competition.md:152`.

None of these distinguishes OBSERVED vs REPLAY_SUPPORTED vs NO_SUPPORT for a *counterfactual
action*.

---

## 7. History required for offline replay, and where it is read

### What the runner consumes as "history"

All history is **inline in the case file** (`visible_view` `:174-190`): `state` (including
`experiments`, `evidence`, `claims`, `hypotheses`), `revisions`, `scheduler`,
`observation_packet`, `available_literature`, `known_conditions`, `insight_cards`. The memory
layer is rebuilt from these in-process via `cg.full_index(state, revisions, "replay", None,
scheduler)` (`:276-277`) — the revisions string is hard-coded `"replay"`, so historical route
identity is lost.

### Where it reads history from (paths)

- **Only the case JSON**: `load_case(path)` reads `path.read_text` (`:161-171`); `load_cases(dir)`
  globs `dir/*.json` (`:620-628`). No other file is read by the replay path.
- Shipped fixture directory: `examples/replay/adversarial/` (`test_research_replay.py:27`,
  `examples/replay/README.md`), consumed by `release_check.py:716` and
  `preset_router.py:2803` (both compute the path as `<component>/examples/replay/adversarial`).
- `smoke` **writes** a synthetic route into `<work>/.research-idea-pipeline/routes/A/`
  — `research-state.json` (via `cg.STATE_NAME`, `:1171`) and
  `cognition/model-revisions.jsonl` (via `cg.REVISIONS_NAME`, `:1195`) — then builds
  `cognition/index.json` and `cognition/context-brief.md` (`:1203`, `:1226`). It never reads a real
  project's history back into a replay case.

### Is it sufficient?

**No, for real offline replay.** Gaps:

1. No importer/exporter between a live route's canonical history and a case's `visible` section.
   Real paths such as `.research-idea-pipeline/routes/<R>/research-state.json`,
   `cognition/model-revisions.jsonl`, `cognition/index.json`, `cognition/insight-cards.jsonl`,
   `scheduler.json` (`cognition.py:67-73`, `:400`, `:1662-1669`) are never read by this module.
2. `scheduler` is an opaque pass-through (`:184`, `:276-277`); in 12 of 14 fixtures it is `null`
   (`adv1.json`), so scheduler-dependent behaviour is untested.
3. `insight_cards` is plumbed to `cg.project_insights` (`:324`) but the generated cases default it
   to `[]` (`:901`), so the insight tripwire is only exercised by hand-built cases.
4. No execution ledger / journal / per-round history is replayed; `smoke` only synthesises one round.
5. No `state_version`/`revisions` cutoff mechanism to guarantee the visible view predates
   `later_results` (see §2).

---

## 8. CLI subcommands + public function signatures

CLI parser: `build_parser` (`:1357-1370`); dispatch: `main` (`:1373-1442`).

| Subcommand | Flags | Purpose | Lines |
|---|---|---|---|
| `validate` | `--case <file>` (**`--dir` not accepted**) | load one case, print `{"id","valid"}`, exit 3 on diagnostics | `:1400-1410` |
| `show` | `--case <file>` | print the leak-stripped agent-visible view | `:1411-1417` |
| `run` | `--case <file>` `[--arm]` `[--runner]` | run one case under one arm, print the run result | `:1418-1425` |
| `suite` | `--dir <cases/>` `[--runs N]` `[--runner]` | run the full ablation ladder over a directory | `:1426-1433` |
| `ablate` | `--dir <cases/>` `[--runs N]` `[--runner]` | identical code path to `suite` (alias) | `:1426-1433` |
| `adversarial` | `--write <dir>` | generate the 14 cases as `advN.json` | `:1379-1392` |
| `smoke` | `--work <dir>` | end-to-end synthetic route run | `:1393-1399` |
| `--selftest` | — | in-process assertions, exit 0/1 | `:1375-1376` |

Note: `--arm` defaults to `full_cie` and is constrained to `ABLATION_ARMS` (`:1364`); `suite`/
`ablate` always run **all four** arms and ignore `--arm` (`:1431` passes `ABLATION_ARMS`).

Public functions (module-level, non-underscore):

| Signature | One-line purpose | Lines |
|---|---|---|
| `case_errors(case: Any) -> List[Diagnostic]` | validate a replay case, return `RP1`/`RP2`/`RP5` diagnostics | `:109` |
| `load_case(path: Path) -> Dict[str, Any]` | read + validate one case JSON or raise `CognitionError` | `:161` |
| `visible_view(case: Dict) -> Dict` | build the leak-stripped payload the runner may see | `:174` |
| `forbidden_strings(case: Dict) -> List[str]` | every ≥12-char hidden string that must not appear | `:202` |
| `leak_scan(case: Dict, visible: Any) -> List[str]` | return the forbidden strings actually present | `:223` |
| `cie_offline_runner(visible: Dict, arm: str) -> Dict` | deterministic model-free runner over shipped CIE machinery | `:232` |
| `load_runner(spec: Optional[str]) -> Callable[[Dict,str],Dict]` | resolve `module:function` or the built-in runner | `:367` |
| `decision_errors(decision: Any) -> List[Diagnostic]` | validate a `replay-decision@1`, enforce `RP3`/`RP5` | `:382` |
| `evaluate(case, decision, baseline_decision=None) -> Dict` | score one decision across seven dimensions | `:418` |
| `run_case(case, arm="full_cie", runner=None) -> Dict` | leak-check + run + evaluate one case under one arm | `:592` |
| `load_cases(directory: Path) -> List[Dict]` | load and naturally sort every `*.json` case in a directory | `:620` |
| `run_suite(cases, arms=ABLATION_ARMS, runs=1, runner=None) -> Dict` | run the ablation and emit the honest report | `:655` |
| `adversarial_cases() -> List[Dict]` | generate the 14 canonical adversarial cases | `:908` |
| `smoke(work: Path) -> Dict` | end-to-end state→prediction→revision→restart check | `:1162` |
| `by_id_case(results: Sequence[Dict], ident: str) -> Dict` | deterministic case-id lookup for tests | `:1254` |
| `selftest() -> int` | in-process self-check, returns an exit code | `:1259` |
| `build_parser() -> argparse.ArgumentParser` | construct the CLI parser | `:1357` |
| `main(argv: Optional[Sequence[str]] = None) -> int` | CLI entry point | `:1373` |

Module-level constants that are effectively public API: `SCHEMA_CASE`, `SCHEMA_DECISION`
(`:54-55`), `ABLATION_ARMS`, `ARM_CAPABILITIES` (`:63-70`), `METRIC_DIMENSIONS` (`:73-81`),
`HIDDEN_KEYS` (`:84-85`), `FORBIDDEN_BEHAVIOURS` (`:88-99`), `NOVELTY_LABELS` (`:102`),
`EXIT_OK/ERROR/HARD/ENV` (`:57-60`).

Private-but-tested: `_behaviour_present` is called directly by
`test_research_replay.py:394-396`.

---

## 9. Metrics / report structures that must remain backward compatible

External consumers lock these shapes:

- `release_check.py:713-755` (`step_discovery_replay`, wired at `:889`) asserts:
  `report["per_arm"][arm]["pass_rate"]`, `["dimensions"][dim]["mean"]`, `report["sufficient_sample"]`,
  `report["claim"]` must contain `不得宣称提升`, `report["undifferentiated_arms"]` truthy,
  `smoke["passed"]`, `smoke["canonical_untouched"]`, `len(adversarial_cases()) == 14`.
- `preset_router.py:2800-2825` reads `report["sample_size"]`,
  `report["per_arm"]["full_cie"]["dimensions"][dim]`, `report["undifferentiated_arms"]`,
  `report["limitations"]`, `report["results"]` (see gap in §10), and declares outputs
  `("per_dimension","sample_size","undifferentiated_arms","limitations")` (`preset_router.py:584`,
  mirrored in `presets/discovery-replay.md:82-87`).
- `test_research_replay.py` asserts the exact arm tuple (`:231-232`), the exact schema/keys of
  `evaluation` (`:138-149`), no aggregate keys (`:141-144`), `per_arm[*].observations`/`cases`
  (`:246-248`), and runner label `"external runner"` (`:300`).
- `test_preset_router.py:597-600` asserts the discovery-replay preset is leak-checked and emits no
  composite score.

Frozen contract surface (do not rename/remove or change types):

1. Case schema `research-idea-pipeline/replay-case@1` and its required keys (§1.1).
2. Decision schema `research-idea-pipeline/replay-decision@1`; required `arm`, `mechanism_terms`,
   `used_memory`; `arm` ∈ `ABLATION_ARMS`; `novelty_self_rating is None`.
3. Ablation schema `research-idea-pipeline/replay-ablation@1` with the exact key set at `:705-730`.
4. Smoke schema `research-idea-pipeline/replay-smoke@1` with `steps`/`passed`/`canonical_untouched`/
   `fixture_marking`.
5. The seven `METRIC_DIMENSIONS` names verbatim, each as `{value, basis, reason}` with `null` = unassessable.
6. The four `ABLATION_ARMS` ids verbatim and their `capabilities` tuples.
7. `violations` string vocabulary, including `decision_did_not_change` and
   `repeated_a_blocked_direction` (`:534-537`), and the ten `FORBIDDEN_BEHAVIOURS`.
8. CLI subcommand names/flags and exit codes `0/1/3/4`.
9. `run_case` result keys `{case_id, arm, decision, evaluation, diagnostics, leak_checked}`.

### Known backward-compat hazards (documentation vs code)

- `presets/discovery-replay.md:70` documents `validate --dir examples/replay/adversarial`, but the
  `validate` branch requires `--case` and returns `EXIT_ERROR` without it (`research_replay.py:1400-1403`).
  `preset_router.py:2819` also advertises this invalid command.
- `preset_router.py:2806-2808` builds `{"mean", "n"}` from `dimensions`, but `_dimension_means`
  emits `observable_cases`/`total_cases` (`:645-651`), so **`n` is always `None`**.
- `preset_router.py:2813-2814` reads `report.get("results")`, a key that does **not** exist at the
  top level of `run_suite`'s return (`:705-730`), so `leak_checked` is computed over an empty list
  and is vacuously `True`.
- The preset's declared output `per_dimension` (`preset_router.py:584`,
  `presets/discovery-replay.md:82`) does not literally exist in the report — the report emits
  `per_arm[arm]["dimensions"]`.

---

## 10. Where counterfactual evidence-class tagging (OBSERVED / REPLAY_SUPPORTED / NO_SUPPORT) could attach

Constraint from tests: any new key must avoid the substrings `total`, `overall`, `score`,
`weighted` (`test_research_replay.py:141-144` scans the whole serialized `evaluation`), must not
introduce `hidden`/`answer` into the visible view (`:95-98`, `:463-467`), and must not add a
required field to `decision_errors` in a way that breaks an existing runner whose decision lacks it
(`:389-391`). Additive, optional keys only.

Recommended attachment points, safest first:

1. **Inside each metric object** — extend `_metric` (`:414-415`) to emit
   `{"value","basis","reason","evidence_support"}` where `evidence_support ∈
   {"OBSERVED","REPLAY_SUPPORTED","NO_SUPPORT"}`. Every consumer reads `.value`/`.basis`/`.reason`
   only (`_dimension_means` `:641-643`; `preset_router.py:2806-2808`; tests `:146-150`), so an extra
   key is invisible. Natural mapping: `NO_SUPPORT` ⇔ today's `None` (keep `value: None` for
   compatibility and add the tag alongside); `OBSERVED` for dimensions read from the case's own
   canonical history (`mechanistic_understanding`, `memory_accumulation`); `REPLAY_SUPPORTED` for
   dimensions produced by re-running the pipeline (`prediction_quality`, `search_efficiency`,
   `stagnation_recovery`, `intervention_quality`).
2. **A sibling block on the evaluation result** — add `evaluation["evidence_support"]` (a dict
   keyed by the seven dimension names) next to `metrics`/`violations`/`passed` in the `evaluate`
   return (`:539-547`). `run_case`/`run_suite` pass it through untouched; no existing reader
   enumerates evaluation keys.
3. **On the decision** — `decision["evidence_class"]` already exists (`:254`, `:316`) carrying
   `pc.EVIDENCE_CLASSES` values. Add a **separate** key such as `decision["counterfactual_support"]`
   rather than overloading `evidence_class` (which is produced by `pc.assess_experiment` and is
   semantically about the observation packet, `prediction_compare.py:1254-1265`). `decision_errors`
   tolerates unknown keys (`:382-398`), but the tag must not be *required* or a pluggable external
   runner (`test_research_replay.py:289-302`) starts failing `RP3`.
4. **Per-arm aggregation** — add `per_arm[arm]["evidence_support_counts"]` (avoid `score`/`total`)
   inside the `per_arm[arm]` block (`:670-681`), computed from (1) or (2). `release_check.py` and
   `preset_router.py` read only named keys, so this is additive.
5. **Case-level declaration** — optionally add `evaluation_only.evidence_support` to the case
   schema (`:144-157`) so the expected support class is authored with the ground truth. `case_errors`
   would need a new optional validation branch; do **not** put it in `hidden.answer`, because every
   `answer` string ≥12 chars becomes a leak marker (`:209-211`) and every `answer` key feeds
   scoring.

**Do not** put the tag on the `visible` view: that would risk the leak scan and would re-introduce
the "runner sees the evaluation" failure mode the module exists to prevent (`:9-13`).

### Top gaps (ranked)

1. No real-history ingestion path — replay is fixture-only (`:161-171`, `:620-628`); no route
   `research-state.json` / `model-revisions.jsonl` / `scheduler.json` importer.
2. No policy/selection-effect measurement — only outcome correlation and proxies (`:232-339`,
   `:474-484`); `memory_prediction` ≡ `full_cie` (`:696-701`, `discovery-replay.md:99-100`).
3. No `NO_SUPPORT` / counterfactual evidence-class concept anywhere; `None` + free-text `reason`
   is the only unassessability signal (`:434-436`, `:545-546`).
4. Leak guard is exact-substring and ≥12 chars only; no paraphrase/numeric/temporal-consistency
   check (`:202-225`).
5. `identification_controls` is never populated by the built-in runner (`:259`), so
   `intervention_quality` silently floors at 0.0 for every case carrying `required_controls`
   (`:456-458`, `:515-519`).
6. No execution-history awareness: proposed ≠ executed; nothing checks whether an action ever
   ran (`:351-364`, `:492`).
7. Three concrete doc/wiring defects: `validate --dir` advertised but unsupported
   (`presets/discovery-replay.md:70`, `preset_router.py:2819`); `n` always `None`
   (`preset_router.py:2806-2808` vs `:645-651`); `leak_checked` vacuously `True`
   (`preset_router.py:2813-2814` vs `:705-730`).
8. `revisions` are lossily reprojected with a hard-coded route name `"replay"` (`:276-277`);
   historical route identity cannot round-trip.
