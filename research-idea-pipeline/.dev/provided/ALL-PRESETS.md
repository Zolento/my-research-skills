# CIE 16 Preset Prompts（完整阅读版）

# CIE Preset Shared Contract（所有 Preset 共同适用）

> 这是加载时的共同契约，不是新的 R 阶段、Research State 或 Scheduler。加载一个预设时，先读取当前安装版 `SKILL.md`、项目 `AGENTS.md` / 适用 `CLAUDE.md`，再加载本文件与选中的单个 Preset；需要时按现有 references 补充。不得一次注入所有预设。

## 权威与权限

1. 仅使用当前项目已生效的研究契约、路线锚点、已有授权、实际执行环境；已有 `research-state.json` 不得重新 Bootstrap。尚未确定路线且不能唯一确定时，先解决路线归属；不猜测。
2. canonical Research State、冻结预注册与原始实验产物是科学事实依据。Cognitive Memory、Context Brief、Strategy Memory、Preset 事件均为索引、派生或辅助建议，不是第二份科学真相。
3. 证据必须经过现有 R8/R9.O/R10/R11 及 Evidence Qualification 规则；运行失败不等于机制被否证；未经事前冻结的预测不能追认。Scope 不得无证据扩大。
4. 现有 AALG、PEIG、容量/干预强度/优化条件/可识别性、公平对照、资源限制、角色隔离和 Anchor Change Order 均优先于 Preset。
5. 先判断意图是否只读/建议/执行；只读请求不能触发实验或科学状态写入。不可自行授权 GPU、修改主锚点、推送、合并、发布或执行破坏性操作。
6. 每次科研动作之前从磁盘恢复相关 State、Scheduler、Cognitive Memory 与尚未完成的执行检查点；重要更新后核验、持久化并保证可恢复，不依赖聊天历史。
7. 如本环境没有自动事件监听器、运行时执行器或 Dispatcher，不能假装 Preset 已自动触发/动作已派遣。明确输出 `recommendation_only` / `blocked` 以及缺口。

## 标准执行与回报

- 开始：报告 `preset_id`、入口、路线、state_version、意图与执行边界，核验关键先决条件。
- 过程：使用已有 R 阶段和工具完成本 Preset 所定义的工作；任何失败、证据与权限冲突均保留原始来源和范围。
- 结束：给出 `action_taken`、`scientific_delta`、`decision_delta`、`state_writeback`、`next_action`、`stop_reason`；无变化应如实写 `none`，不得包装为 Insight。
- 派生记忆写回前先确认源版本；若 State 变化，按现有授权更新 canonical 再重建认知投影。只有实际拥有的 API 才能调用，不得虚构工具或状态字段。


---

# Autonomous Research Loop

Preset ID: `research-loop`  
Top-level Entry: `continue-research`  
Trigger: `manual`  
Execution Scope: `execute`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
用户要求“继续科研、自动运行、持续 Loop”。已初始化项目直接继续，绝不重新 Bootstrap。只在已经授权的范围内持续推进。

## 执行协议
1. 恢复项目锚点、当前路线、State、Scheduler、Cognitive Memory、证据和在途实验；校验 Skill 版本及预算，确认未完成动作是否已被执行。
2. 调用现有 Meta-Controller 选择合法动作；优先能够改变科学认识、产生区分性预测或形成方法干预的动作，不以填满日志为目标。
3. 对机制假设构造适用条件、竞争解释、可观测预测和便宜的判别干预；允许清楚标注的探索性假设，不可事后伪造预注册。
4. 执行前经过 R8、容量/强度/优化条件/可识别性、公平比较及 GPU 授权检查；执行进程用已存在的运行 ID 与结果记录防重。
5. 经 Outcome Analysis、Evidence Qualification、R10/R11 修订状态和认知模型；更新失败边界与调度经验，证明本轮记忆是否改变后续研究动作。
6. 返回步骤 1，直到预算、用户指令、权限、安全、无合法动作或正式研究终止条件触发。每轮必要检查点落盘。

## 防漂移与退出
连续动作不带来新预测、结构变化或决策价值时，不继续同构诊断；交给 `stagnation-breaker`。上下文不一致交给 `context-drift-recovery`。工程故障交给 `experiment-failure-recovery`。每次转交只触发一次，不能互相递归。

## 产出
每轮简要记录有效证据、新预测、模型修订、下一次决策、实际派遣、state_version、预算与停止原因；没有 Insight 就报告没有。


