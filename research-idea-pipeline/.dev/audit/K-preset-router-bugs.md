# K — preset_router.py 对抗审计：Skill-RSI 控制平面（branch-local）

> 目标：`research-idea-pipeline/scripts/preset_router.py`（Skill-RSI 层，c9fb540..d23cbf1）。
>
> **重要：审查期间 HEAD 移动了。** 开始时 HEAD=`d23cbf1`；审查过程中其它提交落到本分支
> （`751454d`、`2365069`、`790c816`、`7ddde7f`），`source_freeze.py` 的未提交修改也被提交。
> 因此本报告以 **当前 HEAD=`7ddde7f`** 为主基线，所有 CONFIRMED 结论都在该 HEAD 上重新复现过；
> 同时标注在 `d23cbf1` 基线是否也存在，以及被并发提交修掉的项。
>
> 复现方式：全部为真实运行的真 fixture（`pr._fixture` / `examples/preflight-identifiability/ct-mri.json`），
> 无 mock、无源码改动。复现脚本放在 `/tmp`，正文给出等价的最小命令。

---

## 0. 测试套件与发布闸门（精确计数）

**当前 HEAD=`7ddde7f`：**

```
$ python3 -m unittest discover -s scripts -p 'test_*.py'
Ran 1695 tests in 13.274s
OK (skipped=3)
exit=0

$ python3 scripts/release_check.py | tail -1
PASS
exit=0
```

**审查起点 `d23cbf1`（当时工作树另有 `source_freeze.py`/`test_source_freeze.py` 未提交修改）：**

```
$ python3 -m unittest discover -s scripts -p 'test_*.py'
Ran 1685 tests in 9.721s
FAILED (failures=3, skipped=3)
  3 × test_structural_equivalence（examples/structural-equivalence/paradigm-candidate.json EQ8）
$ python3 scripts/release_check.py | tail -1
FAIL
```

即 `d23cbf1` 基线的 3 个失败与发布 FAIL 均来自 Structural Equivalence fixture
（`collapse_result: "collapses"` 与 verdict `paradigm-candidate` 不相容），与 preset_router 无关，
已由后续提交修复。

---

## 1. 每个 preset 的实际写入（问题 1）

在 `7ddde7f` 上对 `pr.PRESET_IDS` 全部 16 个 preset，同一 fixture、分别 `apply=False`/`apply=True`，
对 route 目录做前后文件哈希快照。结果：

| preset | scope/权限 | apply=False 新建/修改 | apply=True 新建/修改 |
|---|---|---|---|
| research-loop | execute | 无 | `source-integrity.jsonl`, `.head`, `.source-integrity.lock` |
| paradigm-escape | discover_only | 无 | `source-integrity.jsonl(+head/lock)` |
| research-recovery | derived（BLOCKED） | 无 | 无 |
| scientific-replanning | advisory（HOLD） | 无 | 无 |
| **research-audit** | **read_only** | 无 | **无** |
| **research-review** | **read_only** | 无 | **无** |
| context-drift-recovery | derived | 无 | 无（NO_CHANGE 分支） |
| stagnation-breaker | advisory | 无 | 无 |
| experiment-failure-recovery | derived | 无 | 无 |
| evidence-conflict-repair | discovery | 无 | 无 |
| resource-recovery | derived | 无 | 无 |
| memory-consolidation | derived | 无 | `cognition/index.json`, `cognition/context-brief.md`, `source-integrity.jsonl(+head/lock)` |
| **loop-health-check** | **read_only** | 无 | **无** |
| strategy-evolution | strategy | 无 | `scheduler.json`（改写）, `source-integrity.jsonl(+head/lock)` |
| hypothesis-rebalance | strategy | 无 | 无 |
| **discovery-replay** | **read_only** | 无 | **无** |

结论（HEAD）：**四个 read_only preset 在 `--apply` 下不再写任何控制平面文件**。
`decision-trajectory.jsonl` / `policy/` 没有任何 read_only preset 会写（它们只出现在
research-loop 的 apply 派发路径与策略生命周期命令中）。

**但在 `d23cbf1` 基线这是真 bug（K-1，已在后续提交修复，保留记录）：**

