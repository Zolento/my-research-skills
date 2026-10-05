# 源码与论文阅读规范（S1 采集）

**不要只根据文件名判断结构。** 决定计算图的是函数体，不是目录名。

## 1. 代码：优先搜索这些入口

```
forward()        training_step()   train_step()      loss()
compute_loss()   criterion()       sample()          reconstruct()
solve()          solver()          update()          step()
inference()      predict()         encode()          decode()
configure_optimizers()            freeze() / requires_grad_
```

**检索顺序（自顶向下）：**

```
1. 训练入口（train.py / lightning_module / trainer）→ 拿到 loss 与优化对象
2. 模型定义（model / net / backbone）→ 拿到 tensor 流与分支
3. loss / objective 定义 → 拿到监督关系与 reference data 来源
4. 推理 / 重建脚本（inference.py / reconstruct.py / eval）→ 拿到部署期可用信息
5. config / yaml / argparse → 拿到冻结项、阶段、开关
```

**追踪链：**

```
input → preprocessing → main model → 中间变量 → loss/objective
      → 梯度路径 → output
```

**必须显式回答（否则不得进入 S2）：**

| 问题 | 证据来源 |
|---|---|
| 训练时输入是什么？推理时输入是什么？ | `training_step()` vs `inference()` / `reconstruct()` |
| 哪些 loss 只在训练存在？ | loss 定义是否出现在推理路径 |
| 哪些 reference data 推理不可见？ | fully-sampled / target 的读取位置 |
| 哪些网络被冻结？ | `requires_grad_(False)` / `eval()` / `detach()` / freeze 配置 |
| 哪些参数被更新？ | optimizer 的 `params` 列表 |
| 是否存在多个训练阶段？ | 多个 optimizer / 多个 loop / stage 配置 |
| 是否有迭代 solver？ | `for k in range(K)` 内既调用模型又做算子更新 |

## 2. 迭代 solver 的识别（高频误判点）

```python
for k in range(K):
    x = x - eta * A_H(A(x) - y)     # data consistency
    x = denoiser(x)                  # prior / neural module
```

**不要**画成 `measurement → Flow Model → reconstruction`。
正确抽象：

```
x_k → [Data Step] → [Prior Step] → x_{k+1}      （回流 K 次）
        ▲                ▲
   measurement y     Flow prior
```

**要区分两个层次：**

- **model architecture**（被调用的网络）；
- **optimization / reconstruction algorithm**（调用它的循环与更新规则）。

两者都要出现，且不能互相替代。

## 3. 多阶段训练

若存在 Stage 1/2/3，每个阶段都要记录：

```
- 该阶段可访问的数据；
- 该阶段冻结 / 更新的参数；
- 该阶段的 loss；
- 阶段之间的传递物（checkpoint / 初始化 / 特征）；
- 阶段边界是否构成 domain / source-free 约束。
```

## 4. 论文：优先看这些位置

```
Abstract → Method Overview → Method → Algorithm → Equation definitions
→ Figure captions → Implementation Details → Appendix
```

**记录：** 核心变量、数据流、模型组件、optimizer / solver、objective、conditioning、
source / target domain、frozen / trainable、training-only 操作、inference-only 操作。

**不要临摹已有 Figure**——它是证据之一，不是模板。目标是理解方法后**重新构图**。
若某模块只在 Figure 里出现而正文/公式无法确认，按 **D 级**处理（进 `Uncertainties`）。

## 5. 引用格式（写入 Evidence Summary 与 Alignment Notes）

| 来源 | 格式 | 例 |
|---|---|---|
| 代码符号 | `<file>::<symbol>()` | `solver.py::dc_step()` |
| 代码区间 | `<file>:L<a>-L<b>` | `train.py:L40-L58` |
| 论文章节 | `Sec. <n>[.<m>]` | `Sec. 3.2` |
| 公式 | `Eq. (<n>)` | `Eq. (8)` |
| 算法 | `Algorithm <n>` | `Algorithm 1` |
| 图注 | `Fig. <n> caption` | `Fig. 2 caption` |
| 用户陈述 | `[user]` | `[user] source-free 是硬约束` |
| 未能定位 | `[未在材料中定位]` | 同时进 `Uncertainties` |

**路径以「相对项目根」为准**，且**不写进主图**——主图只留论文级标签。

## 6. 采集阶段的常见错误

| 错误 | 后果 | 正确做法 |
|---|---|---|
| 只看 `README`/文件名 | 画出不存在的模块 | 读 `forward()` / `loss()` 实体 |
| 忽略 `detach()` / `eval()` | 冻结与可训练画混 | 逐参数检查梯度路径 |
| 忽略 split-mask / 数据增强 | 误判监督信号来源 | 追 `compute_loss()` 的输入 |
| 把 `argparse` 默认值当事实 | 画出未启用的分支 | 以 config 实际值与代码为准，标注来源 |
| 只看训练脚本 | inference 图丢失或出错 | 必读推理入口 |
| 论文 Figure 当模板 | 复制而非重构 | 用正文/公式重建关系 |
