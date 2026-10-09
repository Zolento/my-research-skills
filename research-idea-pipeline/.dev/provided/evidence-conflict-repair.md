# Evidence Conflict Repair

Preset ID: `evidence-conflict-repair`  
Top-level Entry: `audit`  
Trigger: `event_or_manual`  
Execution Scope: `evidence_repair`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 触发
预测、观测、Evidence、Claim、Insight、认知记忆间存在不同版本、缺失引用、失效来源或相互矛盾的合法性标记。

## 执行协议
1. 将相关实验和预测升级链临时置于不得提升科学支持的状态；保存冲突清单和原始来源。
2. 逐级核对冻结预注册、结果结构/原始摘要、执行有效性、统一 Evidence Qualification、R9.O、R10/R11 及 Scope。
3. 区分观察错误、元数据错误、无效证据、真正冲突预测；不能用猜测补齐历史 prediction_ref 或事后改变冻结规则。
4. 按已有权限进行修复/失效传播；仅在合法状态迁移之后重建 Memory、Scheduler 投影。未解决的冲突保持 HOLD。
5. 验证没有通过其他入口间接认证 Insight，且同一冲突不反复重试。

## 产出
冲突来源、资格判断、合法修复或 HOLD、受影响的 Claim / Insight / Memory 引用及复核结果。
