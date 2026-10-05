# Mode D claim-first 重构：独立对抗性验收报告

**验收对象：** 分支 `research-idea-pipeline-dev`，全部改动未提交，基线 commit `d467b52`。
**验收契约：** [`docs/mode-d-claim-first-spec.md`](mode-d-claim-first-spec.md)（下称「spec」）。
**验收者：** teammate `verifier`（只读；本文件是本次验收唯一写入的文件）。
**验收时间：** 2026-10-06。
**工作目录：** `research-idea-pipeline-dev/`（下文文件行号均相对仓库根）。

**立场声明：** 本报告不采信任何写作者（含 Lead）的自述。每条结论都附 文件:行号 与可重跑命令。
找不到问题的项在 §7 逐条列出「扫了什么、用什么命令扫的」，以便区分「真的没问题」与「没扫」。

> **⚠️ 阅读顺序：** §1—§9 是**第一轮（修复前）**的验收记录，保留原始证据供追溯。
> **第二轮（修复后）的增量复核在 §10**，其中给出 19 条修复的逐条确认、修复引入的新问题、
> § 引用全量重扫与机械校验重跑。**交付判定以 §10.6 为准。**

---

## 0. 结论摘要

| 级别 | 条数 | 是否阻塞交付 |
|---|---|---|
| **MAJOR** | **2** | 是（都属 spec §7 机械校验 / §2 冻结枚举，必须修） |
| MINOR | 10 | 建议本轮修（局部不一致、引用语义错配、作用域未限定） |
| NIT | 7 | 可选 |

**总体结论：需修后交付。** 本轮重构的主体已经落地：spec §6.1—§6.9 的 9 组验收项中 **5 组完整达成、
4 组部分达成**（§6.2 / §6.3 / §6.8 / §6.9）；跨层枚举（`epistemic_status` 五值 / `C0—C5` /
`(O,T,R)` / `S1—S6` / `G1—G5` / 六维 / 六攻击面角色 / `eligible|conditional|not-eligible`）
**未发现自创值、意译值或拼接值**；
spec §7 的 8 项机械校验中 6 项实测通过、2 项失败（均为 MAJOR 的直接后果）。
两项 MAJOR 的修法都很小（一处改节号、一个示例文件的 3 处语法 + 3 个单元格），
修完即可交付。

---

## 1. MAJOR

### MAJOR-1 `mode-d` 整节重写后，仍有两处外部引用指向**已删除的旧节号**

**现象：** mode-d 从 D0—D8 重排为 D0—D9（含 D4.x / D5.x / D9.x 子节），
但两个**外部**引用仍写着旧编号 `D3.3` 与 `D3.2`，这两个节在当前 mode-d 里都不存在。

**文件:行号**

| # | 位置 | 原文（节选） | 旧节号 | 现在应该指向 |
|---|---|---|---|---|
| 1 | `research-idea-pipeline/SKILL.md:912` | 「…roles §4.2 派遣矩阵、mode-d **D3.3 汇总表**）」 | `D3.3 汇总表` | `mode-d` §D5.5 汇总表（或 §D4.5 汇总格式） |
| 2 | `research-idea-pipeline/README.md:202` | 「新颖性判定（C1、**D3.2**、E2.2）」 | `D3.2 文献检索规则（S-Lit 强制）` | `mode-d` §D5.3 `S-Lit` 的文献检索规则 |

**证据（命令）**

```bash
cd research-idea-pipeline
# mode-d 当前只到 D3，没有任何 D3.x 子节：
grep -nE '^#{2,4} ' references/mode-d-narrative-generation.md | sed -n '1,12p'
#   31:## 定位与边界   65:## 输入   82:## 快速索引：D0—D9
#   99:## D0. Evidence Ledger   133:## D1. Claim Graph   181:## D2. Scientific Typing
#   242:## D3. Anchor Eligibility   275:## D4. Narrative Realization   ← D3 无子节
# 另：`git show d467b52:...mode-d-...md | grep -nE '^#{2,4} '` 可见旧版确有
#   ### D3.2 文献检索规则（S-Lit 强制） 与 ### D3.3 汇总表
grep -rnE 'D3\.[23]' --include=*.md .
#   ./README.md:202:...（C1、D3.2、E2.2）...
#   ./SKILL.md:912:...`mode-d` D3.3 汇总表...
```

**影响：** spec §7 第 1 项机械校验「相对链接可达 + §引用可解析」失败；
SKILL §8 A2 行本身是「改规则必须同步汇总表」的维护指令，却指向已删节，
维护者按它去核对会找不到目标。这正是本轮 spec §6.3 要求「交叉引用全部可解析」要防的回归。

**建议修法：** 把 `SKILL.md:912` 的 `` `mode-d` D3.3 汇总表 `` 改为 `` `mode-d` §D5.5 汇总表 ``；
把 `README.md:202` 的 `C1、D3.2、E2.2` 改为 `C1、D5.3、E2.2`（或与 SKILL.md:240 的写法对齐：
`Mode C 的 C1、Mode D 的 S-Lit、Mode E 的 S-Lit/S-Nov`）。

---

### MAJOR-2 规范示例 `example-d-narrative.md` 在**冻结槽位**里写了 spec 未定义的第三种语法与非枚举值

**现象：** 两处偏离 spec §2 的冻结契约，都在「会被照抄的示例」里（SKILL §8 A3 明说
「示例会示范旧写法，且比正文更容易被照抄」）：

**(a) claim graph 证据槽出现第三种语法 `Ci ← Ej, [待验证]`。**
spec §2.2 冻结的语法只有两种：`C2 ← E3, E4`；无证据写 `C2 ← [待补]`。
`[待验证]` 在 spec §2.1 / claim-first-policy §2 硬规则 3 里是**台账条目**的标注，不是证据槽取值；
claim-first-policy §4.2 对「机制未知」明确要求写成 `C_i ← [待补]`。

| 文件:行号 | 原文 |
|---|---|
| `research-idea-pipeline/examples/example-d-narrative.md:80` | `C2 ← E1, [待验证] 现有方法共享假设 X（可逆性只用于采样），在 Y 下结构性失效。` |
| `research-idea-pipeline/examples/example-d-narrative.md:169` | `C0 ← E1, E3, E4    C1 ← E6    C2 ← E1, [待验证]    C3 ← E1, E2, E4 …` |
| `research-idea-pipeline/examples/example-d-narrative.md:209` | 包装前后对照表「包装后」行依据列：`C2 ← E1, [待验证]`、`C3 ← E4`、`C0 ← E3` |

**(b)「当前措辞等级」列写了非枚举值 `待补` / `待验证`。**
evidence-policy §1 冻结五级：`已核实` / `部分核实` / `据本次检索未见` / `待核实` / `待补证明`；
claim-first-policy §2.1 规定 `Planned` → **待核实** + `[待补]`、`Hypothesized` → **待核实** + `[待验证]`。

| 文件:行号 | 原文（当前措辞等级列） |
|---|---|
| `research-idea-pipeline/examples/example-d-narrative.md:434` | 缺失证据清单表 C5 行「当前措辞等级」= `待补` |
| `research-idea-pipeline/examples/example-d-narrative.md:435` | 同行 C2 的假设归因（E10）「当前措辞等级」= `待验证` |
| `research-idea-pipeline/examples/example-d-narrative.md:437` | 同行 E12「当前措辞等级」= `待补` |

**证据（命令）**

```bash
cd research-idea-pipeline
grep -n '← .*待验证' examples/example-d-narrative.md
#   80:C2 ← E1, [待验证] …
#   169:C0 ← E1, E3, E4 … C2 ← E1, [待验证] …
#   209:| 包装后 | … | `C2 ← E1, [待验证]`、… |
sed -n '430,440p' examples/example-d-narrative.md        # 缺失证据清单表：措辞等级列 = 待补 / 待验证
# 对照（同一概念在权威处的写法）：
grep -n 'current_wording_level' references/mode-d-narrative-generation.md templates/state.template.json
#   mode-d:782  "current_wording_level": "待核实"
#   state.template.json:324  "current_wording_level": "待核实"
grep -n '该机制\*\*必须\*\*写成' references/claim-first-policy.md
#   216: 1. 该机制**必须**写成 `C_i ← [待补]`。
```

**影响：** `state.json` 的 `claim_graph.*.evidence` 与 `missing_evidence[].current_wording_level`
是机器可读契约。照抄示例的执行者会写出第三种证据槽 token 和一个不存在的措辞等级，
下游解析（`Ci ← Ej` 计数、措辞等级校验）失效。这也是本轮 SKILL §8 A5 要消灭的跨层漂移。

