# I — Consistency & Contract Audit of the Skill-RSI layer

**Revision under audit: commit `8887a48`** (range `d13ecd4..8887a48`), i.e. the committed
"shipped" state. Every `file:line` below is a **HEAD** line, verified with
`git show HEAD:research-idea-pipeline/<path>`. Where a file is byte-identical at HEAD and in
the working tree (e.g. `preset_router.py`, `research_replay.py`, `rsi_ablation.py`,
`policy_transfer.py`) the line number is valid for both.

Scope: `research-idea-pipeline/` (COMP) at repo `skill-rsi-dev`.
Method: grep/read + executed verification. **No file was modified except this report.**
All shell commands below are run with **cwd = the component directory**
(`…/skill-rsi-dev/research-idea-pipeline`).

> ### ⚠ Revision note — the working tree is NOT HEAD
> During this audit another writer applied **uncommitted** edits to the working tree
> (`git diff | md5sum` = `42e6f967ea2054ca09bf073b15d85adf`). Those edits *already fix* several
> findings below, so this report must be read against `8887a48`, not the dirty working tree.
> Working-tree edits observed:
> - `SKILL.md`, `presets/memory-consolidation.md`, `presets/strategy-evolution.md`,
>   `references/skill-rsi-policy.md` → fix **R-1**, **R-2**, **R-3** (PT range → `PT1`—`PT11`;
>   DT7/DT8 + full PT1–PT11 enumeration added).
> - `scripts/decision_trajectory.py` → deletes the dead `TRAJECTORY_LOCK` (**R-16**) and adds a
>   runtime `guard_store_path` gate.
> - `scripts/policy_evolution.py` → wires `source_freeze.guard_errors` into `candidate_errors`
>   (**R-12**) and changes `applicability` handling.
> - `scripts/source_freeze.py` → fail-closed edits.
>
> Findings R-5, R-6, R-7, R-8, R-9, R-10, R-13, R-14, R-15 are **still present in the working
> tree** (their files are untouched by the concurrent edit).

---

## 1. Rule-code parity (`DT*`, `PE*`, `PT*`)

### 1.1 Codes actually emitted at HEAD

```sh
git show HEAD:research-idea-pipeline/scripts/decision_trajectory.py | grep -oE '"(DT)[0-9]+"' | sort -u
git show HEAD:research-idea-pipeline/scripts/policy_evolution.py     | grep -oE '"(PE)[0-9]+"' | sort -u
git show HEAD:research-idea-pipeline/scripts/policy_transfer.py      | grep -oE '"(PT)[0-9]+"' | sort -u
```

| Namespace | Implemented at HEAD | Count |
|---|---|---|
| DT | `DT0 DT1 DT2 DT3 DT4 DT5 DT6 DT7 DT8 DT9 DT10` | 11 |
| PE | `PE1 … PE14` | 14 |
| PT | `PT1 … PT11` | 11 |

Implementation sites at HEAD:
- `DT7` trajectory/policy store may not be named as an evidence source —
  `scripts/decision_trajectory.py:522` and `:639`.
- `DT8` no duplicate dispatch under a renamed trajectory id —
  `scripts/decision_trajectory.py:542`.
- `PT11` fail-closed expiry on missing/非法 `state_version` / `max_state_version_gap` —
  `scripts/policy_transfer.py:1502,1507,1513,1518`; wired into the `expired` CLI at
  `scripts/policy_transfer.py:1770`.
- `PT11` was introduced by the later fix commit:
  `git log --oneline -S'PT11' d13ecd4..8887a48 -- research-idea-pipeline/scripts/policy_transfer.py`
  → `2506405`.

### 1.2 Codes advertised at HEAD

```sh
for f in SKILL.md references/skill-rsi-policy.md presets/strategy-evolution.md \
         presets/research-loop.md presets/stagnation-breaker.md presets/memory-consolidation.md; do
  echo "== $f"; git show HEAD:research-idea-pipeline/$f | grep -nE '(DT|PE|PT)[0-9]'
done
git show HEAD:research-idea-pipeline/README.md | grep -nE '(DT|PE|PT)[0-9]'   # no output
```

