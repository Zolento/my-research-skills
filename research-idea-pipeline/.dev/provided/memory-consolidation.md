# Cognitive Memory Consolidation

Preset ID: `memory-consolidation`  
Top-level Entry: `continue-research`  
Trigger: `event_or_manual`  
Execution Scope: `derived_only`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
合法 R11 更新、机制修订、新会话恢复或认知索引版本落后于 canonical State。

## 执行协议
1. 根据 canonical State、正式预注册、有效实验和 provenance 重新构建认知索引；复用已有 cognition build/check，勿重写权威事实。
2. 合并同义机制索引但保留不同适用范围、版本、失败条件和原始 ID；被否证机制保留为有范围的负面知识。
3. 对旧预测、异常和认知修订标记 valid / stale / unresolved；历史无法恢复的预测标记 retrospective/unknown，不得追认冻结。
4. 生成精简 Hot/Warm 上下文摘要；核对 State version、引用、过期传播和跨会话加载。
5. 若仅为派生投影更新，不能上调 Claim、Insight 或 Scheduler 成功指标。

## 产出
更新的索引、实际变化/失效传播、版本核验和可恢复性检查结果。
