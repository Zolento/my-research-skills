# R 架构 Wave 3（角色层）：独立对抗性验收报告

**验收对象：** 分支 `research-idea-pipeline-dev`，基线 `bc175f5`，本次快照 `6315643`（工作树干净）。
**契约：** [`docs/r-architecture-wave3-spec.md`](r-architecture-wave3-spec.md)（下称「spec」）。
**验收者：** teammate `verifier`（只读；本文件是本次验收唯一写入的文件）。
**验收时间：** 2026-10-06 ｜ **工作目录：** `research-idea-pipeline-dev/`（文件行号相对仓库根）。

**立场声明：** 不采信任何自述。所有结论附 文件:行号 与可重跑命令；
「扫过但没问题」的项在 §5 逐条列出，以区分「真的没问题」与「没扫」。
**先给一条最重要的结构性事实：** Wave 3 提交 `6315643` 只改了 **5 个文件**
（`git diff --name-only bc175f5 6315643`：SKILL.md / phase-r12 / phase-r7 / roles.md / scoring-policy），
其中 `roles.md` 只有 **2 个 hunk（+27/−4）** —— **§1B、§4.2、§5、§6、§7 一行未动**。
spec §7 文件地图要求的 `venue-standards.md` **改动 0 行**。这直接决定了下面的结论。

---

## 0. 结论摘要

| 级别 | 条数 | 说明 |
|---|---|---|
| **MAJOR** | **6** | 派遣矩阵未后移、§1B/§5 未改（仍 1—5 分制）、SKILL 与 venue-standards 未同步、R12-pre 落盘互斥、R 阶段文件仍在派 venue 角色 |
| MINOR | 7 | S-Integrity 未接入四处、锚点分工、R7 表把完整性算作 R7 面、缺校准表、示例残留、§6 清单缺项、缺 Kill Condition 反例 |
| NIT | 3 | `R3—R65` 笔误、README venue 引用（已知未做）、SKILL 一句被替换得不通顺 |

**总体结论：需修后交付。** Wave 3 的**新增内容质量好且自洽**：phase-r7 的 R7 五元组节、
R13 Integrity Gate 节、scoring-policy §0、SKILL §2/§3/§4/§7、phase-r12 的 pre/post 节
五处字面一致（五元组字符串逐字相同），`S-Integrity` 的边界（vs `S-Repro` / `R-Experimental`）
与「只在 R13 生效」写得清楚，机械面全绿，三方 14 阶段仍逐字一致。
但**角色层的「后移」只做了一半**：`roles.md` 的**权威派遣矩阵、攻击面角色段、输出骨架**
三处全部保持 Wave 2 状态（仍按 1—5 分、仍派会议审稿人），`venue-standards.md` 未改，
SKILL 内部还留下两处相反的 venue 作用域表述 —— 执行者按 `roles.md §4.2` / `§5B` 走，
得到的行为与 SKILL §3 / spec §6 相反。

---

## 1. MAJOR

### M-1 `roles.md §4.2` 派遣矩阵**完全未后移**：会议审稿人仍被派到 R3—R6 / R8 / R7·R10·R13

**现象：** 矩阵列头与行都是 Wave 2 状态，四个会议审稿人在 `B3 头脑风暴` / `C 方案生成` /
`E 方案复核` 三列都是 **●**（派遣），只有 `D 叙事审核` 列写 `—（D6 仅校准）`。
矩阵里**没有 `S-Integrity` 行**。

**文件:行号 / 证据（命令）：**

```bash
cd research-idea-pipeline
sed -n '300,305p' references/roles.md
#   | 角色 | B·头脑风暴(B3) | B·idea 审核(B5) | C·方案生成 | D·叙事审核 | E·方案复核 |
#   | R-CVPR    | ● | ● | ● | —（D6 仅校准） | ● |
#   | R-ICML    | ● | ● | ● | —（D6 仅校准） | ● |
#   | R-NeurIPS | ● | ● | ● | —（D6 仅校准） | ● |
#   | R-MICCAI  | ● | ● | ● | —（D6 仅校准） | ● |
grep -n 'S-Integrity' references/roles.md | sed -n '1,5p'
#   只有 :16 / :263 / :272 —— §4.2 矩阵无此行
git diff bc175f5 6315643 -- references/roles.md | grep -c '^@@'      # → 2（未触碰 §4.2）
```

**与哪些规则冲突（三处）：**
- `roles.md:14`：「`R-CVPR` / `R-ICML` / `R-NeurIPS` / `R-MICCAI` **不再出现在任何 R 阶段的派遣表里**」；
- `SKILL.md:602—605`：R3—R6 行「**不派 venue 角色**」、R8 行「**venue 角色不派**」、
  R7/R10/R13 行「**venue 角色不参与科学发现**」；
- spec §6 第 1 行 / §8 验收 1。

矩阵下方唯一相关的说明（`:327`）只排除了 **D5/D6**：「会议审稿人…不作为 D5 主审派遣，
只在 D6 venue calibration 中以校准表出现」—— `B3`/`C`/`E` 三列的 ● 没有被排除。
**建议修法：** ①列头改为 R 阶段（`R3—R6`（B3/B5） / `R8`（C） / `R12`（D） / `R7·R10·R13`（E））；
②四个会议审稿人行改为 `—（仅 R12/R13 校准表，不派子代理）`，B5 列若保留需写明
「concept 级快筛（spec §6 消歧）」；③补 `S-Integrity` 行（R13 生效，其他列 —）。

---

### M-2 `roles.md §1B` 攻击面审稿人段**未改**：仍以 `1—5` 分为主输出，没有五元组

**现象：** spec §3 的唯一硬规则是「每个 assurance 算子**必须**输出五元组，**而不是一个分数**」。
`§1B` 现在的口径与它相反，且没有任何五元组字段。

**文件:行号 / 证据（命令）：**

```bash
sed -n '97,113p' references/roles.md
#   ## 1B. 攻击面审稿人（R12 主审）                      ← 仍是 Wave 1 的标题
#   **派遣：** R12 的 D5 一次性派遣下列六人…                ← 内部节号 D5
#   **打分边界（重要）：** 每个攻击面审稿人**只在自己的主责维度上给一个 `1—5`**
#   …5. 输出格式见 §5 骨架 B，字数下限见 §7。               ← 骨架 B 也只输出分数（见 M-3）
sed -n '97,166p' references/roles.md | grep -cE '五元组|Kill Condition|Attack, Target'
#   → 0
```

