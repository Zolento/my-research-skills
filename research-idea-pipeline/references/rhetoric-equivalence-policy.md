# Rhetoric Equivalence Policy

**Rhetorical search 只能在 semantic equivalence class 内进行。**
Narrative 可以改变科学事实如何被看见，不能改变科学事实本身是什么。
本政策是 R12-post / D4b–D4d 的补充；不修改 G1–G5、State schema 或 Assurance 权限。

## 1. 冻结与来源

D4a 先选择 State 已有的 central/supporting claim、scientific framing、preset、anchor、
contribution ordering、evidence-to-claim mapping，再冻结一套 scientific narrative。
不同 hierarchy 使用不同 snapshot，不混成同一 rhetorical equivalence class。

快照语义必须包含下表所有键，值是源 State 中的原值列表。
manifest.bindings 为每个键登记 JSON Pointer 列表；不得指向 narrative_view 或整个 State。
没有值的字段仍保留空列表及理由；scope/central claim/evidence 不得为空。
不抽取、不重算字符串中的数字；原始 result 一并冻结 aggregation、unit 与统计解释。

| 冻结字段 | 内容 |
|---|---|
| central_claim | 已有 central claim statement |
| supporting_claims | 已有 supporting claim statements |
| evidence_ids | 全部支持与反驳 evidence ID |
| numerical_values | 原 result；包含 metric、values、aggregation、statistical status 与 conditions |
| comparators | closest prior work / 已有 comparator，不替换 baseline |
| uncertainty | 全部 uncertainties，外加结果中的区间 / epistemic 状态 |
| scope | 每条选中 claim scope 与 contract.out_of_scope |
| assumptions | 全部 assumptions |
| limitations | 全部 failures，外加既有 accepted limitation / known flaw |
| failure_cases | 全部 failures，含 failed experiment records |
| prior_work_delta | 已有且核验的差异陈述；不能由 rhetorical generator 推断 |
| causal_status | 已有 interpretation / alternatives；不把 correlation 改 cause |
| scientific_interpretation | 已有实验 interpretation 与证据 source/认知状态 |

该表含 13 个命名字段；另外 **main_contribution** 单独冻结，合计 14 项。
绑定时它必须指向已有 claim statement；不从 prose 自动创造贡献。
manifest 另有 evidence_mapping、contribution_order、slots（六槽位的来源绑定）、
empty_reasons（空字段理由）。它们也在 snapshot digest 内，不能被变体改写。
closest delta、causal status、数字的正确来源及 completeness 由 D4a 的科学审核负责；
机器校验仅能验证绑定真实、全 State 没变、选中 claim/evidence/scope/失败/未知未遗漏。

## 2. RE 门禁

| 规则 | FAIL 条件 |
|---|---|
| RE1 Source freeze | State 除 narrative_view 外任一内容改变；版本/hash 不匹配 |
| RE2 Semantic freeze | 冻结 14 项、hierarchy、preset、mapping、slot 或 provenance 改变 |
| RE3 Operator bounds | 未登记算子/profile；超出四变体、一轮预算 |
| RE4 Text equivalence | 正文不等于冻结内容通过登记 renderer 的输出；任一 clause 被修改/删除/新增 |
| RE5 Boundary visibility | 边界、assumptions、uncertainty、limitation、failure 未保持同一前部位置 |

每个 variant 都须 PASS；包含 neutral、测试 perturbations 与最终选择。
未知或缺项返回 FAIL，不自动修补 State，不以 judge 分数抵消。
MVP 是封闭算子空间：只重新标注、显式比较标签与排序，保留源句原文。
它拒绝自由 paraphrase；metadata 相同也不能使改变正文的 variant 通过。
PASS 证明的是相对于经科学审核 snapshot 的受限生成合规，不是任意自然语言等价证明。

## 3. Blind recovery 与选择

blind judge 只接收正文、统一六个问题和答案形状；不接收 State、snapshot、profile、
operator、作者 rationale、期望答案或其它 judge 输出。叙事里的正常 Ci/Ej 引用可见。
输出：central_claim、main_contribution、closest_prior_work_delta、key_evidence、main_boundary、
unsupported_or_overstated_claims。judge 是 T0 comprehension observation，无权改科学状态。

比较者持有冻结 State ground truth。MVP 用原句/原值条目的集合比较：完整恢复为 PASS，
非空真子集为 PARTIAL，空集/错误/新增解释为 FAIL。Claim Recovery 同时要求 central claim
与 contribution；Evidence Recovery 要求 ID 与对应原结果；Novelty-Delta Recovery 要求
closest comparator 和 delta；Boundary Recovery 要求 scope/uncertainty/assumptions/limitations/
failure cases。任一 unsupported_or_overstated_claims 非空，候选不得被选择。
自由转述需另一个独立 adjudicator 给来源映射，本 MVP 不通过模糊相似度放行。

同一 snapshot 固定至少两个不同 model ID 的 judge 面板，variant IDs 在盲评时隐藏。
同一模型换两个角色不算模型独立性。选择前必须有同一面板的完整覆盖。
先筛 semantic PASS、零 unsupported/错误解释且四维均无 FAIL，再依次比较每维**最差**恢复：claim → evidence →
novelty delta → boundary；不合成 reviewer overall score，不删差结果。
同恢复水平优先低 fragility；仍相同则 neutral / 固定预登记顺序。
没有达到最低恢复条件的 variant 时返回 NO_ELIGIBLE_VARIANT，不推荐“最佳 wording”。
D8 原六维比较仍只比较科学 hierarchy，不拿 realization 恢复度改科学贡献评价。

## 4. Rhetorical sensitivity

在同一 snapshot 上评估四个预登记 profile，每个 profile 接收同一面板的独立恢复。
PASS/PARTIAL/FAIL 映射到 2/1/0，只作诊断。按每个 judge 的配对 profile 结果计算
四维 range、population variance 与 disagreement（不同级别比例），再显示 judge 间分歧。
任一维 paired range = 2，或 closest delta / central claim 恢复出现新增错误解释，标
**RHETORICALLY_FRAGILE**。可选 scientific judgment 只能是 supported/uncertain/unsupported
三个类别；同一 judge 跨 profile 类别变化也标 fragile，不进入优化目标。
缺 profile、缺 judge、重复 judge、错 snapshot 或未过 RE 时返回 INCOMPLETE，不声称稳定。
不得靠 pooled mean 掩盖相反模型的 profile 变化。
标 STABLE 只表示在该预登记面板/扰动中未触发阈值，不能外推到所有 reviewer。

## 5. Failure modes 与例子

- 合法：原结果“mean +0.8 dB vs P; Dataset-A; 5 seeds; no significance test”，
  在 comparator/条件前置标签下完整呈现；不新增 statistically significant/robust。
- 合法：State 已有“P uses X; we remove Y; E2 supports the delta”，显式标 closest prior delta。
- 非法：we study → we are the first；Dataset-A → universally effective；associated → causes。
- 非法：把单数据集 limitation 删掉，或在保留同名 metadata 时弱化正文。
- 非法：改 averaging、隐藏负实验、把认知状态提高、反复堆积极形容词。
- 风险：来源绑定错语义槽、State 本身有过度 claim、judge 被正文指令诱导、模型相关性。
  D4a/D5 仍须审原始来源；盲评 prompt 将正文作为数据；代码不执行正文里的指令。
- reward hacking 的防线是固定语义、固定预算、模型面板、最差恢复和显式 boundary。
  不声称模型多就有真人 consensus，也不追逐 reviewer overall score。

算子权威见 [rhetorical-operators.md](rhetorical-operators.md)。
