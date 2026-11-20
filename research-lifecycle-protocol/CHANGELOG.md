# Changelog — research-lifecycle-protocol

本文件记录 Research Lifecycle Protocol 的正式发行历史。**当前正式稳定版：2.4.0**。
版本序列从 1.0.0 重新建立；此前的 v1.x / v2.x 是同一组件的公开开发迭代记录，原样保留、不改写。

格式：`## <version> — <date>`，条目分为 Added / Changed / Fixed / Security / Docs。
每个版本的权威说明见 `docs/releases/<version>.md`。

## 未发布 — dev 分支（在 2.4.0 之后）

### Added

- **历史保留迁移模式** `--preserve-known-legacy-violations`：把「存储完整性」与「科研状态合规」
  分开。可读、可追溯但违反当前科研规则的历史状态（如 Outcome Policy 在结果之后才冻结）
  可以在绑定逐条违规基线与 state digest 后无损搬运；结构损坏、状态不可解析、哈希链损坏
  在任何模式下仍然拒绝。`verify` 分为 `storage_integrity_ok` /
  `historical_state_unchanged` / `scientific_gate_ok` / `legacy_violations_preserved`
  四个信号，保留模式下返回 `VERIFIED_WITH_LEGACY_ISSUES`，不返回 `VERIFIED`。
- `plan --baseline-out` 与 `migrate --violation-baseline`：迁移决定绑定一份已审阅的清单，
  基线漂移（含同数量不同条目）一律 `REFUSED`。

### Fixed（第二轮）

- **`verify` 的证明材料改为强制项**：缺 `source-snapshot.json`、`source-fingerprint.json`，
  或在保留模式下缺 `violation-baseline.json`，一律 `VERIFY_FAILED`。旧实现读不到就跳过该项
  比对，删掉一份证据即可让不完整的验证通过。基线文件损坏、或摘要与内容自相矛盾，同样失败。
  `rewrite-manifest.json` 在本次迁移发生过重写时强制；没有重写请求的迁移现在也会写一份空清单。
- **成功提示不再建议删除归档**：`.rlp-archive/<id>` 与 `.rlp-migration/<id>` 是回滚与校验所需的
  证据，提示改为要求保留，删除留给人事后决定。
- **`test_migration_transaction.py` 的测试入口移回文件末尾**：新增测试类曾排在
  `if __name__ == "__main__"` 之后，直接运行脚本时不会执行。

### Fixed

- **快照不再静默跳过不可读目录**：`snapshot()` 记录 `unreadable` 并置 `complete=false`；
  预检与复制都把它当硬失败。旧行为会让迁移在数据缺失的情况下仍报 `MIGRATED` 且 `verify ok`。
- **备份容量按文件系统分别核对**：`plan` 分别报告 `project_free_bytes` 与 `backup_free_bytes`，
  两者都要有余量。旧实现只查项目盘，备份盘已满时会在事务中途失败。
- **回滚不再留下「无控制根」现场**：目标旧根被占用时直接拒绝且不移动任何目录；归档移动失败
  时把新根放回原位并返回 `ROLLBACK_FAILED`。旧实现会把新根挪到 forward-root 后失败。
- **被拒的尝试不再遮蔽真实迁移**：`refused` 事件保留为审计记录，但 `journal_state` 只把
  带生命周期事件的尝试当作「当前尝试」，`_completed_migration` 扫描全部记录。
- **`--rewrite` 的忽略项会报告**：指向历史证据或不存在文件的请求进入 `rewrites_ignored`，
  不再静默跳过。`--rewrite` 支持重复指定。
- **崩溃残留的锁文件可见但不阻塞**：`maintenance_status` 增加 `owner_alive` 与 `stale`。
  内核会随进程释放 `flock`，残留文件不再被当作活跃持有者，也不被无声忽略。
- **空旧根不再可迁移**：旧根没有任何可识别的控制平面内容时预检直接拒绝，
  避免切出一个 `INVALID_STORAGE_ROOT` 的新根。

## 2.4.0 — 2026-11-20

### Added

- **MRI Research Contract v1.0 接入**：`domain-profiles/mri-reconstruction/training-policy.md`
  受管段重写为 Contract v1.0 简版（9 条 + MRI-10 CSM 来源），内置原文副本
  `docs/contracts/mri-research-contract-v1.0.md`。两种合法选模协议 `full_val_gt` /
  `gt_free_frozen` 均可执行；`best_val_metric` 只收 `PSNR` 与 `complex_NMSE`。