| Document (HEAD) | DT | PE | PT |
|---|---|---|---|
| `SKILL.md:1008` | `DT0`—`DT10` ✔ | — | — |
| `SKILL.md:1009` | — | `PE1`—`PE14` ✔ | — |
| `SKILL.md:1010` | — | — | **`PT1`—`PT10` ✘** |
| `references/skill-rsi-policy.md:55-57` | `DT0..DT6, DT9, DT10` — **DT7/DT8 missing** | — | — |
| `references/skill-rsi-policy.md:106-109` | — | `PE1..PE14` ✔ | — |
| `references/skill-rsi-policy.md:157-162` (§8) | — | — | **zero `PTn` enumerated** (`grep -cE 'PT[0-9]'` = 0) |
| `presets/strategy-evolution.md:58-59` | `DT0`—`DT10` ✔ | `PE1`—`PE14` ✔ | **`PT1`—`PT10` ✘** |
| `presets/research-loop.md:63` | `DT0`—`DT10` ✔ | — | — |
| `presets/stagnation-breaker.md:56` | `DT0`—`DT10` ✔ | — | — |
| `presets/memory-consolidation.md:56` | — | — | **`PT1`—`PT10` ✘** |
| `README.md` | none | none | none |

### 1.3 Findings — rule codes

**R-1 (MEDIUM) Stale `PT1`—`PT10` range in three shipped docs at HEAD.**
`PT11` is emitted and wired, but `SKILL.md:1010`, `presets/strategy-evolution.md:59` and
`presets/memory-consolidation.md:56` advertise only `PT1`—`PT10`.
Verify: `git show HEAD:research-idea-pipeline/SKILL.md | grep -n 'PT1'` and
`git show HEAD:research-idea-pipeline/scripts/policy_transfer.py | grep -n '"PT11"'`.

**R-2 (MEDIUM) Implemented-but-undocumented `DT7` / `DT8` at HEAD.**
`references/skill-rsi-policy.md:55-57` enumerates the DT rules and omits `DT7` and `DT8`,
although both are implemented (`scripts/decision_trajectory.py:522,542,639`). The force-fix
commit `2506405` states "the advertised DT7/DT8 rules are implemented"; the reference
enumeration was never extended.
Verify: `git show HEAD:research-idea-pipeline/references/skill-rsi-policy.md | grep -n 'DT7\|DT8'`
→ no match.

**R-3 (MEDIUM) No `PTn` rule is documented in the reference at HEAD.**
`references/skill-rsi-policy.md` §8 (`:157-162`) describes the transfer gate in prose only;
`grep -cE 'PT[0-9]'` on that file = 0, while `PT1`…`PT11` are all emitted. The namespace is
mentioned only in `SKILL.md`/two presets, and with the wrong range.
Verify: `git show HEAD:research-idea-pipeline/references/skill-rsi-policy.md | grep -cE 'PT[0-9]'`.

**R-4 (INFO) `README.md` names no RSI rule code** — nothing stale, but zero coverage.

---

## 2. Output-contract parity

### 2.1 `research-loop` §7 vs `_handle_research_loop`

Doc: `presets/research-loop.md:104-112`. Code: `scripts/preset_router.py:2262-2301`; registry
`outputs` at `scripts/preset_router.py:282`. This file is unchanged between HEAD and the
working tree.

Observed payload (executed at HEAD-equivalent code):

```sh
cd scripts && python3 - <<'PY'
import tempfile, pathlib, io, contextlib, preset_router as pr
with tempfile.TemporaryDirectory() as t:
    sp = pr._fixture(pathlib.Path(t)/"research-loop")
    with contextlib.redirect_stdout(io.StringIO()):
        p,_,_ = pr.run_preset("research-loop", sp, apply=True)
print(sorted(p.keys())); print(sorted((p["observed"] or {}).keys()))
print(sorted((p["decision"] or {}).keys()))
PY
```

| §7 claimed field | Actual at HEAD |
|---|---|
| `loop_state` | **absent everywhere** (only `observed.loop` = stage-name list, `observed.current`) |
| `next_action` | present (top-level) ✔ |
| `dispatched_action` / `strategy_changed_dispatch` | present but nested under `decision`, not top-level |
| `evidence_delta` | **absent everywhere** |
| `scientific_delta` / `decision_delta` / `policy_delta` | present, nested under `decision`; `policy_delta.level` set ✔ |
| `changed_decision` | present (top-level + `decision`) ✔ |
| `hold_reason` | present (top-level) ✔ |
| unified fields incl. `canonical_untouched` | all present ✔ (`:3093`) |

