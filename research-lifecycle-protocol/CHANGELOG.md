# Changelog — research-lifecycle-protocol

本文件记录 Research Lifecycle Protocol 的正式发行历史。**当前正式稳定版：2.0.0**（2.1.0 开发中，见 2.1.0 条目）。
版本序列从 1.0.0 重新建立；此前的 v1.x / v2.x 是同一组件的公开开发迭代记录，原样保留、不改写。

格式：`## <version> — <date>`，条目分为 Added / Changed / Fixed / Security / Docs。
每个版本的权威说明见 `docs/releases/<version>.md`。

## 2.0.0 — 2026-11-10

Research Lifecycle Protocol rename plus the MRI Reconstruction Domain Profile.
Merged into `main` on 2026-11-10 and tagged `research-lifecycle-protocol/v2.0.0`.
See `docs/releases/v2.0.0.md`.

### Added
- Domain profiles: optional `mri-reconstruction` profile under `domain-profiles/`
  (acquisition, self-supervision, evaluation, attribution guard, mechanism-to-method
  search and two task variants), loaded through an explicit `domain=` contract — never
  as a second source of scientific truth.
- Trivial Attribution Guard (TAG): a six-way classification of repeated, low-value
  attributions that cannot change a research decision; it never bypasses PEIG/AALG,
  never launches GPU work and never silences a verified physical defect.
- Mechanism-to-Method Search (MMS): an R3–R6 domain discovery policy that turns
  mechanism hypotheses into concrete, falsifiable method candidates through the
  existing I2M pipeline.
- `scripts/rlp_paths.py` and `scripts/test_identity_compat.py`: the identity,
  protocol-namespace and storage-root compatibility boundary is now machine-checked.

### Changed
- Skill identity: `research-idea-pipeline` → `research-lifecycle-protocol`
  (frontmatter `name`, install slug, repository directory and development branch).
  The protocol namespace `research-idea-pipeline/...@1` and the legacy project root
  `.research-idea-pipeline/` were frozen for compatibility at that release; new
  projects defaulted to `.research-lifecycle-protocol/`, and a project carrying both
  roots failed closed instead of silently picking one. (v2.1.0 made the new root the
  only runtime root and added the migration tool.)

### Compatibility
- Legacy projects keep loading without re-bootstrap, without state resets and without
  budget or ledger changes. Existing tags and release notes keep their historical name.

## 2.0.1 — 2026-11-10

Domain evidence qualification and execution-path integrity. Released on the
`research-lifecycle-protocol/dev` branch; the tag follows the merge to `main`.
See `docs/releases/v2.0.1.md`.

### Added
- Evidence-qualified TAG verdicts: `PHYSICAL_LIMIT_WITH_SCOPE` and
  `VALIDITY_BLOCKER` are bounded by resolvable canonical evidence
  (`limit_type` + `source_refs` / `validity_evidence_refs`), not by the agent's own
  `verified` label; detection-power results stay conditional and unverified
  interpretations degrade to review.
- Evidence revocation/dependency invalidation re-checked against the current state on
  every classification; fresh evidence ids with identical content do not count as
  novelty.
- TAG event idempotency (`event_id`) and a lock-file transaction for concurrent
  appends; loop enforcement events flow through the real `research-loop` apply entry.
- DP12–DP14 participate in the real Evidence Outcome transaction (metric direction
  contract, structural-recovery evidence, GT provenance), fail closed on a damaged
  TAG log, and frozen thresholds bind to the frozen preregistration digest.
- MMS candidate validation is wired into the I2M candidate path (unbypassable when a
  domain profile is active), with physical-limit scope matching and structural
  candidate deduplication.

### Changed
- `ssl-contract.md`: legal frozen-Ω_val model selection is not a GT leak; the
  violation is GT selection or post-hoc rule changes.
- `variants/wave-3d-structure.md`: 20 coils is a coil count, not an acceleration
  factor; numeric examples are task-local.
- `SKILL.md`: single introduction; the skill is defined as a stateful research
  lifecycle protocol, not an idea pipeline.

## 2.2.0 — 2026-11-10

Context & Architecture Optimization. `SKILL.md` 156 KB → 28 KB；三级上下文
（L0/L1/L2）、机器可读的上下文依赖声明、章节级加载、Research Context Packet、
子 Agent 最小任务契约、上下文基线与基准工具。**不改科研规则**。
详见 `docs/releases/v2.2.0.md`、`docs/context-baseline.md`、`docs/context-benchmark.md`、
`docs/rule-relocation-matrix.md`、`docs/context-architecture.md`。

> 版本号在更名（`research-idea-pipeline` → `research-lifecycle-protocol`）时重新起算；
> 下表里 `research-idea-pipeline/v2.2.0`、`v2.3.x` 属于旧名时期的历史迭代。

