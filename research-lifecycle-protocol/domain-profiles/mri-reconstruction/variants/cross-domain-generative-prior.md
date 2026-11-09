# Variant: Cross-Domain Generative Prior（CT→MRI 先验适配）

> 任务级配置样例：以当前 CT-FM 研究为回放样例。参数以项目契约为准，本文只冻结
> **研究策略与评价边界**；数值示例不是所有 MRI 项目的默认值。

## 1. 任务形态

- CT → MRI 迁移：冻结的 CT 域 flow matching 生成先验，适配到欠采样多线圈 MRI。
- 目标域自监督微调 / 欠采样 MRI 后验修正（SSDU 类信息边界，见 `../ssl-contract.md`）。

典型冻结配置（`domain/<profile>.json` 的 `frozen`）：

```jsonc
{"components": ["ct-fm backbone", "fm time distribution", "fbs 100 steps",
                "forward operator", "sampling mask"],
 "forbidden_changes": ["主干权重", "时间分布", "推理算法步数", "采样协议"]}
```

适配容量：小参数 adapter / bypass 模块；`control_condition.capacity_matched: true` 必填。

## 2. 研究策略（MMS 方向优先级）

优先探究（方向 → 具体问题）：

| 方向 | 问题 |
|---|---|
| `prior_posterior_adaptation` | 为什么来源先验不能充分匹配目标域？测量条件信息如何影响适配？ |
| `representation_inductive_bias` | 有效适配容量与参数数量是否一致？adapter 的归纳偏置够不够表达目标域修正？ |
| `measurement_prior_coupling` | 后验修正对完整 FBS 重建轨迹的影响发生在哪些步骤？哪些测量方向约束修正？ |
| `ssl_information_use` | 目标域自监督微调的监督信息效率；objective mismatch 是否来自时间分布失配 |

**不允许因为困难而默认建议修改冻结条件。** "解冻主干/加步数/改采样"是 C 类变更
（用户授权），不是方法探索的默认出口。在冻结边界内仍可改变的数学对象包括：
adapter 结构与参数化、近端步中的先验加权、测量条件化项、蒸馏/一致性目标、
训练-推理动力学的耦合方式。

## 3. 评价边界

- 主指标：目标域重建指标（全图）；结构指标按锚点声明。
- **先验域指标（CT 域 FID 等）不得作为 MRI 重建改进的证据。**
- SSL 损失改善 ⇏ 重建改善（见 `../evaluation-policy.md` §1）。
- 阈值在结果前冻结；与 baseline（冻结 CT-FM 无 adapter、随机初始化 adapter 等容量对照）
  比较时预算必须一致。

## 4. 归因纪律（TAG）

该任务的历史高频平凡归因：`forward_operator_mismatch`（"MRI 算子太复杂"）、
`conditioning`（"FBS 100 步病态"）、`noise_level`、`overstrong_prior`。
同一指纹重复归因会被 TAG 判为 `REPEATED_ATTRIBUTION`；合法去向是
MMS 菜单中未拥挤的方向，或带新证据的判别实验（`NOVEL_DECISION_RELEVANT_DIAGNOSIS`）。

已验证的物理限制（若有）必须带适用范围记录；范围内不得虚构可行改进。
