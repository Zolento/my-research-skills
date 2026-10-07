# R12 Narrative Realization Architecture Note

## 审计基线

分支：`research-idea-pipeline/narrative-realization-dev`。
本地 main / origin/main：`fd2b63e`（v2.1.1）。SSH fetch 失败，HTTPS DNS 失败，
远端 API 也不可达；不能声称已验证远端最新 main。独立 worktree 保留 main 原样。
基线 release_check：PASS；456 tests，4 skips。

已审阅 SKILL、phase-r12、claim-first、narrative-patterns、scoring、research-state-policy、
Assurance reference、state 模板、example-d、validator、golden path 与 release tests。
这是技能包维护，不是运行一个科研项目；不创建项目锚点或运行 R3/R7。

## 当前职责与不变量

| 阶段 | 职责 |
|---|---|
| D0 | 复核 Evidence Ledger；区分 Observed/Supported 与未验证证据 |
| D1 | 展开已有 Claim Graph，逐条 Ci ← Ej；claim 创建属于 R3 |
| D2 | Scientific Typing (O,T,R) 与贡献类型 |
| D3 | Anchor Eligibility；not-eligible 不得进入叙事 |
| D4 | 选择 preset，生成 2–4 套不同 hierarchy，填 S1–S6，跨域 stress test |
| D5 | 六攻击面审核、S-Lit、S-Devil、交叉质询 |
| D6 | contribution type → evidence contract → venue calibration |
| D7 | G1 grounding / G2 prior delta / G3 identification / G4 integrity / G5 venue |
| D8 | 仅通过 G1–G5 的 hierarchy 作原有六维比较，不合成 overall score |
| D9 | 推荐、runner-up、缺证据、最小实验；正文落文档，描述符落 narrative_view |

Evidence Ledger、Claim Graph、Anchor Eligibility 依次进入 D4。R12 文中某些旧
`state.json.claim_graph/slots/gates` 写法与 D9.5 的载体约束冲突；以 D9.5 和
research-state-policy 为准：它们是文档内容，不增加 state 顶层字段。
State 的 S1–S7/V1–V24 管对象/引用/升级/闭环，不验证自由文本的语义等价。
G1–G5 是证据门禁，任何 fail 不可被分数救回；新 RE 门禁是额外前置检查，
不新增 G6，不替代 Assurance，也不把 LLM judge 升级为科学证据。

## 最小变更方案

旧：D0 → D1 → D2 → D3 → D4 → D5 → D6 → D7 → D8 → D9。
新：D0 → D1 → D2 → D3 → D4a → freeze → D4b → D4c → D4d → D5…D9。

- **Scientific Narrative Search (D4a)** 保留原 D4 的 hierarchy/preset/六槽位搜索。
  只能选择、组织 State 已有的 claim，不允许创造、收窄或强化 State 真值。
  每套 hierarchy 独立冻结；不同 hierarchy 不是 rhetorical variants。
- **Rhetorical Realization Search (D4b)** 每套冻结后，仅搜索 evidence framing 和
  contribution stance。先登记算子和固定预算，再生成最多四套表达，不看分数递归爬山。
- **Semantic-Equivalence Audit (D4c)** 比较 14 项冻结语义、state fingerprint、
  evidence mapping 与完整正文。MVP 使用来源绑定的受限 renderer；正文未按受限算子
  产生，即 FAIL。不能只比 generator 自报的 metadata，也不声称证明任意散文等价。
- **Blind Claim-Recovery Probe (D4d)** 独立 judge 只收到正文与六个恢复问题；
  adjudicator 才读取 ground truth。四项 PASS/PARTIAL/FAIL，unsupported 声称单列。
- **Sensitivity diagnostic** 固定同一冻结故事的 neutral/evidence/contribution/conservative
  扰动，固定多 judge 面板，记录最差恢复、range/variance/disagreement。缺数据不可判稳健。

载体：snapshot/variants/probes/audit JSON 为叙事文档的配套 artifacts，放到
`routes/<R>/narrative-realization/<doc-id>/`；State 仍只保存既有四键描述符。
不迁移 state schema，不改 D0–D3/D5–D9 的科学职责。

冲突处置：旧 R12 可新增 uncertainty；**冻结后的 D4b–D4d 不可新增或改 uncertainty**。
新缺口先记 narrative_gap，中止该 snapshot，交 R1/R8/R10，再重新冻结；不静默自动修补。
原 pre/post 文档有表述交叉，保留原划分，仅在 post 的每套故事内启用 realization。

## 验证计划与边界

每步运行相关检查并记录于下表。发布仍以 release_check 最后一行为准。
支持来源绑定、固定表达模板与顺序搜索；任意 paraphrase、自动科学事实抽取、真实模型
效果均不在此 MVP 证明范围。来源 completeness 仍需 D4a 科学审计，hash 不是可信签名。

| 阶段 | 验证记录 |
|---|---|
| architecture | 基线 release_check PASS（456 tests / 4 skips） |
| operator registry | JSON 解析、7 算子 / 4 固定 profile 白名单检查 PASS；不改原有行为 |
| equivalence policy | 明确 RE1–RE5、14 项冻结、原句恢复和完整多模型面板；原 release_check PASS |
| realization generation | 2 个只读/四 profile 测试 PASS；source fixture 通过 State gate；release_check PASS（458 tests / 4 skips） |
| blind claim recovery | 8 个新增测试 PASS；无 truth 泄漏、三值恢复、overstatement/overall score 拒绝、双模型完整面板；release_check PASS（464 tests / 4 skips） |
| sensitivity audit | 14 个新增测试 PASS；配对 range/variance/disagreement、类别判断漂移、缺数据 INCOMPLETE、最差恢复排序；release_check PASS（470 tests / 4 skips） |
| adversarial cases | 33 个新增测试 PASS，含全部八 case、14 字段变异、正文/来源/预算/CLI/release 注入；release_check PASS（489 tests / 4 skips） |
