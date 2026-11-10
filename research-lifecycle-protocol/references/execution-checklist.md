# Execution Checklist（完整输出前自检）

> `SKILL.md` §6 保留**最小十条**；本文件是完整清单，含文献、评分、叙事、门禁的全部检查项。
>
> **加载条件：** 交付前的完整自检、审查某次输出是否达标、或需要证明「检查确实做了」时加载。
> 常规单轮回复只跑 `SKILL.md` §6 的最小十条。

本文件由 v2.2.0 的 L0 精简产生：内容来自 `SKILL.md` §6，未改变任何检查项。

## 1. 完整自检清单（每次输出前）

- [ ] phase 已明确，且与该阶段的输入约定一致。
- [ ] **面向用户的汇报科学优先**：默认五段、先结论；没有把 PID / GPU UUID / 长路径 /
      内部版本号当作主文；没有把相关性写成因果性，没有把 smoke 写成有效性。
- [ ] **提出或修改方法时已做 method-depth 检查**：六问有实质回答或明确标 `unknown`；
      没有编造数学目标、机制或统计结论。
- [ ] **例行维护已实际完成**：认知投影 / STATUS / 索引等 A 类动作已执行或已确认无变化；
      没有向用户询问是否执行例行维护；维护失败已保留 `hold_reason`，没有宣称已同步。
- [ ] **B 类更新全部过门禁**：outcome / claim / assurance / failure / decision 没有绕过
      R9.O / R10 / R11 / R7；进程终止未被写成科学完成；过期 telemetry 未被当作当前事实。
- [ ] **负结果与阻塞仍可见**：没有因为简洁而隐藏负证据、重大不确定性或门禁阻塞。
- [ ] **用户只请求分析时没有执行实验**；用户请求继续科研时没有因例行维护反复请求批准。
- [ ] **锚定点（核心目标）已与用户确认**，并已写入 frontmatter 的 `core_goal`、
      路线 `INDEX.md` 的路线概要、以及 `state.json`；**未确认就开工属于违规**。
- [ ] **锚点体系完整（新增）**：根 `INDEX.md` 已声明**项目主锚点**；
      本路线的 `anchor_role` 已给出；`supporting` 时 `serves` / `serves_evidence`
      已填**且可证伪**；答不出已降级为 `orthogonal` 并在根 `INDEX.md` 公开写明
      "不参与主锚点成功判据"（`orthogonal` 不得进 R12、不得作投稿主线）。
      **`core_goal` 只记主锚点**；次锚点写的是 `core_goal_secondary`，不是
      `"theory+feasibility"` 这种拼接值。
- [ ] **锚点与产出不一致时已落盘处置，而不是只提示（新增）**：要么重新定位
      （可证伪的 `serves` 或 `orthogonal`），要么向用户提请换方向。
      **没有自行换方向、换项目主锚点或开新路线**（只有用户能授权，走 §0.2 变更单）。
- [ ] **派遣方式已定**：环境有 Team 能力时**已询问用户**；用户显式要求 Team 而环境
      不具备时，已**显式告知回退**（未静默降级、未假装使用 Team）。
- [ ] **已读项目 `AGENTS.md` 与目标路线的 `INDEX.md`**，并遵循其约定；
      **`AGENTS.md` 引用的文件已逐个校验存在性**，缺失项已记入根 `INDEX.md` 的 Warnings。
- [ ] 文献检索：**先尝试 web search，再本地与多源**；网页发现有来源记录。
      不可用或失败已记录；明确离线时跳过。网页与本地命中均没有替代多源核验。
