# Scientific Replanning

Preset ID: `scientific-replanning`  
Top-level Entry: `continue-research`  
Trigger: `manual_or_blocked`  
Execution Scope: `plan`

> 加载 `../shared-contract.md` 与当前 Skill 的有效阶段契约后，执行以下协议。不得把本文件当作覆盖已有权限和硬规则的新授权。

## 意图
当前路线的关键假设被否证、目标暂不可达或研究资源条件变化，需要调整行动计划而不擅自换主锚点。

## 执行协议
1. 恢复锚点、已完成与无效实验、失败边界、剩余资源、合法行动集合。
2. 将已验证事实与未证实解释分开；提出至少两条可执行的替代研究路径，给出各自的关键依赖、判别试验和失败条件。
3. 对路径比较科学重要性、执行依赖、证据质量、预期决策变化和成本；不得简单以 EIG 或模型自评分选优。
4. 标记 retain / defer / abandon / request_anchor_change。需要变更项目主锚点只能准备 Anchor Change Order 请求用户授权；不得自动执行。
5. 选一项合法下一动作，写入现有计划/调度通道并报告是否实际派遣。未经明确执行授权只生成建议。

## 产出
路线重排、弃置理由、资源约束、下一决策及可证伪的成功/失败标准。
