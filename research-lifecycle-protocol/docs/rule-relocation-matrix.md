# Rule Relocation Matrix（v2.2.0）

本文件记录 `SKILL.md` 精简过程中**每一条**内容的去向。它存在的理由是一条硬要求：

> 任何没有确定新权威位置的硬约束，**不得删除**。

下表按原 `SKILL.md` 的小节逐条给出：原位置、新权威位置、加载触发、是否硬规则、
对应机器校验、对应回归测试。字节数是 v2.1.1 的实测值。

---

## 0. 判定方法

先做了一次**逐句**审计（不是按主题猜测）。三个判定值：

| 判定 | 处理 |
|---|---|
| `DUPLICATE` | 目标权威已有等价规范 → 不搬运。差异部分（阈值、顺序、禁止项）随下一类处理 |
| `UNIQUE` | 只在 `SKILL.md` 存在 → **必须**迁入指定权威 |
| `STALE` | 与既有权威冲突 → **不搬运**，并在本文件登记（矛盾随重复一起消失） |

搬运是机械可核对的：脚本逐行比对目标文档，只有「目标里找不到该行」时才追加。
因此下表 `已存在 / 迁入` 两列是可复算的，不是估计。

---

## 1. 逐节去向

| 原小节 | 字节 | 新权威位置 | 加载触发 | 硬规则 | 机器校验 | 回归测试 |
|---|---|---|---|---|---|---|
| 引言（身份与职责分离） | 1,733 | **L0 保留** | 每次 | 是 | `release_check` L0 标记 | `test_context_architecture.TestL0Contract` |
| §0 入口与四层解析 | 7,024 | **L0 §0.3 保留**（压缩为表格）+ [invocation-prompts](../references/reference-index.md) | 每次 | 是 | `preset_router check`、`router-fixtures` | `test_preset_router`、`test_state_check.TestSemanticEntryFirst` |
| §0「各阶段的分工」 | 4,203 | [references/scheduler-policy.md](../references/scheduler-policy.md) §「Discovery Loop 与 Assurance Loop 的分工」 | 需要判断该跑哪侧时 | 否 | — | 本文件 §4 |
| §0.1 锚定点 | 7,161 | [references/anchor-policy.md](../references/anchor-policy.md) §1 | 开工前；换方向 / 重新定位 / `anchor_role` 有争议 | **是**（门槛部分留在 L0） | L0 标记 `只有用户能授权` | `TestL0Contract` |
| §0.2 锚点变更单 | 2,357 | [references/anchor-policy.md](../references/anchor-policy.md) §2 | 要改锚点时 | **是** | 同上 | 同上 |
| §0.3 Bootstrap 编排 | 2,370 | [references/invocation-prompts.md](../references/invocation-prompts.md) | `start-project` | 是 | `context_planner` 的 `entry_context` | `test_context_architecture` |
| §0.31 Cold Handoff vs Resume | 1,219 | [references/identity-and-compatibility.md](../references/identity-and-compatibility.md) | 接管 / 恢复判定 | 是 | `legacy_handoff.resume_decision` | `test_legacy_handoff` |
| §0.4 I2M | 7,729 | [references/insight-to-method-policy.md](../references/insight-to-method-policy.md) §1 | 提方法候选 / 判方法进展 | 部分是 | `insight_to_method.py`（I2M60—64） | `test_insight_to_method` |
| §0.5 沟通与运维自主 | 1,668 | [references/operational-autonomy-policy.md](../references/operational-autonomy-policy.md) | 每次汇报 | 是 | `operational_reconcile.py` | `test_scientific_communication` |
| §1.1 文献检索 | 6,425 | [references/literature-policy.md](../references/literature-policy.md)（67 行迁入 / 1 行已存在 / **1 行 STALE 未搬**） | 文献任务；L0 保留顺序约束 | 是 | `literature_search.py` | `test_literature_search` |
| §1.2 顶会标准锚定 | 1,988 | [references/venue-standards.md](../references/venue-standards.md)（21 行迁入） | 仅 R12 / R13 | 是（scoping） | L0 §6 的 scoping 断言 | `test_state_check`（venue scoping） |
| §1.3 输出规范 | 2,126 | [references/writing-policy.md](../references/writing-policy.md)（25 行迁入） | 落盘前 | 是 | `ste_lint_zh.py` | `test_ste_lint_zh` |
| §1.4 项目组织与落盘 | 7,726 | [references/project-layout.md](../references/project-layout.md)（82 行迁入 / 9 行已存在） | 要写文件时 | 是 | `render_status.py`、`rlp_paths.py` | `test_storage_spec`、`test_render_status` |
| §1.5 推进纪律（四步链） | 4,933 | [references/insight-to-method-policy.md](../references/insight-to-method-policy.md) §2 | 发现自己在做纯证明性工作 | 是 | — | 本文件 §4 |
| §1.6 修复门 | 2,296 | **L0 §1.6 保留**（原文约 90% 已在 phase-r7/r9-r11） | 每次 | **是** | `insight_to_method`、`state_check` | `TestL0Contract` |
| §1.7 认识论权限边界 | 1,614 | **L0 §1.7 保留**（30% 重复，属独有 framing） | 每次 | **是** | L0 标记 | `TestL0Contract` |
| §1.8 认知记忆 | 8,328 | [references/cognitive-memory-policy.md](../references/cognitive-memory-policy.md)（89 行迁入 / 3 行已存在） | 恢复 / 投影 | 是 | `cognition.py`（CM1—CM10） | `test_cognition` |
| §1.9 旧项目接管 | 3,056 | [references/legacy-handoff.md](../references/legacy-handoff.md)（39 行迁入） | 接管 | 是 | `legacy_handoff.py`（LH1—LH16） | `test_legacy_handoff` |
| §1.10 Preset 库与 Router | 4,418 | [references/preset-policy.md](../references/preset-policy.md)（45 行迁入） | 选择预设 | 是 | `preset_router check` | `test_preset_router` |
| §1.11 Skill-RSI | 2,207 | [references/skill-rsi-policy.md](../references/skill-rsi-policy.md)（22 行迁入 / 2 行已存在） | 策略演化 | 是 | `policy_evolution.py`（PE1—PE17） | `test_policy_evolution` |
| §2 共享资源索引 | 19,340 | [references/reference-index.md](../references/reference-index.md) | 查权威位置 | 否（目录） | L0 必须链接它 | `test_structural_equivalence.test_new_assets_are_registered_in_skill` |
| §3 子代理派遣总览 | 3,556 | [references/subagent-context.md](../references/subagent-context.md) | 派遣前 | 部分是 | `subagent_context.py check` | `test_context_architecture.TestSubagentContext` |
| §3.1.0 Mesh worktree 模式 | 547 | **L0 §3.1.0 保留**（根 `AGENTS.md` §23.1 绑定该锚点） | 派遣前 | **是** | L0 锚点断言 | `TestL0Contract.test_anchors_cited_elsewhere_still_exist` |
| §3.1 Team 优先询问 | 1,724 | [references/subagent-context.md](../references/subagent-context.md) §6.1 + L0 一句话 | 派遣前 | 是 | — | 本文件 §4 |
| §4 各 R 阶段速查 | 14,645 | **删除**（187 条中 181 条 DUPLICATE）；2 条 UNIQUE 入 [phase-r12](../references/phase-r12-narrative.md)；4 条 STALE 未搬 | — | — | `step_stage_index_parity`（阶段集合 + 读写列不得回流） | `test_state_check.TestReleaseCheckGate` |
| §5 衔接与状态回写 | 1,267 | **L0 §5 保留**（压缩） | 每阶段收尾 | **是** | `state_check.py --check` | `test_state_check` |
| §6 执行自检清单 | 10,680 | [references/execution-checklist.md](../references/execution-checklist.md) + **L0 §6 最小十条** | 交付前 | 是 | 十个 checklist 项 | `test_context_architecture.TestL0Contract` |
| §7 设计依据 | 11,513 | [references/design-rationale.md](../references/design-rationale.md) | 质疑设计时 | 否 | — | `test_state_check.test_skill_design_note_does_not_claim_r12_uses_the_reverse_score` |
| §8 规则变更自检 | 10,116 | [references/development-selfcheck.md](../references/development-selfcheck.md) | 改规则时 | 是（对维护者） | `release_check.py` | `test_structural_equivalence.test_new_gate_is_documented_in_skill_selfcheck` |

