# Subagent Context（子 Agent 的最小任务契约）

> **唯一权威。** 每个科研子 Agent 应当收到什么上下文、被授予什么权限、输出什么形状，
> 全部定义在本文件。`SKILL.md` §3 只保留派遣原则与不可绕过的三条边界。
>
> **加载条件：** 派遣子 Agent 前加载本文件对应的角色契约（按角色切片，不整份加载）。
> 主 Agent 自己执行时不加载。
>
> 运行时：`scripts/subagent_context.py`（`roles` / `build` / `check`）。

## 1. 为什么子 Agent 需要裁剪

主 Agent 的上下文不是子 Agent 的任务上下文。把 `research-state.json` 全文、R0—R14 全部
阶段说明和主 Agent 的历史对话一并塞给子 Agent，会带来三个具体损失：

1. **注意力稀释。** 子 Agent 的任务是「检索这 12 篇的近邻并判定结构差异」，
   它不需要知道另一条路线为什么 pivot。
2. **权限幻觉。** 拿到完整 state 的子 Agent 容易顺手改 claim 状态。
   上下文越完整，越像「我也有权写」。
3. **证据污染。** 子 Agent 看到主 Agent 的结论，会倾向于复述结论而不是独立判定。

**裁剪的是上下文，不是责任。** 子 Agent 仍然必须满足角色库里对该角色的全部要求
（见 [roles.md](roles.md)），只是不需要读别的角色的要求。

## 2. 三条不可越过的边界

| # | 边界 | 含义 |
|---|---|---|
| 1 | **不得绕过已有状态写入权限** | 子 Agent 的写权限是 `state_check` / `render_status` / 门禁脚本所允许的子集。上下文裁剪不得扩张它 |
| 2 | **`Context Packet` 不是第二个授权来源** | Packet 描述「当前授权是什么」，不产生授权。授权只有用户能给 |
| 3 | **子 Agent 自评不得升级为科学证据** | 主 Agent 汇总，但汇总不是认证。子 Agent 的分数、`supported` 判断、`novel` 判断都只是输入 |

## 3. 角色契约（按角色切片加载）

每个角色只加载自己那一行对应的契约。字段含义：

- `receives` —— 必须交给子 Agent 的上下文项；
- `never` —— **不得**交给它的内容；
- `may_write` —— 允许写的落盘位置（空 = 只读）；
- `exec` —— 是否允许执行实验；
- `approval` —— 是否需要上级显式批准。

### 3.1 Literature Agent（S-Lit / 检索）

| 项 | 内容 |
|---|---|
| 目的 | 检索、核验近邻工作、判定结构差异与新颖性边界 |
| `receives` | 研究问题原话；本次任务的一句话指令；检索范围（源、时间窗、语言）；要比对的论文清单；评价规则（`literature-policy` 的等级与措辞）；来源与引用要求；输出 Schema；**当前权限（只读）** |
| `never` | 完整 `research-state.json`；主 Agent 的结论与偏好；其他角色的评审意见；未完成实验的结果 |
| `may_write` | 无（只读）。缓存与 trace 写到 `<route>/docs/refs/cache/` 与子代理原始件目录 |
| `exec` | 否 |
| `approval` | 不需要（只读动作），但**写真实 Zotero 库需要用户明确请求** |
| 输出 | 每条结果带 `source`、DOI/arXiv id、检索式、命中位置；未核实的标 `待核实` |

### 3.2 Theory Agent（S-Theory）

| 项 | 内容 |
|---|---|
| 目的 | 判定机制假设是否成立，找反例与不可能性，给出边界条件 |
| `receives` | 机制假设（`statement` + `assumptions`）；涉及的数学对象与符号约定；前提与冻结条件；现有理论证据（只给与本假设相关的 evidence 切片）；待证明或待否证命题；输出契约 |
| `never` | 完整补充实验日志；其他候选的完整档案；主 Agent 的方向偏好 |
| `may_write` | 无（只读）。草稿写到子代理原始件目录 |
| `exec` | 否（纯理论不需要 GPU） |
| `approval` | 不需要 |
| 输出 | 命题形式化；证明或反例；失败在哪一步；需要的额外假设；**`待补证明 · 待核实`** 必须显式标注 |

### 3.3 Experiment Agent（A-Experimenter）

