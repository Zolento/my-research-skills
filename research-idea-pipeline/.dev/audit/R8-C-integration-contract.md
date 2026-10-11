# R8-C integration and contract drift

HEAD reviewed: **53ea2006b010b98d323e6be04467aa4b5998f8af** (`research-idea-pipeline/skill-rsi-dev`).

Method note: the live worktree was **dirty and actively changing** during this audit
(`git status` showed `M scripts/policy_evolution.py`, `M scripts/test_promotion_credentials.py`,
`M .dev/round9/record.md`, untracked `R8-A`/`R8-B` reports; HEAD later advanced 53ea200 → 389e36b).
Every result below was produced from a **clean export of the pinned commit**:

```sh
rm -rf /tmp/r8c_53 && mkdir -p /tmp/r8c_53
git -C <worktree> archive 53ea200 | tar -x -C /tmp/r8c_53
cd /tmp/r8c_53/research-idea-pipeline
```

I re-checked the six main findings against the current worktree (389e36b) and all six strings
are still present, so they are not artifacts of the export.

Baseline (clean 53ea200, run alone):
- `python3 scripts/release_check.py` → **PASS** (18 steps), exit 0.
- `python3 -m unittest discover -s scripts -p 'test_*.py'` → **OK, Ran 1810 tests, skipped=4**
  (no `.git` in the export; with `.git` present the repo reports skipped=3).

---

## CONFIRMED

### C-1 `research-loop` reports `policy_delta.level = "L2"` for every applied policy, including an L3 human-approved ACTIVE policy [MED]

- repro (self-contained; run from a clean 53ea200 export, `scripts/` on `PYTHONPATH`):
  ```sh
  cd /tmp/r8c_53/research-idea-pipeline/scripts && python3 - <<'PY'
  import sys, tempfile, pathlib, json
  sys.path.insert(0, ".")
  import test_skill_rsi_e2e as t, policy_evolution as pe, preset_router as pr
  case = t.RsiProject(); temp = tempfile.TemporaryDirectory()
  sp = case.project(pathlib.Path(temp.name) / "A")
  case.propose_policy(sp); case.activate(sp)          # full L3 path: approve-l3 + validate-research
  for r in pe.load_records(sp)[0]:
      if r.get("record") == "transition":
          print("transition", r.get("policy_id"), r.get("from"), "->", r.get("to"), "level=", r.get("level"))
  p = pr.run_preset("research-loop", sp, apply=True)[0]
  print("policy_delta:", json.dumps(p["decision"]["policy_delta"], ensure_ascii=False))
  print("scoped_policy:", json.dumps(p["observed"]["scoped_policy"], ensure_ascii=False))
  PY
  ```
- observed:
  ```
  transition P-RSI PROPOSED -> SHADOW level= L1
  transition P-RSI SHADOW -> REPLAY_EVALUATED level= L2
  transition P-RSI REPLAY_EVALUATED -> BOUNDED_TRIAL level= L2
  transition P-RSI BOUNDED_TRIAL -> VALIDATED level= L3
  transition P-RSI VALIDATED -> ACTIVE level= L3
  policy_delta: {"status": "applied", "level": "L2", "policy_id": "P-RSI", "scope": {"problem_structure": "repair-vs-discriminate", "scope_kind": "local"}}
  scoped_policy: {"policy_id": "P-RSI", "applied": true, "conditions_ok": true, "unmet_conditions": [], "source": "active_scoped_policy", "tampered": false, "diagnostics": [], "write_failure": null, "dispatched_action": "R2", "strategy_overrode_scheduler": true}
  ```
  The control plane records `VALIDATED -> ACTIVE level=L3` and a sealed `l3-approval@1` event
  (`pe.approval_events(sp)`); the consumer reports `L2` and `scoped_policy` has **no level field
  and no approval/credential field at all**. The only level literal in the router is hardcoded:
  `preset_router.py:2175` (`"level": "L2" if applied else None`) and `:2244`
  (`dispatch.get("level") or "L2"`). The e2e test that locks this in
  (`test_skill_rsi_e2e.py:166`, `assertEqual(..., "L2")`) dates from commit `c9fb540` (pre-L3) and
  was not updated by rounds 7–8.
