# Hypothesis Portfolio Rebalance

Preset ID: `hypothesis-rebalance`  
Top-level Entry: `explore`  
Trigger: `manual_or_scheduled`  
Execution Scope: `portfolio`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
当当前 Hypothesis Portfolio 被单一假设、同构结构或同一个学习算子支配时，恢复多样性与风险分散。

## 执行协议
1. 从当前 QD archive、结构签名、机制模型、否证约束中识别重复组合；比较不同 niche 的贡献和证据覆盖。
2. 明确哪些假设是同义变体、哪些在不同观察或干预下给出实质不同的预测；不凭词面多样性判定创新。
3. 调用现有 P1—P6 及 R4/R6 的隔离种群规则，允许反转占优假设并保留少量高风险高发现潜力方向。
4. 结合预算、证据等级与研究锚点提出 retain / pause / explore；淘汰不得跨越有效否证作用域，也不得自动改主锚点。
5. 与合法调度器衔接，输出具体候选和将改变的下一次动作；无派遣接口时只报告建议。

## 产出
组合集中度、结构差异、新假设独立预测、重新平衡建议与追踪引用。