**建议修法（二选一，需 Lead 裁决并回写 spec）：**
- 保守修法（推荐，不动 spec）：`example-d-narrative.md:80/169/209` 改为 `C2 ← E1`，
  把 `[待验证]` 移到括号说明或紧邻的一行（如 `E10 [待验证] → C2 的机制半支，见缺失证据清单`）；
  `:434/:437` 的 `待补` 与 `:435` 的 `待验证` 改为 `待核实`（`[待补]` / `[待验证]` 留在备注里）。
- 若认为第三种语法有价值，则**先改 spec §2.2 与 claim-first-policy §3**，再同步示例与
  `state.template.json`——不得让示例单方面扩展冻结语法。

---

## 2. MINOR

### MINOR-1 SKILL §8 A 表新增 A5，但「四类」计数未同步（违反 SKILL 自己的 B2 规则）

**现象：** A5 行本轮新增（`git diff` 可见为 `+` 行），但节标题与引言仍写「四类」。
SKILL §8 B2 明写「**标题里的"N 条"必须与该节实际条目数一致**」，`deprecated-terms.txt`
还专设「规则条数（与实际条目数不符的旧说法）」一节 —— 这是本仓库自己定义过的漂移类。

**文件:行号：** `research-idea-pipeline/SKILL.md:907`（`### A. 四类高危位置（历史上反复漏）`）、
`research-idea-pipeline/SKILL.md:905`（`而是下面 A 组这四类"看起来不像规则"的位置。`）；
表格实际为 `A1`—`A5` 五行（`:911`—`:915`）。

**证据（命令）**

```bash
cd research-idea-pipeline
grep -nE '^\| A[0-9]' SKILL.md            # A1..A5 → 5 行
git show d467b52:research-idea-pipeline/SKILL.md | grep -nE '^\| A[0-9]'   # 旧版只有 A1..A4
git diff -- SKILL.md | grep -nE '^\+.*A5 \|'                               # A5 为本轮新增
```

**建议修法：** `SKILL.md:905`、`:907` 的「四类」改为「五类」。

---

### MINOR-2 `Transfer Legitimacy Argument` / `L1—L3` 被归到了错误的文件节

**现象：** venue-standards 两处把跨域「迁移合法性论证 + L1/L2/L3 分级」的出处写成
`claim-first-policy.md §4`，但 claim-first-policy §4 是「Central Proposition：全局承重墙」，
既无 `Transfer Legitimacy Argument` 这个小节名，也不定义 `L1/L2/L3`
（该定义在 `narrative-patterns.md:229—255`，claim-first-policy §4.2 只是**指过去**）。

**文件:行号**

| 位置 | 原文 |
|---|---|
| `research-idea-pipeline/references/venue-standards.md:306` | `迁移合法性分级见 [claim-first-policy.md](claim-first-policy.md) §4 的 `Transfer Legitimacy Argument`（`L1` / `L2` / `L3`）。` |
| `research-idea-pipeline/references/venue-standards.md:555` | EC-10 行「依据」列 = `ICML-7 / [claim-first-policy.md](claim-first-policy.md) §4`（「最低证据契约」列提到 `L1`/`L2`/`L3`） |

**证据（命令）**

```bash
cd research-idea-pipeline
grep -nE '^#{2,4} ' references/claim-first-policy.md | sed -n '5,10p'
#   171:## 4. Central Proposition：全局承重墙
#   180:### 4.1 七类论文的命题形态（逐字）
#   195:### 4.2 旧「机制」规则的降级（关键）      ← §4 下只有这两节
grep -rn 'Transfer Legitimacy Argument' references/ | sed 's/^/  /'
#   narrative-patterns.md:229 ## 4. 跨域 Transfer Legitimacy Argument   ← 定义所在
#   narrative-patterns.md:243 **`L1 / L2 / L3` 举证等级（逐字，不得改写）：**
#   claim-first-policy.md:344 | §4 Transfer Legitimacy Argument | … | §4 |   ← §7.3 表把方向写反了源头
```

**根因：** `claim-first-policy.md:344` 的 §7.3 表左列是「narrative-patterns 的 §4」、
右列是「被引节 = claim-first-policy §4」；venue-standards 读这张表时取了左列的节名 + 左侧文件名。
**建议修法：** venue-standards 两处改指 `narrative-patterns.md §4`；
同时给 `claim-first-policy.md:344` 该行加半句说明（如「定义在 narrative-patterns §4，
本节只登记跨域子规则」），消除歧义。

---

### MINOR-3 `mode-d` §D9.5 的 `state.json` 片段与 `templates/state.template.json` D 段不一致

**现象：** 同一份 state 片段，两处字段名/结构不同；其中 `Soundness margin` 一处违反 mode-d 自己的 D8 硬约束。

| 项 | `mode-d` §D9.5 | `state.template.json` |
|---|---|---|
| 逐维胜出理由 | `"why": "逐维理由：……"`（`references/mode-d-narrative-generation.md:779`） | `"why_per_dimension": {}`（`templates/state.template.json:319`） |
| `Soundness margin` 双读数 | 无该字段，只有 `"Soundness_margin": 3`（`mode-d:776`） | `"Soundness_margin_readings": {"experimental": null, "theory": null}`（`state.template.json:300`） |

**证据（命令）**

```bash
cd research-idea-pipeline
grep -n '"why"\|why_per_dimension\|Soundness_margin"\|Soundness_margin_readings' \
  references/mode-d-narrative-generation.md templates/state.template.json
sed -n '616,619p' references/mode-d-narrative-generation.md
#   - **`Soundness margin` 的两个读数并存，不得平均。** 实验侧与理论侧各自成立或各自缺失。
```

**影响：** spec §6.3 明确要求「`state.json` 片段示例与新字段一致」。
mode-d D9.5 是执行者手中的规范片段，缺 `Soundness_margin_readings` 会诱导只记一个数，
与 D8:618「两个读数并存，不得平均」和 `state.template.json:306` 的
`"Soundness_margin": "两个读数并存，不得平均"` 互相矛盾。

**建议修法：** `mode-d:776` 的 ranking 项补 `"Soundness_margin_readings": {"experimental": 3, "theory": 2}`；
`mode-d:779` 的 `"why"` 改为 `"why_per_dimension"`（与模板一致）。二者取一为准，另一处跟随。

---

### MINOR-4 三处「交叉质询与中位数规则完全一致」未限定作用域，与 Mode D「无中位数」冲突

**现象：** 这三句是「Team / 默认子代理方式不改变标准」的说明，把「中位数规则」当成全局；
但 Mode D 已退役中位数（scoring-policy §5 明写「Mode D 不使用本节任何一条」）。

**文件:行号：** `research-idea-pipeline/SKILL.md:569`、`research-idea-pipeline/references/roles.md:268`、
`research-idea-pipeline/README.md:127`。

**证据（命令）**

```bash
cd research-idea-pipeline
grep -rn '中位数规则完全一致' --include=*.md .
#   ./README.md:127 / ./references/roles.md:268 / ./SKILL.md:569
sed -n '139,143p' references/scoring-policy.md
#   ## 5. 逐维中位数与一票否决（**Mode E 仍适用**；Mode D 已改用 §3 门禁 + §4 六维）
#   > **Mode D 不使用本节任何一条**：不做归一化后的中位数、不做一票否决、不走「带条件的推荐」出口。
```

**建议修法：** 三处改为「交叉质询与**聚合规则**完全一致（Mode D = 门禁 `G1—G5` + 六维；
Mode E = 归一化后中位数 + 一票否决）」。

---

### MINOR-5 两处「四个会议审稿人必须三段」未限定为 B/C/E（spec §8 缺陷 3 只修了 §1.2）

**现象：** spec §8 缺陷 3 要求「SKILL §1.2 的『四会议审稿人两角度 + 会议特性』限定作用域」，
§1.2 已修（`SKILL.md:286—288`），但该要求的**两处副本**仍是全局句式。

**文件:行号**

| 位置 | 原文 |
|---|---|
| `research-idea-pipeline/SKILL.md:757`—`759` | `- [ ] **四个会议审稿人的评价都含「理论角度 + 应用角度 + 会议特性判定」三段**（见 roles.md §1.0）；R-MICCAI 不适用时已标 "不适用"` |
| `research-idea-pipeline/README.md:230`—`235` | `**审稿人评价的两角度 + 会议特性：** 四个会议审稿人（R-CVPR / R-ICML / R-NeurIPS / R-MICCAI）的每一次评价都必须给出 …` |

**证据（命令）**

