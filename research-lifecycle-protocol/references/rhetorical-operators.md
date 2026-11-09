# Rhetorical Operator Registry

本文件的 JSON 是 MVP 的机器权威；生成器与 RE validator 读取同一份 registry。
算子只能作用于已经冻结的 scientific narrative。

```json
{
  "evidence_framing": {
    "allowed": ["comparator_forward", "effect_forward", "consistency_forward", "evidence_reordering"],
    "frozen": ["metric", "values", "aggregation", "uncertainty", "conditions", "interpretation", "statistical_status"]
  },
  "contribution_stance": {
    "allowed": ["explicit_prior_delta", "explicit_contribution", "contribution_salience"],
    "frozen": ["novelty", "priority", "scope", "prior_work_identity", "scientific_delta", "contribution_order"]
  },
  "budget": {"max_variants": 4, "max_rounds": 1},
  "profiles": {
    "neutral": [],
    "evidence-forward": ["comparator_forward", "effect_forward", "consistency_forward", "evidence_reordering"],
    "contribution-forward": ["explicit_prior_delta", "explicit_contribution", "contribution_salience"],
    "slightly-conservative": ["explicit_prior_delta"]
  }
}
```

| 算子 | 行为 | 前提 / 拒绝条件 |
|---|---|---|
| comparator_forward | 将 comparator 标签和已有比较内容放到 evidence 前 | 不选择新 comparator，不改变优劣方向 |
| effect_forward | 显示“Reported comparison / effect”标签，提前已有结果 | 保留 metric/数值/单位/aggregation/统计状态；不计算新 effect |
| consistency_forward | 将既有 interpretation 与数值并列展示 | 无一致性证据时不新增 consistent/robust 断言 |
| evidence_reordering | 提前 S5，保留全部 Ci ← Ej | 不删除负证据，不把局部 evidence 扩为全局 |
| explicit_prior_delta | 显示 closest prior work 与实际 delta | 差异必须已有来源；无来源标 gap 并停下 |
| explicit_contribution | 明确显示 actual contribution 标签 | 不把工程组合变成新的 scientific knowledge |
| contribution_salience | 提前 S2/S4，保持 frozen hierarchy | 不改变 central claim、科学贡献顺序或 priority |

稍保守 profile 只增加“Frozen scope and uncertainty apply”提示，保留同一 certainty；
不能把 supported 改成 tentative，也不能用保守语气删掉 contribution。
所有 profile 都把 scope、uncertainty、assumptions、limitations、failure cases 放在同一
前部位置；不把弱点推到结尾或附录。

**允许优化：** evidence visibility、claim clarity、actual prior-work delta、information
ordering、reviewer comprehension、ambiguity。
**禁止优化：** maximize reviewer score、hide weaknesses、reduce visibility of limitations、
inflate novelty、inflate scope、repeat positive adjectives、optimize toward one reviewer model、
recursive reviewer hill-climbing without bounds。

Strength visibility optimization, not weakness laundering.
预算和 judge 面板必须在看恢复结果前固定；失败只报告，不通过追加 wording 搜索追分。
未来的 abstract salience、bounded scope framing、technical register、linguistic complexity
不属于本分支新增算子。
冻结与审计规则见 [rhetoric-equivalence-policy.md](rhetoric-equivalence-policy.md)。