- `scripts/report_lint.py` + `scripts/test_report_lint.py`：用户报告的结构检查
  （`REP-01`—`REP-07`），只拦客观缺字段与格式违规，不是科研门禁。
- `scripts/test_mri_training.py`：40 用例覆盖同步幂等、两种选模、CSM 三模式与 profile 交叉一致。
- `scripts/layout_guard.py`：项目组织规范（DI-1—DI-8）的执行器。`preflight` / `check` /
  `audit` / `selftest` 四个动作，13 类路径 kind、route 与 XID 登记核验（预注册 / manifest /
  canonical state 三处）、`routes/<R>/docs/` 扁平、受保护入口与软链接穿越、`AGENTS.md` 体量。
- `scripts/test_layout_guard.py`：允许与拒绝两侧的 fixture，含两种真实 registry 形状、
  三处 XID 登记、宽模式拒绝、审计分级与退出码 0/3/4。
- `templates/AGENTS.project.md`：项目执行契约模板（≤ 6.6 KB），只写执行边界。
- `templates/layout-policy.template.json`：路径例外登记骨架（窄模式 + 授权人 + 理由）。

### Changed

- **四层分工定稿**：`AGENTS.md` 管执行边界，RLP 管科研生命周期，项目契约管具体实验，
  `layout_guard.py` 管目录合规。`references/project-layout.md` §0 重写。
- **优先级拆分**：布局可以让（用户指令 ＞ 冻结协议 ＞ `AGENTS.md` ＞ RLP 默认布局），
  **门禁不能让**（state 转换、证据资格、强制门禁不受该顺序影响）。
- `AGENTS.md` 不再作为规则副本的合法载体：重复记述按内容错误处理，删副本留指针；
  体量 >10 KB 告警、>20 KB 违规。

### Changed（续）

- 灵敏度来源（MRI-10）：默认强制数据集存储 CSM；只有显式联合估计灵敏度且在启动前冻结
  方法协议的方法类别例外。例外不覆盖跨方法比较的评估参考。
- `layout_guard.py` 的 `AGENTS.md` 体量预算改为**只计项目自撰部分**，Skill 注入的受管块
  按 SHA 单独校验，不计入预算。
- `layout_guard.py` 与 `operational_reconcile.py` 增加 `--quiet` / `--summary`：
  正常通过时不出声，HOLD 与阻塞照常输出，退出码不变。

### Fixed

- 六个真实项目的布局漂移此前无任何机制可发现（未声明顶层目录、`log/` 与 `logs/` 并存、
  控制目录 31 份 `research-state.*.json`、`docs/` 子目录、缺 `STATUS.md`）。`audit` 现在
  逐项报出并分级。
- 模板命名为 `AGENTS.md` 会被 agent 运行时当作指令自动加载；模板统一用 `.project.md` 后缀。

详见 [v2.4.0 发布说明](docs/releases/v2.4.0.md)。

## 2.3.1 — 2026-11-18

- 多线圈评估采用 MoSA 线圈合并口径。使用存储 CSM 做复数共轭加权求和，GT 与重建共用评估尺度。
- 明确自监督 mask split 损失可用于参数更新，`best_val` 按完整 val GT 的 PSNR 或 NMSE 选择。执行门禁拒绝声明使用损失留出测量的选模配置。

详见 [v2.3.1 发布说明](docs/releases/v2.3.1.md)。

## 2.3.0 — 2026-11-18

### Added

- 所有 MRI 重建路线执行统一的数据划分、尺寸、mask、checkpoint、指标和训练前报告规范。
- MRI 项目启动时同步项目根 `AGENTS.md`。`issue` 和 `run` 核对已识别 MRI 项目的规则与绑定配置。

### Changed

- 全监督和自监督统一用完整 val GT 的 PSNR 或 NMSE 选 `best_val`，完整 test 用于最终报告。
- 自监督训练继续使用约定的拆分和损失更新参数。禁止用自监督 mask split 损失或测量残差选模。

详见 [v2.3.0 发布说明](docs/releases/v2.3.0.md)。

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
