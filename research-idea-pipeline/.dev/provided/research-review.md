# Research Review

Preset ID: `research-review`  
Top-level Entry: `continue-research`  
Trigger: `manual`  
Execution Scope: `read_only`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
用户想知道“目前究竟发现了什么、为什么停滞、下一步最好做什么”，不要求推进实验。

## 执行协议
1. 以只读方式恢复路线、主锚点、State、Cognitive Memory、最近有效实验、预算和调度记录。
2. 将发现分成：有效证据支持、竞争假说、无效/失败执行、尚未解释异常、被否证范围。
3. 指出当前最薄弱的因果/数学链条和最高价值的不确定性；辨别是否因反复归因而停滞。
4. 比较不超过三种下一动作，说明各自的决策价值、证据条件和成本，不派遣任何动作。

## 产出
一页研究现状，包含 Scientific Delta、未解机制、最关键风险与下一建议。明确标记 `read_only`，不得写回 State、启动 GPU 或暗中切换为执行模式。
