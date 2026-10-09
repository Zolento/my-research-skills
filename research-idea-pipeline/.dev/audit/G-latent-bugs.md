# Skill-RSI 对抗式复核：未暴露缺陷清单（branch-local）

> 复核对象：`research-idea-pipeline/skill-rsi-dev` 在 `139f7b9` 上的 Skill-RSI 实现。
> 方法：4 路独立对抗审计（E/F 见 `.dev/audit/`）+ 主开发者的可执行复现探针（`/tmp/rsi-probe/probe*.py`）。
> **每条 CONFIRMED 都实跑过并保留观察到的输出**；SUSPECTED 单列。

## 严重度汇总

| 严重度 | 数量 | 已修复 | 未修复 |
|---|---|---|---|
| HIGH | 12 | 见下 | 见下 |
| MEDIUM | 16 | | |
| LOW / INFO | 12 | | |

---

## A. 决策轨迹（`decision_trajectory.py`）

### BUG-1 HIGH — append 的 read-then-lock TOCTOU（已修复）
`append_record` 先在锁外 `load_records` 计算 `seq`/`previous`，再在锁内 append。
复现：8 线程并发 append → **只有 4 行、seq 全部为 1、哈希链断裂、head 缺失**。
策略存储同样受影响（`append_chained`）。这是真实数据损坏，不是竞态噪声。
修复：把「读 + 校验 + 追加 + 写 head」全部放进同一把锁（`append_chained(validate=...)`），
并改用 per-store 锁文件名。复现探针现为 8 行 seq 1..8、链完整。

### BUG-2 HIGH — 轨迹身份含挂钟时间，重复派遣只在一秒内偶然被拦（已修复）
`trajectory_id` 基于含 `decided_at` 的 context digest；两条**同一决策**相隔 1 秒即得到不同 id，
都被接受。修复：新增 `decision_identity()`（剔除挂钟与遥测字段），并让 `_payload_digest`
忽略易变字段，使「同一决策晚一秒重提」返回 `DUPLICATE` 而「改写选择」仍返回 `DT2 INVALID`。

### BUG-3 MEDIUM — 文档声称 `DT0`—`DT10`，实现里 `DT7`/`DT8` 不存在（已修复）
`SKILL.md` 与 `plan.md` 声称有 `DT7`（轨迹不得作为证据）与 `DT8`（防重复派遣），实际 0 处实现。
（`evidence[]` 侧的同类约束此前由 `state_check` 的 V5 间接拦住，属于「另有规则」，不是 DT7。）
修复：真正实现 `DT7`（拒绝把轨迹/策略存储写进 `evidence_refs`）与 `DT8`（同 `state_version`
下同一行动已被派遣过则拒绝改名重放）。

### BUG-4 LOW — 日志中间插入空行会被误判为篡改（已修复）
`load_chained` 用 `enumerate` 的行号（含空行）比对 `seq` → 报 `DT0`。
修复：改用「已解析记录数 + 1」。

### BUG-5 LOW — `append_record(allow_replay=...)` 是死参数（已修复）
`if not allow_replay: pass`，参数完全无效且误导。已删除。

---

## B. 反事实回放（`research_replay.py`）

### BUG-6 HIGH — 离线 runner 允许策略「越层」（已修复）
`_apply_policy_candidate` 的层级比较写成 `if current_tier is not None`；当 runner 尚未产生
`chosen_intervention` 时该检查被跳过，于是 **低 EIG/高成本动作可以压过高 EIG/低成本动作**，
违反 spec「不得越层」。修复：无当前选择时以**最优合法层**为基准。

### BUG-7 MEDIUM — 对合规候选误报「绕过 guard」（已修复）
只要 arm 缺少某 guard，就无条件设 `policy_gate_bypassed` / `policy_scope_bypassed` /
`policy_support_bypassed`，**即使候选本身是已晋升、有作用域、有独立评价的**，也会被
`_behaviour_present("apply_unpromoted_policy")` 判为违规。修复：只在对应检查**确实失败**时置位，
并补上此前缺失的 `apply_untracked_policy`。

