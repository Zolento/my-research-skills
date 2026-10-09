# E — Adversarial audit of `source_freeze.py`

Target: `scripts/source_freeze.py` (846 lines) — Skill source freeze: manifest + normalized-path write guard + hash-chained audit events.
Baseline: all 16 tests in `scripts/test_source_freeze.py` pass (`python3 -m unittest test_source_freeze` → `Ran 16 tests ... OK`).
Method: no production file was modified. Every reproduction runs against a throwaway tree built by `/tmp/sfaudit/harness.py`
(a `tempfile.TemporaryDirectory` fake skill tree, never the real Skill source). `sys.path` is pointed at `research-idea-pipeline/scripts`.

Unless stated otherwise, the harness tree is:

```
TREE = SKILL.md, shared-contract.md, preset-registry.json, router-fixtures.json,
       scripts/guard.py, scripts/util.py, presets/research-loop.md, references/policy.md,
       templates/state.template.json, schemas/x.schema.json,
       .dev/hidden-answer.md, examples/demo.md
route = <tmp>/project/.research-idea-pipeline/routes/A
```

Severity legend: HIGH = attacker gets a green light to write protected source, or the audit/verification
claim is defeated in a way that matters; MEDIUM = false PASS/false negative or fail-open on a realistic
call pattern; LOW = nuisance, docstring/guarantee mismatch, unreachable-in-production; INFO = observation.

Provenance: `scripts/source_freeze.py` was **not modified** by this audit (mtime 05:54:43). A concurrent
process modified `scripts/decision_trajectory.py` at 06:29:29 while this audit was running; the E-3
reproduction was re-run against the modified file and still behaves as shown (the shared loader still
rejects the integrity log).

---

## CONFIRMED (reproduced in this session)

### E-1 — HIGH — `guard_write` default is allow-all outside the Skill root (fail-open whitelist)
**File:** `scripts/source_freeze.py:362-363` (`allowed_roots: Sequence[Any] = ()`), `:396` (`if allowed_roots:`), `:407` (`return _allow(resolved)`)

**What is wrong.** The module advertises a "规范化路径写入守卫 / 写入白名单" (normalized-path write
whitelist, docstring lines 13-15, and `enforced_by_this_module` line 575). But `allowed_roots` defaults
to the empty tuple, and the scope check is *skipped* when it is falsy. With the default, `guard_write`
only rejects the hardcoded protected/hidden/canonical names; **any** other absolute path anywhere on the
filesystem returns `ALLOWED`. `guard --target <path>` without `--route` therefore exits 0 for `/etc/passwd`,
`~/.ssh/authorized_keys`, a sibling project directory, or the skill's own `docs/`.

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile, pathlib
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    for p in ['/etc/passwd','/tmp/owned.txt', pathlib.Path(t)/'outside'/'x.txt', skill/'docs'/'x.md']:
        print(p, '->', sf.guard_write(p, skill_root=skill)['code'])