```bash
cd research-idea-pipeline
grep -rn '四个会议审稿人' --include=*.md . | sed 's/^/  /'
#   SKILL.md:283（§1.2，已限定）/ SKILL.md:757（§6 清单，未限定）
#   README.md:230（未限定）/ roles.md:14、358 / venue-standards.md:77（反向声明）/ mode-b:158 / mode-e:102、149
sed -n '286,288p' SKILL.md    # §1.2 的作用域限定（对照用）
```

**影响：** Mode D 执行者读到 §6 执行自检清单时，可能认为必须产出四份三段式会议审稿意见 ——
与 D5「会议审稿人不作为主审」「六人全部派遣」直接冲突（spec §8 缺陷 3 要防的正是这个）。
**建议修法：** 两处句首加「（仅 Mode B / C / E；Mode D 的 D6 只出校准表，不派子代理）」。

---

### MINOR-6 `README.md` 的 Mode D 速查行仍是旧描述

**现象：** 「五个 Mode」表里 D 行还是叙事优先的旧表述，与 SKILL.md:50 的新描述不一致，
也没有任何 claim-first / 证据台账 / 门禁信息。

**文件:行号：** `research-idea-pipeline/README.md:141`
（`| **D** | `narrative-generation` | **基于 idea + 方案**生成多种顶会风格叙事逻辑，并拉起子代理评审，筛出最佳叙事 | 是 | … |`）

**证据（命令）**

```bash
cd research-idea-pipeline
sed -n '50p' SKILL.md    # 新表述：先建证据台账与 claim graph，再生成 2—4 套真正不同的叙事，经攻击面审核与硬门禁后筛出最佳叙事
sed -n '141p' README.md  # 旧表述
git diff -- README.md | grep -c '^+.*claim-first'   # README 的 Mode D 正文已重写，但本表行未同步
```

**建议修法：** 与 `SKILL.md:50` 对齐。

---

### MINOR-7 spec §3 的文件地图漏登记 `README.md` 与 `references/writing-policy.md`（两者实际被改）

**现象：** spec §3「文件地图与写作用域（互不重叠）」没有这两行，但它们都在本轮改动里
（`git status` 显示 ` M`）。discipline 1 说「只改自己作用域内的文件」，
所以这两个文件既没有所有者，也没有被纳入「谁负责同步」的清单 —— 后果是 README
只被部分同步（见 MINOR-1/5/6 与 MAJOR-1 的第 2 条）。

**证据（命令）**

```bash
cd research-idea-pipeline-dev
git status --short                    # 15 个 M + docs/ + claim-first-policy.md
git diff --stat -- research-idea-pipeline/README.md research-idea-pipeline/references/writing-policy.md
#   README.md | 60 +++++++++++++++++++++++++++---------------  (38+/22-)
#   writing-policy.md | 2 +-   （§6 分工表 1 行）
```

**建议修法：** spec §3 补两行（`README.md`、`references/writing-policy.md` → 所有者 Lead，
依赖「全部」），并在 spec §10 记一行；同时把 README 里剩余的 Mode D 表述一次扫完
（`grep -nE 'Mode D|套路|D[0-9]\.' README.md`）。

---

### MINOR-8 spec 内部冲突：§5 接口要求同步 `project-layout §2.4`，§9 P1-4 却说「本轮不做」

**现象：** `project-layout.md §2.4` 本轮已被改成 claim-first 结构（新增证据台账 / claim graph /
`S1—S6` 骨架），这符合 spec §5 接口行「仅当文件结构变化时同步 §2.4 叙事文档结构」，
但与 §9 P1-4「`project-layout.md` §2.4 叙事文档内部结构按六槽位更新 —— 本轮登记，不做」矛盾。
按 spec §3 纪律 4「发现 spec 有错：改动 spec 必须经 Lead」，本轮应同时改 spec 并在 §10 记录，
但 `docs/mode-d-claim-first-spec.md §10` 只有「初版」一行。

**文件:行号：** `docs/mode-d-claim-first-spec.md:300`（§5 接口行）、`:450`（§9 第 4 条）、
`:454—458`（§10 变更记录，仅 1 行）；`research-idea-pipeline/references/project-layout.md:203—261`（实际已改）。

**证据（命令）**

```bash
cd research-idea-pipeline-dev
sed -n '300p;450p;456,458p' docs/mode-d-claim-first-spec.md
git diff --unified=0 -- research-idea-pipeline/references/project-layout.md | grep -E '^[-+]#{3,4} '
#   -#### N2.2 五段式叙事主线（详写套 ≥300 字；摘要套只给摘要级主线）
#   +#### S1 Context / S2 Tension / S3 Central Proposition（可证伪）/ … / S6 Consequence & Boundary
```

**附注：** spec §2.4 与 §2.8 正文含「2026-10-06 追加」条款，同样未进 §10。
**建议修法：** 二者取一：① 删掉 §9 P1-4（因为本轮已做）；或 ② 在 §9 P1-4 标注「本轮已提前完成」。
无论哪种，都在 §10 补记「§2.4 单值约束追加」「§2.8 读数归属追加」「project-layout §2.4 已同步」
「README / writing-policy 纳入同步范围」。

---

### MINOR-9 `claim-first-policy` §7.3 声明的引用点，在 `narrative-patterns` 里不存在

**现象：** claim-first-policy §7 自述是「引用契约」，其 §7.3 表声称 narrative-patterns §5
引用本文件 §2；实测 narrative-patterns §5 只引 evidence-policy §3，全文未出现 claim-first-policy。
而 spec §6.2 的验收项是「禁用表述 §、包装纪律 § 保留并**指向 claim-first-policy**」——
§6 包装纪律满足（`narrative-patterns.md:297`），§5 禁用表述不满足。

**文件:行号：** `research-idea-pipeline/references/claim-first-policy.md:346`（声明行）、
`research-idea-pipeline/references/narrative-patterns.md:265—276`（§5 全文）。

**证据（命令）**

```bash
cd research-idea-pipeline
sed -n '338,348p' references/claim-first-policy.md      # §7.3 表：| §5 禁用表述 | … | §2 |
sed -n '265,277p' references/narrative-patterns.md     # §5 只出现 evidence-policy.md
grep -n 'claim-first-policy' references/narrative-patterns.md   # 0 命中
```

**建议修法：** 在 `narrative-patterns.md` §5 末句补一条指向
`[claim-first-policy.md](claim-first-policy.md) §2`（替代表述必须落回台账条目）；
或在 claim-first-policy §7.3 把该行的「被引节」改为 `evidence-policy §3`。

---

### MINOR-10 `L1/L2/L3` 在同一文件内有两个互不相干的含义，且没有消歧注

**现象：** `L1/L2/L3` 既表示**检索尽职调查等级**，又表示**跨域迁移合法性举证等级**。
两个含义在 `venue-standards.md` 与 `SKILL.md` 内部并存，且相邻不远。
`templates/INDEX.md:117` 对「表内行号 T1 vs 触发条件 T1—T7」有消歧注，`L1/L2/L3` 没有。

**文件:行号**

| 含义 | 位置 |
|---|---|
| 迁移举证等级（spec §2.10） | `references/narrative-patterns.md:243—249`、`references/venue-standards.md:307`、`:555`、`SKILL.md:767` |
| 检索尽职调查等级 | `SKILL.md:240`（T4）、`SKILL.md:741`（§6 清单）、`references/venue-standards.md:390`（§7.4「L3 穷尽检索」）、`references/literature-policy.md` |

**证据（命令）**

```bash
cd research-idea-pipeline
sed -n '243,249p' references/narrative-patterns.md   # L1/L2/L3 = structural hypothesis / invariance / theorem
sed -n '390p' references/venue-standards.md           # L3 穷尽检索（同文件另一含义）
sed -n '240p' SKILL.md; sed -n '767p' SKILL.md        # 同文件两种含义
grep -rniE '检索.*等级.*无关|与.*检索.*L[123].*无关|迁移.*等级.*无关' --include=*.md .
#   无输出 → 全仓没有针对该符号冲突的消歧注
```

**建议修法：** 在 `narrative-patterns.md §4` 的 L1/L2/L3 表前加一句
「本节的 `L1/L2/L3` 是**迁移举证等级**，与 literature-policy 的**检索尽职调查等级** L1/L2/L3 无关」，
并在 `SKILL.md` 首次同时出现处（§6 清单）沿用同一限定词。

---

## 3. NIT

