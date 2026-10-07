# research-idea-pipeline

面向 **CVPR / ICML / NeurIPS / MICCAI** 投稿的研究创意全流程辅助 Skill。覆盖文献调研、idea
发现（含 idea 级审核）、方案生成、**多 preset 叙事生成与审稿**、方案复核的完整链路。
可单独运行任一双循环阶段，也可串联运行。

**字母顺序 = 工作流顺序：**

```
A 文献调研 → B idea 发现 → C 方案生成 → D 叙事生成 → E 方案复核
```

> **状态：已构建，待审核。** 本项目尚未安装到任何 skills 目录
> （`~/.claude/skills/`、`~/.agents/skills/` 等）。

---

## 目录结构

```
research-idea-pipeline/
├── SKILL.md                          # 入口：phase 分发（R0—R14）+ 全局不变量 + 首次运行编排
├── README.md                         # 本文件
├── references/
│   ├── research-state-policy.md      # ★ R1 权威：八类一等对象、逐阶段读写、Shape Gate S1—S7 + 引用完整性 V1—V24
│   ├── project-layout.md             # ★ 目录规范：八条 DI invariant、routes/、README/STATUS/INDEX、XID、DEC
│   ├── scheduler-policy.md           # 跨阶段调度：R0—R14 是能力不是 workflow；八级 next_action_policy + EIG÷cost
│   ├── invocation-prompts.md         # 四个用户入口调用契约（start-project / continue-research / explore / audit）
│   ├── project-intake.md             # 存量项目接管清单（9 维度；已有信息不得重复询问）
│   ├── claim-first-policy.md         # claim 语义：证据台账 + Claim Graph C0—C5 + 可证伪 central proposition + Anchor Eligibility
│   ├── evidence-policy.md            # 措辞等级 ↔ 认知状态（唯一定义）
│   ├── literature-policy.md          # 禁止只停留在本地；T1—T8 扩检；L1/L2/L3；饱和判据
│   ├── scoring-policy.md             # 两层评分：硬门禁 G1—G5 + 排序六维；极性归一化/中位数/一票否决
│   ├── roles.md                      # 共享角色：八攻击面审稿人 + 证据核验员；venue 角色仅作 R12/R13 校准
│   ├── narrative-patterns.md         # 十套叙事 preset（N1—N10，**只用于 R12**；QD niche 是七个独立科学结构轴）+ (O,T,R) 选 preset + 六槽位 S1—S6
│   ├── venue-standards.md            # CVPR / ICML / NeurIPS / MICCAI 2026 标准（逐条附 URL）+ 顶刊 + contribution type
│   ├── writing-policy.md             # 受控中文三档（asd-ste100 / Strict / 中文-顺）
│   └── phase-r0-contract.md          # R0：研究契约（只写 contract）
│       phase-r2-r5-field-mapping-retrieval.md   # R2 / R5：领域测绘 + 共演化检索
│       phase-r3-r6-discovery.md      # R3—R6：双轨发现 / 隔离种群 / 进化
│       phase-r8-evidence-contract.md # R8：证据契约 + 结果预注册
│       phase-r9-r11-experiment-loop.md          # R9 / R10 / R11：实验树 / 修复门 / 状态回写
│       phase-r12-narrative.md        # R12：claim-first 叙事（state 的视图）
│       phase-r7-r10-r13-assurance-repair-review.md  # R7 / R10 / R13：对抗保证 / 元认知修复 / artifact 审计
├── scripts/
│   ├── state_check.py                # ★ 机械闸门：Shape Gate S1—S7 + V1—V24（退出码 0 / 3 硬违规 / 4 环境）
│   ├── render_status.py              # ★ 把 state 投影为 routes/<R>/STATUS.md（幂等；--check 校验过期）
│   ├── env_probe.py                  # 工作解释器发现 + 依赖自检（退出码 4）
│   ├── literature_sources.py         # 多源适配器 arxiv / openalex / crossref + 合并层
│   ├── literature_search.py          # 可运行检索器（多源并集 / 每源状态 / 退避 / 缓存 / 代理检测）
│   ├── refs_index.py                 # 为 docs/refs/ 下每个 PDF 建 index.json（--check / --migrate）
│   ├── ste_lint_zh.py                # 受控中文 linter（vendored，MIT）
│   ├── test_state_check.py           # 离线测试：S1—S7 与 V1—V24 反例 + 表格/契约键/Carrier/打包完整性
│   ├── test_render_status.py         # 离线测试：STATUS 幂等 + 三方节集合一致
│   ├── test_golden_path.py           # 集成测试：R0→R14 字面执行 + 5 条对抗路径
│   ├── test_literature_search.py     # 离线测试（不联网）
│   └── test_refs_index.py            # 离线测试：索引旧 schema 迁移（保留旧字段）
├── templates/
│   ├── INDEX.root.md                 # 根级 INDEX.md 骨架（路线总表投影）
│   ├── README.route.md               # 路线级 README.md 骨架（路线身份证）
│   ├── INDEX.md                      # 路线级 INDEX.md 骨架（资产目录 + 时间线）
│   ├── STATUS.md                     # 路线级 STATUS.md 骨架（state 的人类投影）
│   ├── research-state.template.json  # Research State 骨架（八类对象 + 附加槽位）
│   ├── structural-equivalence-audit.template.json  # Structural Equivalence audit 骨架（十四个 facet + verdict）
│   └── scheduler.template.json       # 调度 telemetry 骨架（不进 state）
├── examples/
│   ├── example-project-layout.md     # 多路线目录与文档管理（新目录规范的完整示例）
│   ├── example-d-narrative.md        # claim-first 叙事与选型
│   ├── example-full-pipeline.md      # 主链路串联（R3—R6 → R8 → R12 → R7）
│   ├── example-field-mapping-standalone.md  # 单独文献调研（R2 / R5）
│   ├── example-followup-review.md    # 接续复核
│   ├── example-writing-tier.md       # 受控中文两档对照（asd-ste100 改写样例）
│   └── structural-equivalence/       # near-neighbor audit fixture 七件：equivalent.json / reframing-neighbor.json / transfer-only.json / component-neighbor.json / mechanism-neighbor.json / formulation-delta.json / paradigm-candidate.json
└── docs/refs/                        # 参考文献库格式示例（目标项目里放根目录 docs/refs/）
```

