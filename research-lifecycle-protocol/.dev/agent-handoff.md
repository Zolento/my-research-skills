# Agent Handoff — research-lifecycle-protocol/dev（branch-local）

## 待办：v2.4.1 之后的文档修订（只在 dev，未进 main）

`docs/releases/v2.4.1.md` 与 `references/identity-and-compatibility.md` §9.1 原写「四路信号中前三个
成立而门禁不成立」。四路信号的列举顺序里，前三个包含 `scientific_gate_ok`，所以那句话描述了一个
不可能出现状态。已改为点名：`storage_integrity_ok`、`historical_state_unchanged`、
`legacy_violations_preserved` 为真，`scientific_gate_ok` 为假。

修订提交 `793c0b2` 只在 `research-lifecycle-protocol/dev`。**没有合进 `main`**：`release_check.py`
的发布元数据步骤要求 main 的 HEAD 正好等于 tag 指向的提交，任何 post-tag 提交都会让那一步失败
（实测：`v2.4.1 points at 5b4a52b5, not at the release commit`）。所以 main 仍停在 `5b4a52b`，
显示旧措辞；这条修订随下一个版本进入 main。tag `research-lifecycle-protocol/v2.4.1` 未动。

下一轮只读预检不受影响。八切点崩溃注入矩阵的缺口仍按发布说明披露，不阻断预检。

## 第五轮：v2.5.0 发布前正确性审计（2026-11-21）

### 修了什么

| 缺陷 | 影响 | 修法 |
|---|---|---|
| P0-A 纯语言保护漏检 | 无单位数值、否定方向、重复值只改一处都可能放行 | 受保护清单按出现次数比较；新增「否定方向」；输出固定带 `semantic_review_required` |
| P0-B ID 并发分配 | `O_EXCL` 只保护完整路径，两个进程可拿同一 ID | 控制根内短时锁覆盖「查号→选号→校验→建文件」；未注册路线、非法 slug、缺 docs 目录都不建任何目录 |
| P0-C review 被误判 | `F003-theory.md` 与 `F003-review-r01.md` 共存被当成冲突 | 主文档与 review 分开索引；只报主文档重复、同轮 review 重复、只有 review 无主文档 |
| P1-D staged 上下文 | 不传 `--root` 跳过项目检查；链接按工作区判定 | 默认从仓库根推断项目根；链接按索引判定，工作区独有/本次删除判 BLOCK，无法判定判 REVIEW |
| 门禁不一致 | `allocate` 生成自由 slug 与 `type: null`，过不了 `preflight` | allocate 只接受 DI-8 枚举、写好 `type`、anchor 固定 R000；既有自由 slug 规则未放宽 |

### 兼容性

- 15 份真实文档的检查结果**逐条不变**（2 BLOCK / 315 WARN / 4 REVIEW，位置相同）。
- 未改 DQ 编号、未放宽目录规则、未动科研门禁与 Research State。
- `allocate` 的合法 slug 范围变窄：自由 slug 文档只能手写（`preflight` 仍拒绝它们，这是既有规则）。

### 读数

`release_check.py` PASS；离线 2563 tests；`test_doc_quality.py` 76 例。

## 第四轮：v2.5.0 中文科研文档的类型感知质量检查（2026-11-21）

### 读数

- `release_check.py` PASS；离线 2530 tests（新增 `test_doc_quality.py` 43 例）。
- 15 份真实 route F 文档：句子层原报 658 条 hard → `doc_quality.py` 判 2 条 BLOCK
  （都是真实的跨路线裸文件名链接）、315 WARN、4 REVIEW_REQUIRED。

### 判断

- **D-16 分级以确认强度为准，不以严重度为准。** BLOCK 只放机器能确认的结构错误；
  可读性归 WARN；科学判断归 REVIEW_REQUIRED。
- **D-17 linter 的 hard 不等于门禁的 hard。** 整篇文档尺度上，分号与句长是 WARN；
  套话仍为 BLOCK；「闭环」在 MRI 语境是术语，宣传词因此降级。