**同一文件内的自相矛盾：** `roles.md:26` 写「**不适用于** §1B 的攻击面审稿人（他们按 §5 骨架 B
**输出五元组**）」—— 而 §1B 与骨架 B 都不输出五元组。
**还缺三条 spec 要求的硬规则：** `Kill Condition` 必须可判定（spec §3 规则 1）、
`Discriminating Test` → `X`/`TBD`（规则 2）、**assurance 不得改 `claims[].status`**（规则 3）。
**建议修法：** §1B header 改为「（`R7` 的八个攻击面，Wave 3 起）」；`打分边界` 改为
「**主输出是五元组**（`(Attack, Target Claim, Alternative, Discriminating Test, Kill Condition)`）；
1—5 分只作次要记录」；补三条硬规则（可直接复用 `phase-r7:399—415` 的措辞）。

---

### M-3 `roles.md §5` 三种骨架**未改**：骨架 2 仍输出 `1—5`，骨架 3 未含 `S-Integrity`

**现象：** 骨架选择表与骨架 2 模板都是 Wave 2 状态；`S-Integrity`（本波唯一新角色）
**不属于任何骨架**；骨架 1 的使用者范围仍是「R3—R6 / R8 / R7 / R10 / R13 给分」。

**文件:行号 / 证据（命令）：**

```bash
sed -n '374,379p' references/roles.md
#   | **骨架 2** | §1B 的攻击面审稿人（六人） | **只给主责维度一个 1—5** |      ← 应为「输出五元组」
#   | **骨架 3** | 不打分角色（S-Lit / S-Nov / S-Repro / S-Devil；R12 下另含按需的 S-Feas） | **不给分** |
#                                                                                 ← 无 S-Integrity
sed -n '411,433p' references/roles.md
#   ### 5B. R12 攻击面审稿人（§1B 的六人）
#   **主责维度评分：** <`主责维度名`，1—5；同向，高 = 好>                          ← 骨架里没有五元组
sed -n '381,401p' references/roles.md | grep -nE 'R3—R6|R8|给分'
#   :377 骨架 1 使用者「R3—R6 / R8 / R7 / R10 / R13 给分；R12 的 D6 校准不给分」
#   :399 「**评分：** <1—5 分，R3—R6 审核 / R8 / R7 / R10 / R13 需要；D6 校准判定不需要评分>
#   :401 「### 质疑 / 补充（**R3—R65** / R8 / R7 / R10 / R13 交叉质询必填）」    ← 且是笔误（见 n-1）
```

**你问的 6b 答案：** **骨架 2 没有改成五元组**（仍是 `1—5`）。
**建议修法：** 骨架表第 3 列改为「主输出」：骨架 1 = 校准判定（不给分）、骨架 2 = **五元组**、
骨架 3 = 类别结论；骨架 2 模板把 `**主责维度评分：**` 改为五元组五行（分数降为可选记录行）；
骨架 3 使用者补 `S-Integrity`；§5A 的两处 `R3—R6 / R8 / R7 / R10 / R13` 改为「仅 R12/R13 校准」。

---

### M-4 `venue-standards.md` 未被 Wave 3 触及，仍规定会议审稿人在 R3—R6 / R8 / R7·R10·R13 派遣；SKILL 自身也有同款残留

**现象：** spec §7 文件地图把 `venue-standards.md` 列为 UPDATE（引用同步），实测 Wave 3 提交
对该文件 **0 行改动**；其 §0.1 的表仍写「**是否派遣子代理 = 是**」。SKILL 内部也还留着两处
相反作用域（§1.2 与 §6 清单）。

**文件:行号 / 证据（命令）：**

```bash
git diff bc175f5 6315643 --stat -- research-idea-pipeline/references/venue-standards.md   # → 无输出
sed -n '72,73p' research-idea-pipeline/references/venue-standards.md
#   | **R3—R6 / R8 / R7 / R10 / R13 的会议审稿人**（R-CVPR / …） | 每个会议审稿人**必须**输出三段 | 是 |
sed -n '632p' research-idea-pipeline/references/venue-standards.md
#   | [roles.md](roles.md) §1、§5、§6 | §0 两角度框架（限 R3—R6/R8/R7/R10/R13 会议审稿人 + `D6`） |
sed -n '323p;821p' research-idea-pipeline/SKILL.md
#   :323 「本条适用于**仍使用会议审稿人的 阶段（R3—R6 / R8 / R7 / R10 / R13）**」
#   :821 「（**仅 R3—R6 / R8 / R7 / R10 / R13**；R12 的 D6 只出汇总校准表，不派会议审稿人）」
```

**为什么是 MAJOR：** 这不是「引用扫尾」而是**派遣口径互斥** —— `SKILL.md:602—605` 说
R3—R6/R8/R7·R10·R13 都「不派 venue 角色」，同文件 `:323`/`:821` 与 `venue-standards.md:72`
却说这些阶段**要**派并且「必须输出三段」。
**建议修法：** 三处作用域统一为「**R12 / R13 的 venue calibration 表**（不派子代理）；
B5 的 concept 级快筛按 spec §6 消歧保留，但不得用于排序」；`venue-standards.md §0.1`
表的「是否派遣子代理」列改为「否（校准表）」。

---

### M-5 `R12-pre` 的落盘目标：spec 与 `phase-r12` **直接互斥**

**现象：** spec §4 说 pre「**不得写进 `narrative_view` 以外的地方**」（= pre 的产物要落在
`narrative_view`）；`phase-r12` 说 pre「产出一份预期叙事草稿（**不落 `narrative_view`**）…
**不得写进 `narrative_view`**」。

**文件:行号 / 证据（命令）：**

```bash
sed -n '85p' docs/r-architecture-wave3-spec.md
#   | **R12-pre** | R8 之后、R9 之前 | 只写「若 `H` 被验证，可能成立的 thesis 是…」；**不得决定研究方向**，
#     不得写进 `narrative_view` 以外的地方 |
sed -n '830p' research-idea-pipeline/references/phase-r12-narrative.md
#   | **R12-pre** | … | 只写「若 H 被验证…」；产出一份**预期叙事草稿**（不落 `narrative_view`）
#     | **不得决定研究方向**；不得据此筛候选、排实验优先级；**不得写进 `narrative_view`** |
sed -n '846p' research-idea-pipeline/references/phase-r12-narrative.md
#   | **R12** | `claims` / `evidence` / `failures` / `uncertainties` | `narrative_view`（+ 必要时新增 `uncertainties`） |
```