| # | 现象 | 文件:行号 | 证据（命令） | 建议修法 |
|---|---|---|---|---|
| 1 | §7 设计依据第 5 条仍以「多套路并行生成 + 多子代理打分，才能找到该 idea 的最优叙事位置」论证 Mode D，未按 SKILL §8 A1 自检「这条还在支持当前规则吗」更新，与紧邻的第 12—14 条（claim-first / 删 11 维 / 攻击面）读起来像两份并列依据 | `research-idea-pipeline/SKILL.md:830` | `sed -n '828,831p;870,874p' SKILL.md` | 在该条末尾加「（本轮已改为：先定 claim 与门禁，再在通过门禁的候选间做六维比较）」 |
| 2 | 「套路」与「preset」混用；`narrative-patterns.md:3-4` 已声明统一称 preset | `research-idea-pipeline/SKILL.md:172`（「叙事资格（先于选套路）」）、`SKILL.md:33`、`README.md:4`、`examples/example-b-to-c-d-e.md:3` | `grep -rn '套路' --include=*.md .` | 现行规则句统一为 `preset`；「叙事套路」只保留在触发关键词（`SKILL.md:21`） |
| 3 | writing-policy §8 第 6 条是「机器可读契约只准写」白名单，但未收录本轮新冻结项（`epistemic_status` 五值、`(O,T,R)`、`G1—G5`、六维、`eligible/conditional/not-eligible`），而 claim-first-policy 与 mode-d 都以它为依据 | `research-idea-pipeline/references/writing-policy.md:218—247`（§8 第 6 条表）；引用方 `references/claim-first-policy.md:247`、`references/mode-d-narrative-generation.md:186` | `sed -n '236,247p' references/writing-policy.md` | 表中补 4 行，或在 spec §9 登记为 P1 |
| 4 | 示例小节标题用「或」写双轴取值，易被抄成双值字段 | `research-idea-pipeline/references/narrative-patterns.md:215` | `sed -n '215p' references/narrative-patterns.md` | 标题只留一个单值（如 `(O=Method, T=infeasibility, R=prove)`），另一取值在正文说明 |
| 5 | §6 清单里的「§2.1 封闭枚举」未写文件名（同文件 §1.4 规则 3 写了 `project-layout.md §2.1`） | `research-idea-pipeline/SKILL.md:743` | `sed -n '743p;372,373p' SKILL.md` | 补文件名 |
| 6 | mode-d 要求逐候选登记 `(O,T,R)`（D4.2(3)、D4.5 表），`state.template.json` 的 `presets[]` 无对应槽位（`typing` 只有按 idea 一组）；示例为此额外加了一段解释 | `references/mode-d-narrative-generation.md:330`、`:395—398`；`templates/state.template.json:205—216` | `sed -n '205,216p' templates/state.template.json`；`sed -n '47,49p' examples/example-d-narrative.md` | 在 `presets[]` 加 `typing: {O,T,R}`（A4 类「规则有、载体无」） |
| 7 | 本轮替换掉的旧表述未追加进 `deprecated-terms.txt`（「五段式」「≥4 套候选」「六子代理（D）」），机械闸门因此拦不住回归 | `research-idea-pipeline/references/deprecated-terms.txt`（全文 58 行，末节止于「至少被 4 个子代理审核」） | `tail -6 references/deprecated-terms.txt`；`grep -rn '五段式' --include=*.md .`（0 命中） | 追加三条正则（若担心 Mode E 误伤可加 `--` 上下文限定） |

---

## 4. spec §6.x 达成情况总表

| 验收组 | 结论 | 关键证据（文件:行号） | 缺口 |
|---|---|---|---|
| **§6.1** `claim-first-policy.md`（新） | **达成**（7/7） | 公式 `claim-first-policy.md:33`；`B→K` 逐字 `:52—54`；五值表 `:83—89`；映射表 `:108—115`；`C0—C5` `:139—148`；七类形态 `:182—190`；承重墙 `:177`；降级 `:195—218`；`(O,T,R)` `:229—241`；单值约束 `:258—260`；三值结论 `:275—279`；prior≠decision `:290—291`；每节「引用本节的 Mode」`:71/:130/:166/:220/:264/:307`；§7 引用清单 `:311—369` | — |
| **§6.2** `narrative-patterns.md`（重写） | **部分达成**（7/8） | 记法说明 `:6—9`；十套表 10/10 含 MICCAI `:47—56`；`(O,T,R)+anchor` 选择表 `:65—138`；多 preset 命中 `:9/:33/:36`；六槽位 `:146—153`；四类填法 `:177—225`；五步升级 + 第 3 步改名 + L1/L2/L3 `:229—255`；自检清单 `:308—324` | 「禁用表述 § 指向 claim-first-policy」只满足包装纪律（§6），§5 未指 → MINOR-9 |
| **§6.3** `mode-d-narrative-generation.md`（重写） | **部分达成**（8/9） | D0—D9 表与 spec §4 逐字一致 `:86—95`；定位段 `:6—8`；预期贡献声明 `:19—21`；11 维/极性/稳健度在 D 全无（见 §5 扫描）；六攻击面 + S-Devil/S-Lit/S-Nov/S-Repro 分工与打分边界 `:409—450`；D9 六项含缺失证据清单与最小实验 `:644—655`；交叉引用自解析 `:34/:285/:297/:413/:527/:554/:624/:684` | D9.5 片段与 `state.template.json` 不一致 → MINOR-3 |
| **§6.4** `scoring-policy.md`（重写） | **达成**（5/5） | 两层表 `:6—10`；§2 限定 Mode E `:51—54`；非独立样本 `:22—30`、`:98—100`；旧 §4/§5 标注 `:139—146`；冲突以本文件为准 `:17` | — |
| **§6.5** `roles.md`（更新） | **达成**（4/4） | §1B 六角色 `:89—155`；R-CVPR 等保留给 B/C/E + D6 校准 `:14—18`；§4.2 矩阵 `:279—296`；§6 攻击面量表 `:438—480`；§7 字数表 D5 行 `:493—494`；骨架 5A/5B/5C `:358/:388/:413` | — |
| **§6.6** `evidence-policy.md`（更新） | **达成**（2/2） | §3 映射 `:40—70`；§2 编号 `1.`—`8.` 无重号 `:18—38` | — |
| **§6.7** `venue-standards.md`（更新） | **达成**（6/6，外部可核性见 §8 限制） | ICML 四维拆分 §2.1 `:143—152`；NeurIPS 按 contribution type §3.1 `:180—186`；ICLR §10.3 `:596—624`；CVPR §1 `:110—135`；MICCAI §4.1 `:223—232`；顶刊 §9.1—9.3 `:416—477`；`clinical significance ≠ methodological innovation` §9.4 `:479—491`；顺序硬规则 §10.0 `:497—535` 含「不得 venue 直接选 preset」`:524`；未核实项标【待核实】`:434—441`、`:163—169`、`:256—262`；来源 URL 清单 `:36—56` | `Transfer Legitimacy` 出处写错 → MINOR-2 |
| **§6.8** `SKILL.md`（Lead） | **部分达成**（8/9） | §0.1 D 行 `:172`；§1.2 作用域 `:286—288`；§1.5 承重墙 + 降级 `:421—432`；§2 资源索引含 claim-first `:497`；§3 D 行 `:530`；§4 D 速查 `:624—642`；§5 衔接图未变 `:665—681`；§6 D 项 `:763—769`、`:773—774`；§7 新增 12/13/14 `:870—895`；§8 A5 登记 `:915` | §8 A 计数「四类」未同步 A5 → MINOR-1；§8 A2 内旧节号 → MAJOR-1 |
| **§6.9** `templates/` 与 `examples/` | **部分达成**（2/3） | `state.template.json` D 段含 8 个新字段且无 venue `scores` 键 `:144—333`，JSON 合法；`example-d-narrative.md` 含 claim graph `:75—84`、六槽位 `:150—176`、门禁表 `:364—384`、六维排序 `:388—426`、缺失证据清单 `:430—444`；examples + templates linter 硬违规 0 | 冻结枚举/语法误用 → MAJOR-2 |

---

## 5. 机械校验（spec §7）实测结果

全部命令在 `research-idea-pipeline/` 下执行，与 spec §7 的清单一一对应。