### BUG-8 MEDIUM — `coverage_report` 覆盖率指标口径错误（已修复）
`evaluable_fraction = 不同动作 id 数 / 轨迹数`。三条都已观测、且恰好选择同一动作的轨迹 → **1/3**。
修复：改为「有真实 outcome 的轨迹数 / 轨迹总数」。

---

## C. 策略演化（`policy_evolution.py`）

### BUG-9 HIGH — 回滚把 REJECTED 策略重新变成 active（已修复）
回滚只检查目标历史里是否出现过 VALIDATED/ACTIVE，于是**曾被 VALIDATED 后又 REJECTED** 的策略
可以被恢复，`active_policy_id` 指向它。复现：`rollback(P-B, to=P-A)` → `ROLLED_BACK`，
`P-A` 状态 `REJECTED`，但 active = `P-A`。这直接违反「防止同一失败策略重复晋升」。
修复：目标当前状态必须是 `SUPERSEDED`/`ACTIVE`；REJECTED/ROLLED_BACK 为终态；禁止自回滚。

### BUG-10 HIGH — 回滚后目标仍标为 SUPERSEDED，策略状态机自相矛盾（已修复）
回滚只写「指针」，不恢复目标的生命周期状态；`active_policy()` 又只看指针 → 返回一个
`SUPERSEDED` 策略，且对它做任何转移都被 `PE10` 拒绝（**回滚是死路**）。
修复：`SUPERSEDED → ACTIVE` 成为合法「恢复」转移，回滚显式写入该转移；`active_policy()`
同时要求指针与状态都是 ACTIVE。

### BUG-11 MEDIUM — `promote_to_active` 自带证据（已修复）
它硬编码 `independent/leakage_checked/reproducible/sample_adequate/distinguishable=True` 与
`degraded_dimensions=[]`，完全无视已记录的 replay 结论。
修复：新增 `recorded_evaluation()`（跨转移合并证据），晋升只读取记录值，缺失即 fail-closed。

### BUG-12 MEDIUM — 7 种「授权策略面」中有 3 种根本没有消费者（已修复）
实测：`exploration_operator_preference` ✅、`same_tier_preference` ✅、`applicability` ✅；
`same_tier_order` 只认成员不认顺序；`menu_choice` 完全无效（affinity 从不读 menu）；
`probe_order` / `local_resource_allocation` 连 advice 都不产生。
而且 `candidate_errors` 不要求「至少一个可消费变更」，所以**无消费者的策略也能晋升为 ACTIVE**。
修复：`same_tier_order`/`probe_order` 保留请求顺序（`prefer_rank`）；`menu_choice` 映射到
其声明的 operator/island/shift；新增 `CONSUMABLE_CHANGE_KINDS`，只有建议性变更的策略被 `PE2` 拒绝。

### BUG-13 MEDIUM — 可执行内容正则三处误判（已修复）
- `r"../"` **未转义**，被当成「任意两字符 + `/`」：`"ratio 3/4"`、`"appendix / section 3"`
  都被判为「路径穿越」。
- `r";\s*\w"` 把正常英文分号句判为「shell 语句分隔」。
- `r"\beval\s*\("` 命中 `"eval(uation)"`。
修复：转义为 `\.\./`；分号规则要求后接真实命令名；其余保留（宁可误拦）。

### BUG-14 MEDIUM — `cross_project_transfer_allowed` 可能整条消失（见 F-5，待修）
`source_route`/`source_project` 从不由 `propose()` 写入，且 `current_route` 为空时直接返回
`NOT_REQUIRED`，`preset_router` 随即应用该策略。见 F 节。

---

## D. 路由与循环集成（`preset_router.py`）

### BUG-15 HIGH — 被篡改的策略日志仍被消费（已修复）
`scoped_policy_state` 以 `tolerant=True` 读取并**丢弃**全部链诊断，然后照常加载 ACTIVE 策略。
复现：改写 `candidates.jsonl` 首行改变 `prefer_action` → 路由器照用被篡改的策略。
修复：有诊断即返回 `tampered`，`strategy_dispatch` 拒绝消费，`research-loop` 报
`HOLD / policy_store_tampered`。

