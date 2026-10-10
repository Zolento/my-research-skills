# 调用契约：四个用户入口

> **结论：用户只需要说四个入口之一。`R0`—`R14` 是**内部实现**，用户不需要知道它们。**
>
> **在调用解析里的位置：** 这四个入口是 [SKILL.md](../SKILL.md) §0 解析顺序的**第 1 层**
> （自然语言等价表达是第 2 层）。`phase=` 是**第 3 层**的专家 / 调试覆盖，**不是常态入口**。

**为什么要有这个文件：** 系统内部已经成熟（15 阶段、八类对象、24 条硬规则），
但**入口若没做好，真实使用会退化成「用户一调用 → Agent 看见 R0—R14 → 不知道该从哪开始」**。
本文件把调用契约固定下来，**防止实际使用时绕过新哲学**（尤其：不要一上手就发散、不要编造状态）。

| 入口 | 什么时候用 | 主要做什么 | **不做什么** |
|---|---|---|---|
| **`start-project`** | **第一次**进入一个已有代码 / 实验 / 文献的项目 | 只跑 Bootstrap 序列 `B0`—`B6`（[SKILL.md](../SKILL.md) §0.3） | **不跑 `R3`—`R14`**；不编造状态 |
| **`continue-research`** | 已有 Research State，咨询或授权继续研究 | 核对状态 → 按授权推荐或执行 → 回写证据 → 重选动作 | 不超出授权、资源预算和停止条件 |
| **`explore`** | **强制进入 Discovery**（尤其 Paradigm Escape） | 跑 `R3`—`R6`，且**保证 `P1`—`P6` 全跑** | 不用 feasibility / venue fit 杀范式候选 |
| **`audit`** | **只攻击当前路线**，不扩展 | 跑 `R7` / `R10` / `R13` | **不产生新 idea**；不改 `claims[].status`（除 R10 的合法处置） |

**自然语言等价表达**（用户不必记斜杠命令）：

| 入口 | 用户可能这样说 |
|---|---|
| `start-project` | 「读一下我这个项目，现在什么情况」「我刚 clone 下来，帮我建立研究状态」 |
| `continue-research` | 「接着做」「下一步该干什么」「现在最值得做什么」 |
| `explore` | 「多给我一些新方向」「跳出现在的思路」「有没有完全不同的做法」 |
| `audit` | 「攻击一下我现在的路线」「这套说法站得住吗」「帮我找漏洞」 |

---

## 0.1 预设：入口内部的协议（自然语言即可，不必记 id）

四个入口解决"从哪进"；**预设**解决"进去以后按哪套协议做"。用户直接用自然语言表达，
Router 负责解析（显式 id > 别名 > 意图词 + 入口 > 意图词 > Loop 自动建议），
政策见 [preset-policy.md](preset-policy.md)；共同约束见 [shared-contract.md](../shared-contract.md)；元数据见 [preset-registry.json](../preset-registry.json)；基准用例见 [router-fixtures.json](../router-fixtures.json)（`preset_router.py check --fixtures`）。

| preset | 入口 | 授权 | 用户可能这样说（registry `intent_examples`） |
|---|---|---|---|
| `research-loop` | `continue-research` | `execute` | 「继续自动科研」、「按现有授权持续跑 loop」 |
| `paradigm-escape` | `explore` | `discover_only` | 「跳出当前思路」、「换一个完全不同的数学建模角度」 |
| `research-recovery` | `continue-research` | `recover_no_experiment` | 「恢复之前的科研工作」、「上下文没了，恢复项目状态」 |
| `scientific-replanning` | `continue-research` | `plan` | 「重新规划当前路线」、「这条路线被否证了，重新制定计划」 |
| `research-audit` | `audit` | `audit` | 「审查论文方案」、「找出当前实验的致命缺陷」 |
| `research-review` | `continue-research` | `read_only` | 「现在研究进展怎么样」、「总结当前真实发现，不要执行」 |
| `evidence-conflict-repair` | `audit` | `evidence_repair` | 「实验结果和 evidence 对不上」、「修复 claim 和 memory 冲突」 |
| `context-drift-recovery` | `continue-research` | `recover_no_experiment` | 「Skill 规则丢了，恢复上下文」、「上下文压缩以后重新确认规则」 |
| `memory-consolidation` | `continue-research` | `derived_only` | 「整理认知记忆」、「State 更新后刷新 Cognitive Memory」 |
| `resource-recovery` | `continue-research` | `runtime_recovery` | 「GPU 不够了」、「环境崩溃，恢复执行」 |
| `experiment-failure-recovery` | `continue-research` | `engineering_recovery` | 「训练 OOM 了」、「实验 NaN 了，检查并恢复」 |
| `loop-health-check` | `continue-research` | `inspect_only` | 「检查科研 loop 健康度」、「有在真正推进科研吗」 |
| `stagnation-breaker` | `continue-research` | `decision_only` | 「一直在重复归因」、「检查是不是陷入局部最优」 |
| `strategy-evolution` | `continue-research` | `strategy_update` | 「根据历史结果改进探索策略」、「让策略记忆真正影响下一轮决策」 |
| `hypothesis-rebalance` | `explore` | `portfolio` | 「所有 idea 都一样」、「重新平衡假设组合」 |
| `discovery-replay` | `continue-research` | `evaluation_only` | 「做一次历史研究回放」、「检验自进化策略是否真的更好」 |