```
$ python3 - <<'PY'
import json,sys,tempfile,pathlib
sys.path.insert(0,'scripts'); import preset_router as pr
tmp=tempfile.mkdtemp(); sp=pr._fixture(pathlib.Path(tmp)/'A')
for pid in pr.PRESET_IDS:
    p,_,c=pr.run_preset(pid, sp, apply=True)
    if p['execution_scope'] in ('audit','read_only','inspect_only','evaluation_only'):
        print(pid, p['status'], 'writes=', p['writes'],
              'integrity=', p.get('source_integrity',{}).get('status'))
PY
```
`d23cbf1` OBSERVED：`research-audit/research-review/loop-health-check/discovery-replay`
全部 `status=OK code=0`、`writes=[]`、`source_integrity=PASS`，但 route 目录被创建
`source-integrity.jsonl` + `.head` + `.source-integrity.lock`。
这是「只读 preset 写控制平面」+「`writes` 谎报」+ 违反各自 protocol §8 写入集合
（`presets/research-review.md:50`「只读，不写任何阶段产物」）。
`7ddde7f` 已改为仅在 `apply and (violated or payload["writes"])` 时写审计事件，问题消失。

---

## 2. CONFIRMED findings（均在 `7ddde7f` 复现）

### K-2 · HIGH · 损坏的 policy 存储以 `UnicodeDecodeError` 逃出 `run_preset`
- 位置：`scripts/preset_router.py:2085`（`scoped_policy_state` →`pe.load_records`）→
  `scripts/decision_trajectory.py:130`（`load_chained` 的 `path.read_text`）。
- 问题：`scoped_policy_state` 的新逻辑把 `load_records(tolerant=True)` 的 diagnostics 当作
  「tampered→HOLD」。但 `tolerant=True` 只覆盖 JSON 解析/链错误；`read_text` 的
  `UnicodeDecodeError`（非法 UTF-8）**不是** `Diagnostic`，且 `run_preset` 新加的
  `except (cg.CognitionError, OSError)`（`preset_router.py:3083`）不包含 `UnicodeDecodeError`
  （它是 `ValueError` 子类），于是直接 traceback。可读但非 UTF-8 的策略日志 = 任何人能放进
  route 的坏字节，就能让路由崩溃而不是 HOLD。
- 复现：
```
$ cd research-idea-pipeline && python3 - <<'PY'
import json,sys,tempfile,pathlib
sys.path.insert(0,'scripts'); import preset_router as pr
tmp=tempfile.mkdtemp(); route=pathlib.Path(tmp)/'A'; sp=pr._fixture(route)
(route/'policy').mkdir()
(route/'policy'/'candidates.jsonl').write_bytes(b'\xff\xfe{"record":"candidate"}\n')
pr.run_preset('research-loop', sp, apply=False)
PY
```
- OBSERVED：
```
  File ".../decision_trajectory.py", line 130, in load_chained
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
```
- 预期：产出 `HOLD`，`hold_reason=policy_store_tampered`（或 `handler_error`），附带可诊断事件，
  不得有 traceback。
- 性质：**回归**（c9fb540 新增 tampered 语义；2506405/790c816 的异常收窄未覆盖 `ValueError`）。
  `d23cbf1` 同样存在（当时已是 traceback）。

### K-3 · HIGH · 非法 UTF-8 的 `decision-trajectory.jsonl` 逃出新加的 `except`
- 位置：`scripts/preset_router.py:2238-2247`（`dt.append_record` 的 try 只捕获
  `(dt.TrajectoryError, OSError)`）；底层 `decision_trajectory.py:130` 抛 `UnicodeDecodeError`。
- 问题：新增注释明确写「A damaged trajectory store must produce a diagnosable HOLD, not a
  traceback」，但只覆盖了 `TrajectoryError`/`OSError`。损坏的 UTF-8 轨迹日志绕过该保护。
  （可读性权限错误 `PermissionError` 是 `OSError`，已被正确转成
  `decision_trajectory_unreadable`；只有编码损坏漏网。）
