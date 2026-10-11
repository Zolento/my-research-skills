# R8-A approval surface

HEAD: 53ea2006b010b98d323e6be04467aa4b5998f8af
Scope: `scripts/policy_evolution.py` L3 approval + artifact-store machinery (`approve_l3`,
`approval_errors`, `approval_events`, `_read_approvals`, `_approval_seal`,
`_approval_event_digest`, `approvals_dir`, `policy_lock`, `_store_artifact`, `_read_artifact`,
`_append`, `begin_bounded_trial` `attempt`, `record_research_validation`,
`_artifact_gate_errors` `SCHEMA_RESEARCH_VALIDATION` branch, `latest_evaluation_artifact`) and
the reuse of `experiment_execute.Ledger`.

> **Working-tree note.** At audit time the worktree copy of `policy_evolution.py` had
> uncommitted, unrelated edits (frozen-rule schema validation, +50 lines). All line numbers and
> reproductions below are against a clean `HEAD` export, not the dirty worktree:
>
> ```sh
> rm -rf /tmp/r8a-head && mkdir -p /tmp/r8a-head
> git -C <worktree> archive HEAD research-idea-pipeline | tar -x -C /tmp/r8a-head
> cd /tmp/r8a-head/research-idea-pipeline
> ```
>
> **POST-AUDIT HEAD MOVEMENT (important).** While this audit ran, the worktree advanced from the
> pinned `53ea200` to `389e36b` (`0fad638` "close four gaps found by the Lead's own review
> sweep", then `389e36b` round-nine record). `0fad638` already fixes **A-1** (it deletes the
> `restoring` exemption, re-presents the stored L3 credential on restore, and pre-validates
> rollback atomically). Re-run against `389e36b`: A-1 now returns `INVALID`/`PE11`, while
> **A-2, A-3, A-4, A-5, A-6 and A-7 still reproduce unchanged** (see per-finding status). A-1 is
> kept below as evidence for the pinned HEAD but must not be re-fixed.
>
> I read `.dev/round7/record.md` and `.dev/round8/record.md` first. Round 8 §1.1/§1.3 claims
> every VALIDATED/ACTIVE path (including `rollback()`'s `SUPERSEDED → ACTIVE` restore) re-runs
> `_artifact_gate_errors()` and re-checks the approval's existence/expiry/seal/binding, and §6
> documents only the "route-write attacker can forge the ledger and its key" limitation. None of
> the findings below is covered by those documented limitations.

Reproductions share one helper file. Write it once, then run the per-finding snippets from the
component root:

```sh
cat > /tmp/r8a_repro_lib.py <<'PY'
"""Shared setup for the R8-A approval-surface reproductions (run from the component root)."""
import sys, pathlib, json
sys.path.insert(0, "scripts")
import cognition as cg, policy_evolution as pe, research_replay as rr, rsi_test_support as support

def store():
    import tempfile
    tmp = tempfile.mkdtemp(); route = pathlib.Path(tmp)/"A"; route.mkdir(parents=True)
    sp = route/cg.STATE_NAME
    sp.write_text(json.dumps({"_schema":"research-idea-pipeline/research-state@1",
        "state_version":3,"contract":{"goal":"g","primary_anchor":"A0","constraints":[],
        "resources":{},"out_of_scope":[]},"claims":[],"evidence":[],"assumptions":[],
        "hypotheses":[{"id":"H1","statement":"h","status":"active","validity":"valid",
                       "island":"P1","operator":"reframe"}],"experiments":[],"literature":[],
        "failures":[],"uncertainties":[{"id":"U1","question":"q","importance":"high",
                       "uncertainty":"high","status":"open","validity":"valid"}],
        "assurance":[],"repairs":[],"narrative_view":{},"reviews":[],
        "decision":{"verdict":"continue","rationale":"","next_phase":"R3"}})+"\n", encoding="utf-8")
    pe.freeze_evaluation_rules(sp); return sp, pathlib.Path(tmp)/"work"

def report():
    rep = rr.run_suite(rr.adversarial_cases()[:4], arms=["rsi_full","full_cie"], runs=2)
    for arm, shift in (("rsi_full",0.5),("full_cie",-0.05)):
        for row in rep["per_arm"][arm]["results"]:
            row["evaluation"]["metrics"]["search_efficiency"]={"value":round(0.5+shift,4)}
        block=rep["per_arm"][arm]; block["dimensions"]={}
        for name in rr.METRIC_DIMENSIONS:
            vals=[r["evaluation"]["metrics"][name]["value"] for r in block["results"]
                  if r["evaluation"]["metrics"][name]["value"] is not None]
            block["dimensions"][name]={"mean":round(sum(vals)/len(vals),4) if vals else None,
                                       "min":min(vals) if vals else None,"max":max(vals) if vals else None}
    return rep

def propose(sp, pid):
    pe.propose(sp, {"policy_id":pid,"policy_schema_version":"1","parent_policy_id":None,
        "status":"PROPOSED","scope":{"scope_kind":"local","problem_structure":"reframe-loop"},
        "applicable_conditions":[{"kind":"min_open_uncertainties","value":1}],
        "strategy_changes":[{"kind":"same_tier_preference","prefer_action":"R2"}],
        "supporting_trajectory_ids":["DT-1"],"counterexamples":["c"],
        "expected_effect":{"mechanism":"m","direction":"up"},"revalidation_conditions":["r"],
        "evaluation_refs":[],"rollback_target":None,
        "evaluation_rules_digest":pe.evaluation_rules_digest(sp)}, trajectory_support={"DT-1"})

def to_bounded_trial(sp, pid):
    propose(sp, pid)
    pe.transition(sp, pid, "SHADOW", level="L1")
    pe.evaluate_candidate(sp, pid, report())
    pe.begin_bounded_trial(sp, pid, dispatch_evidence={"dispatched":"R2"})

def credential(sp, wd, pid):
    sig = pe.policy_record(pe.load_records(sp)[0], pid)["signature"]
    return support.research_validation(sp, pid, wd, signature=sig,
                                       rules_digest=pe.evaluation_rules_digest(sp))

def to_validated(sp, wd, pid, expires=86400):
    to_bounded_trial(sp, pid)
    cred = credential(sp, wd, pid)
    assert pe.approve_l3(sp, policy_id=pid, credential=cred, approver="human",
                         confirm_human=True, expires_in_seconds=expires)["status"]=="APPROVED"
    assert pe.record_research_validation(sp, pid, cred)["status"]=="VALIDATED"
    return cred

def to_active(sp, wd, pid, expires=86400):
    cred = to_validated(sp, wd, pid, expires)
    assert pe.promote_to_active(sp, pid)["status"]=="ACTIVE"
    return cred
PY
```

---

## CONFIRMED

### A-1 `SUPERSEDED → ACTIVE` restore bypasses the human gate entirely [HIGH at audit HEAD 53ea200 — FIXED upstream by 0fad638, do not re-fix]

- repro:
  ```sh
  python3 - <<'PY'
  import sys, time, shutil
  sys.path.insert(0, "/tmp"); import r8a_repro_lib as L
  import policy_evolution as pe
  sp, wd = L.store()
  L.to_active(sp, wd, "P-1", expires=1)      # approval lives one second
  time.sleep(2)
  L.to_active(sp, wd, "P-2", expires=86400)  # supersedes P-1
  shutil.rmtree(pe.approvals_dir(sp))        # no approval ledger exists at all
  print("events after wiping the approval ledger:", pe.approval_events(sp))
  r = pe.transition(sp, "P-1", "ACTIVE")     # public entry, no authority token, no evidence
  print("transition(SUPERSEDED->ACTIVE):", r.get("status"), "level=", r.get("level"), r.get("diagnostics"))
  print("statuses:", pe.latest_status(pe.load_records(sp)[0]))
  print("active policy:", (pe.active_policy(pe.load_records(sp)[0]) or {}).get("policy_id"))
  PY
  ```
- observed:
  ```
  events after wiping the approval ledger: []
  transition(SUPERSEDED->ACTIVE): ACTIVE level= L3 []
  statuses: {'P-1': 'ACTIVE', 'P-2': 'SUPERSEDED'}
  active policy: P-1
  ```
- expected: `ACTIVE` is a gated target. Round 8 states that ACTIVE re-verifies the approval
  (present, unexpired, seal intact, still bound to the same credential). A superseded L3 policy
  whose approval has expired *and whose entire approval ledger has been deleted* must not return
  to ACTIVE (level L3, consumed by `advice_from_active_policy`). The CLI blocks
  `transition --to ACTIVE` (line 2575), but the public Python entry does not, and `rollback()`'s
  `SUPERSEDED → ACTIVE` restore takes the same bypass.
- source: `scripts/policy_evolution.py:1676` (`restoring = current == "SUPERSEDED" and target == "ACTIVE"`),
  `scripts/policy_evolution.py:1683` (`if target in GATED_TARGETS and not restoring:` — this
  skips both the `authority_ok` check *and* `_artifact_gate_errors`),
  `scripts/policy_evolution.py:1778` (`transition`), `scripts/policy_evolution.py:1791`/`1840`
  (`rollback` calls `_transition_locked(..., "ACTIVE", ...)` directly). Confirmed with
  `rollback` as well: after the ledger wipe, `rollback(P-2, to_policy_id="P-1")` returns
  `ROLLED_BACK` and `active_policy` is `P-1`.

### A-2 The approval "credential binding" is read from the artifact itself; a missing binding matches any approval [MED]

- repro:
  ```sh
  python3 - <<'PY'
  import sys, pathlib, json, copy
  sys.path.insert(0, "/tmp"); import r8a_repro_lib as L
  import policy_evolution as pe, cognition as cg, decision_trajectory as dt
  sp, wd = L.store(); L.to_validated(sp, wd, "P-1")
  recs, _ = pe.load_records(sp)
  ref = [(r.get("evidence") or {}).get("evaluation_ref") for r in recs if r.get("to")=="VALIDATED"][-1]
  art = pathlib.Path(ref["path"]); doc = json.loads(art.read_text(encoding="utf-8"))
  forged = copy.deepcopy(doc)
  forged["task_provenance"]["task_id"] = "T-NEVER-REVIEWED"   # a different, never-approved credential
  forged["approval"] = {}                                     # binding fields dropped
  forged["digest"] = cg.digest_of({k:v for k,v in forged.items() if k!="digest"})
  art.write_text(json.dumps(forged, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
  st = pe.candidates_path(sp); head = dt.head_path(st); out=[]; prev=None
  for rec in [json.loads(l) for l in st.read_text(encoding="utf-8").splitlines() if l.strip()]:
      if rec.get("record")=="transition" and rec.get("to")=="VALIDATED":
          rec["evidence"]["evaluation_ref"]["digest"] = forged["digest"]
      rec=dict(rec); rec["seq"]=len(out)+1; rec["previous"]=prev; out.append(rec); prev=dt._digest(rec)
  st.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True)+"\n" for r in out), encoding="utf-8")
  head.write_text(dt._digest(out[-1]), encoding="ascii")
  print("forged artifact approval block:", forged["approval"])
  print("promote_to_active:", pe.promote_to_active(sp,"P-1").get("status"))
  PY
  ```
- observed:
  ```
  forged artifact approval block: {}
  promote_to_active: ACTIVE
  ```
- expected: `_artifact_gate_errors` must recompute the credential digest from the artifact's
  credential content and require it to equal the sealed event's `credential_digest`; a missing
  `approval.credential_digest`/`approval.digest` must fail closed, not degrade to
  "any valid approval for this policy". The same fail-open applies with the real approval block
  left in place: an approval granted for credential A authorizes an artifact describing
  credential B because the digest is never recomputed from B.
  Function-level witness: with one valid approval in the ledger,
  `pe.approval_errors(sp, policy_id="P-1")` (both digests `None`) returns `[]`.
- source: `scripts/policy_evolution.py:1372-1376` (the digest args come from
  `payload["approval"]`, the artifact's own untrusted field),
  `scripts/policy_evolution.py:1523-1526` (`credential_digest is None or ...` /
  `approval_digest is None or ...`).
- honest caveat: the attacker must be able to write the (unkeyed) artifact store and the unkeyed
  `decision-trajectory.jsonl` chain. Round 8 §6.1 already documents that route write access lets
  an attacker forge the approval ledger and its key, so this does not add a *new* capability for
  that attacker. It is reported because the code fails open on an absent/mismatched binding field
  and because the binding is not derived from the credential content, so the HMAC on the
  approval ledger is the only thing protecting the binding and it is bypassed here without any
  key access.

### A-3 Duplicate approval + last-match selection + write-before-transition bricks the dispatch record [MED]

- repro:
  ```sh
  python3 - <<'PY'
  import sys
  sys.path.insert(0, "/tmp"); import r8a_repro_lib as L
  import policy_evolution as pe, cognition as cg
  sp, wd = L.store(); L.to_bounded_trial(sp, "P-1")
  cred = L.credential(sp, wd, "P-1")
  print("approve long-lived :", L.support.approve(sp, "P-1", cred)["status"])
  print("approve 0s (dup)   :", pe.approve_l3(sp, policy_id="P-1", credential=cred,
        approver="human-2", confirm_human=True, expires_in_seconds=0)["status"])
  print("approval_errors    :", [d.render() for d in pe.approval_errors(
        sp, policy_id="P-1", credential_digest=cg.digest_of(cred))])
  before = sorted(p.name for p in pe.evaluations_dir(sp).glob("*.json"))
  r = pe.record_research_validation(sp, "P-1", cred)
  print("record_research_validation:", r.get("status"), r.get("diagnostics"))
  after = sorted(p.name for p in pe.evaluations_dir(sp).glob("*.json"))
  print("orphan artifact written:", after != before)
  print("retry after a fresh valid approval:",
        pe.record_research_validation(sp, "P-1", cred).get("diagnostics"))
  PY
  ```
- observed:
  ```
  approve long-lived : APPROVED
  approve 0s (dup)   : APPROVED
  approval_errors    : []
  record_research_validation: INVALID ['PE15  policy[P-1]  人工批准已过期']
  orphan artifact written: True
  retry after a fresh valid approval: ['PE11  policy[P-1]  该派遣记录已被另一份 L3 凭证使用：派遣记录不可重复使用']
  ```
- expected: with a valid, unexpired human approval present, VALIDATED should either succeed or
  fail for a stable reason; a refused call must not persist a credential artifact. Instead the
  entry accepts an approval via `approval_errors` (any match), then stores an artifact whose
  `approval` block is built from the *last* matching event (`[-1]`, the expired duplicate); the
  `VALIDATED` gate then re-checks the artifact's own (expired) digest and refuses — after the
  artifact has been written. That orphan permanently claims the single-use dispatch record, so
  every retry fails with PE11 even with a fresh valid approval.
- source: `scripts/policy_evolution.py:2186-2195` (`approval_errors` accepts any match, then
  `[...][-1]` picks the last event), `scripts/policy_evolution.py:2233` (`_store_artifact`
  runs before `_transition_locked`), `scripts/policy_evolution.py:2236` (transition/gate runs
  after the write).

### A-4 `policy_id` is unvalidated and is interpolated into an artifact path [MED]

- repro:
  ```sh
  python3 - <<'PY'
  import sys
  sys.path.insert(0, "/tmp"); import r8a_repro_lib as L
  import policy_evolution as pe
  for pid in ("a/b", "a\x00b"):
      sp, wd = L.store()
      print("propose", repr(pid), "->", pe.propose(sp, {"policy_id":pid,"policy_schema_version":"1",
          "parent_policy_id":None,"status":"PROPOSED",
          "scope":{"scope_kind":"local","problem_structure":"reframe-loop"},
          "applicable_conditions":[{"kind":"min_open_uncertainties","value":1}],
          "strategy_changes":[{"kind":"same_tier_preference","prefer_action":"R2"}],
          "supporting_trajectory_ids":["DT-1"],"counterexamples":["c"],
          "expected_effect":{"mechanism":"m","direction":"up"},"revalidation_conditions":["r"],
          "evaluation_refs":[],"rollback_target":None,
          "evaluation_rules_digest":pe.evaluation_rules_digest(sp)}, trajectory_support={"DT-1"})["status"])
      pe.transition(sp, pid, "SHADOW", level="L1")
      try:
          pe.evaluate_candidate(sp, pid, L.report()); print("evaluate -> ok")
      except Exception as e:
          print("evaluate ->", type(e).__name__+":", e)
  PY
  ```
- observed:
  ```
  propose 'a/b' -> PROPOSED
  evaluate -> FileNotFoundError: [Errno 2] No such file or directory: '/tmp/tmpcig50pcg/A/policy/evaluations/a/b.9d527a673c761b48.json.pending'
  propose 'a\x00b' -> PROPOSED
  evaluate -> ValueError: embedded null byte
  ```
- expected: a rejected/unrepresentable `policy_id` should produce a diagnosable refusal, not an
  uncaught traceback from `_store_artifact`. `candidate_errors` only checks that `policy_id` is
  present; `'..'` and absolute paths are caught by the source-freeze/executable scans, but a bare
  `/` component or a NUL byte is not. `_store_artifact` then does
  `directory / f"{policy_id}.{digest16}.json"` with no confinement check. The same crash is
  reachable from `begin_bounded_trial` (trials dir) and through the CLI `evaluate`/`trial`
  commands, regressing the round-7 §9.1 "no raw traceback" fix.
- source: `scripts/policy_evolution.py:861` (`name = f"{payload.get('policy_id')}...."`),
  `scripts/policy_evolution.py:858-868` (`_store_artifact`), call sites
  `scripts/policy_evolution.py:2063` and `:2144`.

### A-5 `_read_approvals` ignores the ledger's truncation `head` [LOW]

- repro:
  ```sh
  python3 - <<'PY'
  import sys
  sys.path.insert(0, "/tmp"); import r8a_repro_lib as L
  import policy_evolution as pe, experiment_execute as ex
  sp, wd = L.store(); L.to_bounded_trial(sp, "P-1")
  L.support.approve(sp, "P-1", L.credential(sp, wd, "P-1"))
  adir = pe.approvals_dir(sp); ev = adir/"events.jsonl"
  lines = ev.read_text(encoding="utf-8").splitlines(keepends=True)
  ev.write_text(lines[0], encoding="utf-8")        # delete the trailing approval event
  print("_read_approvals :", len(pe._read_approvals(sp)[0]), "events, problem:", pe._read_approvals(sp)[1])
  try:
      with ex.Ledger(adir).locked(): print("Ledger.locked(): ok")
  except Exception as e:
      print("Ledger.locked():", type(e).__name__, e)
  PY
  ```
- observed:
  ```
  _read_approvals : 1 events, problem: None
  Ledger.locked(): ValueError LEDGER_TRUNCATED_OR_INCOMPLETE
  ```
- expected: round 8 §1.3 says the approval ledger reuses the `Ledger`'s truncation detection.
  `_read_approvals` re-implements the seal-chain check but never reads or compares the `head`
  digest, so trailing events can be removed without being reported as tampering. Combined with
  A-3, deleting a trailing expired duplicate makes an earlier approval effective again. (Deleting
  a *middle* event is still detected; only trailing truncation is missed.)
- source: `scripts/policy_evolution.py:1408-1436` (`_read_approvals`; no `head` reference),
  versus `scripts/experiment_execute.py:54-55`.

### A-6 `approve_l3` raises an uncaught `OverflowError` for a huge integer lifetime [LOW]

- repro:
  ```sh
  python3 - <<'PY'
  import sys
  sys.path.insert(0, "/tmp"); import r8a_repro_lib as L
  import policy_evolution as pe
  sp, wd = L.store(); L.to_bounded_trial(sp, "P-1")
  try:
      pe.approve_l3(sp, policy_id="P-1", credential=L.credential(sp, wd, "P-1"),
                    approver="h", confirm_human=True, expires_in_seconds=10**400)
  except Exception as e:
      print(type(e).__name__+":", e)
  PY
  ```
- observed:
  ```
  OverflowError: int too large to convert to float
  ```
- expected: `approve_l3` returns `{"status": "INVALID", ...}` for unusable lifetimes, as it does
  for `NaN`/`inf` (those are rejected by the JSON encoder's `allow_nan=False` and caught). A
  public entry should not leak `OverflowError`. `--expires-in` is `type=float`, so the CLI cannot
  reach the large-int case, but `float("1e400") == inf` is still handled via the encoder.
- source: `scripts/policy_evolution.py:1487` (`"expires_at": now + float(expires_in_seconds)`),
  the surrounding `try` at `:1490` catches only `(ValueError, OSError)`.

### A-7 `begin_bounded_trial` writes the trial artifact before validating the transition [LOW]

- repro:
  ```sh
  python3 - <<'PY'
  import sys
  sys.path.insert(0, "/tmp"); import r8a_repro_lib as L
  import policy_evolution as pe
  sp, wd = L.store(); L.propose(sp, "P-1"); pe.transition(sp, "P-1", "SHADOW", level="L1")
  print("trial from SHADOW:", pe.begin_bounded_trial(sp, "P-1", dispatch_evidence={"x":1}).get("status"))
  print("trial artifacts:", [p.name for p in pe.trials_dir(sp).glob("*.json")])
  PY
  ```
- observed:
  ```
  trial from SHADOW: INVALID
  trial artifacts: ['P-1.8716b2fe783979c7.json']
  ```
- expected: a refused entry leaves no artifact (round 7 fixed exactly this for the L3 credential
  path, R7-4). Here `_store_artifact` runs before `_transition_locked`. Under concurrency, five
  refused threads plus the one success produced two trial artifacts, both reporting the same
  `attempt` value — the field whose stated purpose (`:2166-2168`) is to keep attempts distinct.
- source: `scripts/policy_evolution.py:2144` (`_store_artifact`) before
  `scripts/policy_evolution.py:2145` (`_transition_locked`).

---

## SUSPECTED

- **S-1 Artifact filename is only the first 16 hex of the digest** (`policy_evolution.py:861`).
  Two different payloads for the same policy can collide on 64 bits. In practice a full ref
  digest is always stored, so an overwrite is caught by `_read_artifact`'s `ref.digest` check and
  fails closed; a 2^32 collision search is not a practical attack. Not a confirmed bug, but the
  truncation is unnecessary and weakens a content-addressed store.
- **S-2 `_read_approvals` reads the whole `events.jsonl` into memory** (`read_text`,
  `policy_evolution.py:1422`). A very large file is an OOM/DoS vector for every promotion check.
  Unbounded growth of an append-only approval ledger is unlikely but not capped.
- **S-3 The symlink guard covers only `approvals_dir` itself**
  (`policy_evolution.py:1466`), not `approvals/key` or `approvals/events.jsonl`. A file-level
  symlink relocates the ledger and bypasses the stated "approval must stay inside the route"
  intent (it still cannot forge a seal without the key). Within the documented §6.1 limitation,
  but inconsistent with the directory check.
- **S-4 TOCTOU on the symlink check**: `is_symlink()` is evaluated before `policy_lock`; the
  directory could be swapped between the check and `Ledger.locked()`.
- **S-5 A-2 with the genuine approval block retained** (an approval granted for credential A used
  to authorize an artifact describing credential B) passes the same way; the repro shows the
  stricter `approval: {}` variant only to make the missing-binding fail-open explicit.

---

## NOT-BUGS (checked, clean)

1. **Lock ordering / deadlock (H1).** 3 threads × `approve_l3` (takes `policy_lock` then the
   `Ledger` flock) + 3 threads × `approval_events`/`approval_errors` readers, 6 threads with a
   barrier and per-thread joins: `elapsed 0.03s alive: 0 errors: []`, 15 approvals recorded, 16
   events. The approvals ledger is locked only inside `approve_l3` (grep: sole
   `ex.Ledger(approvals_dir(...))` call at `policy_evolution.py:1491`), and all readers already
   hold `policy_lock`, so the order is always policy-lock → ledger-lock. No hang, no inversion.
2. **Concurrent `begin_bounded_trial`.** 6 barrier-synchronized threads: exactly one
   `BOUNDED_TRIAL`, the rest `INVALID`; no duplicate transition. (The orphan artifact is A-7.)
3. **`attempt` counter correctness (H6).** Trial 1 → `attempt=1`; `BOUNDED_TRIAL → HOLD →
   REPLAY_EVALUATED → BOUNDED_TRIAL` → `attempt=2`, with distinct artifact digests/names.
   `attempt` is computed from the record log under `policy_lock` and the transition is appended
   under the same lock, so two *recorded* attempts cannot share a number or collapse to one
   digest.
4. **Digest canonicalization (H2).** `_approval_event_digest` uses bare-hex `eo.digest` and is
   only ever compared against another `_approval_event_digest`; `credential_digest`,
   artifact `digest` and `_read_artifact` all use prefixed `cg.digest_of`. No place mixes the two
   formats; the only vacuity found is the `None` fallback in A-2.
5. **Approval integrity (H4).** Middle-event deletion, seed-event rewrite, zero-length key,
   key replaced by a symlink/longer/shorter content, invalid UTF-8 events, `events.jsonl` as a
   directory, missing key, and duplicate/replayed events all fail closed as "tampered" or "no
   approval" (the chain's `previous` check detects any reordered/replayed event; a replayed
   event would need the HMAC key to be re-sealed).
6. **Expiry semantics (H5).** `expires_in_seconds` NaN/inf → `INVALID` (the `Ledger`'s
   `allow_nan=False` rejects the event and `approve_l3` catches it); zero/negative → `APPROVED`
   but `approval_errors` correctly reports "已过期" and `record_research_validation` returns
   `INVALID`; `expires_at` missing/0 → `float(0) <= now` → expired. `float("nan") <= now` is
   false, but NaN can never be persisted, so the comparison direction is not exploitable via the
   public API. `now` injection is test-only.
7. **`_read_approvals` error handling (H7).** Invalid UTF-8 → `批准账本不可读（UnicodeDecodeError）`;
   key/symlink/length changes → `批准账本被篡改`; directory-instead-of-file and missing key/events
   → empty list with no approval (fail closed). Only trailing truncation is missed (A-5).
8. **Automated self-authorisation (H8).** `approve_l3` is called only by the CLI
   (`policy_evolution.py:2594`) and `--selftest` (`:2876`, `:2921`); no research/promotion entry
   calls it. The `Ledger` seed event is only created when `approve_l3` opens the approvals
   ledger, so no automated path can make `approval_events()` non-empty.
9. **Artifact path confinement.** `_read_artifact` rejects a symlink inside the artifact
   directory that resolves outside it: `['评价产物不在策略存储目录内（拒绝越界路径）']`.
10. **`promote_to_active` re-validation.** For a normal VALIDATED→ACTIVE promotion the gate
    re-reads the artifact, re-runs `_validation_errors`, re-runs `approval_errors` and recomputes
    the level; a tampered-seal/expired approval is refused (consistent with
    `test_promotion_reverifies_the_approval`). The gap is only the `restoring` short-circuit
    (A-1) and the artifact-sourced digest (A-2).
11. **Baseline.** `python3 -m unittest discover -s scripts -p 'test_*.py'` on the clean HEAD
    export exits 0 (no failures; consistent with round 8's 1810 OK / skipped=3).

---

### Suggested priority

A-1 is already closed upstream. For the current HEAD, fix **A-2** first: enforce the credential
binding by recomputing the digest from the artifact's credential content and failing closed when
`approval.credential_digest`/`approval.digest` are missing. Then **A-3** (select the approval that
was actually validated, and validate the staged transition before writing any artifact) and
**A-4** (validate `policy_id` / confine `_store_artifact`). A-5–A-7 are hardening.
