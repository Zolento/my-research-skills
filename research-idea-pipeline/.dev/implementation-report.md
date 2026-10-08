# Audit and development record (KEEP_BRANCH_ONLY)

Worktree: /home/lenovo/code/myproj/skills-dev/main. Initial branch main; HEAD and
main ref: 139c9e907e437443b640b57271c85236023616e7. Initial status clean. Existing
worktrees: main, failure-analysis (0d1eb80), zotero (139c9e9). No new worktree.
Development branch: feat/preflight-identifiability-loop-guard.

Baseline: release_check.py PASS; 551 tests, 4 skipped; 9/9 release checks PASS.
Full output: baseline-tests.log.

## Root causes

1. assurance kill_condition/discriminating_test is enforced by V9, but has no
risk severity/type/arm binding. critical/high can remain prose or a test ID.
2. R9 14-section plan requires fair compute/data/tuning; V11 checks stage targeting,
V21 preregistration presence/version/ops. Neither checks actual arm values or hashes
before dispatch. R8 expected outcome contract is not an execution authorization.
3. R11 accepts seven meaningful deltas; interpretation/scope/dependencies/new U can
be progress without independent evidence. EO1 grounds applied result packets, but
there is no mechanical repeated-diagnostic counter.
4. V10 enforces R10 disposition/closure fields, not causal distinction or decision
value. RUN_TEST/NARROW_SCOPE can repeatedly create a legal-looking state.
5. Scheduler explicitly lacks a validator; high/medium rating based on declared
changes does not authorize useful action and can be inflated by U bookkeeping.
6. Failure Memory actually enforces source-bound outcome history, constraints,
ancestor claim/hypothesis lines, seed/commit-independent protocol stop signatures,
retry-fix clearances, independent Assurance. Reuse it. T8 remains trigger prose;
there is no finite mechanical threshold. No supported GPU launch implementation
exists; add one honest, bounded managed entrypoint, do not claim global interception.

Design authority: references/execution-identifiability.md. Additive carriers first,
then schemas/templates, validators, launcher and mock tests. No R-stage/enum change.

## 实现与接口

权威规范先更新，再落 schemas/templates，随后接入 validators 与 mock 测试。
保留八类一等对象、15 个 R 阶段、R10 五值与 R14 四值；没有新增独立 workflow。

- `scripts/execution_gate.py`：PEIG、风险到真实实验臂/比较的追踪、schema 校验、AALG 等价判定、EX1、来源绑定的 Scheduler EIG 核验。
- `scripts/experiment_execute.py`：`issue` / `run` / `diagnose` / `scheduler-check`。正式启动必须经过当前 Scheduler、Failure Memory、PEIG 和 receipt 检查。run 默认 dry-run；测试中的 execute 路径被 subprocess mock 接管。
- `scripts/evidence_outcome.py`：原 check-plan 复用 PEIG；managed 协议的 stop signature 排除 ID/seed/预注册措辞；validate/apply CLI 核验已消费执行记录，新增可选 `--execution-ledger`。
- `scripts/state_check.py`：不改变 S1–S7/V1–V24，增加 EX1，核验扩展结构与不可静默改写的执行/预登记摘要。
- `scripts/release_check.py`：增加 schemas/templates/CT→MRI fixture/容量反例检查；原测试入口保留。
- `scripts/test_execution_gate.py`：70 个新增离线用例。`test_state_check.py` 将原 Scheduler validator 缺口的 skip 改为真实来源核验及变异测试，更新对应文档边界断言。
- `schemas/`：preflight-protocol、diagnostic-protocol、execution-manifest、scheduler 四份可执行 schema；标准库校验其使用的 JSON Schema 子集，无新增第三方依赖。
- `templates/`：新增上述三份协议/manifest 模板；现有 State/Scheduler 模板添加兼容说明与空载体。
- `examples/preflight-identifiability/`：CVPR27 CT→MRI source-free、measurement-only SSL synthetic fixture 与使用说明。
- `references/execution-identifiability.md`：设计、执行权限、有限终止、证据绑定、人审、覆盖边界与迁移的权威规范。
- 同步 SKILL、R7/R8/R9/R9.O/R10/R11 契约、Scheduler/Research State/Evidence Outcome 规范及组件 README。R14 决策权限保持原定义。
- 根 `README.md` 仅更新组件索引的一行：AGENTS.md §8 要求新增重要入口时同步项目地图。没有修改其他 skill。

