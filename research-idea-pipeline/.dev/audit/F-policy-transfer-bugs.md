# F — Adversarial audit: `scripts/policy_transfer.py` (+ `policy_evolution.cross_project_transfer_allowed`)

- Scope: `scripts/policy_transfer.py` (1730 lines), `scripts/policy_evolution.py::cross_project_transfer_allowed`,
  `scripts/preset_router.py::strategy_dispatch`, `scripts/decision_trajectory.py` (load/rebuild), `scripts/test_policy_transfer.py`.
- Baseline: `python3 -m unittest test_policy_transfer` → **Ran 46 tests … OK** (all findings below are *not* covered).
- Method: every finding was reproduced with a script in `/tmp/ptrepro/` (`common.py`, `confirmed.py`) or a direct
  `python3 -c`-style invocation. No repository file other than this report was modified.
- Environment: Python 3.14, repo root `/home/lenovo/code/myproj/skills-dev/research-idea-pipeline/skill-rsi-dev/research-idea-pipeline`.

Fail-closed is the module's stated contract (module docstring: “未声明的键按 fail-closed 处理：无法证明条件成立即阻塞”;
`transfer_decision`: “任何一条诊断都返回 BLOCK”). Findings H1–H6 and M1–M3 are violations of that contract where the
gate returns **ALLOW** (or silently accepts unverifiable provenance).

---

## CONFIRMED (reproduced)

### H1 — PT8 never sees a killed hypothesis (re-proposing a killed mechanism is ALLOW)

- **Severity:** HIGH
- **File:line:** `scripts/policy_transfer.py:572-587` (`negated_mechanisms` scans only `claims[]` and
  `failures[].negative_knowledge`; it never scans `hypotheses[]` or an index `mechanisms[]`).
- **What is wrong:** `state_check.HYPOTHESIS_STATUSES` is `("active","elite","archived","killed")` and
  `cognition`'s mechanism statuses include `refuted`. A hypothesis/mechanism that is `killed`/`refuted`
  is the canonical form of “被否证的机制”, yet `negated_mechanisms()` returns nothing for it, so
  `_negated_errors` (PT8, `1080-1111`) cannot fire. A policy may re-propose the exact killed mechanism id
  and transfers.
- **Reproduction:**
  ```python
  import common, policy_transfer as pt
  s = common.fixture_state()
  s["hypotheses"][0]["status"] = "killed"
  print([i["id"] for i in pt.negated_mechanisms(s)])
  print(common.transfer(common.allow_policy(mechanism={"id": "H1"}), s, s)["status"],
        common.transfer(common.allow_policy(mechanism={"id": "H1"}), s, s)["codes"])
  ```
- **OBSERVED:**
  ```
  [H1.negated] ["C1", "C2"]                # H1 missing entirely
  [H1.verdict] {"status": "ALLOW", "codes": []}
  ```
- **Expected:** `negated_mechanisms` should include `hypotheses[].status in (killed, archived)` and
  index mechanisms with `status == "refuted"`; `transfer_errors` should return PT8.
- **Exploitability:** Direct. The realistic fixtures expose it: `templates/research-state.template.json`
  has `failures[0].negative_knowledge == []` and no killed claim, and
  `examples/preflight-identifiability/ct-mri.json` (`state`) has one `ungrounded` claim and no failures —
  so on both realistic inputs the negation set from failures is empty and a killed hypothesis is the only
  available negation, which this bug ignores.

### H2 — PT8 matches the `finding` reason, not the `ruled_out` proposition

- **Severity:** HIGH
- **File:line:** `scripts/policy_transfer.py:597`
  (`statement = memory.get("finding") or memory.get("ruled_out") or failure.get("what") or ""`).
- **What is wrong:** For a `negative_knowledge` entry, the *negated proposition* is `ruled_out`; `finding`
  is only the explanation. By storing `finding` as the canonical statement and using it for the
  equality/substring test (`1099-1110`), a policy that restates the ruled-out claim verbatim is not
  matched, while restating the explanation *is* matched. This inverts PT8's purpose.