- **D-18 纯语言修改是可执行承诺。** compare 抓公式、数值、指标、ID、DOI、摘要、路径、
  情态、数据范围；用 mode 区分「伪装成润色的科学改动」与「已授权的科学修订」。
- **D-19 ID 分配用 O_EXCL，不建第二套登记表。** `layout_guard.py allocate` 撞车自动换号。

### 未做

- 不改 R0—R14、Evidence Qualification、Outcome 门禁、Research State schema、真实实验冻结件。
- 不做对话回复 linter，不碰三家 Hook。

### 下一轮候选

1. 把 `doc_quality.py check --staged` 接进真实项目的 pre-commit。
2. F008 的两处跨路线链接按 `../../E/docs/` 修正（需项目侧决定）。
3. 在 route F 上跑一次全量 `check`，把 REVIEW_REQUIRED 逐条过一遍。

## 第三轮：P0/P1 修复 + 迁移器加固 + 历史保留迁移（2026-11-20，2.4.0 之后）

### 读数

- `release_check.py` PASS；迁移四套测试：transaction 55、storage_migration 17、storage_spec 7、
  legacy_handoff 49，全绿。全量离线 2454+ tests。
- 虚拟项目 `.rlp-lab` 端到端 0 failure。沙箱演练：带 EO1 债务的旧项目在保留模式下
  `MIGRATED_WITH_LEGACY_ISSUES`，`storage_integrity_ok=true`、`scientific_gate_ok=false`、
  `legacy_violations_preserved=true`。

### 交付

| 件 | 说明 |
|---|---|
| P0 | SKILL §1.4 两种选模并列表述；CSM `not_applicable` 核对线圈数（profile `coils` 或 `csm.coil_count`，未知即拒绝）；选模协议与 profile `model_selection.protocol` 双向一致 |
| P1 | `report_ref` 必须真实存在、内容含本次 `selection` 与 `csm.mode`、摘要进入绑定；训练报告过一遍 `report_lint` 并把结果写进绑定（advisory）；`REP-03` 改为值级校验；修正 `rlp_paths.py resolve --project` 示例 |
| P2 | 删除 `layout_guard` audit 的不可达代码；`report_lint --quiet`；降噪口径写进沟通政策 |
| 迁移 | `preserve_known_legacy_violations` 模式 + 四路 verify 信号 + 快照完整性/备份容量/回滚/日志/锁残留/空根七项修复 |

### 设计判断

- **D-12 存储迁移与科研合规解耦。** 可读可追溯的历史债务允许无损搬运，但必须绑定逐条基线与
  state digest，且结果状态是 `VERIFIED_WITH_LEGACY_ISSUES`。绝不返回 `VERIFIED`。
- **D-13 基线用逐条比对，不用计数。** 同数量不同条目、描述被改都拒绝；staging 阶段再比一次。
- **D-14 三类结论分开报。** 存储迁移成功 ≠ 科研状态合法 ≠ 路线可继续执行。
- **D-15 报告 lint 只做结构。** 接进 `report_ref` 绑定是「调用既有 lint」，不新增门禁。

### 真实项目（MoSA）状态

未执行任何 `migrate --apply`。Route A 保持 active，31 条历史违规原样保留，DEC001 未改，
X92 未改。等待用户许可后再按「Git 状态 → 源快照 → 外部写入者 → 备份位置 → 授权」顺序核对。

### 下一轮候选

1. 真实 MoSA 迁移演练（只读 plan + 备份连通性验证），不切换。
2. 把 `layout_guard.py check` 接进项目 pre-commit。
3. `.dev/` 五份记录在合并时按 PROMOTE / KEEP_BRANCH_ONLY / DELETE 处理。

## 最新一轮：v2.4.0 执行边界与目录合规分离（2026-11-20）

**状态：开发完成，停在 dev 分支，未合并 main、未打 tag、未刷新全局安装。**

### 交付

