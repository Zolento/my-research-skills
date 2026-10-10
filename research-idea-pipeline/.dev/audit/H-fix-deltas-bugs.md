# H — Fix-delta adversarial review

> **Target:** `research-idea-pipeline/skill-rsi-dev`, component `research-idea-pipeline/`.
> **Fix commits under review:** `2506405` (close latent fail-open defects) and `8887a48` (docs).
> **Prior reports read:** `.dev/audit/E-source-freeze-bugs.md`, `F-policy-transfer-bugs.md`, `G-latent-bugs.md`.
> **Method:** defeated each E/F finding claimed FIXED in `G-latent-bugs.md` §H with a *different* input than
> the original repro; then hunted holes introduced by the fixes and ran the regression gates.
> **All findings below were reproduced against the committed tip `8887a48`**, not the dirty working tree
> (see "Workspace caveat").

## Workspace caveat (important)

At review time the checkout was **dirty**: a concurrent agent had uncommitted edits (and an untracked
`.dev/audit/I-consistency.md`). `git diff` showed:
`SKILL.md`, `presets/memory-consolidation.md`, `presets/strategy-evolution.md`,
`references/skill-rsi-policy.md`, `scripts/decision_trajectory.py`, `scripts/policy_evolution.py`,
`scripts/source_freeze.py`, and 3 test files.

To keep the review attributable to the two fix commits, every finding was re-checked against a pristine
`git archive HEAD` extraction in `/tmp/headscripts`. The committed hashes verified by the probes:

| file | committed `8887a48` sha256 | working-tree sha256 | same? |
|---|---|---|---|
| `scripts/policy_transfer.py` | `44fb99cc…5614c9` | `44fb99cc…5614c9` | yes |
| `scripts/source_freeze.py` | `1eb789cd…a9623d` | `5df816a9…742b495` | **no** (concurrent edit) |
| `scripts/policy_evolution.py` | `6eebc85` (diff blob) | `b708e90…` | **no** (concurrent edit) |

The concurrent `source_freeze.py` edits only touch `_SHELL_TOKENS` / `guard_errors` (they wire
`guard_errors` into `policy_evolution.candidate_errors`); they do **not** touch `guard_write`, the
integrity chain, or the exclusion walk. All H-01…H-05 outputs below were produced against the committed
`/tmp/headscripts` copy.

---

## Severity summary

| ID | Severity | Area | Status |
|---|---|---|---|
| H-01 | MEDIUM | `guard_write` scope | CONFIRMED — incomplete fix of E-1 |
| H-02 | MEDIUM | write whitelist / enforcement | CONFIRMED — incomplete fix of E-11/E-15 |
| H-03 | MEDIUM | `guard_write` argument handling | CONFIRMED — **regression** introduced by 2506405 |
| H-04 | MEDIUM | hard-link detection | CONFIRMED — incomplete fix of E-2 |
| H-05 | LOW | `ALLOWED_WRITE_SCOPES` coverage | CONFIRMED — incomplete fix of E-11 |
| H-06 | HIGH | PT10 counterexample coverage | CONFIRMED — incomplete fix of F-3 |
| H-07 | MEDIUM | expiry / F-6 | CONFIRMED — incomplete fix of F-6 |
| H-08 | MEDIUM | F-5 provenance | CONFIRMED — incomplete fix of F-5 |
| H-09 | LOW | PT8 / F-2 | CONFIRMED — incomplete fix of F-2 |
| S-1 | LOW | integrity append | SUSPECTED (pre-existing, not a fix regression) |

---

## CONFIRMED (reproduced against committed `8887a48`)

### H-01 — MEDIUM — `allowed_roots` given as a *string* widens the whitelist to filesystem root `/`

