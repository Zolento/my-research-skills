
## Round 3 — Prediction Integrity / Evidence Qualification / Insight Certification

目标：把三处「事后可操作」的漏洞堵死，并让证据资格只有一个判定入口。

- P0-1 branch mode 事后选择：分支模式必须由**预注册冻结**（`outcome_mode` + `branch_rule`），
  分支由**冻结规则作用于原始观测**导出，而不是由提交者声明；旧 state 默认 completeness。
- P0-2 统一 Evidence Qualification Gate：`qualify_evidence()` 是唯一判定入口（检查 `PQ1`—`PQ8`），
  `assess_experiment` / `evidence_transition_allowed` 只消费它，source/provenance 失败必须 fail closed。
- P1 Insight Certification：`evidence_supported_insight` 必须绑定到具体 `prediction_ref`，
  具有合格预测—观测判定、合格 R9.O 收据、方向一致的支持性 Evidence 与**通过**的 SENA 审计。

新增规则号：`PC10`（分支/判定集合完整性）、`PC11`（Insight 证据绑定）。