**R-5 (MEDIUM) `research-loop` §7 claims `loop_state` and `evidence_delta`; neither exists.**
Both are also declared in the shipped registry contract at `scripts/preset_router.py:282`.
(The two lines pre-date the layer — they are context lines in
`git diff d13ecd4 8887a48 -- research-idea-pipeline/presets/research-loop.md` — but they are
wrong at HEAD.)
Verify: `grep -n 'loop_state\|evidence_delta' scripts/preset_router.py` → only line 282.

### 2.2 `strategy-evolution` §7 vs `_handle_strategy_evolution`

Doc: `presets/strategy-evolution.md:106-112`. Code: `scripts/preset_router.py:2921-2943`;
registry `outputs` at `:544`.

| §7 claimed field | Actual at HEAD |
|---|---|
| `priors_before` | **absent**; nearest real field `observed.candidates_before` |
| `priors_after` | **absent**; nearest `observed.candidates_after` |
| `recommendation_before` | **absent**; nearest `observed.chosen_without_memory` |
| `recommendation_after` | **absent**; nearest `observed.chosen` / `decision.dispatch` |
| `changed_decision` | present ✔ |
| unified fields | all present ✔ |

**R-6 (MEDIUM) `strategy-evolution` §7 claims four `priors_*`/`recommendation_*` fields that do
not exist.** The same four names are declared at `scripts/preset_router.py:544`.
Verify: `grep -n 'priors_before\|recommendation_before' scripts/preset_router.py` → only 544.

Extra fields returned by both handlers (`assurance_*`, `pending_r10`, `decision_gate`,
`source_integrity`, …) are unlisted in §7 but that is a superset, not a violation.

---

## 3. Write-set parity (`presets/*.md` §8 vs handler `writes`)

`_result` seeds `writes: []` (`scripts/preset_router.py:1657`) and each handler fills it.

| Preset | Handler writes (HEAD code) | §8 allowed list (HEAD doc) | Verdict |
|---|---|---|---|
| `research-loop` | `cognition/ 投影…` (`:2207`) + `decision-trajectory.jsonl` (`:2241`) + `scheduler.json` (`:2255`) | `research-state.json`, `cognition/ 投影`, `执行账本` (`presets/research-loop.md:116-119`) | **2 unlisted writes** |
| `strategy-evolution` | `cognition/model-revisions.jsonl` (`:2896`) + `scheduler.json` (`:2907`) | `策略修订`, `policy/`, `decision-trajectory.jsonl`, `source-integrity.jsonl` (`presets/strategy-evolution.md:116-120`) | `model-revisions` ≈ 策略修订; **`scheduler.json` unlisted**; `decision-trajectory` over-allowed |
| `stagnation-breaker` | `[]` always (`:2696`) | `诊断记录`, `scheduler 只读` | OK |
| `memory-consolidation` | `cognition/index.json`, `cognition/context-brief.md` (`:2824`) | same two (`presets/memory-consolidation.md:97-99`) | OK |

**R-7 (HIGH — contract violation) `research-loop` §8 omits the two new control-plane writes.**
The apply path writes `<route>/decision-trajectory.jsonl`
(`dt.TRAJECTORY_NAME = "decision-trajectory.jsonl"`) and `<route>/scheduler.json`
(`cg.SCHEDULER_NAME = "scheduler.json"`) at `scripts/preset_router.py:2241` and `:2255`, but
`presets/research-loop.md:116-119` lists neither. §8 line 121 mentions
`scheduler.strategy_decisions[]` only as a telemetry *field*, not the `scheduler.json` file
write, and never mentions the trajectory write. The shipped registry `writes` tuple
(`scripts/preset_router.py:279`) is stale in the same way. `research-loop.md` was **not**
touched by the layer at all (`git diff d13ecd4 8887a48 -- presets/research-loop.md` shows only
§5/§7 changes), so the write contract silently fell behind the new handler behaviour.
Verify:
```sh
grep -n 'writes' scripts/preset_router.py | sed -n '1,40p'          # 2207, 2241, 2255
git show HEAD:research-idea-pipeline/presets/research-loop.md | grep -n 'decision-trajectory\|scheduler.json'
```

