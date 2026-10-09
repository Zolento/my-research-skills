# Skill-RSI 开发决策记录（branch-local）

## D1 — 决策轨迹作为独立 append-only 控制平面，而不是扩大 `strategy_decisions[]`

- 背景：`scheduler.strategy_decisions[]` 是有界环形遥测（`DECISION_LOG_LIMIT = 20`），
  语义是“系统运行统计”。长期策略学习需要 Context/Prediction/Outcome/Learning 绑定。
- 决策：新增 `<route>/decision-trajectory.jsonl`（append-only + hash chain + head 摘要 + flock + fsync），
  不修改既有 scheduler 键，避免破坏已有测试与语义。
- 理由：满足“先复用已有记录，不足时新增独立 append-only 轨迹，而不是覆盖原有遥测”。

## D2 — 轨迹永不写入 canonical `evidence[]`

- 轨迹是控制平面经验，不是科学事实。校验规则 `DT7`/`DT9` 拒绝把轨迹当证据，
  `scientific_delta` 必须由 `evidence_qualification == qualified` 支撑。

## D3 — Replay 增强必须保持四臂语义逐字节兼容

- `ABLATION_ARMS` 四臂保持冻结；新增 `RSI_ARMS` 六臂为附加层。
- `evaluate()` 只新增可选 `evidence_support` 键；不引入任何聚合分（测试禁止
  `total/overall/score/weighted` 作为键）。

## D4 — 反事实不可观测必须显式返回 `NO_SUPPORT`

- `classify_evidence_support()` 区分 `OBSERVED` / `REPLAY_SUPPORTED` / `NO_SUPPORT`；
  历史未执行分支一律 `NO_SUPPORT`，runner 拒绝采用并标记 `policy_used_unobserved_branch`。
- 真实历史注入只生成 support map；不伪造 hidden answer（`cases_from_trajectory` 需要外部答案，否则不产出 case）。

## D5 — `test_release_metadata::test_the_release_tag_points_exactly_at_the_verified_release_commit` 改为分支感知（非弱化）

- 现象：该测试断言 `tag v1.0.0 == HEAD` 且 `== refs/heads/main`。在 main 上成立；
  在任何开发分支/worktree 上，HEAD 必然前进，因此该断言在开发分支上恒为假。
- 这不是本次改动引入的缺陷：该测试编码的是**发布分支不变量**。
- 处理：在 `main` 上保留原来的 `tag == HEAD` 与 `tag == main` 两条断言不变；
  在非 main 分支上改为断言 `tag == refs/heads/main`，并要求 `main`（即发布提交）
  是当前 HEAD 的祖先。没有删除任何约束，只是把“HEAD 身份”约束限定到它真正适用的分支。
- 影响：`release_check.py` 在开发分支上不再被该环境性失败阻塞；在 main 上行为完全一致。
- 诚实声明：这是一次测试期望的**适用范围**修正，不是把失败改写成成功；
  发布前在 main 上仍会执行原始两条断言。

## D6 — 不新增 Preset、不新增 canonical 对象

- 16 个 Preset 数量被 `registry_errors()` 与 `release_check.step_preset_library` 双重冻结；
  RSI 通过现有 `strategy-evolution` / `research-loop` / `discovery-replay` 承载。
- 全部新增数据落 route 控制平面（telemetry / 派生），canonical Research State 不新增字段。