---

## 开工前：锚定点与派遣方式

### 锚定点（核心目标）—— **必须先问，不得猜**

开始任何 R 阶段之前，先与用户确认本工作的核心目标。用户没说就**反问**，
**不要默认成"提高性能"**。**项目主锚点未声明前不得开工。**

| 锚点 | 核心目标 | 成功判据 | 贡献类型 |
|---|---|---|---|
| **理论** | 提出并验证理论：定理 / 界 / 不可能性 / 统一框架 | 命题成立、证明无缺口、假设必要且紧 | Theory |
| **性能** | 提高某个任务 / 指标的绝对性能 | 公平比较下超过最强基线 | 方法 |
| **现象** | 发现并解释反直觉现象 | 解释唯一且具预测力 | 实证 |
| **基准** | 揭示现有评测掩盖的失败 | 基准暴露真实失败模式 | 实证 / 问题定义 |
| **可行性** | 把不可行 / 过贵的方法变可行 | 保持理论保证同时显著降本 | Concept & Feasibility |
| **负结果** | 证明某目标在一定条件下不可能 | 不可能性成立且给出可达松弛 | Negative Results |

**三层锚点体系**（层级不分清，规则会互相打架）：

| 层级 | 写在哪 | 字段 |
|---|---|---|
| **项目主锚点** | 根 `INDEX.md`，**只声明一次** | （项目级） |
| **路线锚点** | 路线 frontmatter | `core_goal` + `anchor_role` + `serves` + `serves_evidence` |
| **次锚点** | 路线 `README.md` 概要与 `state.json` | `core_goal_secondary`（**不进 `core_goal`**） |

- **`core_goal` 只记主锚点**（单值）；写 `"theory+feasibility"` 会被下游脚本判为非法。
- **`anchor_role`** 取 `primary` / `supporting` / `orthogonal`：
  `supporting` **必须可证伪**（说出一个会因它改变的下游决策 + 对主锚点判据的可测影响），
  只写"有理论价值"不算，答不出就标 `orthogonal`；
  **`orthogonal` 不得进入 R12、不得作为投稿主线。**
- **「必须服务」的强制力是「服务，否则降级 + 公开正交」，不是「服务，否则作废」。**
  被禁止的是**沉默**：既不服务、又不公开标注、还继续当主线推进。
