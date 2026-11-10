# Identity and Compatibility（命名、协议与落盘兼容）

> 本文件区分三件经常被混为一谈的事：**Skill 名称**、**机器协议标识**、**项目运行目录**。
> 2.0.0 的重命名只改第一件。后两件是数据契约，改名会破坏已有项目。

## 1. 三层命名

| 层 | 2.0.0 之前 | 2.0.0 起 | 是否随重命名改变 |
|---|---|---|---|
| Skill 身份 | `research-idea-pipeline` | `research-lifecycle-protocol`（RLP） | **是**：frontmatter `name`、安装 slug、仓库目录、开发分支 |
| 机器协议标识 | `research-idea-pipeline/...@1` | 不变 | **否**：冻结为不透明协议标识 |
| 项目运行目录 | `.research-idea-pipeline/` | 新项目用 `.research-lifecycle-protocol/`；旧项目保留旧根 | **否**：旧根继续有效，绝不自动迁移 |

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
- **运行入口闸门**：Research Loop（`project_context`）、`operational_reconcile`、
  `experiment_execute issue/run`、`cognition build`、`render_status --root` 与
  `legacy_handoff take` 都先过存储矩阵；只读工具（`state_check`、
  `legacy_handoff detect`、迁移工具）不受限。

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

## 4. 旧项目兼容检查

升级 Skill 后，对旧项目执行以下只读检查。全部通过才继续科研动作。

```sh
# 1) 身份与根解析
python3 scripts/rlp_paths.py check --project <project>

# 2) canonical state 不因升级而失效
python3 scripts/state_check.py --check <project>/.research-idea-pipeline/routes/A/research-state.json

# 3) 只读接管审计（不重新 Bootstrap）
python3 scripts/legacy_handoff.py detect --state <project>/.research-idea-pipeline/routes/A/research-state.json

# 4) 认知投影可从磁盘重建
python3 scripts/cognition.py build --state <project>/.research-idea-pipeline/routes/A/research-state.json
python3 scripts/cognition.py check --state <project>/.research-idea-pipeline/routes/A/research-state.json

# 5) 人读视图与 canonical state 一致
python3 scripts/render_status.py --root <project> --route A --check
```

上述命令中，第 4 步会写派生投影，但**不得**修改 `research-state.json`。
第 2、3、5 步是只读或幂等校验。

兼容性硬要求：

1. 不自动重新 Bootstrap 旧项目。
2. 不重置 `research-state.json`、evidence、failure、assurance、repair。
3. 不重置 AALG/PEIG 预算、诊断次数或执行账本。
4. 不把旧 schema id 判为无效。
5. 不在旧项目里创建第二个 canonical state，也不创建第二个运行根。
6. 不改写原始实验产物或历史摘要。

## 5. 迁移是可选的，且必须人工决定

本版本**不提供**自动迁移。如果项目确实要改用新根：

1. 先停掉所有执行与调度，备份整个旧根。
2. 用 `state_check.py`、`legacy_handoff.py detect`、`cognition.py check` 核对旧根完整。
3. 复制（不是移动）旧根到新根，逐项复核字节一致性。
4. 确认没有第二个根后，再更新项目自己的入口文档。
5. 旧根保留为归档，直到用户明确批准删除。

迁移失败时回滚方式：删除新根、恢复旧根。**不要**在迁移中途重新 Bootstrap。

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
| 旧项目 | 旧根下 state 通过 `state_check`，`cognition check` 无漂移，预算与账本不变 |
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
