# 示例：形状图例与 `SKETCH_VARIANTS: both`

演示**形状编码语义**图例（[sketch-primitives.md](../references/sketch-primitives.md) §1）
与 `SKETCH_VARIANTS: both` 的双画法对照。

- `SKETCH_STYLE: enhanced` —— 允许伪 3D / tensor 堆叠 / 图像框；
- `SKETCH_VARIANTS: both` —— 每份 Draft 内**两个 `text` 块**：先 clean、后 enhanced。
  两块**共用同一个 grammar**，**不是两份 draft**，也不算多样性；
- 两个 draft 的 grammar 仍然互不相同（`Linear Pipeline` vs `Data / Model / Objective`）。

**本示例演示的形状：**

```text
data     ┌────┐        model     ╔════╗        loss      ╭────╮
         │ d  │                  ║ m  ║                  │ L  │
         └────┘                  ╚════╝                  ╰────╯
operator [ IFFT ]      state     x_t / v_θ（不加框）  tensor  分层堆叠框
image    [slice] 角标  stage/band 大外框（不是节点）
```

> 图例是**画法**约定：形状只表达"这是什么类型的对象"，不改变节点的
> `Inputs` / `Outputs`，也不新增元素表行。

---

## 调用

```
调用 academic-figure-draft-architect
sources:          examples/demo-source/
FIGURE_TYPE:      architecture
SKETCH_STYLE:     enhanced
SKETCH_VARIANTS:  both
DETAIL_LEVEL:     medium
NUM_DRAFTS:       2
FOCUS:            讲清 velocity field 的条件结构，以及共享编码器这一信息点
MUST_INCLUDE:     [Flow Prior, Shared Encoder, Velocity Head, velocity field]
MUST_NOT_INCLUDE: [Cross Attention, Adapter, Contrastive Loss]
KNOWN_FACTS:      [Flow Prior 在 target 阶段冻结]
```

---

## 1. Figure Understanding

条件 flow-matching 先验 `v_θ(x, t, cond)` 把状态与条件像分别编码后拼接，再由 head 输出速度场。

- **输入：** 状态 `x_t`（训练期是 flow 插值点）与条件像 `cond`；`cond` 默认取零填充伴随 `x_0 = Aᴴ M y`；
- **核心计算路径：** `x_t` 与 `cond` 各过一次**共享权重**的卷积编码器 →
  两路特征与时间嵌入拼接 → velocity head → `v_θ`；
- **训练关系：** flow-matching loss 用源域 fully-sampled 图像 `x_1` 作为目标分布，
  **只在源域阶段存在**；
- **inference 关系：** 部署期只把冻结的 θ 放进 unrolled solver，条件像仍取 `x_0`；
- **核心贡献：** 生成式先验的条件结构，以及"target 阶段只调步长参数"的适配方式。

**注意：** 本图只画**先验内部**，不画 solver 循环——solver 由
[example-auto-inference.md](example-auto-inference.md) 与
[example-code-grounded.md](example-code-grounded.md) 覆盖。

---

## 2. Evidence Summary

| Figure element | Evidence | Confidence |
|---|---|---|
| k-space (y, M) | `infer.py::reconstruct()` 的入参 | High |
| Zero-filled 伴随 x_0 | `solver.py::zero_filled_init()`（`ifft2(mask * y)`） | High |
| 条件像 cond | `train.py::training_step()` 的 `cond = zero_filled_init(y, m_tr)` | High |
| 状态 x_t（flow 插值点） | `train.py::flow_matching_loss()` 的 `x_t = (1-t)*x0 + t*x1` | High |
| 共享编码器 | `models/flow.py::FlowPrior.encode()` | High |
| 状态与条件共用编码器 | `models/flow.py::FlowPrior.velocity()` 对 `x` 与 `cond` 各调一次 `encode()` | High |
| 特征拼接（含时间嵌入） | `models/flow.py::FlowPrior.velocity()` 的 `torch.cat([h_x, h_c, t_emb])` | High |
| velocity head | `models/flow.py::FlowPrior.velocity_head` | High |
| velocity field v_θ | `models/flow.py::FlowPrior.velocity()` 的返回值 | High |
| flow-matching loss | `train.py::flow_matching_loss()` | High |
| 源域目标图像 x_1 | `train.py::flow_matching_loss()` 的 `x1` 入参（源域 fully-sampled） | High |
| 多步 inner prior sampler | `configs/base.yaml::solver.prior_inner_steps`（**代码未引用**） | Low |

---

### 2.1 多样性矩阵（自检用，非契约段）