* **file:line:** `scripts/source_freeze.py:533` (`for allowed in allowed_roots:`), reached from `:558-563`.
* **What is wrong.** The fix removed the old `if allowed_roots:` guard and now iterates `allowed_roots`
  unconditionally. A `str` is iterable, so `allowed_roots="/tmp/.../routes/A"` is iterated
  **character by character**. The character `'/'` resolves via `_resolve_allowed_root("/")` to the real
  root `/`, which becomes one of the accepted roots. Any target under `/` whose *first path component*
  is a member of `ALLOWED_WRITE_SCOPES` is then `ALLOWED` — including `/scheduler.json`, `/policy/x`,
  `/cognition/x`. This is exactly the "scope check looks right but the caller's value is wrong-typed"
  vector the fix was supposed to make fail-closed.
* **Reproduction**
  ```bash
  cd /tmp && python3 - <<'PY'
  import sys, tempfile, pathlib
  sys.path.insert(0, "/tmp/headscripts/research-idea-pipeline/scripts")
  import source_freeze as sf
  t = pathlib.Path(tempfile.mkdtemp()); skill = t/"skill"
  (skill/"scripts").mkdir(parents=True)
  for r in ["SKILL.md","scripts/guard.py"]: (skill/r).write_text("#\n")
  route = t/"proj"/"routes"/"A"; route.mkdir(parents=True)
  for tgt in ["/scheduler.json","/policy/x","/cognition/x","/etc/passwd"]:
      print(tgt, "->", sf.guard_write(tgt, skill_root=skill, allowed_roots=str(route))["code"])
  PY
  ```
* **OBSERVED**
  ```
  /scheduler.json -> ALLOWED
  /policy/x       -> ALLOWED
  /cognition/x    -> ALLOWED
  /etc/passwd     -> OUTSIDE_WRITE_SCOPE
  ```
* **Expected:** a non-sequence `allowed_roots` (or any unparseable item) must fail closed
  (`RESOLUTION_ERROR` / deny), as the docstring claims ("任何解析失败都 fail-closed").
* **Classification:** **incomplete fix** of E-1 (the original `/etc/passwd` default repro is closed; the
  wrong-typed-argument variant is not).

### H-02 — MEDIUM — the write whitelist denies the real runtime trajectory store, and `guard_write` is not called by any production code

* **file:line:** `scripts/source_freeze.py:122-123` (`ALLOWED_WRITE_SCOPES` contains `"decision-trajectory"`),
  `scripts/decision_trajectory.py:55` (`TRAJECTORY_NAME = "decision-trajectory.jsonl"`),
  `scripts/source_freeze.py:533-565` (`guard_write`).
* **What is wrong.** (a) The whitelist entry is the *directory* name `decision-trajectory`, but the
  runtime store is the *file* `<route>/decision-trajectory.jsonl` at the route root. `_write_scope_of`
  returns the bare file name for a top-level file, so the real store is **denied**. (b) `guard_write` has
  **no production caller**: a whole-repo grep finds only `source_freeze.py` itself (its `guard` CLI +
  `selftest`) and `test_source_freeze.py`. The research loop reaches `source_freeze` only through
  `SourceFreeze` (manifest/verify/HOLD), never `guard_write`. The "write whitelist" is therefore
  documentation, not enforcement. (The concurrent uncommitted edit wires `guard_errors` — not
  `guard_write` — into `policy_evolution.candidate_errors`.)
* **Reproduction**
  ```bash
  cd /tmp && python3 - <<'PY'
  import sys, tempfile, pathlib
  sys.path.insert(0, "/tmp/headscripts/research-idea-pipeline/scripts")
  import source_freeze as sf
  t = pathlib.Path(tempfile.mkdtemp()); skill = t/"skill"
  (skill/"scripts").mkdir(parents=True)
  for r in ["SKILL.md","scripts/guard.py"]: (skill/r).write_text("#\n")
  route = t/"proj"/"routes"/"A"; route.mkdir(parents=True)
  for name in ["decision-trajectory.jsonl","cognition/x","scheduler.json",
               "assurance/x",".execution/x","source-integrity.jsonl"]:
      print(name, "->", sf.guard_write(route/name, skill_root=skill, allowed_roots=[route])["code"])
  PY
  grep -rn "guard_write" --include=*.py /tmp/headscripts | grep -v test_
  ```
