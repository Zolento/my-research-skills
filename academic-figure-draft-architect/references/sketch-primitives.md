# 速写原语与视觉图例（Sketch Primitives）

字符 draft **不是终稿插图**。但它可以**暗示对象类型**：让 U-Net 一眼看出是网络块、
让特征图一眼看出是 tensor、让输入一眼看出是图像。

本文件是**速写原语与视觉图例的唯一权威定义**。`SKILL.md`、`templates/` 与
`scripts/check_draft.py` 一律引用本文件，**不再各自重复定义**。

**总纲（一句话）：**

> 在 Markdown 草图中，视觉暗示只用于**区分对象类型**，
> 不得引入材料不支持的结构细节。

**目标是 wireframe / storyboard，不是 ASCII art。**

## 0. 边界（先读）

| 问题 | 答案 |
|---|---|
| 改变十段式 schema 吗 | **不改变**（[output-contract.md](output-contract.md) 仍是权威） |
| 增加 grammar 枚举吗 | **不增加**（[visual-grammar.md](visual-grammar.md) §1 仍是 A–H） |
| 增加元素表 `Type` 值吗 | **不增加**（见 §7 映射表） |
| 能算作 draft 之间的多样性吗 | **不能**（见 §8） |
| 生成 SVG / PNG 吗 | **不生成**（仍由下游绘图代理负责） |

## 1. 形状编码语义（核心图例）

**形状是语义，不是装饰。** 下面这张图例是全 Skill 的house style；
读到一个 `Type` 就知道该画什么形状，反过来看到一个形状就知道它是什么 `Type`。

| 对象 | 字形 | 元素表 `Type` |
|---|---|---|
| 数据 / 图像输入输出 | 普通框 `┌─┐`（图像另加 `[image]` / `[slice]` 角标） | `data` / `output` |
| **模型 / 网络块** | **双线框 `╔═╗`** | `model` |
| 轻量算子 | 单行方括号节点 `[ FFT ]` | `operator` |
| tensor / 特征图 | 错位堆叠框（见 §4） | `state` / `data` |
| loss / objective | 小圆角框 `╭─╮`，或 `( Loss )` | `objective` / `supervision` |
| state 变量 | **不加框**（`x_k`、`θ*`） | `state` |
| stage / domain | 大外框或 `═══` 分隔带（**不是节点**） | — |
| 冻结 / 可训练 | 框内 `[FROZEN]` / `[TRAINABLE]` | `Status` 限定词 |
| 核心贡献 | 框内 `[CORE CONTRIBUTION]` | —（标记） |

**图例三条规则：**

1. **字形集封闭。** 只允许 [ascii-design-language.md](ascii-design-language.md) §1 列出的
   字形；三个框族为单线 `┌┐└┘│`、双线 `╔╗╚╝║`、圆角 `╭╮╰╯│`。
2. **优先复用 4–8 个原语，而不是给每个节点发明一个独特字形。**
   节点一多，字符画的两个典型失败就会同时出现：错位、以及风格不一致导致下游
   SVG 代理无法解析。
3. **`★` 与 emoji 不用。** 核心贡献统一写 `[CORE CONTRIBUTION]`
   （对齐与字体兼容，见 [ascii-design-language.md](ascii-design-language.md) §1 回退原则）。
   `[PROPOSED]` 与它同义，**不另立**。

## 2. 原语总表

| 原语 | 用于 | 权威定义 |
|---|---|---|
| **平面块** flat block | 数据、通用步骤 | [ascii-design-language.md](ascii-design-language.md) §1 |
| **方括号算子** inline operator | FFT / Mask / DC / Norm / Concat 等轻量算子 | [ascii-design-language.md](ascii-design-language.md) §5（Level 3） |
| **伪 3D 块** pseudo-3D block | 可选加强：主要神经模块 | **本文件 §3** |
| **tensor 堆叠** tensor stack | 特征图 / 多通道 / 多尺度 / latent | **本文件 §4** |
| **图像框** image frame | MRI / CT / 重建结果等图像类输入输出 | **本文件 §5** |
| **回环线** loop cue | 迭代 recurrence | [ascii-design-language.md](ascii-design-language.md) §1（循环行） |
| **stage 容器** stage panel | training / inference / source / target / Stage A–C | [ascii-design-language.md](ascii-design-language.md) §5（Level 1） |

