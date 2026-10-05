# F001-method-overview — Figure Draft（worked example, code-grounded）

> 本文件是本 skill 的**旗舰示例**：输入是一个真实的小型源码库
> [`examples/demo-source/`](demo-source/)，输出是十段式 draft。
> 契约见 [references/output-contract.md](../references/output-contract.md)。

**参数：**

```yaml
FIGURE_TYPE: method-overview
DETAIL_LEVEL: medium
NUM_DRAFTS: 3
FOCUS: 突出 solver 与 flow prior 的交替结构，以及 target adaptation 只更新少量参数这一点
TARGET_PAPER: 未给出（默认双栏会议论文，按单栏宽度缩放）
MUST_INCLUDE: [unrolled solver, flow prior, target adaptation]
MUST_NOT_INCLUDE: [Cross Attention, Adapter, Projection Head, Contrastive Loss, fully-sampled target data at inference]
KNOWN_FACTS:
  - source-free / self-supervised 是方法定义，不是实现细节 [user]
  - target adaptation 期间 flow prior 冻结 [user]
sources: [examples/demo-source/]
```

---

## 1. Figure Understanding

- **输入**：欠采样 k-space `y` 与采样掩膜 `M`（推理期只有这两项）。
- **输出**：unrolled solver 收敛后的重建图像 `x̂`（`infer.py::reconstruct()`）。
- **核心计算路径**：`x₀ = A^H M y`（`solver.py::zero_filled_init()`），随后 `K` 次交替迭代
  `x_{k+1} = PriorStep(DataStep(x_k))`；`DataStep` 是非参数化 data-consistency 梯度步
  （`solver.py::dc_step()`），`PriorStep` 是沿 flow-matching 速度场 `v_θ` 的单步 Euler 更新
  （`solver.py::prior_step()` → `models/flow.py::FlowPrior.velocity()`）。
- **训练关系（stage 1 源域预训练）**：`train.py::source_pretrain()` 同时训练 flow prior `θ`
  与 solver 参数 `φ`；监督信号是 SSDU 分掩膜目标（`M_tr` 驱动 solver，`M_ho` 计算 loss）
  加上一个使用**源域全采样图像**的 flow-matching 目标。
- **适配关系（stage 2 目标域适配）**：`train.py::target_adapt()` 冻结 flow prior，
  只更新约 `2K+1` 个标量 `φ`（`solver.py::SolverParams`），仍用 SSDU hold-out 目标；
  **全过程不使用任何目标域全采样数据**。
- **inference 关系**：`solve()` 用冻结的 `θ₀` 与适配后的 `φ` 跑 `K` 次迭代；
  推理区不含 target / GT / fully-sampled reference。
- **核心贡献（按 FOCUS）**：① solver 与 flow prior 的**交替 unrolled 结构**；
  ② target adaptation **只更新极少量参数**、prior 保持冻结的 source-free 适配方式。

---

## 2. Evidence Summary

