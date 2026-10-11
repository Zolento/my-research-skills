# R8-B permission pipeline

HEAD: 53ea200 (branch `research-idea-pipeline/skill-rsi-dev`)

Audit of the pre-existing permission machinery (`execution_gate`, `experiment_execute.Ledger`,
`evidence_outcome`, `state_check`) and the new round-8 dependency edge in which
`policy_evolution` reuses that machinery for the L3 human-approval ledger (PE15) and the
fair-comparison record (PE16).

Scope note: while this audit ran, the working tree advanced to `0fad638` (the Lead's own sweep).
That commit does **not** touch any line cited below (`_equivalence_errors`, `_read_approvals`,
`approve_l3`, `Ledger`, `scheduler_check`), so every finding below is still present at
`0fad638`; all line numbers are for `53ea200`, the audited HEAD.

---

## CONFIRMED

### B-1 `_equivalence_errors` compares the wrong two arms; a confounded L3 credential reaches VALIDATED and ACTIVE [MED]

`_validation_errors` calls `_equivalence_errors(equivalence, list(per_arm), ...)` — i.e. it
passes every arm in insertion order, **not** the declared `candidate_arm`/`control_arm`
(`policy_evolution.py:1214`). `_equivalence_errors` then hard-codes the compared pair as the
first two entries: `left, right = envs[arm_names[0]], envs[arm_names[1]]`
(`policy_evolution.py:1583`). The controlled-axis equality, the contrast check and the
"undeclared changed variable" check all use only that pair. The verdict, however, is computed
from `candidate_arm`/`control_arm` (`policy_evolution.py:1220`), which are chosen independently
(`policy_evolution.py:1141-1148`).

There is a second, compounding effect: stored artifacts are serialised with `sort_keys=True`
(`policy_evolution.py:864`), so on the promotion re-check the arm order is alphabetical rather
than the submitted order. An author who names the decoy arms so that they sort first defeats the
check at both stages: at submission time because the decoys are listed first, and at promotion
time because they sort first.

Net effect: an L3 credential whose **actually compared** arms differ on the controlled axis
`model` is accepted as `VALIDATED` and then promoted to `ACTIVE` with PE16 reporting no
diagnostics.

- repro (from component root `research-idea-pipeline/skill-rsi-dev/research-idea-pipeline`):
```sh
python3 - <<'PY'
import copy, sys
sys.path.insert(0, "scripts")
import test_l3_trust_boundary as tlb, rsi_test_support as support

case = tlb.L3Case(methodName="runTest"); case.setUp()
try:
    case.ready()
    cred = case.credential()                      # candidate_arm="policy", control_arm="control"
    pa, ca = cred["per_arm"].pop("policy"), cred["per_arm"].pop("control")
    da, db = copy.deepcopy(pa), copy.deepcopy(ca)
    da["executor"], db["executor"] = "aaa", "aab"
    cred["per_arm"] = {"aaa": da, "aab": db, "policy": pa, "control": ca}
    base = support.equivalence()["arms"]["policy"]["environment"]
    cred["equivalence"] = {"arms": {
        "aaa": {"instance": "i-a", "environment": dict(base, strategy="s1")},
        "aab": {"instance": "i-b", "environment": dict(base, strategy="s2")},
        "policy": {"instance": "i-p", "environment": dict(base, strategy="pi", model="model-a")},
        "control": {"instance": "i-c", "environment": dict(base, strategy="cc", model="MODEL-B")}},
        "contrast_axes": ["strategy"], "paired_task_ids": ["T0", "T1", "T2"]}
    print("compared arms model:", cred["equivalence"]["arms"]["policy"]["environment"]["model"],
          "vs", cred["equivalence"]["arms"]["control"]["environment"]["model"])
    case.approve(cred)
    r = case.record(cred)
    print("record_research_validation ->", r["status"], r.get("codes"))
    print("promote_to_active          ->", tlb.pe.promote_to_active(case.state_path, "P-1")["status"])
finally:
    case.tearDown()
PY
```
- observed:
```
compared arms model: model-a vs MODEL-B
record_research_validation -> VALIDATED None
promote_to_active          -> ACTIVE
```
- expected: `INVALID` with a `PE16` diagnostic naming the `model` axis, because the two arms the
  benefit verdict is computed from are not equivalent. PE16 must check the declared
  `candidate_arm`/`control_arm` pair (or every pair), not the two first dictionary keys.
- source: `scripts/policy_evolution.py:1214`, `scripts/policy_evolution.py:1545-1609`
  (`1583` is the hard-coded pair), `scripts/policy_evolution.py:1141-1148`,
  `scripts/policy_evolution.py:864`.

### B-2 A malformed approval-ledger line crashes the human-approval path instead of yielding a `PE15` diagnostic [MED]

`_read_approvals` verifies the seal chain but its `except` only covers
`(UnicodeDecodeError, OSError, json.JSONDecodeError)` (`policy_evolution.py:1434`). A line that
is valid JSON but not an object (e.g. `[]`) reaches `event.pop("seal", "")`
(`policy_evolution.py:1426`) and raises `TypeError`; an object line with no `seal` is harmless
there (`.pop` has a default) but the same shape breaks the writer path below. Because the reader
is called from `approval_errors`, which is called from the promotion gate
(`policy_evolution.py:1373-1376`), a corrupt/tampered ledger propagates a raw exception out of
the transition instead of the documented "批准账本被篡改" `PE15`.

The new dependency edge has the same problem on the writer side: `approve_l3` wraps
`ex.Ledger(...).locked()` in `except (ValueError, OSError)` (`policy_evolution.py:1490-1496`),
but `experiment_execute.Ledger.locked()` raises `TypeError`/`KeyError` for the same malformed
lines (`experiment_execute.py:51`), and `experiment_execute.main`'s own handler
(`experiment_execute.py:305`) catches those. Reusing the `Ledger` therefore inherited its
exception types without inheriting the CLI's guard.

- repro:
```sh
python3 - <<'PY'
import json, pathlib, shutil, subprocess, sys
SCRIPTS = "scripts"
sys.path.insert(0, SCRIPTS)
import cognition as cg, policy_evolution as pe

BASE = pathlib.Path("/tmp/r8b_b2"); shutil.rmtree(BASE, ignore_errors=True)
route = BASE / "A"; route.mkdir(parents=True)
state = {"_schema": "research-idea-pipeline/research-state@1", "state_version": 3,
         "contract": {"goal": "g", "primary_anchor": "A0", "constraints": [], "resources": {},
                      "out_of_scope": []}, "claims": [], "evidence": [], "assumptions": [],
         "hypotheses": [{"id": "H1", "statement": "h", "status": "active", "validity": "valid",
                         "island": "P1", "operator": "reframe"}], "experiments": [],
         "literature": [], "failures": [],
         "uncertainties": [{"id": "U1", "question": "q", "importance": "high",
                            "uncertainty": "high", "status": "open", "validity": "valid"}],
         "assurance": [], "repairs": [], "narrative_view": {}, "reviews": [],
         "decision": {"verdict": "continue", "rationale": "", "next_phase": "R3"}}
sp = route / cg.STATE_NAME
sp.write_text(json.dumps(state, ensure_ascii=False) + "\n", encoding="utf-8")
digest = pe.freeze_evaluation_rules(sp)["digest"]
pe.propose(sp, {"policy_id": "P-1", "policy_schema_version": "1", "parent_policy_id": None,
    "status": "PROPOSED", "scope": {"scope_kind": "local", "problem_structure": "reframe-loop"},
    "applicable_conditions": [{"kind": "min_open_uncertainties", "value": 1}],
    "strategy_changes": [{"kind": "same_tier_preference", "prefer_action": "R2"}],
    "supporting_trajectory_ids": ["DT-1"], "counterexamples": ["c"],
    "expected_effect": {"mechanism": "m", "direction": "up"},
    "revalidation_conditions": ["r"], "evaluation_refs": [], "rollback_target": None,
    "evaluation_rules_digest": digest})
cred = BASE / "credential.json"; cred.write_text('{"policy_id": "P-1"}\n', encoding="utf-8")
adir = pe.approvals_dir(sp); adir.mkdir(parents=True, exist_ok=True)
(adir / "key").write_bytes(b"k" * 32); (adir / "events.jsonl").write_text('[]\n', encoding="utf-8")

cp = subprocess.run([sys.executable, "policy_evolution.py", "approve-l3", "--state", str(sp),
                     "--policy-id", "P-1", "--validation", str(cred), "--approver", "human",
                     "--confirm-human"], cwd=SCRIPTS, capture_output=True, text=True)
print("approve-l3 exit:", cp.returncode, "stdout:", repr(cp.stdout.strip()))
print("stderr tail:", cp.stderr.strip().splitlines()[-1])
try:
    pe.approval_errors(sp, policy_id="P-1", credential_digest="x")
except Exception as exc:
    print("approval_errors RAISED:", type(exc).__name__, exc)
PY
```
- observed:
```
approve-l3 exit: 1 stdout: ''
stderr tail: TypeError: 'str' object cannot be interpreted as an integer
approval_errors RAISED: TypeError pop expected at most 1 argument, got 2
```
- expected: `approve-l3` returns `{"status": "INVALID", ..., "codes": ["PE15"]}` (exit 3) with a
  "批准账本被篡改/不可读" diagnostic, and `approval_errors` returns a `PE15` Diagnostic — matching
  the round-8 record's documented behaviour for a tampered approval ledger.
- source: `scripts/policy_evolution.py:1421-1435`, `scripts/policy_evolution.py:1490-1496`,
  `scripts/policy_evolution.py:1373-1376`, `scripts/experiment_execute.py:51`,
  `scripts/experiment_execute.py:305`.

### B-3 `Ledger` crash windows permanently brick the ledger with no repair path [MED]

`append` fsyncs `events.jsonl` first and only then renames `.head.pending` over `head`
(`experiment_execute.py:71-77`). If the process dies, the machine loses power, or the rename is
not durable before that point, the ledger recovers with a valid event chain but a stale `head`.
`locked()` then raises `LEDGER_TRUNCATED_OR_INCOMPLETE` (`experiment_execute.py:55`) on **every**
subsequent call and nothing ever rewrites `head`, so the ledger is permanently unusable. The
same applies to a crash after the key is created but before `events.touch`
(`experiment_execute.py:45-47`), which permanently raises `LEDGER_HISTORY_MISSING`.

This affects both ledgers built on this machinery: the execution ledger (no further
`issue`/`run`) and the round-8 approval ledger (no further `approve_l3`, and PE15 can never be
satisfied, so no promotion). Fail-closed, but a durable availability failure on the RSI
promotion path.

- repro:
```sh
python3 - <<'PY'
import sys, json, shutil
from pathlib import Path
sys.path.insert(0, "scripts")
import experiment_execute as ex, evidence_outcome as eo

d = Path("/tmp/r8b_b3"); shutil.rmtree(d, ignore_errors=True)
with ex.Ledger(d).locked() as L:
    L.append({"kind": "e1"})                 # events.jsonl fsynced; head = digest(e1)

# simulate a crash after events.jsonl was fsynced but before the head rename became durable
lines = (d / "events.jsonl").read_text(encoding="utf-8").splitlines()
(d / "head").write_text(eo.digest(json.loads(lines[0])), encoding="ascii")

for attempt in (1, 2):
    try:
        with ex.Ledger(d).locked() as L:
            print("reopen OK")
    except Exception as exc:
        print(f"reopen {attempt}: {type(exc).__name__}: {exc}")
PY
```
- observed:
```
reopen 1: ValueError: LEDGER_TRUNCATED_OR_INCOMPLETE
reopen 2: ValueError: LEDGER_TRUNCATED_OR_INCOMPLETE
```
- expected: either the append should be ordered so the tail is self-describing without a side
  file (e.g. seal the head digest into the next `previous`, or make `head` recoverable from the
  chain), or `locked()` should offer an explicit, logged recovery/repair path so a durable crash
  does not permanently disable execution and L3 approval.
- source: `scripts/experiment_execute.py:42-55`, `scripts/experiment_execute.py:68-78`.

### B-4 PE16's required axes are presence-only and disjoint from `execution_gate.FAIR`; an all-null record passes [LOW]

`_equivalence_errors` only checks that each `_REQUIRED_EQUIVALENCE_AXES` key **exists**
(`policy_evolution.py:1584-1587`), never that it carries a value. An equivalence record whose
six controlled axes are all `null` (with a single differing declared contrast axis) is accepted,
so it proves nothing about model/harness/tools/data/budget/task equivalence. Separately, the
required set (`model, harness, tools, visible_data, budget, task_ids`) is disjoint from
`execution_gate.FAIR` (`compute_hours, data_split, optimization.tuning_trials`,
`execution_gate.py:15`): an L3 record that never mentions tuning trials, compute hours or the
data split passes, even though the gate requires those axes to be present and equal
(`execution_gate.py:202-203`, reached via `at()` which raises on absence). The docstring's claim
that PE16 "mirrors the existing execution_gate comparison semantics"
(`policy_evolution.py:1549-1550`) holds only for the "undeclared changed variable" rule, not for
the axis set.

- repro:
```sh
python3 - <<'PY'
import sys
sys.path.insert(0, "scripts")
import policy_evolution as pe, execution_gate as eg
AXES = pe._REQUIRED_EQUIVALENCE_AXES
null_scaffold = {a: None for a in AXES}
rec = {"arms": {"policy": {"instance": "i1", "environment": dict(null_scaffold, strategy="s1")},
                "control": {"instance": "i2", "environment": dict(null_scaffold, strategy="s2")}},
       "contrast_axes": ["strategy"], "paired_task_ids": ["T1"]}
print("all-null axes accepted:", pe._equivalence_errors(rec, ["policy", "control"], {}))
print("FAIR (gate)            :", eg.FAIR)
print("PE16 required axes     :", AXES)
PY
```
- observed:
```
all-null axes accepted: []
FAIR (gate)            : ('compute_hours', 'data_split', 'optimization.tuning_trials')
PE16 required axes     : ('model', 'harness', 'tools', 'visible_data', 'budget', 'task_ids')
```
- expected: PE16 should require non-empty values for the controlled axes and should include the
  gate's fairness axes (at least `tuning_trials`-equivalent), or the two definitions should be
  reconciled in one place so "fair comparison" has a single meaning.
- source: `scripts/policy_evolution.py:779`, `scripts/policy_evolution.py:1545-1609`,
  `scripts/execution_gate.py:15`, `scripts/execution_gate.py:202-203`.

### B-5 `scheduler_check` raises on a malformed `outcome_analysis` instead of returning FAIL [LOW]

`scheduler_check` calls `state_check.check_state(state)` and appends `STATE_INVALID`, but does not
return early (`execution_gate.py:363`). It then calls `actual_eig(x['outcome_analysis'])`
(`execution_gate.py:373`) with no guard, and `actual_eig` indexes
`receipt['audit_trail']['state_delta']` (`execution_gate.py:341`). A malformed receipt therefore
raises `TypeError` out of a function whose contract is to return
`{'status': 'FAIL'|'PASS', 'errors': [...]}`. `experiment_execute` and `state_check` wrap the
call, but `strategy_memory.scheduler_verdict` does not (`scripts/strategy_memory.py:998`).

- repro:
```sh
python3 - <<'PY'
import json, sys
sys.path.insert(0, "scripts")
import execution_gate as eg
s = json.loads((eg.ROOT/'examples/preflight-identifiability/ct-mri.json').read_text(encoding='utf-8'))['state']
x = s['experiments'][-1]
x.update(status='done', outcome_analysis={"audit_trail": "x", "analysis": {"experiment_id": x['id']}})
delta = {"claim_status_changes": [], "uncertainty_changes": [], "hypothesis_status_changes": [],
         "new_uncertainties": [], "unexpected_observations": 0}
sched = {"state_version": s['state_version'], "next_actions": [],
         "eig_calibration": {"records": [{"experiment": x['id'], "predicted_information_gain": "high",
                                          "observed_delta": delta, "actual_information_gain": "zero"}]}}
try:
    print("returned:", eg.scheduler_check(s, sched))
except Exception as exc:
    print("RAISED:", type(exc).__name__, exc)
PY
```
- observed:
```
RAISED: TypeError string indices must be integers, not 'str'
```
- expected: `{'status': 'FAIL', 'errors': [..., 'STATE_INVALID']}`; `actual_eig` should be
  guarded (or skipped) once the state is known invalid.
- source: `scripts/execution_gate.py:359-374`, `scripts/execution_gate.py:339-356`,
  `scripts/strategy_memory.py:998`.

---

## SUSPECTED

- **S-1 Tail truncation of the approval ledger is undetected.** `_read_approvals` verifies the
  chain and `previous` pointers but never consults `head`, unlike `Ledger.locked()`
  (`policy_evolution.py:1416-1436` vs `experiment_execute.py:54-55`). Deleting the last
  `events.jsonl` line leaves a self-consistent chain. Direction is fail-closed (deletion cannot
  create an approval), so this is a divergence from the "reuse `Ledger`" claim rather than a
  bypass; it also means the reader does not see the crash/truncation state B-3 detects.
- **S-2 The ledger key is trusted without permission/length checks.** `locked()` reads the key
  with `read_bytes()` and never checks its mode or length (`experiment_execute.py:49`). A key
  copied or `chmod 0644`'d still verifies (confirmed: `Ledger` reopens a 0644 key successfully),
  so any local user who can read the key can seal forged events without route write access. This
  is adjacent to the documented "route writer can forge the ledger" limitation (round8 §6.1),
  but extends it from writers to readers, so it is worth a `stat.S_IMODE(key).st_mode == 0o600`
  / 32-byte check. No exploit was built.
- **S-3 `evidence_outcome.digest` is not type-injective.** A `str` is hashed raw, everything else
  via `json.dumps` (`evidence_outcome.py:38-40`), so `digest("123") == digest(123)` and
  `digest("null") == digest(None)`. No reachable confusion was found in this scope (the `Ledger`
  always hashes dicts), but the property is easy to trip over in future bindings.

---

## NOT-BUGS (checked, clean)

- **`Ledger` chain integrity.** Deleted middle event, reordered events, duplicated event,
  rewritten seed `policy` event, key replaced with 32 random bytes, key replaced with an empty
  file → all raise `LEDGER_TAMPERED`. Verified with a probe building each corruption and
  re-opening the ledger.
- **Concurrent creation of a brand-new ledger directory.** Eight threads opening the same fresh
  directory concurrently all succeeded with exactly one seeded `policy` event (flock covers the
  key/events creation window at `experiment_execute.py:38-48`). Cross-process/cross-host flock
  remains unverified and is a documented limitation (round8 §6.5), so it was not re-tested.
- **`run`/`issue` receipt lifecycle.** `FORGED_RECEIPT` (flipped seal), `UNKNOWN_OR_USED_RECEIPT`
  (well-formed but never-issued receipt), `EXPIRED_RECEIPT` (both `now < issued_at` and
  `now >= expires_at`), `RECEIPT_CONTENT_MISMATCH` (manifest file content changed after issue),
  and replay against a cloned experiment id are all refused. A preview (`execute=False`) consumes
  nothing and leaves exactly zero `consume` events; a subsequent real run succeeds and a second
  real run gets `UNKNOWN_OR_USED_RECEIPT`. Two concurrent `execute=True` calls on one receipt
  produced exactly one `consume` event and one `UNKNOWN_OR_USED_RECEIPT` — the single-use check
  and the budget recheck both run inside the ledger lock (`experiment_execute.py:205-254`).
- **Historical `dry_run: true` consume events** are ignored by the single-use check
  (`experiment_execute.py:212-214`), matching the stated compatibility intent.
- **`_comparison_errors` crash-on-bad-input.** It is only reachable from `peig` after
  `schema_errors` (`execution_gate.py:173-196`). Fuzzed malformed protocols (`comparisons`
  object, missing `compute_hours`, `predictions=None`, `optimization=None`, `arms=None`,
  non-string `training_dof`, `lr=NaN`, non-numeric `budget_hours`, unknown arm references,
  `risk_controls=None`) all returned `HOLD` with schema diagnostics and never raised. The
  `None`-vs-missing and dotted-key `flatten` edge cases are unreachable because the arm schema
  forbids additional properties and requires typed leaves, and because `peig` validates the
  schema first.
- **Malformed-state fuzzing for the documented entry points.** `peig`, `state_check.check_state`
  and `scheduler_check` (schema-invalid input) returned `HOLD`/`FAIL`/`ok=False` without
  raising for `execution_record` receipts of `None`/`{}`/list, `experiments=[{}]`,
  `experiments=None`, `claims=[{}]`, `scheduler={}`, `scheduler=None`. `state_check` explicitly
  wraps `evidence_outcome.state_errors` and `execution_gate.state_errors`
  (`state_check.py:1760-1771`); B-5 is the one crash path that escapes that wrapping.
- **`gpu_devices` empty.** The schema requires `minItems: 1`
  (`schemas/execution-manifest.schema.json`), so `hours*3600/len(manifest['gpu_devices'])`
  (`experiment_execute.py:261`) cannot divide by zero with a schema-validated manifest.
- **`human_exception` cannot masquerade as a formal PASS.** A formal protocol with
  `human_exception` set yields `HOLD` with
  `HUMAN_EXCEPTION: cannot masquerade as formal PASS` (`execution_gate.py:239`); PASS is only
  produced when `formal` and `not errors` (`execution_gate.py:244`). For non-formal modes the
  status is `PILOT_ONLY`. Expiry, scope and `max_hours` are enforced at issue
  (`experiment_execute.py:191-193`) and expiry is re-checked at run
  (`experiment_execute.py:239`); the protocol itself is pinned by the receipt binding
  (`experiment_execute.py:226`), so it cannot be swapped between issue and run. Note the
  exception can only further restrict an already-passing gate — it can never lift a HOLD, because
  `issue` returns on `gate['status'] == 'HOLD'` before reaching the exception block
  (`experiment_execute.py:190-193`).
- **PE15 vs `human_exception` semantics.** They are separate mechanisms on separate paths
  (L3 policy promotion vs experiment execution) and there is no bypass between them: no automated
  entry calls `approve_l3` (only the CLI at `policy_evolution.py:2680`, the module selftest, and
  `rsi_test_support`), and `approval_errors` is re-run against the stored credential on every
  VALIDATED→ACTIVE gate (`policy_evolution.py:1373-1376`), bound to the credential digest,
  policy signature, rules digest and expiry. No contradiction with `human_exception` was found.
