# Experiment Failure Recovery

Preset ID: `experiment-failure-recovery`  
Top-level Entry: `continue-research`  
Trigger: `event_or_manual`  
Execution Scope: `engineering_recovery`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
OOM、NaN、异常退出、数据解码失败、训练崩溃、作业失联或硬件故障。

## 执行协议
1. 锁定 run_id、实验 ID、提交版本、配置、数据、日志和进程事实；判断进程是否仍在运行，禁止盲目重试。
2. 分类为 environment / data / numerical / resource / code / scientific-invalid；按最小可复现实例验证失败原因，避免无意义归因。
3. 优先采用不改变科学干预定义的工程修复；若修改 batch size、精度、步数等会影响公平性或优化条件，必须重新进行可识别性与预注册核查。
4. 生成合法重试计划，保留原失败 attempt 与 provenance，增设 attempt ID；不得把执行失败写成科学负面证据。
5. 当修复无把握或预算不足时 HOLD，记录人工授权条件。

## 产出
失败分类、根因证据、最小修复、重试幂等性检查、科学有效性是否受损与下一动作。