**已在这些文件里有权威定义的原语，本文件不重述**，只补三种新增原语。

## 3. 伪 3D 块（pseudo-3D block）

**用途：** 在 `enhanced` 档下**加强**模型块的视觉重量。
**模型块的默认形状是双线框 `╔═╗`**（§1）；伪 3D 是可选的第二级强化，
**不是**默认，也不是驱动 SVG 的依据。

**模板（紧凑版，推荐）：**

```text
   ┌──────────────┐
  /  Flow Prior  /|
 /──────────────/ |
 |              | |
 |    U-Net     | /
 └──────────────┘/
```

**模板（扁平版，排版紧张时用）：**

```text
    _____________
   /           /|
  /  Denoiser / |
 /___________/  |
 |           |  /
 |___________| /
```

**规则：**

1. **只用于主要模型组件。** 不要给每个算子都加立体感。
2. **透视要浅、要示意化。** 一个斜角面足够；不追求灭点、阴影、渐变。
3. **不逐层展开 encoder / decoder。** 除非架构本身是论文贡献。
4. **优先一个紧凑块 + 标签**（`U-Net Prior` / `Backbone` / `Denoiser`），
   而不是拆成 `Encoder → Bottleneck → Decoder`。
5. **立体只是 hint，不是要求。** 去掉斜角面后语义不得改变。
6. **同层模块要么都用伪 3D，要么都不用。** 混用会暗示不存在的类型差异。
7. **不得用于 loss / supervision / 数据节点 / 变量。** 它们有各自的形状（§1）。
8. **每个伪 3D 块必须对应元素表里一条记录**（见 §7），不得只画块不登记。
9. 单份 draft 内**不超过 3 个**伪 3D 块（`scripts/check_draft.py` 超出即警告 W6）。

## 4. tensor 堆叠（tensor stack）

**用途：** 暗示"这是张量 / 特征图 / 多尺度表示"，且**张量性本身有语义**。

**模板（错位堆叠版，推荐）：**

```text
      ┌──────────┐
    ┌──────────┐ │
  ┌──────────┐ │ │
  │ Features │ │ │
  └──────────┘ │ │
    └──────────┘ │
      └──────────┘
```

**模板（分层版）：**

```text
   ┌──────────┐
   │ Tensor   │
   ├──────────┤
   │ Tensor   │
   ├──────────┤
   │ Tensor   │
   └──────────┘
```

**规则：**

1. **只在"是不是张量"有语义时用。** 一个中间变量不需要堆叠。
2. **必须写清这叠是什么：** `multi-scale features` / `latent tensor` /
   `channel stack` / `feature pyramid`。只画叠不标注 = 无信息量。
3. **可见层数 3–5。** 超过 5 层 `scripts/check_draft.py` 警告（W5）。
4. **不模拟真实张量维度。** 尺寸变化用**框宽随空间尺寸缩放**表达
   （见 [sketch-templates.md](sketch-templates.md) §3），不在框内堆 `B×C×H×W`。
5. **层数不得被读成"有 N 个 stage"。** 若层数确实对应真实阶段数，
   那应该画 **stage 容器 + 平面块**，不是 tensor 堆叠。
6. 对应元素表一条记录（见 §7）。

## 5. 图像框（image frame）

**用途：** 暗示"这是图像类对象"（MRI / CT / 重建输出），
与模型块、tensor 堆叠在视觉上区分开。

**模板：**

```text
┌──────────────┐
│   MRI Input  │
│   [slice]    │
└──────────────┘
```

**规则：**

1. **占位角标固定为 `[image]` 或 `[slice]`。** 这是图像框的标记，
   便于人和脚本识别；不要自创别的角标。