- **只有用户能授权换方向。** agent 不得以"我发现主锚点不可达""另一个方向更有意思"
  为由自行换方向 / 换主锚点 / 开新路线 —— 只能**提请**（记 Warnings + 问用户）与
  **降级**（标 `orthogonal` 并公开标注）。换方向走[锚点变更单](#锚点变更单anchor-change-order)。
- **§1.5 的例外只认「项目主锚点」**：只有项目主锚点为 `theory` / `negative` 时，
  "第 4 步改为给出可检验推论"才对路线生效 —— **自称 `core_goal: theory` 的路线不豁免**。

锚点如何约束各 R 阶段：A 定**检索边界**、B 定**推导与筛选**、C 定**贡献类型与实验**、
D 定**叙事资格与 preset**（先做 **Anchor Eligibility Test**，见 claim-first-policy §6；
再按 `(O,T,R)` + eligible anchor 选 preset）、E 定**评审侧重**。

### 锚点变更单（Anchor Change Order）

对**项目主锚点**的变更记在根 `INDEX.md`，对**路线锚点**的变更记在该路线 `README.md`。
append-only。字段：日期 / 旧方向 → 新方向 / 类型（**增补** / **替换**）/ 依据 / 受影响产物。

**两条硬约束：**
1. **`类型: 替换` 而没有「受影响产物」清单 = 变更单无效。**
2. **`替换` 的依据必须是「用户显式指令原话」** —— 证据只能作为**提请**材料，
   **不能**作为变更依据。

### 派遣方式：Team 优先询问

**派发子代理前先判断环境是否具备 Team 能力**（可创建持久、可被寻址的 teammate，
如 Agent Teams）：

| # | 情形 | 处理 |
|---|---|---|
| 1 | **具备** Team 能力 | **必须先询问用户是否使用 Team**，不得自行决定。用户要求用 → 用 Team；不要或未表态 → 默认子代理 |
| 2 | **不具备**，用户也没提 | 用默认子代理，无需询问 |
| 3 | 用户**显式要求 Team** 但环境不具备 | **回退到默认子代理**，并**显式告知"当前环境无 Team 能力，已回退"** |

- **不得静默降级**；**不得假装使用了 Team**；**不得因"更高级"就默认启用**。
- **方式不改变标准：** 角色库、派遣矩阵、评分维度、交叉质询与**聚合规则**完全一致
  （R12 = 硬门禁 `G1—G5` + 六维排序；R7 / R10 / R13 = 归一化后逐维中位数 + 一票否决）
  （见 [roles.md](references/roles.md) §4.1）。
- 用 Team 时必须守**写作用域**：并行写者写互不重叠的文件；写冲突按
  "重新读取后再提交"处理。

---

## R 阶段总览（R0—R14）

| R 阶段 | 名称 | 作用 | 读 state | 写 state |
|---|---|---|---|---|
| **R0** | `research-contract` | 目标 / 约束 / 资源 / **provisional anchor** | — | `contract` |
| **R1** | `research-state` | **常驻**：维护八类一等对象 | 全部 | 全部 |
| **R2—R6** | `discovery` | 领域测绘 → 双轨发现 → 隔离种群 → 共演化检索 → 进化 | `literature` / `assumptions` / `failures` | `hypotheses` / `literature` |
| **R7—R8** | `assurance & contract` | 六攻击面审核 + 硬门禁 `G1—G5`；每个 central claim 一张证据契约 | `claims` / `evidence` | `assurance` / `claims.contract` |
| **R9—R11** | `experiment loop` | 实验树 + EIG 选实验 + **修复门** + 状态回写 | `uncertainties` / `experiments` | `experiments` / `repairs` / `uncertainties` |
| **R12—R14** | `narrative & decision` | 叙事（state 的视图）→ artifact 审计 → `continue` / `pivot` / `archive` / `submit` | `claims` / `evidence` | `narrative_view` / `reviews` / `decision` |

### 双循环各管什么

> **等价旧口号：** R3 决定"做不做"，R8 决定"做什么"，R12 决定"怎么讲"，R7 + R10 决定"做得对不对"。

| 维度 | R3—R6（idea 级） | R7 / R10 / R13（方案级） |
|---|---|---|
| 对象 | 一句话级 idea / 技术方向 | 成型的 proposal + 实验计划 |
| 可行性 | 概念可行性：路线是否成立 | 工程可行性：具体做法能否跑通、变量是否可控 |
| 正确性 | 前提是否自洽 | 方法正确性：推导/实现/指标/统计是否成立 |
| 创新性 | 方向是否已被覆盖、是否非平凡 | 方案是否**实质复现**已有工作 |
| 复现性 | 不涉及（不派 S-Repro） | 必查（S-Repro + 防复现六项检查） |
| 深度 | 快筛：双判定 + 致命反驳 | 深审：六攻击面 + 交叉质询 + 逐维中位数 |

**R7 / R10 / R13：** 结论卡片**必须**给出复现风险等级；**复现风险 = 高时总体判定不得为"高"**；
**R7 / R10 / R13 下 S-Devil 归一化后的新颖性稳健度 ≤ 2 时同样不得为"高"**（除非走「带条件的推荐」）。
**E 不是链条终点，而是反馈环**（可回流 C 或 B）：触发点为 ① C 产出后首次复核；
② **实验完成、有实测结果后**（防复现检查必须重做）；③ 投稿被拒 / 改投时。

### R12：claim-first 叙事（本 Skill 的差异化能力）

同一 State 的 claim、证据和边界可能因表达顺序被误读。**叙事层不得凌驾于证据之上**，
R12 的哲学是 **claim-first, evidence-constrained, narrative-last**：

> 找到**在现有证据下最强但不过度**的科学主张，再找最短的故事让审稿人正确理解它。
> `Narrative quality = Claim strength × Evidence alignment × Reviewer comprehensibility`

流程（D0—D9）：

1. **D0 证据台账** → **D1 Claim Graph**（`C0—C5`；每个 `Ci` 必须 `Ci ← Ej` 或标 `[待补]`）；
   **D2 科学分类** `(O, T, R)`；**D3 Anchor Eligibility** —— 作者的目标 anchor 是**先验偏好**，
   不是决定；与证据冲突时**必须显式告知**。
2. **D4a 科学叙事实现**：从[十套叙事 preset](references/narrative-patterns.md) 生成
   **2—4 套真正不同的 claim hierarchy**（**不是**同一主张的四种措辞），每套填满
   **六槽位 `S1—S6`**。跨域类必须做 **anti-application stress test**，迁移合法性按
   **`L1/L2/L3`** 分级 —— **不再要求人人都有 theorem**。
   然后逐套 freeze，进入 **D4b 等价表达 → D4c 正文等价门禁 → D4d 盲恢复与配对敏感性**。
   四个固定 profile 仅改变 evidence framing / contribution stance。
   完整说明见 [equivalence policy](references/rhetoric-equivalence-policy.md) 和
   [runnable example](examples/narrative-realization/README.md)。
3. **D5 攻击面审核**：六个**攻击面审稿人**（R-Novelty / R-Causal / R-Experimental /
   R-Theory / R-Generalization / R-Utility）**全部派遣、不得裁减**；**S-Lit 恒派**
   （L3 穷尽 + 负检索记录）；**S-Devil 不打分**（只出致命弱点清单 + 最简解释反例）。
4. **R12 / R13 的 venue calibration**（按 contribution type 校准会议适配，**不是** venue 直接选 preset）
   → **D7 硬门禁 `G1—G5`**（任一 `fail` ⇒ `not_submission_ready`，且**不参与排序**）
   → **D8 六维排序**（Significance / Originality / Soundness margin / Explanatory depth /
   Generality / Narrative compression）→ **D9 输出**（含**缺失证据清单与最小必要实验 / 定理**）。
5. **叙事包装 = 重新定位，不是夸大**：只改参照系，不改事实；每句声称都要能在
   方案里找到证据（`Ci ← Ej`）。

表达层优化 claim/evidence/实际 prior delta/boundary 的恢复准确率，不优化 reviewer overall score。
每套表达都冻结科学语义并保留相同前部 limitation 面板。恢复失败不推荐，缺数据标 INCOMPLETE。
轻微等价措辞引发大幅恢复变化时标 RHETORICALLY_FRAGILE，原 G1–G5 和六维比较仍有效。

---

## 全局硬约束（摘要，完整见 [SKILL.md §1](SKILL.md)）

### 1. 文献检索：先尝试 web search，再本地与多源

先按 [literature-policy.md §1.1](references/literature-policy.md) 尝试 web search，核验发现的原始页面。
再查本地与多源。工具不可用时记录并继续；明确离线时跳过。网页发现不能替代多源核验。
凡触发下列任一条件，必须查**全部启用源**并扩大范围：

| # | 触发条件 | 最低等级 |
|---|---|---|
| T1 | **创新性声明**（"首次提出 / 没人做过 / 首个 / 该方向空白"） | **L3 穷尽** |
| T2 | **理论不清**（证不出来、假设无法验证、收敛性说不清） | L2 强化 |
| T3 | **可行性不确定** | L2 强化 |
| T4 | 新颖性判定（`phase-r12` §D5.3、`phase-r7` §R7.3.2） | **L3 穷尽**（**例外：R3—R6 的 §R3.7 概念级快筛 = L2**） |
| T5 | 本地命中不足（< 5 条） | L2 强化 |
| T6 | 用户要求"尽可能多 / 彻底查" | **L3 穷尽** |
| T7 | "现有工作尚未……"式论断 | L2 强化 |
| T8 | 方法瓶颈：已观察到性能平台、候选反复失败，或诊断不再改变方法决定且缺少新干预 | L2 强化 |

- **尽职调查等级：** L1 快速 / L2 强化（≥4 检索式）/ L3 穷尽（≥8 检索式，含否定式与负结果）。
- **饱和判据：** 连续两轮扩大检索零新增、或达上限、或达标且新增趋零。
  **未达饱和就停止属于违规。**
- **禁止推断：** 本地未命中 ≠ 不存在；arxiv 未见 ≠ 无人研究过；429 中断 ≠ 检索完整。
- **创新性声明门禁：** 完成 L3 + S-Lit 核实 + 负检索记录，三项缺一只能写
  **"据本次检索未见"**，不得写"首次提出"。
- **卡点第一动作是检索：** 理论证不出、不确定能不能做时，先查该问题本身、相邻领域
  的处理方式、以及**负结果文献**。

**代理环境识别：** 发起 arxiv 请求前先解析 `arxiv.org` / `export.arxiv.org`。
**若解析到本地 IP**（回环 / 私有网段 / 链路本地 / `0.0.0.0`，例如 Clash 的
`198.18.x.x` fake-IP），说明**可能存在代理环境**——DNS 已被 hosts 或本地代理接管。
此时：① 报告中单列「代理环境提示」并写明**具体 IP**；② **不得**据此判定
"在线源不可用"或"无人在研究"；③ 代理链路上的 429 **未必**是官方限流；
④ 用于支撑创新性声明时记入 `STATUS.md` 的 Critical uncertainties。**只告警，不阻断。**

### 2. 顶会标准锚定

创新性判定必须引用 CVPR / ICML / NeurIPS / MICCAI 的具体标准；贡献必须标注类型；
"首次提出"必须经 S-Lit 核实。R7 / R10 / R13 另有**防复现六项检查**与复现风险等级。
**证据等级与措辞统一见 [evidence-policy.md](references/evidence-policy.md)**
（已核实 / 部分核实 / 据本次检索未见 / 待核实 / 待补证明），各 R 阶段 不再各自定义。

**venue calibration 表的两角度 + 会议特性（仅 R12 / R13）：** venue calibration 的四个会议视角（原 R-CVPR / R-ICML / R-NeurIPS /
R-MICCAI）的每一次评价都必须给出 **① 理论角度**（命题 / 假设 / 推导是否成立、形式化
是否完整）+ **② 应用角度**（能否落地、可验证性、影响面）+ **③ 会议特性判定**
（按本会议首要标准，引用具体条目）。**只写一个角度 = 评审不合格。** R-MICCAI 对无临床
属性的工作标 **"不适用"**，其两个条件性维度**不进中位数向量**。见
[roles.md §1.0](references/roles.md) 与 [venue-standards.md §0](references/venue-standards.md)。

**推进纪律：理论建模是手段，不是终点。** **禁止在「证明性工作」上停留与反复。**
每个 idea / 方案都要走通**四步链**：

| 步 | 内容 |
|---|---|
| 1 | **数学理论建模** —— 形式化变量、假设、目标、结构性质 |
| 2 | **寻找证据** —— 文献证据 + 实验证据 |
| 3 | **结合机器学习方法提出方法**，并标注**方法来源** |
| 4 | **改进最终任务性能** —— 可测指标 + 公平比较 |

- **明令禁止：** 反复打磨证明；把"证不出来"当阻塞；贡献只说"我们证明了 X"却没有方法与
  可验证性能；在证明性工作上无限迭代。
- **证明预算：** 证明类工作设显式预算；用尽仍未完成 → 标 **"待补证明 · 待核实"**，
  转入第 2—4 步，**不得阻塞链路**。（底线不变：不得声称"已证明"却未证明。）
- **唯一例外：** 主锚点为**理论 / 负结果**时，第 4 步改为"给出**可被实验检验的推论**或
  **可达到的松弛**"，但第 2、3 步仍必须走通。

**方法来源必须显式标注：`原创` / `部分原创` / `迁移`。**

| 标注 | 含义 | 判据 |
|---|---|---|
| **原创** | 核心机制由本工作提出 | 指出最接近先前工作 + **机制层面**的差异 |
| **部分原创** | 部分来自既有工作，但有关键改造 / 新组合 / 新性质 | 写明**改了哪一条** + 带来的新性质 |
| **迁移** | 把其他领域 / 任务的既有方法搬来，机制不变 | 写明**来源领域 + 迁移合法性依据**；**迁移本身不算增量** |

**不得留空、不得模糊**（"受 X 启发"不算标注）；**把「迁移」写成「原创」属于夸大**；
标为「迁移」的必须证明**迁移本身带来新性质**，否则 R7 / R10 / R13 按**复现风险高**处理。
见 [venue-standards.md §5.1](references/venue-standards.md)。

### 3. 输出规范

结构化报告；引用给 `[作者, 会议/年份]`；无法确认标注"待核实"，**不得臆造**；
"没做到"必须关联具体未建立的结构性质或未满足的理论条件。

**形式：受控中文**（[writing-policy.md](references/writing-policy.md)）。这份政策管三个表面：
**落到文档**（`routes/<R>/docs/*.md`）、**返回对话**（每次阶段的报告正文）、**子代理意见**。
它只管形式，不管内容。

| 抓手 | 做法 |
|---|---|
| 一句一动作 | 不用分号连接动作，拆成两句 |
| 句长 | 指令句 ≤ 25 字，说明句 ≤ 40 字 |
| 去虚动词 | 「进行分析」→「分析」；「进行了实验验证」→「验证了」 |
| 去套话 | 删掉「需要注意的是」「在一定程度上」 |
| 去营销形容词 | 「无缝」「显著提升」删掉，或换成测量值 |
| 术语一致 | 一份文档内一个概念只用一个写法 |
| 段与列表 | 一段一主题（≤ 6 句）；≥ 3 项用列表或表格 |
| 返回对话 | **第一段就是结论** |

**三档：**

| 档 | 什么时候用 | 执行到哪一步 |
|---|---|---|
| **asd-ste100** | **用户显式声明时**（可选最强档） | 句长一律 ≤ 25 字；打开同义轮换；建议类升硬 |
| **Strict** | 实验流程计划书的步骤、命令、路径 | 全部规则，含硬性句长上限与「一词一义」 |
| **中文-顺** | 默认：其余正文（词汇规则只作方向） | 结构规则全部执行 |

**机械闸门：** 落盘**之前**跑 `python scripts/ste_lint_zh.py --disable synonym-rotation <文件>`，
**硬违规须为 0**；asd-ste100 档改跑 `python scripts/ste_lint_zh.py --max-chars 25 <文件>`，
且建议类报告需**人工逐条处置**（脚本不会因此失败）。**Agent 不得自行升档。**

> ⚠️ **情态是内容。** 不得为了压句长，把「实验**可能**受批次效应影响」改成「实验受批次效应影响」
> ——那不是简化，是换了个结论。句长上限最容易引诱人删掉的正是这些词。

> ⚠️ **不要拿 linter 扫本 Skill 自己的规范文本**（`SKILL.md` / `references/*.md`）。
> 范围只有上面三个表面。

---

## 项目组织与文档落盘

```
<项目根目录>/
├── AGENTS.md              # 共享契约；存在则优先遵循
├── README.md              # ★ 根级：项目总览
├── INDEX.md               # ★ 根级：路线总表投影（Route | Goal | Status | Thesis | Blocker）
├── docs/                  # ★ 跨路线共享区（不放路线文档）
│   ├── refs/              # ★ 必需：参考文献库（= 本地文献库根目录）
│   │   ├── papers/        # {paper_id}.pdf（不进版本库）+ .json sidecar + 可选 .md
│   │   ├── cache/<source>/ # 查询缓存（按源分目录）
│   │   └── index.json     # ★ 必需：PDF 索引，进版本库
│   ├── decisions/         # ★ 项目级重大决策 DEC<NNN>-<slug>.md
│   ├── notes/             # 可选：跨路线共享笔记（按 AGENTS.md）
│   └── latex/             # 可选：跨路线共享 LaTeX（按 AGENTS.md）
├── routes/A/
│   ├── README.md          # ★ 路线身份证：这条路线是什么（低频变更）
│   ├── STATUS.md          # ★ 当前状态人类摘要（research-state.json 的投影）
│   ├── INDEX.md           # ★ 资产目录 + 时间线（不再承载当前状态）
│   ├── docs/              # ★ 本路线文档（扁平；不建子目录）
│   │   ├── A000-anchor.md # 冻结契约：路线锚点 + anchor_role + serves
│   │   ├── A001-field-map.md
│   │   ├── A002-discovery.md  # 含 I1..In 与审核结论
│   │   ├── A003-proposal.md
│   │   ├── A004-experiment-plan.md
│   │   ├── A005-narrative.md          # R12：一次调用一份
│   │   └── A003-review-r01.md         # 审阅挂被审 ID，轮次零填充
│   └── （无 src/）        # route 不复制代码；差异用 configs/routes/A/ 表达
├── routes/B/
│   ├── README.md
│   ├── STATUS.md
│   ├── INDEX.md
│   └── docs/
├── src/                   # ★ canonical implementation（唯一）
├── experiments/A/<XID>/   # ★ 实验注册表：想做什么（pre-registration）
├── results/A/<XID>/       # ★ 观察到什么（observation）
├── shared/                # 跨路线公用代码/笔记
└── .research-idea-pipeline/routes/A/research-state.json  # 机器状态（不入 docs）
```

| 规则 | 说明 |
|---|---|
| 命名 | `routes/<R>/docs/<路线字母><NNN>-<slug>.md`；审阅为 `<ID>-review-r01.md`，接续 `-r02.md` |
| 存放 | **路线文档放 `routes/<R>/docs/`（扁平，不建子目录）**；**根 `docs/` 是跨路线共享区，只保证有 `refs/` 与 `decisions/`**，路线文档不得放这里 |
| slug 枚举 | **封闭**：`anchor` / `field-map` / `discovery` / `theory` / `evidence` / `proposal` / `experiment-plan` / `result-analysis` / `decision` / `narrative` / `review` |
| 派生文档 | **禁止自创 slug**。枚举外的派生物（`paper-outline` / `experiment-cards` / `math-consolidation` …）归到最接近的枚举，原义写 frontmatter 的 **`subtype`**，并在路线 INDEX 文档表加 **`subtype` 列** |
| 落盘三档 | **交付物** → `routes/<R>/docs/`；**中间产物**（子代理原始评审件、草稿） → `.research-idea-pipeline/routes/<R>/<被审ID>-r<NN>/`；**机器状态** → `.research-idea-pipeline/routes/<R>/research-state.json`。**正式 review 必须自带摘要**，原始件不得被当作结论引用 |
| 子编号 | `I<n>` idea、`N<k>` 叙事 preset、`K<n>` 贡献、`X<n>` 实验、`H<n>` 假设；引用写作 `<文档ID>/<子编号>` |
| ID | 按路线独立递增、永不复用；审阅记录不占新序号 |
| 锚点文档 | `<R>000-anchor.md`（`type: anchor`）是**冻结契约**，frontmatter 带 `anchor_version` + `anchor_hash`；改锚点走锚点变更单并升版本 |
| 文档 ID 前缀 | `A`/`B` 是**路线编号**，与 R 阶段无关；阶段记在 frontmatter |
| 三文件分工 | 路线 `README.md` 答"是什么"（很低频）；`STATUS.md` 答"现在怎样"（很高频，由 `render_status.py` 从 state 生成）；`INDEX.md` 答"有哪些材料"（中等） |
| INDEX.md | 只放**资产目录 + 时间线**（Key Documents / Experiments / Decisions / Reviews / Milestones / Recent Research Changes / Archive）；**不含当前状态** |
| STATUS.md | **当前状态**（Current thesis / findings / hypotheses / uncertainties / attacks / experiments / negative findings / next actions / decision）；**是 state 的投影，禁止手改** |
| 负结果 | 被证伪的假设**不得删除**，进 `STATUS.md` 的 Most important negative findings |
| XID | 每个正式实验一个唯一 `XID`，贯穿 `experiments` / `configs` / `results` / `logs` / `checkpoints` / state |
| 机器状态 | 进 `.research-idea-pipeline/routes/<R>/`，**不进 docs** |
| **PDF 索引** | **`docs/refs/` 下每个 PDF 必须在 `docs/refs/index.json` 有记录**；索引进版本库、PDF 不进 |

完整规范见 [references/project-layout.md](references/project-layout.md)（含八条 DI
invariant 与手工建骨架的检查清单）。骨架可参考
[templates/INDEX.md](templates/INDEX.md)（路线资产目录）、
[templates/STATUS.md](templates/STATUS.md)（路线当前状态）、
[templates/INDEX.root.md](templates/INDEX.root.md)（根级路线总表）与
[templates/README.route.md](templates/README.route.md)（路线身份证）。

---

## 命令行检索器

```bash
# 默认：本地 + 全部已实现源（arxiv / openalex / crossref）合并
python3 scripts/literature_search.py -q "diffusion model combinatorial optimization" --max 20

# 环境自检（建议先跑一次）—— 确认工作解释器与依赖
python3 scripts/literature_search.py --check-env

# 创新性声明：L3 穷尽 + 自动扩检 + 追加同义词/否定式检索式
python3 scripts/literature_search.py -q "discrete diffusion combinatorial optimization" \
    --level L3 --exhaustive \
    --also-query "score-based generative model discrete optimization" \
    --also-query "limits of diffusion model combinatorial optimization" \
    --mailto you@example.com --json

# 会议过滤（A3 第 ③ 级自动化；★ 只在 OpenAlex 上服务端生效）
python3 scripts/literature_search.py -q "..." --venue "Neural Information Processing Systems"

# 引文追溯（A3 第 ⑤ 级）
python3 scripts/literature_search.py -q "..." --cited-by "10.1109/TPAMI.2023.3261988"
python3 scripts/literature_search.py -q "..." --references "2209.04747"

# 离线：不查任何在线源（会打印规则违反提示；不得支撑创新性声明）
python3 scripts/literature_search.py -q "..." --local-only    # 或 --offline
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--query` / `-q` | 必填 | 检索关键词或研究问题（支持中文；`--check-env` 时可省） |
| `--max` / `-n` | `20` | **每个在线源每次查询**的条数上限；本地命中不受此限制 |
| `--limit` | 不截断 | 最终返回条数上限（截断时保留本地优先顺序，并报告截断量） |
| `--sources` | 全部 | 启用的源：`arxiv,openalex,crossref` 或 `all`。**少指定会打印覆盖警告** |
| `--venue` | 无 | 会议/期刊名 → OpenAlex 解析后过滤（**只在 OpenAlex 生效**） |
| `--cited-by` | 无 | 前向引文追溯（谁引用了它）。ID 可为 DOI / arXiv ID / OpenAlex ID |
| `--references` | 无 | 后向引文追溯（它引用了谁）。ID 同上 |
| `--mailto` | `$RESEARCH_MAILTO` | OpenAlex / CrossRef 的 polite pool 联系方式 |
| `--check-env` | 关 | 只做解释器/依赖自检并退出；不满足时退出码 `4` |
| `--no-reexec` | 关 | 禁止自动切换到合格解释器（默认会切换并打印 `[env]` 行） |
| `--from-year` / `--to-year` | 无 | 年份过滤（含端点；启用过滤时**年份未知的条目被排除**） |
| `--level {L1,L2,L3}` | 无 | 尽职调查等级，输出达成情况（饱和只对 L2/L3 是硬要求） |
| `--exhaustive` | 关 | 自动执行 A3 第 ②④ 级扩大检索直到饱和 |
| `--also-query` | 无 | 追加检索式（可重复）；A3 第 ① 级 |
| `--local-only` / `--offline` | 关 | **显式**不查任何在线源（违反默认规则；**不得用于支撑创新性声明**） |
| `--local-dir` | `./docs/refs` | 本地库；亦可用 `RESEARCH_LOCAL_LITERATURE` |
| `--cache-dir` | `<local-dir>/cache` | 缓存目录；亦可用 `RESEARCH_LIT_CACHE` |
| `--refresh` | 关 | 跳过缓存（仍查本地与在线源，可与 `--exhaustive` 同用） |
| `--no-cache` | 关 | 不读缓存（结果仍会写入缓存） |
| `--json` / `--quiet` | 关 | JSON 输出 / 静默 |

**退出码：**

| 码 | 含义 |
|---|---|
| `0` | 全部启用源成功 |
| `1` | 硬错误（参数、本地库不可读、渲染失败） |
| **`2`** | **存在降级** —— **任一**启用源 `unavailable` / `partial`；结果不完整，检索视为未饱和 |
| **`4`** | **环境不满足** —— 依赖缺失或找不到可用解释器（**依赖缺失 ≠ 源不可用 ≠ 没人做过**） |

**依赖：** `arxiv`（检索）与 `pypdf`（PDF 索引），**必须在同一个解释器里**。
脚本会自动发现工作解释器（已激活环境 → 项目 `.venv` → conda 各环境 → PATH）；
唯一命中则切换并打印 `[env]` 行，多个候选不猜，找不到则退出码 `4`。

**输出：** 文献列表（含 `sources`）+ **每源状态** + 检索过程记录 + 源日志（429 / 失败 /
代理）+ 缓存更新记录 + 范围扩大记录 + **逐检索式的负检索记录** +
**饱和判定与等级达成情况**。

---

## 参考文献库格式（`docs/refs/`）

**参考文献统一放项目根目录的 `docs/refs/`**，它同时就是检索脚本的本地文献库根目录
（脚本默认 `--local-dir ./docs/refs`）。

```
docs/refs/
├── index.json                 # ★ PDF 索引（强制，进版本库）
├── papers/{paper_id}.pdf      # PDF 原文（大文件，不进版本库）
├── papers/{paper_id}.json     # sidecar 元数据：title/authors/abstract/year/venue/url
├── papers/{paper_id}.md       # 可选：全文或笔记（参与全文匹配）
└── cache/{query_hash}.json    # 查询缓存（**按源分目录**：<source>/<hash>.json）
```

### ★ PDF 必须入索引

**`docs/refs/` 下的每一个 PDF，都要在 `docs/refs/index.json` 里有一条记录**，包含
`file` / `paper_id` / `title` / `authors` / `year` / `arxiv_id` / `doi` / `url` /
`abstract` / `keywords` / `pages` / `size_bytes` / `sha256` / `added_at` / `source` /
`metadata_from` / `needs_verification`。

**索引进版本库，PDF 不进** —— 别人 clone 到的是完整文献清单，不必下载几十 GB 原文。

```bash
python3 scripts/refs_index.py            # 扫描 ./docs/refs，写入 ./docs/refs/index.json
python3 scripts/refs_index.py --check    # 只校验；不一致时退出码 3
python3 scripts/refs_index.py --migrate  # 旧 schema → 当前 schema（保留旧字段）
```

| 元数据来源 | 说明 |
|---|---|
| `papers/{paper_id}.json`（sidecar） | 最准，检索脚本写入 |
| PDF 内嵌元数据 | `pypdf`；缺失时回退命令行 `pdfinfo` |
| **旧索引继承（`--migrate`）** | `metadata_from = "legacy"`；**同样不算已核实** |
| 文件名解析 | 兜底；此时 `needs_verification = true` |

**未入索引的 PDF 视为不存在**；新增/替换/删除 PDF 后**必须重建索引**。

**旧 schema 的迁移路径：** `--check` 报「索引缺少 pdfs 数组（schema 不符）」时，
索引是旧版形状（平铺列表 / 以文件名为键的字典）。**直接重建会丢掉旧条目里已有的
title / venue / year**，所以要用 `--migrate`（保留旧字段 + 写 `migrated_from`），
迁移后再 `--check` 确认。

**`needs_verification` 的后果（不只是个标记）：**
- 该条目**不得**用于支撑「首次提出 / 未见前作 / 复现风险低」类声明；
- **其数量必须计入根 `INDEX.md` 的全局 Warnings**；
- **超过 5** 触发补元数据 TODO（写 sidecar 后重建索引），**不得长期累积**。

完整字段约定见 [references/literature-policy.md](references/literature-policy.md) §7.1
与 [references/evidence-policy.md](references/evidence-policy.md) §2 规则 7。

---

## 状态传递

每个 R 阶段 输出附加 `state.json` 片段（模板见
[templates/research-state.template.json](templates/research-state.template.json)，顶层直接是八类一等对象数组 + `contract`）。
机器状态写入 `.research-idea-pipeline/routes/<R>/research-state.json`，
人类可读产出写入**所在路线的 `routes/<R>/docs/`**；
当前状态由 `research-state.json` 投影成 `routes/<R>/STATUS.md`（**禁止手改**）。

**接续规则以权威读写表为准**（[research-state-policy.md](references/research-state-policy.md) §5）。
该表在**三处逐字一致**：`SKILL.md` §0、policy §5、以及各 `phase-*.md` 的「读 / 写 World Model」表
（由 `scripts/test_state_check.py` 的 `TestTableIntegrity` 与比较器机械核对）。

**四条不可越界的铁律：**

1. **写回是收工条件** —— 任何阶段不得在未写回 state 的情况下宣告完成。
2. **只写本阶段那一行** —— 表中未列出的字段不得顺手改；跨阶段修改必须走 `repairs[].state_delta`。
3. **状态迁移只能取枚举值** —— 不得自造 `mostly-supported` 这类中间态。
4. **认识论权限边界** —— **`R14` 能杀研究分支，不能杀真理主张**：`claims[].status`
   只能经 `R8`（证据驱动的单向升级）或 `R10`（`state_delta`）改变（`SKILL.md` §1.7，由 `V22` 机械强制）。

---

## 检索脚本的四点工程修正

检索链路有四处在本环境会失效，已在实现中修正并记录在
[literature-policy.md §5.2 / §5.3](references/literature-policy.md)：

1. **`arxiv.HTTPError` 并非 arxiv 包稳定导出的异常。** 实际 429 多为
   `urllib.error.HTTPError`（`.code`）或带 `.response.status_code` 的异常。
   脚本兼容捕获 `status` / `code` / `status_code` 及异常文本中的 `429`。
2. **`hash(query)` 跨进程不稳定**（受 `PYTHONHASHSEED` 影响），不能作缓存文件名。
   改用 `hashlib.md5(...)[:16]`。
3. **缓存键必须含检索参数。** 只按 query 建键会导致"用更大的 `--max` 复跑却命中旧的
   小结果集"，直接损害 L3 与扩检索质量。缓存键 = `md5(query|max|from_year|to_year)`。
4. **"本地命中即返回"被取消。** 本地检索改为起点而非终点；默认取本地 + 多源 的
   并集，只有显式 `--local-only` 才跳过 arxiv（并打印规则违反提示）。

---

## 维护本 Skill 时

改动任何**规则 / 命名 / 枚举 / 计数 / 路径**之前，先读
[SKILL.md §8 规则变更自检清单](SKILL.md)。

> 本仓库的实际漂移记录显示：改了规则后**漏掉的从来不是规则本身**，而是
> **设计依据段、速查汇总表、示例与模板、语义字段与规则的一致性**这**四类**
> "看起来不像规则"的位置。

> **A4（语义字段）的现实教训：** 规则说"锚点必须落盘"，但 frontmatter 没有
> `anchor_role` / `serves` 的槽位；强制"锚点文档"，但类型枚举里没有 `anchor`；
> 允许"主+次锚点"，但 `core_goal` 只有一个槽。**规则有、载体无** —— 只查计数与
> 链接是查不出来的。每条新规则都要问：①字段表里有槽位吗？②枚举里有值吗？

---

## 安装

走仓库的 `npx skills` 流程（仓库根 `README.md` 有完整的安装与维护说明）：

```bash
npx skills add Zolento/my-research-skills -g -s research-idea-pipeline -y
```

本机开发时也可直接装开发版：

```bash
rsync -a --delete --exclude '__pycache__' \
  research-idea-pipeline/ ~/.agents/skills/research-idea-pipeline/
```

> `~/.claude/skills/research-idea-pipeline` 通常是指向 `~/.agents/skills/` 的软链 —— 装一处即两处生效。

**调用**：指定 `phase=R0..R14` 即可；**首次进入已有项目**走 Bootstrap（`SKILL.md` §0.3，只观察不推进）；
日常用四个入口 `start-project` / `continue-research` / `explore` / `audit`
（契约见 [references/invocation-prompts.md](references/invocation-prompts.md)）。
需要最强受控档时加 `writing=asd-ste100`。
