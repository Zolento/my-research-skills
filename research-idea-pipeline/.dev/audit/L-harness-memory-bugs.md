# L — adversarial review: harness / memory / replay (Skill-RSI)

Target: `research-idea-pipeline/` at `d23cbf1` (range `d13ecd4..d23cbf1`).
Scope: `scripts/rsi_ablation.py`, `scripts/release_check.py` (`step_skill_rsi` + modified
`step_release_metadata`/`STEPS`), `scripts/strategy_memory.py` (`advice=`, `prefer_rank`,
`_order_actions`, `action_affinity`), `scripts/research_replay.py` (new public API).

Review-only: no repository file was modified. All reproductions ran against an immutable
`git archive d23cbf1` snapshot in `/tmp/rsi_head` and copies in `/tmp/rsi_dev*`.

> Process note: the live checkout advanced past `d23cbf1` while this review ran (parallel
> agents committing `790c816`, `2365069`, `751454d`, `7ddde7f`). At capture time
> `git diff d23cbf1..HEAD -- <scope files>` was empty, so every line number below is valid for
> `d23cbf1`; a parallel agent has since started editing `research_replay.py` in the working
> tree, which is unrelated to this report. The live tree also carried uncommitted edits to
> `source_freeze.py` / `test_source_freeze.py` / `policy_transfer.py`, which made one
> full-suite run flaky. Counts therefore come from the clean `d23cbf1` snapshot.

## Counts (clean `d23cbf1` checkout, `/tmp/rsi_head`)

| Command | Result |
|---|---|
| `python3 -m unittest discover -s scripts -p 'test_*.py'` | `Ran 1680 tests ... OK (skipped=4)`, exit 0 |
| `python3 scripts/release_check.py` | last line `PASS`, exit 0 |
| `python3 scripts/rsi_ablation.py --selftest` | `selftest OK`, exit 0 |

Live tree at review end (concurrently edited, not the review target):
`Ran 1695 tests ... FAILED (failures=1)` for one instant (a `policy_transfer` test the
parallel agent was editing), then `release_check.py` → `PASS` with `Ran 1695 tests ... OK
(skipped=3)` while the same manual discover was failing — i.e. the live failure is an
editing race, not a defect of the reviewed commit.

---

## CONFIRMED

### L1 — the `.dev/` dependency scanner misses real dependencies (fail-open in the release gate)
Severity: High (the gate claims "no `.dev/` runtime dependency" while allowing it)
File: `scripts/release_check.py:805-806` (patterns), `:813-816` (selftest/fixture skip), `:819-820`

What is wrong: the regex only matches `Path(...)`, `x / ".dev"`, `".dev/…"` and
`open("….dev")`. It does not match `os.path.join(root, ".dev", …)`, a `DEV = ".dev"`
variable used later, a nested `scripts/**` module, or `.dev` reached through any alias.
Worse, `current` is only reset on a line starting with `def `/`class `, and any function whose
name contains `selftest`/`fixture` suppresses the scan until the next top-level def; module
level statements placed after the last `def selftest` are therefore never scanned.

Reproduction (copy in /tmp, never the repo):
```
cp -r /tmp/rsi_head/research-idea-pipeline /tmp/rsi_dev
printf '\nimport os\ndef _x(r):\n    return os.path.join(r, ".dev", "cache", "x.json")\n' >> /tmp/rsi_dev/scripts/cognition.py
cd /tmp/rsi_dev && python3 -c "import sys;sys.path.insert(0,'scripts');import release_check as rc;print(rc.step_skill_rsi())"
```
OBSERVED:
```
(True, '5 selftests + 7 RSI suites green; ... no .dev/ runtime dependency; ...')
```
A `Path(...) / ".dev"` form **is** caught (`(False, 'shipped scripts depend on .dev/: cognition.py:2551')`),
so the miss is specifically pattern coverage. A function named `load_fixture_config` containing
`Path(root) / ".dev" / "config.json"` also passes (`True`), as does a module-level
`_LEAKED = Path(...) / ".dev" / "x.json"` appended after `selftest` in `rsi_ablation.py`.