"
```
**Observed output**
```
/etc/passwd -> ALLOWED
/tmp/owned.txt -> ALLOWED
/tmp/tmpXXXX/outside/x.txt -> ALLOWED
/tmp/tmpXXXX/skill/docs/x.md -> ALLOWED
```
CLI form (same session, real script path):
```
$ python3 scripts/source_freeze.py guard --target /etc/passwd --root /tmp/tmpXXXX/skill
... "allowed": true, "code": "ALLOWED" ...
exit code: 0
```
**Expected.** Either `allowed_roots` should default to a *closed* scope (deny anything not explicitly
allowed), or the function should refuse to return `ALLOWED` when no scope was supplied. At minimum the
"whitelist" wording must not be used when the empty default means "everything".
**Exploit.** A caller that follows the documented single-argument form (`guard_write(target,
skill_root=root)`) — exactly what the shipped tests do (`test_source_freeze.py:105, 111, 154, 161`) — gets
no protection outside the Skill root. Nothing in the repo calls `guard_write` in production (`grep`:
only `test_source_freeze.py`), so this is latent, not live. The CLI path *is* live and returns exit 0.

---

### E-2 — HIGH — hard link to a protected file bypasses `guard_write`; the protected source is writable with `ALLOWED`
**File:** `scripts/source_freeze.py:354` (`real = Path(os.path.realpath(...))`), `:380-384` (protected check on the realpath)

**What is wrong.** `normalize_target` collapses the path to a `realpath` string and the guard decides
purely on that string. `os.path.realpath` resolves *symlinks* but not *hard links*. A hard link created
inside an allowed route (or anywhere not protected) shares the inode with `skill/SKILL.md`, so its
realpath is the route path, `_protected_relpath` is `False`, and the write is approved — while the bytes
land in the protected file.

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile, pathlib, os
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    frozen = sf.manifest(skill)
    link = route/'hard-SKILL.md'
    os.link(skill/'SKILL.md', link)
    g = sf.guard_write(link, skill_root=skill, allowed_roots=[route])
    print('guard through hardlink:', g)
    if g['allowed']:
        link.write_text('OWNED BY ATTACKER\n', encoding='utf-8')
    print('SKILL.md now:', repr((skill/'SKILL.md').read_text()))
    print('verify after write:', sf.verify(frozen, skill)['status'], sf.verify(frozen, skill)['changed'])
"
```
**Observed output**
```
guard through hardlink: {'allowed': True, 'code': 'ALLOWED', 'reason': '目标可写：/tmp/tmp8i_3id9n/project/.research-idea-pipeline/routes/A/hard-SKILL.md', 'resolved': '.../hard-SKILL.md'}
SKILL.md now: 'OWNED BY ATTACKER\n'
verify after write: VIOLATION ['SKILL.md']
same inode: True
```
**Expected.** The guard should refuse to authorize a write whose inode is one of the frozen files
(compare `os.stat(target).st_ino/st_dev` against the protected set), or the deployment plan must state
that hard links defeat the path guard. `verify` does catch the content change afterwards, but only
*after* the write was explicitly authorized.
**Exploit.** Any process able to create a hard link in a route directory (same filesystem, permitted by
default on Linux) can edit protected source with `guard_write` returning `ALLOWED` and no `HOLD` at
authorization time. The separate `verify()` pass still flags it, so this is a guard bypass, not a silent
freeze bypass.

---

### E-3 — HIGH — the "hash-chained append-only audit" is forgeable, replayable, truncatable, and is never verified
**File:** `scripts/source_freeze.py:486` (`record = {**base, **dict(event)}`), `:496-515` (`integrity_events`)

**What is wrong.** Three independent defects compound:
1. `record = {**base, **dict(event)}` merges the caller's event *over* the chain fields, so a caller
   (or anything feeding untrusted JSON into `event`) can set `seq`, `previous`, `recorded_at` directly.
2. `integrity_events()` only `json.loads` each line; it never checks `previous`, `seq`, or any tail digest.
   Deleting the log, truncating it to a prefix, deleting a middle line, or splicing in a forged line is
   completely undetected. Contrast `decision_trajectory.load_chained` (`decision_trajectory.py:122-173`),
   which raises `TrajectoryError` on a chain break, bad `seq`, or a missing/incorrect head file.
3. The two modules use *incompatible* chain conventions (`source_freeze._line_digest` = sha256 of the raw
   line, unsorted keys; `decision_trajectory._digest` = `cognition.digest_of(record)`, canonical sorted
   keys), so the shared loader rejects the integrity log outright — confirming nothing reuses it.

**Reproduction (forge + delete)**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile, json
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    sf.record_integrity_event(route, {'action':'A'})
    sf.record_integrity_event(route, {'action':'B'})
    sf.record_integrity_event(route, {'action':'FORGED','seq':1,'previous':'sha256:deadbeef','recorded_at':'1999-01-01T00:00:00+00:00'})
    print('forged record:', json.dumps(sf.integrity_events(route)[-1], ensure_ascii=False))
    p = route/sf.INTEGRITY_NAME
    lines = p.read_text().splitlines()
    p.write_text(chr(10).join([lines[0], lines[2]])+chr(10))
    print('after middle-line deletion:', [e['seq'] for e in sf.integrity_events(route)])
    p.unlink()
    print('after full log deletion:', sf.integrity_events(route))