- [ ] 已判定触发条件（T1—T8）并达到对应尽职调查等级（L1/L2/L3）与饱和判据。
- [ ] 每条文献结果标注了 `source`；结果集是本地 + 多源 的并集。
- [ ] 若发生 429，输出了等待日志，且退避符合 `10→20→40→80→160s`、上限 5 次。
- [ ] **每个启用源都有状态**（`ok` / `partial` / `unavailable` / `skipped`）；任一源降级已在输出中显式说明，且**退出码为 2**。
- [ ] **饱和计数只在「当期可用源集合未变」时累加**；集合一变已重置计数。
- [ ] 若少用了源（`--sources`），报告中已写明理由；源覆盖不完整时结论措辞已降级。
- [ ] **已解析 `arxiv.org` / `export.arxiv.org`；若解析到本地 IP，输出了「代理环境提示」段**
      （写明具体 IP 与判定类型），且**没有**据此判定"在线源不可用 / 无人在研究"。
- [ ] arxiv 结果已写入缓存。
- [ ] **创新性 / 新颖性判定**依据 prior-work collision + structural novelty +
      scientific non-triviality（**不是** venue 口味）；贡献标注了类型。
- [ ] **只有 R12 / R13 的 venue calibration 与投稿评估**引用具体顶会标准；
      **R3—R6 不得用顶会口味判断候选**（见 §4 R3—R6 的两阶段 fitness）。
- [ ] **每个方法都标了「方法来源」**（`原创` / `部分原创` / `迁移`）且**可核验**；
      没有把「迁移」包装成「原创」；标为「迁移」的**已证明迁移本身带来新性质**，
      否则其复现风险按"高"处理。
- [ ] **四步链完整**（数学建模 → 证据 → 结合 ML 方法 → 任务性能）；**没有在证明性
      工作上停留或反复**；未完成的证明已标 **"待补证明 · 待核实"** 并转入后续步骤，
      而不是阻塞链路；**也没有声称"已证明"却未完成证明**。
- [ ] **四个会议审稿人的评价都含「理论角度 + 应用角度 + 会议特性判定」三段**
      （**仅 venue calibration 表**）
      （见 [roles.md](../references/roles.md) §1.0）；R-MICCAI 不适用时已标 **"不适用"**
      而非硬凑临床相关性。
- [ ] **R3—R6：每个 candidate 都完成 §R3.7 概念级审核**（新颖性判定 / 概念可行性 /
      重叠度 / 致命反驳），没有「只给 idea 不给审核」；且未误派 S-Repro；
      **进入 QD archive 的 elite 已达 L2**，含「首次提出」声称的已达 L3 并附负检索记录。
- [ ] **assurance 五元组齐备**：每个攻击面都给了 `(Attack, Target Claim, Alternative, Discriminating Test, Kill Condition)`；**`Kill Condition` 可判定**；只有分数没有 Kill Condition 的评审**不合格**。
- [ ] **Integrity Gate（R13）**：leakage / cherry-picking / metric misuse / post-hoc bias 已逐项过闸；**R7/R8 未要求 artifact 审计**。
- [ ] **R12：先有证据台账与 claim graph，再有叙事**：`C0—C5` 完整，每个 `Ci` 都有
      `Ci ← Ej` 或标 `[待补]`；每套候选都能写出一句话的**可证伪 central proposition**；
      候选是 **2—4 套真正不同的 claim hierarchy**（**不是**同一主张的四种措辞）；
      每套用**六槽位 `S1—S6`**（`S5` 覆盖 `C0`—`C4`，`S6` 写出**不成立的条件**）；
      跨域类已做 **anti-application stress test** 与 **Transfer Legitimacy（L1/L2/L3）**；
      **六个攻击面审稿人全部派遣、S-Lit 恒派、S-Devil 不打分**；已做**叙事包装
      （重新定位，非夸大）**；**D9 给出了缺失证据清单与最小必要实验 / 定理**；无禁用表述。
- [ ] **R7 / R10 / R13：结论卡片给出了复现风险等级**，并回答了"设计层面贡献 vs 实现层面改进"；
      复现风险 = 高时总体判定不为"高"；**S-Devil 归一化后的新颖性稳健度 ≤ 2 时总体判定
      同样不为"高"**（除非走「带条件的推荐」并写明理由、缓解路径与验证点）。
- [ ] **R12：硬门禁 `G1—G5` 已逐项判定**（任一 `fail` ⇒ `not_submission_ready`，
      且**不参与六维排序**）；排序用的是**六个同向维度**，**未做也不需要极性归一化**。