- expected: under the round-7/8 contract every ACTIVE policy is necessarily L3-evidenced
  (`VALIDATED`/`ACTIVE` only accept `policy-research-validation@1` + PE15 approval), and
  `references/skill-rsi-policy.md` §6/§7 require `policy_delta` to carry the evaluation level and
  forbid conflating L1/L2/L3. The consumer cannot distinguish an L3-approved policy from an
  old-contract L2 policy, and silently under-reports the recorded level.
  (Caveat for the parent: §7 of `presets/strategy-evolution.md` can also be read as
  "L2 = operational dispatch effect", under which L2 is defensible. The factual drift — the
  consumer discards the recorded level and the approval — is confirmed either way.)
- source: `scripts/preset_router.py:2168,2175,2244`; `scripts/test_skill_rsi_e2e.py:166`;
  `references/skill-rsi-policy.md` §6–7.

### C-2 The release gate still prints PASS after the round-7/8 L3 contract suites are deleted [MED]

- repro:
  ```sh
  rm -rf /tmp/r8c_scan3 && cp -r /tmp/r8c_53 /tmp/r8c_scan3
  cd /tmp/r8c_scan3/research-idea-pipeline
  rm scripts/test_l3_trust_boundary.py scripts/test_promotion_credentials.py
  python3 scripts/release_check.py | tail -3
  ```
- observed: `PASS` (exit 0). The Skill-RSI step still prints
  `5 selftests + 7 RSI suites green; policy promotion needs an independent replay ...`.
  `release_check.py:795-802` hard-codes a suite list that predates rounds 6–8
  (`test_policy_evolution`, `test_policy_transfer`, `test_counterfactual_replay`,
  `test_source_freeze`, `test_rsi_ablation`, `test_skill_rsi_e2e` — it omits
  `test_l3_trust_boundary.py`, `test_promotion_credentials.py`, `test_promotion_integrity.py`).
  `step_tests()` runs `discover test_*.py` generically and asserts no minimum test count, so a
  deleted suite (count 1810 → 1745) is invisible.
- expected: the step that advertises policy-lifecycle coverage should pin the suites that test the
  current contract (PE15/PE16, credential classes, approval ledger), or at least assert the
  expected test count; otherwise a regression that removes the L3/fairness tests passes the gate.
- source: `scripts/release_check.py:791-802,875-877`.

### C-3 `README.md` still documents the pre-round-7 promotion contract [MED]

- repro:
  ```sh
  sed -n '406,413p' /tmp/r8c_53/research-idea-pipeline/README.md
  grep -c 'validate-research\|approve-l3\|PE15\|PE16' /tmp/r8c_53/research-idea-pipeline/README.md
  ```
- observed: line 409–410 — `... BOUNDED_TRIAL → VALIDATED → ACTIVE, and every promotion needs an
  independent, leakage-checked, reproducible replay evaluation with the evaluation rules frozen
  beforehand.` The second command prints `0`: the README never mentions the L2 cap on replay
  credentials, `validate-research`, `approve-l3`, PE15 (human approval) or PE16 (fairness).
- expected: the component README should state that replay evidence caps at L2, and that
  VALIDATED/ACTIVE require a `policy-research-validation@1` credential plus a recorded human
  approval and a fairness record — the same contract the reference doc and CLI now enforce.
- source: `README.md:406-413`.

### C-4 `policy_evolution.py --help` still says nothing reaches ACTIVE without a replay evaluation [LOW]

- repro:
  ```sh
  cd /tmp/r8c_53/research-idea-pipeline && python3 scripts/policy_evolution.py --help | sed -n '/Nothing reaches/,+3p'
  ```