| 项 | 内容 |
|---|---|
| 目的 | 执行**已冻结**的实验并如实回报 |
| `receives` | 冻结的实验 manifest（内容绑定）；具体实验动作；资源限制（GPU/时长/存储）；**不允许修改的配置清单**；验收指标与停止条件；输出路径与证据要求 |
| `never` | 未冻结的候选方案；主 Agent 对结果的期望；其他实验 arm 的结果（避免选择性调参） |
| `may_write` | 只写 `experiments/` 与 `results/` 下自己的产物。**不写 `research-state.json`** |
| `exec` | 是，但**只在 manifest 授权范围内** |
| `approval` | 改变预算、延长冻结期、动新 GPU 需要用户批准 |
| 输出 | `execution_record`（含 manifest digest、实际命令、arm/control 真实取值、退出状态）；失败要区分实现错误与无效执行 |

### 3.4 Assurance Agent（六个攻击面 / S-Devil / S-Repro / S-Integrity）

| 项 | 内容 |
|---|---|
| 目的 | 攻击一个已成型方案，给出可判定的 Kill Condition |
| `receives` | 被审对象（claim / 方案 / artifact 路径）；该攻击面的定义（只给自己的那一面）；相关 evidence 与 assumptions 切片；已存在的反例与 failure memory；五元组输出契约 |
| `never` | 其他攻击面的评审意见（**独立判定**必须先于交叉质询）；主 Agent 的倾向；S-Devil 的分数（它不打分） |
| `may_write` | 无（只读）。原始评审件写子代理原始件目录 |
| `exec` | 否 |
| `approval` | 不需要 |
| 输出 | `(Attack, Target Claim, Alternative, Discriminating Test, Kill Condition)`；**Kill Condition 必须可判定**；只有分数没有 Kill Condition 的评审不合格 |

### 3.5 Discovery Agent（R3 的 P1—P6 隔离算子）

| 项 | 内容 |
|---|---|
| 目的 | 在**隔离上下文**里产生候选，保持多样性 |
| `receives` | 研究锚点与约束；分配给它的算子（**只给它这一个**）；可用的文献与 failure memory 切片；输出 Schema（含 `niche` / `operator` / `parents` / `generation`） |
| `never` | 其他算子产出的候选（隔离的意义就在这里）；QD archive 全文；主 Agent 的排序 |
| `may_write` | 无。候选由执行者统一写入 |
| `exec` | 否 |
| `approval` | 不需要 |
| 输出 | 结构化候选 + 一句话 `falsifier` + `nearest_prior` |

## 4. 不变量：裁剪不得造成权限扩张

`scripts/subagent_context.py check` 机械校验以下五条：

1. 每个角色的 `permits` 必须是**父级权限的子集**（子集关系按能力枚举判定）；
2. `may_write_canonical_state` 只允许出现在主 Agent 或显式被用户授权的角色上；
3. 任何角色都**不得**获得 `modify_anchor`（改主锚点只有用户能做）；
4. `exec` 为真的角色必须同时给出 `manifest_required: true` 与 `approval_required` 字段；
5. `never` 列表必须非空 —— 一个「什么都给它」的角色契约等于没有裁剪。

## 5. 证据切片的要求

不同子 Agent 只获得自己需要的证据切片，但**必须保留可追溯性**：

- 每条切片带原始 `evidence_id` / `experiment_id` / `paper_id`；
- 切片是**引用**，不是重写。子 Agent 不得修改切片内容；
- 主 Agent 汇总时，任何被引用的结论都要能回溯到切片与原始对象；
- 子 Agent 的 `supported` / `novel` 判断**不进入** canonical state 的 `status` 字段，
  只能作为 R7 / R10 的输入。


## 6. 派遣方式与角色库（从 L0 迁入）

> **派遣前先定「派遣方式」（§3.1）：Team 还是默认子代理。** 方式未定不得开始派遣。

所有 R 阶段共享同一角色库。按阶段需派遣的子代理如下（角色定义不重复，见
[references/roles.md](../references/roles.md)）：