---

## 2. 必须留在 L0 的 13 条硬约束

删除其中任何一条都会让「精简」变成「丢规则」。`release_check.step_context_architecture`
逐个字符串校验，`test_context_architecture` 再校验一次。

| # | 硬约束 | L0 位置 | 标记串 |
|---|---|---|---|
| 1 | canonical Research State 是唯一科学事实源 | §1.1 | `唯一科学事实源` |
| 2 | 已有项目禁止重新 Bootstrap | §0.4 | `禁止重新 Bootstrap` |
| 3 | 用户授权不可由 Agent 自行升级 | §1.2 | `用户授权不可由 Agent 自行升级` |
| 4 | GT-free 边界不得因摘要精简而失效 | §1.4 | `GT-free` |
| 5 | 实验必须过执行与证据门禁 | §1.5 | `执行门禁` |
| 6 | R14 不得把路线终止等同于科学真理否定 | §1.7 | `不得把「路线终止」等同于「科学真理被否定」` |
| 7 | 重大科学主张需要来源与适用范围 | §1.1 | `相关性不得写成因果性` |
| 8 | 子 Agent 不得绕过已有状态写入权限 | §3.1 | `子 Agent 不得绕过已有状态写入权限` |
| 9 | 实验预算 / 冻结协议 / Anchor 不得自行修改 | §1.5 | `冻结` |
| 10 | 无法加载必需规则时不得假装完成审查 | §1.4 | `没读规则` |
| 11 | 锚点变更只有用户能授权 | §0.2 | `只有用户能授权` |
| 12 | `loaded` 与 `referenced` 必须区分 | §2.1 | `loaded` |
| 13 | 缺必需上下文不得继续 | §2.1 | `blocked_missing` |