### BUG-16 HIGH — 损坏的轨迹存储导致未捕获异常（已修复）
ACTIVE 策略 + `apply=True` + 损坏的 `decision-trajectory.jsonl` →
`TrajectoryError` **穿透 `run_preset` 与 CLI**（无 try/except），用户看到 traceback 而非 HOLD。
修复：轨迹/telemetry 写入全部包在 `try/except`，失败转 `HOLD` + `hold_reason`
（`decision_trajectory_rejected` / `decision_trajectory_unreadable` / `scheduler_telemetry_unwritable`）。

### BUG-17 MEDIUM — 虚假 Policy Delta（已修复）
当上一轮记录的策略决策被「消费」但循环落在非调度分支（`dispatched_action` 为 None）时，
输出 `policy_delta = {"status":"consumed","level":"L2"}` —— **什么都没派遣却报告 L2 策略增量**。
修复：只有「策略确实改变了动作 **且** 该动作被派遣」才产生 policy_delta，否则 `none`。

---

## E. 源码冻结（`source_freeze.py`）— 由独立对抗审计发现

| ID | 严重度 | 问题 | 状态 |
|---|---|---|---|
| E-1 | HIGH | `guard_write(allowed_roots=())`（默认形态）跳过范围检查：`guard_write("/etc/passwd")` → ALLOWED，CLI 退出 0。写入白名单声明为假 | 修复中 |
| E-2 | HIGH | 硬链接绕过：guard 只比 realpath 字符串，`os.link(SKILL.md, route/hard)` 后写 `route/hard` 即改写 `SKILL.md` | 修复中 |
| E-3 | HIGH | 完整性审计链可伪造/重放/截断且从不校验；调用方可覆盖 `seq/previous`；日志本身不受保护 | 修复中 |
| E-4 | HIGH | 相对 `allowed_roots` 相对 skill 根解析：`allowed_roots=["."]` 等于开放整个 Skill 根 | 修复中 |
| E-5 | MEDIUM | `verify()` 只比 sha256，忽略 manifest 的 root/symlink/realpath：树 B 可对树 A 的 manifest 报 PASS | 修复中 |
| E-6 | MEDIUM | 畸形 manifest 抛 `AttributeError` 而非 VIOLATION | 修复中 |
| E-7 | MEDIUM | `hold_on_violation(route, None)` 返回 `PASS`（fail-open） | 修复中 |
| E-8 | MEDIUM | `EXCLUDED_DIRS` 任意深度匹配：`scripts/.dev/evil.py`、`*/__pycache__/*` 不可见 | 修复中 |
| E-9 | MEDIUM | 受保护目录下的**符号链接目录**既不进 manifest 也不进 added/removed/escapes | 未修（记录） |
| E-10 | MEDIUM | `guard_errors` 多处漏判，且**是死代码**（无生产调用者） | 部分（移除装饰性常量） |
| E-11..E-16 | LOW | `allow_canonical` 未绑定 route；`route_dir=None` 不写事件；审计写入不受 guard；`guard_write(skill_root)` 放行；`ALLOWED_WRITE_SCOPES` 未使用；改回原样检测不到 | 部分 |

---

## F. 策略迁移（`policy_transfer.py`）— 由独立对抗审计发现

所有条目都是**契约违反（应 BLOCK 却 ALLOW）**。

