# Identity and Compatibility（命名、协议与落盘兼容）

> 本文件区分三件经常被混为一谈的事：**Skill 名称**、**机器协议标识**、**项目运行目录**。
> 重命名只改第一件。后两件是数据契约，改名会破坏已有项目。

## 0. 当前存储规则（v2.1.0 起生效，优先于本文其余历史说明）

**所有正式科研运行统一使用 `<project>/.research-lifecycle-protocol/`。**
它是唯一的运行时控制根。

旧根 `<project>/.research-idea-pipeline/` 只允许下列用途：

- **只读审计**（`state_check`、`legacy_handoff detect`、迁移工具 `inspect`）；
- **显式迁移**（用户对具体项目执行 `migrate_project_root.py`）；
- **历史兼容**（旧证据、哈希链、冻结预注册中的旧路径原样保留）；
- **灾难恢复**（`rollback` 之后旧根重新成为迁移来源）。

迁移工具**已存在**，但**绝不自动执行**：`start-project` / `continue-research` /
Resume 遇到旧根只输出 `MIGRATION_REQUIRED` 与迁移命令。

**旧项目在迁移完成前不能执行正式科研操作**（Research Loop、受管执行、认知投影写入、
STATUS 写入、Cold Handoff 都会被闸门拒绝）。只读检查与迁移预检仍然可用。

迁移期间的停写边界：RLP 自身写入入口受维护锁保护；外部写入者（DSH Research Mesh
worker、训练/结果收集进程、第三方脚本）**不获取该锁**，工具无法证明其静止，必须由
操作者在 `--apply` 时确认。RLP 不声称跨系统强制互斥。

## 1. 三层命名

| 层 | 2.0.0 之前 | 2.0.0 起 | 是否随重命名改变 |
|---|---|---|---|
| Skill 身份 | `research-idea-pipeline` | `research-lifecycle-protocol`（RLP） | **是**：frontmatter `name`、安装 slug、仓库目录、开发分支 |
| 机器协议标识 | `research-idea-pipeline/...@1` | 不变 | **否**：冻结为不透明协议标识 |
| 项目运行目录 | `.research-idea-pipeline/` | `.research-lifecycle-protocol/`（**唯一运行时控制根**，见 §0） | **否**：旧根只作迁移/审计/灾难恢复来源，不作为正式运行目录 |

历史发行 tag（例如 `research-idea-pipeline/v1.1.0`）属于发布历史，不改名、不删除。
新版本 tag 使用 `research-lifecycle-protocol/vX.Y.Z`。

Cognitive Insight Engine（CIE）是内部认知能力模块的名称，不是 Skill 名称，也不参与安装。

## 2. 不可改动的兼容面

以下内容在 2.0.0 中保持不变。改动它们会让旧项目无法读取，属于兼容性破坏：

- 所有 schema / 协议 id：`research-idea-pipeline/research-state@1`、`.../scheduler@1`、
  `.../replay-case@1`、`.../decision-trajectory@1`、`.../policy-*@1` 等。
- 旧运行目录 `.research-idea-pipeline/routes/<R>/` 下的 canonical state、预注册、
  `cognition/model-revisions.jsonl`、`scheduler.json`、执行账本、方法产物与历史摘要。
- 既有 tag 与 release notes 中的历史名称。
- 账本与轨迹的哈希链格式、文件锁与原子写语义。

`scripts/rlp_paths.py` 把上述常量集中到一处，并提供只读解析。它的 selftest 与
`scripts/test_identity_compat.py` 是这条边界的机械证据。

## 3. 运行时根解析规则（v2.1.0 存储矩阵）

**`.research-lifecycle-protocol/` 是唯一合法的运行时控制根。** 旧根
`.research-idea-pipeline/` 只作为历史项目的迁移来源，不再是合法的日常运行目录。

`scripts/rlp_paths.runtime_status(project_root)` 的固定状态矩阵：