---

# Paradigm Escape

Preset ID: `paradigm-escape`  
Top-level Entry: `explore`  
Trigger: `manual_or_stagnation`  
Execution Scope: `discover_only`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
当前问题表示可能局部最优，需要改变建模对象和假设，而不是继续修改 loss、超参数或模块名称。

## 执行协议
1. 确认停滞有实证迹象；保存当前研究锚点、经过核验的观察/反例和原路线，暂停同构优化，**不清空**历史与失败预算。
2. 构造与当前方法无关的 Problem Skeleton：可观测量、不可观测量、物理约束、目标变量、必要假设、已排除条件。标明哪些是数学必然，哪些只是当前实现选择。
3. 调用已有 R3—R6 的 P1—P6 探索协议；严格保持探索岛隔离，P3 只输出规范化 typed intermediate，P4 只读取允许的抽象骨架，不能提前混入其他岛候选。
4. 重点寻找新的变量/表示空间、信息结构、约束集合、目标、动力学、可识别性或优化层级；每个候选写明旧表述被改变的部分、理论后果、适用条件与最强反例。
5. 要求候选提出与旧模型不同的可检验预测或明确不可检验的原因。恢复完整历史后，使用 R4 结构指纹、R5 文献近邻和 R7 Assurance 检查伪创新。
6. 形成最多 3 个实质不同的优先候选；为每个提出低成本判别干预。不能达到 3 个有效候选就如实报告；不为达数量编造。

## 边界和退出
这是 Discovery，不自动启动未授权实验；挑战主锚点可以存档，但改变锚点须用户授权。无法产生结构差异则停止再次发散并记录为什么失败。

## 产出
旧表示的约束、新表示的数学对象、独立预测、最小判别、结构近邻与下一步候选；未证实不写为事实。


---

# Research Recovery

Preset ID: `research-recovery`  
Top-level Entry: `continue-research`  
Trigger: `manual`  
Execution Scope: `recover_no_experiment`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
用户换会话、换 Agent、上下文遗失或请求恢复当前科研工作；只做完整状态恢复，不擅自扩大到新实验。

## 执行协议
1. 从安装位置确认 Skill 版本，读取对应入口、项目规则和授权。读取路线 State / Scheduler / Cognitive Memory、进程状态、最新实验与 Git 工作区状态。
2. 检查 State/Memory 的来源版本、未完成 R10 修复、失败限制、预注册锁定状态、资源预算；必要时仅重建可派生记忆，不改历史结论。
3. 针对在途 GPU/外部任务检查实际进程和产物；未知状态不自动重试。检查配置/代码/数据版本与原任务匹配。
4. 恢复上一条已承诺且尚未完成的合法研究动作；区分真正阻断、可独立推进工作和已完成动作。
5. 形成一份有限的恢复检查点；如果用户只要求恢复，报告状态并停止。若同时明确授权继续研究，再转 `research-loop`，沿用原预算。

## 产出
恢复的研究问题、可信机制、关键异常、被否证方向、运行中任务、下一个动作及无法恢复项。


---

# Scientific Replanning

Preset ID: `scientific-replanning`  
Top-level Entry: `continue-research`  
Trigger: `manual_or_blocked`  
Execution Scope: `plan`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
当前路线的关键假设被否证、目标暂不可达或研究资源条件变化，需要调整行动计划而不擅自换主锚点。

## 执行协议
1. 恢复锚点、已完成与无效实验、失败边界、剩余资源、合法行动集合。
2. 将已验证事实与未证实解释分开；提出至少两条可执行的替代研究路径，给出各自的关键依赖、判别试验和失败条件。
3. 对路径比较科学重要性、执行依赖、证据质量、预期决策变化和成本；不得简单以 EIG 或模型自评分选优。
4. 标记 retain / defer / abandon / request_anchor_change。需要变更项目主锚点只能准备 Anchor Change Order 请求用户授权；不得自动执行。
5. 选一项合法下一动作，写入现有计划/调度通道并报告是否实际派遣。未经明确执行授权只生成建议。

## 产出
路线重排、弃置理由、资源约束、下一决策及可证伪的成功/失败标准。


---

# Adversarial Research Audit

Preset ID: `research-audit`  
Top-level Entry: `audit`  
Trigger: `manual`  
Execution Scope: `audit`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
严格审查当前论点、方法、预测、创新性和实验完整性；不趁审计扩展 Discovery 候选。

