# Research Loop Health Check

Preset ID: `loop-health-check`  
Top-level Entry: `continue-research`  
Trigger: `event_or_manual`  
Execution Scope: `inspect_only`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
每个有意义的科研闭环后或用户要求健康检查；长循环中可按现有调度频率进行，但不能占满研究计算预算。

## 执行协议
1. 从真实 action/evidence 日志检视重复动作、失败恢复次数、科学有效结果、机制预测、state delta、决策 delta 与实际资源消耗。
2. 区分科学无突破但实验有效、执行故障、伪进展（新增文档但无新证据）和正常探索。
3. 对触发阈值的类别只推荐相应 preset：context drift、stagnation、experiment failure、evidence conflict、resource；不自行跨权限执行。
4. 记录当前快照上已建议/已派遣的恢复动作，防止检查器和修复器循环触发。

## 产出
简短健康状态、触发证据、被推荐动作与是否已派遣、暂停/继续条件；不把代理自评作为核心度量。