| 现场 | 状态 | 运行行为 |
|---|---|---|
| 两个目录都不存在 | `NEW_PROJECT` | 新项目初始化使用新根 |
| 只有新根（有可识别内容） | `READY` | 正常加载和执行 |
| 只有新根（空/不可识别） | `INVALID_STORAGE_ROOT` | 禁止静默修复或重建 |
| 只有旧根 | `MIGRATION_REQUIRED` | 暂停正式运行，先迁移 |
| 新旧根同时存在 | `AMBIGUOUS_STORAGE_ROOT` | fail closed |

API 分层：

- **正常运行路径**：`resolve_runtime_root(project_root)` / `default_state_path(...)`
  —— 只返回新根；旧根场景抛出对应错误（异常类带稳定 `STATUS` 标记）。
- **历史迁移路径**：`inspect_legacy_root(project_root)` /
  `resolve_storage_root(...)` —— 专供迁移、审计和只读兼容检查使用。
- **运行入口闸门**：Research Loop（`preset_router.run_preset` / `project_context`）、
  `operational_reconcile`、`experiment_execute issue/run`、`cognition build`、
  `render_status` 与 `legacy_handoff take` 先过存储矩阵，再持**共享维护锁**：
  迁移/回滚期间这些入口拒绝写入并返回 `MAINTENANCE_IN_PROGRESS`。只读工具
  （`state_check`、`legacy_handoff detect`、迁移工具 `inspect`/`plan`）不受限。
  外部写入者不获取该锁，见 §0 与 §5.1。

`MIGRATION_REQUIRED` 是**工程控制平面的迁移状态**，不是科研机制失败：
不计入 Failure Memory，不触发科学重规划，不重启实验。

迁移使用正式工具（默认只读，`--apply` 才执行）：

```sh
python3 scripts/migrate_project_root.py inspect --project <project>
python3 scripts/migrate_project_root.py plan    --project <project> --backup-root <dir>
python3 scripts/migrate_project_root.py migrate --project <project> --backup-root <dir> --apply
python3 scripts/migrate_project_root.py verify  --project <project> --migration-id <id>
python3 scripts/migrate_project_root.py rollback --project <project> --migration-id <id>
```

旧项目不得自动迁移；`start-project` / `continue-research` / Resume 遇到旧根只输出
`MIGRATION_REQUIRED` 与迁移操作说明。

CLI：

```sh
python3 scripts/rlp_paths.py resolve --project <project-root>
python3 scripts/rlp_paths.py check   --project <project-root>
```

`check` 在 `MIGRATION_REQUIRED` / `AMBIGUOUS_STORAGE_ROOT` / `INVALID_STORAGE_ROOT`
时退出码 3，并提示迁移命令；`resolve` 输出 JSON（含 `runtime_status` 与
`schema_namespace`——恒为 `research-idea-pipeline`，标记 `frozen: true`）。

## 4. 旧项目兼容检查（只读，迁移前）

升级 Skill 后，先对旧项目做**只读**检查；这些命令不会写控制平面，也不会改变科研状态。

```sh
# 1) 身份与根解析（旧根会返回 MIGRATION_REQUIRED 与迁移提示）
python3 scripts/rlp_paths.py check --project <project>

# 2) canonical state 不因升级而失效
python3 scripts/state_check.py --check <project>/.research-idea-pipeline/routes/A/research-state.json

# 3) 只读接管审计（不重新 Bootstrap）
python3 scripts/legacy_handoff.py detect --state <project>/.research-idea-pipeline/routes/A/research-state.json

# 4) 迁移预检（只读）
python3 scripts/migrate_project_root.py inspect --project <project>
```

**会写控制平面的命令在旧根上会被拒绝**（`MIGRATION_REQUIRED`）：
`cognition.py build`、`render_status.py`（写 STATUS）、`legacy_handoff.py take`、
Research Loop 与受管执行。它们只能在迁移完成后运行——这是有意的：
旧根不再是运行时根，向其写入会产生第二份控制平面。