## 执行协议
1. 确认被审对象、其精确版本及全部证据来源；区分论文文字、代码行为与真实实验产物。
2. 按既有 R7/R10/R13 审核理论必要条件、结构近邻、替代解释、数据泄漏、容量/优化公平性、可识别性、统计有效性、Scope 和复现条件。
3. 每个实质攻击给出：目标 Claim、最强反例/替代机制、已有证据缺口、能改变判断的最小判别，以及 kill/repair/narrow 条件。
4. 如有 critical flaw，按合法 R10 修复合同处理，不直接修改 Claim Status 或自行制造闭环；需要未授权新实验时请求授权。

## 产出
经证据排序的关键漏洞及其判别、状态影响和阻断条件。不生成新研究方向；不能仅靠主观评分。


---

# Research Review

Preset ID: `research-review`  
Top-level Entry: `continue-research`  
Trigger: `manual`  
Execution Scope: `read_only`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
用户想知道“目前究竟发现了什么、为什么停滞、下一步最好做什么”，不要求推进实验。

## 执行协议
1. 以只读方式恢复路线、主锚点、State、Cognitive Memory、最近有效实验、预算和调度记录。
2. 将发现分成：有效证据支持、竞争假说、无效/失败执行、尚未解释异常、被否证范围。
3. 指出当前最薄弱的因果/数学链条和最高价值的不确定性；辨别是否因反复归因而停滞。
4. 比较不超过三种下一动作，说明各自的决策价值、证据条件和成本，不派遣任何动作。

## 产出
一页研究现状，包含 Scientific Delta、未解机制、最关键风险与下一建议。明确标记 `read_only`，不得写回 State、启动 GPU 或暗中切换为执行模式。


---

# Context Drift Recovery

Preset ID: `context-drift-recovery`  
Top-level Entry: `continue-research`  
Trigger: `event`  
Execution Scope: `recover_no_experiment`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
检测到 Skill/Context 版本不一致、关键规则不在活跃上下文、当前动作偏离锚点、压缩/会话重启等有记录的信号。没有程序性触发器时只作为人工调用协议。

## 执行协议
1. 暂停派遣新副作用动作，保存当前动作和触发事件；避免重复记录同一状态版本的事件。
2. 重新从磁盘加载 Skill 核心规则、当前路线锚点、State、Scheduler、Cognitive Memory 与执行检查点；检查版本与权限。
3. 核验下一动作是否仍合法，是否重复完成或被失败证据禁止；记录漂移类型和已恢复的契约。
4. 可恢复则回到中断动作；不可恢复则 HOLD，报告唯一明确的阻断原因。不得在恢复流程内递归调用自身。

## 产出
recovered/hold、前后版本与动作、恢复证据、仍存在的缺口。


---

# Stagnation Breaker

Preset ID: `stagnation-breaker`  
Top-level Entry: `continue-research`  
Trigger: `event_or_manual`  
Execution Scope: `decision_only`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
连续有效闭环无独立预测/科学决策变化、候选结构指纹重复、AALG 诊断预算耗尽，或由运行轨迹观察到重复诊断。单次负结果不足以触发。

## 执行协议
1. 读取最近有效研究动作、结构签名、失败作用域、诊断预算及研究目标，区分工程卡死、优化卡住与建模范式卡住。
2. 计算可核验的停滞证据：相同机制前提、重复行动、预测/决策 delta 缺失；不以 Agent 主观感受作为触发依据。
3. 如果是工程故障，路由 `experiment-failure-recovery`；如果仍存在便宜且有区分力的判别干预，优先允许一次合法干预。
4. 仅当表征层停滞确立，输出 `paradigm-escape` 的单次触发建议/调度决策；保持原研究锚点和所有失败限制。
5. 同一状态快照和原因不可反复自触发；给出停止、冷却或等待新证据条件。

## 产出
停滞证据、分型、下一 preset 或实验、未触发理由及消除循环的检查点。


---

# Experiment Failure Recovery

Preset ID: `experiment-failure-recovery`  
Top-level Entry: `continue-research`  
Trigger: `event_or_manual`  
Execution Scope: `engineering_recovery`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
OOM、NaN、异常退出、数据解码失败、训练崩溃、作业失联或硬件故障。

