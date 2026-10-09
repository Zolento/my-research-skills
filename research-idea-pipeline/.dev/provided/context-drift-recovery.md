# Context Drift Recovery

Preset ID: `context-drift-recovery`  
Top-level Entry: `continue-research`  
Trigger: `event`  
Execution Scope: `recover_no_experiment`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
检测到 Skill/Context 版本不一致、关键规则不在活跃上下文、当前动作偏离锚点、压缩/会话重启等有记录的信号。没有程序性触发器时只作为人工调用协议。

## 执行协议
1. 暂停派遣新副作用动作，保存当前动作和触发事件；避免重复记录同一状态版本的事件。
2. 重新从磁盘加载 Skill 核心规则、当前路线锚点、State、Scheduler、Cognitive Memory 与执行检查点；检查版本与权限。
3. 核验下一动作是否仍合法，是否重复完成或被失败证据禁止；记录漂移类型和已恢复的契约。
4. 可恢复则回到中断动作；不可恢复则 HOLD，报告唯一明确的阻断原因。不得在恢复流程内递归调用自身。

## 产出
recovered/hold、前后版本与动作、恢复证据、仍存在的缺口。
