# Skill-RSI 开发计划（branch-local）

> 本文件是开发工作区文档，不进入 main（根 AGENTS.md §5/§13）。

## 基线

| 项 | 值 |
|---|---|
| 仓库 | `Zolento/my-research-skills` |
| 起点 | `origin/main` @ `ea0214e30f75bb9709d0c01efe25dc5f9fc3f804` |
| 组件 | `research-idea-pipeline/` |
| 声明版本 | `SKILL.md` `metadata.version = "1.0.0"`（CHANGELOG 说明 v1.x/v2.x tag 为历史迭代，1.0.0 为重整后正式稳定版）|
| worktree | `/home/lenovo/code/myproj/skills-dev/research-idea-pipeline/skill-rsi-dev` |
| 分支 | `research-idea-pipeline/skill-rsi-dev` |
| 基线测试 | 1436 tests, OK (skipped=3)；`state_check --selftest` OK；`release_check.py` PASS（17 步）|

基线原始输出保存在 `.dev/baseline/`。

## 不可变约束（贯穿全部实现）

1. Harness、基础模型、Agent 调度、平台工具接口均不修改；只用 Skill 可控边界。
2. R0—R14、八类 canonical 对象、双循环、四入口、16 Preset、Scheduler 八级优先级不变。
3. 不新增第九类 canonical 对象；一切新增数据落 route 控制平面（telemetry / 派生存储）。
4. 科研运行期间不得自主修改 Skill 源码；实现机械可检的源码冻结与写入白名单。
5. 无反事实伪造：历史未执行的行动分支只能返回 `NO_SUPPORT`。
6. L1/L2/L3 严格区分；候选生成 ≠ 已应用 ≠ 行为改变 ≠ 能力提升。

## 新增模块（最小实现）

| 阶段 | 模块 | 类型 | 真实消费者 |
|---|---|---|---|
| P2 | `scripts/decision_trajectory.py` | 新增 | `policy_evolution.py`、`policy_transfer.py` |
| P3 | `scripts/research_replay.py`（增强） | 就地增强 | `release_check.py`、`preset_router.py` |
| P4/P5 | `scripts/policy_evolution.py` | 新增 | `preset_router._handle_strategy_evolution`、`_loop_step` |
| P4 | `scripts/strategy_memory.py`（增强） | 就地增强 | `preset_router` 的 dispatch 路径 |
| P6 | `scripts/preset_router.py`（增强） | 就地增强 | `research-loop` preset 输出 |
| P7 | `scripts/policy_transfer.py` | 新增 | `policy_evolution` scope 校验、memory-consolidation |
| P8 | `scripts/source_freeze.py` | 新增 | `preset_router` 运行前后核验、`release_check` |
| P9 | `scripts/rsi_ablation.py` + `test_*.py` | 新增 | `release_check` |

正式文档：`references/skill-rsi-policy.md`（渐进加载，由 `SKILL.md` 链接），并更新
`presets/strategy-evolution.md`、`presets/research-loop.md`、`presets/discovery-replay.md`、
`presets/stagnation-breaker.md`、`presets/memory-consolidation.md`、`README.md` 的必要章节。

## Milestones

1. M1 架构审计：差距矩阵 + 冻结基线测试 → 提交审计文档。
2. M2 Decision Trajectory：可信轨迹 + 完整性测试。
3. M3 Replay Enhancement：证据分级 + 反事实不可观测 + 防泄漏。
4. M4 Policy Evolution：候选/作用域/生命周期/评估/回滚。
5. M5 Research Loop Integration：真实 dispatch 消费 + 三类 Delta + 停滞恢复。
6. M6 Safety & Regression：源码冻结、权限对抗、全量回归与发布前检查。
7. M7 Docs & Compat：正式文档与向后兼容。

## 命令约定

- 测试：组件根目录 `python3 -m unittest discover -s scripts -p "test_*.py"`
- 单模块：`python3 -m unittest discover -s scripts -p "test_policy_evolution.py"`
- 发布闸门：`python3 scripts/release_check.py`（只看 exit code 与最后一行）