* **OBSERVED**
  ```
  decision-trajectory.jsonl -> OUTSIDE_WRITE_SCOPE
  cognition/x               -> ALLOWED
  scheduler.json            -> ALLOWED
  assurance/x               -> ALLOWED
  .execution/x              -> ALLOWED
  source-integrity.jsonl    -> ALLOWED
  (grep) scripts/source_freeze.py only — no production caller
  ```
* **Expected:** the whitelist must name the actual store (`decision-trajectory.jsonl`), or `guard_write`
  must be invoked by the runtime write path it claims to guard.
* **Classification:** **incomplete fix** of E-11/E-15 ("`ALLOWED_WRITE_SCOPES` decorative"); the constant is
  now used, but it is both wrong for the real trajectory store and unused at runtime.

### H-03 — MEDIUM — `guard_write(allowed_roots=None)` / non-iterable now raises `TypeError` (regression)

* **file:line:** `scripts/source_freeze.py:533` (`for allowed in allowed_roots:` — no type guard).
* **What is wrong.** The pre-fix code was `if allowed_roots:` then iterate, so `None`/`0` were treated as
  "no scope" and the call returned normally. The fix iterates unconditionally, so `allowed_roots=None`,
  `allowed_roots=42`, or `allowed_roots=some_pathlib.Path` (a non-sequence) now raise an uncaught
  `TypeError` instead of returning a denial dict — violating the documented "任何解析失败都 fail-closed"
  contract and crashing callers.
* **Reproduction**
  ```bash
  cd /tmp && python3 - <<'PY'
  import sys, tempfile, pathlib
  sys.path.insert(0, "/tmp/headscripts/research-idea-pipeline/scripts")
  import source_freeze as sf
  t = pathlib.Path(tempfile.mkdtemp()); skill = t/"skill"
  (skill/"scripts").mkdir(parents=True)
  for r in ["SKILL.md","scripts/guard.py"]: (skill/r).write_text("#\n")
  route = t/"proj"/"routes"/"A"; (route/"cognition").mkdir(parents=True)
  for val in (None, 42, route):
      try: print(repr(val), "->", sf.guard_write(route/"cognition"/"x",
                                                 skill_root=skill, allowed_roots=val)["code"])
      except Exception as e: print(repr(val), "-> EXC", type(e).__name__, e)
  PY
  ```
* **OBSERVED**
  ```
  None            -> EXC TypeError 'NoneType' object is not iterable
  42              -> EXC TypeError 'int' object is not iterable
  PosixPath(...)  -> EXC TypeError 'PosixPath' object is not iterable
  ```
* **Expected:** deny with a structured dict (`OUTSIDE_ALLOWED_SCOPE` / `RESOLUTION_ERROR`).
* **Classification:** **regression introduced by 2506405**.

### H-04 — MEDIUM — hard-link detection is bypassed as soon as the protected file is deleted

* **file:line:** `scripts/source_freeze.py:424-433` (`_protected_identities` enumerates `protected_files`),
  `:521-525` (identity comparison).
* **What is wrong.** `_protected_identities()` stats only files that currently exist under `PROTECTED`.
  If an attacker hard-links a protected file into an allowed scope and then removes the original, the
  inode is no longer in the identity set, so writing through the surviving hard link is `ALLOWED`. The
  fix's claim "路径可以漂白，inode 不能" holds only while the original file still exists.