Expected: every actual `.dev` path construction is detected, and the skip must not leak past
the end of a selftest/fixture helper.
Regression: new (`step_skill_rsi` added in this range).

### L2 — a `.dev/` scanner false positive rejects a legitimate filename
Severity: Low
File: `scripts/release_check.py:805` (`Path\([^)]*\.dev`)

What is wrong: `Path(` followed by any character then `.dev` matches unrelated filenames.

Reproduction:
```
printf '\nfrom pathlib import Path\ndef load_local_config():\n    return Path("config.dev.json")\n' >> /tmp/rsi_dev5/scripts/cognition.py
```
OBSERVED: `(False, 'shipped scripts depend on .dev/: cognition.py:2551')` for a file that has
no `.dev/` directory dependency.
Expected: only a path *segment* equal to `.dev` counts.

### L3 — `_order_actions` lets an operator/island-aligned action beat an explicit `prefer_action`
Severity: Medium
File: `scripts/strategy_memory.py:1023-1026` (sort key), `:901-907` (`prefer_rank`)

What is wrong: only the `prefer_actions` route sets `prefer_rank`; the operator/island route
returns `aligned=True, prefer_rank=None`, and the key falls back to `declared_order`. So an
explicit `same_tier_preference`/`same_tier_order` can be silently overridden by a
merely operator-aligned action declared earlier — contradicting the comment "an explicit
requested rank wins over declaration order".

Reproduction:
```
python3 -c "import sys;sys.path.insert(0,'scripts');import strategy_memory as sm
state={'hypotheses':[{'id':'H1','operator':'reframe','island':'I1'}],'uncertainties':[]}
acts=[{'action':'A','target':'H1','eig':'high','cost':'low'},{'action':'B','target':'H1','eig':'high','cost':'low'},{'action':'C','target':'H1','eig':'high','cost':'low'}]
print([x['action'] for x in sm._order_actions(state,acts,{'operator':'reframe','prefer_actions':['B']})])"
```
OBSERVED: `['A', 'B', 'C']` (B explicitly preferred, A chosen first). With
`prefer_actions=['C']` → `['A', 'C', 'B']`.
Expected: an explicit `prefer_actions` rank outranks operator/island alignment (or the
docstring/comment is wrong).
Regression: the `prefer_rank` mechanism itself is new in this range; the operator-route
behaviour is pre-existing.

### L4 — `undifferentiated_arms` compares only dimension means, hiding pass-rate/violation differences
Severity: Medium
File: `scripts/research_replay.py:1168-1173` (signature), used at `:1195/:1204-1206`

What is wrong: the signature is a JSON dict of the seven `mean` values only. Two arms with
equal means but different `pass_rate`, `violations`, `observable_cases`, `min`/`max` are
declared "indistinguishable", and the report then says extra capability must not be claimed.

Reproduction: `/tmp/probe_undiff.py` (custom runner; one arm triggers
`self_certify_novelty`).
OBSERVED:
```
arm_a pass_rate= 1.0 violations= []                 means=... search_efficiency 0.0
arm_b pass_rate= 0.0 violations= ['self_certify_novelty'] means=... search_efficiency 0.0
undifferentiated_arms: [['arm_a', 'arm_b']]
```
Expected: an arm that violates a forbidden behaviour is never reported as undifferentiated
from a clean arm.
Regression: pre-existing shape; surfaced by the new guard-probe emphasis.

### L5 — `sufficient_sample` is true while every dimension is unobservable, and the claim asserts measured deltas
Severity: Medium
File: `scripts/research_replay.py:1175-1192`; `run_case`/`run_suite` never call `case_errors`
(`:1047-1083`, `:1121`)

