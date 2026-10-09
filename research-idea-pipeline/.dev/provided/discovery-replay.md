# Discovery Replay Evaluation

Preset ID: `discovery-replay`  
Top-level Entry: `continue-research`  
Trigger: `manual_or_scheduled`  
Execution Scope: `evaluation_only`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
评价 CIE / Strategy Evolution 是否真的改善科学发现和下一动作质量，而不是证明 Prompt 看起来更好。

## 执行协议
1. 使用现有 research_replay / fixture 机制，选择含历史冻结点、隐藏后续结果和独立答案来源的案例。隔离隐藏信息，防止被检索索引、Memory 或候选生成提前看到。
2. 用相同初始 State、模型、预算、合法工具、停止标准比较 baseline 与新策略；尽可能多次重复运行并控制随机波动。
3. 评估：有效预测准确/校准、判别干预质量、结构创新、无价值诊断次数、下一决策变化、科学证据有效性与资源消耗。
4. 不把候选生成 Agent 的自评当作主要评判；已知历史结论或独立验证与盲评优先。
5. 清楚区分单元测试、合成端到端、真实 Agent A/B 和真实科学新发现的证据等级。策略未优于 baseline 应保留旧策略或标记试验性，不自动晋升。

## 产出
复现实验条件、隔离校验、对照结果与不确定性、是否建议 promotion 和尚未验证的推断。