| Figure element | Evidence | Confidence |
|---|---|---|
| Alternating unrolled solver `x_{k+1} = PriorStep(DataStep(x_k))`, `K` steps | `solver.py::solve()`, `configs/base.yaml` (`solver.num_steps: 8`) | High |
| Data-consistency step | `solver.py::dc_step()` | High |
| Prior step (one Euler step on `v_θ`) | `solver.py::prior_step()` | High |
| Flow prior velocity field | `models/flow.py::FlowPrior.velocity()` | High |
| Zero-filled adjoint initialization `x₀` | `solver.py::zero_filled_init()`, `configs/base.yaml` (`solver.init: zero_filled`) | High |
| Small adaptation parameter set `φ` | `solver.py::SolverParams`, `configs/base.yaml` (`adapt.trainable`) | High |
| Flow prior frozen during target adaptation | `train.py::target_adapt()`, `README.md` | High |
| SSDU split-mask supervision (`M_tr` / `M_ho`) | `train.py::split_mask()`, `train.py::holdout_loss()` | High |
| Flow-matching objective, source stage only | `train.py::flow_matching_loss()` | High |
| Source pre-training updates both `θ` and `φ` | `train.py::source_pretrain()` | High |
| Source-free constraint (no fully-sampled target data) | `README.md`, `infer.py::reconstruct()` | High |
| "Data Consistency" drawn as one aggregated block | `solver.py::dc_step()` (fft2 → mask·residual → ifft2 → `x − α·`) | Medium |
| Inference unroll depth actually used | `infer.py::reconstruct()` vs `configs/base.yaml` (`solver.num_steps`) | Medium |
| Adaptation unroll depth (8) vs inference K (8) | `configs/base.yaml` (`adapt.unroll`, `solver.num_steps`); `train.py::target_adapt()` | High |
| Inner ODE depth of the prior step | `configs/base.yaml` (`solver.prior_inner_steps: 4`) vs `solver.py::solve()` | Low |
| Standalone multi-step ODE sampler | `models/flow.py::FlowPrior.sample()` | Low |

---

### 2.1 多样性矩阵

| 维度 | Draft A | Draft B | Draft C |
|---|---|---|---|
| 主阅读方向 | 环形（水平循环 + 上方回流线） | 双列对照（训练 \| 推理），推理列内为纵向循环 | 上→下三段（源域 / 目标域 / 推理） |
| 信息分组方式 | 按 solver 迭代步分组 | 按 train / inference 分组 | 按 domain + stage 分组 |
| 视觉中心 | 循环体（Data Step ↔ Prior Step） | 冻结 / 可训练对比（目标域适配段） | 域分隔带与 target adaptation 段 |
| 抽象层级 | medium：算子级（DC / prior 两步） | medium：模块级 + 算子级混合（训练列聚合为 `Solver K`） | medium：算子级推理 + 聚合训练阶段 |
| training/inference 表达 | 行内标记 + 底部虚线适配 inset | 左右分区容器 | 上下 `═══` 分隔带 + 容器标题 |
| 循环表达 | 显式回流线 + `repeat K` | 纵向闭环 + `repeat K` | 下方回流线 + `repeat K` |

---

## 3. Draft A — Iterative Loop

> 设计意图：把 solver 与 flow prior 的交替结构本身当作全图的唯一主角，
> 循环闭合成环，冻结的 flow prior 从下方接入 prior step；target adaptation
> 压缩成底部一条虚线 inset，只强调「只更新 φ、θ 冻结」。

```text
        ┌─────────────┐             ┌────────────────┐     ┌────────────────────┐
y,M ──▶ │ x₀=A^H(My)  │ ──▶ x_k ──▶ │ Data Step (DC) │ ──▶ │ Prior Step (v_θ)   │ ──▶ x_{k+1} ─┐
        └─────────────┘     ▲       └────────────────┘     └────────────────────┘              │
                            │               ▲                        ▲                         │
                            │               │ y, M (acquired)        │ v_θ(x, t, cond)         │
                            │                                        │                         │
                            │                             ┌────────────────────┐               │
                            │                             │ Flow Prior  v_θ    │               │
                            │                             │ θ₀   [FROZEN]      │               │
                            │                             └────────────────────┘               │
                            │                                                                  │
                            │                                                                  │
                            │                                                                  │
                            └──────────────────────────── repeat K ────────────────────────────┘


                                        ┌──────────────────────────┐
after K iterations: x_{k+1} ───▶        │ Reconstructed Image x̂   │ [INFERENCE ONLY]
                                        └──────────────────────────┘

─ ─ ─ ─ ─  TARGET ADAPTATION (source-free, no fully-sampled target)  ─ ─ ─ ─ ─
┌──────────────────────────────┐         ┌──────────────────────────────┐
│ Solver Params φ  [TRAINABLE] │◀ ─ ─ ─ ─│ SSDU Objective  [TRAIN ONLY] │
│ log α, log β, prior_scale    │         │ hold-out M_ho on y_t         │
└──────────────────────────────┘         └──────────────────────────────┘
Flow Prior v_θ  [FROZEN]   (no gradient path reaches θ during adaptation)
```