* **Reproduction**
  ```bash
  cd /tmp && python3 - <<'PY'
  import sys, tempfile, pathlib, os
  sys.path.insert(0, "/tmp/headscripts/research-idea-pipeline/scripts")
  import source_freeze as sf
  t = pathlib.Path(tempfile.mkdtemp()); skill = t/"skill"
  (skill/"scripts").mkdir(parents=True)
  for r in ["SKILL.md","scripts/guard.py"]: (skill/r).write_text("#\n")
  route = t/"proj"/"routes"/"A"; (route/"cognition").mkdir(parents=True)
  os.link(skill/"SKILL.md", route/"cognition"/"hard")
  print("before delete:", sf.guard_write(route/"cognition"/"hard", skill_root=skill,
                                         allowed_roots=[route])["code"])
  os.unlink(skill/"SKILL.md")
  print("after delete :", sf.guard_write(route/"cognition"/"hard", skill_root=skill,
                                         allowed_roots=[route])["code"])
  PY
  ```
* **OBSERVED**
  ```
  before delete: HARD_LINK_TO_PROTECTED
  after delete : ALLOWED
  ```
* **Expected:** `HARD_LINK_TO_PROTECTED` (or at minimum a `PROTECTED_*` denial), independent of whether
  the original path still exists.
* **Classification:** **incomplete fix** of E-2. Impact is bounded: the protected path is already gone
  (manifest `verify()` reports it in `removed`), so this is an inode-level claim gap rather than a way to
  edit a live protected file.

### H-05 — LOW — the `ALLOWED_WRITE_SCOPES` check is skipped for every target inside `skill_root`

* **file:line:** `scripts/source_freeze.py:558` (`if not inside_root and not canonical_ok:`).
* **What is wrong.** Scope enforcement is gated on `not inside_root`. A route that lives *inside* the
  Skill root (e.g. `<skill>/localroutes/A`) gets no scope check at all: `<skill>/localroutes/A/evil.sh`
  is `ALLOWED` even though `evil.sh` is not in `ALLOWED_WRITE_SCOPES`. The intended production layout puts
  routes outside the Skill root, so this is latent — but the guard's documented scope contract does not
  hold for in-root routes.
* **Reproduction**
  ```bash
  cd /tmp && python3 - <<'PY'
  import sys, tempfile, pathlib
  sys.path.insert(0, "/tmp/headscripts/research-idea-pipeline/scripts")
  import source_freeze as sf
  t = pathlib.Path(tempfile.mkdtemp()); skill = t/"skill"
  (skill/"scripts").mkdir(parents=True)
  for r in ["SKILL.md","scripts/guard.py"]: (skill/r).write_text("#\n")
  inr = skill/"localroutes"/"A"; inr.mkdir(parents=True)
  print(sf.guard_write(inr/"evil.sh", skill_root=skill, allowed_roots=[inr]))
  PY
  ```
* **OBSERVED**
  ```
  {'allowed': True, 'code': 'ALLOWED', 'reason': '目标可写：.../skill/localroutes/A/evil.sh', ...}
  ```
* **Expected:** `OUTSIDE_WRITE_SCOPE` (the top-level scope `localroutes` is not a known route scope).
* **Classification:** **incomplete fix** of E-11.

### H-06 — HIGH — PT10 fail-closed is still neutralised by a *valid but unsatisfied* `conditions` list

* **file:line:** `scripts/policy_transfer.py:1035` (`if conditions: structured = True`),
  `:1071-1083` (evaluate conditions; `continue` when none is satisfied),
  `:1093-1096` (`if not structured:` fail-closed block). Unchanged in commit 2506405 except the malformed
  branch.
* **What is wrong.** The F-3 fix makes *malformed* condition **elements** fail closed, but a counterexample
  that declares **no structure** and carries a *well-formed yet unsatisfied* condition still takes the
  `continue` at line 1082-1083 **before** the `if not structured` fallback at line 1093. Because
  `_counterexample_tokens` sets `structured = True` merely because `conditions` is a non-empty list,
  adding one harmless condition (e.g. an equality against a value the target does not have) removes the
  "反例未声明适用结构" block entirely. This is the same "add a condition to neutralise PT10" vector as the
  original H3, just with a syntactically valid condition.