- 复现（需 dispatch 真正 applied；用 recorded strategy decision 即可）：
```
$ cd research-idea-pipeline && python3 - <<'PY'
import json,sys,tempfile,pathlib
sys.path.insert(0,'scripts'); import preset_router as pr, cognition as cg
tmp=tempfile.mkdtemp(); route=pathlib.Path(tmp)/'A'; sp=pr._fixture(route)
st=json.loads(sp.read_text())
for e in st['experiments']:
    if e['status'] in ('planned','running'): e['status']='completed'
sp.write_text(json.dumps(st)); cg.op_build(sp, route/cg.COGNITION_DIRNAME)
(route/cg.SCHEDULER_NAME).write_text(json.dumps({"state_version":st['state_version'],
  "next_actions":[{"action":"R1","type":"repair","target":"C1","eig":"high","cost":"low"}],
  "eig_calibration":{"records":[]},"operator_stats":{"by_operator":{}},
  "strategy_decisions":[{"state_version":st['state_version'],"adopted":True,
                         "dispatch":{"action":"R1"}}]}))
(route/'decision-trajectory.jsonl').write_bytes(b'\xff\xfe{"record":"decision"}\n')
pr.run_preset('research-loop', sp, apply=True)
PY
```
- OBSERVED：
```
  File ".../decision_trajectory.py", line 130, in load_chained
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
```
- 预期：`HOLD` + `write_failure=decision_trajectory_unreadable: UnicodeDecodeError`。
- 性质：**回归**（2506405 新增该 try/except 时覆盖不全）。

### K-4 · MEDIUM/HIGH · apply 运行写入审计事件失败时 `PermissionError` 逃出 `run_preset`
- 位置：`scripts/preset_router.py:3101-3115`（`sf.hold_on_violation` / `sf.record_integrity_event`），
  底层 `source_freeze.py:717`。该块在 handler 的 try/except 之外，无任何保护。
- 问题：`apply=True` 且 `payload["writes"]` 非空（research-loop 的 `writes` 永远非空；
  strategy-evolution 会写 scheduler）时，会尝试在 route 写 `source-integrity.jsonl`；
  若 route 不可写（只读挂载、权限错误），审计写入本身抛 `OSError` 并 traceback。
  审计是"记录"语义，失败不应让整次运行崩溃。
- 复现：
```
$ cd research-idea-pipeline && python3 - <<'PY'
import json,sys,os,tempfile,pathlib
sys.path.insert(0,'scripts'); import preset_router as pr, cognition as cg
tmp=tempfile.mkdtemp(); route=pathlib.Path(tmp)/'A'; sp=pr._fixture(route)
st=json.loads(sp.read_text())
(route/cg.SCHEDULER_NAME).write_text(json.dumps({"state_version":st['state_version'],
  "next_actions":[{"action":"R1","type":"repair","target":"C1","eig":"high","cost":"low"}],
  "eig_calibration":{"records":[]},"operator_stats":{"by_operator":{}}}))
os.chmod(route,0o555)
try: pr.run_preset('strategy-evolution', sp, apply=True)
finally: os.chmod(route,0o755)
PY
```
- OBSERVED：
```
  File ".../preset_router.py", line 3107, in run_preset
    event = sf.record_integrity_event(context["route_dir"], {
  File ".../source_freeze.py", line 717, in record_integrity_event
    with lock_path.open("a", encoding="utf-8") as lock:
PermissionError: [Errno 13] Permission denied: '.../.source-integrity.lock'
```
  `research-loop apply=True` 同样逃出（无 handler 写入时 `writes` 仍非空）。
- 预期：审计事件写失败应降级为可诊断的 HOLD（或 warning），退出码 4，而不是 traceback。
- 性质：**回归**（2365069 引入「审计事件在 handler 之后单独写」的新路径；
  `d23cbf1` 的 `freeze.__exit__` 也会抛同一 `PermissionError`，同样 traceback）。

### K-5 · MEDIUM · 无策略时仍报 `policy_delta: applied / L2`（假 Delta）
- 位置：`scripts/preset_router.py:2214-2217`。
- 问题：新增注释声称「A policy delta exists only when a policy actually changed the dispatched
  action」，但条件只要求 `dispatch["applied"]` + `strategy_changed_dispatch` + `dispatched_action`，
  未要求 `dispatch["policy_id"]` 非空。记录的上一轮策略决策（`source=recorded_strategy_decision`,
  `policy_id=None`）重排了动作时，仍会写出 `{"status":"applied","level":"L2","policy_id":null}`
  ——没有任何策略存在却报告 L2 策略生效。