| 维度 | Draft A | Draft B |
|---|---|---|
| 主阅读方向 | 左→右（单程） | 上→下三带 |
| 信息分组 | 按 **velocity field 的数据流** | 按 **data / model / objective** |
| 视觉中心 | 共享编码器与拼接 | Model 带 |
| 抽象层级 | medium（算子级） | medium（算子级） |
| train/inference 表达 | 行内 `[TRAIN ONLY]` 标记 | 三带分区 + 行内标记 |
| 循环表达 | 未出现 | 未出现 |

> `both` 的两个变体只在**画法**上不同（clean / enhanced），**不参与**本矩阵，也不算多样性。

---

## 3. Draft A — Linear Pipeline

> 设计意图：沿数据流从左到右画一次完整的 velocity field 计算，把"共享编码器"这个
> 真正的结构点放在视觉中心。**入口是图像域的 `x_t` 与 `cond`**——编码器是卷积，
> 不做任何 FFT。

**clean 变体（只用平面框与方括号算子）：**

```text
[slice] x_t ──┐
              ├──▶ ┌──────────────────┐
[slice] x_0 ──┘    │ Shared Encoder   │
                   └────────┬─────────┘
                            │ h_x / h_c
                            ▼
                   ┌──────────────────┐
                   │ concat + t emb   │
                   └────────┬─────────┘
                            ▼
                   ┌──────────────────┐
                   │ Velocity Head    │
                   └────────┬─────────┘
                            ▼
                      velocity  v_θ
```

**enhanced 变体（模型用双线框，特征用 tensor 堆叠）：**

```text
[slice] x_t ──┐
              ├──▶ ╔══════════════════╗
[slice] x_0 ──┘    ║ Shared Encoder   ║
                   ╚════════┬═════════╝
                            │ h_x / h_c
                            ▼
                   ┌──────────────────┐
                   │ Features slice 1 │
                   ├──────────────────┤
                   │ Features slice 2 │
                   ├──────────────────┤
                   │ Features slice 3 │
                   └────────┬─────────┘
                            ▼
                   ╔══════════════════╗
                   ║ Velocity Head    ║
                   ╚════════┬═════════╝
                            ▼
                      velocity  v_θ
```

**Best for:**
- 论文里需要单独讲清先验条件结构的补充图
- 附录 Fig.（需要看清 `encode(x)` 与 `encode(cond)` 共享权重）

**Strength:** 共享编码器只画一次，`h_x / h_c` 两条支路汇合于拼接点，条件结构不含糊；
enhanced 变体用双线框与堆叠框把"模型 / 特征图"直接编码进形状。

**Weakness:** 入口两路都用 `[slice]` 角标，容易被误读成"图像输入"而忽略
`x_t` 在训练期其实是 flow 插值点；需要 caption 点一句。

---

## 4. Draft B — Data / Model / Objective

> 设计意图：按 **data / model / objective** 三带铺开，把"数据从哪来"与
> "优化什么"都放进来，并明确 flow-matching loss 需要**源域**的 fully-sampled 图像。

**clean 变体：**

```text
DATA ──────────────────────────────────────────────────
  [slice] k-space (y, M) ──▶ [ IFFT ] ──▶ cond x_0
        │
        ▼
MODEL ─────────────────────────────────────────────────
  ┌──────────────────┐
  │ Shared Encoder   │
  └────────┬─────────┘
           │ h_x / h_c
           ▼
  ┌──────────────────┐
  │ concat + t emb   │
  └────────┬─────────┘
           ▼
  ┌──────────────────┐
  │ Velocity Head    │
  └────────┬─────────┘
           │ v_θ
           ▼
OBJECTIVE ─────────────────────────────────────────────
                      ┌────────────────────┐
  x_1 (source) ──────▶│ Flow-matching Loss │
                      └─────────┬──────────┘
                                │ update θ
```

**enhanced 变体：**

```text
DATA ──────────────────────────────────────────────────
  [slice] k-space (y, M) ──▶ [ IFFT ] ──▶ cond x_0
        │
        ▼
MODEL ─────────────────────────────────────────────────
  ╔══════════════════╗
  ║ Shared Encoder   ║
  ╚════════┬═════════╝
           │ h_x / h_c
           ▼
  ┌──────────────────┐
  │ Features slice 1 │
  ├──────────────────┤
  │ Features slice 2 │
  ├──────────────────┤
  │ Features slice 3 │
  └────────┬─────────┘
           ▼
  ╔══════════════════╗
  ║ Velocity Head    ║
  ╚════════┬═════════╝
           │ v_θ
           ▼
OBJECTIVE ─────────────────────────────────────────────
                      ╭────────────────────╮
  x_1 (source) ──────▶│ Flow-matching Loss │
                      ╰─────────┬──────────╯
                                │ update θ
```