* **Reproduction**
  ```bash
  cd /tmp && python3 - <<'PY'
  import sys
  sys.path.insert(0, "/tmp/headscripts/research-idea-pipeline/scripts")
  import policy_transfer as pt
  # committed test fixture module (fixtures only; pt is the committed copy above)
  import importlib.util as u
  spec = u.spec_from_file_location("tp", "/home/lenovo/code/myproj/skills-dev/"
      "research-idea-pipeline/skill-rsi-dev/research-idea-pipeline/scripts/test_policy_transfer.py")
  tp = u.module_from_spec(spec); spec.loader.exec_module(tp)
  s = tp.fixture_state()
  def errs(ce):
      return [d.as_dict()["detail"] for d in
              pt._counterexample_errors(tp.allow_policy(counterexamples=[ce]), s, 0.5)]
  print("no cond         :", errs({"id": "CE"}))
  print("false valid cond:", errs({"id": "CE", "conditions":
        [{"field": "contract.primary_anchor", "op": "eq", "value": "__nope__"}]}))
  PY
  ```
* **OBSERVED**
  ```
  no cond         : ['反例未声明适用结构，无法排除其覆盖目标（fail-closed 阻塞）']
  false valid cond: []
  ```
* **Expected:** a counterexample that declares no applicable structure must block — adding an unsatisfied
  condition must not make the block disappear.
* **Classification:** **incomplete fix** of F-3 (HIGH, contract violation: should BLOCK, returns ALLOW).

### H-07 — MEDIUM — a negative integer `state_version` silently disables all trajectory expiry

* **file:line:** `scripts/policy_transfer.py:1497-1499` (`isinstance(raw_version, int)` accepted with no
  non-negativity check), `:1542` (`if current is None: expired`), `:1556`
  (`if current - min(versions) > gap`).
* **What is wrong.** The F-6 fix rejects missing / non-int / `bool` versions, but accepts **negative**
  ints as a valid `current`. `current - min(versions)` then becomes hugely negative, so the comparison
  against `gap` is never true and **no trajectory is ever reported expired**, with zero diagnostics.
  `state_check.S7` already declares `state_version` must be a non-negative integer; the expiry helper is a
  standalone gate (CLI `expired`, public function, no `state_check` run) so this is reachable.
* **Reproduction**
  ```bash
  cd /tmp && python3 - <<'PY'
  import sys
  sys.path.insert(0, "/tmp/headscripts/research-idea-pipeline/scripts")
  import policy_transfer as pt, importlib.util as u
  spec = u.spec_from_file_location("tp", "/home/lenovo/code/myproj/skills-dev/"
      "research-idea-pipeline/skill-rsi-dev/research-idea-pipeline/scripts/test_policy_transfer.py")
  tp = u.module_from_spec(spec); spec.loader.exec_module(tp)
  recs = [tp.decision_record(tp.fixture_state(version=1), project="A", version=1)]
  for ver in [3, 100, -1, -10**9, 3.0]:
      st = tp.fixture_state(); st["state_version"] = ver
      rep = pt.expired_trajectories_report(recs, st)
      print(ver, "-> expired", rep["expired"], "diags", len(rep["diagnostics"]))
  PY
  ```
* **OBSERVED**
  ```
  3      -> expired [] diags 0
  100    -> expired ['DT-sha256:cadfb22df5b20'] diags 0
  -1     -> expired [] diags 0
  -1000000000 -> expired [] diags 0
  3.0    -> expired ['DT-sha256:cadfb22df5b20'] diags 1
  ```
* **Expected:** negative `state_version` is invalid (S7) → fail closed (all expired + PT11 diagnostic),
  exactly like the float case.
* **Classification:** **incomplete fix** of F-6.

### H-08 — MEDIUM — F-5 provenance remains self-attested: a candidate that declares `source_route` = current route bypasses the gate

* **file:line:** `scripts/policy_evolution.py:559`
  (`record.setdefault("source_route", cg.route_of(Path(state_path)))`), `:1084-1088`
  (`source = ... or candidate.get("source_route") or ...`; `str(source) == str(current_route)` →
  `NOT_REQUIRED`). Docstring at `:1070` is stale (claims `propose()` does not stamp provenance).