| ID | 严重度 | 问题 | 状态 |
|---|---|---|---|
| F-1 | HIGH | `negated_mechanisms` 只看 `claims[]`/`failures[].negative_knowledge`，**看不到 `hypotheses[].status=killed`**，于是 PT8 对最常见的否证形态失效 | 修复中 |
| F-2 | HIGH | PT8 匹配的是 `finding` 而不是被否证的 `ruled_out` 命题，真正被否证的主张反而通过 | 修复中 |
| F-3 | HIGH | PT10 的反例覆盖对任何**畸形条件**直接 `continue`，加一条 `op:"no_such_op"` 即可让覆盖检查消失 | 修复中 |
| F-4 | HIGH | 非列表的 `applicable_conditions`/`required_tools` 被静默忽略（`None`/字符串/数字 → ALLOW） | 修复中 |
| F-5 | HIGH | `cross_project_transfer_allowed` 在 `current_route` 为空或无 source 声明时返回 `NOT_REQUIRED`，迁移门整体消失 | 修复中 |
| F-6 | HIGH | `expired_trajectories` 把缺失/非整数 `state_version` 当 0，删掉版本号即可关闭全部过期判定 | 修复中 |
| F-7 | MEDIUM | 任意 JSONL 都被接受为 decision_experience，且链诊断被丢弃 | 修复中 |
| F-8 | MEDIUM | 结构匹配可自证：不给 `source_state` 时策略自报签名得 1.0 | 修复中 |
| F-9 | MEDIUM | `compression_report` 在重复 id 且顺序不同时会丢掉不可丢弃项（模糊测试 458 次违规） | 修复中 |
| F-10 | MEDIUM | ReDoS：策略自带 `op:"regex"`，`(a+)+$` 在 28 个 a 上耗 9.3 s，n=40 超 25 s | 修复中 |
| F-11 | MEDIUM | CLI `compress` 在 REFUSED 时仍退出 0 | 修复中 |
| F-12 | MEDIUM | PT9 的「跨项目证据」可自述（`evidence_projects:["A","B"]`，0 条记录即 ALLOW） | 未修（记录） |
| F-13..F-16 | LOW | PT10 忽略 `word+digit` 反例；PT1 白名单漏掉内嵌科学数组；未捕获异常而非 INVALID；未知种类理由被丢弃 | 部分 |

---

## G. 复核方法学说明（诚实边界）

- 每条 CONFIRMED 都有可复现命令与观察输出；`/tmp/rsi-probe/probe1..9.py` 保留全部复现。
- E/F 两节的原始报告含逐条 file:line、复现命令与「已检查但**不是** bug」的负结果清单，
  见 `.dev/audit/E-source-freeze-bugs.md` 与 `.dev/audit/F-policy-transfer-bugs.md`。
- 本轮**没有**发现 Harness / 基础模型 / Agent 调度层面的问题：这些区域未改动。
- 仍未验证的假设：并发修复只在同机多线程下验证；未做跨主机/网络文件系统验证。
  `source_freeze` 的硬链接检测在同内容场景下的严格性、以及 case-insensitive 文件系统行为，
  仍未在真实平台上验证（记录为残余风险）。

---

## H. 修复后的复核（第二轮）

### BUG-18 HIGH（本轮修复过程中**新引入并已修掉**）
E-8 的修法把 `__pycache__` 从「仅顶层排除」改成「受保护树内部也登记」，于是
**解释器生成的 `.pyc` 进入冻结清单**。复现：删除 `scripts/__pycache__/*.pyc` 后运行
`run_preset(..., apply=True)` → `source_integrity: VIOLATION` → `HOLD`
（`added: scripts/__pycache__/decision_trajectory.cpython-314.pyc` …）。
后果是「任何新部署/改源码后的第一次运行都会 HOLD」——一个部署级误报，比原缺陷更严重。

修复：`EXCLUDED_DIRS_ANYWHERE = (".git", "__pycache__")`（任意深度排除解释器产物），
`.dev` / `examples` 仍只在顶层排除，因此「往 `scripts/` 里塞一个 `.dev/evil.py`」依然可见。
验证：冷缓存下 `source_integrity: PASS`，清单回到 135 项且不含任何 `__pycache__`。

### 修复后的逐条状态

