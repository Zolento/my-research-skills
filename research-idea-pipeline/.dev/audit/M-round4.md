# 第四轮整体检查（branch-local）

> 基线：`751454d`（第三轮修复后）。本轮由主开发者直接完成——两个派出的独立审计代理
> 长时间未产出报告，**未采用其结论**（见文末「过程问题」）。所有结论都来自本仓库内可复现的探针。

## 本轮发现并修复

### F4-1 HIGH — 源码冻结只在 `apply=True` 时运行（契约与实现不符）
Skill-RSI 政策 §9 要求「科研运行开始时记录实际加载的 Skill 版本与源码摘要」，但
`run_preset` 只在 `apply=True` 时进入 `SourceFreeze`，于是**只读诊断（research-audit /
research-review / loop-health-check 等）全程没有任何源码完整性核验**。
复现：`apply=False` 时 `payload["source_integrity"]` 为 `{"status": "SKIPPED"}`。
修复：**每次 Preset 执行都做前后核验**（含只读运行）；套件耗时 10s → 11s。
`source_integrity` 现在总是出现且为 `PASS`，只读运行仍不写任何文件。

### F4-2 MEDIUM — 审计事件是「未声明的写入」
`apply=True` 时每个 Preset 都会写 `source-integrity.jsonl`，但 `payload["writes"]` 不列它。
复现：`research-audit` + `apply=True` → 磁盘多出 `source-integrity.jsonl`，而 `writes == []`。
修复：审计事件**只在本次执行允许写入时记录**（`apply` 且处理器声明了写入，或发生违规），
并在 `writes` 中声明。只读 / 审计类 Preset 即使 `apply=True` 也**完全不写**。
（第一次尝试无条件追加会把已出货的 `test_a_plain_audit_never_writes...` 判红——正是该契约的内容。）

### F4-3 MEDIUM — 处理器异常穿透路由与 CLI（无诊断）
`CognitionError` / `OSError` 从处理器抛出后直接穿透 `run_preset` 与 CLI，调用方看到
traceback 而不是状态。复现：把处理器替换为 `raise OSError("disk full")` → 未捕获。
修复：`(CognitionError, OSError)` → `HOLD` + 退出码 4 + `hold_reason="handler_error"` +
新规则 `PR10`；**不重试、不放宽门禁、不把工程故障写成科学否证**。
编程错误与不可恢复错误（`ValueError` / `MemoryError`）**仍然抛出**，这是刻意的边界并已文档化。
`PR` 规则范围相应扩为 `PR1`—`PR10`（authoritative 文档 + 各 Preset 的范围句）。

### F4-4 HIGH（过程）— 并发复核代理污染了出货 fixture
复核期间发现 `examples/structural-equivalence/paradigm-candidate.json` 被改成
`"collapse_result": "collapses"`（非法枚举），直接判红 3 个出货测试与发布闸门。
已用 `git checkout` 还原，当前工作树相对 HEAD 无该文件改动。
教训已记入本轮：复核代理必须在 `/tmp` 的 `git archive` 副本上做破坏性实验。

## 已验证**不需要**改动的（本轮的负结果）

| 检查 | 观察 |
|---|---|
| 每个 Preset `apply=False` 的写入 | 全部 16 个：**零写入** |
| 只读 / 审计 Preset `apply=True` | `writes == []`，无审计事件，不写盘 |
| 多路由隔离 | 路由 A 的 ACTIVE 策略只改变 A 的派遣（R2 + `policy_delta=applied`）；路由 B 完全不受影响（无 `policy/`、无轨迹、R1、`policy_delta=none`） |
| 哈希种子确定性 | 4 个 `PYTHONHASHSEED` 下 1691 tests 全绿；策略存储与重建快照在 seed 0/7/4242 及重复构建下**逐字节一致** |
| 候选自称 ACTIVE 但无转移记录 | 不被当作生效策略 |
| 最后一次转移为 HOLD | 不被当作生效策略 |
| 同一存储两条 ACTIVE | 后写入者生效（`transition` 正常路径会自动 SUPERSEDED 前一条） |
| `level_report(l3_evidence=[])` | `NOT_VERIFIED`（空列表不构成 L3 证据） |
| `prefer_rank` 重复项 / 未知动作 | 顺序确定；未知动作被忽略；`recommend_strategy` 从不设置 `prefer_actions`，既有排序不变 |
| `run_suite(arms=['baseline'])` | 正常，`sufficient_sample=False`（样本不足如实报告） |
| 泄漏审计对二进制文件 | 可检出（`RP7`） |
| 完整性违规时的状态映射 | `HOLD` / 退出码 4 / `SRC1` 诊断；只读 Preset 也会记录该安全事件并在 `writes` 中声明 |

## 仍未解决（如实记录）

1. **短 token 泄漏盲区**：`RP2` 子串守卫只检查 ≥12 字符的隐藏串。若隐藏答案只由短 id
   （如 `X1`）表达，则不会被判为泄漏。这是 `forbidden_strings()` 的既有设计取舍
   （短 token 太常见），不是本轮引入；已在报告中明确为覆盖限制。
2. `verify()` 的内容+身份核验已补齐（E-5/E-9），但仍不覆盖「enter/exit 之间改了又改回」（E-16）。
3. PT9 跨项目证据仍可自述（F-12）。
4. 并发修复只在同机多线程验证，未跨主机 / 网络文件系统。
5. **L3 仍未验证** —— 全部结论基于合成 fixture 与单元测试。

## 过程问题（必须记录）

本轮派出的两个独立对抗审计代理（`preset_router` 定向、消融/闸门/策略记忆定向）在
约 90 分钟内**没有产出任何报告**，其中一个在早期直接修改了出货 fixture（F4-4）。
因此本轮结论**全部由主开发者自行复现**，其分工范围内的关键项（只读保证、逐 Preset 写入、
路由隔离、哈希确定性、策略存储异常状态、异常穿透、消融诚实性、L3 声明）已逐条覆盖并记录负结果。
未采用任何未交付代理的结论。

## 验证（本轮结束时）

| 检查 | 结果 |
|---|---|
| 全量单元测试 | **1691 tests OK (skipped=3)**（第三轮 1685） |
| `release_check.py` | **PASS（18 步）** |
| 5 个模块 `--selftest` | 全 OK |
| 冷 `__pycache__` 端到端 | `source_integrity: PASS` |
| 4 个哈希种子 | 全部 1691 tests OK |
