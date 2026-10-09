# Stagnation Breaker

Preset ID: `stagnation-breaker`  
Top-level Entry: `continue-research`  
Trigger: `event_or_manual`  
Execution Scope: `decision_only`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
连续有效闭环无独立预测/科学决策变化、候选结构指纹重复、AALG 诊断预算耗尽，或由运行轨迹观察到重复诊断。单次负结果不足以触发。

## 执行协议
1. 读取最近有效研究动作、结构签名、失败作用域、诊断预算及研究目标，区分工程卡死、优化卡住与建模范式卡住。
2. 计算可核验的停滞证据：相同机制前提、重复行动、预测/决策 delta 缺失；不以 Agent 主观感受作为触发依据。
3. 如果是工程故障，路由 `experiment-failure-recovery`；如果仍存在便宜且有区分力的判别干预，优先允许一次合法干预。
4. 仅当表征层停滞确立，输出 `paradigm-escape` 的单次触发建议/调度决策；保持原研究锚点和所有失败限制。
5. 同一状态快照和原因不可反复自触发；给出停止、冷却或等待新证据条件。

## 产出
停滞证据、分型、下一 preset 或实验、未触发理由及消除循环的检查点。
