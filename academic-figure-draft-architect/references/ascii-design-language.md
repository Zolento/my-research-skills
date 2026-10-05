# 字符图设计语言（字形 / 线型 / 宽度）

字符 draft 也要按**论文 figure** 的标准画：balanced、spacious、aligned、minimal、
clear hierarchy、clear visual center。

## 1. 字形集（只用这些，保证跨字体稳定）

```
框：      ┌ ─ ┐    │    └ ┘    ├ ┤ ┬ ┴ ┼
箭头：    ▶ ◀ ▲ ▼      → ← ↑ ↓      ─  │
分叉：    ├─▶  └─▶  ──▶  ──┐  ┌──  ──┘  └──
循环：    回流线用 ─ ┐ ┌ ┘ │ 组成闭环，并在旁标 repeat K
分隔：    ═══════ 或 ────────  （domain / stage 分隔带）
标记：    [FROZEN] [TRAINABLE] [TRAIN ONLY] [INFERENCE ONLY]
          [CORE CONTRIBUTION] [? uncertain]
变量：    纯文本 + Unicode 下标（x_k、x_{k+1}、v_θ、θ₀）
```

**回退原则：** emoji（`🔒`）在部分字体下破坏对齐，**优先用方括号标记**；
一份 draft 内只用一种冻结写法。

**`[? label]` 的语义：** 它是 **D 级占位**，不是框、不是箭头、**不占元素 ID、不进元素表**；
`label` 必须同时出现在 `Uncertainties`。材料其实支持该模块存在、只是"是否启用/是否共享
参数"待确认时，不要降级成 D —— 用 `observed · optional` + 注释。

**禁止：** 依赖 ANSI 颜色、依赖特定字体、依赖渲染器才能看懂的图。字符图必须在
**纯文本 Markdown monospace** 下可读。

## 2. 线型语义（全文一致，写进 SVG Handoff）

| 线型 | 字符 | 语义 |
|---|---|---|
| 实线 | `───▶` | inference / 前向计算 |
| 虚线 | `─ ─ ▶` | training supervision（loss、target、gradient） |
| 点线 | `┈┈┈▶` 或 `···▶` | optional / conceptual / initializes |
| 双线 | `═══▶` | 分隔带（domain / stage 边界），不是数据流 |

**同一语义在所有 draft 中保持同一种线型**；不同语义**不得**共用同一种线型。

## 3. 中英混排宽度（对齐的根本规则）

> **显示宽度 ≠ 字符数。** 中日韩字符占 **2 列**，ASCII 与制表符占 **1 列**。
> 这是字符图错位的唯一主因。

**约定（脚本同此）：**

| 字符类别 | East Asian Width | 计宽 |
|---|---|---|
| ASCII、数字、希腊字母、上下标 | Na / N | 1 |
| 中日韩统一表意文字、全角标点 | W / F | **2** |
| 制表符 `─ │ ┌ ┐ └ ┘ ├ ┤` | A（Ambiguous） | **1** |

**做法：**

1. **优先英文技术标签**（论文图本来就是英文），中文只用于旁注；
2. 含中文的行，**按 `2 × 中文字数` 补齐空格**；
3. **同级模块框宽必须接近**；框宽用显示宽度算，不是字符数；
4. 框的上下边界显示宽度必须相等，内部行的右边框必须落在同一显示列。

**错位示例：**

```text
❌ 不等宽（中文按 1 列算了）
┌──────────────┐
│ Encoding 编码 │
└──────────────┘

✅ 正确（"编码" = 4 列）
┌────────────────┐
│ Encoding 编码  │
└────────────────┘
```

**自检捷径：** 把 draft 贴进等宽终端（或 `scripts/check_draft.py`）核对右边框是否成一条
垂直线。脚本会以**警告**报告"框上下边界宽度不一致 / 右边框不齐 / 角字符不配对"，
`--strict` 下升级为错误。

## 4. train / inference / frozen 的字符表达

```text
TRAINING ────────────────────────────────
target y ─ ─ ─ ─ ─ ─ ┐
                     ▼
input x ─▶ [Model] ─▶ prediction ─▶ [Loss] ─ ─▶ update θ

INFERENCE ───────────────────────────────
input x ─▶ [Model] ─▶ prediction        （无 target）

┌────────────────────┐
│ Source Prior θ₀    │
│ [FROZEN]           │
└────────────────────┘
```

**规则：** 训练专属的线一律虚线；inference 区不得出现 target / 参考数据；
冻结块不得有指向它的 `updates` 边。

## 5. 样式层级（决定 SVG 的层级）

| 层级 | 字符表达 | SVG 对应 |
|---|---|---|
| **Level 1** domain / stage 容器 | `═══` 分隔带 + 大写标题，或大框 | 背景带 / 容器 |
| **Level 2** 主要模块 | 双线或粗框 `┏━┓` / 常规模块框 | 主要 group |
| **Level 3** 算子 / loss / 标记 | 小框、单行框、方括号标记 | 次要 group |
| **Level 4** 注释 | 无框文本、`repeat K`、`[TRAIN ONLY]` | 无框文本 |

**视觉中心 = 核心贡献模块**，用最重的框；auxiliary 信息（measurement operator、
frozen checkpoint）用最轻的画法。

## 6. 美观硬规则

- 同级模块**框宽接近**，左右尽量对称；
- **避免交叉箭头**；必须交叉时用弯曲走线并保持不穿过框体；
- **避免过长箭头**；长距离用分段或中间节点；
- 用**空白**表达 semantic grouping（不同 group 之间至少 1 行空行）；
- **loss 用虚线或侧向箭头**，不要与主数据流同权重；
- **循环结构要让 reader 一眼看到 recurrence**（回流线闭合成环，不是断开的箭头）；
- 核心创新在**中心**，auxiliary 不得抢占中心；
- 每行不超过约 **100 显示列**，保证双栏论文缩放后可读。

## 7. 反模式清单

```
❌ 逐层展开 Conv/ReLU/Norm …（除非是创新点）
❌ 用源码变量名做标签（tmp_x / pred2）
❌ 所有节点一样大的框，没有视觉中心
❌ 训练监督用实线，看起来像 inference 输入
❌ 把 GT 画在 inference 区
❌ 中文标签不补宽度导致右边框歪斜
❌ 一张图塞进两个互不相干的 story
❌ 用颜色/emoji 表达关键语义（渲染环境不可控）
```