- observed:
  ```
  * Nothing reaches `ACTIVE` without an independent, leakage-checked, reproducible replay
    evaluation (`PE11`), and the evaluation rules must be unchanged since the candidate was
    generated (`PE12`).
  ```
- expected: `ACTIVE` now requires a `policy-research-validation@1` credential + a human approval
  (`approve-l3`, PE15) + a fairness record (PE16); a replay evaluation only reaches
  `REPLAY_EVALUATED`/`BOUNDED_TRIAL` at L2. The CLI help is the first thing an operator reads and
  it describes the old lifecycle.
- source: `scripts/policy_evolution.py:30-32` (module docstring rendered by `--help`).

### C-5 `references/skill-rsi-policy.md` rule index and "four controlled entries" omit the new L3 entry points [LOW]

- repro:
  ```sh
  sed -n '109,112p;134,138p' /tmp/r8c_53/research-idea-pipeline/references/skill-rsi-policy.md
  python3 /tmp/r8c_53/research-idea-pipeline/scripts/policy_evolution.py --help | grep -o 'validate-research\|approve-l3'
  ```
- observed: §5.1 enumerates `PE1`…`PE14` and stops at `PE14` (PE15/PE16 are defined later in
  §5.3.1.1/§5.3.1.2 but never added to the index). §5.3.1 says
  `必须使用四个受控入口：evaluate / trial / validate / promote。` — omitting `validate-research`
  (the entry that actually produces VALIDATED) and `approve-l3`; plain `validate` no longer reaches
  VALIDATED without a pre-recorded L3 credential (it returns PE11).
- expected: the authoritative reference's rule index and controlled-entry list should match the
  implemented CLI (`validate-research`, `approve-l3` are accepted and required).
- source: `references/skill-rsi-policy.md:109-112,134-138`; `scripts/policy_evolution.py` CLI.

### C-6 Stale `PE1`—`PE14` ranges in two formal docs [LOW]

- repro:
  ```sh
  grep -n 'PE1`—`PE14' /tmp/r8c_53/research-idea-pipeline/SKILL.md \
      /tmp/r8c_53/research-idea-pipeline/presets/strategy-evolution.md
  grep -oE 'PE[0-9]+' /tmp/r8c_53/research-idea-pipeline/scripts/policy_evolution.py | sort -u | tr '\n' ' '
  ```
- observed: `SKILL.md:1009` — `有作用域的策略候选（\`PE1\`—\`PE14\`）…`;
  `presets/strategy-evolution.md:58` — `Skill-RSI 另产生 \`DT0\`—\`DT10\` / \`PE1\`—\`PE14\` / \`PT1\`—\`PT11\``.
  The code emits `PE1 PE2 … PE16` (both PE15 and PE16 exist).
- expected: ranges should be `PE1`—`PE16`.
- source: `SKILL.md:1009`; `presets/strategy-evolution.md:58`.

### C-7 `rsi_ablation.py` L2 evidence still claims promotion needs only an independent replay [LOW]

- repro:
  ```sh
  cd /tmp/r8c_53/research-idea-pipeline && python3 scripts/rsi_ablation.py report \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['levels']['L2_operational_validity']['evidence'])"
  ```
- observed: one evidence string is `"晋升需要独立 replay 评价，且评价规则冻结后不可改动"`.
- expected: promotion to ACTIVE now additionally requires the L3 research-validation credential,
  the human approval and the fairness record; saying "promotion needs an independent replay" is the
  old lifecycle (the README documents this `report` command, so the claim is user-visible).
- source: `scripts/rsi_ablation.py:306`.

### C-8 "registry↔protocol parity" does not check the registry `trigger` field against the protocol doc [LOW]