**影响：** 执行者无法判断 pre 的草稿落在哪里；若按 spec 字面执行，pre 会写 `narrative_view`，
与 `phase-r12:846`（R12 整体才写 `narrative_view`）以及「post 才落 `narrative_view`」冲突。
**建议修法（二选一，需 Lead 裁决）：** ①改 spec §4 该格为「pre 的产物是**草稿**，
**不得**写入 `narrative_view`（那是 post 的产物）」；②或允许 pre 写 `narrative_view`，
同时把 `phase-r12:830/846` 的写入口径改成「pre 写 draft 段、post 覆盖为定稿」。
**注意：** 你问的「pre 的产物能反过来筛候选」这个漏洞**已堵住** ✅（`:830` 明写
「不得据此筛候选、排实验优先级」，且给了机械问法「这条产物能让某一轮 R3/R9 改变选择吗」）。

---

### M-6 R 阶段文件里**仍有 venue 角色的派遣落点**（`phase-r3-r6` B3、`phase-r8` C1、`phase-r7` 旧 E 流程）

**现象：** SKILL §3 已写「不派 venue 角色」，但三个 phase 文件里的**旧流程仍在派遣它们**，
且 `phase-r7` **没有像 `phase-r3-r6` 那样的作用域裁决/banner**。

**文件:行号 / 证据（命令）：**

| 落点 | 位置 | 原文（节选） |
|---|---|---|
| B3 头脑风暴 | `references/phase-r3-r6-discovery.md:108—125` | 「**派遣以下子代理**…\| R-CVPR \| 从方法落地…\| R-ICML \| …\| R-NeurIPS \| …\| R-MICCAI \| …」+「7 个视角，合计 ≥ 21 个原始候选」 |
| R8 C1 创新性研究 | `references/phase-r8-evidence-contract.md:28—40` | 「**派遣：** R-CVPR / R-ICML / R-NeurIPS / R-MICCAI 四视角**分别独立**评估…」「四个审稿人一律按「两角度 + 会议特性」评审」 |
| R8 state 片段 | `references/phase-r8-evidence-contract.md:194` | `"novelty_verdict": {"R-CVPR": "中", "R-ICML": "高", …}` |
| R7 旧 E2 八子代理 | `references/phase-r7-r10-r13-assurance-repair-review.md:91—98` | `### E2.1 八子代理分工` + 四会议审稿人表（含 `R-MICCAI` 临床维度） |
| R7 旧 E3 中位数 | 同上 `:201`、`:207—208`、`:336—339`、`:355`、`:358`、`:369` | 中位数表 / `review_output` 片段以 `R-CVPR`/`R-ICML` 为键 |

```bash
grep -n 'R-CVPR\|R-ICML\|R-NeurIPS\|R-MICCAI' references/phase-r3-r6-discovery.md | head -4
grep -n '派遣：.*R-CVPR' references/phase-r8-evidence-contract.md
grep -nE '^#{2,3} E[0-9]|^## R7 assurance' references/phase-r7-r10-r13-assurance-repair-review.md
#   phase-r7 结构：E0—E8（:10—:323，旧流程，无 banner）→ R7 assurance（:379）→ R13 审计（:424）
```

**为什么是 MAJOR：** ①与 `SKILL.md:602—605`、`roles.md:14`、spec §6 直接冲突；
②`phase-r7` 的旧 E 流程与新 R7 节**同文件并存且旧节在前**，与 Wave 2 在 `phase-r3-r6`
踩过的坑同型（那里后来补了「作用域裁决 + 三处 banner」）。
**建议修法：** ①`phase-r3-r6` B3：删掉四个会议审稿人行，改为「按 island 分轨由执行者生成；
快筛由 `S-Lit`/`R-Novelty`/`R-Causal`/`S-Feas`/`S-Devil` 承担」；
②`phase-r8:28—40` 改为「**不派 venue 角色**；创新性判定按 B5 快筛结论增量复核」，
`:194` 的 `novelty_verdict` 键改为攻击面/类别键；
③`phase-r7` 给 E0—E8 加与 `phase-r3-r6` 同款的**作用域裁决注 + 分节 banner**
（至少 E2.1/E3），并注明「venue 角色仅 R12/R13 校准表」。

---

## 2. MINOR