| # | 校验项 | spec 期望 | 实测 | 结论 |
|---|---|---|---|---|
| 1 | 相对链接可达（去代码围栏） | 0 断链 | 355 条链接，**0 断链**（`/tmp/verify/links.py`，脚本见下） | ✅ |
| 1b | § 引用可解析 | 全部可解析 | 682 处 `§` 逐处解析目标文件 + 节号，其中 **2 处不可解析**；另 `§n`/`§N`/`§X` 为占位符、`§2 文档索引` 类指向路线 `INDEX.md` 章节，已逐个人工确认 | ❌ MAJOR-1 |
| 2 | 废弃词扫描 | exit 1（0 命中） | `grep -rnE "$PAT" --include=*.md .` → **无输出，exit 1** | ✅ |
| 3 | 反引号紧跟 `docs/`（缺 routeX 前缀） | 0 命中（排除模板） | spec §7 第 3 条命令 → **无输出，exit 1** | ✅ |
| 4 | JSON 合法 | 两个文件可 load | `state.template.json` OK；`docs/refs/index.json` OK；`refs_index.py --check` exit 0（`[ok] 索引与 0 个 PDF 一致`） | ✅ |
| 5 | 离线测试 | 全过 | `python3 -m unittest discover -s scripts -p "test_*.py"` → **Ran 56 tests … OK**，exit 0 | ✅ |
| 6 | 受控中文（examples + templates 默认档） | 硬违规 0 | `--selftest` OK；`for f in examples/*.md templates/*.md; do … --disable synonym-rotation "$f"; done` → **9/9 rc=0** | ✅ |
| 7 | 旧机制残留（Mode D 语境 0） | 区分合法保留 | 见下表，**Mode D 现行规则 0 命中**；SKILL §7/§8 与 Mode E 命中属 spec §7 明示的合法保留 | ✅ |
| 8 | 标题增删检查 | 无整节被吞 | 15 个改动文件的 `git diff -U0 \| grep -E '^[-+]## '` 逐条核对，删除项全部对应 spec §4/§6 的预期替换 | ✅ |

**第 1 项链接检查脚本（可重跑）：**

```python
# /tmp/verify/links.py —— 去代码围栏后提取 [..](path)，排除 http/#，逐条 os.path.exists
# 输出：links checked: 355  broken: 0
```

**第 7 项逐条扫描结果（关键：区分现行规则 vs 合法保留）：**

| 旧机制 | 全仓命中 | 判定 |
|---|---|---|
| `五段式` | **0** | ✅ |
| `≥4 套` / `至少 4 套` | **0** | ✅ |
| `11 维` | `SKILL.md:880`（§7 第 13 条「为什么删掉」）、`SKILL.md:915`（§8 A5 举例） | ✅ 合法（spec §7 明示的历史说明） |
| `11 个维度` | 0 | ✅ |
| `新颖性稳健度 = 6 − 反驳分` | `scoring-policy.md:62/:71`（§2，已限定 Mode E 且写明「Mode D 不使用」）；`mode-e-proposal-review.md:176/:231/:240`；`SKILL.md:771/:775`（§6 的 Mode E 项）、`:851/:880/:882`（§7 第 10/13 条）；`README.md:158`（已标 Mode E）；`examples/example-b-to-c-d-e.md:172`、`example-followup-review.md:53`（Mode E 语境） | ✅ 合法（Mode E 现行 + 设计依据） |
| `四个会议审稿人`（作为 D 的派遣角色） | `roles.md:279—282` 矩阵 D 列 = `—（D6 仅校准）`；`mode-d:412`、`SKILL.md:530`、`venue-standards.md:75—79` 均为**否定式声明** | ✅ 合法；仅 `SKILL.md:757`、`README.md:230` 未限定（→ MINOR-5） |
| `中位数`（作为 D 的聚合） | `scoring-policy.md §5` 全部标注 Mode E；`mode-d:513`「不做中位数」；`roles.md:322`「不做逐维中位数」；`scoring-policy §4 规则 5` 仅允许「状态标记」用途且不得进排序 | ✅ 合法；仅三处通用句未限定（→ MINOR-4） |

---

## 6. 对抗性找碴：构造的 6 个场景与结果

| # | 假设执行者会怎么错 | 结果 | 证据 |
|---|---|---|---|
| 1 | 某节说「门禁 fail 不参与排序」，另一节仍按中位数选最佳 | **未发现反例**（该规则四处一致） | `mode-d:580—581`、`:624`、`:630`；`scoring-policy:92—95`、`:135`；`state.template.json:307`；`examples/example-d-narrative.md:390` |
| 2 | 一处说 D 派 6 个攻击面审稿人，另一处说派 4 个会议审稿人 | **发现**：矩阵/正文均已改，但两处通用句未限定作用域 | `roles.md:279—304`（正确）vs `SKILL.md:757`、`README.md:230`（未限定）→ MINOR-5 |
| 3 | `state.template.json` 字段与 `mode-d` §D9.5 片段不一致 | **发现 2 处**：`why` / `why_per_dimension`；缺 `Soundness_margin_readings` | `mode-d:776`、`:779` vs `state.template.json:300`、`:319` → MINOR-3 |
| 4 | `project-layout §2.4` / `templates/INDEX.md §2.2` / `examples/example-project-layout.md` 三处叙事追踪表形状不一致 | **未发现反例**（路线 INDEX 三处均为 8 列同形） | `project-layout.md:433—436`、`templates/INDEX.md:96—98`、`examples/example-project-layout.md:144—146` 列名逐字相同；`project-layout §2.4:213—216` 的 7 列「摘要表」是叙事文档内的另一张表，非同一张 |
| 5 | mode-d 整节重排后，别处仍引旧节号 | **发现 2 处**：`D3.3`、`D3.2` | `SKILL.md:912`、`README.md:202` → MAJOR-1 |
| 6 | 示例把 spec 未定义的 token 带进 state.json | **发现**：`Ci ← Ej, [待验证]` 与措辞等级列 `待补`/`待验证` | `examples/example-d-narrative.md:80/169/209/434/435/437` → MAJOR-2 |

---

## 7. 扫过但未发现问题的项（负面结论清单，含命令）

以下每一项都实际扫过（不是「看起来没问题」）：

1. **`epistemic_status` 五值**：全仓出现 20/28/21/25/15 次（Hypothesized/Observed/Planned/Supported/Unknown），
   无第六值、无中文值、无大小写变体。
   命令：`grep -rnoE '\b(Observed|Supported|Hypothesized|Planned|Unknown)\b' --include=*.md --include=*.json . | awk -F: '{print $NF}' | sort | uniq -c`。
2. **`C0—C5`**：`C0 ←`…`C5 ←` 出现 18/9/15/11/11/9 次；无 `C6`/`C7` 作为 claim 节点
   （命中的 `C6/C7` 全部是 Mode C 的步骤号或 frontmatter 说明）。
   命令：`grep -rnoE 'C[0-9] *(←\|<-)' …`；`grep -rnoE '\bC[6-9]\b' …`。
3. **`(O,T,R)` 三轴全部枚举**：20 个取值全部命中规范拼写（`Resource-System`、`build-benchmark`、
   `hidden-assumption`、`evaluation-mismatch`、`unexplained-phenomenon` 等），
   下划线/驼峰/空格变体 **0 命中**；拼接值只出现在两处**禁止**语句里。
   命令：`grep -rniE 'resource[_ ]?system|build[_ ]benchmark|hidden[_ ]assumption|…' --include=*.md .`；
   `grep -rnE 'Method\+|Evaluation\+' --include=*.md .`。
4. **`S1—S6` 槽位名**：`S1 Context`/`S2 Tension`/`S3 Central Proposition`/`S4 Resolution`/
   `S5 Evidence Contract`/`S6 Consequence & Boundary` 在 mode-d、narrative-patterns、
   state.template.json（下划线形式）、example-d 中逐字一致，无第七槽、无改名。
5. **`G1—G5` 门禁名**：`G1 Claim grounding`×8、`G2 Prior-work distinction`×6、
   `G3 Identification`×5、`G4 Factual integrity`×5、`G5 Venue scope`×12，无改名/意译。
6. **六维拼写**：`Soundness margin`（含空格）、`Explanatory depth`、`Narrative compression`
   首字母大写形式 26/12/12 次；`Soundness Margin`/`Narrative Compression` 等变体 0 次；
   JSON 键 `Soundness_margin` 与 `Narrative_compression` 与模板一致。
7. **六个攻击面角色**：`R-Novelty` 27、`R-Causal` 30、`R-Experimental` 25、`R-Theory` 25、
   `R-Generalization` 25、`R-Utility` 26；无 `R-Causality`/`R-Experiment` 之类变体；
   `R-TMI`/`R-JMLR`/`R-NMI`/`R-ICLR` 各 1 次，全部出现在「本轮**不**新增该角色」的否定句里。
8. **`eligible` / `conditional` / `not-eligible`**：全仓（含反引号与裸写）29/18/11 次，
   无 `not eligible`（空格）、无 `ineligible`、无 `not_eligible`、无 `eligible_conditional`。
   命令：python 正则 `(eligible|conditional|not-eligible|not eligible|ineligible|not_eligible)`
   加词边界扫全部 `*.md` / `*.json`（见 `/tmp/verify/` 同名脚本）。
9. **`L1/L2/L3` 迁移等级**：`narrative-patterns.md:247—249` 与 spec §2.10 逐字一致
   （structural hypothesis + falsification experiments / formal invariance + sufficient conditions
   / theorem + proof + necessity-tightness）；含义冲突见 MINOR-10（这是消歧问题，不是取值漂移）。