2. **只用于材料里真实存在的图像类对象。** 输入是 k-space / raw 数据却画成图像框，
   属于**语义错误**（见 §6 约束 C）。
3. 与平面块的差别只在角标与居中排版，**不需要额外装饰**。
4. 对应元素表 `Type: data` 或 `output`（见 §7）。

## 6. 三类别约束

这三类是防止"为了像论文图而乱补细节"的核心。

### A. 允许哪些（能不能画的开关）

- 模型块用双线框 `╔═╗`；`enhanced` 档可再加伪 3D；
- 张量 / 特征图可用堆叠矩形；
- MRI / CT 类输入输出可用图像框；
- 轻量算子用 `[ FFT ]` 式单行节点。

### B. 什么时候才该用（防滥用）

**只在能改善沟通时用。** 满足任一即**不用**：

- 破坏对齐（框宽不等、右边框不齐）；
- 增加视觉噪声、淹没问题主线；
- 喧宾夺主（装饰压过方法逻辑）；
- 对理解没有帮助；
- 让 5–15 秒看懂主路径变得困难；
- 同一份图里已经出现两种以上框族（information overload）。

### C. 不要误导语义（硬约束）

- **形状暗示不得让人以为存在材料里没有的架构细节。**
- 不得因为"像 U-Net"就画成完整 U-Net——材料只支持"一个网络"时，
  就标 `Backbone`，不要画 encoder/decoder 分支。
- 没有张量语义时不得画 tensor 堆叠。
- **伪 3D 块在语义上仍然只是一个节点**：它的 `Inputs` / `Outputs` 必须与其他
  节点一致，**不得因为画得"立体"就暗示它做了额外计算**。
- **形状必须与元素表 `Type` 一致**：画成 `╔══╗` 却在表里登记成 `operator`，
  属于契约违规（`scripts/check_draft.py` 警告 W8）。

约束 C 的落点是 [evidence-policy.md](evidence-policy.md)（禁止补造）与
`SKILL.md` §0.2；违反属于契约违规，不是排版问题。

**反例（训练信号不要画成立体块或模型框）：**

```text
      ╭────────────╮
pred ─▶   Loss     │
gt   ──▶           │
      ╰────────────╯
```

## 7. 与元素表的接口

**原语不引入新的 `Type` 值。** 原语只是同一个节点的另一种画法：

| 原语 | 对应元素表 `Type` |
|---|---|
| 双线框 / 伪 3D 块 | `model`（或 `parameter` / `state`） |
| tensor 堆叠 | `state` 或 `data` |
| 图像框 | `data` 或 `output` |
| `[ FFT ]` 单行节点 | `operator` |

**硬规则：**

- 每个原语实例**恰好对应一条**元素表记录；
- 原语**不得**新增元素表行；
- 元素表的 `Inputs` / `Outputs` 语义不因画法改变；
- **一致性对**：tensor 堆叠里的层数若在元素表中没有对应记录，
  说明它是纯装饰，应当删掉。

## 8. 两个正交参数：`SKETCH_STYLE` 与 `SKETCH_VARIANTS`

**风格**与**产出份数**是两件事，不要混成一个参数。

### 8.1 `SKETCH_STYLE`（视觉风格）

| 值 | 行为 | 机器校验 |
|---|---|---|
| `auto`（**缺省**） | 由材料自行推断；推断结果按下面某一档执行 | 无额外限制 |
| `clean` | 只用平面框 / 双线框 / 方括号算子。**禁止**伪 3D / tensor 堆叠 / 图像框角标 | 违反 = 错误（E16） |
| `enhanced` | 三个新增原语可用，按 §3–§6 约束 | 超量 = 警告（W5 / W6） |
| `block_architecture` | 偏网络结构：强调 tensor path / skip / 分支汇合；优先 `╔═╗` 模型块 | 同上 |
| `stage_panel` | 偏多阶段：用大外框表达 Stage A/B/C、source/target、pretrain→adapt→recon | 同上 |
| `loop_centric` | 偏迭代：把 recurrence（`x_k → DC → Prior → x_{k+1}` + 回流线）放视觉中心 | 同上 |

