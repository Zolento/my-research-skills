# Reference Index（完整资源目录）

> **唯一目录。** `SKILL.md` §2.3 只列「按域最常用的一份」，本文件列**全部**资源。
> 新增或改名任何 reference / template / script 时必须同步本文件与
> `references/section-index.json`（`python3 scripts/section_index.py build`）。
>
> **加载条件：** 需要找「这件事的权威文件在哪」时加载。**不要**在每个任务里默认加载。

本文件由 v2.2.0 的 L0 精简产生：内容来自 `SKILL.md` §2 的共享资源索引，未改变任何条目。

## 1. 资源目录

| 资源 | 位置 | 内容 |
|---|---|---|
| 子代理角色库 | [references/roles.md](../references/roles.md) | 会议审稿人 R-CVPR / R-ICML / R-NeurIPS / **R-MICCAI**（**仅 venue calibration 用，不参与科学发现**）；**攻击面审稿人 R-Novelty / R-Causal / R-Experimental / R-Theory / R-Generalization / R-Utility**；A-Author / A-Experimenter；S-Lit / S-Nov / S-Theory / S-Feas / S-Devil / S-Repro / **S-Integrity** |
| 顶会创新性标准 | [references/venue-standards.md](../references/venue-standards.md) | CVPR / ICML / NeurIPS / MICCAI 四视角锚定标准 + 防复现标准 |
| 叙事 preset 库 | [references/narrative-patterns.md](../references/narrative-patterns.md) | **十套叙事 preset（N1—N10，非互斥、非创新等级）**、**(O,T,R) + anchor 选 preset**、**六槽位 S1—S6**、跨域 **Transfer Legitimacy Argument（L1/L2/L3）**、禁用表述、叙事自检 |
| Rhetorical Realization | [references/rhetorical-operators.md](../references/rhetorical-operators.md)、[references/rhetoric-equivalence-policy.md](../references/rhetoric-equivalence-policy.md) | D4a 科学 hierarchy 与 D4b 表达搜索分离；冻结 14 项、RE1–RE5、盲恢复与配对敏感性；不优化 reviewer overall score |
| Realization 工具与模板 | [scripts/rhetorical_realization.py](../scripts/rhetorical_realization.py)、[scripts/validate_rhetorical_variant.py](../scripts/validate_rhetorical_variant.py)、[templates/narrative-realization.md](../templates/narrative-realization.md) | 有界生成、来源绑定、实际正文 gate、blind payload、恢复比较、多模型面板；独立 artifact，不迁移 State schema |
| **Claim-first 政策** | [references/claim-first-policy.md](../references/claim-first-policy.md) | **R12 现行（P0）**：总纲公式（`Claim strength × Evidence alignment × Reviewer comprehensibility`）、**证据台账 `epistemic_status`**、**Claim Graph `C0—C5` + `Ci ← Ej`**、**可证伪 central proposition**、**`(O,T,R)` 三轴**、**Anchor Eligibility Test**。**R3—R6 / R8 / R7 / R10 / R13 的接入登记为 P1**（见 `docs/claim-first-spec.md` §9） |
| 文献检索规范 | [references/literature-policy.md](../references/literature-policy.md) | 禁止只停留在本地、T1—T8 强制扩检、L1/L2/L3 尽职调查、饱和判据、429 退避、代理环境识别、缓存 |
| 项目组织规范 | [references/project-layout.md](../references/project-layout.md) | **Wave 6 目录规范**：**八条 DI invariant**、`routes/` 聚合、**`README`/`STATUS`/`INDEX` 三文件职责分离**、**`STATUS.md = f(research-state.json)` 投影**、`XID` 贯穿、`experiments/` 与 `results/` 分离、`docs/decisions/DEC`、**三层锚点体系落盘**（`anchor_role`/`serves`）、`docs/` 命名与 `slug` 封闭枚举 + `subtype`、**落盘三档**（交付物/中间产物/状态）、锚点变更单、route fork 门槛、Git 边界、`AGENTS.md` 优先与可达性校验、并发写入 |
| 评分与聚合政策 | [references/scoring-policy.md](../references/scoring-policy.md) | **两层**：**硬门禁 `G1—G5`（不聚合、不打分）** + **排序六维**（**R12 主用**）；1—5 标尺；极性归一化（**仅 R7 / R10 / R13 仍用**）；逐维度中位数、**一票否决 + 带条件的推荐出口** |
| 证据等级与措辞 | [references/evidence-policy.md](../references/evidence-policy.md) | **五类共享政策**：已核实 / 部分核实 / 据本次检索未见 / 待核实 / 待补证明 ↔ 允许与禁止表述；**§3 认知状态 ↔ 措辞等级映射**（各 R 阶段 不再各自定义） |
| **科研汇报政策** | [references/scientific-communication-policy.md](../references/scientific-communication-policy.md) | **默认用户汇报**：`Problem → Insight → Method → Evidence → Decision`、按阶段调整篇幅、**method-depth 六问**、因果 / smoke / 编造禁令、默认隐藏的操作细节、审计 / 调试展开规则、**R12 边界** |
| **运维自主政策** | [references/operational-autonomy-policy.md](../references/operational-autonomy-policy.md) | **A 类例行维护自动执行 / B 类证据门禁更新 / C 类特权动作仍由用户授权**；canonical 唯一写入、进程终止不等于完成、过期 telemetry 不得作决策依据、有限恢复、汇报前 reconciliation |
| **运维协调脚本** | [scripts/operational_reconcile.py](../scripts/operational_reconcile.py) | 薄层协调：A 类投影幂等刷新、scheduler / monitor 新鲜度、终态实验 outcome 条件检测、结构化 `HOLD`；**不重建证据门禁、不写第二套 canonical state** |
| 受控中文写作 | [references/writing-policy.md](../references/writing-policy.md) | **落盘文档 / 对话返回 / 子代理意见共用**：三档 **asd-ste100（可选最强档，须用户显式声明）/ Strict / 中文-顺**、结构规则（硬）、词汇规则（方向；asd-ste100 档下升为执行）、中文六种机器味、**情态是内容** |
| 受控中文 linter | [scripts/ste_lint_zh.py](../scripts/ste_lint_zh.py) | 机械首查：分号 / 超长句 / 虚动词 / 营销词 / 套话 / 同义轮换 / 被动 / 复合体貌 / 含糊词 / 半角标点；`--baseline`、`--disable`、`--selftest`（MIT，vendored） |
| 检索实现脚本 | [scripts/literature_search.py](../scripts/literature_search.py) | 可运行实现：**本地 + 多源**并集、每源状态、`--level`、`--exhaustive`、`--also-query`、`--venue`、`--cited-by`、退避、代理检测、`--check-env` |
| 多源适配器 | [scripts/literature_sources.py](../scripts/literature_sources.py) | arxiv（新）/ openalex（关系）/ crossref（出处）+ 跨源合并层 |
| 环境自检脚本 | [scripts/env_probe.py](../scripts/env_probe.py) | 发现工作解释器（已激活环境 → 项目 `.venv` → conda → PATH）；依赖缺失时退出码 4 |
| 离线测试 | [scripts/test_literature_search.py](../scripts/test_literature_search.py) | stdlib unittest，全离线（环境发现 / 跨源合并 / 等级判定） |
| PDF 索引脚本 | [scripts/refs_index.py](../scripts/refs_index.py) | 为 `docs/refs/` 下每个 PDF 建 `index.json` 条目；`--check` 校验（不一致退出码 3）、**`--migrate` 旧 schema 迁移（保留旧字段）** |
| 索引迁移测试 | [scripts/test_refs_index.py](../scripts/test_refs_index.py) | 离线测试：三种旧索引形状的迁移、「保留旧字段」、`--check` 退出码与提示 |
| **Research World Model 政策** | [references/research-state-policy.md](../references/research-state-policy.md) | **R1 权威**：八类一等对象（`C`/`E`/`AS`/`H`/`X`/`LIT`/`F`/`U`）+ `contract`、逐阶段读写时机、**Shape Gate S1—S7** 与 **V1—V24** |
| **World Model 模板** | [templates/research-state.template.json](../templates/research-state.template.json) | R1 常驻骨架（顶层直接是各对象数组）；**模板自身必须通过 S1—S7 与 V1—V24** |
| **状态校验脚本** | [scripts/state_check.py](../scripts/state_check.py) | **机械闸门**：**Shape Gate `S1—S7`**（在 V1—V24 之前跑）**+ 引用完整性 `V1—V24`**；`--check` / `--json` / `--selftest` / `--list-rules`；退出码 0 通过 / 3 硬违规（含形状）/ 4 环境 |
| 状态校验测试 | [scripts/test_state_check.py](../scripts/test_state_check.py) | 离线测试：S1—S7 与 V1—V24 各有反例 + 退出码行为 + 表格/契约键一致性 |
| **存量项目接管** | [references/project-intake.md](../references/project-intake.md) | 在**已有代码 / 实验 / 文献 / 结论**的项目里启动本 Skill 时的接管清单：9 个盘点维度、落盘映射、集中提问上限 |
| **调用契约（四个用户入口）** | [references/invocation-prompts.md](../references/invocation-prompts.md) | `start-project` / `continue-research` / `explore` / `audit`：固定用户调用契约，**用户不需要知道 `R` 编号**；防止实际使用时绕过新哲学（一上手就发散、编造状态） |
| **跨阶段调度（Meta-Controller）** | [references/scheduler-policy.md](../references/scheduler-policy.md) | `R0`—`R14` 是**能力**不是 workflow：八级 `next_action_policy` + `EIG ÷ cost`；telemetry 落 [scheduler.template.json](../templates/scheduler.template.json)，**不进 state** |
| **Structural Equivalence 政策** | [references/structural-equivalence-policy.md](../references/structural-equivalence-policy.md) | **跨阶段保证服务（不是第 16 个阶段）**：canonical scientific structure（十四个 facet + 十一个 typed relation）、domain-aware / domain-stripped 两套表示、load-bearing delta、Counterfactual Collapse Test、verdict 十值（含 `paradigm-candidate`）、audit artifact 契约、SENA-1（R7）/ SENA-2（R13）、无 score 纪律、`EQ1`—`EQ13` 机械闸门；**§15 起为 near-neighbor 判断层**：`near_neighbor_verdict` 八值、Preserved Core / Structural Delta、Local Neighborhood Test、Removal Test、Theory-Stripping（P5）、Structure-Preservation（P4）、provenance 四值 + 三值 relation、Null Hypothesis + Minimal Delta、claim-strength gate（不是 idea-kill）、population telemetry、对称不确定性闸门（未知证据既不膨胀也不塌缩）、禁 scalar 决定 novelty、`NN1`—`NN14` |
| **Structural Equivalence 模板** | [templates/structural-equivalence-audit.template.json](../templates/structural-equivalence-audit.template.json) | Minimal Structural Delta Certificate 骨架（schema `@2` = §8 基础键 + §24 near-neighbor 必填键）；**模板自身必须通过 artifact 侧 `EQ4`—`EQ13` 与 `NN1`—`NN14`**（`--route` 侧的 `EQ1` / `EQ2` / `EQ3` / `EQ12` 需要真实 state，模板不跑） |
| **Structural Equivalence 检查器** | [scripts/structural_equivalence_check.py](../scripts/structural_equivalence_check.py) | **机械闸门**：只查「审计做没做完整 / 引用是否存在 / schema 是否满足 / claim 强弱是否与 verdict 或 near_neighbor_verdict 相容」，**不宣判 novelty**，**不决定 H 与 P 是否结构等价**；两层规则 `EQ1`—`EQ13` + `NN1`—`NN14`；`--artifact` / `--route` / `--selftest` / `--list-rules`；退出码 0 / 1 / 3 / 4 |
| 路线级索引模板 | [templates/INDEX.md](../templates/INDEX.md) | `routes/<R>/INDEX.md` 骨架（**资产目录 + 时间线**：Route Overview / Key Documents / Experiments / Decisions / Reviews / Milestones / Recent Research Changes / Archive；**不含已证实/已证伪/TODO/Bugs/Warnings**） |
| 路线级状态模板 | [templates/STATUS.md](../templates/STATUS.md) | `routes/<R>/STATUS.md` 骨架（`research-state.json` 的投影；**由 `render_status.py` 生成**） |
| 根级索引模板 | [templates/INDEX.root.md](../templates/INDEX.root.md) | 根 `INDEX.md` 骨架（**路线总表投影**：`Route | Goal | Status | Thesis | Blocker` + 项目主锚点声明 + 全局 Warnings） |
| 路线级说明模板 | [templates/README.route.md](../templates/README.route.md) | `routes/<R>/README.md` 骨架（**路线身份证**：Research Question / Why / Relation / Thesis / Scope / Lineage / Resources / Entry points） |
| 串联示例 | [examples/](../examples/) | 主链路串联（`R3—R6 → R8 → R12 → R7`）、接续复核、单独文献调研、多路线目录管理的示例；**受控中文两档对照（asd-ste100 改写样例）见 [example-writing-tier.md](../examples/example-writing-tier.md)** |
| **认知记忆政策（CIE Phase 1）** | [references/cognitive-memory-policy.md](../references/cognitive-memory-policy.md) | 四类认知记忆（机制 / 异常 / 竞争 / 科学价值）、三层权威边界、支持等级推导阶梯、`CM1`—`CM10` 规则（`CM7`—`CM10` 为 warning，不翻转退出码）、记忆生命周期与 hot/warm/cold 加载、写入禁止项 |
| **认知记忆脚本** | [scripts/cognition.py](../scripts/cognition.py) | Memory Builder + Validator + Recall / Context Brief；`build` / `check` / `brief` / `recall` / `--selftest` / `--list-kinds`；**只读 canonical，从不写 `research-state.json`** |
| 认知记忆测试与示例 | [scripts/test_cognition.py](../scripts/test_cognition.py)、[examples/cognition/](../examples/cognition/README.md) | 离线测试（兼容性 / 可重建性 / 支持度推导 / 写入禁止 / 失效过滤 / CLI / fixture）+ 合成 fixture（**不是真实科研证据**） |
| **预测 / 异常 / 机制竞争（CIE Phase 2）** | [references/prediction-anomaly-competition.md](../references/prediction-anomaly-competition.md) | 可判定判据 `criterion`、**冻结的 branch mode**（`outcome_mode`/`branch_rule`）、观测包来源绑定、七类结果、**统一证据资格门（`PQ1`—`PQ8`，fail closed）**、竞争区分力、诊断→干预行为切换、Insight Card 与**按预测逐个绑定**的认证；规则 `PC1`—`PC11`；**不得自我认证创新性** |
| **预测比较器脚本** | [scripts/prediction_compare.py](../scripts/prediction_compare.py) | `freeze` / `compare` / `compete` / `switch` / `insight` / `--selftest`；判据形状、来源绑定、冻结完整性（`PC4`/`PC5`）、分支规则（`PC10`）、**唯一证据资格入口 `qualify_evidence`**、Insight 证据绑定（`PC11`）、区分力与行为切换 |
| **旧项目接管（Legacy Handoff）** | [references/legacy-handoff.md](../references/legacy-handoff.md)、[scripts/legacy_handoff.py](../scripts/legacy_handoff.py) | 已初始化项目**禁止重新 Bootstrap**；只读兼容性审计 `LH1`—`LH16`、`canonical` 无损、重建认知记忆、`unknown`/`retrospective` 标注、接管报告、幂等与回滚；**严重错误阻止写回** |
| 接管回归测试 | [scripts/test_legacy_handoff.py](../scripts/test_legacy_handoff.py) | 无损接管 / 跨会话重启 / 重复接管 / 缺失历史 / 失效传播 / 预测时间泄漏 / 多路线隔离 / 下一轮复用旧知识 / 严重错误阻止写回 |
| **科学价值与自适应发现（CIE Phase 3）** | [references/scientific-value-adaptive-discovery.md](../references/scientific-value-adaptive-discovery.md) | Decision Value / Discovery Potential 分维判断（**无总分**，`SV1`—`SV8`）、Taste Memory 双层权限、八种探索菜单到既有算子的映射、防锁死规则、`P4` 上下文隔离 |
| **策略记忆脚本** | [scripts/strategy_memory.py](../scripts/strategy_memory.py) | `value` / `taste` / `operators` / `recommend` / `apply` / `validate`；字典序排序（无权重）、探索下限、算子重启条件；**scheduler.json 只读** |
| **历史回放与验证（CIE Phase 4）** | [references/discovery-replay.md](../references/discovery-replay.md) | replay case schema、隐藏信息泄漏防护（`RP2`）、七维独立指标、四 arm 消融、十四个对抗 case、端到端 smoke；**未做真实 Agent A/B** |
| **回放脚本与 fixture** | [scripts/research_replay.py](../scripts/research_replay.py)、[examples/replay/](../examples/replay/README.md) | `validate` / `show` / `run` / `suite` / `ablate` / `adversarial` / `smoke`；可插拔 `--runner module:function`；fixture 为**合成**，不是真实科研证据 |
| **Skill-RSI 政策（策略级自我改进）** | [references/skill-rsi-policy.md](../references/skill-rsi-policy.md) | 在既有 R0—R14 与硬门禁内让**科研策略**演化：三层记忆分离（科学 / 决策经验 / 策略）、反事实证据分级（`OBSERVED` / `REPLAY_SUPPORTED` / `NO_SUPPORT`）、有作用域的策略候选与生命周期（`PROPOSED`→…→`ACTIVE`，失败 `REJECTED`/`HOLD`/`ROLLED_BACK`）、独立评价晋升、回滚、源码冻结与写入白名单；**不新增 canonical 对象、不新增 Preset、不在运行期修改 Skill 源码** |
| **决策轨迹脚本** | [scripts/decision_trajectory.py](../scripts/decision_trajectory.py) | `<route>/decision-trajectory.jsonl`：append-only + 哈希链 + 尾部摘要；Context / Decision / Prediction / Outcome / Learning；规则 `DT0`—`DT10`（过期状态、事后预测、结果泄漏、来源悬空、未合格证据不得声称科学增量）；**轨迹不是科学证据，永不写入 `evidence[]`** |
| **策略演化脚本** | [scripts/policy_evolution.py](../scripts/policy_evolution.py) | 有作用域的策略候选（`PE1`—`PE16`）、评价规则冻结、生命周期与晋升门、回滚、失败签名上限（换 `policy_id` 无效）；晋升后只经既有 `strategy_decision()` 生效 |
| **策略迁移脚本** | [scripts/policy_transfer.py](../scripts/policy_transfer.py) | 只读的三层记忆分离视图、基于**声明结构**（不是领域关键词）的迁移门 `PT1`—`PT11`、过期经验与已否证机制的拒绝、无损记忆压缩检查 |
| **源码冻结脚本** | [scripts/source_freeze.py](../scripts/source_freeze.py) | 受保护源码清单 + 规范路径/符号链接核验 + 写入白名单 + 哈希链审计事件；运行期检测到源码被改即 `HOLD` 且**不自动修订**；如实声明残余风险（Prompt 禁令不是安全边界） |
| **RSI 消融与开销** | [scripts/rsi_ablation.py](../scripts/rsi_ablation.py) | 四臂冻结之上追加 `rsi_full` 与 leave-one-out；逐维比较、报告不可区分与 `NO_SUPPORT`；字节/延迟/额外调用开销；L1/L2/L3 分别如实申报 |
| **领域协议（Domain Profiles）** | [domain-profiles/README.md](../domain-profiles/README.md) | **可选**领域研究协议；显式启用（`<route|project>/domain/<profile>.json`），未声明 = RLP Core；Profile 是规则扩展，不是第二份事实，不新增 canonical 对象 |
| **MRI 重建领域协议** | [domain-profiles/mri-reconstruction/PROFILE.md](../domain-profiles/mri-reconstruction/PROFILE.md) | 自监督/欠采样 MRI：物理与信息边界（[acquisition](../domain-profiles/mri-reconstruction/acquisition-contract.md) / [ssl](../domain-profiles/mri-reconstruction/ssl-contract.md)）、评价与阈值冻结（[evaluation](../domain-profiles/mri-reconstruction/evaluation-policy.md)）、任务变体（[CT→FM](../domain-profiles/mri-reconstruction/variants/cross-domain-generative-prior.md) / [Wave-3D](../domain-profiles/mri-reconstruction/variants/wave-3d-structure.md)）；规则 `DP1`—`DP14`（[scripts/domain_profile.py](../scripts/domain_profile.py)） |
| **平凡归因守卫（TAG）** | [domain-profiles/mri-reconstruction/attribution-guard.md](../domain-profiles/mri-reconstruction/attribution-guard.md) | 六类归因判定（`VALIDITY_BLOCKER` / `NOVEL…` / `REPEATED_ATTRIBUTION` / `PHYSICAL_LIMIT_WITH_SCOPE` / `METHOD_TRANSITION_READY` / `INSUFFICIENT_EVIDENCE`）；结构化机制指纹（非关键词匹配）；规则 `TG1`—`TG9`；事件链 `<route>/domain/tag-events.jsonl`；**不绕过 PEIG/AALG、不阻断真实缺陷**（[scripts/domain_guard.py](../scripts/domain_guard.py)） |
| **机制到方法搜索（MMS）** | [domain-profiles/mri-reconstruction/mechanism-search.md](../domain-profiles/mri-reconstruction/mechanism-search.md) | 六方向菜单（无聚合分）+ 方法候选十问契约 `MM1`—`MM8a`；经既有 I2M 进入 R8，不建平行流水线（[scripts/domain_mms.py](../scripts/domain_mms.py)） |
| **身份与兼容** | [references/identity-and-compatibility.md](../references/identity-and-compatibility.md) | Skill 名称 / 协议命名空间 / 运行目录三层边界；双根 fail-closed；旧项目兼容检查与人工迁移步骤（[scripts/rlp_paths.py](../scripts/rlp_paths.py)） |

---

