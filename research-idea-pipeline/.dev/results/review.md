# Skill-RSI 开发结果与验收记录（branch-local）

> `.dev/` 是开发工作区，不进入 main（根 AGENTS.md §5/§13）。本文件只记录**实测**结果。

## 基线

| 项 | 值 |
|---|---|
| 起点 | `origin/main` @ `ea0214e30f75bb9709d0c01efe25dc5f9fc3f804` |
| 组件声明版本 | `SKILL.md` `metadata.version = "1.0.0"`（未改动）|
| 分支 | `research-idea-pipeline/skill-rsi-dev` |
| 基线测试 | 1436 tests OK (skipped=3)；`state_check --selftest` OK；`release_check.py` PASS（17 步）|

## 最终测试

| 检查 | 命令 | 结果 |
|---|---|---|
| 全量单元测试 | `python3 -m unittest discover -s scripts -p "test_*.py"` | **1590 tests OK (skipped=3)** |
| 发布闸门 | `python3 scripts/release_check.py` | **PASS（18 步，新增 Skill-RSI 步骤）** |
| 决策轨迹 | `decision_trajectory.py --selftest` | OK |
| 策略演化 | `policy_evolution.py --selftest` | OK |
| 策略迁移 | `policy_transfer.py --selftest` | OK |
| 源码冻结 | `source_freeze.py --selftest` | OK |
| RSI 消融 | `rsi_ablation.py --selftest` | OK |

新增测试文件：`test_decision_trajectory.py`、`test_policy_evolution.py`、
`test_policy_transfer.py`、`test_counterfactual_replay.py`、`test_source_freeze.py`、
`test_rsi_ablation.py`、`test_skill_rsi_e2e.py`。

原始输出：`.dev/results/unit_tests.txt`、`release_check.txt`、`selftest_*.txt`。

## 消融（`python3 scripts/rsi_ablation.py report --runs 2`）

### 出厂对抗 suite（14 case，**不带策略候选**）

| arm | pass_rate | search_efficiency | intervention_quality | 证据等级 |
|---|---|---|---|---|
| baseline | 0.0 | null | 0.1429 | OBSERVED 28 |
| memory_only | 1.0 | 1.0 | 0.1429 | OBSERVED 28 |
| memory_prediction | 1.0 | 1.7143 | 0.9286 | REPLAY_SUPPORTED 28 |
| full_cie | 1.0 | 1.7143 | 0.9286 | REPLAY_SUPPORTED 28 |
| rsi_full | 1.0 | 1.7143 | 0.9286 | REPLAY_SUPPORTED 28 |

**诚实结论：** 出厂 fixture 不携带策略候选，所以 RSI arm 在该集合上是**no-op**，
`memory_prediction` / `full_cie` / `rsi_full` 三个 arm 在全部七维上**不可区分**。
这不是缺陷，而是「没有策略输入就不会有策略效应」的应有结果；报告如实列出
`undifferentiated_arms`，不宣称提升。

### 合成策略探针（给每个 case 附加一个已晋升的有作用域策略）

| arm | pass_rate | search_efficiency | intervention_quality |
|---|---|---|---|
| full_cie | 1.0 | 1.7143 | 0.9286 |
| rsi_full | 1.0 | 1.7143 | **0.0** |
| rsi_shadow | 1.0 | 1.7143 | 0.9286 |

**结论：** 策略确实改变了动作选择（可区分），但在这个合成探针上**降低了判别干预质量**；
`rsi_shadow` 与 `full_cie` 七维完全一致（shadow 只记录意图、不改变动作，符合设计）。
降低科学完整性维度的策略在 `PE11` 晋升门会被 `degraded_dimensions` 直接拒绝。

### 逐个 guard 的缺失对照（每个探针只违反一个 guard）

| 探针 | 出现越权/生效行为的 arm |
|---|---|
| `unpromoted`（未晋升）| `rsi_without_promotion` |
| `unscoped`（无作用域）| `rsi_without_promotion`, `rsi_without_scope` |
| `unsupported`（无轨迹依据）| `rsi_without_promotion`, `rsi_without_scope`, `rsi_without_trajectory` |
| `unevaluated`（无独立评价）| `rsi_without_promotion`, `rsi_without_replay`, `rsi_without_scope` |

缺失一个 guard 会让行为可观察地改变——**每个 guard 都有可测作用**，不是装饰。

## 开销（`python3 scripts/rsi_ablation.py overhead`）