**Best for:**
- 主论文的训练侧图（需要同时交代数据、模型、目标）
- 需要在图里显式表达"目标函数需要 fully-sampled 源图像"的场合

**Strength:** 三带分区让"数据从哪来、模型是什么、优化什么"一屏可读；
增强版把"这是模型 / 这是特征图 / 这是目标函数"直接编码进三种形状。

**Weakness:** 偏纵向，双栏排版会缩得偏小；`x_1 (source)` 与 DATA 带的关系靠跨带箭头
表达，需要 caption 补一句"仅源域可用"。

---

## 5. Recommended Draft

**Recommended: Draft B**

Why:
1. `architecture` 类型要看 tensor path 与数据来源，B 的三带把两者都放进了版面；
2. 只有 B 画出"目标函数需要源域 fully-sampled 图像"这条约束；
3. B 的 data 带显式给出 `cond x_0` 的来源（`[ IFFT ]`），A 把 `x_0` 当成既有输入；
4. tensor 堆叠只出现在 B 的 MODEL 带，形状差异直接区分模型与特征图；
5. 竖向三带在单栏论文里的缩放损失小于 A 的横向长链。

（Draft A 更适合作为讲**先验内部条件结构**的补充图；两者都不画 solver 循环。）

---

## 6. Alignment Notes

```text
N1  k-space (y, M)      ── infer.py::reconstruct() 的入参；[slice] 角标表示图像域对象
N2  IFFT (Aᴴ M y)       ── solver.py::ifft2() 被 solver.py::zero_filled_init() 调用
N3  cond x_0            ── train.py::training_step() 的 cond = zero_filled_init(y, m_tr)
N4  x_t (flow 插值点)   ── train.py::flow_matching_loss() 的 x_t = (1-t)*x0 + t*x1
N5  Shared Encoder      ── models/flow.py::FlowPrior.encode()
N6  Feature stack       ── models/flow.py::FlowPrior.velocity() 的 torch.cat([h_x, h_c, t_emb])
N7  Velocity Head       ── models/flow.py::FlowPrior.velocity_head
N8  Velocity field v_θ  ── models/flow.py::FlowPrior.velocity() 的返回值
N9  Flow-matching Loss  ── train.py::flow_matching_loss()
N10 x_1 (source image)  ── train.py::flow_matching_loss() 的 x1 入参（源域 fully-sampled）
```

**语义聚合声明：**

- `"Feature stack"（N6）` is a semantic abstraction of: `FlowPrior.velocity()` 中
  `torch.cat([h_x, h_c, t_emb], dim=1)` 的通道拼接；图中画成 3 层**只表示"这是一个多通道
  特征张量"**，**不代表真实通道数**（`base_ch = 32`）。
- `"Shared Encoder"（N5）` is a semantic abstraction of: `FlowPrior.encode()` 被
  `velocity()` 对 `x` 与 `cond` 各调用一次（权重共享是调用方式决定的，不是新模块）。
- `"IFFT (Aᴴ M y)"（N2）` is a semantic abstraction of: `zero_filled_init()` 里的
  `ifft2(mask * y)`——把掩码相乘与逆变换画成一个算子节点。

**命名映射：**

```
Flow Prior θ      ↔ models/flow.py::FlowPrior
Velocity field    ↔ models/flow.py::FlowPrior.velocity()
Shared Encoder    ↔ models/flow.py::FlowPrior.encode()
cond x_0          ↔ solver.py::zero_filled_init()
```

**未画出的内容（明确声明）：**

- **multi-step inner prior sampler**：`configs/base.yaml` 声明
  `solver.prior_inner_steps: 4`，但 `prior_step()` 每步只做一次 Euler 更新，
  `FlowPrior.sample()` 也未被任何地方调用 ⇒ 材料无法确认意图 ⇒ **不画**（U1）。
- **unrolled solver 循环**：不属于本图的 `FIGURE_TYPE`（`architecture`），
  由 [example-auto-inference.md](example-auto-inference.md) 覆盖 ⇒ 不画。
- **Cross Attention / Adapter / Contrastive Loss**：命中 `MUST_NOT_INCLUDE` 且代码无实现
  ⇒ 不画、不进元素表。

---

## 7. Uncertainties