| # | 现象 | 文件:行号 | 证据（命令） | 建议修法 |
|---|---|---|---|---|
| m-1 | **`S-Integrity` 未接入四处**：§4.2 矩阵（见 M-1）、§5 骨架 3（见 M-3）、**§6 攻击面量表**（无此行）、**§7 字数表**（无此行）；`scoring-policy.md` **完全未提** `S-Integrity` / Integrity Gate —— 而它是「不通过即不得提交」的 Gate 承担者，评分政策无处登记 | `roles.md:461—505`（§6）、`:507—520`（§7）；`scoring-policy.md` 全文 | `grep -n 'S-Integrity' roles.md`（仅 :16/:263/:272）；`grep -c 'Integrity' scoring-policy.md` → 0 | §6 表加一行「S-Integrity（R13）\| Integrity Gate 判定 \| 喂 G？/直接否决」；§7 加其字数行；`scoring-policy §3` 注明「Integrity Gate 与 `G1—G5` 并列，不通过即不得提交」 |
| m-2 | 锚点→「首要审查项」仍点名会议审稿人，属于派遣式表述 | `roles.md:352—354` | `sed -n '352,354p' roles.md`（「理论 → S-Theory 与 **R-ICML**…」） | 改为「理论 → `R-Theory` 与 `S-Theory`；性能 → `R-Experimental` 与 `A-Experimenter`；现象/基准 → `R-Causal`/`R-Utility`」 |
| m-3 | `phase-r7` 的**八攻击面表把「完整性」列为 R7 的攻击面**（`:392`），未标「R13 起」；同页下方 R13 段才是 Gate | `phase-r7-r10-r13-assurance-repair-review.md:392`（对照 `:429`、`:433—437`） | `sed -n '381,392p;429,437p'` | 该行角色列改为「`S-Integrity`（**R13 起生效**，R7 只登记待查项）」 |
| m-4 | spec §7 文件地图要求 `phase-r7` 含 **venue 校准表**；实测该文件只有一句排除说明（`:419`），没有校准表 | spec `:121`；`phase-r7:419` | `grep -nE '^\| (CVPR\|ICML\|NeurIPS\|MICCAI)' phase-r7-*.md` → 无 | 要么在 R7 节补一张最小校准表（并入 `venue-standards.md §10.2` 的键），要么把 spec §7 该行改为「引用 §10.2」 |
| m-5 | `examples/` 两处仍以会议审稿人做派遣/评分；**不在**你的「已知未做」清单里（清单只点 `example-d-narrative.md`） | `examples/example-b-to-c-d-e.md:22`（B3 派 7 个头脑风暴子代理含四会议角色）、`:35`（source R-ICML）；`examples/example-followup-review.md:49`（R-CVPR 分数行） | `grep -n 'R-CVPR\|R-ICML\|R-NeurIPS\|R-MICCAI' examples/*.md` | 与 `phase-r3-r6` / `phase-r7` 的修法同步改；或把这两个示例补进「已知未做」清单 |
| m-6 | SKILL §6 执行自检清单**未加**五元组 / `Kill Condition` 可判定 / Integrity Gate 三项（spec §7 只要求 SKILL §2/§3/§4/§7，故列 MINOR 而非未达成） | `SKILL.md:785—877`（§6） | `sed -n '785,877p' SKILL.md \| grep -cE '五元组\|Integrity'` → 0 | 加两条勾选项：R7/R10/R13 的每份 assurance 输出五元组且 Kill Condition 可判定；R13 的 Integrity Gate 已判定 |
| m-7 | spec §8 验收 2 要求 `Kill Condition` 可判定**给正反例**；实际只给了一个**正例**（MIND 例），没有「不可判定长什么样」的反例 | spec `:61—70`、`:134`；`phase-r7:411` | `sed -n '61,70p' docs/r-architecture-wave3-spec.md`；`sed -n '399,401p' phase-r7-*.md` | 补一条反例：`Kill Condition: "if the mechanism is wrong"` → 不可判定，attack 无效（并说明缺「若观察 O 则 X」结构） |

---

## 3. NIT

| # | 现象 | 文件:行号 | 证据 | 建议 |
|---|---|---|---|---|
| n-1 | 笔误 `R3—R65`（应为 `R3—R6`；疑似 `R3—R6` 与 `B5` 的批量替换事故） | `roles.md:401` | `sed -n '401p' roles.md` | 改 `R3—R6`；同时该行范围本身应随 M-4 改为「仅 R12/R13 校准」 |
| n-2 | README 仍写「会议审稿人在 R3—R6 / R8 / R7 / R10 / R13 每次评价给三段」（属你登记过的已知未做：README venue 引用扫尾） | `README.md:232—235` | `sed -n '232,235p' README.md` | 随 README 扫尾一起改 |
| n-3 | `SKILL.md:204` 的句子被 Wave 2 的 shortlist→elite 替换改得不通顺：「QD archive 的 elite 集合 只收服务主锚点的 idea」 | `SKILL.md:204` | `sed -n '204p' SKILL.md` | 改为「只把服务主锚点的候选登记进 QD archive 的 elite 集合」 |

---

## 4. spec §8 验收标准逐条判定

| # | 验收项（spec §8） | 判定 | 证据 |
|---|---|---|---|
| 1 | `roles.md` 里 venue 角色不再出现在**任何 R 阶段的派遣表**（只在校准表） | **未达成** | `roles.md:300—305`（§4.2 矩阵 ●）+ `:352—354` + `:377`；另外 `venue-standards.md:72`、`SKILL.md:323/821`、`phase-r3-r6:115—118`、`phase-r8:30` 也仍是派遣口径（M-1 / M-4 / M-6） |
| 2 | 每个 assurance 算子给出五元组；`Kill Condition` 可判定（给正反例） | **部分达成** | 五元组字面在 5 处逐字一致（spec`:58`、`phase-r7:397`、`scoring-policy:39`、`SKILL:733/979`、`roles:269`）；**`roles §1B` 无五元组**（M-2）；**只给正例、无不可判定反例**（m-7） |
| 3 | assurance 不得改 `claims[].status` 写成硬规则，与 §1.6 一致 | **达成** | `phase-r7:414`（规则 3，指向 `../SKILL.md` §1.6）；`SKILL.md:548`（§1.6「改 `claims[].status` 只能经 R10」）；`SKILL.md:735`（§4 同款）；`SKILL.md:779`（§5 同款）。`roles §1B` 未收录该规则（并入 M-2） |
| 4 | `S-Integrity` 是 Integrity Gate 承担者，且**只在 R13 生效** | **达成** | `roles.md:263—276`（含 vs `S-Repro` / `R-Experimental` 的分工 + 「只在 R13 生效（R7/R8 无 artifact…）」）；`phase-r7:429` + 时机表 `:433—437`；`SKILL.md:605`（「`S-Integrity`（完整性，R13 生效）」）+ `:736` |
| 5 | R12-pre / R12-post 的输入输出边界写清（pre 不得决定方向；post 不得新增 `evidence`） | **部分达成** | `phase-r12:824—845` ✅（含「不得据此筛候选」与机械问法）；`SKILL.md:704—706` ✅ 与之一致；**但 spec §4 与 `phase-r12:830` 对 pre 的落盘目标互斥**（M-5） |
| 6 | venue 校准表与 `venue-standards.md` §10 一致 | **部分达成** | `phase-r7:419` 指向 §10 ✅；但 `phase-r7` 无校准表（m-4），且 `venue-standards.md` 本次 0 改动、其 §0.1 与 SKILL 作用域仍相反（M-4） |
| 7 | 全量机械校验：链接 / `§` 引用 / JSON / 单测 / linter / deprecated-terms | **达成** | §5.4 全绿（413 链接 0 断链、deprecated 0、JSON 合法、**116 tests OK**、`--selftest` 0、模板 0、linter 9/9） |
| 8 | 三方口径 14 阶段仍逐字一致 | **达成** | 独立脚本复跑：**14/14 逐字相同**，唯一「不一致」是 R1（policy §5 明写 R1 不占行） |
| 9 | 独立 verifier 对抗验收通过 | **未通过（本报告）** | 见 §1 — §3 |

---

## 5. 必做项复核（方法 + 命令 + 结果）

### 5.1 复核范围与只读纪律