What is wrong: `sufficient = sample_size >= 2 and len(cases) >= 3` is purely a count.
`run_suite` also accepts cases that `load_case` would reject (`RP1`). With 3 cases whose
answers carry no scoreable content, all seven means are `None` yet the report says
`sufficient_sample: True` and claims "重复运行后的实测差值".

Reproduction: `/tmp/probe_sufficient.py`.
OBSERVED:
```
case_errors: [[Diagnostic('RP1', 'case.hidden.answer.true_outcome_class')], ...]
sufficient_sample: True sample_size: 3
claim: 重复运行后的实测差值；合成 fixture 上的差值不是真实科研性能
dims: {all seven: None}
```
Expected: `sufficient_sample` requires at least one observable decision; invalid cases are
refused before scoring.
Regression: `sufficient_sample`/claim text is part of the reviewed replay reporting; case
validation omission is pre-existing.

### L6 — `cases_from_trajectory` fabricates an observed action `"None"`
Severity: Medium
File: `scripts/research_replay.py:1033`

What is wrong: `"observed_actions": [str(chosen)] if view.get("outcome") else []` guards on
the outcome but not on `chosen`. `support_map_from_trajectory` (`:964-968`) correctly guards
with `if chosen:`; this function does not.

Reproduction (`chosen=None`, valid candidates, outcome appended):
```
python3 -c "... dt.build_decision_record(..., chosen=None, candidates=[{...}]) ; append outcome ; rr.cases_from_trajectory(path, state=state, hidden_answers={tid:{'true_outcome_class':'PREDICTION_HELD'}})"
```
OBSERVED:
```
append decision: APPENDED
append outcome: APPENDED
evidence_support: {'observed_actions': ['None'], 'replay_supported_actions': []}
```
Expected: an outcome with no chosen action yields `observed_actions: []`, and the case should
not claim any action was observed.
Regression: new public API (`cases_from_trajectory`) in this range.

### L7 — `coverage_report` counts an outcome-without-decision trajectory as evaluable (regression)
Severity: Medium
File: `scripts/research_replay.py:990` (changed from `len(support["observed_actions"])` in this range)

What is wrong: `evaluable = (#views with outcome != None)`. A trajectory that has an outcome
record but no decision (or a decision with no `chosen`) can never be replayed/scored, yet it
inflates `evaluable_trajectories`/`evaluable_fraction`.

Reproduction: `/tmp/probe_api.py` section G — a JSONL containing only an `outcome` record.
OBSERVED:
```
trajectories: 1, observed_actions: [], replay_supported_actions: [],
evaluable_trajectories: 1, evaluable_fraction: 1.0
```
Expected: `evaluable_trajectories` counts trajectories that expose both a chosen action **and**
an outcome (as `support_map_from_trajectory` does).
Regression: **new** — the previous expression would have reported 0 here.

### L8 — `guard_probes` counts a *refused* candidate as a diverging arm
Severity: Medium
File: `scripts/rsi_ablation.py:145-152`

What is wrong: `diverging` is true as soon as any of the bypass flags is set, but a bypass
flag is set before later checks can still refuse the candidate and leave
`chosen_intervention` unchanged. A guard can therefore be "measured" while buying nothing.

Reproduction: `/tmp/probe_refused_diverging.py` — candidate prefers a low-tier action, so the
tier bar rejects it after the scope guard is bypassed.
OBSERVED:
```
full_cie chosen= X2 applied= None scope_bypassed= None reason= None
rsi_without_scope chosen= X2 applied= None scope_bypassed= True reason= preferred_action_in_another_tier:XLOW
diverging_arms: ['rsi_without_scope']
chosen identical to guarded arm? True
```
(On the 14 shipped cases every guard arm does apply 14/14, so the defect is latent there, but
it fires for any mixed-tier probe.)
Expected: "diverging" means the decision actually changed (or the policy applied), not merely
that a bypass flag was set.
Regression: new (`guard_probes` added in this range).