- 复现（`/tmp/repro_false_delta.py`）：
```
$ cd research-idea-pipeline && python3 - <<'PY'
import json,sys,tempfile,pathlib
sys.path.insert(0,'scripts'); import preset_router as pr, cognition as cg
tmp=tempfile.mkdtemp(); route=pathlib.Path(tmp)/'A'; sp=pr._fixture(route)
st=json.loads(sp.read_text())
for e in st['experiments']:
    if e['status'] in ('planned','running'): e['status']='completed'
sp.write_text(json.dumps(st)); cg.op_build(sp, route/cg.COGNITION_DIRNAME)
(route/cg.SCHEDULER_NAME).write_text(json.dumps({"state_version":st['state_version'],
  "next_actions":[{"action":"R1","type":"repair","target":"C1","eig":"high","cost":"low"},
                  {"action":"R2","type":"repair","target":"C2","eig":"high","cost":"low"}],
  "eig_calibration":{"records":[]},"operator_stats":{"by_operator":{}},
  "strategy_decisions":[{"state_version":st['state_version'],"adopted":True,
                         "dispatch":{"action":"R2"}}]}))
p,_,_=pr.run_preset('research-loop', sp, apply=False)
print(p['decision']['policy_delta'], p['observed']['scoped_policy']['source'])
PY
```
- OBSERVED：
```
{'status': 'applied', 'level': 'L2', 'policy_id': None, 'scope': None} recorded_strategy_decision
```
- 预期：策略增量只在真正有 ACTIVE scoped policy 改写排序时出现（或显式区分
  `source=recorded_strategy_decision`），否则 `{"status":"none",...}`。
- 性质：**回归**（c9fb540 引入 policy_delta；2506405 收紧了判定但漏了 `policy_id`）。

### K-6 · LOW/MEDIUM · tampered policy store 用 HOLD 覆盖 handler 的 BLOCKED（退出码错）
- 位置：`scripts/preset_router.py:2190-2200`：`_loop_step` 先按 state 得到 `status=BLOCKED`
  （如缺 contract → `blocked=True`），随后 `if dispatch.get("tampered"): status="HOLD"` 无条件覆盖。
- 复现：
```
$ cd research-idea-pipeline && python3 - <<'PY'
import json,sys,tempfile,pathlib
sys.path.insert(0,'scripts'); import preset_router as pr
tmp=tempfile.mkdtemp(); route=pathlib.Path(tmp)/'A'; sp=pr._fixture(route)
st=json.loads(sp.read_text()); st['contract']={}; sp.write_text(json.dumps(st))
(route/'policy').mkdir()
(route/'policy'/'candidates.jsonl').write_text('{"record":"candidate","policy_id":"X"}\n')
p,_,code=pr.run_preset('research-loop', sp, apply=False)
print(p['status'], code, p.get('hold_reason'))
PY
```
- OBSERVED：`HOLD 4 policy_store_tampered`（`_loop_step` 返回 `blocked=True`，本应 `BLOCKED`/`EXIT_HARD=3`）。
- 预期：BLOCKED（合同/硬门禁问题）优先于 HOLD；至少两者都出现在 payload 中，不能被静默降级。
- 性质：**回归**（2506405 新增的 tampered 分支）。

### K-7 · LOW · 仍为 ACTIVE 的策略因「更晚的 ACTIVE 策略随后 HOLD」而被静默丢弃
- 位置：`scripts/policy_evolution.py:628-633`（`rebuild_state` 的 `active` 指针只记最后一次
  `to==ACTIVE` 的转移）与 `:640-656`（`active_policy` 要求该指针的 `latest_status=="ACTIVE"`），
  经 `preset_router.py:2089` 的 `scoped_policy_state` 暴露。