| R 阶段 | 派遣子代理 |
|---|---|
| **R2 / R5** | 无（执行者直接完成检索与归纳） |
| **R3—R6** | **候选由隔离 Exploration Agents 按 island 生成**：`P1`—`P6` 各一个独立上下文（**互不可见**），另加 `local`；执行者只做编排、隔离、路由、汇总与写 state，**不得亲自补写候选**。generation 完成后才由 `S-Lit` + `R-Novelty` + `R-Causal` + `S-Feas` 做 concept 级 hygiene 快筛，`S-Devil` 出致命反驳。**不派 venue 角色**；**不派 S-Repro**。详见 [phase-r3-r6-discovery.md](../references/phase-r3-r6-discovery.md) §R3.3—§R3.6 |
| **R8** | 证据契约与 `proposal.md` 由 `A-Author` / `A-Experimenter` 落盘；核实由 `R-Theory` / `S-Theory` / `S-Feas`（常规）+ **R7 的 `S-Lit` 结论（不重做 L3）**；`S-Nov` 按需。**venue 角色不派**，**不派 `S-Repro`**，**不派六个攻击面审稿人** |
| **R12** | **攻击面审核（六人全部派遣、不得裁减）**：R-Novelty、R-Causal、R-Experimental、R-Theory、R-Generalization、R-Utility；**S-Lit 恒派**（L3 穷尽 + 负检索记录）；**S-Devil 不打分**（只出致命弱点清单 + 最简解释反例，喂 `G3`/`G4`）；按需 **S-Nov / S-Feas / S-Repro**。会议审稿人**不派**，只在 **R12 / R13 的 venue calibration** 中以校准表出现 |
| **R7 / R10 / R13** | **R7 按八个攻击面派遣算子**：`S-Lit`（最近工作碰撞）+ `R-Novelty`、`R-Causal`（更简单解释）、`R-Experimental`（识别 + 统计两读数）、`R-Theory`、`R-Generalization`（scope）、`S-Repro`（实现与可复现）、**`S-Integrity`（完整性，R13 生效）**；`S-Feas` 按需。**venue 角色**（见 [roles.md](../references/roles.md) §1）**不参与科学发现**，只在 R12/R13 的校准表里出现。 |

**职责边界：** 不派遣 S-Repro 到 R3—R6（idea 阶段无代码可复现）；**§R3.7 的审核是
概念级快筛**，不要与 R7 / R10 / R13 的方案级深审重复。详见
[phase-r3-r6-discovery.md](../references/phase-r3-r6-discovery.md) §R3—R6.0 与
[phase-r7-r10-r13-assurance-repair-review.md](../references/phase-r7-r10-r13-assurance-repair-review.md) §R7.0。

**派遣原则：** 子代理必须**独立产出**，不得互相抄袭结论；汇总时去重并保留来源标注。
**R12 与 R7 / R10 / R13 都要求交叉质询**：每个子代理对其余子代理的评分提出至少一条质疑或补充。

**聚合规则分两套**（权威定义见 [scoring-policy.md](../references/scoring-policy.md)）：

- **R12：先过硬门禁 `G1—G5`**（任一 `fail` ⇒ `not_submission_ready`，**不参与排序**），
  再按**六个同向维度**排序，**不做极性归一化**（D 已无反向维度）。
- **R7 / R10 / R13：仍按极性归一化后的逐维度中位数聚合** —— 含 S-Devil 的**反向维度**，
  定义见 [scoring-policy.md](../references/scoring-policy.md) §2 与 §5（本文件不复述公式，
  避免同一规则两份写法）。

> ⚠️ **不得用「6 个子代理都同意」声称 reviewer consensus** —— 六个 reviewer **不是独立
> 样本**（同一基础模型换 prompt，`corr ≫ 0`）。见 [scoring-policy.md](../references/scoring-policy.md) §3。

### 6.1 派遣方式：Team 优先询问（强制）

**每次准备派发子代理前，先判断当前环境是否具备 Team 能力**（能创建持久、可被寻址的
teammate，例如 Agent Teams）。然后按三种情形处理：

| # | 情形 | 处理 |
|---|---|---|
| 1 | **环境具备 Team 能力** | **必须先询问用户是否使用 Team**，不得自行决定。用户要求用 → **用 Team**；用户不要或未表态 → 用默认子代理 |
| 2 | **环境不具备 Team 能力，用户也没提** | 用**默认子代理**，无需询问 |
| 3 | **用户显式要求用 Team，但环境不具备该能力** | **回退到默认子代理**，并**明确告知用户"当前环境无 Team 能力，已回退"** |

**硬约束：**

- **不得静默降级：** 回退必须显式说出来，不能让用户以为用了 Team。
- **不得假装用了 Team：** 没有该能力时，输出中不得出现"已派发 teammate"之类表述。
- **不得因为"Team 更高级"就默认启用：** Team 有持久化与并发写入成本，必须由用户选择。
- **方式不改变标准：** 无论用 Team 还是默认子代理，**角色库、派遣矩阵、评分维度、
  交叉质询与聚合规则完全一致**（R12 = 硬门禁 `G1—G5` + 六维排序；R7 / R10 / R13 = 归一化后
  逐维中位数 + 一票否决；见 [references/roles.md](../references/roles.md)）。
  Team 只改变执行方式，**不改变审查标准**。
- **用 Team 时必须守写作用域：** 并行写者写**互不重叠**的文件；写冲突按
  "重新读取后再提交"处理（见 [project-layout.md](../references/project-layout.md) §5）。

> 详见 [references/roles.md](../references/roles.md) §4。

---