10. **Mode D 的 `scores` 键**：`templates/state.template.json` D 段无 `scores`/`review_output`
    任何按会议命名的键（命中的 `review_output` 全在 Mode E 段与 E 文档）；
    命令：`grep -rn '"scores"\|review_output' --include=*.json --include=*.md .`。
11. **`≥4 套候选` → `2—4 套`**：skill 目录内 18 处全部统一为「2—4 套真正不同的 claim hierarchy」，
    包含 README、SKILL、project-layout、两个 examples、roles §7 计数行；
    `grep -rn '≥4 套' --include=*.md .` = **0 命中**。
12. **`scripts/` 未被动**（spec §1.3 非目标）：`git status --short research-idea-pipeline/scripts` 为空。
13. **有序列表编号**（对照上一轮修掉的「§2 两条 `7.`」缺陷）：按节重扫
    SKILL / claim-first-policy / mode-d / narrative-patterns / scoring-policy / roles /
    evidence-policy / venue-standards / project-layout / example-d / templates.INDEX / README，
    **无重号**（报告里的 4 处「非 1 起」是同一节内的多个独立列表，人工确认合法）。
    命令：`/tmp/verify/numcheck2.py`。
14. **计数型标题抽查**：SKILL §1「五条」= 1.1—1.5 五节 ✅；SKILL §1.4「八条硬性规则」= 8 条 ✅；
    project-layout §1.1「六条硬性规则」= 6 条 ✅；claim-first-policy §4.1「七类」= 7 行 ✅；
    narrative-patterns §1「十套」= 10 行 ✅；roles §5「三种骨架」= 5A/5B/5C ✅；
    venue-standards §2.1「四个维度」/§2.2「三种来源」✅；README「五个 Mode」= 5 行 ✅。
    唯一不符的是 SKILL §8 A「四类」vs 5 行（→ MINOR-1）。
15. **跨文件引用语义抽查**（除已列问题外全部对得上）：
    `writing-policy §8 第 6 条` ✅（`:218—247` 第 6 条存在）；
    `mode-b §B5.2` ✅（`mode-b-idea-discovery.md:165`）；
    `mode-c §C3 第 4 节` ✅（`mode-c-proposal-generation.md:91`）；
    `mode-d §D5.3` ✅（`:492`）；`roles §1B/§4.2/§5/§6/§7` ✅；`scoring-policy §1—§6` ✅。
16. **`S-Feas` 是否属自创角色**：不是。`roles.md:294` 的派遣矩阵在**改动前**就已是
    `| S-Feas | — | ● | ● | ○ | ● |`（D 列为 ○），本轮 mode-d/SKILL/example 只是与既有角色库对齐；
    spec §2.9 未列 S-Feas 属于 spec 描述不全，不是产物违规。证据：
    `git show d467b52:research-idea-pipeline/references/roles.md | sed -n '/### 4.2 派遣矩阵/,/Mode A/p'`。

---

## 8. 未覆盖项与验收限制

1. **venue-standards 的 2026 官方 URL 与原文引句未做外部复核。** 本验收环境
   `web_fetch https://icml.cc/...` 与 `web_fetch https://neurips.cc/...` 均返回
   `URL hostname resolves to a non-public IP address`（代理环境，与 `SKILL.md:259—267`
   描述的 fake-IP 现象一致），`web_search` 返回 401。因此我**只能**核对：
   条目是否带 URL、是否区分【原文】/【概括】/【待核实】、未经核实的项是否已标【待核实】
   （三处已标：`:434—441` TMI 四准则、`:163—169` ICML 断言纪律、`:256—262` MICCAI 受试者划分）。
   **引句与 URL 的真实性无法在本环境证明，也不能证伪。** 这一项需要 Lead 或有网环境复核。
2. **Mode E 的语义正确性不在本轮范围**（spec §1.3 非目标）。我只核对了 Mode E 相关内容的
   **交叉引用与作用域标注**（见 §5 第 7 项），未评审其规则本身。
3. **`scripts/` 未评审**（spec §1.3「本轮无脚本改动」，`git status` 证实未改）；
   `unittest` 与 `refs_index --check` 仅作为回归闸门执行。
4. **`docs/refs/README.md`、`literature-policy.md`、`mode-a/b/c/e*.md`、`writing-policy.md` 正文**
   未逐节评审（不在本轮改动范围）；只扫了它们**指向本轮改动文件的 § 引用**。
5. 本报告**未修改任何被审文件**；未 `git commit` / `git push`。
   唯一写入：`docs/verify-mode-d-claim-first.md`。

---

## 9. 修复清单（按优先级，给 Lead）

| 优先级 | 动作 | 文件:行号 |
|---|---|---|
| 1 | 改 `D3.3` → `§D5.5`；改 `D3.2` → `D5.3` | `SKILL.md:912`、`README.md:202` |
| 2 | 示例的 `C2 ← E1, [待验证]` 改为 `C2 ← E1` + 旁注；措辞等级列 `待补`/`待验证` → `待核实` | `examples/example-d-narrative.md:80/169/209/434/435/437` |
| 3 | 「四类」→「五类」 | `SKILL.md:905`、`:907` |
| 4 | 迁移合法性出处改指 `narrative-patterns.md §4` | `venue-standards.md:306`、`:555` |
| 5 | D9.5 与 state 模板字段对齐 | `mode-d:776`、`:779` |
| 6 | 三处 + 两处通用句加作用域限定 | `SKILL.md:569`/`:757`、`roles.md:268`、`README.md:127`/`:230` |
| 7 | README Mode D 行同步 | `README.md:141` |
| 8 | spec 补文件地图两行 + §9 P1-4 与 §10 记录 | `docs/mode-d-claim-first-spec.md:300/450/456` |
| 9 | narrative-patterns §5 补指向 claim-first-policy §2 | `narrative-patterns.md:275—276` |
| 10 | L1/L2/L3 消歧注 | `narrative-patterns.md:243` 前 |
| 11 | NIT 1—7（可选） | 见 §3 表 |

**一句话总体结论：** 主体达成，`docs/mode-d-claim-first-spec.md` §6.x 中 **5 组完整达成、
4 组部分达成（§6.2 / §6.3 / §6.8 / §6.9）**；**2 项 MAJOR（旧节号 2 处、示例冻结枚举误用 6 处）
修完即可交付**；其余 17 项为 MINOR/NIT，可同轮顺手清掉。

> **⏩ 第二轮更新（Lead 修复后增量复核）：见 §10。**
> 本报告 §1—§9 记录的是**修复前**的第一轮验收（保留原始证据，便于追溯）。
> §10 给出 19 条修复的逐条确认、修复引入的新问题、§ 引用全量重扫与机械校验重跑结果。
> **当前交付判定以 §10 为准：仍需修（1 项声明未落实 + 2 项新引入小问题），全部是行级修复。**

---

## 10. 增量复核（第二轮：修复验证）

**复核范围：** 只验证 Lead 的修复本身（是否改到、是否引入新矛盾、是否漏改同类），
不重跑第一轮的全量内容评审。所有命令在 `research-idea-pipeline/` 下执行。

### 10.1 19 条修复逐条确认