| 件 | 说明 |
|---|---|
| `scripts/layout_guard.py` | DI-1—DI-8 的执行器：`preflight` / `check` / `audit` / `selftest`，退出码 0/3/4 |
| `scripts/test_layout_guard.py` | 30 用例（允许/拒绝两侧、registry 两形状、XID 三来源、宽模式拒绝、审计分级） |
| `templates/AGENTS.project.md` | 执行契约模板 6.7 KB，受控中文硬违规 0 |
| `templates/layout-policy.template.json` | 路径例外骨架（窄模式 + 授权 + 复审条件） |
| `references/project-layout.md` §0 | 四层分工、优先级拆分、`AGENTS.md` 边界与体量、guard 判定表 |
| `references/invocation-prompts.md` | B0 增加 `layout_guard.py audit`（不自动整理目录） |
| `references/project-intake.md` | 盘点第 2 步加路径审计 |
| `release_check.py` | 新步骤 `Project layout guard` |
| `docs/releases/v2.4.0.md` + `CHANGELOG.md` | 发布说明与条目；版本 2.4.0 全链一致 |

### 读数

- `release_check.py` **PASS**（25 步）；`test_layout_guard.py` 30 OK；`layout_guard selftest` 0。
- 虚拟项目 `/home/lenovo/code/myproj/skills-dev/.rlp-lab/rlp-fixture` 端到端 0 failure
  （clean audit / 6 preflight / check / state_check / render_status / resolve / MRI sync /
  注入违规判 3 / 恢复判 0）。重建：`python3 .rlp-lab/build_fixture.py --verify`。
- `AGENTS.md`：模板 6657 B；加 MRI 受管块 10037 B（warn 12000 / block 20480）。
- 六个存量项目审计（只读）：`block` 合计 596 项，明细见 `.dev/layout-audit-2026-11-20.md`。

### 设计判断

见 [.dev/boundary-redesign.md](boundary-redesign.md) §4。要点：`AGENTS.md` 是执行边界而不是
`layout.json` 的投影（D-1）；纯伴随/密度补偿禁令**留在项目**（D-3，残余风险已登记）；
托管块保留但按 Skill 投影管理（D-4）；不提供 `agents_migrate.py`（D-6）。

### 第二轮：MRI Contract v1.0 接入（同日）

- 受管段重写：9 条 + MRI-10 CSM 来源；全文副本 `docs/contracts/mri-research-contract-v1.0.md`。
- `mri_training.py`：`full_val_gt` / `gt_free_frozen` 平权；`best_val_metric` ∈ PSNR / complex_NMSE；
  `csm.mode` 三值 + `source` / `sample_identity` / `protocol_ref` / `eval_reference`；
  与领域 profile 交叉核对。
- 新增 `report_lint.py`（REP-01—07）、`test_report_lint.py`、`test_mri_training.py`（40 用例）。
- `test_execution_gate.py` 增加 GT-free 端到端通过 + 无冻结方案拒绝两条。
- `layout_guard.py`：体量预算只计项目自撰部分（受管块 6.4 KB 单列）；`--quiet` / `--summary`。
- 读数：`release_check` PASS；`test_mri_training` 40 OK；虚拟项目 verify 0 failure
  （AGENTS.md 总计 13949 B，受管块 6179 B，项目自撰 7770 B）。

### 下一轮候选

1. 逐项目处理 6 个存量项目的 `block`（需用户授权；先登记窄例外还是整改要分项目判断）。
2. 把 `layout_guard.py check` 接进各项目 pre-commit（脚本已可用，强制与否归项目）。
3. `research-idea-pipeline` 旧目录（skills-dev 根下）仍是 2.x 之前的残留，未处理。
4. L0 仍 28.9 KB（上限 40 KB）；再加内容前先看 `docs/rule-relocation-matrix.md`。

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
| F 回归 | 2339 tests OK（skipped=4）、`release_check` PASS、MRI replay 4/4、安装副本 smoke PASS |
| F+ 审查补丁 | 4 个执行链路缺陷已修（章节加载 / domain 绑定 / 超预算 PASS / Router 消费计划） |

### 实测读数

- 每次调用协议上下文：平均 129,431 → 39,401 字符（−70%）；工具调用 4.08 → 3.75。
  `resume` / `context-drift` 由 3 升到 4（显式加载认知记忆两个章节，旧基线漏计）。
- 子 Agent 上下文：123,449 → 17,762 字符（−86%）。
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