迁移完成后，同样的检查在新根上执行：

```sh
python3 scripts/cognition.py build --state <project>/.research-lifecycle-protocol/routes/A/research-state.json
python3 scripts/cognition.py check --state <project>/.research-lifecycle-protocol/routes/A/research-state.json
python3 scripts/render_status.py --root <project> --route A --check
```

兼容性硬要求：

1. 不自动重新 Bootstrap 旧项目。
2. 不重置 `research-state.json`、evidence、failure、assurance、repair。
3. 不重置 AALG/PEIG 预算、诊断次数或执行账本。
4. 不把旧 schema id 判为无效。
5. 不在旧项目里创建第二个 canonical state，也不创建第二个运行根。
6. 不改写原始实验产物或历史摘要。

## 5. 迁移：正式工具，绝不自动执行

迁移是正式科研运行的前置条件，但**是否迁移、迁移哪个项目、何时迁移**由用户决定。
工具不会自动发现项目，也不允许无人值守执行。

```sh
# 1) 只读预检：存储矩阵、durable 清单、科研资产指纹、路径依赖、维护锁状态
python3 scripts/migrate_project_root.py inspect --project <project>

# 2) 只读计划：迁移 ID、备份目的地、磁盘容量、待重写文档
python3 scripts/migrate_project_root.py plan --project <project> --backup-root <dir>

# 3) 停止所有写入者（RLP 会话/Loop/Mesh/执行器/监控），确认备份目录可写
# 4) 执行迁移（必须显式确认外部写入者已静止）
python3 scripts/migrate_project_root.py migrate --project <project> \
  --backup-root <dir> --apply --assume-writers-quiesced [--rewrite <doc>...]

# 5) 按迁移记录校验（不是重新生成一份 manifest 就当成功）
python3 scripts/migrate_project_root.py verify --project <project> --migration-id <id>

# 6) 恢复科研：入口自动 Research Resume（旧根已归档，不再是运行时根）
```

事务保证（v2.1.1）：

| 保证 | 机制 |
|---|---|
| 并发迁移互斥 | `.rlp-migration/control.lock` 独占锁；RLP 写入入口共享锁，迁移期间拒绝写入 |
| 源目录不被静默改变 | 预检/备份后/staging 后/cutover 前四次快照比对；变化即 `SOURCE_CHANGED_DURING_MIGRATION` |
| 备份可验证 | 逐文件类型/大小/SHA-256/符号链接/manifest；备份后才允许切换 |
| 历史记录不改写 | Research State、预注册、证据、收据、TAG 链、决策轨迹字节不变 |
| 回滚守卫 | 完整 durable manifest 比对；任何迁移后写入 → `ROLLBACK_REFUSED_NEW_WORK` |
| 文档重写可恢复 | cutover 后才提交，逐文件原子替换并记录原字节与 journal |

**失败处理**：`inspect`/`plan` 只读；失败时旧根与备份保留，报告给出 `status` 与
`errors`。中断用 `recover`（默认只读，`--apply` 只执行可证安全的动作）；回滚用
`rollback --migration-id`。**回滚是灾难恢复**：完成后项目回到 `MIGRATION_REQUIRED`，
不是恢复正常科研执行。

不允许：把备份放进被迁移的控制根、用 `mv` 手工迁移、用全局字符串替换"清理"历史路径、
在迁移后已产生新写入时强行回滚。

## 5.1 外部集成缺口（DSH Research Mesh）

RLP 侧契约已指向新控制根；Mesh 插件是外部仓库，本轮不修改其 Schema。若插件配置
（例如 `rsi.skillPath`、canonical root、worker 只读路径）仍硬编码旧目录，需要插件侧
协同修复：把项目根/控制根配置改为 `.research-lifecycle-protocol/`，并让 worker 只读该
根。迁移期间不得启动 Mesh。