## 执行协议
1. 锁定 run_id、实验 ID、提交版本、配置、数据、日志和进程事实；判断进程是否仍在运行，禁止盲目重试。
2. 分类为 environment / data / numerical / resource / code / scientific-invalid；按最小可复现实例验证失败原因，避免无意义归因。
3. 优先采用不改变科学干预定义的工程修复；若修改 batch size、精度、步数等会影响公平性或优化条件，必须重新进行可识别性与预注册核查。
4. 生成合法重试计划，保留原失败 attempt 与 provenance，增设 attempt ID；不得把执行失败写成科学负面证据。
5. 当修复无把握或预算不足时 HOLD，记录人工授权条件。

## 产出
失败分类、根因证据、最小修复、重试幂等性检查、科学有效性是否受损与下一动作。


---

# Evidence Conflict Repair

Preset ID: `evidence-conflict-repair`  
Top-level Entry: `audit`  
Trigger: `event_or_manual`  
Execution Scope: `evidence_repair`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
预测、观测、Evidence、Claim、Insight、认知记忆间存在不同版本、缺失引用、失效来源或相互矛盾的合法性标记。

## 执行协议
1. 将相关实验和预测升级链临时置于不得提升科学支持的状态；保存冲突清单和原始来源。
2. 逐级核对冻结预注册、结果结构/原始摘要、执行有效性、统一 Evidence Qualification、R9.O、R10/R11 及 Scope。
3. 区分观察错误、元数据错误、无效证据、真正冲突预测；不能用猜测补齐历史 prediction_ref 或事后改变冻结规则。
4. 按已有权限进行修复/失效传播；仅在合法状态迁移之后重建 Memory、Scheduler 投影。未解决的冲突保持 HOLD。
5. 验证没有通过其他入口间接认证 Insight，且同一冲突不反复重试。

## 产出
冲突来源、资格判断、合法修复或 HOLD、受影响的 Claim / Insight / Memory 引用及复核结果。


---

# Resource & Execution Recovery

Preset ID: `resource-recovery`  
Top-level Entry: `continue-research`  
Trigger: `event_or_manual`  
Execution Scope: `runtime_recovery`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
GPU/CPU/存储不足、依赖变化、环境失联、队列阻断、时间或计算预算不足。

## 执行协议
1. 查询真实资源使用和在途作业，不根据聊天记录假定进程已停止；识别可重入和不能重复的外部副作用。
2. 记录当前执行意图、任务 ID、尝试次数、检查点及预算余额；不得重置配额或重复派遣已完成实验。
3. 寻找符合原科学协议的资源替代、可在 CPU 上完成的验证、理论推导或必要文献工作；改变科学条件需要重新预注册/比较设计。
4. 可安全恢复则重启/继续，不能恢复则 HOLD；禁止通过减少必要对照伪造可执行性。

## 产出
资源事实、可执行替代、预算变化、实际派遣状态、恢复条件。


---

# Cognitive Memory Consolidation

Preset ID: `memory-consolidation`  
Top-level Entry: `continue-research`  
Trigger: `event_or_manual`  
Execution Scope: `derived_only`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
合法 R11 更新、机制修订、新会话恢复或认知索引版本落后于 canonical State。

## 执行协议
1. 根据 canonical State、正式预注册、有效实验和 provenance 重新构建认知索引；复用已有 cognition build/check，勿重写权威事实。
2. 合并同义机制索引但保留不同适用范围、版本、失败条件和原始 ID；被否证机制保留为有范围的负面知识。
3. 对旧预测、异常和认知修订标记 valid / stale / unresolved；历史无法恢复的预测标记 retrospective/unknown，不得追认冻结。
4. 生成精简 Hot/Warm 上下文摘要；核对 State version、引用、过期传播和跨会话加载。
5. 若仅为派生投影更新，不能上调 Claim、Insight 或 Scheduler 成功指标。

## 产出
更新的索引、实际变化/失效传播、版本核验和可恢复性检查结果。


---

# Research Loop Health Check

Preset ID: `loop-health-check`  
Top-level Entry: `continue-research`  
Trigger: `event_or_manual`  
Execution Scope: `inspect_only`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
每个有意义的科研闭环后或用户要求健康检查；长循环中可按现有调度频率进行，但不能占满研究计算预算。