**安全规则（`PR1`—`PR10`）：** 否定不触发（「不要审计」→ `HOLD`）；歧义取最小授权并要求确认；
只给 `phase=R<n>` 时交回既有阶段；只陈述问题先只读诊断；**只读提问绝不升级为执行**；
工程故障不写成科学否证。

## 1. `start-project` — 第一次进入现有项目

**用途：** 把「一个已有代码/数据的仓库」变成「有 Research State 的项目」。

**它只做一件事：看清现状。** 见 [SKILL.md](../SKILL.md) §0.3 的 `B0`—`B6`。

**可直接粘贴的提示词：**

```text
用当前项目的 Research Skill 接管这个项目。这是第一次运行。

只做首次接管（Bootstrap），不要推进研究：
1. 盘点已有资产（README / AGENTS.md / 代码结构 / 训练与推理入口 / configs /
   已有实验结果 / logs / refs / 笔记），已有信息不要重复问我。
2. 建立一个**最小**的 Research State：只写 contract 与模板骨架，
   顶层 state_version 写 0。
3. **状态必须稀疏**：每一条都要能指回真实来源（文件 / 代码 / 数据 / 用户原话）。
   指不回去的不要写。宁缺勿造。
4. 只在有依据时写 uncertainties；**不要**生成 hypotheses 或未来实验计划。
5. 最后告诉我：现在已知什么、最危险的隐含假设、最关键的未知量、
   以及**下一步建议**——然后停下等我确认。

不要跑发现、提案、叙事或审查阶段。
```

---

## 2. `continue-research` — 按用户授权继续研究

**前置：先判断这是不是已有项目。** 入口**只有四个**，接管不新增第五个。
检测到 canonical `research-state.json` 时，它就是一个**已初始化项目**：
**不得执行全新 Bootstrap（`B0`—`B6`）**，只能走 Legacy Research Handoff。

```sh
python3 scripts/legacy_handoff.py detect --state .research-idea-pipeline/routes/<R>/research-state.json
python3 scripts/legacy_handoff.py take   --state .research-idea-pipeline/routes/<R>/research-state.json
```

`detect` 判定 `bootstrap_forbidden`；`take` 执行**只读**兼容性审计并重建认知记忆，
然后写接管报告。**严重兼容性错误一律不写回**（退出码 3），
**不得通过重建一份新 Research State 绕过问题**。规则见
[legacy-handoff.md](legacy-handoff.md)。

**先区分意图。**「下一步建议是什么」只要求建议。「接着做」「继续探索方法」授权执行。
用户明确要求只给建议时，给出建议后停止。不得把执行请求默认改成咨询。

执行请求下，在已授权范围内循环：

1. 核对 state、scheduler 与最新实验产物。记录尚未核实的差异。
2. 读认知记忆 `cognition/context-brief.md`（默认路径，无需用户指定）：
   恢复机制、未解异常、未收口竞争、禁止重复方向与上一轮决策。
3. 按 [scheduler-policy.md](scheduler-policy.md) §3 选择当前可执行动作。
4. 执行动作，核验产物，按对应阶段契约回写 state。
5. 用新增证据重选动作；收尾时重建认知记忆
   （`python3 scripts/cognition.py build --state <state.json>`，并让 `check` 退出 0）。
   已有授权不因跨越阶段而失效。

停止条件是用户指定边界、预算耗尽、必要授权缺失，或确无可执行动作。
若修复尚未闭环，停止不代表阶段完成。报告阻塞，保留有效状态和未完成产物；不得伪造 closure。
等待实验时，继续不依赖结果且已获授权的工作。无独立工作时报告等待原因。
不得把推荐下一步、重复校验或创建文档当作已经执行了研究动作。