"
```
**Observed output**
```
forged record: {"schema": "research-idea-pipeline/source-integrity-event@1", "seq": 1, "recorded_at": "1999-01-01T00:00:00+00:00", "previous": "sha256:deadbeef", "action": "FORGED"}
after middle-line deletion: [1, 1]
after full log deletion: []
```
**Reproduction (identical-content replay + shared loader)**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf, decision_trajectory as dt
    ev = {'action':'A','seq':1,'previous':None,'recorded_at':'T'}
    sf.record_integrity_event(route, ev); sf.record_integrity_event(route, ev)
    lines = (route/sf.INTEGRITY_NAME).read_text().splitlines()
    print('two appends produced IDENTICAL lines:', lines[0]==lines[1])
    try: dt.load_chained(route/sf.INTEGRITY_NAME)
    except Exception as e: print('shared loader rejects the log:', type(e).__name__, str(e)[:120])
"
```
**Observed output**
```
two appends produced IDENTICAL lines: True
shared loader rejects the log: TrajectoryError DT0  source-integrity.jsonl:2  哈希链断裂：历史行被改写或被删除
```
**Expected.** Chain fields must be written *after* the merge (never overridable), and
`integrity_events` (or a `verify_integrity_chain`) must validate `previous`/`seq` and detect deletion,
mirroring `load_chained`. The deployment plan's `enforced_by_this_module` claim "带哈希链的只追加审计事件"
is not provided.
**Exploit.** `source-integrity.jsonl` is not a protected path, so `guard_write` allows writing/deleting it
even with `allowed_roots=[route]` (observed `code: ALLOWED`). Combined with the missing verification, the
audit trail provides no tamper evidence at all: an attacker deletes the log, rewrites it, or injects
forged `HOLD`/`VERIFY_PASS` records at will.

---

### E-4 — HIGH — relative `allowed_roots` are resolved against the Skill root, so `"."` silently grants the whole Skill root
**File:** `scripts/source_freeze.py:352` (`lexical_path = lexical if lexical.is_absolute() else (root_real / lexical)`), `:400` (`normalize_target(allowed, root=skill_root)`)

**What is wrong.** Every relative target and every relative allowed root is resolved against `skill_root`,
not the current working directory. A caller that passes a relative route (e.g. `--route .`, or a route
expressed relative to the repo checkout) gets `skill_root` as the allowed scope, and `_is_inside` then
admits any non-protected path under the Skill root.

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    print('allowed_roots=[\".\"], target skill/docs/x.txt ->',
          sf.guard_write(skill/'docs'/'x.txt', skill_root=skill, allowed_roots=['.'])['code'])
    print('allowed_roots=[\".\"], target skill/presets/y  ->',
          sf.guard_write(skill/'presets'/'y', skill_root=skill, allowed_roots=['.'])['code'])
"
```
**Observed output**
```
allowed_roots=["."], target skill/docs/x.txt -> ALLOWED
allowed_roots=["."], target skill/presets/y  -> PROTECTED_SKILL_SOURCE
```
**Expected.** Either relative scopes should resolve against `os.getcwd()` (documented), or a scope that
normalizes to `skill_root` itself should be rejected as too broad. Silently widening the scope to the whole
Skill root is the opposite of the whitelist intent.
**Exploit.** `guard --target docs/anything.md --route .` against the real Skill root returns exit 0. Every
existing non-protected directory of the Skill (`docs/`, top-level `.gitignore`, etc.) becomes writable.

---

### E-5 — MEDIUM — `verify()` ignores the manifest's `root`, `count`, `digest`, `symlink` and `realpath`
**File:** `scripts/source_freeze.py:304-330` (only `sha256` at `:317` is compared)

**What is wrong.** `verify` compares relative-path → `sha256` only. `manifest_payload["root"]` is never
consulted, so a manifest frozen for tree A reports `PASS` against any other tree with the same relative
layout and content. And because `symlink`/`realpath` are never compared, replacing a protected regular
file with an **in-root** symlink to an identical-content file (an excluded directory such as `.dev` is
convenient, since it is unwritable-protected but not manifested) yields `PASS` with empty
`changed/added/removed`.

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile, pathlib, os
with tempfile.TemporaryDirectory() as t:
    a,_ = harness.build(pathlib.Path(t)/'a'); b,_ = harness.build(pathlib.Path(t)/'b')
    import source_freeze as sf
    frozen = sf.manifest(a)          # frozen BEFORE the swap
    print('manifest.root =', frozen['root'])
    print('tree B vs A manifest:', sf.verify(frozen, b)['status'])
    (a/'.dev'/'copy.md').write_text('# references/policy.md\n', encoding='utf-8')
    os.remove(a/'references'/'policy.md')
    os.symlink(pathlib.Path('..')/'.dev'/'copy.md', a/'references'/'policy.md')
    print('in-root symlink swap:', sf.verify(frozen, a))
"
```
**Observed output**
```
manifest.root = /tmp/tmpkiv4ro_0/a/skill
tree B vs A manifest: PASS
in-root symlink swap: {'status': 'PASS', 'changed': [], 'added': [], 'removed': [], 'symlink_escapes': [], 'checked': 10}
```
**Expected.** `verify` should reject a manifest whose `root` differs from the supplied root (or at least
report it), and should treat any change of `symlink`/`realpath` for an existing path as `changed`, since
the manifest deliberately records those fields.
**Exploit.** Limited: the swapped-to target is inside the root, so `_symlink_escapes` does not fire, but
its content hash is still pinned through the symlinked path. The main damage is a false `PASS` for a
structurally altered protected tree and for a manifest verified against the wrong root. Nuisance / false
negative rather than a content-write bypass. Note the outside-root case *is* caught (see "Not a bug" N-3).

