# Figure 语义模型（先有语义，后有布局）

**布局必须由关系产生，不能反过来为了布局修改算法。**

## 1. Entities（节点类型 — 与元素表 `Type` 同值域）

| Type | 含义 | 例 |
|---|---|---|
| `data` | 输入 / 观测 / 中间数据 | Undersampled k-space、Measurement y |
| `model` | 神经网络 / 参数化模块 | Flow prior、Reconstruction net |
| `operator` | 数学算子 / 处理步骤（非参数化） | DC step、Mask、FFT、Gradient update |
| `state` | 被迭代更新的量 | Current reconstruction x_k、velocity v |
| `objective` | loss / 目标函数 | Self-supervised loss、Eq. (7) |
| `parameter` | 参数集合 / checkpoint | θ、Source prior θ₀ |
| `supervision` | 监督信号 / reference data | Fully-sampled target、Split-mask measurement |
| `output` | 最终输出 | Reconstructed image |

## 2. Relations（边语义 — 每种关系有默认视觉表达）

| Relation | 含义 | 默认视觉表达 |
|---|---|---|
| `transforms` | A 经计算得到 B | 实线箭头 `───▶` |
| `conditions` | A 作为 B 的输入条件（不作为数据流） | 侧向实线箭头（从侧面进框） |
| `supervises` | A 监督 B | **虚线箭头** `─ ─ ▶` |
| `updates` | A 更新参数 B | 虚线/点线箭头，指向参数块 |
| `compares` | A 与 B 比较（loss 内部） | 汇入 loss 框的两条线 |
| `freezes` | A 冻结 B | `[FROZEN]` 标记，**无梯度箭头** |
| `initializes` | A 初始化 B | 点线箭头，标注 `init` |
| `iterates` | A 与 B 构成循环 | 回到起点的回流线 + `repeat K` |
| `branches` | A 分成多路 | 分叉符 `├─▶` / `└─▶` |
| `merges` | 多路合成 | 汇合符 `──┐ ├──▶` |

## 3. 生成 draft 前的内部十问（缺一即不得开工；答不出不得补全）

```
1  核心输入是什么？
2  最终输出是什么？
3  方法的核心创新位于哪里？（须来自用户说明或论文）
4  数据经过哪些真正重要的转换？
5  哪些路径只在训练存在？
6  哪些组件被冻结？
7  哪些变量被迭代更新？
8  loss 作用于什么？
9  是否存在 source / target / GT 泄漏问题？
10 哪些部分证据不足？
```

- 第 3 问答不出 ⇒ **不得**标 `[CORE CONTRIBUTION]`。
- 第 5、6 问答不出 ⇒ 该区域在图中标 `[未在材料中定位]` 并进 `Uncertainties`。
- 第 10 问的答案逐条映射成 `Uncertainties` 的 `U<k>` 条目。

## 4. 图必须分层级（不要把所有信息摊在一个平面）

```
Level 1  数据 / domain            ← 最外容器（stage / domain 带）
Level 2  核心算法模块              ← 视觉中心，最重
Level 3  loss / supervision / 更新 ← 侧向或下方，视觉次重
Level 4  输出                     ← 收束
```

复杂算法用嵌套：

```
Outer loop
    └── Inner solver
            ├── Data step
            └── Prior step
```

或上下分区：

```
Training
────────────────────

Inference
────────────────────
```

**层级决定 SVG 样式层级**（见 [output-contract.md §7](output-contract.md)）。

## 5. 训练 / 推理 / 冻结（强制可见）

| 检查 | 规则 |
|---|---|
| 输入集不同 | training 区与 inference 区**必须能一眼区分**（容器标题、分隔带、或左右分区） |
| reference data | fully-sampled 参考 / target / GT **只能出现在 training 区** |
| 训练专属 loss | 用虚线语义，**不得**画成 inference 输入 |
| 冻结 | `[FROZEN]`；**不得**有梯度箭头指向它 |
| 可训练 | `[TRAINABLE]`；有指向它的 `updates` 边 |
| 多阶段 | 必须标出每阶段：哪些参数冻结 / 更新、哪些数据可访问 |
| 约束类方法 | source-free / zero-shot / unpaired 是**方法定义**，用分隔带表达（`──────── NO SOURCE DATA ────────`），不能只写在 caption |

**典型错误对照：**

```text
❌ 错误（把 GT 画进 inference）
INFERENCE
target y ────────┐
                 ▼
input x → model → prediction

✅ 正确
TRAINING
target y ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
                                ▼
input x → model → prediction → [Loss] ─ ─▶ update θ

INFERENCE
input x → model → prediction        （无 target）
```

## 6. 迭代方法必须画成 recurrence

如果存在 iterative solver，**不得**压成单程 pipeline：

```text
❌ measurement → Flow Model → reconstruction      （若真值是 solver + prior 联合结果）

✅
              ┌───────────────────────┐
              │                       │
              ▼                       │
x_k ───▶ Data Step ───▶ Prior Step ───▶ x_{k+1}
              ▲              ▲
              │              │
        measurement y    Flow prior
```

**model architecture** 与 **optimization / reconstruction algorithm** 是两个层次：前者是
被调用的模块，后者是调用它的循环。两者都要出现，且**不得互相替代**。

## 7. 因果链优先（而不是文件结构）

读者应能顺次回答：

```
输入是什么？ → 发生了什么？ → 为什么需要核心模块？ → 核心模块改变了什么？ → 最后输出什么？
```

**不要**按文件 / 类的组织结构画图（那是代码调用图，不是论文图）。

## 8. 冻结组件写法（emoji 不可用时的回退）

```text
┌────────────────────┐        ┌────────────────────┐
│ Source Prior       │        │ Source Prior       │
│ [FROZEN]           │  或    │ (frozen)           │
└────────────────────┘        └────────────────────┘
```

**同一份 draft 内保持一种写法**，不要混用 `🔒` 与 `[FROZEN]`。