- 复现：
```
$ cd research-idea-pipeline && python3 - <<'PY'
import sys,tempfile,pathlib
sys.path.insert(0,'scripts'); import preset_router as pr, policy_evolution as pe, decision_trajectory as dt
def c(i): return {"record":"candidate","policy_id":i,"status":"PROPOSED","origin_stamped":True,
                  "source_route":"A","scope":{"scope_kind":"route"}}
def t(i,f,to): return {"record":"transition","policy_id":i,"from":f,"to":to,"at":"x","reason":"r","level":"L1"}
recs=[c("P1"),t("P1","PROPOSED","ACTIVE"),c("P2"),t("P2","PROPOSED","ACTIVE"),t("P2","ACTIVE","HOLD")]
tmp=tempfile.mkdtemp(); sp=pr._fixture(pathlib.Path(tmp)/'A')
p=pe.candidates_path(sp); p.parent.mkdir(parents=True,exist_ok=True)
for r in recs: dt.append_chained(p,r)
print("latest", pe.latest_status(recs))
print("active_id", pe.rebuild_state(recs)["active_policy_id"])
print("consumed", pr.scoped_policy_state(pr.project_context(sp))["candidate"])
PY
```
- OBSERVED：`latest_status={'P1':'ACTIVE','P2':'HOLD'}`，`rebuild_state().active_policy_id='P2'`，
  `scoped_policy_state().candidate=None`。即 P1 仍 ACTIVE，却因指针指向已 HOLD 的 P2 而不被消费。
- 预期：`rebuild_state` 的 active 指针应指向当前状态仍为 ACTIVE 的策略，或对「多个/悬空 ACTIVE」
  报 fail-closed 诊断；不应出现「快照说 P2 是 active，而 P2 的状态是 HOLD」。
- 性质：**已存在**（policy_evolution 属 Phase 4/5），但由本文件的深层消费者在 review 目标内暴露。
  该路径是 fail-closed（不误用策略），所以定级 LOW。

### K-8 · LOW · 裸相对路径使 `route=""` / `project=""`，并削弱跨项目迁移门
- 位置：`scripts/cognition.py:403`（`route_of` 取 `state_path.parent.name`）；使用点
  `preset_router.py:2226`（`route=cg.route_of(...)` / `project=ctx["route_dir"].name`）与
  `preset_router.py:2121`（`cross_project_transfer_allowed(current_route=...)`）。
- 复现（`/tmp/repro_bare.py`）：`cd <tmp> && python3 ... run_preset('research-loop','research-state.json',apply=True)`
  （fixture 由 `pr._fixture(Path('.'))` 建在 cwd）。
- OBSERVED：轨迹记录 `route=""`；`cross_project_transfer_allowed` 在 `current_route=""` 且候选
  **未打戳**（无 `origin_stamped`）时返回 `NOT_REQUIRED`（`policy_evolution.py:1114-1121`），
  即迁移门被绕过；正常路由（`current_route` 非空）会 BLOCK。
- 预期：`route_of` 对空 parent 给出可诊断的错误/拒绝，而不是静默产生空路由；或迁移门对空
  `current_route` 一律 fail-closed。
- 性质：**已存在**（route_of），新消费路径放大了后果。

### K-9 · LOW · symlink state 下 policy 存储与 scheduler/轨迹/认知/审计存储分家
- 位置：`policy` 走 realpath（`policy_evolution.py:190` `Path(state_path).resolve().parent/policy`），
  而 `route_dir`/`scheduler`/`cognition`/`decision-trajectory`/`source-integrity` 走词法
  `state_path.parent`（`preset_router.py:2221`、`cognition.py:2169`、`source_freeze` 的 route）。
- 复现（`/tmp/repro_symlink_route2.py`）：`B/research-state.json` 为真文件，`A/research-state.json`
  是 symlink → `../B/research-state.json`；B 放 `policy/candidates.jsonl`。
- OBSERVED：
```
route_of -> 'A' | policy store dir -> .../B/policy
A/ source-integrity: True | B/ source-integrity: False
```
  路由 A 读 B 的策略存储，却把审计/轨迹/Scheduler 写到 A。两套路径解析规则不一致。
- 预期：同一 route 的所有控制平面存储使用同一（解析后的）根，或显式拒绝 symlink state。
- 性质：**回归/新暴露**（policy 的 realpath 是既有行为，但新消费者把二者放在同一次运行里）。

### K-10 · LOW · 孤儿 `.head` 不被视为 tamper（与 source_freeze 不一致）
- 位置：`scripts/decision_trajectory.py:127-128`：`if not path.exists(): return [], diagnostics`
  —— 完全忽略 `.head`。对比 `source_freeze._load_integrity_chain` 明确报
  「存在 head 摘要但日志缺失」。
