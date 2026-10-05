# 视觉语法库（A–H）与多样性要求

**名称是封闭枚举**：Draft 标题里的 grammar 必须能匹配到下表的规范名
（`scripts/check_draft.py` 会校验）。

## 1. 八种 grammar

| 规范名 | 适用 | 主阅读方向 | 视觉中心 |
|---|---|---|---|
| **A. Linear Pipeline** | `Input → Process → Process → Output` | 左→右 | 中段关键模块 |
| **B. Dual / Multi Branch** | measurement branch / prior branch / conditioning branch 最终汇合 | 左→右 + 上下分叉 | 汇合点 / 融合处 |
| **C. Hierarchical System** | `system ├── solver │ ├── DC │ └── prior └── adaptation` | 上→下（含缩进树） | 顶层系统边界 |
| **D. Iterative Loop** | `x_k → update → x_{k+1}` | 环形 | 循环体 |
| **E. Train vs Inference** | 训练与推理左右 / 上下对照 | 双列对照 | 两区差异处 |
| **F. Data / Model / Objective** | 三个语义区 | 上→下三带 | Model 带 |
| **G. Source / Target Domain** | source pretraining → frozen prior → target adaptation | 上→下 + 分隔带 | 分隔带 / 适配阶段 |
| **H. Temporal / Stage View** | `Stage A → Stage B → Stage C` | 左→右（时间轴） | 最后阶段 / 变化量 |

**不要强行使用不符合方法的 grammar。** 例如方法本身没有循环，就不能为了好看画成
Iterative Loop。

## 2. 选择规则

1. 先看**方法真正的驱动结构**：是单程 pipeline、双分支汇合、迭代、还是阶段推进？
2. 再看 `FIGURE_TYPE`（见 [figure-types.md](figure-types.md)）要求的侧重。
3. 最后看 `FOCUS`：重点在哪，就把哪种 grammar 放在视觉中心。
4. 一份 draft 只用一个主 grammar；**不允许把两张图硬拼成一张**。

## 3. 多样性矩阵（强制填写）

`NUM_DRAFTS` 份 draft 必须在下列 6 维中**至少 2 维不同**（推荐 3 维）：

| 维度 | 取值示例 |
|---|---|
| 主阅读方向 | 左→右 / 上→下 / 环形 / 双列对照 |
| 信息分组方式 | 按 pipeline / 按 domain / 按 train-infer / 按 data-model-objective |
| 视觉中心 | 核心贡献 / 系统边界 / 汇合点 / 循环体 |
| 抽象层级 | overview（模块级）/ medium（算子级）/ detailed（tensor 级） |
| training/inference 表达 | 分区容器 / 双列对照 / 行内标记 |
| 循环表达 | 显式回流线 / `repeat K` 注释 / 未出现 |

**在文档开头（`Figure Understanding` 之后）用一张小表记录本矩阵**，便于审阅者确认
多样性是结构性的，不是 cosmetic 的。

## 4. 什么不算多样性（假多样性）

```
❌ 只改框大小 / 框的圆角
❌ 只改箭头方向（左→右 换成 上→下，但分组、中心、层级全一样）
❌ 只换几个近义词（"Prior Step" vs "Denoising Step"）
❌ 只是把同一张图拆成上下两半
```

**判据：把两份 draft 的字符图叠在一起，如果信息分组与视觉中心完全一致，
就是假多样性。**

## 5. 信息密度预算

字符 draft **不是代码调用图**。避免：

```text
❌ Conv → ReLU → Conv → Norm → ReLU → Conv → …
```

**除非这些层本身就是论文创新**。优先聚合成：

```text
┌─────────────────────┐
│ Reconstruction Net  │
└─────────────────────┘
```

只展示对理解**贡献 / 信息流 / 优化过程 / 核心创新**有帮助的结构。

| `DETAIL_LEVEL` | 建议节点数 | 建议层数 | 规则 |
|---|---|---|---|
| `overview` | 6–12 | 2–3 | 只留主干 + 核心创新；loss 可合并 |
| `medium` | 10–20 | 3–4 | 主干 + 关键算子 + 监督关系 |
| `detailed` | 20–35 | 4+ | 允许 solver 内部步骤与 tensor 级变量；仍禁止逐层展开 |

**超过 35 个节点基本可以判定是代码调用图**，需要重新聚合。

## 6. 与图类型的对应（速查）

| FIGURE_TYPE | 首选 grammar | 次选 |
|---|---|---|
| method-overview | A / F | B |
| architecture | B / C | A |
| training | E / F | G |
| inference | A / D | B |
| optimization | D / H | C |
| domain_adaptation | G（source→target） | E |
| motivation | F（问题→机制→洞见） | B |
| comparison | 统一语法的并列（同抽象层级） | H |
| ablation | H（阶段/变体视图） | F |

完整侧重与必备元素见 [figure-types.md](figure-types.md)。
