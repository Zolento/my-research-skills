# Operational Autonomy Policy（内部运维与证据门禁）

> **定位：** 本文件规定 Agent 在**已授权范围内**如何自主完成记录维护，以及哪些操作
> **永远不能**因为「自主」而绕过证据门禁。它不是新的 R 阶段，不是第二套 Research State，
> 也不是新的授权系统。
>
> **一句话：** 例行维护自动做完；科学更新过既有门禁；特权动作仍由用户授权。
>
> 相关文件：[scientific-communication-policy.md](scientific-communication-policy.md)、
> [research-state-policy.md](research-state-policy.md)、
> [evidence-outcome-contract.md](evidence-outcome-contract.md)、
> [scheduler-policy.md](scheduler-policy.md)、
> [loop-assurance-review.md](loop-assurance-review.md)、
> [invocation-prompts.md](invocation-prompts.md)。

## 0. 三类操作

| 类别 | 定义 | 默认行为 | 授权 |
|---|---|---|---|
| **A. Routine Maintenance** | 已授权、确定性、幂等、可验证、**不改变科学事实**的状态投影与记录维护 | **自动执行，不询问用户** | 入口已有的执行授权 |
| **B. Evidence-Gated Scientific Updates** | 改变 experiment outcome、claim、hypothesis、assurance、failure、repair 或 research decision | 过 R9.O / R10 / R11 / R7 与相关校验器；全部通过才可自动提交，否则 `HOLD` | 入口已有执行授权 + 全部门禁 |
| **C. Privileged Research Actions** | 改变主锚点、突破预算、修改冻结协议、执行未授权的大规模训练、绕过证据门禁 | 保持既有授权边界；**本次改造不新增任何权限** | 仅用户显式授权 |

**分类的目的不是放宽权限，而是把「不需要用户决策的事」从用户面前移走。**

## 1. A 类：例行维护

同时满足以下条件才是 A 类：

1. **已授权**：当前入口的 `execution_scope` 允许写，且不是只读请求；
2. **确定性**：同一输入产生同一输出，不依赖随机数、时钟或模型判断；
3. **幂等**：重复执行不产生额外事实、不重复追加记录、不推高 `state_version`；
4. **可验证**：有校验器或内容比较可以证明结果正确；
5. **不改变科学事实**：不改 claim / hypothesis / evidence / failure / assurance 的
   科学内容与状态。

典型 A 类操作：

- 重建认知投影 `cognition/index.json` 与 `cognition/context-brief.md`；
- 重渲染路线 `STATUS.md`；
- 按既有路径维护索引、归档日志、关联监控记录；
- 非科学事实的状态同步（例如把已生成产物登记到人类视图）；
- 调度与监控 telemetry 的**一致性检查**（不是伪造刷新）；
- 运行前后源码完整性审计事件；
- 清理临时产物与可重建缓存。

**规则：**

- **不向用户询问是否执行 A 类。** 直接做完，只在失败或影响判断时报告。
- **A 类不得写 `research-state.json`。** 投影刷新不得改变 canonical state，也不得
  推高 `state_version`。
- **不得把「刷新版本号」当成同步。** 过期 scheduler 必须按当前 state 重新评估；
  把旧 `state_version` 直接改成新值属于伪造 telemetry。
- **同一动作重复执行必须安全。** 内容未变时不得重写、不得追加重复日志。
- **维护失败必须保留真实阻塞信息。** 例如 `projection_refresh_failed`、
  `status_render_failed`、`canonical_state_invalid`。**不得宣称已同步。**
- **维护失败不得回滚或覆盖科学事实。** 只报告失败并保留原状态。

## 2. B 类：证据门禁的科学更新

B 类包括：

- 提交 experiment outcome（`done` / `failed` + `outcome_analysis` 事务）；
- 改变 `claims[].status`、`hypotheses[].status`、`scope`、`known_flaws`；
- 写入 `evidence[]`、`failures[]`、`repairs[]`、`uncertainties[]` 的科学内容；
- 写入 post-update Assurance；
- 改变 research decision（continue / pivot / archive / submit）；
- 任何会改变主锚点成功判据的判断。

**自动提交的充分条件（缺一即 `HOLD`）：**

1. 走 canonical 的合法写入路径，不直接编辑 JSON 绕过事务；
2. 已有执行授权（`continue-research` 的 execute 或等价的显式授权）；
3. packet、analysis、audit 三件套齐备，且来源、摘要与当前 state 绑定；
4. `evidence_outcome.validate()` 与 `state_check.py` 通过；
5. 独立审计没有 `FAIL` / `UNKNOWN`；
6. `base_state_digest` 未过期，运行产物未被替换；
7. 不触发 stop rule、预算、公平对照或 pre-registration 冲突。

**失败时的行为：**

- `HOLD`，并给出结构化原因：`outcome_transaction_missing`、
  `outcome_transaction_stale`、`outcome_audit_unknown`、`outcome_receipt_blocked`、
  `state_gate_failed`、`stale_scheduler` 等；
- 保留原始来源与未完成产物；
- **不得从日志自动推断 outcome**，不得为了过门禁把 `done` 写回去再补分析；
- **不得因为自动提交失败就改用户授权或放宽门禁。**