**双线框与圆角框在 `clean` 档同样可用**——它们是平面形状，不带透视。

`block_architecture` / `stage_panel` / `loop_centric` **只是侧重**，不是新的禁用集；
它们不改变证据标准，也不改变 grammar 选择规则（§0）。

**风格与 `FIGURE_TYPE` 不绑定。** 同一个 `FIGURE_TYPE: optimization` 既可以是
`SKETCH_STYLE: clean`，也可以是 `enhanced` —— 见 [figure-types.md](figure-types.md)。

### 8.2 `SKETCH_VARIANTS`（产出份数）

| 值 | 行为 | 机器校验 |
|---|---|---|
| `single`（**缺省**） | 每份 Draft 段一个 `text` 块 | — |
| `both` | 每份 Draft 段给**两个** `text` 块：**先 clean，后 enhanced** | 缺一块 = 警告（W7） |

**默认不产出双份。** 需要"同结构另一种画法"对照时才显式写 `SKETCH_VARIANTS: both`。

**参数缺失时** `SKETCH_STYLE` 按 `auto`、`SKETCH_VARIANTS` 按 `single` 处理，
并在输出开头声明这是缺省值（与 `SKILL.md` §1 其他参数同规则）。
任一参数取枚举外的值判为错误（E17）。

### 8.3 `both` 模式下的关键约束

`both` 的两个 `text` 块**不是两份 draft**：

- 仍写在同一段 `## <n>. Draft <X> — <grammar>` 内，**共用一个 grammar**；
- **不占用新的 Draft 字母**；
- `Recommended: Draft <X>` 仍只按**结构**推荐，不得指向某个变体；
- **不得把两个变体算作多样性**——多样性只看 grammar 与信息分组
  （[visual-grammar.md](visual-grammar.md) §3/§4）。

## 9. 与 SVG Handoff 的接口

用原语时，在 `SVG Handoff Notes` 增加一行：

```text
Sketch primitives:       model (double-line) x2 (Flow Prior, Denoiser)；tensor stack x1 (multi-scale)；image frame x2 (MRI in, recon)
```

下游绘图代理据此决定哪些节点升级成实体块、哪些保持平面框。
**这一行只描述画法，不改变分组与线型语义。**

## 10. 机器校验

`scripts/check_draft.py` 实现的检查（条件见 [output-contract.md](output-contract.md) §9）：

| 检查 | 级别 | code |
|---|---|---|
| `SKETCH_STYLE: clean` 下出现伪 3D / tensor 堆叠 / 图像框角标 | 错误 | `E16` |
| `SKETCH_STYLE` 或 `SKETCH_VARIANTS` 取值不在枚举内 | 错误 | `E17` |
| 单份 draft 的 tensor 堆叠可见层数 > 5 | 警告 | `W5` |
| 单份 draft 的伪 3D 块 > 3 | 警告 | `W6` |
| `SKETCH_VARIANTS: both` 但某 Draft 段的 `text` 块少于 2 | 警告 | `W7` |
| 双线框 `╔` 未落到元素表的 `model` 行（追溯到非 `model` 行，或无法追溯） | 警告 | `W8` |
| 三个框族的边框对齐（单线 / 双线 / 圆角） | 警告 | `W4` |

脚本**只认几何签名**（斜角线、`├──┤` 分隔行、错位堆叠、`[image]`/`[slice]` 角标、
三个框族的角字符），**不判断该不该用**。§6 的 A / B / C 三类约束由
`SKILL.md` §8 自检清单负责——**脚本查得到的挂脚本，查不到的写进自检清单**，
不留"声明了却没有载体"的规则。

## 11. 高频模板库

具体场景的现成字符模板（U-Net、迭代求解、skip connection、train/infer 分栏、
source→target 适配、多尺度金字塔……）见
[sketch-templates.md](sketch-templates.md)。**那是模板库，不是强制清单**：
按 §1 的图例组合 4–8 个原语即可，不要为每个节点发明新形状。