## 执行协议
1. 从真实 action/evidence 日志检视重复动作、失败恢复次数、科学有效结果、机制预测、state delta、决策 delta 与实际资源消耗。
2. 区分科学无突破但实验有效、执行故障、伪进展（新增文档但无新证据）和正常探索。
3. 对触发阈值的类别只推荐相应 preset：context drift、stagnation、experiment failure、evidence conflict、resource；不自行跨权限执行。
4. 记录当前快照上已建议/已派遣的恢复动作，防止检查器和修复器循环触发。

## 产出
简短健康状态、触发证据、被推荐动作与是否已派遣、暂停/继续条件；不把代理自评作为核心度量。


---

# Strategy Evolution

Preset ID: `strategy-evolution`  
Top-level Entry: `continue-research`  
Trigger: `manual_or_scheduled`  
Execution Scope: `strategy_update`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
利用历史研究表现调整探索算子及下一动作选择，不改变科学证据与硬门禁。

## 执行协议
1. 汇集可信的操作者表现：可区分预测、有效干预、无效诊断、结构重复、证据质量、成本。限制于相同或可比的问题结构，不以自评创新分替代反馈。
2. 复用现有 Strategy Memory 生成有 provenance 的候选策略更新，并保留 exploration floor、失效范围和重新激活条件。
3. 检查当前 Scheduler 是否有实际消费建议的 Strategy Decision Adapter：只能在同等合法、同等硬优先级的动作中调整顺序，不允许改 AALG、锚点、预算或证据规则。
4. 若有 adapter，比较**相同** state_version、合法动作集合、固定规则下 with-memory / without-memory 的行动排序或选择；记录 baseline、applied、decision_changed、dispatch_status 与不变原因。
5. 若没有 adapter，**必须明确输出 `recommendation_only`，不得声称 L2 实际策略进化**；提出消费接口的工程缺口，但不能伪造 `strategy_applied=true`。
6. 候选策略只有经独立 Replay/对照验证才可声称带来科研能力改进；实际策略应用不等于 Insight 增益。

## 产出
L1 建议、L2 实际调度影响证据、L3 独立效果证据，分别标记 verified/unverified；下一步合法探索动作。


---

# Hypothesis Portfolio Rebalance

Preset ID: `hypothesis-rebalance`  
Top-level Entry: `explore`  
Trigger: `manual_or_scheduled`  
Execution Scope: `portfolio`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
当当前 Hypothesis Portfolio 被单一假设、同构结构或同一个学习算子支配时，恢复多样性与风险分散。

## 执行协议
1. 从当前 QD archive、结构签名、机制模型、否证约束中识别重复组合；比较不同 niche 的贡献和证据覆盖。
2. 明确哪些假设是同义变体、哪些在不同观察或干预下给出实质不同的预测；不凭词面多样性判定创新。
3. 调用现有 P1—P6 及 R4/R6 的隔离种群规则，允许反转占优假设并保留少量高风险高发现潜力方向。
4. 结合预算、证据等级与研究锚点提出 retain / pause / explore；淘汰不得跨越有效否证作用域，也不得自动改主锚点。
5. 与合法调度器衔接，输出具体候选和将改变的下一次动作；无派遣接口时只报告建议。

## 产出
组合集中度、结构差异、新假设独立预测、重新平衡建议与追踪引用。


---

# Discovery Replay Evaluation

Preset ID: `discovery-replay`  
Top-level Entry: `continue-research`  
Trigger: `manual_or_scheduled`  
Execution Scope: `evaluation_only`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
评价 CIE / Strategy Evolution 是否真的改善科学发现和下一动作质量，而不是证明 Prompt 看起来更好。

## 执行协议
1. 使用现有 research_replay / fixture 机制，选择含历史冻结点、隐藏后续结果和独立答案来源的案例。隔离隐藏信息，防止被检索索引、Memory 或候选生成提前看到。
2. 用相同初始 State、模型、预算、合法工具、停止标准比较 baseline 与新策略；尽可能多次重复运行并控制随机波动。
3. 评估：有效预测准确/校准、判别干预质量、结构创新、无价值诊断次数、下一决策变化、科学证据有效性与资源消耗。
4. 不把候选生成 Agent 的自评当作主要评判；已知历史结论或独立验证与盲评优先。
5. 清楚区分单元测试、合成端到端、真实 Agent A/B 和真实科学新发现的证据等级。策略未优于 baseline 应保留旧策略或标记试验性，不自动晋升。

## 产出
复现实验条件、隔离校验、对照结果与不确定性、是否建议 promotion 和尚未验证的推断。


---