### L9 — every RSI arm is reported as an unknown ablation arm
Severity: Medium/Low (false diagnostic on every RSI decision)
File: `scripts/research_replay.py:457-458`, constants `:64` (`ABLATION_ARMS`) vs `:68` (`RSI_ARMS`)

What is wrong: `decision_errors` validates `decision["arm"] not in ABLATION_ARMS`, but the RSI
arms live in `RSI_ARMS` and are not members of the frozen four.

Reproduction: `/tmp/probe_api.py` section D.
OBSERVED: `run_case(case, "rsi_full")["diagnostics"] ==
[{"rule": "RP3", "path": "decision.arm", "detail": "未知的 ablation arm"}]`.
Expected: `RSI_ARMS` is accepted by `decision_errors` (the frozen `ABLATION_ARMS` tuple can
stay frozen; the validation should use their union).
Regression: new (RSI arms added in this feature range).

### L10 — `overhead_report(iterations=0)` raises `ZeroDivisionError`
Severity: Low
File: `scripts/rsi_ablation.py:244`, `:249`

What is wrong: latency is `(elapsed)/iterations`; `iterations` is not validated and `range(0)`
makes both loops empty.

Reproduction: `python3 -c "import sys;sys.path.insert(0,'scripts');import rsi_ablation as ra;ra.overhead_report(iterations=0)"`
OBSERVED: `ZeroDivisionError: division by zero`.
Expected: a clear validation error, or `None` for unmeasurable latency. (The CLI never exposes
`iterations`, so this needs a direct API call.)
Regression: new.

### L11 — `leak_audit`/RP7 has a `.pyc` blind spot and a case-file false positive
Severity: Medium/Low
File: `scripts/research_replay.py:886-907` (`.pyc` skip at `:899`; whole-dir substring scan)

What is wrong (a) false negative: `if resolved.suffix in (".pyc",): continue` makes a hidden
answer reachable only from a compiled file invisible to isolation. (b) false positive: if
`case_dir` is the directory that holds the case JSON (written with `ensure_ascii=False`, as a
raw `json.dumps(case)` can be), the case file itself contains the hidden answer and RP7 always
fires, so `run_case(..., require_isolation=True)` refuses every case.

Reproduction: `/tmp/probe_leak.py` (F1) and:
```
python3 -c "import json,sys,tempfile,pathlib;sys.path.insert(0,'scripts');import research_replay as rr
case=rr.adversarial_cases()[0]
with tempfile.TemporaryDirectory() as t:
    p=pathlib.Path(t)/'case.json'; p.write_text(json.dumps(case,ensure_ascii=False),encoding='utf-8')
    print(rr.leak_audit(case,rr.visible_view(case),case_dir=pathlib.Path(t)))"
```
OBSERVED:
```
F1 -> audit: []                                   # marker present only in cached.pyc
F2 -> ['RP7: 可见目录中的 case.json 含隐藏答案文本']   # case file self-match
```
The existing test masks (b) because it also writes a `notes.txt` marker.
Expected: RP7 scans binary payloads too (or explicitly documents the exclusion), and excludes
the case file that is the subject of the audit.
Regression: new API in this range.

### L12 — `must_not_conflate` is decorative
Severity: Low
File: `scripts/rsi_ablation.py:313-314`; only consumer `:404` (`len(...) == 4`)

What is wrong: it is a four-item string list; nothing joins it back to the L1/L2/L3 claims or
enforces that a claim about "策略已被应用" is not reported as "科研能力获得独立证据支持的改善".
Reproduction: `grep -rn must_not_conflate scripts/` → only the definition and a length check.
Expected: either it enforces something or it is documentation only.

---

## SUSPECTED

### L13 — `level_report(l3_evidence=...)` marks L3 VERIFIED for any truthy value
Severity: Low
File: `scripts/rsi_ablation.py:300-301`
`if l3_evidence:` is falsy-correct for the empty list/`{}` (the example in the brief is **not**
a bug), but `[0]`, `["maybe"]`, `{"x": 1}` all produce `status == "VERIFIED"` with no schema
check and no independence/blind-review validation. `full_report` and the CLI never pass
evidence, so it needs a direct caller.