- repro:
  ```sh
  rm -rf /tmp/r8c_scan5 && cp -r /tmp/r8c_53 /tmp/r8c_scan5
  cd /tmp/r8c_scan5/research-idea-pipeline
  python3 - <<'PY'
  import json, pathlib
  p = pathlib.Path("preset-registry.json"); d = json.loads(p.read_text())
  for r in d["presets"]:
      if r["preset_id"] == "strategy-evolution": r["trigger"] = "manual"
  p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
  PY
  python3 -c "import sys;sys.path.insert(0,'scripts');import release_check;print(release_check.step_preset_library()[0])"
  grep -n 'registry trigger' presets/strategy-evolution.md
  ```
- observed: `True` (step passes) while `presets/strategy-evolution.md:10` still documents
  `registry trigger | manual_or_scheduled` and `preset-registry.json` now says `manual`.
  `registry_errors` (`preset_router.py:860-873`) validates `execution_scope` and `trigger` against
  the *vocabulary* and `entry`/`execution_scope` against the protocol text, but never checks the
  registry `trigger` against the protocol's declared `registry trigger`.
- expected: the step advertises "registry↔protocol parity"; a registry trigger that contradicts the
  protocol doc should fail it (a mutation of `execution_scope` is correctly caught, so the gap is
  specific to `trigger`).
- source: `scripts/preset_router.py:860-873`; `scripts/release_check.py:884-886,929`.

### C-9 The documented RSI lifecycle R4→R5→R6 does not run literally with the shipped replay fixture [LOW]