- 只写 `docs/verify-r-wave3.md`；未改任何被审文件；未 `git commit`。
- 复核对象：Wave 3 提交 `6315643` 的 5 个文件 + spec §7 文件地图点名的 `venue-standards.md`
  （未改，作为缺陷记录）。

### 5.2 venue 角色逐处判定（**逐个判断，不是只看计数**）

全仓命中 80 处（`grep -rnE 'R-CVPR|R-ICML|R-NeurIPS|R-MICCAI' --include=*.md`，分布：
phase-r7 22、roles 17、venue-standards 11、phase-r3-r6 11、SKILL 6、phase-r8 3、phase-r12 3、
README 3、examples 3）。**按性质分类：**

| 类别 | 位置 | 判定 |
|---|---|---|
| 校准视角定义 | `roles.md:12/20/22/26/30/48/58/70/79`；`venue-standards.md:96—99/322—325/327/329`；`roles.md:497` | ✅ 允许 |
| 排除说明（不参与科学发现） | `roles.md:14/16/327`；`SKILL.md:565`；`phase-r12:416/556`；`phase-r7:419` | ✅ 允许（但 `roles:327` 只排除 D5/D6，未覆盖 B3/C/E → 见 M-1） |
| 设计依据 / 历史说明 | `SKILL.md:955/974`（§7 第 16 条）；`phase-r12:802`（旧 `scores` 键已删） | ✅ 允许 |
| B5 concept 级快筛 | `phase-r3-r6:166—169/202/205/244` | ✅ 允许（Wave 3 spec §6 第 3 行明示消歧） |
| **派遣落点（违规）** | `roles.md:302—305`（§4.2 ●）、`:352—354`、`:377`；`venue-standards.md:72/632`；`SKILL.md:323/821`；`phase-r3-r6:115—118`；`phase-r8:30/38/194`；`phase-r7:95—98/201/207—208/336—339/355/358/369`；`examples/example-b-to-c-d-e.md:22/35`、`example-followup-review.md:49` | ❌ M-1 / M-4 / M-6 / m-2 / m-3 / m-5 |
| 已知未做（不计缺陷） | `README.md:232—235` | 登记为 n-2 |

### 5.3 五元组契约四处比对

| 位置 | 是否含五元组 | `Kill Condition` 可判定 | status 禁改 | 字段名与顺序 |
|---|---|---|---|---|
| `phase-r7` R7 节（`:394—417`） | ✅ | ✅ 规则 1（「写成『若观察 O 则 X』；写不出即无效」） | ✅ 规则 3（→ SKILL §1.6） | ✅ 与 spec 逐字相同 |
| `roles.md` 攻击面节（§1B `:97—166`） | ❌ **无** | ❌ | ❌ | — |
| `scoring-policy §0`（`:34—45`） | ✅ | ✅（「只有分数、没有可判定的 Kill Condition 的评审不合格」） | —（未提，属 phase-r7 权威） | ✅ 逐字相同 |
| `SKILL §4`（`:733—737`） | ✅ | ✅ | ✅（「assurance 不得直接改 `claims[].status` —— 只能经 R10」） | ✅ 逐字相同 |
| （附）`roles.md` `S-Integrity` 节（`:269`） | ✅ | —（只说同构） | — | ✅ 逐字相同 |

**字面量比对命令：** `grep -rn 'Attack, Target Claim, Alternative, Discriminating Test, Kill Condition' --include=*.md .`
→ 5 处全部逐字相同（spec`:58`、`scoring-policy:39`、`roles:269`、`phase-r7:397`、`SKILL:733/979`）。
**结论：字段名与顺序四处一致 ✅；但四处中的 `roles` 攻击面节完全没有五元组（M-2）。**
`assurance 不得改 claims[].status` 与 `SKILL §1.6`（`:548`）**一致** ✅。

### 5.4 机械校验（自己跑，快照 `6315643`）

| # | 项 | 结果 |
|---|---|---|
| 1 | 相对链接（去围栏） | **413 条，0 断链** ✅ |
| 2 | deprecated-terms | **exit 1，0 命中** ✅ |
| 3 | JSON（模板 + refs 索引） | 合法 ✅ |
| 4 | `python3 -m unittest discover -s scripts -p "test_*.py"` | **116 tests OK** ✅ |
| 5 | `state_check --selftest` | exit 0 ✅ |
| 6 | 模板 `--check` | exit 0 ✅ |
| 7 | examples + templates linter | 9/9 硬违规 0 ✅ |
| 8 | `--list-rules` ↔ `policy §4` | **15 条逐字一致，无缺失** ✅ |
| 9 | 三方口径 14 阶段 | **14/14 逐字相同** ✅ |

### 5.5 找碴（你指定的三项）

| 项 | 结论 | 证据 |
|---|---|---|
| **① R3—R6 改成「按 island 分轨生成、不派 venue 角色」后还有没有可派遣落点？** | **有落点，但没写在该写的地方，且旧落点仍在生效**。落点存在：`SKILL.md:602` 给出「concept 级快筛由 `S-Lit` + `R-Novelty` + `R-Causal` + `S-Feas` 承担，`S-Devil` 出致命反驳」✅；但 `phase-r3-r6` 的 **R3 正式段（`:325—349`）只说「按 island 分轨」，没有一句「谁生成候选」**，而 **B3（`:108—125`）仍在指示派 7 个具名子代理（含四个会议角色）**。执行者最可能照 B3 派人（旧节在前、有「派遣」祈使句），从而既违 spec §6 又回到「一轮 brainstorm」。**建议**：在 R3 段补一句「候选由执行者按 island 分轨生成；子代理仅用于快筛与攻击面，角色必须取自 `roles.md`」并把 B3 的四个会议角色行删除 | §1 M-6；`sed -n '319,353p;108,125p' phase-r3-r6-*.md` |
| **② `roles.md §5` 骨架 2 是否已改为输出五元组？** | **没有**：骨架选择表仍写「只给主责维度一个 1—5」，骨架 B 模板仍以「主责维度评分 1—5」为主输出；`§1A:26` 却已宣称「他们按 §5 骨架 B 输出五元组」→ 同文件自相矛盾 | §1 M-3；`sed -n '374,379p;411,433p' roles.md` |
| **③ `roles §4.2` 矩阵是否还有 `R-CVPR` 等旧列？** | **有**：`R-CVPR`/`R-ICML`/`R-NeurIPS`/`R-MICCAI` 四行仍在，且在 `B3 头脑风暴`/`C 方案生成`/`E 方案复核` 三列是 **●**；列头也仍是旧的 `B/C/D/E` 命名；无 `S-Integrity` 行 | §1 M-1；`sed -n '300,305p' roles.md` |