**Best for:**
- 主论文 Fig. 2（当「交替 unrolled solver + flow prior」就是贡献本体时）
- `FIGURE_TYPE=optimization` / `inference` 的变体图

**Strength:** 交替结构与 `repeat K` 的 recurrence 一目了然；`x_k → Data Step → Prior Step → x_{k+1}` 与源码逐行对应；条件输入（`y, M`、`v_θ`）从下方进入，不与主数据流抢权重；冻结的 prior 与 trainable 的 φ 同时出现在一个视场内。

**Weakness:** source-free / 域迁移这条方法定义只能靠底部一行虚线 inset 表达，权重偏弱；训练阶段的 SSDU 监督、源域全采样参考完全没有展开，读者无法从这张图看出 `θ` 是怎么来的。

---

## 4. Draft B — Train vs Inference

> 设计意图：把「训练期能看到什么 / 推理期能看到什么」做成左右两列硬分区，
> 让 source-free 约束与「prior 冻结、只更新 φ」成为视觉中心；推理列内仍保留
> 完整闭合的交替循环。

```text
======= TRAINING  (no target GT) =======              ======== INFERENCE (y, M only) ========
[STAGE 1]  SOURCE PRETRAIN
 y_s,M ─▶[MaskSplit]─┬──▶ M_tr ─▶[Solver K]─▶ x̂_s              ┌──────────────┐
                     └─▶ M_ho ─┐                       y, M ──▶ │ x₀ = A^H(M y)│ ──▶ x_k
 x_ref (fully sampled) ─ ─ ─ ─ ┼─▶[SSDU Loss]─▶φ                └──────────────┘
 [Flow Prior θ] [TRAINABLE] ─ ─┴─▶[Flow-Match]─▶θ                                    │
──────────  freeze θ  ──────────                                                     ├─ repeat K ──┐
[STAGE 2]  TARGET ADAPTATION                                                         │             │
 y_t (undersampled only),M ─▶[Solver K]─▶ x̂_t                                       ▼             │
 [Flow Prior θ₀] [FROZEN] ─▶ prior step, no gradient                          ┌────────────┐
 [Solver Params φ] [TRAINABLE] ◀ ─ [SSDU Loss]                                │ Data Step  │
=========================================                                     └────────────┘
                                                                                     ▼             │
                                                                              ┌────────────┐
                                                              θ₀ [FROZEN] ──▶     │ Prior Step │
                                                                              └────────────┘
                                                                                     │             │
                                                                                     x_{k+1}───────┘
                                                                                     │
                                                                                     ▼
                                                                          ┌────────────────────┐
                                                                          │ Reconstruction x̂  │
                                                                          └────────────────────┘
                                                       no target image / no ground truth
```

**Best for:**
- 主论文 Fig. 2（当论文的主 claim 是 source-free 适配时）
- 与训练图 / 适配图配套的 method overview

**Strength:** 最高频的论文图错误（train / inference 混淆、把 GT 画进推理区）在这张图里几乎不可能发生：左列顶部就写着 `(no target GT)`，右列写着 `(y, M only)`；`[TRAINABLE]` 与 `[FROZEN]` 分列两侧，`φ` 的更新箭头（虚线）只出现在 stage 2；推理列的 `repeat K` 闭环保留了交替结构。

**Weakness:** 两列信息密度不对称（左列 12 行、右列 21 行），排版时需要额外平衡；训练列把 solver 聚合成 `[Solver K]` 一个块，抽象层级与推理列（算子级）不完全一致。

---

## 5. Draft C — Source / Target Domain