PEIG 的 PASS/PILOT_ONLY/HOLD 不宣判科学真理。每个已登记风险由真实设计控制、预注册比较判别、显式 R10 scope 限制或 owned UNIDENTIFIABLE 处置。存在的 control ID 不等于有效控制。

默认边界：同一 claim lineage/证据快照中，每类执行权限最多 3 次失败修订；等价诊断最多 2 次；pilot 最多 1 次、2 GPU 小时；receipt 有效期 900 秒。项目参数在 ledger 第一次操作时冻结。正式修订到限，仍允许单独有界 pilot 获取新证据；pilot 自身的失败修订也有上限。资源预算、状态、命令和协议绑定，不能靠新 ID/seed、改 scope 或增加 U/文档重置。

新证据必须是 source-bound observation。生成解释的结果不能作为其独立确认；事后解释标 exploratory，未核实原因仍为 uncertainty/unknown。新增机制需要新的实际判别设计及来源绑定审查，修改机制名或结构距离标签不解锁旧设计。

## 测试矩阵与命令

命令均在本 worktree 执行，没有真实 GPU 训练、联网科研检索或 R0–R14 科研流程启动。

```sh
python3 research-idea-pipeline/scripts/release_check.py
python3 -m unittest discover -s research-idea-pipeline/scripts -p 'test_*.py' -v
git diff --check
```

| 检查 | 最终结果 | 证据 |
|---|---|---|
| 开发前基线 | PASS：551 tests，547 PASS、4 SKIP | baseline-tests.log |
| 全量 unit/integration | PASS：621 tests，618 PASS、0 FAIL、3 SKIP | final-unit-tests.log |
| 完整仓库 release gate | PASS：10/10 checks | final-release-tests.log |
| 原 S/V 规则与表格 | PASS：31 条规则逐字一致、28 行读写表一致 | final-release-tests.log |
| State 模板、CLI、迁移、Outcome/Failure Memory/stop/R10/R11 | PASS，包含于全量测试与 release gate | final-unit-tests.log |
| 新增 PEIG/AALG 用例 | PASS：70/70 | final-unit-tests.log 中 test_execution_gate |
| 包内链接、文档脚本引用、示例 | PASS：17 个脚本引用，旧示例回归及新 fixture mutation | final-release-tests.log |
| 完整临时安装候选副本 | PASS：621 tests，3 SKIP；10/10 checks | installed-copy-tests.log |
| git diff --check | PASS：退出码 0，无输出 | 最终 Git 核验 |
| 额外 skill-creator quick_validate | **FAIL：退出码 1，基线与最终均失败** | skill-validator.log |

通用 skill-creator validator 不支持已有 frontmatter `argument-hint`。未修改该既有入口字段；没有把这项失败计为通过。仓库自己的 frontmatter/入口兼容测试通过。原有 3 个 skip 分别为：阶段写者身份识别、锚点关系状态载体、population telemetry producer；它们不属于本次实现，不宣称已解决。原 Scheduler EIG 缺口的 skip 已替换为实际机械测试。

安装候选副本由完整包复制产生，排除 `.dev`/`__pycache__`。测试比对 scripts/schemas/templates/references 文件字节，并在副本执行完整 release gate。没有更新全局已安装 skill，等待人工审阅。

## 十项反例证明

以下都是被拒绝的负例；测试通过表示拒绝行为正确，并不是坏协议被接受。