| # | Lead 声明 | 现值（文件:行号） | 判定 |
|---|---|---|---|
| 1 | MAJOR-1a：SKILL A2 → `§D5.5` | `SKILL.md:916`：``…`roles` §4.2 派遣矩阵、`mode-d` §D5.5 汇总表）`` | ✅ 达成 |
| 2 | MAJOR-1b：README T4 `D3.2` → `D5.3` | `README.md:203`：`\| T4 \| 新颖性判定（C1、D5.3、E2.2） \| **L3 穷尽**…`（行号由 202 移到 203） | ✅ 达成 |
| 3 | MAJOR-2a：示例证据槽 | `examples/example-d-narrative.md:80`：`C2 ← E1 …（机制归因是 Hypothesized，标 [待验证]，见缺失证据清单）`；`:169`：`… C2 ← E1 …`；`:209`：`` `C2 ← E1`、`C3 ← E4`、`C0 ← E3` `` | ✅ 达成（`[待验证]` 已移出证据槽，成为括号注） |
| 4 | MAJOR-2b：措辞等级列 | `:434` `待核实`、`:435` `待核实`、`:437` `待核实`；`:436` `待补证明 · 待核实`（原本正确，保留） | ✅ 达成（全列落回 evidence-policy §1 五级） |
| 5 | MINOR-1：四类 → 五类 | `SKILL.md:909`「A 组这**五类**"看起来不像规则"的位置」；`:911`「### A. **五类**高危位置（历史上反复漏）」；表 `A1`—`A5` 五行 | ✅ 达成 |
| 6 | MINOR-2：venue-standards 两处 + claim-first §7.3 两行 | `venue-standards.md:306` ✅ 已改指 `[narrative-patterns.md](narrative-patterns.md) §4 的 Transfer Legitimacy Argument`；**`venue-standards.md:555`（EC-10 行）仍写 `ICML-7 / [claim-first-policy.md](claim-first-policy.md) §4`** ❌；`claim-first-policy.md:344` ✅ 已补「定义在 narrative-patterns.md §4」、`:345` ✅ | ⚠️ **部分达成（1/2）→ 见 §10.2 N-1** |
| 7 | MINOR-3：D9.5 补字段 | `mode-d:776` ✅ 已补 `"Soundness_margin_readings": {"experimental": 3, "theory": 2}`；`mode-d:779` ✅ `why` → `why_per_dimension`；**但同一行 `"Soundness_margin"` 的取值变成了字符串**（见 §10.2 N-2） | ⚠️ **部分达成 + 引入新类型不一致** |
| 8 | MINOR-4：三处改「聚合规则」 | `roles.md:268`、`SKILL.md:569—571`、`README.md:127—129` 均为「…交叉质询与**聚合规则**完全一致（Mode D = 硬门禁 `G1—G5` + 六维排序；Mode E = 归一化后逐维中位数 + 一票否决）」；`grep -rn '中位数规则完全一致'` → **0 命中** | ✅ 达成，且与 scoring-policy §3/§4/§5 逐条对得上（§10.2 已核） |
| 9 | MINOR-5：两处作用域 | `SKILL.md:758—759`：「（**仅 Mode B / C / E**；**Mode D 的 D6 只出汇总校准表，不派会议审稿人**）」；`README.md:231`：「**审稿人评价的两角度 + 会议特性（仅 Mode B / C / E）：**」 | ✅ 达成 |
| 10 | MINOR-6：README Mode D 行 | `README.md:142` 与 `SKILL.md:50` **逐字一致**（先建证据台账与 claim graph…经攻击面审核与硬门禁后筛出最佳叙事） | ✅ 达成 |
| 11 | MINOR-7：spec §3 补两行 | spec §3 表新增 `research-idea-pipeline/README.md`（UPDATE 同步速查/树/Mode D 段）与 `references/writing-policy.md`（UPDATE §6 分工表 1 行），所有者均 **Lead** | ✅ 达成 |
| 12 | MINOR-8：spec §9 P1-4 + §10 | `docs/mode-d-claim-first-spec.md:452` P1-4 划删并写「**本轮已提前完成**」；§10 现共 8 行（初版 + 7 行新增，含 §2.4/§2.8/§3/§7/P1-4/本轮修复） | ✅ 达成 |
| 13 | MINOR-9：narrative-patterns §5 指向 | `narrative-patterns.md` §5 末段新增「**替代表述必须落回证据台账条目**（[claim-first-policy.md](claim-first-policy.md) §2）」；`claim-first-policy.md:345` 反向标注「（`narrative-patterns` §5 末句已指向本节 §2）」 | ✅ 达成（引用与被引两侧闭合） |
| 14 | MINOR-10：L1/L2/L3 消歧 | `narrative-patterns.md` §4 L1/L2/L3 表前新增「⚠️ **消歧：** 本节的 `L1`/`L2`/`L3` 是**迁移举证等级**，与 literature-policy 的**检索尽职调查等级**无关 —— 两者同形不同义，引用时必须带限定词」 | ✅ 达成 |
| 15 | NIT-1：SKILL §7 第 5 条 | `SKILL.md:832—834` 新增「（**本轮已改为：** 先定 claim 与证据，再过硬门禁 `G1—G5`，最后只在**通过门禁的候选间**做六维比较 —— 见本节第 12—14 条…）」；§7 条目编号连续 `1.`—`14.`，第 12/13/14 条确为 claim-first / 删 11 维 / 攻击面 | ✅ 达成 |
| 16 | NIT-2：D 行「选套路」 | `SKILL.md:172`：「D \| **叙事资格（先于选 preset）：**…」 | ✅ 达成（其余「套路」残留见 §10.3 N-5） |
| 17 | NIT-3：writing-policy §8 第 6 条白名单 | `writing-policy.md` §8 第 6 条表新增 5 行：`epistemic_status` 五值 / `(O, T, R)` 三轴单值 / `anchor_eligibility` 三值 / 门禁·槽位·排序维度 / 攻击面审稿人名 | ✅ 达成（逐字与 spec §2 一致） |
| 18 | NIT-5：SKILL §6 补文件名 | `SKILL.md:800`：「只用 [project-layout.md](references/project-layout.md) §2.1 封闭枚举」 | ✅ 达成 |
| 19 | NIT-6 / NIT-7：state `presets[].typing` + deprecated 三条 | `templates/state.template.json` `presets[]` 新增 `"typing": { "O": "Method", "T": "hidden-assumption", "R": "design-algorithm" }` ✅；`references/deprecated-terms.txt` 追加 `五段式` / `≥4 套候选` / `六子代理` 三条 ✅ | ✅ 达成 |

**小计：17 条完整达成，2 条部分达成（第 6、7 条）。**

### 10.2 修复引入的新问题

#### N-1（**MAJOR**，按 Lead 自己设定的判定标准「有一条没改到就是 MAJOR」）`venue-standards.md:555` 的迁移合法性出处未改

- **现象：** Lead 声明「venue-standards.md **两处**改指 narrative-patterns.md §4」，实测只改了 `:306`；
  `:555` 的 EC-10 行依据列仍写 `claim-first-policy.md §4`（该节不含 `Transfer Legitimacy Argument`
  定义，也不定义 `L1/L2/L3`）。
- **现值（命令）：**

  ```bash
  cd research-idea-pipeline
  grep -n 'narrative-patterns.md) §4' references/venue-standards.md     # 只有 :306 一处
  sed -n '555p' references/venue-standards.md
  # | EC-10 | `O=Method` 且 `R=reformulate`（跨域迁移） | … ③ 合法性等级 `L1`/`L2`/`L3` 与声称的贡献等级**匹配** | ICML-7 / [claim-first-policy.md](claim-first-policy.md) §4 |
  sed -n '195,198p' references/claim-first-policy.md   # §4 下只有 4.1 七类形态 / 4.2 机制降级
  ```
- **影响面（诚实分级）：** 就影响而言这是第一轮 **MINOR-2 的残留**——claim-first-policy §4.2 确实
  写着「跨域类必须给出迁移合法性论证（见 narrative-patterns.md §4）」，读者能顺链找到定义，
  所以不构成断链，只构成「同一份文件里两处同类引用一半改一半没改」的不一致。
- **建议修法（一行）：** `:555` 依据列改为 `ICML-7 / [narrative-patterns.md](narrative-patterns.md) §4（迁移合法性分级）`，
  或保留 claim-first-policy §4 但补「（定义见 narrative-patterns §4）」。

#### N-2（MINOR）`mode-d` §D9.5 的 `Soundness_margin` 槽从数字变成了字符串

- **现象：** MINOR-3 修复时把模板里 `reasons.Soundness_margin` 的说明句
  「两个读数并存，不得平均」误填进了**维度取值槽**，导致该槽与其他五个维度的类型不一致。
- **文件:行号 / 证据（命令）：**

  ```bash
  cd research-idea-pipeline
  sed -n '776p' references/mode-d-narrative-generation.md
  # {"idea_id": "I1", …, "Significance": 4, "Originality": 4,
  #  "Soundness_margin": "两个读数并存，不得平均",              ← 字符串（应为数字）
  #  "Soundness_margin_readings": {"experimental": 3, "theory": 2}, …}
  grep -n '"Soundness_margin"\|why_per_dimension' templates/state.template.json
  # 300:  "Soundness_margin": null,                     ← 数字槽（占位）
  # 301:  "Soundness_margin_readings": {…}
  # 307:  "reasons": {"Significance": …, "Soundness_margin": "两个读数并存，不得平均"}   ← 说明句的位置
  ```
  结构化逐字段比对（`/tmp/verify` 脚本：解析 §D9.5 围栏 JSON vs `state.template.json` 的 `D` 段，
  递归比较键集与类型）结果：**共享键无缺失、无多余；唯一语义类型不一致是 `Soundness_margin`**。
- **建议修法：** 把 `mode-d:776` 的 `"Soundness_margin"` 改成 `3`（或 `null`），
  把「两个读数并存，不得平均」移到同项的 `"reasons"` 里（模板已经是这个写法）。