| ID | 状态 | 验证方式 |
|---|---|---|
| BUG-1 并发 TOCTOU | **FIXED** | 8 线程 → 8 行、seq 1..8、链完整 |
| BUG-2 重复派遣身份 | **FIXED** | 相隔 5 分钟的同一决策 → `DUPLICATE`；改写 → `DT2` |
| BUG-3 DT7/DT8 缺失 | **FIXED** | 引用轨迹作证据 → `DT7`；改名重复派遣 → `DT8` |
| BUG-4 空行误判 | **FIXED** | 中间插空行 → 正常读取 |
| BUG-5 死参数 | **FIXED** | 参数已删除 |
| BUG-6 离线越层 | **FIXED** | 低层偏好不再压过高 EIG/低成本动作 |
| BUG-7 误报绕过 | **FIXED** | 合规 ACTIVE 候选不再被指控；`apply_unpromoted_policy` 为 False |
| BUG-8 覆盖率口径 | **FIXED** | 3 条同动作已观测轨迹 → 1.0 |
| BUG-9 回滚 REJECTED | **FIXED** | `PE13` 拒绝 |
| BUG-10 SUPERSEDED 死路 | **FIXED** | 回滚后目标状态 = ACTIVE，可再次被取代 |
| BUG-11 自带证据晋升 | **FIXED** | 只读 `recorded_evaluation()`；缺失即 fail-closed |
| BUG-12 无消费者策略面 | **FIXED** | 顺序被尊重；menu→operator；仅建议性变更 → `PE2` |
| BUG-13 正则误判 | **FIXED** | 普通英文/比例文本通过；真实 shell 仍被拒 |
| BUG-14 迁移门消失 | **FIXED** | `propose()` 打上来源路由；缺来源 + 已知路由 → BLOCK |
| BUG-15 篡改策略仍被消费 | **FIXED** | `HOLD / policy_store_tampered` |
| BUG-16 损坏轨迹崩溃 | **FIXED** | `HOLD`（不再 traceback） |
| BUG-17 虚假 Policy Delta | **FIXED** | 未派遣时 `policy_delta = none` |
| E-1 | **FIXED** | `/etc/passwd` → `OUTSIDE_ALLOWED_SCOPE` |
| E-2 | **FIXED** | 硬链接 → `HARD_LINK_TO_PROTECTED` |
| E-3 | **FIXED** | 截断/伪造 → `SourceFreezeError`；head sidecar；日志受保护 |
| E-4 | **FIXED** | `allowed_roots=["."]` 不再开放 Skill 根 |
| E-6/E-7/E-8/E-14/E-15 | **FIXED** | 见 `test_source_freeze.py`（31 项） |
| E-5 / E-9 / E-10 / E-11 / E-12 / E-13 / E-16 | **未修（已记录）** | `verify()` 只比内容；符号链接目录不入清单；`guard_errors` 死代码；`allow_canonical` 未绑 route；`route_dir=None` 不写事件；审计写入未受 guard；enter/exit 之间「改了又改回」检测不到 |
| F-1..F-11, F-15 | **FIXED** | 见 `test_policy_transfer.py`（81 项） |
| F-12 PT9 自述证据 | **未修（已记录）** | 仍需外部可信来源 |
| F-13/F-14/F-16 | **部分** | 低危，未逐一处理 |

### 修复后的验证

| 检查 | 结果 |
|---|---|
| 全量单元测试 | **1661 tests OK (skipped=3)**（复核前 1590） |
| `release_check.py` | **PASS（18 步）** |
| 5 个模块 `--selftest` | 全 OK |
| 冷 `__pycache__` 端到端 | `source_integrity: PASS` |
| 消融（probe 集）| `rsi_full` vs `full_cie` 可区分；逐 guard 探针**一一对应**（修复误报后不再溢出） |

### 仍未验证 / 残余风险

1. 并发修复只在同机多线程下验证，未跨主机或网络文件系统验证。
2. `source_freeze` 的硬链接检测只覆盖「同 inode」；同内容不同 inode 的替换仍靠内容摘要。
3. E-16（enter/exit 之间改了又改回）在设计上检测不到，已在 `RESIDUAL RISK` 中声明。
4. F-12 的跨项目证据仍可自述，需要外部可信来源才能收紧。
5. 本轮所有结论都基于合成 fixture 与单元测试，**不构成 L3 科研能力证据**。