| 用户要求 | 主要测试（test_execution_gate.py） | 机械拒绝 |
|---|---|---|
| 1 critical 容量风险无对照 | test_critical_capacity_no_control / test_control_id_does_not_resolve_missing_comparison | HOLD / MISSING_RISK_CONTROL |
| 2 Psi 增加容量未控制 | test_psi_added_capacity_not_controlled / test_omitted_capacity_attack_is_not_ignored | INEFFECTIVE_RISK_CONTROL / UNREGISTERED_CAPACITY_RISK |
| 3 未冻结/不可观测剂量 | test_unfrozen_dose / test_unobservable_dose | UNFROZEN_DOSE / schema error |
| 4 不对称调参预算 | test_asymmetric_tuning | UNFAIR_BUDGET |
| 5 缺预注册/事后改写 | test_missing_preregistration / test_preregistration_rewrite_after_mock_execution_rejected | HOLD / EX1 与 EO1 违反 |
| 6 配置、代码、划分、协议与 receipt 不同 | test_modified_config_after_issue / test_modified_code_or_split_rejected / test_protocol_or_prereg_modified_after_receipt | RECEIPT_CONTENT_MISMATCH |
| 7 伪造许可/过期/重复使用 | test_manual_pass_forgery / test_receipt_expiry / test_mock_dispatch_consumes_receipt | FORGED_RECEIPT / EXPIRED_RECEIPT / UNKNOWN_OR_USED_RECEIPT |
| 8 无新证据重复归因 | test_equal_diagnosis_stops_even_reworded / test_experiment_id_seed_scope_uncertainty_no_reset | STOP_DIAGNOSIS / REDESIGN / T8 |
| 9 post-hoc 包装预注册 | test_posthoc_not_repackaged_preregistered / test_same_result_cannot_independently_confirm / test_renamed_source_cannot_independently_confirm | POST_HOC_IS_EXPLORATORY / SAME_RESULT_NOT_INDEPENDENT_CONFIRMATION |
| 10 stop 后换 ID/seed | test_stop_rule_not_bypassed_by_id_seed_or_reworded_prereg | check-plan FAIL / PEIG HOLD / PIVOT_RECOMMENDED |

额外测试核验命令未经科学执行审查、过期 Scheduler、扩大风险/改假设 ID、追加对照标签、篡改或截断 ledger、审批后 evidence 改变，以及 pilot 卡片反复修订均不能静默解锁。

## 正例、边界与端到端

公平容量对照取得 PASS；真实匹配控制允许额外原始 baseline 存在。prospective pilot、X1/探索和 X2 校准取得 PILOT_ONLY，并受独立预算约束。历史状态仍可读，但没有 protocol 不追认执行 PASS。合法新 source-bound observation、不同实际干预的独立机制协议允许重新诊断。科学争议 UNKNOWN 与不可判别风险返回有限 HOLD，不生成后续任务链。

CT→MRI fixture 全链测试包括：R7 critical capacity attack → R8 protocol/preregistration → PEIG → sealed receipt → mocked GPU dispatch → R9.O proposal → R10/R11 transaction → Assurance → AALG → Scheduler。
正、负、不确定、无效四类模拟分别正确回写。负结果仍为 WEAKENED，优化猜测仍为 unknown；无效协议不产生科学 negative knowledge。full_negative_loop 测试证明第二次等价诊断后，下一次 STOP_DIAGNOSIS 阻止新 receipt；独立观测到来且审查重新绑定后，正常新执行可以进入 PASS，原负结论不被改写。遗漏 R7 对照时 mock dispatch 根本不会被调用。

## 兼容、限制与剩余风险

1. 旧八类 State、S/V/EO gates、R10/R14 枚举和既有 CLI 保留。新载体可为空；严格执行需要实际 adopted outcome policy、真实 R7/design 审查与当前 Scheduler。缺历史日志不虚构回填。
2. 同用户的库调用者必须显式 verify_result_execution；State 的纯内存 EX1 校验不能认证本地密钥。CLI 与 runner 已接入消费记录验证。
3. 覆盖仅为新增 managed entrypoint。原仓库没有 GPU launcher 可直接拦截。直接 shell/SSH/torchrun/sbatch/notebook、外部服务与既有任务不受全局拦截；远程/后台子任务须站点适配器。
4. 内容摘要、JSON carrier 和 reviewer PASS 不证明科学合理性，也不证明任意训练代码遵守配置。容量可比性、剂量测量效度、统计 power、claim scope 与因果解释仍需人审；未列出的依赖、动态导入、并发恶意改文件、代码覆盖 GPU mask 与 detached descendants 不属于进程/文件隔离。
5. Ledger 是本地完整性控制，不是同用户攻击者的安全边界。管理员能改代码/状态/密钥或删整个目录。保留 key/events/head；崩溃造成 event/head 不一致会 fail closed，需人工恢复，不能自动重置次数。
6. 等价检查是保守的结构化设计 fingerprint，不是语义等价证明。真实机制变化应提交不同 identifying design 并接受独立审查；不能靠文字重述获得进展。
7. 额外通用 Skill validator 的既有 FAIL 与三项原 skip 保留为后续事项，未扩大本次开发范围。

