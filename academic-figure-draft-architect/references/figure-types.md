# FIGURE_TYPE 侧重与必备元素

`FIGURE_TYPE` 决定**强调什么 / 省略什么**，不改变证据标准。
**缺省 `auto`**：由材料自行推断出下表之一，并在输出开头声明推断结果
（推断规则见 `SKILL.md` §1.1）。

## 速查

| FIGURE_TYPE | 强调 | 首选 grammar | 必备元素 | 典型错误 |
|---|---|---|---|---|
| `method-overview` | problem → proposed method → output | A / F | 问题输入、核心方法块、输出；loss 可合并 | 塞底层实现细节；核心创新淹没在细节里 |
| `architecture` | tensor path / branch / merge / skip / conditioning | B / C | 输入张量、分支、汇合、conditioning 入口、输出张量 | 分支标注不清；把 conditioning 画成数据流 |
| `training` | data / loss / gradient / trainable-frozen | E / F | 训练输入、reference data、loss、梯度、冻结标记 | 把 loss 画成 inference 输入；冻结块有梯度箭头 |
| `inference` | 部署期可得信息 / solver-model 交互 / 最终输出 | A / D | 部署期输入集（明确排除 GT）、main path、输出 | 画出 target / 参考数据 |
| `optimization` | 状态 x_k / operator / update rule / iteration | D / H | 状态变量、算子、更新规则、迭代次数、初值 | 压成单程 pipeline；缺 prev → next 闭合 |
| `domain_adaptation` | source → 冻结/迁移 → target 的数据可用性变化 | G / E | source 阶段、checkpoint / 迁移接口、target 阶段、**数据可用性约束** | 把 source 数据画成 target 阶段可得；冻结与可训练混淆 |
| `motivation` | 现有问题 / 失败机制 / 提出的洞见 / 预期纠正 | F / B | 失败机制、why、提出的洞见 | 把 hypothesis 画成已验证事实 |
| `comparison` | 各方法**同一抽象层级**的并列 | 统一语法的并列 / H | 基线、本方法、共享的输入输出 | baseline 一个框 vs 本方法十几个框（不公平视觉比较） |
| `ablation` | 变体 / 阶段差异 | H / F | 基准配置、被移除 / 替换的组件、共享部分 | 变体抽象层级不一致 |

## 各类型细则

### method-overview

- 强调 `problem → proposed method → output`，**避免底层实现细节**。
- 5–15 秒能回答：谁进来、什么新、怎么流、优化什么、出什么。
- loss 通常可聚合为一个 objective 块，或用侧向虚线表示。

### architecture

- 强调 **tensor path**：输入张量形状/语义、分支、汇合、skip、conditioning。
- conditioning 输入**从侧面进入**，不要画成主流数据。
- skip connection 必须双向可读；分支后必须能看出汇合点。

### training

- 强调 data / loss / gradient / trainable / frozen。
- **必须**区分：训练期输入 vs 推理期输入；哪些 loss 只在训练；
  哪些 reference data 训练才可见。
- 多阶段训练必须画阶段边界与参数冻结状态。

### inference

- 强调**部署期真正可用的信息**。
- 若方法是 solver + prior 联合重建，必须画出两者交互与迭代，不得只画 `measurement → model`。
- **任何 GT / target / fully-sampled reference 出现在 inference 区 = 契约违规。**

### optimization

- 强调状态 `x_k`、operator、update rule、iteration。
- recurrence 必须闭合（回流线 + `repeat K`）。
- 若同时有 model architecture，需在同一图中体现"被调用的模型"与"调用它的循环"两个层次。

### domain_adaptation

- 强调 **source → 迁移接口 → target** 的流程与**数据可用性边界**。
- **必须画分隔带**表达 source-free / zero-shot / unpaired 等约束
  （例：`──────── NO SOURCE DATA AVAILABLE ────────`）。
- checkpoint / prior 的**冻结与可训练状态必须可见**；迁移接口（adapter / finetune）
  要标出它属于哪一侧。
- source 阶段的数据**不得**出现在 target 阶段的输入里。

### motivation

- 强调：existing problem → failure mechanism → proposed insight → expected correction。
- **hypothesis 不得画成 established fact**：用 `[?]` 标记，并列入 `Uncertainties`。
- failure mechanism 需有来源（论文分析 / 实验现象 / 用户说明），不得凭常识编造。

### comparison

- **保持各方法抽象层级一致**：同一组组件在两条分支里必须是同样粒度。
- 避免 `baseline = 一个框 / our method = 十几个框` 造成的不公平视觉比较。
- 共享部分应显式共享（同色 / 同框），差异部分才是视觉重点。

### ablation

- 强调变体之间**只差什么**；共享组件不要重复放大。
- 抽象层级与主图一致，便于读者对照主图。

## 与 `DETAIL_LEVEL` 的组合

| DETAIL_LEVEL | method-overview | architecture | optimization |
|---|---|---|---|
| `overview` | 只留主干 + 1 个贡献块 | 只留主要分支与汇合 | 只画 1 个更新步 + 回流 |
| `medium` | 主干 + 监督关系 | 分支 / skip / conditioning 全出 | 更新步内部两类算子 |
| `detailed` | 主干 + 关键算子 | 张量级标注 | 初值、K、收敛相关结构 |

密度上限见 [visual-grammar.md §5](visual-grammar.md)。