**可直接粘贴的提示词：**

```text
继续推进当前研究，在已授权资源内执行，不要重复首次接管。
围绕主锚点，让实验结果产生下一条方法假设和可判别的干预。
机制未证实时可以提出候选，但不得把机制假设写成既定事实。
结果产生后先做 [Evidence Outcome Analysis](evidence-outcome-analysis.md)，再经 R10/R11 回写。
有效 negative evidence 进入科学记忆，无效执行不能否证 hypothesis。选下一动作前读取
stop rules，并通过 planning 与 post-update Assurance；缺审计则 HOLD。
候选失败后检查失败范围。遇到方法瓶颈，按 R5.1 补检索并阅读关键机制与实现资料。
将资料转成有来源、适用条件和最小对照的方法干预，再继续探索。
不要求先解释全部未知。遇到真实阻塞时说明依赖和可继续的独立工作。
回报新增证据、方法变化、已执行动作和下一步。
```

---

## 3. `explore` — 强制进入 Discovery

**用途：** 用户明确要**发散**，而不是优化现状。

**可直接粘贴的提示词：**

```text
用当前项目的 Research Skill 做一轮发散探索（Discovery）。

要求：
1. 候选由**彼此隔离**的探索算子生成：P1 问题重构 / P2 假设破坏 /
   P3 领域擦除 / P4 远域结构类比 / P5 理论视角 / P6 反例与测量反转。
   各算子**在产生候选之前不得看到其他算子的候选内容**。
2. 不要只给"改进现有方法"的候选；**至少要有一半候选改变问题本身**。
3. P4 的跨域联系必须逐维给出对应（object / relation / constraint / failure mode），
   只说"两个领域都有 distribution shift"不算。
4. P5 每个理论视角必须导出至少两类非平凡后果（新解释 / 新边界或不可能性 /
   新预测 / 新算法设计 / 新判别实验），否则判为理论包装。
5. P6 的方向必须写成可证伪命题。
6. **不要**用可行性低、暂时没有定理、不像当前主流、venue fit 不明来淘汰候选。
   这些不是本轮的判据。

最后给我：候选清单（各标 island 与结构签名）、哪些是结构上真正不同的、
以及最可能带来"原来这个问题还可以这样看"的那一个。
```

---

## 4. `audit` — 只攻击，不扩展

**用途：** 用户要**对抗性审查**，不要新想法。

**可直接粘贴的提示词：**

```text
用当前项目的 Research Skill 审查我现在的路线。**只攻击，不要提出新方向。**

要求：
1. 按八个攻击面逐个检查：最近工作碰撞 / 更简单解释 / 识别性失败 /
   理论假设失败 / 统计混杂 / 适用范围过度声称 / 可复现性 / 完整性。
2. 每个攻击必须输出五元组：
   （攻击 / 目标主张 / 替代解释 / 判别实验 / 杀死条件）。
3. **不要**给 1—5 分当主要输出——分数不是我要的。
4. 特别注意**最小解释检验**：有没有更简单的解释能产生同样结果
   （多训练几步、参数更多、正则化效应、优化效应、数据泄漏、
   更好调参、通用一致性目标）？没排除之前，不得把结果解释成复杂机制成立。
5. 如果发现 critical flaw，**不要只写进审查报告**——必须给出
   至少一种状态变化（补实验 / 修实现 / 收窄主张 / 重述 / 换路线 / 杀假设 / 接受局限）。

最后给我：致命弱点清单 + 每条的判别实验 + 哪些主张的适用范围被高估了。
```

---

## 5. Agent 的硬约束（四个入口共同适用）

1. **不要把 `R` 编号当作用户语言。** 用户说"帮我看看这个项目"，
   **不要**回答"我将执行 R0 → R1 → R2"；直接用研究者能懂的话说你在做什么。
   用户问起时才解释内部阶段。
2. **入口即边界。** `start-project` **不得**顺带跑探索；`audit` **不得**顺带产出新 idea。
   越界会让用户无法预期成本和结果。
3. **按入口范围收尾。** `start-project`、`explore`、`audit` 完成本次请求后停止。
   `continue-research` 按 §2 区分咨询与执行，不因阶段结束重复请求已有授权。
4. **状态纪律不因入口而放松。** 任何入口都不得编造状态条目
   （判据见 [SKILL.md](../SKILL.md) §0.3：每条必须能指回真实来源）。
