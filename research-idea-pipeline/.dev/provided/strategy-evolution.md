# Strategy Evolution

Preset ID: `strategy-evolution`  
Top-level Entry: `continue-research`  
Trigger: `manual_or_scheduled`  
Execution Scope: `strategy_update`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
利用历史研究表现调整探索算子及下一动作选择，不改变科学证据与硬门禁。

## 执行协议
1. 汇集可信的操作者表现：可区分预测、有效干预、无效诊断、结构重复、证据质量、成本。限制于相同或可比的问题结构，不以自评创新分替代反馈。
2. 复用现有 Strategy Memory 生成有 provenance 的候选策略更新，并保留 exploration floor、失效范围和重新激活条件。
3. 检查当前 Scheduler 是否有实际消费建议的 Strategy Decision Adapter：只能在同等合法、同等硬优先级的动作中调整顺序，不允许改 AALG、锚点、预算或证据规则。
4. 若有 adapter，比较**相同** state_version、合法动作集合、固定规则下 with-memory / without-memory 的行动排序或选择；记录 baseline、applied、decision_changed、dispatch_status 与不变原因。
5. 若没有 adapter，**必须明确输出 `recommendation_only`，不得声称 L2 实际策略进化**；提出消费接口的工程缺口，但不能伪造 `strategy_applied=true`。
6. 候选策略只有经独立 Replay/对照验证才可声称带来科研能力改进；实际策略应用不等于 Insight 增益。

## 产出
L1 建议、L2 实际调度影响证据、L3 独立效果证据，分别标记 verified/unverified；下一步合法探索动作。