---

## 6. 未覆盖项与验收限制

1. **未评审 Wave 3 的科学实质**（15 算子 → 现有角色 + `S-Integrity` 的取舍是否合理、五元组是否
   足以替代分数）—— 该取舍 spec §2 已标注**需用户确认**，属设计决策，不在验收范围。
2. **未核 spec 引用的外部系统**（Co-Scientist 等）：Wave 1 spec 已声明由用户提供、未经核实；
   本环境无外网，不做外部核验。
3. **未逐行评审 `venue-standards.md` 的会议标准内容**（只核它在本波的引用/作用域同步），
   因其本次 0 改动且属 Wave 1 已验收对象。
4. **未评审 `README.md` / `project-layout.md` 的 venue 引用扫尾**（你已登记为已知未做），
   仅登记 README 一处（n-2）。
5. 本报告未修改任何被审文件；未 `git commit`。唯一写入：`docs/verify-r-wave3.md`。

---

## 7. 修复清单（按优先级）

| 优先级 | 动作 | 文件:行号 |
|---|---|---|
| 1 | §4.2 矩阵：四个会议审稿人行改「—（仅 R12/R13 校准表）」、列头改 R 阶段、补 `S-Integrity` 行 | `roles.md:300—305` |
| 2 | §1B：改为五元组主输出 + 补三条硬规则（可判定 Kill Condition / Test→X/TBD / 禁改 status）；标题去 `R12 主审` | `roles.md:97—113` |
| 3 | §5：骨架表第 3 列改「主输出」、骨架 2 模板改五元组、骨架 3 补 `S-Integrity`、§5A 范围改校准 | `roles.md:374—379`、`:411—433`、`:377/:399/:401` |
| 4 | venue 作用域统一（venue-standards §0.1 + SKILL §1.2/§6 + roles §1A 互相对齐） | `venue-standards.md:72/632`、`SKILL.md:323/821` |
| 5 | R12-pre 落盘目标：改 spec §4 或 phase-r12 §R12-pre（二选一，Lead 裁决） | `docs/r-architecture-wave3-spec.md:85`、`phase-r12:830` |
| 6 | 三个 R 阶段文件的 venue 派遣落点清理 + `phase-r7` 补作用域裁决/banner | `phase-r3-r6:115—118`、`phase-r8:28—40/194`、`phase-r7:91—98/201/207—208/336—339` |
| 7 | MINOR m-1—m-7（S-Integrity 接入 §6/§7 与 scoring-policy、锚点分工、R7 面标注、校准表、示例、§6 清单、Kill Condition 反例） | 见 §2 |
| 8 | NIT n-1—n-3（`R3—R65` 笔误、README、SKILL:204 语句） | 见 §3 |

**一句话总体结论：需修后交付** —— 新写的 R7 五元组节 / R13 Integrity Gate / scoring-policy §0 /
SKILL §2·§3·§4·§7 / phase-r12 pre-post **五处自洽且字面一致**，`S-Integrity` 的边界与
「只在 R13 生效」写得清楚，机械面与三方口径全绿；但**角色层的后移只落在 SKILL 与新节上**，
`roles.md` 的**权威派遣矩阵（§4.2）、攻击面角色段（§1B）、输出骨架（§5）三处仍是 Wave 2 状态**
（仍派会议审稿人、仍以 1—5 分为主输出），`venue-standards.md` 未同步，SKILL 内部还有两处
相反作用域表述 —— 这 6 项 MAJOR 修完即可交付。

---

## 8. 增量复核（Wave 3 收官确认）

**快照：** `9d63395`（工作树干净；`docs/verify-r-wave3.md` 已被该提交一并提交）。
**本轮改动：** 8 个文件（`git diff --stat 6315643 9d63395`）：roles.md **+94/−42（12 hunks）**、
SKILL.md、phase-r3-r6、phase-r7、scoring-policy、venue-standards、spec、本报告。
**纪律：** 本次仅向本文件追加本节；未改任何被审文件、未 commit。

### 8.1 六项 MAJOR + MINOR 逐条确认