> 设计意图：以源域 → 目标域 → 推理的三段纵向推进为主轴，用 `═══` 分隔带把
> **NO FULLY-SAMPLED TARGET DATA** 这条硬约束画成物理边界；target adaptation
> 段处在视觉中心，prior 冻结与 φ 可训练并列呈现。

```text
══════ SOURCE DOMAIN  (fully-sampled source k-space) ══════════════════════════════════
 y_s,M ─▶[Mask Split]─┬──▶ M_tr ─▶[ Unrolled Solver ]─▶ x̂_s
                      └─▶ M_ho ─┐
 x_ref (fully sampled) ─ ─ ─ ─  ┼─▶[ SSDU Loss ] ──▶ updates φ
 [ Flow Prior θ ] [TRAINABLE] ─ ┴─▶[ Flow-Match ] ──▶ updates θ
══════ NO FULLY-SAMPLED TARGET DATA ═══════════════════════════════════════════════════
[ TARGET DOMAIN ]  source-free adaptation
 y_t (undersampled only),M ─▶ [Mask Split]─┬──▶ M_tr ─▶[ Solver K ]─▶ x̂_t
                                           └─▶ M_ho ─┐
 [ Flow Prior θ₀ ] [FROZEN] ─▶ no gradient           │
 [ Solver Params φ ] [TRAINABLE ~2K+1] ◀ ─ ─ ─ ─ ─ ─ ┴─ ─▶[ SSDU Loss ]
═══════════════════════════════════════════════════════════════════════════════════════
                       │  θ₀ (frozen) + φ (adapted)
                       ▼
[ INFERENCE ]   y, M only — no target image, no ground truth

         ┌──────────────┐             ┌────────────┐     ┌────────────┐
y, M ──▶ │ x₀ = A^H(M y)│ ──▶ x_k ──▶ │ Data Step  │ ──▶ │ Prior Step │ ──▶ x_{k+1} ──┘
         └──────────────┘     │       └────────────┘     └────────────┘
                              ▲             ▲                  ▲
                              │             │ y, M             │ θ₀ [FROZEN]
                              └───────── repeat K ────────────────────────────────────┘

after K iterations: x_{k+1} ──▶ [ Reconstructed Image x̂ ]
```

**Best for:**
- 训练 / 适配流程图（`FIGURE_TYPE=training`），或 motivation→method 的过渡图
- 需要强调 domain gap 与 source-free 约束的版本

**Strength:** 分隔带把「目标域没有全采样数据」变成一条不可跨越的边界，比 caption 里的说明强得多；三段式让读者一眼看清两个阶段各自能访问什么数据、哪些参数动、哪些不动；推理段仍画出闭合的 `repeat K` 循环。

**Weakness:** 源域与目标域两个训练阶段都被压成 2–3 行，`DataStep` / `PriorStep` 的细节在训练段被聚合，只有推理段是算子级；纵向三段在双栏论文中偏长，缩放后字号偏小。

---

## 6. Recommended Draft

**Recommended: Draft B**

Why:
1. 论文最有风险的主张是 source-free 适配（prior 冻结、只更新少量 φ），Draft B 用左右硬分区把这条主张变成空间事实，读图即可验证，不需要读 caption。
2. 它同时满足 FOCUS 的两个要求：交替循环在推理列以闭合 recurrence 保留，target adaptation 的「少量参数」在左列 stage 2 单独占位。
3. 训练专属监督（`x_ref`、`M_ho`、Flow-Match）全部落在左列虚线路径上，推理列只有 `y, M`，data-leakage 类的审稿意见无法成立。
4. 两个 Level-1 容器（TRAINING / INFERENCE）给下游 SVG 代理一个无歧义的分组层级，跨列连线为零，箭头不易交叉。
5. 最大显示宽度 100 列，按单栏缩放后仍可读；Draft A 的信息更少、Draft C 更长，都不如 B 稳。

---

## 7. Alignment Notes