---

### E-6 — MEDIUM — a malformed manifest makes `verify()` raise instead of returning `VIOLATION`
**File:** `scripts/source_freeze.py:317` (`expected[rel].get("sha256")`), fed by `load_manifest` `:291-301` which validates only that the root is a dict

**What is wrong.** `load_manifest` accepts any JSON object. If `files[rel]` is not a dict (string, list,
number, null), `verify` raises `AttributeError`. The CLI then exits 1 with a traceback, violating the
documented exit-code contract (exit 3 = VIOLATION, exit 4 = environment problem / illegal JSON). This is
a robustness/fail-loud defect, not a fail-open one: the exception propagates out of
`SourceFreeze.__exit__`, so no `HOLD` event is recorded.

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile, pathlib, json, subprocess, sys
SCRIPTS='/home/lenovo/code/myproj/skills-dev/research-idea-pipeline/skill-rsi-dev/research-idea-pipeline/scripts'
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    mf = pathlib.Path(t)/'bad.json'
    mf.write_text(json.dumps({'schema':sf.SCHEMA_MANIFEST,'root':str(skill),'files':{'SKILL.md':'not-a-dict'}}))
    r = subprocess.run([sys.executable, SCRIPTS+'/source_freeze.py','verify','--manifest',str(mf),'--root',str(skill)],capture_output=True,text=True)
    print('exit code:', r.returncode); print(r.stderr.strip().splitlines()[-1])
"
```
**Observed output**
```
exit code: 1
AttributeError: 'str' object has no attribute 'get'
```
**Expected.** `verify` should return `status: VIOLATION` (or `SourceFreezeError` → `EXIT_ENV`) for a
malformed `files` entry, matching the "缺文件不抛异常" spirit and the documented exit codes.
**Exploit.** A corrupt/truncated/hostile manifest aborts verification with no audit record. Low
exploitability (crash, not silent pass) but it defeats the documented error contract.

---

### E-7 — MEDIUM — `hold_on_violation()` treats a non-dict verification as PASS (fail-open)
**File:** `scripts/source_freeze.py:521` (`if not isinstance(verification, dict) or verification.get("status") == "PASS": return {... "status": "PASS" ...}`)

**What is wrong.** A `None`, list, or string `verification` (e.g. the caller lost the result) is reported
as `{"status": "PASS", "reason": "源码完整性通过，无需 HOLD"}` — an affirmative "integrity passed" answer.

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    print('None     ->', sf.hold_on_violation(route, None))
    print('non-dict ->', sf.hold_on_violation(route, ['x']))
    print('empty    ->', sf.hold_on_violation(route, {})['status'])
"
```
**Observed output**
```
None     -> {'status': 'PASS', 'reason': '源码完整性通过，无需 HOLD', 'event': None}
non-dict -> {'status': 'PASS', 'reason': '源码完整性通过，无需 HOLD', 'event': None}
empty    -> HOLD
```
**Expected.** A non-dict verification is "unknown", not "clean": return `HOLD`/raise, never `PASS`.
**Exploit.** A caller that chains `hold_on_violation(route, maybe_result)` where `maybe_result` is `None`
on the error path concludes the tree is intact and continues. Fail-open.