| 项 | 声明 | 现值（文件:行号） | 判定 |
|---|---|---|---|
| **M-1** | §4.2 矩阵重建：列改 R 阶段、会议审稿人四行改「—（仅校准表）」、新增 `S-Integrity` 行、写明不派遣阶段 | `roles.md:309—311`（「列 = R 阶段…不再出现在任何派遣列」+ 表头 `R3—R6 / R7 / R8 / R12 / R13`）；`:314` 四个会议审稿人**合并为一行，五列全 `—（仅校准表）`**；`:315—330` 各行（`S-Integrity` 在 `:321`）；**`:321` `S-Integrity` 行（仅 R13 为 ●）**；`:331`「R0/R1/R2/R5/R9—R11/R14 不派遣子代理」 | ✅ **达成** |
| **M-2** | §1B 改为五元组 primary + 三条硬规则 | `roles.md:97`（标题「R7 / R12 主审；**输出五元组**」）；`:101—102` 派遣 R7 与 R12；`:104—116`：五元组字面 + 5 条硬规则（1 `Kill Condition` 可判定 / 2 `Test`→`X`/`TBD` / 3 **不得直接改 `claims[].status`**→R10 / 4 分数次要 / 5 摘要并存）；`:122` 共同硬要求第 6 条指向 §5 骨架 B | ✅ **达成** |
| **M-3** | §5 三骨架：骨架 1 仅校准表、骨架 2 主输出五元组、骨架 3 含 `S-Integrity`；5B 模板改三段 | `roles.md:391`（骨架 1「**仅用于 venue calibration 表**（R12 / R13）；不是子代理，不产评分」）；`:392`（骨架 2「**主输出五元组**；1—5 分只作次要记录」+ `S-Integrity`）；`:393`（骨架 3 含 `S-Integrity`）；`:425—447` 5B 模板 = ① 五元组（primary，逐字段含可判定 `Kill Condition`）② 摘要 ③ 次要评分；`:415` 笔误 `R3—R65` 已改为「（R7 / R12 交叉质询必填）」 | ✅ **达成**（两处歧义见 §8.3 MINOR-D/E） |
| **M-4** | `venue-standards:72` 派遣列改「否」；`SKILL:324/:823` 旧作用域串改「仅校准表」 | `venue-standards.md:72` 行内容 = 「**venue calibration 表的会议视角**（…仅 R12 / R13）…校准表的每一行**必须**给出三段 \| **否**（表，不是子代理）」；`SKILL.md:324`「本条**仅适用于 venue calibration 表**（R12 / R13）」；`SKILL.md:823`「（**仅 venue calibration 表**）」 | ✅ **达成** |
| **M-5** | spec §4 的 R12-pre 口径与 `phase-r12:830` 一致（不落 `narrative_view`） | `docs/r-architecture-wave3-spec.md:85`：「…**不得决定研究方向**；产出的预期叙事草稿**不落 `narrative_view`**」；与 `phase-r12:830` 完全一致 | ✅ **达成** |
| **M-6** | `phase-r7` 加作用域裁决；`phase-r3-r6` 加「谁生成候选」澄清 | `phase-r7:11—14`「⚠️ **作用域裁决（Wave 3）**：`E0`—`E8` 是旧流程…冲突时以 R7 / R13 节为准；`E2` 的八子代理名单已被八个攻击面算子取代；会议审稿人只在 R12/R13 校准表」；`phase-r3-r6:327—330`「**谁生成候选（Wave 3 澄清）**：候选由**执行者按 island 分轨生成**…子代理不负责生成候选，只用于 concept 级快筛与致命反驳；因此 `B3` 里「派遣 7 个具名子代理各出 ≥3 idea」的**旧指示作废**」 | ✅ **达成** |
| MINOR-1 | `scoring-policy` 新增 §0.1 Integrity Gate | `scoring-policy.md:46—53`：不是评分、与 `G1—G5` 同级但独立、「不通过即不得提交」、「**不进**中位数向量，也不参与排序」、生效时机 R13、权威见 phase-r7 R13 节 | ✅ 达成 |
| MINOR-2 | `SKILL §6` 清单 +2 项 | `SKILL.md:829`（五元组齐备 + `Kill Condition` 可判定）、`:830`（Integrity Gate（R13）+ R7/R8 未要求 artifact 审计） | ✅ 达成 |
| MINOR-3 | `examples` 两处 venue 角色改口径 | **文件未改**：`git diff --name-only 6315643 9d63395 \| grep examples` → 空；`example-b-to-c-d-e.md:22`（B3 派 7 个头脑风暴子代理含四会议角色）、`:35`（source = R-ICML）、`example-followup-review.md:49`（R-CVPR 评分行）**原样** | ❌ **未落地 → MINOR-A** |
| MINOR-4 | `spec §8` 补 `Kill Condition` 正反例 | `docs/r-architecture-wave3-spec.md:134`：「**正例**：「若替代解释在等算力下追平，则移除机制专属 claim」；**反例**：「若结果不好看则重新考虑」（不可判定 → 该 attack 无效）」 | ✅ 达成 |
| MINOR-5 | `roles:401` 笔误 `R3—R65` 修正 | `roles.md:415` 现为「（**R7 / R12** 交叉质询必填）」，笔误已消失 | ✅ 达成 |

**小计：6/6 MAJOR 完整落地；声称的 5 项 MINOR 中 4 项落地，1 项（examples）未落地。**

### 8.2 item 2：`roles.md` venue 残留重跑分类（原 17 处 → 现 13 处）

| 类别 | 位置 | 现值 |
|---|---|---|
| ✅ 排除说明 | `roles.md:14`、`:309—311`、`:314`、`:340`、`:391` | 「不再出现在任何 R 阶段的派遣表」「不再出现在任何派遣列」「—（仅校准表）」「仅用于 venue calibration 表」 |
| ✅ §1/§1A 校准视角定义 | `roles.md:22`、`:30`、`:48`、`:58`、`:70`、`:79`、`:519`（§6 条件性维度，校准相关） | 角色定义与三件套要求（只服务校准表） |
| ❌ **违规（仍未改）** | **`roles.md:365—367`** | 「主锚点 = 理论 → S-Theory 与 **R-ICML** 的证明正确性是首要审查项；性能 → A-Experimenter 与 **R-CVPR**…；现象/基准 → **R-NeurIPS**…」——这些角色已不参与科学发现，却仍被指派「首要审查项」 → **MINOR-B** |
| ⚠️ 旧子步号字面（非违规） | `roles.md:24/45/340/351/355/358/485/487/521/539/545/546` | `D5`/`D6`/`D`/`E2`/`B` 等 Wave 1 子步号（如 `:355`「**D 的叙事审核**」、`:356`「**E2** 方案级深审」、`:485`「**派遣（D5）**」）→ **NIT-A** |

**结论：`roles.md` 里真正的「按 venue 组织」违规从 20+ 处降到 1 处（`:365—367`）**；
其余是旧子步号措辞。

### 8.3 item 3：新矛盾检查（S-Integrity 定义 vs 引用；§0.1 vs phase-r7 R13）

**S-Integrity 定义位置与被引用位置：**

| 位置 | 是否一致 |
|---|---|
| 定义：`roles.md:263—276`（§3，含 vs `S-Repro` / `R-Experimental` 的边界 + 只在 R13 + Integrity Gate） | — |
| §4.2 矩阵 `:320`（R13 ●） | ✅ |
| §5 骨架表 `:392`（骨架 2）与 `:393`（骨架 3） | ⚠️ **同时出现在两个骨架** → 用哪个模板不明确 → **MINOR-D** |
| §5B 标题 `:425`「（§1B 的六人）」 | ⚠️ 未含 `S-Integrity`（与骨架 2 的「六人 + S-Integrity」不一致）→ 并入 MINOR-D |
| §5B 质疑行 `:448`「（**R12** 交叉质询必填）」 | ⚠️ `S-Integrity` 在 **R13** 生效 → 并入 MINOR-D |
| `phase-r7:392`（R7 八攻击面表）+ `:429`（R13 Integrity Gate） | ✅（但 R7 表未标「R13 起」，见上轮 m-3，本轮未改 → NIT） |
| `scoring-policy:46—53`（§0.1） | ✅ |
| `SKILL.md:565/605/736/830` | ✅ |
| `roles.md §6`（R12 攻击面量表）/ `§7`（字数表） | 未列 `S-Integrity` —— 可解释（它是 R13-only，不属 R12 量表；字数由阶段行覆盖），**不作为缺陷**，仅建议在总收官时补一句范围说明 |