**Prepared transaction bundle（唯一可自动提交的形态）：** 三件套放在
`<project>/results/<R>/<XID>/outcome/`，文件名为 `<XID>-packet.json`、
`<XID>-analysis.json`、`<XID>-audit.json`；也接受显式 `--outcome-root` 指向的目录。
只有三件套齐备、`validate()` 通过、摘要仍绑定当前 state 时才自动提交。
**缺任何一件、审计 UNKNOWN 或 base_state_digest 过期 → `HOLD`，不得从日志补写。**

**自动提交不等于科学支持。** 提交只表示事务合法，不表示 claim 被支持，也不授权下一轮
GPU 执行。

## 3. C 类：特权科研动作

以下动作**始终**需要用户显式授权，且不受本政策影响：

- 改变项目主锚点或路线锚点（见 SKILL §0.2）；
- 突破已冻结预算、GPU 配额或运行时限；
- 修改已冻结的实验协议、判据或 pre-registration；
- 执行未授权的大规模训练、外部集群任务或会显著消耗资源的动作；
- 绕过或弱化 R7 / R8 / R9.O / R10 / R11 / R13 的证据门禁；
- 发布、推送、合并、删除实验结果或改写历史结论。

Agent 可以**提请**、给出证据、给出选项与代价，但**不能自行执行**。
**「自主运维」不产生任何新的科研权限。**

## 4. 六条硬不变量

1. **canonical 唯一。** 只通过既有 R 阶段、事务与校验器写 `research-state.json`；
   不建第二套 canonical state。
2. **进程终止不是科学完成。** `SIGTERM`、`SIGINT`、进程消失、队列退出都只说明执行
   状态变化；没有合法 outcome 事务就不能写 `done`，也不能写科学负结论。
3. **过期 telemetry 不是当前事实。** `scheduler.state_version` 与 canonical 不一致时，
   其 `next_actions`、监控记录与 EIG 记录不得作为当前实验决策依据。
4. **未验证日志不是 outcome。** 日志、截图、聊天记录和临时文件只能作为 packet 的来源，
   不能直接推出 claim / hypothesis 状态。
5. **真实阻塞必须保留。** 维护失败、证据不足、审计 UNKNOWN、预算不足与授权缺失都要
   原样报告；不得用「已同步」「已完成」掩盖。
6. **冲突时 HOLD。** 证据冲突、版本冲突、来源被替换或授权边界不清时停止，不覆盖、
   不伪造、不静默选择一方。

## 5. 有限恢复，不无限循环

- 同一维护动作失败后，最多按既有冷却/上限重试；超过上限交人裁决。
- 不得用重复刷新、重复诊断、重复改写报告制造进展。
- 恢复失败时保留 `hold_reason` 与下一次可尝试条件。
- 不得为了「让 loop 继续」而降低门禁、跳过审计或伪造状态。

## 6. 汇报前的 operational reconciliation

每轮面向用户汇报前，按以下顺序内部完成：

1. **读** canonical state、scheduler、认知投影、result artifacts 与未完成事务；
2. **判新鲜度**：scheduler 是否对应当前 `state_version`，监控记录是否过期；
3. **做 A**：内容有变化才重建投影 / 重渲染 STATUS；无变化则不写；
4. **查 B**：终态实验是否缺 outcome 事务；三件套是否齐备且可验证；
5. **过门禁**：`state_check`、`evidence_outcome.validate`、Assurance；
6. **再汇报**：只有完成上述步骤后，才按
   [scientific-communication-policy.md](scientific-communication-policy.md) 输出。

**任何一步失败：** 保留真实失败原因，汇报「阻塞」而不是「完成」。
**不得因为隐藏维护细节而跳过实际维护。**
**也不得因为追求简洁而隐藏关键负结果、重大不确定性或门禁阻塞。**

## 7. 入口与授权边界

| 入口 | 默认授权 | 允许的自主行为 | 不允许 |
|---|---|---|---|
| `continue-research`（执行） | execute | A 自动；B 过门禁后提交；C 提请 | 未授权大规模训练、改锚点、跳过门禁 |
| `continue-research`（只分析/建议） | read-only | 只读检查、指出需要维护的项 | 写 state、跑实验、自动提交 outcome |
| `continue-research`（明确审计） | audit / read-only | 详细读取、完整报告 | 以审计为名修改科学事实 |
| `explore` | discovery | 候选与文献写入 | 执行实验、改 claim 状态 |
| `audit` | audit | 攻击与提案 | 扩展发现、自动写 assurance |
| `start-project` | bootstrap | 只观察、建最小骨架 | 推进 R3—R14 |

**用户只请求分析时，不得擅自执行研究实验。**
**用户请求继续科研时，不得因例行维护反复请求批准。**
**遇到授权缺失、证据冲突或预算不足，保持原有 HOLD 或授权行为，不自行放宽。**

## 8. 自检

- [ ] 本轮 A 类维护已实际执行，而不是只在报告里声称。
- [ ] A 类没有写 canonical state，没有推高 `state_version`。
- [ ] B 类更新全部走既有事务与校验器，失败时 `HOLD` 且原因结构化。
- [ ] 没有把进程终止、过期 telemetry 或未验证日志当作科学事实。
- [ ] 维护重复执行安全；没有无限恢复循环。
- [ ] 冲突时保留双方来源并 `HOLD`，没有覆盖科学事实。
- [ ] 没有因本次改造获得任何新的特权科研权限。
- [ ] 面向用户的汇报已按科学优先政策输出。