* **What is wrong.** `setdefault` preserves a `source_route` supplied by the candidate itself. Because
  `cross_project_transfer_allowed` treats "declared source == current route" as same-route and returns
  `NOT_REQUIRED`, a candidate can name the route it will later be applied in and skip the entire PT gate.
  The fix closed the *missing*-provenance case but still trusts a *self-declared* one.
* **Reproduction**
  ```bash
  cd /tmp && python3 - <<'PY'
  import sys
  sys.path.insert(0, "/tmp/headscripts/research-idea-pipeline/scripts")
  import policy_evolution as pe, policy_transfer as pt, importlib.util as u
  spec = u.spec_from_file_location("tp", "/home/lenovo/code/myproj/skills-dev/"
      "research-idea-pipeline/skill-rsi-dev/research-idea-pipeline/scripts/test_policy_transfer.py")
  tp = u.module_from_spec(spec); spec.loader.exec_module(tp)
  s = tp.fixture_state()
  for label, cand, cur in [
      ("truthful origin B -> applied in A",
       {"id": "P", "scope": {"kind": "structure", "source_route": "B"}}, "A"),
      ("spoofed origin A -> applied in A",
       {"id": "P", "scope": {"kind": "structure", "source_route": "A"}}, "A"),
      ("no provenance, current=A",
       {"id": "P", "scope": {"kind": "structure"}}, "A"),
  ]:
      r = pe.cross_project_transfer_allowed(cand, s, current_route=cur,
              source_state=s, target_tools=["evaluation-harness"])
      print(label, "-> required", r["required"], "status", r["status"])
  PY
  ```
* **OBSERVED**
  ```
  truthful origin B -> applied in A -> required True  status ALLOW   (gate ran)
  spoofed  origin A -> applied in A -> required False status NOT_REQUIRED (gate skipped)
  no provenance, current=A          -> required True  status BLOCK
  ```
* **Expected:** provenance that cannot be independently corroborated (including a self-declared
  `source_route` equal to the target route) should not by itself satisfy the same-route exemption.
* **Classification:** **incomplete fix** of F-5 (inherits the F-12 "self-attested evidence" class).

### H-09 — LOW — PT8 silently drops a `negative_knowledge` entry whose only `ruled_out` is a non-string

* **file:line:** `scripts/policy_transfer.py:645` (`statement = ruled_out or finding or failure.what`),
  `:1238` (`negated_statements = [text for text in ... if text]`).
* **What is wrong.** A non-string-but-truthy `ruled_out` (e.g. `42`) is selected as `statement`,
  `_norm_statement` returns `""`, and the entry is filtered out. With no `finding` and no `failure.what`
  scoring, `negated_statements` is empty and `_negated_errors` `continue`s — PT8 is disabled for that
  entry with no diagnostic, even though the data is malformed and should fail closed.
* **Reproduction**
  ```bash
  cd /tmp && python3 - <<'PY'
  import sys
  sys.path.insert(0, "/tmp/headscripts/research-idea-pipeline/scripts")
  import policy_transfer as pt, importlib.util as u
  spec = u.spec_from_file_location("tp", "/home/lenovo/code/myproj/skills-dev/"
      "research-idea-pipeline/skill-rsi-dev/research-idea-pipeline/scripts/test_policy_transfer.py")
  tp = u.module_from_spec(spec); spec.loader.exec_module(tp)
  st = tp.fixture_state()
  st["failures"][0]["negative_knowledge"] = [{"target_id": "C2", "ruled_out": 42}]
  st["failures"][0]["what"] = ""
  pol = tp.allow_policy(mechanism={"id": "X", "statement": "协议 P 有效"})
  r = pt.transfer_decision(pol, st, source_state=st, target_tools=["evaluation-harness"],
                           source_project="A", target_project="B")
  print(r["status"], r["codes"])
  print("norm_statement(42) =", repr(pt._norm_statement(42)))
  PY
  ```