- **Reproduction:**
  ```python
  import common
  s = common.fixture_state()
  for stmt in ["协议 P 有效", "协议 P 在该 regime 下无效"]:
      r = common.transfer(common.allow_policy(mechanism={"id": "", "statement": stmt}), s, s)
      print(stmt, "->", r["status"], r["codes"])
  ```
- **OBSERVED:**
  ```
  [H2.协议 P 有效] {"status": "ALLOW", "codes": []}
  [H2.协议 P 在该 regime 下无效] {"status": "BLOCK", "codes": ["PT8"]}
  ```
  `ruled_out == "协议 P 有效"` (the thing that was actually killed) → **ALLOW**.
- **Expected:** a re-proposal of `ruled_out` must be PT8; `finding` should be a secondary match.
- **Exploitability:** Direct: any re-proposal that restates the ruled-out content instead of the reason
  bypasses PT8. Note only the *id* path works (`target_id` is used as the id), so an attacker need only
  avoid the id.

### H3 — PT10 counterexample coverage is bypassed by any unsatisfiable/malformed condition

- **Severity:** HIGH
- **File:line:** `scripts/policy_transfer.py:950-956`
  (`if conditions: ... if not any(satisfied): continue`).
- **What is wrong:** `_condition_satisfied` returns `False` both for a legitimately false condition **and**
  for a malformed/unresolvable one (missing field `709`, unknown op `753`, missing value `718`). Unlike
  PT5, which emits a diagnostic for those, PT10 treats “not provably applicable” as “does not apply” and
  `continue`s past the coverage check. Fail-open.
- **Reproduction:**
  ```python
  import common
  s = common.fixture_state()
  def ce(cond): return common.allow_policy(counterexamples=[
      {"id":"CE1","operators":["reframe"],"islands":["P1"], **cond}])
  print(common.transfer(ce({}), s, s)["status"])
  print(common.transfer(ce({"conditions":[{"field":"contract.nope","op":"eq","value":"x"}]}), s, s)["status"])
  print(common.transfer(ce({"conditions":[{"field":"hypotheses[].operator","op":"no_such_op"}]}), s, s)["status"])
  ```
- **OBSERVED:**
  ```
  [H3.no_condition] {"status": "BLOCK", "codes": ["PT10"]}
  [H3.missing_field_condition] {"status": "ALLOW", "codes": []}
  [H3.unknown_op_condition] {"status": "ALLOW", "codes": []}
  ```
- **Expected:** an unresolvable/unknown-op condition must fail closed (PT10), as PT5 does.
- **Exploitability:** Direct. One extra malformed condition on an otherwise-covering counterexample
  neutralises PT10 completely.

### H4 — `applicable_conditions` / `required_tools` with a non-list shape are silently ignored

- **Severity:** HIGH
- **File:line:** `scripts/policy_transfer.py:667-682` (`_collect_conditions`, only `list`/`dict` accepted)
  and `773-784` (`_required_tools`, only via `_as_list`).
- **What is wrong:** A JSON value that is neither list nor dict (string, number, `null`) is dropped with no
  diagnostic, so PT5/PT6 disappear. This contradicts “未声明的键按 fail-closed 处理”.
- **Reproduction:**
  ```python
  import common
  s = common.fixture_state()
  for shape in ["always applies", None, 42]:
      r = common.transfer(common.allow_policy(applicable_conditions=shape), s, s)
      print(repr(shape), "->", r["status"], r["codes"])
  print(common.transfer(common.allow_policy(required_tools="gpu-cluster"), s, s)["status"])
  ```
- **OBSERVED:**
  ```
  [H4.'always applies'] {"status": "ALLOW", "codes": []}
  [H4.None] {"status": "ALLOW", "codes": []}
  [H4.42] {"status": "ALLOW", "codes": []}
  [M5.required_tools_str] {"status": "ALLOW", "codes": []}
  ```
- **Expected:** a non-list `applicable_conditions`/`required_tools` is unprovable → PT3/PT5/PT6 BLOCK.
- **Exploitability:** Direct for any policy supplied as JSON (`policy_transfer.py transfer --policy ...`).
  `policy_evolution.propose()` guards its own path (`PE3` requires a non-empty list), so this is a
  gate-level hole rather than an end-to-end `propose()` hole.