#### N-3（NIT）`deprecated-terms.txt` 新注释的「全仓」与实际扫描范围不符

- **现象：** 新增注释写「以下三条必须保持**全仓** 0 命中」，但文档化的闸门只扫
  `research-idea-pipeline/`（SKILL §8 D4 / spec §7 都是 `cd research-idea-pipeline; grep … .`）。
  仓库根 `docs/` 不在范围内，而 `docs/mode-d-claim-first-spec.md:163` 恰好含「五段式」。
- **证据（命令）：**

  ```bash
  cd research-idea-pipeline && tail -6 references/deprecated-terms.txt
  # # 以下三条必须保持全仓 0 命中（含 §7 设计依据等追溯历史的段落）。
  cd .. && grep -rn '五段式' docs/
  #   docs/mode-d-claim-first-spec.md:163:### 2.6 六槽位（取代五段式）
  ```
- **闸门本身是绿的**（`research-idea-pipeline/` 内 0 命中，见 §10.4），所以这是注释措辞问题。
- **建议修法：** 把「全仓」改成「`research-idea-pipeline/` 内（spec 与验收记录在扫描范围外，
  可保留原字面量）」。

### 10.3 同类漏改扫描（第一轮未列或未处置的项）

| # | 现象 | 文件:行号 | 证据（命令） | 级别 |
|---|---|---|---|---|
| N-4 | 第一轮 NIT-4 **未处置**：小节标题用「或」写双轴取值，仍可能被抄成双值字段 | `references/narrative-patterns.md:215` | `grep -n 'O=Theory 或 Method' references/narrative-patterns.md` | NIT |
| N-5 | 「套路」在 4 处现行文本残留（D 行已改，但这 4 处未动）；`narrative-patterns.md:3—4` 已声明统一称 preset | `SKILL.md:5`（frontmatter description）、`SKILL.md:33`、`README.md:4`、`examples/example-b-to-c-d-e.md:3` | `grep -rn '套路' --include=*.md .`（另 `SKILL.md:21` 是触发关键词、`SKILL.md:832` 已加历史说明、`venue-standards.md:524`/`narrative-patterns.md:3,4,67` 是禁止/说明语境，均合规） | NIT |
| N-6 | 第一轮 NIT-5 的同类：跨文件 § 引用未写文件名（本文件内不存在该节号，只能靠上下文推断） | `writing-policy.md:230`（`§2.1` → project-layout §2.1）、`templates/INDEX.md:54`（`§3.2` → project-layout §3.2）、`SKILL.md:136`（`§3 frontmatter` → project-layout §3）、`project-layout.md:123`/`:142`（`§0.1`/`§0.2` → SKILL §0.1/§0.2） | `grep -rn '见 §[0-9]' --include=*.md .` + 逐条比对目标文件标题 | NIT（均**可解析**，只是缺文件名） |

**同类漏改中未发现 MAJOR/MINOR 级问题：** 旧节号（`D3.x`）残留为 0；`L1/L2/L3` 全部用法都带
限定词（`L3 穷尽` / `尽职调查等级` / `Transfer Legitimacy = L2` / `迁移等级`）；未限定作用域的
「四个会议审稿人」只剩 Mode 专属文件与 Mode E 语境。

### 10.4 § 引用全量重扫（独立复现）

| 检查 | 方法 | 结果 |
|---|---|---|
| 全仓 `§` 引用 | 自写解析器：去代码围栏 → 提取每个 `§token` → 用**本行 + 前两行**的链接/文件名（含 `mode-d`、`roles` 等短名）推断目标文件 → 与目标文件标题集合比对 | 682 处引用；严格解析下 93 个候选未命中 → **逐个人工裁定后 0 处真断链**（裁定分类见下） |
| `§D/§B/§C/§E` 前缀引用（含跨文件） | 对全仓每个 `§[DBCE]<n>` 检查对应 mode 文件是否存在该节号 | **44 处，0 断链** ✅（与 Lead 的独立结果一致） |
| 第一轮 MAJOR-1 的两处 | `grep -rnE 'D3\.[23]' --include=*.md research-idea-pipeline/` | **exit 1（0 命中）** ✅ 已修净 |

**93 个候选的裁定分类（全部为解析器误判，非真断链）：**
① 同行多引用导致目标文件选错（如 `SKILL.md:861` 的 `§4` 是 SKILL 自身 §4，
解析器却取了同行的 `mode-d`）——`SKILL:861/863/876`、`venue-standards:489/490/565/566/585—590/592`、
`roles:105/448`、`narrative-patterns:74`、`literature-policy:51—53`；
② 指向**路线 `INDEX.md` 章节**（`§2 文档索引`/`§3 已证实`/`§4 已证伪`/`§5 TODO`/`§6 Bugs`/`§7 Warnings`/`§9 变更日志`），
目标在 `templates/INDEX.md`——`mode-a:161—166`、`mode-b:226—232`、`mode-c:152—159`、`mode-d:650—657`、
`mode-e:277—283`、`example-d-narrative:441—444`、`example-b-to-c-d-e:125—126`（`templates/INDEX.md` 这些节号全部存在）；
③ 指向 **Mode C 提案**的 `§C1`/`§C3`/`§C4` 与「新增 §10」类文档内引用——`example-d-narrative:59/60`、
`writing-policy:54`、`mode-e:251`、`example-followup-review:37/39`（`mode-c` 的 C1—C5 与 0—13 节均存在）；
④ 指向**仓库根 spec**（`docs/mode-d-claim-first-spec.md` §2.1/§4/§9/§10）——文件在 skill 目录外，属设计内；
⑤ 占位符与历史指代——`§n`/`§N`/`§X`、`claim-first-policy:361` 的 spec §10、
`literature-policy:14` 明写「**原规范** §1.3.1」（指旧版本，非当前节号）；
⑥ 指向 **SKILL** 的跨文件引用——`README:98` §1.5、`project-layout:123/142` §0.1/§0.2、
`claim-first-policy:316—321` §0.1/§1.5/§8、`templates/INDEX.root.md:29` §6（目标均存在）。

### 10.5 机械校验重跑（修复后）

| # | 校验项 | 命令 | 结果 |
|---|---|---|---|
| 1 | 废弃词扫描（含新增 3 条） | spec §7 原命令（`PAT` 取非注释行） | **exit 1，0 命中** ✅；`五段式` / `≥4 套候选` / `六子代理` 单独 grep 也各 0 命中 |
| 2 | 反引号紧跟 `docs/` | spec §7 原命令（排除模板与命令行自身） | **exit 1，0 命中** ✅ |
| 3 | 相对链接（去围栏） | 自写脚本 `/tmp/verify/links.py` | **359 条链接，0 断链** ✅（第一轮 355 条，新增来自本轮修订） |
| 4 | JSON 合法 | `json.load(state.template.json)`、`json.load(docs/refs/index.json)` | 两者 OK ✅ |
| 5 | 索引一致性 | `python3 scripts/refs_index.py --check` | exit 0 ✅ |
| 6 | 离线测试 | `python3 -m unittest discover -s scripts -p "test_*.py"` | **Ran 56 tests … OK**，exit 0 ✅ |
| 7 | 受控中文 | `--selftest`；examples + templates 默认档（9 个文件） | selftest OK；**9/9 rc=0，硬违规 0** ✅ |
| 8 | 训练/发布面未动 | `git status --short research-idea-pipeline/scripts` | 空 ✅ |

### 10.6 第二轮总体结论

**仍需修（1 项声明未落实 + 2 项新引入的小问题），修完即可交付。**

| 待修 | 级别 | 位置 | 修法 |
|---|---|---|---|
| N-1 | **MAJOR**（按 Lead 判定标准；实质为引用一致性） | `venue-standards.md:555` | 一行：依据列改指 `narrative-patterns.md §4` |
| N-2 | MINOR | `mode-d:776` | 一行：`Soundness_margin` 取数字，说明句移入 `reasons` |
| N-3 | NIT | `deprecated-terms.txt` 末段注释 | 半行：「全仓」→「`research-idea-pipeline/` 内」 |
| N-4/N-5/N-6 | NIT（可选） | 见 §10.3 | 见 §10.3 |

**除上述 3+3 项外，19 条修复中的 17 条完整达成、2 条部分达成，未引入其他矛盾：**
MINOR-4 的三句改写与 scoring-policy §3（门禁不打分不聚合）/§4（六维）/§5（仅 Mode E 的中位数与否决）
逐条一致；MINOR-3 的 state 片段与 `templates/state.template.json` 逐字段比对后只余 N-2 一处类型问题；
`deprecated-terms.txt` 新增三条在扫描范围内确实 0 命中。第一轮的 2 项 MAJOR 已修净。