* **OBSERVED**
  ```
  ALLOW []
  norm_statement(42) = ''
  ```
* **Expected:** malformed `negative_knowledge.ruled_out` → PT8/PT1 diagnostic (fail closed).
* **Classification:** **incomplete fix** of F-2 (edge case).

---

## SUSPECTED (reasoned, not a fix regression)

### S-1 — LOW — `record_integrity_event` corrupts a log that does not end in a newline

Appending to an existing `source-integrity.jsonl` that lacks a trailing `\n` concatenates the new JSON
object onto the previous line, producing one invalid line; `_load_integrity_chain` then reports
`不是合法 JSON` and a head mismatch. Repro: create one event, `rstrip("\n")` the file, record a second
event, read with `tolerant=True`. **Pre-existing** (the writer's `splitlines()`-based seq logic is
unchanged), not introduced by 2506405; trigger requires external truncation. Documented here for
completeness because the new read-side validation now surfaces it as a hard error.

---

## Checked and NOT a bug

* **E-8 / `EXCLUDED_DIRS_ANYWHERE` — no real protected file is invisible.**
  Real `SKILL_ROOT` manifest = **135** entries; an independent `find` over the same `PROTECTED` roots,
  excluding only paths that contain a `.git`/`__pycache__` **directory** component, = **135**;
  `find`-only = `[]`, manifest-only = `[]`.
  Synthetic tree: `scripts/.dev/evil.py` **visible**; `presets/.git/config` and
  `references/__pycache__/stale.py` **invisible** (VCS/cache dirs); a regular *file* literally named
  `references/strange/__pycache__` **visible**. No legitimate source file is excluded.
* **E-6 (malformed manifest)** → `verify()` returns `VIOLATION` with `malformed=['scripts/guard.py']`
  (no `AttributeError`); `hold_on_violation` → `HOLD`.
* **E-7 (`hold_on_violation` fail-closed)**: `None`, `{}`, `[]`, `"PASS"`, and a dict without `status`
  all → `HOLD`; only `{'status':'PASS'}` → `PASS`.
* **Integrity chain (E-3)** against the committed code:
  * caller-supplied `seq`/`previous`/`recorded_at` are overwritten (`record_integrity_event` writes chain
    fields after the merge) — the caller can **not** set `recorded_at`;
  * a **duplicated valid line** (first, middle, or last) is **not** silent under `tolerant=True`: it yields
    `哈希链断裂` + `seq 不连续` diagnostics; a blank line inserted between events is tolerated (intended,
    mirrors BUG-4);
  * tail truncation → head mismatch; log deleted but head kept → diagnostic; head deleted but log kept →
    diagnostic;
  * deleting **both** log and head, or an attacker who re-links a forged tail **and** rewrites the head,
    are silent — these are exactly the documented residual risks ("拥有任意文件系统写权限的进程…"), not new
    defects.
* **F-1 (killed hypotheses)**: all real `state_check.HYPOTHESIS_STATUSES`
  (`active`, `elite`, `archived`, `killed`) plus `refuted`/`contradicted` are covered; only non-canonical
  values (`killed_soft`, `None`) are not, and those are rejected by `state_check`.
* **F-2 (ruled_out vs finding)**: proposal matching the `ruled_out` proposition → PT8; matching the
  `finding` text → PT8; `finding`-only entry → PT8. (The non-string `ruled_out` edge is H-09.)
* **F-3 malformed conditions**: missing field / unknown op / regex op → PT10 (fail closed). (The
  conditions-only valid-condition bypass is H-06.)
* **F-4 non-list shapes**: `applicable_conditions` as tuple/str/42/None → **PT5**; `required_tools` as
  str/42 / `requires.tools` str → **PT6**; `required_tools` tuple is accepted (correct).
* **F-6 float/bool/None/str and huge int**: floats/bools/None/str → all expired + PT11 diagnostic; a huge
  positive int behaves normally. Negative int is the gap (H-07).
