# 第十五轮：Evidence Attribution & Research Decision Integrity

> 起始 HEAD `354d0ecd09b5d72abd7fe9db4346742eff15b6c3`。

## 复现（`354d0ec`）与修复

| # | 复现 | 根因 | 修复 |
|---|---|---|---|
| P1-1a | `status: supported` 但 `supporting_evidence: []` 的 claim → `eligible` | 只看 status 文本 | claim 必须有**合格证据支持**（`supporting_evidence` 或证据 `supports`），否则记 `unbacked_claims`，不成立资格 |
| P1-1b | 调用方传 `satisfied=[要求]` → `satisfaction: satisfied` | 外部输入覆盖机械判定 | 逐项判定 `satisfied/unsatisfied/refuted/undetermined`；调用方输入记 `provided_satisfied_ignored`，**不改变**结论；自然语言要求 → `undetermined` |
| P1-1c | 无目标指标约束的实验 targeting 也算关联 | 未校验实验指标 | 实验必须显式测量 `contract.target_metric` 才构成 targeting 关联 |
| P1-2 | 无版本 + `source_ref: exp:NOPE` → Validation Progress | 归属检查可被空版本/不可解析引用绕过 | `attributed()` 要求引用可解析到**真实实验**且与**方法版本/契约摘要**匹配；新增 `unattributed_evidence`；**Design 要求 `definition_digest` 真的变化**；消费水位改由持久化产物（已 outcome analysis 的实验）推导 → **跨重启去重** |
| P1-3 | `review_status: PASS` + 任意 `assurance_ref: whatever` → `MECHANISM_VERIFIED` | 自述字段当审查 | `_review_credential()` 要求 `assurance_ref` **解析到 state 内 PASS 的 assurance 条目**（或该实验的 outcome analysis/assurance PASS）；否则降为「观察到预测现象」（I2M96/97） |
| P2-1 | `version: 2`(int) vs `"v1"`(str) → 选 `v1` | 混合类型分组排序 | 统一解析（int/`"2"`/`"v2"`/`"v10"`）；**不可排序时返回 `ambiguous` + 候选列表**，不猜最新；跨候选契约不互相抢占 |
| P2-2 | 队列有 `repair` 时 I2M 仍成为 Loop 下一步 | I2M 在 Scheduler 选择前返回 | 队列存在 1—3 级动作（`repair`/`propagate_invalidation`）时 I2M 返回 None（仅建议），不取代必要动作 |

## 验证

| 项 | 结果 |
|---|---|
| 全量单元测试 | **1979 OK（skipped=3）** |
| `insight_to_method` selftest | **41 项 OK**（新增：真实审查产物、逐项要求、unattributed、跨重启去重） |
| 模块 selftest | **7/7 OK** |
| `release_check.py` | **PASS** |

## 仍未验证

**L3 科研有效性未验证**：无真实 GPU / 外部调度 / 科研 A/B；本轮证明的是归属与判定的软件正确性。
最小干预测试的真实执行仍依赖既有 PEIG/AALG 与真实算力，不伪造证据。
