# Research Recovery

Preset ID: `research-recovery`  
Top-level Entry: `continue-research`  
Trigger: `manual`  
Execution Scope: `recover_no_experiment`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
用户换会话、换 Agent、上下文遗失或请求恢复当前科研工作；只做完整状态恢复，不擅自扩大到新实验。

## 执行协议
1. 从安装位置确认 Skill 版本，读取对应入口、项目规则和授权。读取路线 State / Scheduler / Cognitive Memory、进程状态、最新实验与 Git 工作区状态。
2. 检查 State/Memory 的来源版本、未完成 R10 修复、失败限制、预注册锁定状态、资源预算；必要时仅重建可派生记忆，不改历史结论。
3. 针对在途 GPU/外部任务检查实际进程和产物；未知状态不自动重试。检查配置/代码/数据版本与原任务匹配。
4. 恢复上一条已承诺且尚未完成的合法研究动作；区分真正阻断、可独立推进工作和已完成动作。
5. 形成一份有限的恢复检查点；如果用户只要求恢复，报告状态并停止。若同时明确授权继续研究，再转 `research-loop`，沿用原预算。

## 产出
恢复的研究问题、可信机制、关键异常、被否证方向、运行中任务、下一个动作及无法恢复项。
