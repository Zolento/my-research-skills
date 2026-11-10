# Agent Handoff — research-lifecycle-protocol/dev（branch-local）

## 最新一轮：v2.2.0 Context & Architecture Optimization（2026-11-10）

**状态：开发完成，停在 dev 分支，未合并 main、未打 tag、未发布、未刷新全局安装。**

起始 HEAD：`f02b340`（main 基线 `787b1d9`）。目标版本 2.2.0（dev 侧 metadata 已 bump）。

### 本轮做了什么

| 阶段 | 交付 |
|---|---|
| A 基线 | `scripts/context_profile.py`（六层测量）+ `docs/context-baseline.md` + 一次真实 Harness 观测 |
| B L0 精简 | `SKILL.md` 156,565 → 28,037 bytes（−82%）+ `docs/rule-relocation-matrix.md` |
| C 加载链路 | registry `context` 声明 + `scripts/context_planner.py` + `scripts/section_index.py` + `references/section-index.json` |
| D 研究记忆 | `scripts/context_packet.py`（13 项，绑定 5 项，可检测失效） |
| E 子 Agent | `scripts/subagent_context.py` + `references/subagent-context.md`（5 角色，5 条权限不变量） |
| F 回归 | 2325 tests OK（skipped=4）、`release_check` PASS、MRI replay 4/4、安装副本 smoke PASS |

### 实测读数

- 每次调用协议上下文：平均 129,426 → 37,855 字符（−71%）；工具调用 4.08 → 3.42，无场景上升。
- 子 Agent 上下文：123,449 → 16,881 字符（−86%）。
- `SKILL.md`：156,565 → 28,037 bytes（−82%）。**未达 10—15 KB 目标**，理由与组成见
  `docs/context-benchmark.md` §5；`release_check` 用 40,000 bytes 作为回归上限。
- 科学能力：**L3 未验证**。行为回归与 Replay 只支持 L1/L2。

### 本轮修掉的既有缺陷

- `PE17` 长期未定义（代码与测试在用）→ 补入 `skill-rsi-policy.md` 规则表。
- R12 两条独有规则随 §4 删除无处安放 → 迁入 `phase-r12-narrative.md`。
- `SKILL.md` 三处「记入根 INDEX 的 Warnings」与既有权威冲突 → 迁移时未搬运。
- frontmatter「24 条机械硬规则」→ 更正为 31 条（S1—S7 + V1—V24）。
- 迁移引入的 18 个文件悬空相对链接 → 机械修复（24 处 docs 链接另修）。

### 已知未修复（下一轮候选）

1. 约 20 处 `.research-idea-pipeline/routes/...` 仍作正常落盘路径出现于 9 个 phase 文档
   （与 v2.1.0 单根政策冲突）。涉及科学落盘路径，需逐条核对。
2. `roles.md` 六攻击面 vs `invocation-prompts` / `phase-r7` 八攻击面表述冲突。
3. `research-state-policy` §5 表与其后说明条目对 R12 写入口径不一致。
4. `preset-policy` 仍有一处旧预设名 `self-evolution.md`（实际为 `strategy-evolution.md`）。
5. L0 仍比 10—15 KB 目标大 13 KB；继续压缩需要删规则或删被外部引用的锚点。

### 恢复本工作的最小步骤

```bash
cd research-lifecycle-protocol
python3 scripts/release_check.py          # 唯一判据
python3 scripts/context_planner.py check  # 依赖声明
python3 scripts/section_index.py check    # 章节索引
```

---

## 当前目标

1. ✅ 更名 `research-idea-pipeline` → `research-lifecycle-protocol`（目录/frontmatter/
   安装/根 README/AGENTS），旧项目与协议命名空间兼容，双根 fail closed。
2. ✅ MRI Reconstruction Domain Profile：`domain-profiles/mri-reconstruction/` +
   `scripts/domain_profile.py`（DP1—DP14）。
3. ✅ TAG（`scripts/domain_guard.py`，TG1—TG9，六类判定，事件链）+ loop 消费点
   （`preset_router._loop_step`，在 `i2m.diagnosis_decision_impact` 之后）。
4. ✅ MMS（`scripts/domain_mms.py`，六方向菜单 + MM1—MM8a 契约）+ TAG 转化菜单。
5. ✅ 合成回放十场景 + 四臂领域消融（`scripts/test_domain_replay.py`）。
6. ✅ release_check 新增 Domain Profiles 步骤；隔离安装/卸载实测。

## 分支状态

- 基线：`main` @ `dcdce9c`（含 1.1.0 发布 + 未发布的科学汇报/运维自主 + Mesh 契约）。
- worktree：`/home/lenovo/code/myproj/skills-dev/research-lifecycle-protocol/dev`。
- 分支提交：896ae67（更名）→ 7d3ac99（MRI profile）→ 3171cce（store 文档移植）→
  本提交（.dev 记录）。
