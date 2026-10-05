# <F<NNN>-<figure_type>> — Figure Draft

> 本文件是**骨架**，尖括号为占位符，不能直接当 draft 交付。
> 契约见 [references/output-contract.md](../references/output-contract.md)。

**参数（缺省值也要写出，并声明哪些是推断的）：**

```yaml
FIGURE_TYPE: <method-overview|architecture|training|inference|optimization|motivation|comparison|ablation>
DETAIL_LEVEL: <overview|medium|detailed>
NUM_DRAFTS: <2-5>
FOCUS: <重点表现什么 | 未给出，按 FIGURE_TYPE 默认侧重>
TARGET_PAPER: <目标会议/论文 | 未给出>
MUST_INCLUDE: [<模块>, ...]
MUST_NOT_INCLUDE: [<内容>, ...]
KNOWN_FACTS: [<用户确认的事实>, ...]
sources: [<代码根目录 / 论文路径 / 用户说明>]
```

---

## 1. Figure Understanding

<5–12 行：输入 / 输出 / 核心计算路径 / 训练关系 / inference 关系 / 核心贡献。
不要复述整篇论文。>

---

## 2. Evidence Summary

| Figure element | Evidence | Confidence |
|---|---|---|
| <视觉元素> | `<file.py::symbol()> / <Eq. (n)> / [user]` | <High\|Medium\|Low> |

---

### 2.1 多样性矩阵（自检用，非契约段）

> 用来证明 A/B/C 的差异是**结构性的**（[visual-grammar.md §3](../references/visual-grammar.md)）。

| 维度 | Draft A | Draft B | Draft C |
|---|---|---|---|
| 主阅读方向 | | | |
| 信息分组 | | | |
| 视觉中心 | | | |
| 抽象层级 | | | |
| train/inference 表达 | | | |
| 循环表达 | | | |

---

## 3. Draft A — <visual grammar>

> 设计意图：<一句话>。

```text
<字符图>
```

**Best for:**
- <适用场景>

**Strength:** <优点>

**Weakness:** <缺点>

---

## 4. Draft B — <visual grammar>

> 设计意图：<一句话>。

```text
<字符图>
```

**Best for:**
- <适用场景>

**Strength:** <优点>

**Weakness:** <缺点>

---

## 5. Draft C — <visual grammar>

> 设计意图：<一句话>。

```text
<字符图>
```

**Best for:**
- <适用场景>

**Strength:** <优点>

**Weakness:** <缺点>

---

## 6. Recommended Draft

**Recommended: Draft <X>**

Why:
1. <最清楚地突出论文贡献>
2. <training/inference 不易混淆>
3. <SVG 转换后容易形成视觉层级>
4. <箭头较少>
5. <对双栏论文缩放更友好>

---

## 7. Alignment Notes

```text
N1 <视觉标签>
└── <file.py::symbol()> 或 <Sec./Eq./Alg.>

N2 <视觉标签>
├── <source 1>
└── <source 2>
```

**语义聚合声明：**
`"<聚合名>" is a semantic abstraction of: <底层操作清单>.`

**命名映射：**
`<论文语义名> ↔ <源码名>`

---

## 8. Uncertainties

```text
Uncertain:
- <不能确认的结构>（U1）
- <不能确认的关系>（U2）
```

<无不确定项时写"无"。>

---

## 9. SVG Handoff Notes

```text
Canvas:                  <landscape|portrait>
Primary flow:            <left → right | top → bottom | cyclic | dual-column>
Suggested visual groups: <group1 / group2 / group3>
Visual emphasis:         <核心贡献，中心最重色>
Secondary elements:      <应弱化的元素>
Line semantics:          solid = inference-forward；dashed = training supervision；dotted = optional/conceptual
Styling hierarchy:       Level 1 = domain/stage container；Level 2 = major module；Level 3 = operator/loss
Color grouping:          <哪些框同色>
De-emphasize:            <哪些模块弱化>
Center node:             <哪个节点放中心>
Curved arrows:           <哪些箭头可弯曲>
Inset candidates:        <哪些部分可放 inset>
```

---

## 10. Figure Element Inventory

| ID | Type | Label | Group | Inputs | Outputs | Status |
|---|---|---|---|---|---|---|
| N1 | <type> | <论文语义名称> | <group> | — | N2 | <observed\|abstraction>[ · <frozen\|trainable\|train-only\|inference-only\|optional\|semantic>] |

<只登记已在图中出现的节点；不要为完整性虚构。>