### Added
- `scripts/context_planner.py`：纯函数式上下文计划器，七个加载状态，四类独立预算，
  超预算不静默截断。
- `scripts/section_index.py` + `references/section-index.json`：稳定章节索引（66 文档 / 977 节），
  可从正文重建，`check` 判红漂移。
- `scripts/context_profile.py`：六层上下文测量（static / loaded / visible / duplicate /
  estimate / calls），明确拒绝把估算当实测。
- `scripts/context_packet.py`：13 项研究上下文包，绑定 state_version / digest / 证据摘要 /
  Skill 版本 / Domain 摘要，失效可检测且禁止清空或重新 Bootstrap。
- `scripts/subagent_context.py` + `references/subagent-context.md`：五个角色契约与五条
  权限不变量（裁剪不得扩张权限）。
- `references/anchor-policy.md`、`references/insight-to-method-policy.md`、
  `references/reference-index.md`、`references/execution-checklist.md`、
  `references/design-rationale.md`、`references/development-selfcheck.md`：原 `SKILL.md`
  内容的权威落点。
- `preset-registry.json` 每个预设新增 `context` 依赖声明；`start-project` 走 `entry_context`。

### Changed
- `SKILL.md` 重构为 L0 常驻核心（156,565 → 28,037 bytes，−82%），保留全部硬约束与被外部
  引用的锚点（§0.1 / §0.2 / §1.6 / §1.7 / §3.1.0）。
- `preset_router.load_preset_context()`：`loaded` 只记实际读取的正文，
  脚本引用改名 `referenced_scripts`，并附 `load_semantics`。
- `release_check.step_readwrite_parity`：改为 `policy ↔ phase-*.md` 逐格比对；
  新增 `step_stage_index_parity`（阶段集合齐备 + 读写列不得回流到 L0）。
- `release_check` 新增 `step_context_architecture`：依赖声明、章节索引、子 Agent 契约、
  L0 上限（40,000 bytes）与 13 个硬约束标记。
- frontmatter 的「24 条机械硬规则」更正为 31 条（S1—S7 + V1—V24）。

### Fixed
- `PE17` 在 `policy_evolution.py` 与测试中使用但规则表未定义 → 补入 `skill-rsi-policy.md`。
- R12 两条独有规则（叙事被淘汰 ≠ 科学被证伪；`已证实`/`已证伪` **不得用来**描述修辞方案）
  迁入 `phase-r12-narrative.md`，避免随 §4 删除而丢失。
- 三处与 `literature-policy` / `project-layout` 冲突的「记入根 INDEX 的 Warnings」表述
  在迁移时**未搬运**，矛盾随重复一起消失。
- 迁移引入的 18 个文件悬空相对链接已机械修复。

### Compatibility
- 不需要迁移任何项目的 canonical state。新增的只有可重建的派生索引。

## 2.1.1 — 2026-11-10

Storage migration safety patch (transaction integrity). See `docs/releases/v2.1.1.md`.

### Added
- Cooperative maintenance lock (`.rlp-migration/control.lock`, `flock`) held
  exclusively by migrate/rollback; RLP write entries hold it shared and refuse
  control-plane writes during maintenance (`MAINTENANCE_IN_PROGRESS`).
- Four-point source-stability check; `SOURCE_CHANGED_DURING_MIGRATION`.
- Full durable control-plane manifest (type/size/SHA-256/symlink/mode); rollback
  compares the whole plane and refuses with `ROLLBACK_REFUSED_NEW_WORK`.
- Journal lifecycle states and corruption detection (`JOURNAL_CORRUPT`), explicit
  recovery actions, `--apply`-gated safe recovery.
- Document rewrite transaction: staged bytes, post-cutover per-file atomic commits,
  journal records and byte-exact restoration.

### Changed
- `migrate --apply` requires `--assume-writers-quiesced`; external writers are listed
  as unprotected instead of implied to be stopped.
- `verify` compares against the manifests recorded during the migration, not a fresh
  self-generated manifest.
- Backup boundary and symlink handling hardened (no follow-out-of-root, no backup
  inside a control root).

### Compatibility
- Machine protocol namespace unchanged; journal schema moves to `@2` while v2.1.0
  journals remain readable.
- Rollback returns the project to `MIGRATION_REQUIRED` — never to normal execution.

## 2.1.0 — 2026-11-10

Project storage unification and safe legacy migration. Released on the
`research-lifecycle-protocol/dev` branch; the tag follows the merge to `main`.
See `docs/releases/v2.1.0.md`.

