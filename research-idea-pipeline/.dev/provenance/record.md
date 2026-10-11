# 第十四轮：I2C Provenance & Decision Consistency Hardening

> 起始 HEAD `907ddc23c42d45c8aa95a8a9d2465763f340644f`。无新 R 阶段 / 无第九类对象 / 无平行状态机。

## 1. 修复前复现（`907ddc2`）

| # | 风险 | 复现结果 |
|---|---|---|
| P1-A | 动作授权身份 | 队列里**其他候选**的 `M-OTHER`（type=method_synthesis, target=other）使当前候选 `authorized_in_queue`；动作无任何候选/版本字段 |
| P1-B | Anchor 关联靠文字 | 仅 `recall@10` 出现在 claim 文本即判 `eligible` |
| P1-C | 进展证据串号 | 声明 `method_version: v2` 的证据算入 **v1** 的 Validation Progress |
| P2-A | 契约排序 | 按 `method_digest` 字典序 → 选中 `zzz-…`（version 1）而非 `aaa-…`（version 2） |
| P2-B | 独立复现被误拒 | 已声明独立性的复现被 `I2M82` 判为重复 |
| 机制 | 自述即证明 | 仅 `mechanism_support: "mechanism"`（无审查凭证）→ `MECHANISM_VERIFIED` |

**未复现（排除）**：与目标无关的 supported claim 已正确 not-eligible；`anchor_gap` 未默认「全部满足」。

## 2. 修复（`scripts/insight_to_method.py`）

- **P1-A**：`method_identity` / `_authorization_errors`（**I2M90–93** / **I2M95**）——授权必须绑定
  `method_candidate` + `method_version`（支持整数版本）+ `method_digest` + `state_version`；
  状态词表扩为 `proposed → admissible → authorized_in_queue → dispatched → executed`；
  新增 `register_method_candidate` 提供**合法首入路径**（生成带绑定字段的 `next_actions[]` 条目，
  新方法不会被永久锁死）。
- **P1-B**：`anchor_link` 返回 `explicit | experiment_targeted | text_only | none`，**文字提及不再
  构成资格**；`anchor_eligibility` 分离输出 `project_objective / research_progress /
  defensible_contribution / anchor_eligibility / anchor_satisfaction`；`anchor_gap` 由**冻结要求**
  （`anchor_requirements`/`frozen_success_criteria`）计算，缺条件时 `undetermined`，缺证据≠反证。
- **P1-C**：`method_progress` 建立 `Evidence → Experiment → Method Version → Hypothesis → Anchor`
  归属链：声明其他版本/其他实验契约的证据记入 `misattributed_evidence` 且不计入；
  `consumed_evidence` 防止同一证据重复消费重置停滞；五维进展保持互不替代。
- **P2-A**：`select_method_contract` 按**版本号 → 登记时间 → 实验 id** 排序（**不再用摘要字典序**）；
  显式引用失效契约返回 `audit_only=True`（仅审计，不视为当前有效方法）；archived/superseded/
  rejected/stale 永不主导 Loop。
- **P2-B**：`planned_validity_errors` 区分**合法独立复现**与无意义重复：声明 `independent_replication`
  （`declared` + 种子 + 统计目的 + 防泄漏）即通过；声明不全 → **I2M84**；**同一执行事件复用** →
  **I2M85**；改名/改 id 仍按设计+目标+事件判定，不绕过。
- **机制审查**：自述字段（`mechanism_support`/`conclusion`）未经审查凭证（`review_status=PASS` /
  T3+ / `assurance_ref`）只能记为「观察到预测现象」（**I2M96/I2M97**），不得判 `MECHANISM_VERIFIED`。

## 3. 验证

| 项 | 结果 |
|---|---|
| 全量单元测试 | **1979 OK（skipped=3）**（+22 项；基线 1957） |
| `test_insight_to_method.py` | **90/90 OK** |
| 模块 selftest | **7/7 OK**（`insight_to_method` 39 项） |
| `release_check.py` | **PASS** |

## 4. 提示词同步

`SKILL.md` §0.4 增：授权绑定候选身份、契约不得用摘要字典序、进展必须归属方法版本、关联不得靠
文字匹配、五概念分离与 `undetermined`、独立复现合法但同事件不得重复计数、机制自述不是审查；
`references/scheduler-policy.md` §3.1 更新动作状态词表与绑定要求。

## 5. 仍未验证

**L3 科研有效性未验证**：无真实 GPU/外部调度/科研 A/B。本轮证明的是**归属与授权一致性**的软件
正确性，不等于科研能力提升；最小干预测试的真实执行仍依赖既有 PEIG/AALG 与真实算力。