- [ ] **R7 / R10 / R13：聚合前已做极性归一化**（S-Devil 反驳分 → 新颖性稳健度 = `6 − 反驳分`），
      汇总表同时给出原始分与归一化分（见
      [scoring-policy.md](../references/scoring-policy.md)）。**不得用「6 个都同意」声称
      reviewer consensus** —— 六个 reviewer 不是独立样本。
- [ ] 所有"首次提出"声称**已完成 L3 穷尽检索**、经 S-Lit 核实、附负检索记录，
      否则已降级为"据本次检索未见"或标注"待核实"；
      **全部措辞符合 [evidence-policy.md](../references/evidence-policy.md) 的证据等级表**。
- [ ] **`STATUS.md` 的 Critical uncertainties 已统计「待核实」条数**；若超过 5，已在本轮内收敛
      （补检索 / 补实验 / 明确降级措辞）；**`needs_verification` 的条数也已计入根
      `INDEX.md` 的全局 Warnings**，超过 5 已开补元数据 TODO。
- [ ] **正文形式已达受控中文**：落盘文件已跑
      `python scripts/ste_lint_zh.py --disable synonym-rotation <文件>` 且**硬违规为 0**
      （无分号串联动作、无超长句、无虚动词「进行分析」、无营销形容词、无套话）；
      对话返回**第一段就是结论**；一份文档内同一概念只用一种写法。
      **若用户显式声明了 asd-ste100 档**，命令改为
      `python scripts/ste_lint_zh.py --max-chars 25 <文件>`，且**建议类报告已逐条人工处置**
      （脚本不会因此失败，见 [writing-policy.md](../references/writing-policy.md) §7）。
      **⚠️ 情态未被删改**（「可能 / 初步」原样保留，见
      [writing-policy.md](../references/writing-policy.md) §5）。
- [ ] 理论/可行性卡点已先检索（含负结果文献），未直接假设成立。
- [ ] 无臆造引用；无法确认处标注"待核实"。
- [ ] **方案/审阅记录已落盘到所在路线的 `routes/<R>/docs/`**，命名符合
      `<R><NNN>-<slug>.md` / `<ID>-review-r01.md`；且**文档前缀 = 路线字母**（不随阶段变化）。
      **`slug` 未越界**（只用 [project-layout.md](../references/project-layout.md) §2.1 封闭枚举）；枚举外的派生物写的是 frontmatter 的
      `subtype`，且路线 `INDEX.md` 文档表**有 `subtype` 列**。
- [ ] **落盘分档正确**：交付物在 `routes/<R>/docs/`（**扁平，无子目录**）；
      子代理**原始评审件**在 `.research-idea-pipeline/routes/<R>/<被审ID>-r<NN>/`，
      **没有**塞进 `docs/`；**正式 review 自带摘要**，且没有引用指向原始件。
- [ ] **`docs/refs/` 下每个 PDF 都在 `docs/refs/index.json` 里有条目**
      （`python3 scripts/refs_index.py --check` 通过）；索引中无绝对路径；
      `needs_verification = true` 的条目**未**用于支撑创新性声明；
      遇到旧 schema 已用 `--migrate`（**不是**直接重建，避免丢旧字段）。
- [ ] **已更新路线 `INDEX.md`**（资产目录：文档索引、Experiments、Decisions、Reviews、
      Milestones、Recent Research Changes）**与 `STATUS.md`**（当前状态，由 state 生成）。
- [ ] 未达饱和的检索、未缓解的风险已记入 `STATUS.md` 的 Critical uncertainties；
      跨路线层面已同步到根 `INDEX.md` 的全局 Warnings。
- [ ] 已附 `state.json` 片段与 **`next_action_recommendation`**（**不是** `next_phase_suggestion`
      —— `R0`—`R14` 是**能力**不是固定流水线；下一步由
      [scheduler-policy.md](../references/scheduler-policy.md) 的 `next_action_policy` 决定）。

---