```text
N1  Measurement y（欠采样 k-space）
└── solver.py::solve() 的 y 参数；infer.py::reconstruct(kspace, ...)

N2  Sampling Mask M
└── solver.py::solve() 的 mask 参数；train.py::split_mask() 的输入

N3  Zero-filled Adjoint Init x₀
└── solver.py::zero_filled_init()   (A^H (M y))；configs/base.yaml: solver.init: zero_filled

N4  Current Reconstruction x_k
└── solver.py::solve() 循环内的局部变量 x

N5  Data Step（Data-Consistency Step）
└── solver.py::dc_step()；步长来自 solver.py::SolverParams.alpha()

N6  Prior Step
└── solver.py::prior_step()；步长来自 solver.py::SolverParams.beta()

N7  Next Iterate x_{k+1}
└── solver.py::solve() 循环内 x 的下一状态；也是循环回流线的起点

N8  Flow Prior v_θ（源域阶段可训练）
└── models/flow.py::FlowPrior；训练见 train.py::source_pretrain()

N9  Velocity Field v_θ(x, t, cond)
└── models/flow.py::FlowPrior.velocity()

N10 Adaptation Parameters φ
└── solver.py::SolverParams 的 log_alpha / log_beta / prior_scale（约 2K+1 个标量）
    configs/base.yaml: adapt.trainable

N11 Source-Pretrained Prior θ₀（冻结复用）
└── train.py::target_adapt() 中 requires_grad_(False) 之后的 models/flow.py::FlowPrior

N12 SSDU Mask Splitting
└── train.py::split_mask()

N13 Training Split M_tr
└── train.py::split_mask() 返回的 m_tr；作为 solver.py::solve() 的 mask 传入

N14 Hold-out Split M_ho
└── train.py::split_mask() 返回的 m_ho；进入 train.py::holdout_loss()

N15 Source Reference x_ref（全采样，仅源域）
└── train.py::source_pretrain() 的 source_loader 第三项；只在 train.py::flow_matching_loss() 中使用

N16 SSDU Objective
└── train.py::holdout_loss() + train.py::data_consistency_loss()

N17 Flow-Matching Objective
└── train.py::flow_matching_loss()

N18 Reconstructed Image x̂
└── infer.py::reconstruct() 的返回值

N19 Target Undersampled k-space y_t
└── train.py::target_adapt() 的 target_loader 迭代项（只有 y 与 mask，没有参考图）

N20 K-Step Alternating Solver（聚合视图）
└── solver.py::solve() 的 K 次 dc_step() → prior_step() 循环
```

**语义聚合声明：**

`"Data Step" is a semantic abstraction of: solver.py::dc_step() 内部的 fft2(x) → mask * (· − y) → ifft2(·) → x − α·(·) 四个张量操作；聚合不改变算子含义，也不隐藏任何训练 / 推理分支（该函数在两个阶段都被调用）。`

`"K-Step Alternating Solver" is a semantic abstraction of: solver.py::solve() 中重复 K 次的 dc_step() → prior_step() 序列。它只出现在 Draft B 的训练列与 Draft C 的源域 / 目标域段；Draft A、B 的推理列与 C 的推理段仍展开到算子级，因此该聚合不会掩盖交替结构。`

`"SSDU Objective" is a semantic abstraction of: train.py::holdout_loss()（在 M_ho 上）与 train.py::data_consistency_loss()（在 M_tr 上）在 train.py::training_step() 中的加权和。`

`"Source-Pretrained Prior θ₀" is the frozen reuse of the same module as "Flow Prior v_θ" after train.py::source_pretrain()；train.py::target_adapt() 对同一批参数调用 requires_grad_(False)。两行分别记录该模块在两个阶段的不同状态，这是状态区分，不是两个模型。`

**命名映射（论文语义名 ↔ 源码名）：**