### H5 — `cross_project_transfer_allowed` returns `NOT_REQUIRED` (gate disappears) in ordinary cases

- **Severity:** HIGH
- **File:line:** `scripts/policy_evolution.py:955-960`
  (`scope = candidate.get("scope") if isinstance(...) else {}`; `source = scope.get("source_route") or scope.get("source_project")`;
  `if not source or not current_route or str(source)==str(current_route): return NOT_REQUIRED`).
- **What is wrong:** (a) `source_route`/`source_project` are never written by `propose()` — a repo-wide grep
  shows only reads (`policy_evolution.py:955,959`) and test injection (`test_skill_rsi_e2e.py:259`), so real
  candidates hit `not source` → `NOT_REQUIRED`. (b) `current_route` is `cg.route_of(ctx["state_path"])`
  (`preset_router.py:2105`) whose result is `state_path.parent.name`; for a bare relative path this is `""`.
  (c) a `scope` that is not a dict (a plain string is legal in `policy_transfer._normalize_scope:986`) is
  coerced to `{}`, discarding provenance. All three turn a would-be cross-project BLOCK into ALLOW
  (preset_router: `transfer["status"] != "BLOCK"` → policy applied).
- **Reproduction:**
  ```python
  import common, pathlib, policy_evolution as pe, cognition as cg
  s = common.fixture_state()
  cand = {"id":"E","scope":{"scope_kind":"project","problem_structure":"x",
                            "source_route":"B","source_project":"B"}}
  print(pe.cross_project_transfer_allowed(cand, s, current_route=cg.route_of(pathlib.Path("research-state.json"))))
  print(pe.cross_project_transfer_allowed({"id":"E","scope":{"scope_kind":"project","problem_structure":"x"}},
                                          s, current_route="A"))
  ```
- **OBSERVED:**
  ```
  [H5.empty_current_route] {"required": false, "status": "NOT_REQUIRED", "reasons": [], "similarity": null}
  [H5.no_source_route]     {"required": false, "status": "NOT_REQUIRED", "reasons": [], "similarity": null}
  ```
  (`cg.route_of(pathlib.Path("research-state.json")) == ""`.)
- **Expected:** unknown provenance with a known `current_route` must run the transfer gate (fail-closed);
  a falsy `current_route` must not silently disable the gate.
- **Exploitability:** High. The producer (`propose`) never stamps provenance, so the gate is effectively dead
  in production. Note the `except Exception` path inside the same function *is* fail-closed, so the hole is
  the input discrimination, not the exception handling.

### H6 — `expired_trajectories` treats a missing/non-int `state_version` as version 0

- **Severity:** HIGH (silently stale experience is treated as fresh)
- **File:line:** `scripts/policy_transfer.py:1324-1326` and `1355`.
- **What is wrong:** `current` falls back to `0` when `state_version` is absent, a string, or a bool; the
  comparison `current - min(versions) > gap` then goes negative and never expires anything.
- **Reproduction:**
  ```python
  import common, decision_trajectory as dt, policy_transfer as pt
  s = common.fixture_state(version=3)
  ctx = dt.build_context(s, scientific_question="q", active_hypotheses=["H1"])
  rec = dt.build_decision_record(s, route="A", project="A", context=ctx,
                                 candidates=[{"action":"H1"}], chosen="H1",
                                 scheduler_priority={"level":1,"label":"x"})
  print(pt.expired_trajectories([rec], {k:v for k,v in s.items() if k != "state_version"}))
  print(pt.expired_trajectories([rec], {"state_version": "200"}))
  print(pt.expired_trajectories([rec], common.fixture_state(version=200)))
  ```
- **OBSERVED:**
  ```
  [H6.no_state_version] []
  [H6.string_state_version] []
  [H6.real_200] ["DT-sha256:c708138258a17"]
  ```
- **Expected:** absent/ill-typed `state_version` is not “version 0”; staleness is unprovable and the module's
  own fail-closed rule implies expiry (or at least a diagnostic), not “fresh”.