* **F-7 (arbitrary JSONL)**: a bogus JSONL gives `chain_ok=False`, `separation_ok=False` and a PT1
  diagnostic; the CLI surfaces `status=DEGRADED` with a hard exit.
* **F-9 (`compression_report`)**: duplicate ids across kinds, in either order, with any non-droppable /
  unknown kind → `REFUSED`.
* **F-10 (ReDoS)**: `policy_transfer.py` has exactly two `re.` call sites, both **constant** patterns
  (`:180` `re.sub(r"\s+", ...)`, `:1052` `re.fullmatch(r"[A-Za-z]+[0-9]...")`). No user-controlled
  pattern reaches `re.*`; the user-supplied `regex`/`matches` operator is refused (returns
  unresolved → PT5/PT10).
* **F-11 (compress exit code)**: `REFUSED` → exit **3**; `transfer` BLOCK → exit 3; `guard /etc/passwd`
  (no route) → exit 3 / `OUTSIDE_ALLOWED_SCOPE`.
* **F-5 basic fail-closed**: no source + `current_route` given → BLOCK; source declared + no route →
  BLOCK; non-dict candidate → BLOCK. (Self-declared matching source is H-08.)
* **F-8 (self-attested signature)**: a policy that self-declares `structural_signature` and is given a
  truthy-but-bogus `source_trajectories=[{}]` still fails to reach `structural_match` (score 0.285
  < 0.5); with `source_state` it is 1.0/ALLOW. Not defeatable in the probes tried.
* **Documented-unfixed, confirmed still open (not new):** E-5 (`verify()` compares only `sha256`),
  E-9 (in-root symlink *directories* neither manifested nor reported), E-16 (change-and-change-back
  inside the window), F-12 (PT9 self-attested cross-project evidence). `G-latent-bugs.md` declares these
  open; this review agrees.

---

## Regression gates (exact counts)

| Gate | Command | Result |
|---|---|---|
| Full suite (from `scripts/`) | `python3 -m unittest discover -p 'test_*.py'` | **Ran 1661 tests — OK (skipped=3)**, exit 0 |
| Full suite (release_check form) | `python3 -m unittest discover -s scripts -p 'test_*.py'` | **Ran 1671 tests — OK (skipped=3)** |
| `release_check.py` | `python3 scripts/release_check.py` | **PASS**, last line `PASS`, **18/18 steps `[ok  ]`**, 0 `[FAIL]` |
| `source_freeze.py --selftest` | `python3 scripts/source_freeze.py --selftest` | `selftest OK`, exit 0 |
| `policy_transfer.py --selftest` | `python3 scripts/policy_transfer.py --selftest` | `selftest OK`, exit 0 |

**Count caveat:** the suite count is currently unstable across invocations/cwd (1661 / 1667 / 1671)
because the checkout is dirty and a concurrent agent is editing `test_decision_trajectory.py`,
`test_policy_evolution.py`, and `test_skill_rsi_e2e.py`; `release_check.py`'s own step 1 reported
`Ran 1667 tests` in this session. Committed `8887a48` — the state the gates were claimed for — is
`1661 tests OK (skipped=3)` when the working tree is clean.

---

## Bottom line

The two commits genuinely close the original E/F repros (E-1 default, E-2 live hard link, E-3 forge/
truncate/replay, E-4, E-6, E-7, E-8, F-1, F-3-malformed, F-4, F-6-missing/non-int, F-7, F-8, F-9, F-10,
F-11, F-5-missing-provenance). However, **9 CONFIRMED delta defects remain**, of which **H-06 (HIGH)**
is a live fail-open (PT10 bypass), and **H-03 is a new regression** introduced by the fix (unguarded
iteration over `allowed_roots`). The write-whitelist itself is still not an enforcement path: `guard_write`
is called only by its own CLI/selftest and by tests, and its `ALLOWED_WRITE_SCOPES` entry for the real
trajectory store is misspelled, so if it *were* wired in it would deny a legitimate runtime write.
