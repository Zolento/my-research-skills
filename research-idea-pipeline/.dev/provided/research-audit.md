# Adversarial Research Audit

Preset ID: `research-audit`  
Top-level Entry: `audit`  
Trigger: `manual`  
Execution Scope: `audit`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
严格审查当前论点、方法、预测、创新性和实验完整性；不趁审计扩展 Discovery 候选。

## 执行协议
1. 确认被审对象、其精确版本及全部证据来源；区分论文文字、代码行为与真实实验产物。
2. 按既有 R7/R10/R13 审核理论必要条件、结构近邻、替代解释、数据泄漏、容量/优化公平性、可识别性、统计有效性、Scope 和复现条件。
3. 每个实质攻击给出：目标 Claim、最强反例/替代机制、已有证据缺口、能改变判断的最小判别，以及 kill/repair/narrow 条件。
4. 如有 critical flaw，按合法 R10 修复合同处理，不直接修改 Claim Status 或自行制造闭环；需要未授权新实验时请求授权。

## 产出
经证据排序的关键漏洞及其判别、状态影响和阻断条件。不生成新研究方向；不能仅靠主观评分。