**R-8 (MEDIUM) `strategy-evolution` §8 under-lists `scheduler.json`.**
The handler rewrites `<route>/scheduler.json` (`scripts/preset_router.py:2904-2907`); §8's
allowed list (`:116-120`) names only `policy/`, `decision-trajectory.jsonl`,
`source-integrity.jsonl` and the revisions log. Conversely, the strategy-evolution handler
never writes `decision-trajectory.jsonl`, although §8 now allows it (over-broad entry).

---

## 4. Command parity

### 4.1 §6 step tables vs returned `steps`

`test_preset_router.test_every_documented_command_is_a_command_the_code_runs`
(`scripts/test_preset_router.py:252-263`) asserts only **code → doc** ("every command the code
runs appears somewhere in the protocol text"); it does **not** assert equality or doc→code.

- `research-loop`: doc 9 rows (`presets/research-loop.md:84-94`) = code 9 steps
  (`scripts/preset_router.py:2179-2189`) ✔
- `strategy-evolution`: doc 5 rows (`presets/strategy-evolution.md:90-96`) = code 5 steps
  (`:2911-2920`) ✔
- `memory-consolidation`: doc 3 rows (`presets/memory-consolidation.md:74-78`) = code 3 steps
  (`:2834-2839`) ✔
- `stagnation-breaker`: doc 1 row (`presets/stagnation-breaker.md:75-79`); code has **two**
  paths — `NO_CHANGE` returns 1 step, `OK` returns 3 (`scripts/preset_router.py:2679-2695`).

**R-9 (MEDIUM) `stagnation-breaker` §6 documents only the `NO_CHANGE` path.**
Two commands from the `OK` path appear nowhere in the protocol file:
`python3 scripts/prediction_compare.py compete --state <state> --competition <CP>` and
`python3 scripts/prediction_compare.py switch --state <state> --scheduler <scheduler>`.
The doc-vs-code test only passes because its fixture never triggers stagnation — a latent test
hole.
Verify:
```sh
git show HEAD:research-idea-pipeline/presets/stagnation-breaker.md | grep -n 'compete\|--scheduler'  # no match
sed -n '2690,2695p' scripts/preset_router.py
```

### 4.2 New CLI subcommands (documented vs real)

Executed `python3 scripts/<s>.py <sub> --help` for every documented command. **Every
documented subcommand exists.**

| Script | Documented (reference / SKILL) | Actual choices | Verdict |
|---|---|---|---|
| `decision_trajectory.py` | `open/outcome/learning/show/list/validate` + `--selftest` (`references/skill-rsi-policy.md:59`) | `{open,outcome,learning,show,list,validate}` + `--selftest` option | ✔ |
| `policy_evolution.py` | `freeze-rules/propose/list/show/transition/evaluate/rollback/state/advice/validate` | identical | ✔ |
| `policy_transfer.py` | `layers/signature/transfer/expired/compress` | `{layers,signature,transfer,expired,compress,selftest}` | **undocumented `selftest`** |
| `research_replay.py` | `ablate --rsi`, `support --trajectory`, `coverage --trajectory`, `validate --dir` (`:84`) | all exist; plus pre-existing `show/run/suite/adversarial/smoke` | ✔ |
| `rsi_ablation.py` | `run/overhead/levels/report` | identical | ✔ |
| `source_freeze.py` | `freeze/verify/guard/plan/selftest` | identical | ✔ |

**R-10 (LOW) Undocumented subcommand `policy_transfer.py selftest`.**
Unlike the other new modules, `policy_transfer.py` exposes `selftest` as a positional
*subcommand* (not a `--selftest` flag), and no shipped doc lists it.
Verify: `python3 scripts/policy_transfer.py --help` →
`{layers,signature,transfer,expired,compress,selftest}`.

Documented example commands in `README.md:421-423` and `presets/strategy-evolution.md:65-72`
were spot-checked: `examples/replay/adversarial` exists and `research_replay.py ablate` accepts
`--dir --rsi --runs`; all `policy_evolution` lifecycle flags exist.

---

## 5. `.dev/` runtime independence

```sh
grep -rn '\.dev' scripts/*.py references/ presets/ templates/ SKILL.md | grep -v __pycache__
```

Every hit is one of: a test file; a comment; `source_freeze`'s deliberate exclusion list
(`scripts/source_freeze.py:102,109,128`); or `release_check.py`'s `.dev/`-dependency guard
(`:777-822`). **No shipped script, preset, reference or template reads from `.dev/` at
runtime.** The invariant holds.

**R-11 (LOW) Shipped comment references a branch-local path.**
`scripts/release_check.py:910` says "See `.dev/decisions.md` D5." `.dev/` is branch-local and
not shipped, so a shipped script pointing maintainers at it is a documentation-hygiene issue,
not a runtime dependency.
Verify: `grep -n '\.dev' scripts/release_check.py` (line 910).

---

## 6. Frozen invariants — all verified

```sh
git diff --stat d13ecd4 8887a48 -- research-idea-pipeline/scripts/state_check.py \
  research-idea-pipeline/templates/ research-idea-pipeline/preset-registry.json
# empty → unchanged
```

- **(a) `research-state.json` top-level keys unchanged.**
  `templates/research-state.template.json` is untouched by the range; keys remain
  `_schema, state_version, _usage, contract, claims, evidence, assumptions, hypotheses,
  experiments, literature, failures, uncertainties, assurance, repairs, narrative_view,
  reviews, decision, _outcome_usage, _execution_usage`. ✔
- **(b) Eight canonical object classes unchanged.** `scripts/state_check.py:143-152`
  `OBJECT_KEYS = claims/evidence/assumptions/hypotheses/experiments/literature/failures/uncertainties`;
  the file is byte-identical across the range. ✔
- **(c) `preset-registry.json` declares exactly 16 presets**
  (`python3 -c "import json;print(len(json.load(open('preset-registry.json'))['presets']))"` → `16`)
  and `SKILL.md:26` still has `version: "1.0.0"`. ✔
- **(d) No new canonical field added by the new code.** The new modules write only
  `<route>/decision-trajectory.jsonl`, `<route>/policy/` and `<route>/source-integrity.jsonl`;
  none writes `research-state.json`. `research_replay.smoke` and the selftests build
  *synthetic* fixtures only (`scripts/research_replay.py:1660` is the smoke fixture).
  Verify: `grep -n 'state_path.write_text' scripts/decision_trajectory.py scripts/policy_evolution.py scripts/policy_transfer.py scripts/rsi_ablation.py scripts/source_freeze.py` → no match. ✔
- **(e) `state_check.py` inputs/outputs unchanged.** The file is absent from the range diff;
  `OBJECT_KEYS`, `EXTRA_KEYS`, `CHECKED_KEYS` (`:143-155`) and the S1–S7/V1–V24 check tables
  are untouched. ✔

---

## 7. Schema-id stability

```sh
git diff d13ecd4 8887a48 -- research-idea-pipeline/scripts/ \
  | grep -E '^[-+].*research-idea-pipeline/[A-Za-z0-9._-]+@[0-9]+' | sort -u
```

The diff contains **no removed (`-`) schema-id line**, so no existing id was replaced or
re-versioned. New `research-idea-pipeline/<name>@1` ids introduced by the layer:

| New schema id | Introduced in |
|---|---|
| `decision-trajectory@1` | `scripts/decision_trajectory.py:48` |
| `policy-candidate@1` | `scripts/policy_evolution.py:55` |
| `policy-transition@1` | `scripts/policy_evolution.py:56` |
| `policy-rollback@1` | `scripts/policy_evolution.py:57` |
| `policy-evaluation-rules@1` | `scripts/policy_evolution.py:58` |
| `policy-state@1` | `scripts/policy_evolution.py:602` |
| `policy-transfer@1` | `scripts/policy_transfer.py:60` |
| `source-freeze@1` | `scripts/source_freeze.py:84` |
| `source-integrity-event@1` | `scripts/source_freeze.py:85` |
| `source-freeze-deployment@1` | `scripts/source_freeze.py:825` |
| `replay-ablation@1` | `scripts/research_replay.py:1180`, `scripts/policy_evolution.py:1268` |
| `replay-coverage@1` | `scripts/research_replay.py:992` |
| `skill-rsi-ablation@1` | `scripts/rsi_ablation.py:167` |
| `skill-rsi-overhead@1` | `scripts/rsi_ablation.py:260` |
| `skill-rsi-levels@1` | `scripts/rsi_ablation.py:309` |
| `skill-rsi-report@1` | `scripts/rsi_ablation.py:321` |

The new code reuses the existing `research-idea-pipeline/research-state@1` only inside
synthetic fixture builders (`scripts/decision_trajectory.py:981`,
`scripts/policy_transfer.py:1805`) — no new state schema version.

**No schema-id violation.** (Pre-existing, out of scope: both
`structural-equivalence-audit@2` and `@3` exist, and `prediction-observation@9` looks odd —
neither is touched by this layer.)

---

## 8. Dead / decorative code introduced by the new layer

All call counts below are for **HEAD**.

| Symbol | Defined (HEAD) | Wired into production at HEAD? | Callers | Verdict |
|---|---|---|---|---|
| `decision_trajectory.TRAJECTORY_LOCK` | `scripts/decision_trajectory.py:56` | **No — never referenced anywhere** | none | **dead constant** |
| `source_freeze.guard_errors` | `scripts/source_freeze.py:576` | **No** | only module selftest `:1006-1015` + `test_source_freeze.py:185-197` | **dead enforcement copy** |
| `source_freeze.ALLOWED_WRITE_SCOPES` | `scripts/source_freeze.py:122` | **Yes** | `guard_write` at `:560` | wired ✔ |
| `decision_trajectory.store_lock` | `scripts/decision_trajectory.py:179` | **Yes** | exclusive `flock` at `:197-198` | wired ✔ |
| `policy_evolution.write_snapshot` | `scripts/policy_evolution.py:635` | **No** | only `test_policy_evolution.py:373` | **test-only** (kills `state_snapshot_path` `:199` too) |
| `rsi_ablation.level_report(l3_evidence=…)` | `scripts/rsi_ablation.py:284`, param used `:300` | **No caller passes it** | prod callers `:324,359,398` omit it; parser `:340-343` has no flag | **test-only** (`test_rsi_ablation.py:142`) |
| `research_replay.cases_from_trajectory` | `scripts/research_replay.py:1005` | **No** | only `test_counterfactual_replay.py:224-228`; CLI `support`/`coverage` use `support_map_from_trajectory` (`:946`) / `coverage_report` (`:980`) | **test-only** |

**R-12 (MEDIUM) `source_freeze.guard_errors` is a dead enforcement path at HEAD.**
It implements an adversarial candidate scan (protected targets, shell metacharacters,
`import os`, `../`) and the module comment at `:132` advertises the wordlist, but no production
code calls it. The executable-content rule that actually runs is
`policy_evolution._executable_errors` (`PE6`, `scripts/policy_evolution.py:297-308`). Only the
selftest exercises `guard_errors`, which gives the false impression of a second enforcement
layer. (The uncommitted working-tree edit now calls it from
`policy_evolution.candidate_errors`, which would fix this.)
Verify: `git grep -n 'guard_errors' HEAD -- scripts/` → definition +
selftest only.

**R-13 (MEDIUM) `policy_evolution.write_snapshot` / `state_snapshot_path` are never called in
production at HEAD.** No shipped doc claims a snapshot file, so this is dead code rather than a
broken claim; the policy log is folded on demand by `rebuild_state`.
Verify: `git grep -n 'write_snapshot\|state_snapshot_path' HEAD -- scripts/`.

**R-14 (LOW) `rsi_ablation.level_report(l3_evidence=…)` is unreachable from the CLI.**
The module documents "never claims L3 without such a run", but the only way to supply L3
evidence is the Python parameter and the parser exposes no flag. The default report is honest
(`L3 = NOT_VERIFIED`), so the mechanism is decorative, not misleading.
Verify: `python3 scripts/rsi_ablation.py --help` (no L3/evidence flag).

**R-15 (LOW) `research_replay.cases_from_trajectory` is test-only at HEAD.** The shipped
`support --trajectory` / `coverage --trajectory` commands use other functions.
Verify: `git grep -n 'cases_from_trajectory' HEAD -- scripts/`.

**R-16 (LOW) `decision_trajectory.TRAJECTORY_LOCK` is a dead constant at HEAD.**
Defined at `scripts/decision_trajectory.py:56`, never referenced; the real lock path is
`store_lock` (`:179`). The uncommitted working-tree edit deletes it.
Verify: `git grep -n 'TRAJECTORY_LOCK' HEAD -- scripts/` → single
definition line.

---

## 9. Summary of confirmed HEAD inconsistencies (by severity)

| # | Severity | Finding | Doc/contract (HEAD) | Impl (HEAD) |
|---|---|---|---|---|
| R-7 | **HIGH** | `research-loop` §8 write-set omits `decision-trajectory.jsonl` and `scheduler.json`, both written on the apply path | `presets/research-loop.md:116-119`; registry `scripts/preset_router.py:279` | `:2207,2241,2255` |
| R-12 | MEDIUM | `source_freeze.guard_errors` wordlist advertised but never wired | `scripts/source_freeze.py:132` comment | only `:1006-1015` + unit test |
| R-1 | MEDIUM | Stale `PT1`—`PT10` range (PT11 exists) | `SKILL.md:1010`, `presets/strategy-evolution.md:59`, `presets/memory-consolidation.md:56` | `scripts/policy_transfer.py:1502+` |
| R-5 | MEDIUM | `research-loop` §7 claims `loop_state` + `evidence_delta`, emits neither | `presets/research-loop.md:105,108`; registry `:282` | handler `:2262-2301` |
| R-6 | MEDIUM | `strategy-evolution` §7 claims `priors_before/after` + `recommendation_before/after`, emits none | `presets/strategy-evolution.md:107-110`; registry `:544` | handler `:2921-2943` |
| R-9 | MEDIUM | `stagnation-breaker` §6 documents only the `NO_CHANGE` path; the `OK` path's `compete` + `--scheduler` steps are undocumented | `presets/stagnation-breaker.md:75-79` | `scripts/preset_router.py:2690-2695` |
| R-2 | MEDIUM | `DT7`, `DT8` implemented but missing from the DT enumeration | `references/skill-rsi-policy.md:55-57` | `scripts/decision_trajectory.py:522,542,639` |
| R-3 | MEDIUM | No `PTn` rule enumerated in the reference | `references/skill-rsi-policy.md:157-162` | `scripts/policy_transfer.py` PT1–PT11 |
| R-8 | MEDIUM | `strategy-evolution` §8 under-lists `scheduler.json` (and over-allows `decision-trajectory.jsonl`) | `presets/strategy-evolution.md:116-120` | `scripts/preset_router.py:2904-2907` |
| R-13 | MEDIUM | `policy_evolution.write_snapshot` / `state_snapshot_path` never used in production | — | `scripts/policy_evolution.py:199,635` |
| R-10 | LOW | Undocumented subcommand `policy_transfer.py selftest` | — | `scripts/policy_transfer.py` choices |
| R-14 | LOW | `level_report(l3_evidence=…)` not reachable from CLI | — | `scripts/rsi_ablation.py:284,340-343` |
| R-15 | LOW | `cases_from_trajectory` test-only | — | `scripts/research_replay.py:1005` |
| R-16 | LOW | `TRAJECTORY_LOCK` dead constant | — | `scripts/decision_trajectory.py:56` |
| R-11 | LOW | Shipped comment points at branch-local `.dev/decisions.md` | — | `scripts/release_check.py:910` |
| R-4 | INFO | `README.md` covers no RSI rule codes | `README.md` | — |

### Verified clean at HEAD
- `.dev/` runtime independence (§5) — no shipped runtime read.
- Frozen invariants (a)–(e) (§6) — all unchanged.
- Schema-id stability (§7) — no replacement/re-versioning; only new `@1` ids.
- All documented CLI subcommands exist (§4.2).
- `ALLOWED_WRITE_SCOPES` and the trajectory `store_lock` are genuinely wired (§8).
- All 9 RSI-related unit suites pass at HEAD, which is why the doc mismatches above are
  uncaught: the parity test asserts only code→doc and only that `outputs` is non-empty.

```sh
cd scripts && for t in test_preset_router test_decision_trajectory test_policy_evolution \
  test_policy_transfer test_research_replay test_rsi_ablation test_source_freeze \
  test_counterfactual_replay test_skill_rsi_e2e; do python3 -m unittest $t; done   # all OK
```