## 6. 安装与卸载

正式安装只认新名称：

```sh
npx skills add Zolento/my-research-skills -g -s research-lifecycle-protocol -y
```

旧名称的安装副本必须移除，避免 catalog 同时出现两套身份：

```sh
npx skills remove research-idea-pipeline -g -y     # 若曾经装过
npx skills remove rsi-pipeline -g -y               # 旧开发变体
```

开发分支安装使用片段语法（分支名含 `/`）：

```sh
npx skills add "Zolento/my-research-skills#research-lifecycle-protocol/dev@research-lifecycle-protocol" -g -y
```

安装副本的 `name:` 必须保持 `research-lifecycle-protocol`。仓库内不得为了安装而改名。
安装副本可以剔除 `.dev/`、`__pycache__` 与临时产物，但不得剔除正式 `references/`、
`domain-profiles/`、`schemas/` 或测试。

## 7. 验收清单

| 检查 | 通过条件 |
|---|---|
| Skill 身份 | `SKILL.md` 的 `name` 为 `research-lifecycle-protocol`；catalog 只出现该名称 |
| 机器协议 | 所有 `research-idea-pipeline/...@1` 常量保持不变 |
| 旧项目 | 旧根只读可审计（`state_check`/`detect`/`inspect`）；正式运行需先迁移，写入入口返回 `MIGRATION_REQUIRED` |
| 迁移 | 备份经 manifest 校验；源快照四次一致；新根与安装 manifest 逐文件相等；回滚被新写入拒绝 |
| 双根 | 同时存在时 `rlp_paths.py check` 退出码 3，运行流程拒绝继续 |
| 历史 | 旧 tag 与 release notes 保留；新 tag 前缀为新名称 |
| 其他组件 | `academic-figure-draft-architect/` 与 `scientific-manuscript-reviser/` 无改动 |

## 8. 何时才允许改协议命名空间

只有在同时满足以下条件时才允许新增新的 schema id 命名空间：

1. 新命名空间与旧命名空间并存，读取器同时接受两者；
2. 提供逐 schema 的双向映射与迁移测试；
3. 旧项目不需要迁移即可继续运行；
4. 有真实的旧状态 fixture 作为回归证据。

仅仅因为 Skill 改名，不构成修改协议命名空间或运行目录的理由。

## Cold Handoff 与 Research Resume 的入口分类

> 以下内容自 v2.2.0 起从 `SKILL.md` 的 L0 常驻核心迁出，本节为该规则的**权威落点**。
> L0 只保留可判定的短约束与本节指针。来源：`SKILL.md` §0.31。

两个**完全不同**的操作，不要混用（判定见 `scripts/legacy_handoff.py:resume_decision`）：
| 场景 | 操作 | 说明 |
|---|---|---|
| 无 canonical state | Bootstrap | 按 §0.3 执行 |
| 有历史但未完成接管 / 真实不兼容迁移 | **Cold Handoff**（`legacy_handoff.py take`）| 一次性：兼容性审计、投影重建、接管报告、可回滚；**不伪造预注册**，canonical state 无损 |
| 已有有效 state（含 `/loop` 每轮唤醒、`continue-research`、会话恢复、上下文压缩后重载）| **Research Resume** | 直接读 canonical state + 认知投影 + Scheduler + 已有方法产物，继续未完成的科研行动 |
| state 不可读 / 真实证据异常 | Recover / HOLD | 走既有恢复链，**不得**通过重建 state 绕过 |
**已有 `research-state.json` ≠ 需要完整接管**；`state_version` 增长、缺少派生报告都**不**构成重新
接管的理由。职责边界：Legacy Handoff 只做一次性接管；Research Recovery 恢复当前科研状态；
Context Drift Recovery 处理投影漂移；Cognition 维护可重建记忆；Scheduler/I2M 决定下一步行动。
