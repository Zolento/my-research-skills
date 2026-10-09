# Resource & Execution Recovery

Preset ID: `resource-recovery`  
Top-level Entry: `continue-research`  
Trigger: `event_or_manual`  
Execution Scope: `runtime_recovery`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
GPU/CPU/存储不足、依赖变化、环境失联、队列阻断、时间或计算预算不足。

## 执行协议
1. 查询真实资源使用和在途作业，不根据聊天记录假定进程已停止；识别可重入和不能重复的外部副作用。
2. 记录当前执行意图、任务 ID、尝试次数、检查点及预算余额；不得重置配额或重复派遣已完成实验。
3. 寻找符合原科学协议的资源替代、可在 CPU 上完成的验证、理论推导或必要文献工作；改变科学条件需要重新预注册/比较设计。
4. 可安全恢复则重启/继续，不能恢复则 HOLD；禁止通过减少必要对照伪造可执行性。

## 产出
资源事实、可执行替代、预算变化、实际派遣状态、恢复条件。