```text
Flow Prior v_θ                 ↔ models/flow.py::FlowPrior
Velocity v_θ(x, t, cond)       ↔ models/flow.py::FlowPrior.velocity()
Zero-filled Adjoint Init x₀    ↔ solver.py::zero_filled_init()
Data Step                      ↔ solver.py::dc_step()
Prior Step                     ↔ solver.py::prior_step()
K-Step Alternating Solver      ↔ solver.py::solve()
Adaptation Parameters φ        ↔ solver.py::SolverParams (log_alpha / log_beta / prior_scale)
Source-Pretrained Prior θ₀     ↔ FlowPrior after train.py::source_pretrain()
SSDU Mask Splitting            ↔ train.py::split_mask()
Training Split M_tr            ↔ m_tr in train.py::split_mask() / training_step()
Hold-out Split M_ho            ↔ m_ho in train.py::split_mask() / holdout_loss()
Source Reference x_ref         ↔ x_ref in train.py::source_pretrain() / training_step()
SSDU Objective                 ↔ train.py::holdout_loss() + data_consistency_loss()
Flow-Matching Objective        ↔ train.py::flow_matching_loss()
Measurement y                  ↔ y in solver.py::solve()
Sampling Mask M                ↔ mask in solver.py::solve()
Target Undersampled k-space y_t ↔ target_loader items in train.py::target_adapt()
Reconstructed Image x̂         ↔ return value of infer.py::reconstruct()
```

---

## 8. Uncertainties

```text
Uncertain:
- configs/base.yaml 用两个独立的键给出迭代深度：adapt.unroll: 8（适配期，
  train.py::target_adapt() 读取）与 solver.num_steps: 8（推理期，infer.py::reconstruct()
  读取）。代码没有任何约束要求两者一致，方法上是否必须一致也无法从给定文件判定；
  图中统一写作 repeat K（= 8），不区分两个深度（U1）。
- configs/base.yaml 声明了 solver.prior_inner_steps: 4，而 solver.py::solve() 从不把它传给
  solver.py::prior_step()，后者只调用一次 FlowPrior.velocity()；prior step 到底是单步 Euler
  还是 4 步内层 ODE 求解无法判定。图中按代码路径画成一次速度评估（U2）。
- models/flow.py::FlowPrior.sample() 实现了一个独立的多步 ODE 采样器，但给定文件中没有
  任何模块调用它；方法是否还存在一条基于采样的第二条推理路径（而非 unrolled solver）
  无法判定。所有 draft 只画 unrolled solver（U3）。
```

---

## 9. SVG Handoff Notes

```text
Canvas:                  landscape（推荐 180 × 120 mm；Draft B 为双列，最大 100 显示列）
Primary flow:            left → right（Draft A / C 主链）；dual-column with a vertical cycle（Draft B）
Suggested visual groups: TRAINING-SOURCE / TRAINING-ADAPT / SOLVER-LOOP / PRIOR / OBJECTIVE / OUTPUT
Visual emphasis:         solver ↔ flow-prior 交替循环（Draft A 中心、B 右列、C 推理段）与
                         target adaptation 的「少量参数 + 冻结 prior」（最重色，1.5–2pt 描边）
Secondary elements:      measurement operator、sampling mask、fully-sampled source reference（最轻，0.5pt 灰）
Line semantics:          solid   ───▶  = inference / forward computation
                         dashed  ─ ─ ▶ = training supervision, loss, parameter update
                         double  ═══   = domain / stage separator band（不是数据流）
                         [FROZEN] / [TRAINABLE] / [TRAIN ONLY] / [INFERENCE ONLY] 一律用方括号文字，
                         不用颜色或 emoji
Styling hierarchy:       Level 1 = TRAINING / INFERENCE / SOURCE DOMAIN / TARGET DOMAIN 容器
                         Level 2 = Flow Prior、Data Step、Prior Step、Solver Params φ
                         Level 3 = Mask Splitting、SSDU / Flow-Matching objective、split masks
                         Level 4 = repeat K、[TRAIN ONLY] 等无框文本
Color grouping:          solver 循环 = 蓝；flow prior（含冻结副本 θ₀）= 橙；adaptation 参数 φ = 绿；
                         losses / supervision = 灰虚线同色；domain 分隔带 = 中性深灰
De-emphasize:            measurement y / mask M、x_ref、M_tr / M_ho —— 降低不透明度，作为背景条件
Center node:             Draft A → Data Step 与 Prior Step 之间的循环体；
                         Draft B → 目标域适配段（[Flow Prior θ₀][FROZEN] 与 [Solver Params φ][TRAINABLE] 的对比）；
                         Draft C → NO FULLY-SAMPLED TARGET DATA 分隔带下方的适配段
Curved arrows:           x_k → x_{k+1} 的回流线（Draft A / C 下方、Draft B 右侧）可做成圆角二次曲线；
                         SSDU loss → φ 的更新虚线在 Draft B 左列可弯曲绕开 M_tr 支线
Inset candidates:        Draft A 底部的 TARGET ADAPTATION inset 可做成右下角虚线框；
                         Draft C 的 INFERENCE 段可做成右下角 inset；
                         FlowPrior.sample() 的多步采样路径不画（见 U3）
```