- main 上已知问题：`references/invocation-prompts.md` 存在合并产生的重复段落
  （~38 行 ×2，来自 d9a5949 合并 a8d42f5）。**本分支未修 main**；合并回 main 前须先在
  main 修掉，否则会把重复段落带回。

## 验证读数

- 全量 unittest：2174+ tests OK（skipped=4）。
- `release_check.py` PASS（19 步，含 Domain Profiles 步骤）。
- 隔离安装：`npx skills add <干净副本> -y` → `.agents/skills/research-lifecycle-protocol/`
  frontmatter `name: research-lifecycle-protocol`、version 2.0.0；副本内
  `release_check.py` PASS；`npx skills remove` 实测成功。
- 全局安装（`-g`）在本会话沙箱内因 `~/.agents` 只读未验证（CLI 报 ENOENT/mkdir）；
  需要在无沙箱环境重跑一次 `-g` 安装确认。

## 未完成 / 风险

1. L3 科研有效性未验证：合成回放只能证明机制接线。下一步最值得做的是拿一个真实
   CT-FM 或 Wave-TOF 项目路线做 TAG/MMS 的真实回放 A/B（隐藏未来信息，对照
   core vs +tag+mms 的重复归因次数与方法候选质量）。
2. main 的重复段落修复 + 本分支合并回 main + 打 `research-lifecycle-protocol/v2.0.0`
   tag（合并时执行，本分支不打）。
3. 旧 RSI 分支清理：见 `.dev/decisions.md` D-RLP-7；`feat/failure-analysis` 因有未合并
   提交保留；`feat/zotero` 按任务要求保留。
4. `domain_mms.recommend_directions` 的失败-机制映射基于 finding 文本中的受控 token；
   项目的 failure 记录应尽量把 `mechanism` 字段写成受控枚举，以提高菜单质量。

## 2026-11-10 收尾（合并与安装）

- main 已合并本分支：merge commit `dacfcd6`（`.dev/` 按约定未进 main，KEEP_BRANCH_ONLY）。
- 已打 annotated tag `research-lifecycle-protocol/v2.0.0`（指向 dacfcd6）并推送 origin。
- 合并前的重复段落（invocation-prompts.md Method-Driven/Resume/核心行为 ×2）已在
  1ee83b0 修复，main 上为单份。
- 正式安装：`~/.agents/skills/research-lifecycle-protocol/`（真实目录，v2.0.0，
  release_check PASS 于可写副本；安装副本与发布树字节一致）。旧 `rsi-pipeline`
  （live + .bak 备份 + 大写 RSI-pipeline 死链接）已全部卸载，catalog 只剩新名称。
- 已知限制：沙箱内 `~/.agents` 只读，变异测试（写真实文件再还原）无法在安装副本
  原位运行；用可写副本 + diff -r 字节一致替代验证。


## 2026-11-10 v2.0.1 收尾

- 六个提交（Phase A–E）：4a8f9a5 / 574a1ca / c8820f8 / 5aaed54 / 08427f1 / 2db2852。
- 缺陷修复矩阵与链路图见 docs/releases/v2.0.1.md；replay 接口见
  scripts/domain_replay.py + examples/domain/mri-reconstruction/。
- L3：NOT YET VALIDATED。下一步 = 真实 CT-FM / Wave-TOF 路线按 pack schema 固化后盲化 A/B。
- 遗留：TAG classify 的机制枚举仍是封闭集合（新机制登记 other_declared 待审）；
  指标契约的 GT 来源验证只覆盖 config/protocol 类来源中的机器记录，
  checkpoint 选择记录的深度验证需要 Execution Manifest 落地后的第二阶段。


## 2026-11-10 v2.1.0 合并与发布

- main 已合并本分支：merge commit `cdabc9a`（`.dev/` 未进 main）。
- tag `research-lifecycle-protocol/v2.1.0`（annotated `2ca9445` → cdabc9a）已推送。
- 本机 `~/.agents/skills/research-lifecycle-protocol/` 已刷新为 v2.1.0（与发布树字节一致）。
- 下一步（真实项目迁移）：逐项目 inspect → plan → migrate --apply → verify → Resume；
  Mesh 插件硬编码旧路径的协同修复仍待外部处理。


## 2026-11-10 v2.1.1 迁移安全补丁

- 提交：04a20b6（维护锁+写入入口闸门）→ fc6f87e（迁移事务：源一致性/全量回滚守卫/
  文档提交事务/journal-recover/备份边界）→ 9e2bf48（文档与发布说明）。
- 关键读数：全量 2278 tests OK (skipped=4)；test_migration_transaction.py 31 项全绿；
  `release_check.py` PASS（版本 2.1.1 一致）。
- 维护锁只覆盖 RLP 自身写入入口；外部 Mesh/训练脚本/第三方插件不受保护，
  `migrate --apply` 因此要求 `--assume-writers-quiesced`。
- 回滚后项目回到 MIGRATION_REQUIRED（灾难恢复，不是恢复正常科研执行）。
- 未合并 main、未打 tag。待用户确认后合并并发布 v2.1.1。