### Added
- The storage matrix: `.research-lifecycle-protocol/` is the only runtime control
  root; `NEW_PROJECT / READY / MIGRATION_REQUIRED / AMBIGUOUS_STORAGE_ROOT /
  INVALID_STORAGE_ROOT` are stable, machine-readable states
  (`scripts/rlp_paths.py runtime_status/resolve_runtime_root`).
- `scripts/migrate_project_root.py`: read-only inspect/plan, verified external
  backup, same-filesystem staging with atomic rename cutover, opt-in
  manifest-tracked operational rewrites, post-migration verification, guarded
  rollback and interrupted-run recovery. Never re-bootstraps, never rewrites
  historical records, never silently repairs.
- `scripts/domain_replay.py` evaluation harness and four structural MRI replay packs
  (CT-FM / Wave-TOF) for the future blinded real-project A/B (L3 NOT YET VALIDATED).

### Changed
- Runtime write entries gate on the storage matrix: research loop, operational
  reconcile, managed execution (issue/run), cognition projections, render_status
  and Cold Handoff `take`. `MIGRATION_REQUIRED` is an engineering control-plane
  state — it never enters Failure Memory or triggers replanning.
- Static storage-spec check (`test_storage_spec.py`): runtime modules may not
  mention the legacy root; SKILL.md may discuss it only in a marked
  legacy/migration/compat context.

### Compatibility
- Machine protocol namespace (`research-idea-pipeline/...@1`) stays frozen.
- Legacy projects keep loading read-only (state_check, legacy detect, migration
  tooling); formal runs require migration. No automatic migration ever runs.

## Unreleased — 2026-10-24

Research-first communication, internally managed operations, evidence-grounded autonomy.
Integrated on main without a new release tag. The current released version remains
1.1.0; these changes are unreleased until the next explicit release.

### Added
- `references/scientific-communication-policy.md`: default
  `Problem → Insight → Method → Evidence → Decision` report, dynamic length, six-question
  method-depth check, causality/smoke/fabrication prohibitions, default-hidden operational
  details, explicit audit expansion and the R12 boundary.
- `references/operational-autonomy-policy.md`: A/B/C operation classes, automatic routine
  maintenance, evidence-gated scientific updates, unchanged privileged actions, termination and
  stale-telemetry rules, bounded recovery and pre-report reconciliation.
- `scripts/operational_reconcile.py`: thin coordinator for idempotent cognition/STATUS refresh,
  scheduler/monitor freshness, prepared outcome-bundle detection, and structured holds.
- `examples/scientific-reporting.md`: before/after X88–X90 examples plus audit expansion.
- `scripts/test_operational_reconcile.py` and `scripts/test_scientific_communication.py`.

### Changed
- `research-loop` now reconciles before selecting an action, emits `operations` /
  `operational_holds`, excludes stale scheduler actions and no longer dispatches stopped
  experiments as if they were runnable.
- `state_check.py` prints EO1/EX1 rows by default instead of only the violation count.
- Shared contract, invocation prompts, preset protocol, scheduler policy, research-state policy
  and evidence policy point to the two new policies.

### Fixed
- The loop previously declared a cognition projection write without executing it.
- A stale scheduler could still supply `next_actions` when its `state_version` did not match
  canonical state.
- A structured stop record (`SIGTERM` / user pause) could be treated as runnable work; it is
  now held as non-completion and never converted to `done` or negative evidence.

## 1.1.0 — 2026-10-18

Skill-RSI 集成版。**代码合并提交**与**发布提交**分离：先以单次提交把开发分支的可分发树
（不含 `.dev/`）并入 `main`，再以本提交升级版本、CHANGELOG 与 Release Notes。

**Added**
- Insight-to-Method Transition：Sketch → Candidate → Preference → Contract → Minimal Test，
  产物落盘于 `<route>/methods/` 并从磁盘恢复；`indeterminate` 不再被默认取第一个候选。
- Research Resume 与 Cold Handoff 的入口分类（`legacy_handoff.resume_decision`）。
- 科研选择比较：四轴（Importance / Insight / Elegance / Evidence）给出 `prefer` / `indeterminate`、
  反对意见、最大不确定性与“复杂度是否必要”，不产生综合评分。
- 只读深度科研总结（11 节 + 统一回报契约），配套通用提示词与 `research_summary.py`。

**Fixed**
- P0 账本完整性：启动失败退款改为在锁内基于重新读取的链写入，并绑定实际消费事件；
  拒绝重复/跨 family/伪造退款。此前锁外追加会破坏哈希链，导致账本永久 `LEDGER_TAMPERED`。
- P1 预算口径统一（`issue()` 与 `run()` 同用 `effective_spend`）；人工例外在预算闸门之前校验，
  仅解除资源限制。