### L14 — non-list `prefer_actions` is accepted
Severity: Low
File: `scripts/strategy_memory.py:901-907`
`preferred = advice.get("prefer_actions") or []` is never type-checked. A string is treated as
a substring container (`prefer_actions="BC"` aligns action `B` and `C`; `"C"` aligns `C`), and
a dict reaches `preferred.index(...)` and raises `AttributeError: 'dict' object has no
attribute 'index'`. Reproduced in `/tmp/probe_order.py`. Advice is produced internally today,
so this is a robustness gap, not a reachable mis-dispatch.

---

## Checked and NOT a bug

- **`diverging_arms` order dependence** — `diverging` is wrapped in `sorted(...)`
  (`rsi_ablation.py:145`); `per_arm`/dict ordering cannot change the result.
- **`skill_rsi_vs_current_cie` against the wrong arm when `RSI_ARMS` grows** — it is
  `pe.distinguishable(core, "rsi_full", "full_cie")`, and `full_cie` is the current CIE+SE
  arm; extending `RSI_ARMS` does not change the comparison.
- **`rsi_probe_cases` mislabelling the diverging arm on the shipped suite** — all 14 cases
  yield exactly one arm per guard variant: `unpromoted→rsi_without_promotion`,
  `unscoped→rsi_without_scope`, `unsupported→rsi_without_trajectory`,
  `unevaluated→rsi_without_replay`.
- **`prefer_rank` changing `recommend_strategy` output** — `recommend_strategy` never emits
  `prefer_actions` (`strategy_memory.py:666-746`), so `prefer_rank` is always `None` there and
  ordering is unchanged.
- **Duplicate `prefer_actions` non-determinism** — `preferred.index(id)` returns the first
  occurrence; `["B","B","C"]` → `['B','C','A']`, deterministic.
- **`prefer_actions` naming an illegal action and still reordering** — ghost-only advice
  (`{"prefer_actions":["GHOST"]}`) leaves the order unchanged; an illegal entry cannot be
  promoted.
- **"same tier only" in `strategy_decision(advice=...)`** — `_order_actions` returns
  `top + rest`; mixed-tier test: prefer the low-tier `B` → `[('A',3.0),('B',0.333)]`, chosen
  stays top-tier. The guarantee holds.
- **`run_suite(arms=["baseline"])`** — returns `arms=['baseline']`, `pass_rate=0.0`,
  `undifferentiated_arms=[]`, no exception.
- **`step_skill_rsi` failing on regressions** — broken `rsi_ablation --selftest` →
  `(False, 'rsi_ablation.py selftest failed: ...')`; broken `test_rsi_ablation.py` →
  `(False, 'test_rsi_ablation.py failed: FAILED (failures=1)')`. It really runs the tests it
  claims: 5 selftests + 7 invocations (`test_decision_trajectory.py` plus six patterns,
  `release_check.py:790-801`).
- **`release_check.step_skill_rsi` not running `test_research_replay.py`** — that file is run
  by the earlier `step_tests` full discovery (`release_check.py:88-91`); the "7 RSI suites"
  claim matches the 7 RSI-labelled invocations.
- **`coverage_report` division by zero** — `evaluable_fraction` is `None` when `total == 0`
  (`:999`).
- **`overhead_report` exceeding a sane bound** — all sizes/counts are measured except the
  declared constant `extra_tool_calls_per_loop = 1`; the only arithmetic hazard is L10.
- **`step_release_metadata` dev-branch tag rule** — on `main` the tag must equal `HEAD`; off
  `main` it must equal `refs/heads/main` and be an ancestor of `HEAD` (empty `main` is
  tolerated). No reachable false negative found in this checkout (tag `v1.0.0 == main ==
  ea0214e`).