## 人工审阅清单

- 审查真实 claim/竞争解释与 R7 attack 是否齐全，capacity 控制是否连接实际 method arm。
- 审查冻结剂量和操作检查能否区分机制；容量、训练自由度、算力与调参是否公平。
- 审查四类 criterion 的科学含义、最小有意义效应、统计方案、scope limit 和 stop 条件。
- 检查真实训练代码如何消费 execution_design，命令/依赖清单是否完整，外部启动器是否需要适配。
- 审查新 evidence 与机制生成来源的独立性，及有限预算是否适合项目。
- 保留 `.dev` 为 KEEP_BRANCH_ONLY；合并前不要将开发日志作为正式包内容。
- 在人工审阅后另行决定是否合并。本次禁止 push/merge/rebase main/PR/release，均未执行。

## Git 与开发文档退出状态

规范/模板提交：a8fdd1b。实现/测试提交：5554ce5。最后的本地交付记录提交包含本报告与原始测试日志；其最终 SHA 以最终回复和 git rev-parse HEAD 为准。

最终分支保留 feat/preflight-identifiability-loop-guard；main ref 必须仍为
139c9e907e437443b640b57271c85236023616e7。最终 git status 应为空。

`.dev` 分类：本报告、baseline-tests.log、final-unit-tests.log、final-release-tests.log、installed-copy-tests.log、skill-validator.log 全部 KEEP_BRANCH_ONLY。正式运行文件不依赖它们；临时中间日志已删除。实现、完整测试、安装候选验证与 Git 核验后停止，不追加科研流程或优化任务。

## 最终合并审查（用户后续授权覆盖原本地交付限制）

用户随后明确要求「最后审查一遍，然后 merge 到 main 并 push」。本节为该审查记录；上面的未合并退出状态是此前交付快照。远端 origin/main 在审查开始时与原基线 139c9e9 一致。

最终审查发现并修复四类边界：

- dry_run 字段改写或非布尔值：结果 CLI 现在同时核验认证账本中的 consume.dry_run=False、实验身份、launch seal，不能将 dry-run 改成正式科学结果。CLI 反例退出 4 且不产生输出状态。
- 子 claim 与竞争假设风险：风险清单覆盖精确目标、全祖先和全部 competitors；子 claim 也继承父 claim 的 R10/AALG 要求。
- 假设或子 claim 换 ID：managed stop signature 只绑定科学设计，目标重叠通过祖先关系单独核验；改名无法释放停止规则，实际不同设计仍可通过既有 planning 检查。旧 legacy signature 不变。
- 审查后改写科学目标：execution_review_digest 现在绑定目标 claim/H 的内容与祖先对象，静默改写 statement 不能沿用原命令审查。

先加入反例复现（5 项失败；随后目标语义绑定反例亦失败），修复后新增模块 77/77 PASS。完整测试 628 项：625 PASS、0 FAIL、3 既有 skip；release_check 10/10 PASS；排除 .dev 的完整安装副本同样通过。此前通用 Skill validator 的既有 frontmatter FAIL 仍未变更，不宣称其通过。

合并时六份 .dev 文件全部 KEEP_BRANCH_ONLY，仅保留在功能分支；main 最终 tree 与 merge diff 不包含这些开发产物。不启动真实 GPU、不创建 PR、不发布 release。
