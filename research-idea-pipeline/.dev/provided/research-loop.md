# Autonomous Research Loop

Preset ID: `research-loop`  
Top-level Entry: `continue-research`  
Trigger: `manual`  
Execution Scope: `execute`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
用户要求“继续科研、自动运行、持续 Loop”。已初始化项目直接继续，绝不重新 Bootstrap。只在已经授权的范围内持续推进。

## 执行协议
1. 恢复项目锚点、当前路线、State、Scheduler、Cognitive Memory、证据和在途实验；校验 Skill 版本及预算，确认未完成动作是否已被执行。
2. 调用现有 Meta-Controller 选择合法动作；优先能够改变科学认识、产生区分性预测或形成方法干预的动作，不以填满日志为目标。
3. 对机制假设构造适用条件、竞争解释、可观测预测和便宜的判别干预；允许清楚标注的探索性假设，不可事后伪造预注册。
4. 执行前经过 R8、容量/强度/优化条件/可识别性、公平比较及 GPU 授权检查；执行进程用已存在的运行 ID 与结果记录防重。
5. 经 Outcome Analysis、Evidence Qualification、R10/R11 修订状态和认知模型；更新失败边界与调度经验，证明本轮记忆是否改变后续研究动作。
6. 返回步骤 1，直到预算、用户指令、权限、安全、无合法动作或正式研究终止条件触发。每轮必要检查点落盘。

## 防漂移与退出
连续动作不带来新预测、结构变化或决策价值时，不继续同构诊断；交给 `stagnation-breaker`。上下文不一致交给 `context-drift-recovery`。工程故障交给 `experiment-failure-recovery`。每次转交只触发一次，不能互相递归。

## 产出
每轮简要记录有效证据、新预测、模型修订、下一次决策、实际派遣、state_version、预算与停止原因；没有 Insight 就报告没有。