---

## 3. 删除为 STALE 的内容（不搬运）

这些行在迁移时被显式排除。**保留它们才是丢规则** —— 它们与既有权威冲突。

| # | 原位置 | 原文（要点） | 冲突对象 | 正确口径 |
|---|---|---|---|---|
| 1 | §1.1 | 「检索未达饱和必须记入 `INDEX.md` 的 Warnings」 | `literature-policy` §3.3 / §6、`phase-r2-r5` §A4.1、`project-layout` §6.2 | 记入 `STATUS.md` 的 **Critical uncertainties**（根 `INDEX.md` 只留跨路线缺口） |
| 2 | §4 R2/R5 | 同上（同一句的第二份副本） | 同上 | 同上 |
| 3 | §4 R3—R6 | 「未核实的『无人区』声称记 Warnings」 | `phase-r3-r6` 落盘第 4 步、`project-layout` §6.2 | → Critical uncertainties |
| 4 | §4 R12 | 「门禁 fail 或六维中位 <3 → Warnings」 | `phase-r12` §D9.4.4、`scoring-policy` §4 规则 5 | → Critical uncertainties |
| 5 | §4 R3—R6 | 「发散策略约束见 §R3.8：每个候选至少通过一种算子推导」 | `phase-r3-r6` §R3.8 定义的是**五种策略**，P1—P6 在 §R3.3 | 两套约束都要满足，不能合并成一句 |

这五条是本轮「删除反而更正确」的实例：`SKILL.md` 里同一条规则的第二份副本已经漂移，
删掉重复之后矛盾不再存在。

---

## 4. 无法机器校验、只能人工保证的部分

下列规则在搬运后**没有**专属机械闸门。它们靠三个较弱但真实的手段保持，必须在维护时人工确认：

| 规则 | 现状 | 补偿手段 |
|---|---|---|
| Discovery / Assurance 的分工 | 只有文字 | `preset_router` 的 `execution_scope` 间接区分 |
| 推进纪律（四步链，不在纯证明上停留） | 只有文字 | `insight_to_method` 的进展五维会暴露「只有解释、没有证据」 |
| Team 派遣优先询问 | 只有文字 | 派遣入口在 `subagent_context.build()`，可人工核对 |
| 设计依据（§7 全部） | 只有文字 | 本文件与 `design-rationale.md` 互相引用 |

**如实声明：** 这四条不是「已被机器保证」，而是「已迁移且仍可读」。把它们的缺失说成
已被校验，会是本轮最严重的失实。

---

## 5. 已知未修复项

| 项 | 影响 | 为何本轮不动 |
|---|---|---|
| 约 20 处 `.research-idea-pipeline/routes/...` 仍作为正常落盘路径出现在 9 个 phase 文档 | 与 v2.1.0 的单根政策冲突 | 涉及科学落盘路径，属规范漂移而非上下文问题，需单独一轮 + 逐条核对 |
| `roles.md` 六个攻击面 vs `invocation-prompts` / `phase-r7` 八个攻击面 | 科学规则冲突 | 不是上下文问题；改它等于改科研评审口径，须用户裁定 |
| `research-state-policy` §5 表与紧随其后的说明条目对 R12 写入口径不一致 | 读写契约内部矛盾 | 属科学契约，须用户裁定 |
| `presets/self-evolution.md` 已改名为 `strategy-evolution.md`，`preset-policy` 仍有一处旧名 | 陈旧路径 | 一行修正，随下一次文档轮处理 |

---

## 6. 复核命令

```bash
python3 scripts/release_check.py                     # 唯一发布判据
python3 -m unittest discover -s scripts -p "test_*.py"
python3 scripts/section_index.py check
python3 scripts/context_planner.py check
```