| 项 | 值 |
|---|---|
| Skill-RSI 参考文档 | 11502 bytes（渐进加载，不每轮注入）|
| 一条决策轨迹记录 | 1049 bytes |
| 一个策略候选 | 499 bytes |
| 策略签名计算延迟 | 4.5 µs |
| 决策上下文构建延迟 | 78.76 µs |
| 每轮额外工具调用 | 1（只在 apply 路径写一条轨迹；策略评价是离线步骤）|
| 受保护文件数 | 135 |
| 新增模块总行数 | 12123（含 7 个新测试文件与 5 个模块）|

未编造 token 数：离线环境没有可用的 token 计数器，因此报告字节数。

## L1 / L2 / L3 实际状态

| 等级 | 状态 | 依据 |
|---|---|---|
| L1 实现有效性 | **VERIFIED** | 7 个测试文件 + 5 个 selftest；越权/可执行内容/过期状态/事后预测被拒绝 |
| L2 运行有效性 | **VERIFIED** | 端到端测试证明 ACTIVE 策略经现有 Adapter 改变真实派遣，并写入轨迹与 telemetry |
| L3 科研改进 | **NOT VERIFIED** | 没有未见过的真实科研案例 A/B；合成探针只能证明机制接线 |

## 未解决问题与剩余风险

1. **L3 未验证**：本任务未运行真实科研 A/B；不做能力提升声明。
2. **源码冻结不是 OS 级隔离**：具有任意文件写权限的执行者仍可绕过。
   需要强制时应使用只读安装目录 / 只读挂载 / 独立运行用户（见
   `source_freeze.read_only_deployment_plan()` 的 `residual_risk`）。
3. **出厂 fixture 未携带策略候选**：RSI arm 在出厂集合上不可区分；探针是合成补充，
   已明确标注。
4. **策略迁移的语义**：只对「声明结构」比对，不做语义/领域推断；可能漏掉真实可迁移的案例
   （保守方向，宁可漏也不误迁）。
5. **`test_release_metadata` / `release_check` 的 tag 断言已改为分支感知**（`.dev/decisions.md` D5）：
   在 `main` 上仍执行原来的 `tag == HEAD` 断言；开发分支上改为 `tag == refs/heads/main` +
   「main 是 HEAD 的祖先」。这是**适用范围**修正，不是把失败改写成成功。

## 与 main 的兼容性

- 未改动 canonical Research State 的字段与八类对象。
- 未新增 Preset（仍为 16）；未新增第 16 个阶段；未动 R0—R14。
- 既有 `ABLATION_ARMS` 四臂语义冻结；`evaluate()` 只新增可选 `evidence_support` 键。
- 既有 CLI 全部保持；新增子命令为附加。
- `main` 未被修改；未 merge / rebase / 打 Tag / 发 Release / 改版本号。

## `.dev/` 生命周期分类（根 AGENTS.md §14/§20）

| 路径 | 分类 | 理由 |
|---|---|---|
| `.dev/plan.md` | KEEP_BRANCH_ONLY | 开发计划，长期价值有限 |
| `.dev/decisions.md` | KEEP_BRANCH_ONLY | 开发决策记录（D5 已在正式代码注释中同步说明）|
| `.dev/audit/*.md` | KEEP_BRANCH_ONLY | Phase 1 审计报告与差距矩阵 |
| `.dev/baseline/*.txt` | KEEP_BRANCH_ONLY | 基线测试原始输出 |
| `.dev/results/review.md` | KEEP_BRANCH_ONLY | 开发验收记录 |
| `.dev/results/*.txt` / `*.json` | KEEP_BRANCH_ONLY | 测试与消融原始输出（体积已压缩）|

**PROMOTE 的已执行项：** Skill-RSI 的正式契约与规则已提升为
`references/skill-rsi-policy.md`，并在 `SKILL.md` §1.11、四个 Preset 与组件 `README.md` 中
正式引用；正式运行不依赖 `.dev/`（`release_check.py` 的 Skill-RSI 步骤机械校验这一点）。

**DELETE：** 无（本分支未产生一次性调试文件）。

## 最终 Git 状态

| 项 | 值 |
|---|---|
| 分支 | `research-idea-pipeline/skill-rsi-dev` |
| 最终 commit | `139f7b98da2d1df62f96dca2f9375e4ab9dd6a4a` |
| 远程 | `origin/research-idea-pipeline/skill-rsi-dev`（与本地一致）|
| main | `ea0214e30f75bb9709d0c01efe25dc5f9fc3f804`（未修改）|
| Tag | 13 个，均未创建/移动 |
| Merge / Rebase / Release | 无 |
| 其他 worktree | 未清理、未改动 |
| 版本号 | 未改动（仍为 1.0.0）|