---

## 10. Figure Element Inventory

| ID | Type | Label | Group | Inputs | Outputs | Status |
|---|---|---|---|---|---|---|
| N1 | data | Measurement y | Solver | — | N3, N5, N20 | observed |
| N2 | data | Sampling Mask M | Solver | — | N3, N5, N12, N20 | observed |
| N3 | operator | Zero-filled Adjoint Init x₀ | Solver | N1, N2 | N4 | observed |
| N4 | state | Current Reconstruction x_k | Solver | N3, N7 | N5 | observed |
| N5 | operator | Data Step | Solver | N4, N1, N2, N10, N13 | N6 | observed |
| N6 | operator | Prior Step | Solver | N5, N8, N9 | N7 | observed |
| N7 | state | Next Iterate x_{k+1} | Solver | N6 | N4, N18 | observed |
| N8 | model | Flow Prior v_θ | Prior | — | N9, N17, N20 | observed · trainable |
| N9 | state | Velocity v_θ(x, t, cond) | Prior | N8, N11 | N6 | observed |
| N10 | parameter | Adaptation Parameters φ | Adaptation | N16 | N5, N6, N20 | observed · trainable |
| N11 | parameter | Source-Pretrained Prior θ₀ | Adaptation | N8 | N9, N20 | observed · frozen |
| N12 | operator | SSDU Mask Splitting | Training | N2 | N13, N14 | observed |
| N13 | supervision | Training Split M_tr | Training | N12 | N5, N20 | observed · train-only |
| N14 | supervision | Hold-out Split M_ho | Training | N12 | N16 | observed · train-only |
| N15 | supervision | Source Reference x_ref | Source | — | N17 | observed · train-only |
| N16 | objective | SSDU Objective | Objective | N7, N13, N14 | N10 | observed · train-only |
| N17 | objective | Flow-Matching Objective | Objective | N8, N15 | N8 | observed · train-only |
| N18 | output | Reconstructed Image x̂ | Output | N7, N20 | — | observed · inference-only |
| N19 | data | Target Undersampled k-space y_t | Adaptation | — | N3, N20 | observed · train-only |
| N20 | operator | K-Step Alternating Solver | Solver | N1, N2, N8, N10, N13, N19 | N18 | abstraction · semantic |

> **未登记的节点：** Cross Attention / Adapter / Projection Head / Contrastive Loss
> （命中 `MUST_NOT_INCLUDE`，`demo-source/` 中亦无对应实现）、inner prior sampler（U2）、
> `FlowPrior.sample()`（U3）—— 均无依据或无法确认，按
> [evidence-policy §2 规则 2、4](../references/evidence-policy.md) 不画、不登记。