- P1 argv 解析与真实 `subprocess` 一致（裸命令走 PATH，路径形式直接打开），
  不可启动的 `argv[0]` 在执行前被拒绝；启动失败与执行失败语义分离。
- 畸形输入不再以未捕获异常终止闸门（非对象 state、空 argv、损坏账本行）。

**Verification**
- L1（实现有效性）：**已验证** — 2054 tests OK / 3 skipped、9 个模块 selftest、`release_check.py` PASS。
- L2（运行有效性）：**部分验证** — 离线回放、真实文件锁与账本、真实 exec 失败路径；真实 GPU /
  外部 Harness 未验证。
- L3（科研有效性）：**未验证** — 未做真实科研 A/B；本版本不主张任何真实科研收益。

见 [docs/releases/v1.1.0.md](docs/releases/v1.1.0.md)。

## 1.0.0 — 2026-10-10

首个正式稳定版。功能集合与 v2.3.3 之后的 main 一致（含 Loop Runtime Correctness Hotfix 与
R7 Assurance 作者工具），并完成发布元数据统一与 R7 `--output` 路径校验修复。

见 [docs/releases/v1.0.0.md](docs/releases/v1.0.0.md)。

### Fixed
- `evidence_outcome.py assurance-store --output <route>/assurance/outcome/<analysis_id>.json`
  曾因比较最后两段路径组件（`("assurance","outcome")`）而被错误拒绝；现改为与由当前
  State route 推导出的**期望路径**比较：同一文件接受，其他 route、其他文件、路径穿越或
  symlink 越界一律拒绝（原有原子写、文件锁、过期与重复提交规则不变）。

### Added
- 自动化版本一致性检查：`scripts/test_release_metadata.py` 与 `release_check.py` step 17
  （SKILL.md / 两个 README / CHANGELOG / Release Notes 必须一致；Schema 与协议 id 不随发行版本漂移）。

## 发行历史（组件历史迭代，按真实 tag 记录）

| 版本 | Tag | Commit | 日期 | 说明（提交标题） |
|---|---|---|---|---|
| 1.2.0 | `research-idea-pipeline/v1.2.0` | `2c633beb` | 2026-10-05 | chore(repo): 新增根级 .gitignore |
| 1.3.0 | `research-idea-pipeline/v1.3.0` | `43b643e0` | 2026-10-06 | release(research-idea-pipeline): v1.3.0 —— bump metadata.version 1.2.0 |
| 1.4.0 | `research-idea-pipeline/v1.4.0` | `3d0b1308` | 2026-10-06 | release(research-idea-pipeline): v1.4.0 —— bump metadata.version 1.3.0 |
| 2.0.0 | `research-idea-pipeline/v2.0.0` | `4303b6c5` | 2026-10-06 | chore: main 不包含开发文档（docs/ 属开发产物，与 skill 交付无关） |
| 2.1.0 | `research-idea-pipeline/v2.1.0` | `e797af15` | 2026-10-07 | Merge branch 'research-idea-pipeline-dev' into main — research-idea-pi |
| 2.1.1 | `research-idea-pipeline/v2.1.1` | `fd2b63ea` | 2026-10-07 | release(research-idea-pipeline): v2.1.1 |
| 2.2.0 | `research-lifecycle-protocol/v2.2.0` | dev | 2026-11-10 | release(research-lifecycle-protocol): v2.2.0 — Context & Architecture Optimization |
| 2.2.0 | `research-idea-pipeline/v2.2.0` | `a889ce38` | 2026-10-08 | docs(research-idea-pipeline): 移除已失效的网络不可用自述（SSH/DNS 已恢复） |
| 2.3.0 | `research-idea-pipeline/v2.3.0` | `4baf4585` | 2026-10-09 | Merge feat/cognitive-insight-engine: Cognitive Insight Engine (R0—R14  |
| 2.3.1 | `research-idea-pipeline/v2.3.1` | `ba9b9cbc` | 2026-10-09 | Merge feat/cognitive-insight-engine: Research Preset Library v2.3.1（共同 |
| 2.3.2 | `research-idea-pipeline/v2.3.2` | `c7acd959` | 2026-10-09 | Merge fix/r10-outcome-loop-liveness: R10/R11 完成判定改用正式事务凭证，修复 Autonomou |
| 2.3.3 | `research-idea-pipeline/v2.3.3` | `7e7942d3` | 2026-10-10 | chore(research-idea-pipeline): 版本号 2.3.2 → 2.3.3（运行时正确性修复） |

> 这些历史 Tag 与 Release 仍然有效，本文档不改写其内容。是否清理旧 Tag 由发布决策单独批准；
> 归档索引见本次发布准备记录（`.dev/`，不进入 main）。