- 复现：
```
$ cd research-idea-pipeline && python3 - <<'PY'
import sys,tempfile,pathlib
sys.path.insert(0,'scripts'); import preset_router as pr
tmp=tempfile.mkdtemp(); sp=pr._fixture(pathlib.Path(tmp)/'A')
pol=sp.parent/'policy'; pol.mkdir(); (pol/'candidates.jsonl.head').write_text('sha256:deadbeef')
print(pr.scoped_policy_state(pr.project_context(sp))['tampered'])
PY
```
- OBSERVED：`False`（无诊断）。而 `.head` 存在但过期时有记录时会正确 tampered=True。
- 预期：与 source_freeze 一致，孤儿 head 也是截断/删除证据 → tampered/诊断。
- 性质：**回归**（c9fb540 的 tamper 语义不完整）。实际影响有限（无日志则无策略可消费）。

### K-11 · SUSPECTED · handler 错误路径丢 `_schema`，且「违规即使只读也记录」与代码不符
- 位置：`scripts/preset_router.py:3083-3096`（新构造的 HOLD payload 无 `_schema`，与
  `_result` 的契约不一致）；`:3099-3115`（注释称 read-only preset 遇源码违规也记录安全事件，
  但条件是 `apply and (violated or ...)`，`apply=False` 时 `violated` 不会写事件）。
- 说明：read-only 运行期间源码被外部改动 → `violated=True`、`status=HOLD`，但没有
  `source-integrity.jsonl` 事件，与注释/安全预期矛盾。未做真复现（需运行期改源码，本任务禁止
  修改除报告外的文件），按代码事实记为 SUSPECTED。`_schema` 缺失是可静态确认的小契约漂移。

### K-12 · SUSPECTED · `project_context` 在 try 之外 → malformed scheduler.json 仍 traceback
- 位置：`scripts/preset_router.py:3072`（`context = project_context(...)` 在
  `:3081` 的 try 之前）；`cognition.load_scheduler:2134` 把非法 JSON 转成 `CognitionError`。
- 复现：
```
$ cd research-idea-pipeline && python3 - <<'PY'
import sys,tempfile,pathlib
sys.path.insert(0,'scripts'); import preset_router as pr, cognition as cg
tmp=tempfile.mkdtemp(); route=pathlib.Path(tmp)/'A'; sp=pr._fixture(route)
(route/cg.SCHEDULER_NAME).write_text('{not json')
pr.run_preset('research-review', sp, apply=False)
PY
```
- OBSERVED：`CognitionError: scheduler is not valid JSON: ...`（未捕获，traceback）。
- 预期：`HOLD`/`EXIT_ENV` + 可诊断环境错误；790c816 的「handler failures → HOLD」没有覆盖
  上下文加载阶段。**已存在**。

### K-13 · SUSPECTED · research-loop apply 的并发/写入申报问题
- 位置：`scripts/preset_router.py:2248-2257`（`scheduler.json` 用 `write_text` 明文重写，无
  `flock`；对比 `decision_trajectory.append_chained` 用 `store_lock`）与 `:2240-2241`
  （`outcome["status"] == "DUPLICATE"` 也把 `decision-trajectory.jsonl` 记入 `writes`，
  尽管没有任何写入）。
- 说明：两个并发 `research-loop apply=True`（active-policy 派发路径）会各自基于旧
  `ctx["scheduler"]` 重写整份 scheduler，后写者覆盖先写者的 `strategy_decisions[]` 追加；
  轨迹因有锁会两条都在。未做确定性并发复现，按代码事实记为 SUSPECTED。
  `DUPLICATE` 谎报写入是可静态确认的（并会让 2365069 的审计条件
  `payload.get("writes")` 误判为"本次有写入"）。

---

## 3. 检查过、确认 NOT a bug（负结果）

- **Q1 HEAD 结论**：read_only preset 在 `apply=True` 下不写任何控制平面文件（见 §1 表）；
  只有 apply 才可能写审计，且只对「声明了写入或违规」的 preset。`d23cbf1` 的 K-1 已修复。
- **Q2(a) 覆盖 next_actions/eig_calibration/operator_stats**：否。
  `strategy_memory.record_strategy_decision`（`strategy_memory.py:1112-1143`）只改
  `strategy_decisions[]`；实测 `next_actions/eig_calibration/operator_stats` 逐字节保持
  （`/tmp/repro_loop_apply.py`）。`load_scheduler` 整体读取、不裁剪字段。