```text
Uncertain:
- inner_prior_sampler：configs/base.yaml 的 solver.prior_inner_steps: 4 在代码中
  没有任何读取点（solver.py::prior_step 只做一次 Euler 更新，FlowPrior.sample()
  无调用者）。无法确认是"未启用的可选结构"还是"废弃配置"，故不进入任何 draft（U1）。
- x_t_semantics：velocity() 的形参名是 x，而 flow_matching_loss() 传入的是插值点 x_t。
  图里按训练期语义标成 x_t；推理期同一位置其实是 solver 的当前重建，
  两种语义共用同一个节点，材料未区分（U2）。
```

---

## 8. SVG Handoff Notes

```text
Canvas:                  landscape (Draft A) / portrait (Draft B)
Primary flow:            left → right (A) / top → bottom (B)
Suggested visual groups: Draft A: 输入支路 / 编码与拼接 / 输出
                         Draft B: DATA / MODEL / OBJECTIVE 三带
Visual emphasis:         N5 Shared Encoder（共享权重是本图的信息点）
Secondary elements:      N2 [IFFT]、N9 Flow-matching Loss
Line semantics:          solid = 前向计算；dotted = 条件注入（cond → encoder）；
                         dashed = 训练监督（仅 OBJECTIVE 带）
Styling hierarchy:       Level 1 = 三带 / 支路容器；Level 2 = 模型块；
                         Level 3 = [IFFT] 算子与 loss
Color grouping:          N5 与它的两个调用点同色；N6 用堆叠色阶
De-emphasize:            N2、N9、N10
Center node:             N5 Shared Encoder
Curved arrows:           cond 支路汇入拼接点的走线
Inset candidates:        enhanced 变体的 tensor 堆叠可放大为 inset
Sketch primitives:       model (double-line) x2 (Shared Encoder, Velocity Head)；
                         tensor stack x1 (Feature stack, 3 visible slices)；
                         image frame x3 ([slice]: x_t, cond x_0, k-space)；
                         operator [IFFT] x1；objective x1 (Flow-matching Loss)
```

---

## 9. Figure Element Inventory

| ID | Type | Label | Group | Inputs | Outputs | Status |
|---|---|---|---|---|---|---|
| N1 | data | k-space (y, M) | Data | — | N2 | observed |
| N2 | operator | IFFT (Aᴴ M y) | Data | N1 | N3 | observed |
| N3 | data | cond x_0 | Data | N2 | N5 | observed |
| N4 | state | x_t (flow interpolant) | Model | — | N5 | observed · train-only |
| N5 | model | Shared Encoder | Model | N3,N4 | N6 | observed |
| N6 | state | Feature stack | Model | N5 | N7 | abstraction · semantic |
| N7 | model | Velocity Head | Model | N6 | N8 | observed |
| N8 | state | Velocity field v_θ | Model | N7 | N9 | observed |
| N9 | objective | Flow-matching Loss | Objective | N8,N10 | N7 | observed · train-only |
| N10 | data | x_1 (source image) | Objective | — | N9 | observed · train-only |

> **形状与 `Type` 一一对应：**
> N5 / N7 是模型块 → 双线框 `╔═╗`；N6 是特征张量 → 分层堆叠框；
> N1 / N3 / N10 是图像域对象 → 带 `[slice]` 角标的普通框；N2 是算子 → `[ IFFT ]`；
> N9 是目标函数 → 圆角框 `╭─╮`；N4 / N8 是**变量**（state）→ **不加框**。
>
> 脚本会检查"双线框是否真的对应元素表里的 `model` 行"（W8）；
> 本表只登记**图中实际出现**的节点——solver 循环不在本图范围，故 `dc_step` /
> `prior_step` / `SolverParams` **不登记**。

---

## 这个示例演示了什么

| 行为 | 体现位置 |
|---|---|
| 形状编码语义 | `╔═╗`↔`model`、`[ IFFT ]`↔`operator`、堆叠框↔`state`、`[slice]`↔`data`、`╭─╮`↔`objective`、变量不加框 |
| `SKETCH_STYLE: enhanced` | 双线框 / tensor 堆叠 / 图像框全部启用 |
| `SKETCH_VARIANTS: both` | 每份 Draft 内两个 `text` 块（clean → enhanced），共用一个 grammar |
| `both` 不算多样性 | 多样性矩阵只比较 A / B 两个 grammar 的分组差异 |
| 形状不改变语义 | N4–N8 的 `Inputs` / `Outputs` 在 clean 与 enhanced 两版中完全一致 |
| 只登记图中有的节点 | solver 循环不在本图，`dc_step` / `prior_step` / `SolverParams` 未登记 |
| 未确认内容不画 | `prior_inner_sampler` 只进 `Uncertainties`（U1） |