- **Exploitability:** Direct: dropping or stringifying `state_version` disables all version-based expiry.
  A jump of 197 versions is flagged with a real int, and invisible with a string.
  Related hazard: a non-int `max_state_version_gap` raises instead of diagnosing
  (`gap=None -> TypeError: '>' not supported between instances of 'int' and 'NoneType'`).

### M1 — `memory_layers` accepts any JSONL as `decision_experience`, discarding chain diagnostics

- **Severity:** MEDIUM (provenance fail-open; the module's 3-layer separation claim is weakened)
- **File:line:** `scripts/policy_transfer.py:227-241` (`_experience_layer`), esp. `229-231`
  (`records, _ = dt.load_records(path, tolerant=True)` — the diagnostics are thrown away; only
  `dt.TrajectoryError` is caught, which `tolerant=True` never raises).
- **What is wrong:** `dt.load_chained(..., tolerant=True)` performs no `_schema`/`record`-kind check and
  downgrades hash-chain/`seq`/tail-digest violations to diagnostics. `_experience_layer` discards them and
  labels the result `source: "decision_trajectory"`, so an arbitrary file full of trajectory-shaped records
  (or a policy/decision record smuggled into JSONL) is reported as verified decision experience with
  `separation_ok: True`.
- **Reproduction:**
  ```python
  import common, json, pathlib, tempfile, policy_transfer as pt, decision_trajectory as dt
  p = pathlib.Path(tempfile.mkdtemp())/"x.jsonl"
  p.write_text(json.dumps({"trajectory_id":"DT-evil","record":"decision",
                           "decision":{"context":{"state_version":3}}}) + "\nnot json\n")
  L = pt.memory_layers(common.fixture_state(), trajectory_path=p)
  print(L["separation_ok"], L["decision_experience"]["count"],
        L["decision_experience"]["trajectories"], L["diagnostics"])
  ```
- **OBSERVED:**
  ```
  [M1.experience] {"separation_ok": true, "count": 1, "trajectories": ["DT-evil"], "diagnostics": []}
  ```
  (non-tolerant loader on the same file: `TrajectoryError: DT0 ... seq 不连续：期望 1，实际 None`.)
- **Expected:** diagnostics from the tolerant load must surface in `memory_layers(...).diagnostics`
  (and `separation_ok` should be False); a trajectory file must be `decision-trajectory.jsonl` with a valid chain.
- **Exploitability:** Medium. The same loader feeds `--source-trajectory` (`1473-1478`), whose records supply
  `qualified_projects` for PT9 (`1178-1187`): two forged `{"record":"outcome","project":"A","evidence_qualification":"qualified"}`
  lines satisfy the broad-scope evidence rule (see M6).

### M2 — structural match without any shared operator/island; self-attested source signature

- **Severity:** MEDIUM
- **File:line:** `scripts/policy_transfer.py:519-529` (`_similarity_from_signatures`; the else-branch only
  requires `score >= threshold and shared`, not a shared *axis*), `1025-1030` (`_transfer_similarity`;
  when `source_state` is not a dict the **policy chooses its own source signature**).
- **What is wrong:** (a) When either side declares no operator/island, a shared `structural_signature`
  (five arbitrary integers) alone yields `structural_match=True`. A target state that declares **no**
  operator/island at all can therefore be judged structurally matching (score 0.71 here). (b) `source_state`
  is optional; with it omitted (the default of the `transfer` CLI — `--source-state` is optional) the policy
  self-declares its source structure and can reach score 1.0 / ALLOW. An attacker only needs to add a common
  dummy operator on *both* sides (`{"operator":"totally_made_up"}`) to get score 1.0.
- **Reproduction:**
  ```python
  import common, policy_transfer as pt
  S = common.fixture_state(); sig = S["hypotheses"][0]["structural_signature"]
  tgt = common.clone(S); tgt["hypotheses"] = [{"id":"H1","structural_signature":common.clone(sig)}]
  r = common.transfer(common.allow_policy(applicable_conditions=[
        {"field":"contract.primary_anchor","op":"eq","value":"phenomenon"}]), tgt, S)
  print("a)", r["similarity"]["score"], r["similarity"]["structural_match"], r["status"])
  r2 = pt.transfer_decision({"id":"EVIL","scope":{"kind":"structure"},
      "structural_signature":{"operators":["reframe"],"islands":["P1"],
                              "structural_signature":common.clone(sig)},
      "evidence_level":"independent","independent_evaluation_refs":["X"],"counterexamples":[]}, S)
  print("b)", r2["similarity"]["score"], r2["status"])
  ```
- **OBSERVED:**
  ```
  [M2.target_has_no_operator] {"score": 0.714286, "match": true, "status": "ALLOW"}
  [M2b.self_attested_no_source] {"score": 1.0, "status": "ALLOW", "codes": []}
  ```
- **Expected:** per the module comment (`524-526`), different/absent operators are different structures; a
  target with no declared axis should not match on distance integers alone, and a missing source state
  should not let the policy assert its own provenance.
- **Exploitability:** Medium. Two states with no operators/islands but identical distance dicts:
  `score = 1.0, structural_match = True`. An unrelated pair can be forced to match by adding one common
  dummy operator token to both (`[1.0, true]`).

### M3 — `compression_report` drops a non-droppable item when the same id appears twice

- **Severity:** MEDIUM (evidence preservation fail-open + order-dependent result)
- **File:line:** `scripts/policy_transfer.py:1376-1382` (dedupe keeps only the **first** occurrence and its
  `kind`) and `1392-1399` (the non-droppable/protected decision uses that first kind).
- **What is wrong:** Duplicate identifiers with conflicting kinds are collapsed before classification, so a
  later `evidence`/`stop_rule`/`scientific_fact`/unknown-kind declaration is invisible and the id can be
  dropped. A 20 000-trial fuzz over ids/kinds/budgets found 458 cases where the returned `status == "OK"`
  and `dropped` contains an id that is also declared `evidence`/`stop_rule`/`scientific_fact`/`mystery`.
- **Reproduction:**
  ```python
  import policy_transfer as pt
  print(pt.compression_report([("X1","policy"),("X1","evidence")], 0))
  print(pt.compression_report([("X1","evidence"),("X1","policy")], 0))
  ```
- **OBSERVED:**
  ```
  [M3.dup] {"status": "OK", "kept": [], "dropped": ["X1"], "reasons": ["丢弃 policy: ['X1']"]}
  [M3.dup_reversed] {"status": "REFUSED", "kept": ["X1"], "dropped": [], "reasons": ["预算 0 < 必须保留的 1 条…"]}
  ```
  Fuzz summary: `violations: 458` (all of type `protected-dropped`, i.e. an evidence/stop_rule/
  scientific_fact/unknown-kind declaration was dropped).
- **Expected:** an identifier declared non-droppable anywhere must be forced; the verdict must not depend on
  input order. (The `kept ∪ dropped` partition itself stays complete and disjoint — see “not a bug”.)
- **Exploitability:** Medium: reordering or duplicating an id lets an evidence item be reported as dropped
  under a benign kind.

### M4 — attacker-controlled regex in conditions → catastrophic backtracking (ReDoS) hangs the gate

- **Severity:** MEDIUM (availability of a read-only safety gate; CLI/loop DoS)
- **File:line:** `scripts/policy_transfer.py:747-751`
  (`ok = ... re.fullmatch(str(value), actual)`).
- **What is wrong:** the policy supplies both the regex and the target field name; `re` has no timeout and
  neither the pattern nor the subject is length-bounded.
- **Reproduction:**
  ```python
  import time, common
  s = common.fixture_state(); s["contract"]["goal"] = "a"*28 + "b"
  t = time.time()
  common.transfer(common.allow_policy(applicable_conditions=[
      {"field":"contract.goal","op":"regex","value":"(a+)+$"}]), s, s)
  print(round(time.time()-t, 2))
  ```
- **OBSERVED:** `n=28 → 9.33 s`; doubling the input doubles the exponent
  (`n=20 → 0.04 s`, `n=24 → 0.74 s`, `n=26 → 2.61 s`, `n=28 → 9.30 s`); `n=40` did not finish within 25 s.
- **Expected:** reject or bound regex evaluation (fail-closed diagnostic instead of hanging).
- **Exploitability:** Medium: a single policy JSON stalls the loop / preset evaluation.

### M5 — CLI exit code for `compress` is 0 on `REFUSED`

- **Severity:** MEDIUM
- **File:line:** `scripts/policy_transfer.py:1524-1529` (`return _emit(compression_report(...))`, defaults
  to `EXIT_OK`), versus `transfer` (`1513`, `EXIT_HARD` on BLOCK) and `layers` (`1493-1494`, `EXIT_HARD` on FAIL).
- **What is wrong:** a refusal — the very thing this command exists to detect — is reported as success to any
  exit-code-driven caller.
- **Reproduction:**
  ```bash
  python3 scripts/policy_transfer.py compress --items '[["E1","evidence"],["P1","policy"]]' --budget 0; echo "exit=$?"
  ```
- **OBSERVED:** JSON with `"status": "REFUSED"` and `exit=0` (compare `transfer` BLOCK `exit=3`,
  `layers` FAIL `exit=3`).
- **Expected:** `REFUSED` → `EXIT_HARD` (3), as the other verdict commands do.
- **Exploitability:** Medium for CI/automation: a lossy compression refusal is indistinguishable from success.

### M6 — PT9 broad-scope evidence is self-attested / unauthenticated

- **Severity:** MEDIUM
- **File:line:** `scripts/policy_transfer.py:1147-1163` (`_evidence_projects` trusts policy keys),
  `1206-1215` (the `independent` short-circuit; the “≥2 qualified outcomes” alternative is never required
  once a single string is present), and `1178-1187` (records are the tolerant-loaded, unauthenticated ones).
- **What is wrong:** a `global`/`cross_project` scope is justified entirely by policy-declared
  `evidence_projects`/`projects` plus at least one free-text `independent_evaluation_refs` string (or by two
  unauthenticated outcome lines in any JSONL). No link to real trajectories/canonical evidence is checked.
  `evidence_level` is also optional and non-string values are treated as absent (`1114-1125`).
- **Reproduction:**
  ```python
  import common
  s = common.fixture_state()
  p = common.allow_policy(scope={"kind":"global"}, evidence_projects=["A","B"])
  print(common.transfer(p, s, s, source_trajectories=[], records=[])["status"])
  ```
- **OBSERVED:** `[L3.self_attested_global] {"status": "ALLOW", "codes": []}` — zero real records.
  With `records=[{"record":"outcome","project":"A","evidence_qualification":"qualified"},
  {"record":"outcome","project":"B","evidence_qualification":"qualified"}]` and no refs → also `ALLOW`.
- **Expected:** the broad-scope justification should be anchored to verified trajectory/evidence records,
  not to policy-supplied strings.
- **Exploitability:** Medium; `policy_evolution`-proposed policies must pass PE3/PE8 first, but the gate API
  and the CLI accept arbitrary JSON.

### L1 — PT10 ignores any bare-string counterexample matching `word+digit`

- **Severity:** LOW/MEDIUM
- **File:line:** `scripts/policy_transfer.py:931-932`
  (`elif re.fullmatch(r"[A-Za-z]+[0-9][A-Za-z0-9\-]*", text): continue`).
- **What is wrong:** the string is assumed to reference a canonical object without checking that it exists,
  so an unverifiable counterexample is treated as provably irrelevant (fail-open), while a Chinese or
  hyphen-only string correctly fails closed.
- **Reproduction:** `common.transfer(common.allow_policy(counterexamples=["Refuted1"]), s, s)`
- **OBSERVED:** `[L1.bare_string_CE] {"status": "ALLOW", "codes": []}` (control `"reframe"` → BLOCK PT10).
- **Expected:** an unresolvable id reference should be a fail-closed PT10 diagnostic.
- **Exploitability:** Low: only relevant when counterexamples are written as bare strings.

### L2 — PT1 does not fire for a policy candidate carrying canonical scientific arrays

- **Severity:** LOW (separation guarantee is weaker than documented)
- **File:line:** `scripts/policy_transfer.py:279-283` — only `scientific_facts`, `scientific_memory`,
  `canonical_facts`, `facts`, `evidence_layer` are checked; `evidence`, `claims`, `hypotheses`,
  `assumptions`, `experiments`, `failures`, `uncertainties`, `mechanisms` are not.
- **What is wrong:** a candidate policy may embed full scientific memory and still be reported
  `separation_ok: True` (nothing leaks into `scientific_memory` — `_scientific_layer` reads the state only —
  but the PT1 “no layer mixing” rule silently passes).
- **Reproduction:**
  ```python
  import common, policy_transfer as pt
  L = pt.memory_layers(common.fixture_state(), policy_records=[
      {"id":"P","scope":{"kind":"structure"},"evidence":[{"id":"E1"}],
       "hypotheses":[{"id":"H9"}],"mechanisms":[{"id":"M1"}]}])
  print(L["separation_ok"], L["diagnostics"])
  ```
- **OBSERVED:** `[L2.PT1_gap] {"separation_ok": true, "diagnostics": []}`
- **Expected:** PT1 for any embedded canonical scientific section.

### L3 — Uncaught exceptions in the CLI and public helpers instead of diagnostics

- **Severity:** LOW
- **File:line:** `scripts/policy_transfer.py:1466-1470` + `1506` (`_read_json` → `json.loads` raises);
  `1490/1499/1507/1519` (`cg.load_state` raises `CognitionError`); `1355` (`max_state_version_gap`
  type error); `policy_evolution.py:957` (`candidate.get` before the `try`).
- **Reproduction:**
  ```bash
  python3 scripts/policy_transfer.py transfer --policy 'not-a-json-file' --target-state /tmp/ptrepro/state.json; echo "exit=$?"
  python3 scripts/policy_transfer.py layers --state /tmp/does-not-exist.json 2>&1 | tail -1; echo "exit=$?"
  ```
- **OBSERVED:** both print a Python traceback (`json.decoder.JSONDecodeError`,
  `cognition.CognitionError: state file not found`) and exit `1`; no `{"status":"INVALID",...}` payload.
  `policy_evolution.cross_project_transfer_allowed([], state, current_route="A")` →
  `AttributeError: 'list' object has no attribute 'get'` (raised before the fail-closed `try`).
- **Expected:** the API/CLI contract is machine-readable diagnostics; unparseable input → `INVALID`/`EXIT_ERROR`.
- **Exploitability:** Low (crash, not a bypass), but it breaks the “exceptions → diagnostics” convention.

### L4 — Minor informational gaps (confirmed, low impact)

- `compression_report` discards the “unknown kind” reasons when `budget >= len(items)` (early return at
  `1401-1403`): `compression_report([("X1","mystery"),("E1","evidence")], 5)` → `reasons: []`, so the
  unknown kind is silently accepted.
- `_evidence_level` (`1114-1125`) ignores non-string levels (`123`, `["independent"]`, `True` → treated as
  absent): with `scope.kind="global"`, `evidence_level=123` plus self-declared projects/refs → ALLOW.
- `_normalize_scope` (`992-998`) accepts `scope={"kind":"structure"}` with no `structures` list; the claimed
  structure is never checked.
- `_counterexample_errors` (`921-923`) builds the target signature **without** `target_index`, while
  `_transfer_similarity` uses it (`1024`). In principle a counterexample covering index-only structure is
  missed; I could not turn this into a BLOCK→ALLOW in practice because both-sides-declared axes still gate
  match (`524-526`) — listed as SUSPECTED, not confirmed.

---

## SUSPECTED (not fully reproduced / not exploitable as a bypass)

- **S1 — `_counterexample_errors` ignores `target_index`** (`policy_transfer.py:921` vs `1024`). Reachable
  asymmetry, but my attempt (counterexample `operators:["weird_op"]` with the operator only in
  `target_index`) still returned `PT4` because `structural_match` requires a shared axis when both sides
  declare axes. Not shown to convert BLOCK→ALLOW; inconsistent API, worth fixing.
- **S2 — `scope` vocabulary mismatch.** `policy_evolution` writes `scope.scope_kind` /
  `scope.problem_structure` (`policy_evolution.py:401-402`), while `policy_transfer._normalize_scope` reads
  `kind`/`type`/`level` (`993`), so a genuine `policy_evolution` candidate is always PT3-blocked by
  `transfer_decision`. This is fail-closed (over-block), not a bypass — but it means `cross_project_transfer_allowed`
  never actually exercises PT1–PT10 on real policies; the H5 provenance hole is what lets them through instead.
- **S3 — `memory_layers` PT1 blacklist is name-based** (`state.policy_layer_extra` or any unlisted key
  evades it). Inherent to a blacklist; noted only.

---

## Checked and NOT a bug

- **Threshold is not reachable from policy data.** `policy`/`source_signature`-supplied `threshold`/
  `similarity_threshold` keys are ignored; the effective threshold is still `0.5`
  (`policy-supplied threshold keys -> BLOCK ['PT4','PT5'] threshold used: 0.5`). It is only settable via the
  explicit `threshold=` kwarg.
- **Jaccard denominator when the union is empty** is correct: `score = 0.0`, `structural_match=False`
  (`structure_similarity({}, {})` → `{'score': 0.0, 'structural_match': False}`; `{}` vs a real state → 0.0).
- **Two truly empty states get no match**; only sharing a `structural_signature` token produces a match (M2).
- **`invalidated_subjects` uses exact set membership, not substring**: `["H"]` does not match `H1`,
  `["H1"]`/`["U1"]`/`["E1"]` do (`invalidated ['H'] -> []`). The task's substring concern does not materialise.
- **`compression_report` never returns `REFUSED` with a non-empty `dropped`**, and for `OK` results the
  `kept ∪ dropped` set equals the deduped identifiers and is disjoint (20 000-trial fuzz: zero
  `REFUSED-nonempty-dropped`, zero `overlap`, zero `not-cover` violations; the only failures were the
  duplicate-id drops in M3).
- **No input mutation:** `transfer_errors`/`transfer_decision`/`structural_signature`/`compression_report`
  do not mutate their arguments (the repo test `test_transfer_never_mutates_its_inputs` passes; I also ran
  the calls with deep-compared snapshots).
- **Non-dict `policy`/`target_state` fail closed:** `None`/`[]`/`"x"`/`42` → `BLOCK` with PT1/PT3/PT4
  (and PT5/PT6/PT7 for a bad target).
- **`NaN` threshold** does not create a match (`structural_match=False`), and `gte NaN` fails closed with PT5.
- **Duplicate JSON keys** are resolved by `json.loads` last-wins; no bypass beyond standard JSON semantics.
- **`cross_project_transfer_allowed` exception path is fail-closed** (`except Exception → BLOCK`), and a
  same-route policy correctly returns `NOT_REQUIRED`; the defect is the input discrimination (H5), not this.
- **Ordering**: `boundaries`, `codes`, `negated_mechanisms`, `_proposed_mechanisms`, `_independent_refs`
  and `_evidence_projects` outputs are sorted or order-stable; the only order-dependent result found is M3.

---

## Reproduction harness

All probes were run from `/tmp/ptrepro/` (`common.py` reproduces the repo's `fixture_state`/`allow_policy`
and adds `transfer`/`codes` wrappers; `confirmed.py` prints every labelled line quoted above). Nothing outside
`/tmp` and this report was written.

Key raw transcripts:
```
[confirmation of 46-test baseline]
Ran 46 tests in 0.337s
OK
```
```
$ python3 scripts/policy_transfer.py compress --items '[["E1","evidence"],["P1","policy"]]' --budget 0
{
  "dropped": [],
  "kept": ["E1","P1"],
  "reasons": ["预算 0 < 必须保留的 1 条（evidence/stop_rule/scientific_fact/protected）；拒绝任何有损压缩"],
  "status": "REFUSED"
}
exit=0
```
```
[ReDoS scaling]  n=20 0.04s | n=24 0.74s | n=26 2.61s | n=28 9.30s | n=40 >25s (timeout)
```