- repro:
  ```sh
  cd /tmp/r8c_53/research-idea-pipeline
  W=$(mktemp -d); A="$W/A"; mkdir -p "$A"
  # (state + candidate as in the §5 R1–R3 table)
  python3 scripts/policy_evolution.py freeze-rules --state "$A/research-state.json" >/dev/null
  python3 scripts/policy_evolution.py propose --state "$A/research-state.json" --policy "$W/candidate.json" >/dev/null
  python3 scripts/policy_evolution.py transition --state "$A/research-state.json" --policy-id P-1 --to SHADOW >/dev/null
  python3 scripts/research_replay.py ablate --dir examples/replay/adversarial --rsi --runs 2 > "$W/report.json" 2>/dev/null
  python3 scripts/policy_evolution.py evaluate --state "$A/research-state.json" --policy-id P-1 --report "$W/report.json"
  python3 scripts/policy_evolution.py trial    --state "$A/research-state.json" --policy-id P-1 --dispatch '{"dispatched":"R2"}'
  ```
  (Full working script: `/tmp/r8c_doc_lifecycle.sh`; it writes the state/candidate and runs the
  doc's R1–R3 first.)
- observed:
  ```
  evaluate -> {"status": "HOLD", "level": "L1", "reason": "没有任何预先定义的收益维度取得正向改善…"}  exit=0
  trial    -> {"status": "INVALID", "codes": ["PE10"], "diagnostics": ["非法状态转移 HOLD → BOUNDED_TRIAL"]}  exit=3
  ```
- expected: `presets/strategy-evolution.md` §5 presents R4→R5→R6 as a contiguous sequence; it has
  no HOLD branch. The shipped adversarial fixture legitimately produces HOLD (this is honest
  behaviour), but the documented sequence as printed does not run end-to-end. Either the doc should
  state the HOLD/retry branch (`HOLD → evaluate again`) or use a supporting report.
- source: `presets/strategy-evolution.md:63-80`.

---

## SUSPECTED

- **S-1 Test isolation hazard (not a contract bug).** The release-gate mutation tests write the
  real shipped files (`references/research-state-policy.md`, `SKILL.md`,
  `examples/structural-equivalence/paradigm-candidate.json`) and restore them in `finally` /
  `tearDownClass`. Two test/gate processes in one tree corrupt each other: running
  `release_check.py` and `unittest discover` concurrently produced spurious
  `FAILED (failures=2/3/5)` and `test_policy_rule_text_matches_validator` /
  `test_step_passes_on_current_tree` failures, which both passed when run alone. Worth guarding if
  CI ever parallelises tests in one checkout.
- **S-2 `.dev` scan skip rule.** `step_skill_rsi`'s AST scan skips any string constant whose
  enclosing function name contains `selftest` or `fixture` (`release_check.py:856-858`). A shipped
  (non-test) helper named e.g. `load_fixture_config()` reading `.dev/` would evade the AGENTS §15
  guard. The scan does have teeth for direct and module-constant literals (verified below).
- **S-3 Undocumented approval surface.** No formal reference names the approval ledger location
  (`<route>/policy/approvals/`, with HMAC `key`/`head`/`events.jsonl`) or the `l3-approval@1`
  schema id; `references/skill-rsi-policy.md:140` only names `policy/evaluations|trials`. Low
  impact but operator-relevant.
- **S-4 Dead code.** `release_check.py:844-847` defines `_used_as_path()` with a no-op body and
  returns `False`; it is never called (the working scan is the `parent_is_usage` loop below it).
  Harmless, but the comment above it describes behaviour it does not implement.

---

## NOT-BUGS (checked, clean)

- **Release gate on clean 53ea200:** `python3 scripts/release_check.py` → `PASS`, exit 0, all 18
  steps exercised (run alone). The earlier FAIL I saw was my own concurrent-run artifact (S-1).
- **Full unit suite on clean 53ea200:** `Ran 1810 tests ... OK (skipped=4)` (no `.git`); the repo
  itself reports `skipped=3`. Both matching the round-8 record's count.
- **PE15 surfacing via CLI:** `validate-research` without an approval → exit **3**, body contains
  `"PE15"` and `没有人工批准记录…`, **no traceback**. Full happy path
  `approve-l3 → validate-research (VALIDATED, level L3) → promote (ACTIVE, level L3)` works, exit 0;
  `approval_events()` shows the sealed `l3-approval@1` record.
- **Router exit codes / hold reasons:** tampered `candidates.jsonl` → `research-loop` `status=HOLD`,
  **exit 4**, `hold_reason="policy_store_tampered"`, `scoped_policy.tampered=true`,
  `policy_delta.status="none"`. Healthy store → `OK`, exit 0. PE15/PE16 never reach the router as a
  HOLD (they refuse the transition before ACTIVE), so there is no PE15/PE16 mis-report path.
- **New artifact kinds:** with `policy/evaluations/*.json`, `policy/trials/*.json` and
  `policy/approvals/` present, `research-loop` still consumes the ACTIVE policy
  (`policy_delta.status="applied"`), reports `canonical_untouched`, and writes the trajectory.
- **`.dev` scanner teeth:** injecting `open(".dev/some_file.txt")` → step FAILs
  (`render_status.py:211`); injecting `DEVDIR = ".dev"` used in a call → step FAILs
  (`render_status.py:DEVDIR`).
- **Registry parity teeth:** mutating `strategy-evolution.execution_scope` to `read_only` → step
  FAILs with `PR3 … 协议文件未声明 授权（read_only）`; 16 presets, id order and `base_contract`
  are checked.
- **CLI surface parity:** every documented `policy_evolution.py` invocation uses an existing
  subcommand/flag (`freeze-rules/propose/transition/evaluate/trial/validate-research/approve-l3/
  promote/rollback`); `python3 scripts/policy_evolution.py --help` accepts all of them.
  `research_replay.py ablate --dir … --rsi --runs 2` and `rsi_ablation.py report` exist.
- **Level honesty elsewhere:** `rsi_ablation.py report` reports `L3_research_improvement`
  `NOT_VERIFIED` with an explicit reason; no code claims automatic L3.
- **No new state/preset:** the changes are confined to the policy control plane; canonical state,
  scheduler priority and `EIG ÷ cost` are untouched by the router paths above.