**`scoring-policy §0.1` 与 `phase-r7` R13 节的一致性：✅ 一致。**
两边都写「不是评分 / 不是 warning、**不通过即不得提交**」；§0.1 额外给出评分政策层的位置
（不进向量、不参与排序、R13 生效、权威在 phase-r7 的 R13 节），phase-r7 `:429` 给出四类命中项
（cherry-picking / leakage / metric misuse / post-hoc）—— 无冲突。

**另发现（§5A 内部残留）：** `roles.md:410` 的模板行仍写
「**评分：** <1—5 分，**R3—R6 审核 / R8 / R7 / R10 / R13 需要**；D6 校准判定不需要评分>」，
与骨架 1「仅用于 venue calibration 表…**不产评分**」矛盾 → **MINOR-E**。

### 8.4 item 4：机械面复跑（快照 `9d63395`）

| # | 项 | 结果 |
|---|---|---|
| 1 | 相对链接（去围栏） | **415 条，0 断链** ✅ |
| 2 | deprecated-terms | **exit 1，0 命中** ✅ |
| 3 | JSON（模板 + refs 索引） | 合法 ✅ |
| 4 | `python3 -m unittest discover -s scripts -p "test_*.py"` | **116 tests OK** ✅ |
| 5 | `state_check --selftest` | exit 0 ✅ |
| 6 | 模板 `--check` | exit 0 ✅ |
| 7 | examples + templates linter | 9/9 硬违规 0 ✅ |
| 8 | `--list-rules` ↔ `policy §4` | **15 条逐字一致，无缺失** ✅ |
| 9 | 三方口径 14 阶段 | **14/14 逐字相同**（唯一「不一致」= R1，policy §5 明写 R1 不占行） ✅ |

### 8.5 剩余项（0 项未落地 MAJOR）

| # | 级别 | 现象 | 文件:行号 | 修法（行级） |
|---|---|---|---|---|
| A | **MINOR（声明未落地）** | `examples` 两处未按声明改口径：B3 仍派 7 个头脑风暴子代理（含四个会议审稿人）、source 仍是 `R-ICML`、reviewer 分数表仍是 `R-CVPR` | `examples/example-b-to-c-d-e.md:22`、`:35`；`examples/example-followup-review.md:49` | 与 `phase-r3-r6:327—330` / `phase-r7:11—14` 同步：B3 改为「执行者按 island 分轨」；`source_agent` 改攻击面/核验员；分数行改攻击面维度或标「旧口径」 |
| B | MINOR | 锚点→「首要审查项」仍点名 `R-ICML` / `R-CVPR` / `R-NeurIPS` | `roles.md:365—367` | 改为 `R-Theory`/`S-Theory`、`R-Experimental`/`A-Experimenter`、`R-Causal`/`R-Utility` |
| C | MINOR | §5A 模板的「评分」行仍写「R3—R6 审核 / R8 / R7 / R10 / R13 需要」，与骨架 1「仅校准表、不产评分」矛盾 | `roles.md:410` | 改为「**校准表不产评分**；如需记录倾向，写类别判定（`适配 / 需补齐 / 不匹配`）」 |
| D | MINOR | `S-Integrity` 同时列在骨架 2 与骨架 3；§5B 标题仍「（§1B 的六人）」未含它；§5B 质疑行写「R12 交叉质询」而它在 R13 生效 | `roles.md:392`、`:393`、`:425`、`:448` | 归一到骨架 2（它输出五元组），§5B 标题改「六人 + `S-Integrity`」，质疑行改「R7 / R12 / R13」 |
| E | NIT | 旧子步号字面：`D5`/`D6`/`D`/`E2`/`B`（如「派遣（D5）」「D 的叙事审核」「E2 方案级深审」「派到 B」） | `roles.md:24/45/340/351/355/358/485/487/521/539/545/546` | 总收官轮统一为 R 阶段号；§6/§7 表头（`D5`/`E2`/`C3`/`B5`）同批处理 |
| F | NIT | 「**六个**攻击面审稿人」（`roles §1B:101`、§4.2 注 `:337`、§6 `:485`）与「**八个**攻击面」（`phase-r7:381`、`SKILL.md:605`）两种口径并存 | 同上 | 统一为「六个攻击面审稿人 + `S-Lit` / `S-Repro` / `S-Integrity` = **八个攻击面**」 |
| G | NIT | `phase-r7:392` 的 R7 八攻击面表把「完整性 / `S-Integrity`」列为 R7 面，未标「R13 起」（上轮 m-3） | `phase-r7:392` | 该行角色列加「（**R13 起**，R7 只登记待查项）」 |

### 8.6 收官结论

**0 项 MAJOR 未落地；1 项声明未落地的 MINOR（A）+ 3 项 MINOR（B/C/D）+ 3 项 NIT（E/F/G）。**
六项 MAJOR 全部核实通过：矩阵已重建且**五列全部 `—（仅校准表）`**、`S-Integrity` 有独立行、
§1B/§5 骨架 2 的主输出**确为五元组**、骨架 3 含 `S-Integrity`、`venue-standards:72` = 「否」、
SKILL 两处作用域改为「仅校准表」、spec §4 与 phase-r12 口径一致、`phase-r7`/`phase-r3-r6`
两处作用域裁决到位；`roles.md` 的 venue 违规从 20+ 处降到 **1 处**（`:365—367`）。
机械面全绿（415 链接 0 断链、116 测试、deprecated 0、模板 0、linter 0、`--list-rules` ↔ policy
15 条逐字一致、三方 14/14）。

**按你的闸门（「只剩 NIT 才能直接说可交付」）：仍需修 —— 4 项 MINOR（A 为声明未落地）+ 3 项 NIT，
全部是一行到三行的文本改动。** 其中 A 是你本轮声明已改而实际未改的一项（examples 三个文件位置），
建议不要并入总收官：它和 `phase-r3-r6` / `phase-r7` 的新口径直接冲突，会让读者在示例里
继续看到「派 7 个会议审稿人头脑风暴」的旧流程。**B/C/D 三处修完（合计 3 行）后，
Wave 3 我这边无其它阻断项，可以做三波总收官。**