---

### E-8 — MEDIUM — `EXCLUDED_DIRS` is matched at *any* depth, so files planted under `scripts/.dev/`, `presets/.git/`, `*/__pycache__/` are invisible to freeze/verify
**File:** `scripts/source_freeze.py:192` (`if dirname in EXCLUDED_DIRS: continue` inside `os.walk`), docstrings `:74-78` ("目录下的**全部文件**都进入清单"), `:176-181` ("产出受保护条目下的所有文件")

**What is wrong.** The exclusion is a bare name test at every level, not a top-level-only test. A new file
under such a nested directory is neither manifested nor reported as `added`; `verify` returns `PASS`.

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    frozen = sf.manifest(skill)
    for rel in ['scripts/.dev/evil.py','presets/.git/hooks/post-checkout','references/__pycache__/p.pyc']:
        p = skill/rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('x\n')
    r = sf.verify(frozen, skill)
    print('added:', r['added'], 'status:', r['status'])
    print('guard would deny plant?', sf.guard_write(skill/'scripts/.dev/evil.py', skill_root=skill)['code'])
"
```
**Observed output**
```
added: [] status: PASS
guard would deny plant? PROTECTED_SKILL_SOURCE
```
**Expected.** Excluded directories should only be excluded when they are the top-level `PROTECTED` entries'
own dev/VCS dirs, or files inside excluded dirs of protected trees should at least be reported as `added`.
The docstring "全部文件都进入清单" is false.
**Exploit.** `guard_write` still blocks writes under `scripts/…`, so this is a freeze/verify **detection**
false negative, not a write bypass. The realistic payload is a poisoned `scripts/__pycache__/*.pyc`,
which the manifest cannot see. (Poisoning not demonstrated; see SUSPECTED S-3.)

---

### E-9 — MEDIUM — in-root symlink *directories* under a protected tree are neither manifested nor reported as added/removed
**File:** `scripts/source_freeze.py:184-187` (symlink dir is yielded but not recursed), `:210-211` (`entry.is_dir()` filter drops it from `protected_files`), `:242-247` (`_symlink_escapes` only flags outside-root targets)

**What is wrong.** A symlink to a directory is yielded by `_iter_protected_entries` but then discarded by
`protected_files` (`is_dir()` is True), and it never appears in `escapes` because its realpath is inside
the root. So it appears in **no** manifest entry and in **no** `added`/`removed`/`symlink_escapes` list.
A symlink-to-a-*file* added in the same place is reported as `added`. The treatment is inconsistent, and a
new symlinked directory can be introduced into a protected tree undetected.

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile, os
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    frozen = sf.manifest(skill)
    os.symlink(skill/'templates', skill/'scripts'/'vendor', target_is_directory=True)
    r = sf.verify(frozen, skill)
    print('status', r['status'], 'added=', r['added'], 'escapes=', r['symlink_escapes'])
    print('in manifest files?', 'scripts/vendor' in sf.manifest(skill)['files'], 'count', sf.manifest(skill)['count'], 'vs', frozen['count'])
"
```
**Observed output**
```
status PASS added= [] escapes= []
in manifest files? False count 10 vs 10
```
**Expected.** Either record the symlink directory itself (path + target) in the manifest, or report it as
`added`. Silently ignoring it contradicts "受保护条目下的所有文件以及 symlink 目录本身（用于越界检测）".
**Exploit.** An undetected new symlinked directory inside e.g. `scripts/` can redirect an import path or
tool resolution to another in-root directory without any freeze signal. Nuisance/false negative.

---

### E-10 — MEDIUM — `guard_errors` has a large false-negative surface (and is dead code)
**File:** `scripts/source_freeze.py:100-107` (`_PROTECTED_TOKENS`/`_SHELL_TOKENS`/`_EXEC_TOKENS`), `:418-458` (plain substring matching)

**What is wrong.** Matching is literal substring matching, so trivial re-encodings pass. Worse,
`guard_errors` is not imported or called anywhere in production (`grep -rn guard_errors scripts/`
hits only `source_freeze.py` and `test_source_freeze.py`), so this is a pure false-negative nuisance.

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness
import source_freeze as sf
cases = {
 'protected name split across keys': {'a':'scripts','b':'guard.py'},
 'windows separator':                {'target':'scripts\\\\guard.py'},
 'windows traversal':                {'target':'..\\\\..\\\\etc\\\\passwd'},
 'fullwidth pipe':                   {'cmd':'rm -rf build ｜ bash'},
 'newline-separated shell':          {'cmd':'rm -rf build\\ncurl http://evil/x'},
 'base64 payload':                   {'cmd':'aW1wb3J0IG9zOyBvcy5zeXN0ZW0oJ3JtIC1yZiAvJyk='},
 'embedded absolute path':           {'note':'write to /etc/passwd'},
 'single-bracket redirect':          {'cmd':'cat</etc/passwd'},
 'bare protected dir name':          {'target':'scripts'},
 'bytes value':                      {'target':b'scripts/guard.py'},
}
for name, c in cases.items(): print(f'{name:34} ->', sf.guard_errors(c))
"
```
**Observed output**
```
protected name split across keys -> []
windows separator                -> []
windows traversal                -> []
fullwidth pipe                   -> []
newline-separated shell          -> []
base64 payload                   -> []
embedded absolute path           -> []
single-bracket redirect          -> []
bare protected dir name          -> []
bytes value                      -> []
```
**Expected.** At minimum: normalise separators, split/inspect multi-token values as path components,
check `..` per component, treat `<`, `&`, newline and fullwidth shell characters as metacharacters, and
inspect `bytes`.
**Exploit.** None in production (unused). If it is ever wired into a policy gate, every case above is an
approval for a malicious candidate.

---

### E-11 — LOW — `allow_canonical=True` is not bound to any route
**File:** `scripts/source_freeze.py:391-394` (only `resolved.name == STATE_NAME` is checked)

**What is wrong.** The guard names a single canonical `research-state.json` per run, but the exemption is
global: with `allow_canonical=True`, a `research-state.json` under *any* directory (a different route,
`/tmp`, even `/etc`) is allowed.

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile, pathlib
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    for p in [pathlib.Path(t)/'other-route/research-state.json', '/etc/research-state.json']:
        print(p, '->', sf.guard_write(p, skill_root=skill, allow_canonical=True)['code'])
"
```
**Observed output**
```
/tmp/tmpXXXX/other-route/research-state.json -> ALLOWED
/etc/research-state.json -> ALLOWED
```
**Expected.** Bind `allow_canonical` to the caller's route (the API has no route parameter, hence no
binding is even possible). Nuisance; a stage that raises the flag for its own state also unblocks every
other state file.

---

### E-12 — LOW — `SourceFreeze(route_dir=None)` records nothing, contradicting its docstring
**File:** `scripts/source_freeze.py:594-599` (docstring "退出时取清单，退出时核验并记录事件"), `:617-629` (`if self.route_dir is not None:`)

**What is wrong.** With the default `route_dir=None`, `__exit__` computes `self.result` but neither writes
a `VERIFY_PASS` nor a `HOLD` event, and leaves `self.event is None` with no warning.

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    with sf.SourceFreeze(root=skill) as fz: pass
    print('result=', fz.result['status'], 'event=', fz.event, 'hold=', fz.hold)
"
```
**Observed output**
```
result= PASS event= None hold= None
```
**Expected.** Either raise/document that `route_dir` is required for auditing, or say "records an event
only when `route_dir` is given". `preset_router.py:3041` always passes `route_dir`, so this is latent.

---

### E-13 — LOW — the audit writer itself is unguarded: a mis-set `route_dir` writes into protected areas
**File:** `scripts/source_freeze.py:465-493` (`record_integrity_event`), `:534` (called from `hold_on_violation`)

**What is wrong.** Neither function consults `guard_write`. `route_dir` is trusted. If it points at the
Skill root (or a protected subdirectory), the `HOLD` event is written *into the frozen tree*.

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    with sf.SourceFreeze(root=skill, route_dir=skill, context='misconfig') as fz:
        (skill/'SKILL.md').write_text('tampered\n')
    print('result:', fz.result['status'], 'HOLD log in skill root?', (skill/sf.INTEGRITY_NAME).is_file())
    print('guard on the log path:', sf.guard_write(skill/sf.INTEGRITY_NAME, skill_root=skill)['code'])
"
```
**Observed output**
```
result: VIOLATION HOLD log in skill root? True
guard on the log path: ALLOWED
```
**Expected.** The audit writer should validate `route_dir` against the allowed route, or the caller
should have to pass an already-vetted route. Also note the log filename is neither `PROTECTED` nor hidden,
so `guard_write` would not stop it even if consulted — the audit log is writable/deletable by design.

---

### E-14 — LOW — `guard_write` approves the Skill root itself and directories (`_protected_relpath(".")` is False)
**File:** `scripts/source_freeze.py:154-156` (`parts[0] in PROTECTED`, `bool(parts)` guard), `:380-384`

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile, pathlib
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    print('skill root ->', sf.guard_write(skill, skill_root=skill)['code'])
    print('allowed root dir ->', sf.guard_write(route, skill_root=skill, allowed_roots=[route])['code'])
"
```
**Observed output**
```
skill root -> ALLOWED
allowed root dir -> ALLOWED
```
**Expected.** A directory target should be rejected (or at least classified distinctly); a target equal to
the Skill root is the one path whose protection set is definitionally everything.
**Exploit.** Nuisance: an `ALLOWED` verdict for a directory cannot itself overwrite a file, but a caller
that renames/removes based on the verdict gets a green light.

---

### E-15 — LOW/INFO — `ALLOWED_WRITE_SCOPES` is decorative; `verify()['checked']` misreports
**File:** `scripts/source_freeze.py:89-92`, `:329` (`"checked": len(expected)`)

`grep -rn "ALLOWED_WRITE_SCOPES" scripts/` shows only the definition and one test assertion
(`test_source_freeze.py:141`); no production code reads it — write scope is decided solely by
`allowed_roots`, as its own comment concedes. `checked` reports `len(expected)` (the manifest size), not
the number of files actually inspected, so a completely vanished tree still reports `checked: 135`.
Both INFO.

---

### E-16 — LOW — change-and-change-back inside the context window is undetected
**File:** `scripts/source_freeze.py:611-612` (`__enter__` = snapshot), `:615-630` (`__exit__` = compare)

**Reproduction**
```bash
cd /tmp/sfaudit
python3 -c "
import harness, tempfile
with tempfile.TemporaryDirectory() as t:
    skill, route = harness.build(t)
    import source_freeze as sf
    with sf.SourceFreeze(root=skill, route_dir=route, context='swap') as fz:
        p = skill/'SKILL.md'; orig = p.read_text(); p.write_text('EVIL\n'); p.write_text(orig)
    print('result:', fz.result['status'], 'events:', [e.get('action') for e in sf.integrity_events(route)])
"
```
**Observed output**
```
result: PASS events: ['VERIFY_PASS']
```
**Expected.** This is inherent before/after TOCTOU. The `residual_risks` list mentions TOCTOU only for
the *symlink* snapshot, not for content revert; the deployment doc should say the digest check is a
before/after comparison and cannot prove the tree was unchanged in between. INFO/nuisance; a
`VERIFY_PASS` event is written even though the source was modified during the run.

---

## SUSPECTED (reasoned, not reproduced on this host)

### S-1 — Case-insensitive filesystems defeat the name comparisons
`_protected_relpath` (`:154-156`) and `_hidden_eval_reason` (`:159-169`) compare `PROTECTED` /
`_HIDDEN_EVAL_*` entries with `==` on the on-disk component. On a case-insensitive filesystem, an attacker
writing to `.../skill.md` / `SKILL.MD` / `references/.DEV/x` may have the OS resolve it to the protected
path while the guard's string compare misses it. Could not reproduce on this Linux/ext4 host
(`os.path.realpath` does not canonicalise case here).

### S-2 — Windows path canonicalisation gaps
Path components with trailing dots/spaces (`".. "`, `"SKILL.md."`) are stripped by Win32 before opening,
so a lexically non-traversing component could still resolve to `..` or to a protected name. The `..`
check at `:348` is lexical only. Not reproducible on Linux.

### S-3 — Poisoned `.pyc` under an excluded `__pycache__`
E-8 shows `scripts/__pycache__/*.pyc` is outside the manifest. Python may load a stale/matching `.pyc`;
if the source mtime/size can be spoofed, the payload executes without any freeze signal. Not demonstrated
(requires building a matching magic+mtime/size header).

---

## Checked and NOT a bug (valuable negative results)

- **N-1 — `..` detection is sound for the variants tested.** `a/../b`, `./scripts/guard.py`,
  `scripts/./guard.py`, `scripts//guard.py`, `a//b`, `....//SKILL.md`, `a/..%2f/b`, trailing slash: all
  either raise `PATH_TRAVERSAL` or resolve to the correct protected/non-protected verdict. `Path.parts`
  normalises `//`, `.`, and `....` is a literal name, not traversal. `sfaudit` run:
  `a/../b -> PATH_TRAVERSAL`, `./scripts/guard.py -> PROTECTED_SKILL_SOURCE`, `scripts/./guard.py -> PROTECTED_SKILL_SOURCE`,
  `scripts//guard.py -> PROTECTED_SKILL_SOURCE`, `....//SKILL.md -> ALLOWED (resolves to skill/..../SKILL.md)`.
- **N-2 — NUL byte is fail-closed.** `guard_write('a\x00b')` → `{"allowed": false, "code": "RESOLUTION_ERROR", "reason": "...lstat: embedded null character in path..."}`. Empty target → `PATH_TRAVERSAL`.
- **N-3 — a protected file replaced by a symlink to an identical copy *outside* the root IS detected.** `_symlink_escapes` fires: `manifest` reports `symlink_escapes: ['SKILL.md']`, `verify` → `VIOLATION`. (The in-root variant is E-5.)
- **N-4 — broken symlinks and symlink loops do not hang or crash.** Loop `loopA -> loopB -> loopA` is walked without recursion (yielded only), recorded with `sha256: None, symlink: True`; `os.walk` does not follow it. A broken symlink pointing outside is caught by `symlink_escapes`; `guard_write` on it → `SYMLINK_ESCAPE`. A broken symlink pointing inside-root resolves to the (missing) real path and is judged by that path.
- **N-5 — a symlink whose parent directory is a symlink is handled.** `os.path.realpath` resolves chains; `route/sub -> skill/references`, target `route/sub/policy.md` → real path under `references/` → `PROTECTED_SKILL_SOURCE`.
- **N-6 — symlink inside the root to another file inside the root: writing through it is correctly classified by the *real* target.** `route/link -> skill/SKILL.md` → `PROTECTED_SKILL_SOURCE`; a symlink to a non-protected in-root file is `ALLOWED` (reasonable).
- **N-7 — concurrent append is serialized correctly.** 4 processes × 50 `record_integrity_event` calls → 200 events, `seq` contiguous `1..200`, and every `previous` equals `_line_digest` of the preceding raw line. The flock+read+append sequence is correct.
- **N-8 — `manifest()` completeness on the real Skill root.** `manifest()['count'] == 135`, `protected_files() == 135`, and an independent `find` over the 9 `PROTECTED` entries (with the same exclusions) returned exactly 135; the symmetric difference was empty. `schemas/` and `router-fixtures.json` exist and are included; `.dev/`, `examples/`, `__pycache__/` are excluded as documented. No silently missing top-level protected path.
- **N-9 — `SourceFreeze.__exit__` on a body exception still verifies and records, and `self.result` is set.** `with SourceFreeze(...): raise RuntimeError` → record written, `fz.result['status'] == 'PASS'`, exception propagates (`return False` is correct).
- **N-10 — `guard_errors` rejects the single-token cases the 16 tests cover:** `SKILL.md`, `scripts/…`, `;`, `&&`, `|`, `$(`, backtick, `>`, `import `, `exec(`, `../`. Those tests are not vacuous; they just cover the easy encodings (E-10 covers the bypasses).
- **N-11 — `hold_on_violation` correctly writes `HOLD` and `repair_attempted: false` for a real `verify` VIOLATION, and does not repair source.** `{}` (empty dict) is also treated as a violation, not a pass.
- **N-12 — `write_manifest` round-trips and cleans up its `.pending` file** (`test_write_manifest_is_atomic_and_load_round_trips` is accurate). No `fsync` of the directory is performed, but atomicity via `os.replace` holds within a filesystem.