- **Q2(b) 无 source-freeze 包裹**：否。`run_preset` 对每次运行都造 `SourceFreeze`
  （`preset_router.py:3078-3097`），无旁路 handler 的调用者（`HANDLERS` 只被 `run_preset` 用）。
- **Q2(c) HOLD/BLOCKED 时写控制平面**：否。轨迹/Scheduler 写入条件含
  `step.get("dispatched_action")`，只有 `_loop_step` 的 scheduler 分支（`blocked=False, hold=False`）
  才设置它；HOLD/BLOCKED 分支均为 `None`。
- **Q2(e) 轨迹 `chosen` 与实际派遣不一致**：未发现。`chosen` 取 `step["dispatched_action"]`；
  `strategy_choice` 仅当它属于 `scheduler.next_actions` 时才生效（`preset_router.py:2054`），
  而 `sm.strategy_decision` 的合法集也来自 `next_actions`（`strategy_memory.py:947`），
  不存在「选了 next_actions 之外的动作却写进 `chosen`」的路径。
- **Q3（非链错误）**：`transition→HOLD` 结尾：不消费（安全）；候选自报 `status: ACTIVE` 无转移：
  不消费（`active_policy_id` 仅由转移/回滚设置）；`rollback` 指向后来 REJECTED 的策略：不消费；
  `.head` 缺失（有记录）或过期：tampered=True。仅 K-7（两个 ACTIVE + 后一个 HOLD）与
  K-10（孤儿 head）例外，已单列。
- **Q4 守卫/冷却/AALG 预算**：新路径不写 `cognition/recovery-log.jsonl`，也不触碰
  `.execution/policy.json`；`record_strategy_decision` 明确不改 `eig_calibration`/预算。
  未发现 `trigger()`/`recovery_guard()`/`op_record`/`op_trigger`/`signal_snapshot` 被新代码绕过。
  （注意：`run_preset` 从不查 ledger，这是既有设计，不是本次回归。）
- **Q5(a)(b)**：绝对路径与带父目录的相对路径得到相同 `route_of`/`route_dir`，不同 route 的
  存储互不串写（正常布局）。仅 K-8（空 parent）与 K-9（symlink）例外。
- **Q6 退出码映射**：`HOLD→EXIT_ENV(4)`、`BLOCKED→EXIT_HARD(3)`、其它→`EXIT_OK(0)` 一致；
  `payload["source_integrity"]` 在 HEAD 每次运行都带（intentional，不是隐藏状态泄漏）；
  `PR9`（只读改 canonical）诊断在 `payload["diagnostics"]` 赋值后才 `hard.append`，
  但该分支在当前 16 个 preset 中不可达（没有 read_only handler 会改 canonical），不列为确认 bug。
- **Q7 其它异常**：policy/trajectory 的 `PermissionError`（可读性）已被
  `run_preset` 的 `(CognitionError, OSError)` 转成 HOLD；非法 JSON 被转为 tamper 诊断；
  scheduler 写失败被 `:2256` 转成 `scheduler_telemetry_unwritable` HOLD。
  仍逃逸的仅 K-2/K-3（`UnicodeDecodeError`）、K-4（审计写入 `OSError`）、K-12（上下文加载）。

---

## 4. 建议的修复方向（不在本次改动范围）

1. `load_chained` 用 `errors="replace"` 或捕获 `(OSError, UnicodeDecodeError)` 并作为
   `Diagnostic` 返回；`run_preset` 的 handler catch 至少包含 `ValueError`。
2. 把 `record_integrity_event` 调用放进 try/except，失败降级为 HOLD/警告。
3. `policy_delta` 增加 `dispatch.get("policy_id")` 前置条件（或单独报告 recorded decision）。
4. tampered 分支不要覆盖更硬的 BLOCKED；`status` 冲突时保留最高严重度。
5. `rebuild_state`/`active_policy` 对多 ACTIVE/悬空指针 fail-closed；孤儿 head 视为 tamper。
6. route 统一 realpath 或拒绝 symlink state；`route_of` 对空 parent 拒绝。
7. `scheduler.json` 写入加锁（镜像 `store_lock`）；`DUPLICATE` 不计入 `writes`。
