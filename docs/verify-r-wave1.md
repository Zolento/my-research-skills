# R 架构 Wave 1：独立对抗性验收报告

**验收对象：** 分支 `research-idea-pipeline-dev`，全部改动未提交，基线 commit `f8cefdc`。
**契约：** [`docs/r-architecture-wave1-spec.md`](r-architecture-wave1-spec.md)（下称「spec」）。
**验收者：** teammate `verifier`（只读；本文件是本次验收唯一写入的文件）。
**验收时间：** 2026-10-06 ｜ **工作目录：** `research-idea-pipeline-dev/`（文件行号相对仓库根）。

**立场声明：** 不采信任何写作者自述。每条结论附 文件:行号 与可重跑命令。
机械校验与「扫过但没问题」的项在 §5、§6 逐条列出，以区分「真的没问题」与「没扫」。

> **⏩ 第二轮更新（Lead 修复后的增量复核）：见 §9。**
> §1—§8 是第一轮（修复前）的验收记录，保留原始证据供追溯。
> §9 给出 8 项 MAJOR 与声称的 MINOR 的逐条确认、三方读写口径现状、新引入的矛盾、
> V11/V12 闸门建议与机械复跑结果。**交付判定以 §9.6 为准。**
> **快照说明：** §9 的核验基线是 **06:12 的文件快照**；Lead 最后一笔编辑在 06:10:25，
> 之后无文件变动（`find research-idea-pipeline -newermt '06:10:30' -type f` 为空）。

---

## 0. 结论摘要

| 级别 | 条数 | 说明 |
|---|---|---|
| **MAJOR** | **8** | 改名不彻底／跨层互斥指令／不存在文件与字段／被删 schema 残留 |
| MINOR | 9 | 计数、术语、作用域、机械闸门与规则的覆盖差 |
| NIT | 5 | 文档结构、占位值、历史注释 |

**总体结论：需修后交付。** 本轮**新增件**（`state_check.py`、`test_state_check.py`、
`templates/research-state.template.json`、`research-state-policy.md`、`phase-r0-contract.md`、
`phase-r9-r11-experiment-loop.md`）质量高且经独立 fixture 验证可用；
`git mv` 迁移的 5 个文件**内容零丢失**（§5.2 逐段比对）。问题集中在
**「机械改名做了一半」**：`Mode [ABCDE]`／`mode=[ABCDE]`／`mode-[abcde]-` 三种字面量确实清零了，
但**裸字母 A—E 表行、`mode-x` 链接标签、"Mode" 术语、被删 schema 的键与旧路径**都留了下来，
其中 3 处直接构成跨层互斥指令（§1.3 / §1.5 / §1.7）。

---

## 1. MAJOR

### M-1 两张「R 阶段」表的表头改了、**表体行仍是 A/B/C/D/E**

**现象：** 表头写「R 阶段」，行首却是退役的旧阶段字母，且内容指向旧架构。

| 位置 | 表头 | 行 |
|---|---|---|
| `research-idea-pipeline/SKILL.md:199—207` | `\| R 阶段 \| 锚点的作用 \|` | `A`（检索边界）/ `B`（推导与筛选）/ `C`（贡献类型与实验，还写 `C4`）/ `D`（叙事资格）/ `E`（评审权重） |
| `research-idea-pipeline/SKILL.md:599—605` | `\| R 阶段 \| 派遣子代理 \|` | `A`（无）/ `B`（B5 审核）/ `C` / `D`（D6）/ `E`（八子代理） |

**证据（命令）：**

```bash
cd research-idea-pipeline
grep -nE '^\| ?[ABCDE] ?\|' SKILL.md
#   203—207：A/B/C/D/E 五行（表头在 201 行写的是「R 阶段」）
#   601—605：A/B/C/D/E 五行（表头在 599 行写的是「R 阶段」）
sed -n '199,207p;599,605p' SKILL.md
```

**为什么 spec §7 的 grep 拦不住：** 判据是 `Mode [ABCDE]|mode=[ABCDE]|mode-[abcde]-`；
这两处只有裸字母，`grep` 三种模式全不命中（下文 §5.5 有验证）。
**影响：** 执行者按「R 阶段」表找锚点约束与派遣名单时，读到的是 A—E，
而 `SKILL.md:104` 只接受 `phase=R<n>` —— 表与入口矛盾。
**建议修法：** ①行首改为 `R2 / R5`、`R3—R6`、`R8`、`R12`、`R7 / R10 / R13`；
②`C4` 改为 `R8 的贡献节`；③`D6` 改为 `R12 的 venue calibration`。

---

### M-2 入口的错误路径写反：把**新语法**当成「不再接受」的旧语法

**现象：** `SKILL.md:106` 写「**旧的 `phase=R0..R14` 不再接受。**」——
`phase=R0..R14` 恰恰是本轮新增的唯一合法入口（同文件 `:23` argument-hint、`:104` 解析规则 1）。
spec §6.2 的要求是「旧 `mode=` 不再接受，报错并给映射」。

**文件:行号 / 证据：**

```bash
sed -n '104,108p' SKILL.md
#   104: 1. 若 `$ARGUMENTS` 含 `phase=R0|R1|…|R14`…按上述顺序依次执行这些阶段。
#   106: 2. **旧的 `phase=R0..R14` 不再接受。** 收到时必须**报错**并给出映射提示
#   107:    （A→R2/R5、B→R3/R4/R6、C→R8、D→R12、E→R7/R10/R13），
grep -rn 'mode=' SKILL.md          # 0 命中 —— 真正该拒绝的字面量已不存在
```

**影响：** 照字面执行会把合法输入当非法拒绝；映射提示（A→R2/R5…）因此悬空，无处触发。
**建议修法：** `SKILL.md:106` 改为「**旧的 `mode=A|B|C|D|E` 不再接受**（该字面量已从入口移除，
见 `deprecated-terms.txt`）；收到时**报错**并给出映射提示」。

---

### M-3 三个 layer 各写一套「读/写 state」，且引入了 **R1 schema 里不存在的 4 个写入目标**

**现象：** `SKILL.md §0` 表、`research-state-policy.md §5` 表、各 `phase-*.md` 末尾读写段
三方对同一阶段的读写字段说法不同；其中 `claims.contract` / `narrative_view` / `reviews` /
`decision` **在 R1 权威 schema 里没有定义**（policy §3 的字段表、`research-state.template.json`、
`state_check.py` 都不认）。

**文件:行号：**

| 写入目标 | 出现处 | 权威 schema 是否定义 |
|---|---|---|
| `claims.contract` | `SKILL.md:73`、`references/phase-r8-evidence-contract.md:206`、`references/phase-r12-narrative.md:812` | ❌ policy §3.1 的 11 个字段里没有 `contract`；§3.10 的 `contract` 是 R0 的**顶层**对象 |
| `narrative_view` | `SKILL.md:77`、`references/phase-r12-narrative.md:813` | ❌ policy §5 R12 行写「默认**零写入**」 |
| `reviews` | `SKILL.md:78`、`references/phase-r7-r10-r13-assurance-repair-review.md:379` | ❌ policy §5 R13 行写的是 `failures[]` / `experiments[].unexpected` / `assurance[]` |
| `decision` | `SKILL.md:79`、`SKILL.md:762` | ❌ policy §5 R14 行写的是 `repairs[].closure` / `claims[].status` / `uncertainties[].status` / `hypotheses[].status` |

**直接违反 policy 自己的禁令：**
`references/research-state-policy.md:129—130`：「**未在本节出现的字段 = 未定义字段**，
**不得**自行添加。确实需要新字段时，**必须**先报 Lead 改 spec」。

**三方读写对照（✗ = 三方不一致）：**

| 阶段 | SKILL §0（`:65—79`） | policy §5（`:356—367`） | phase 文件末尾 | 判定 |
|---|---|---|---|---|
| R0 | 写 `contract` | 写 `contract` | 写 `contract`（`phase-r0:74—79`） | ✅ |
| R2 | 读 `literature`；写 `literature`+`assumptions` | 读 4 项；写 `literature`+`evidence`+`claims`+`uncertainties` | 读 2 项；写 `literature`+`assumptions`（`phase-r2-r5:213—214`） | ✗（policy 独异） |
| R3 | 读 3 项；写 `hypotheses` | 读 4 项；写 `hypotheses`+`assumptions`+`uncertainties` | 读 3 项；写 `hypotheses`（`phase-r3-r6:313—314`） | ✗（policy 独异） |
| R6 | 读 `hypotheses`；写 `hypotheses` | 读 3 项；写 status/EIG/`failures`/`uncertainties` | 无独立 R6 段 | ✗ |
| R7 | 读 `claims`+`evidence`；写 `assurance` | 读 4 项；写 `assurance`+`failures`+`uncertainties` | 读 4 项（含 `experiments`）；写 `assurance`+**`reviews[]`** | ✗ |
| R8 | 读 `claims`+`uncertainties`；写 **`claims.contract`** | 读 4 项；写 `evidence`+`claims.supporting/refuting/scope`+`uncertainties` | 读 3 项；写 **`claims[].contract`**+`uncertainties` | ✗ |
| R9 | 读 2 项；写 `experiments` | 读 3 项；写 `experiments`+`failures`+`assurance` | 读 3 项（含 `hypotheses`）；写 `experiments` | ✗（三种读法） |
| R10 | 读全部；写 3 项 | 读全 state+artifact；写 6 类 | 读 4 项；写 4 项（`phase-r9-r11:192`） | ✗ |
| R11 | 读 `experiments`；写全部 | 读全 state；写归并全 state | 读 `experiments`；写 4 项（`:193`） | ✗（policy 独异） |
| R12 | 读 2 项；写 **`narrative_view`** | 读 5 项；写「零写入，仅 `uncertainties`」 | 读 4 项；写 **`narrative_view`** | ✗（写口径互斥） |
| R13 | 读全部；写 **`reviews`** | 读全 state+artifact；写 3 类 | 并入 R7 段 | ✗ |
| R14 | 读全部；写 **`decision`** | 读全 state+未闭环；写 4 类 | 无 R14 段 | ✗ |

**证据（命令）：**

```bash
cd research-idea-pipeline
python3 - <<'PY'   # 三方提取见 §5.4；此处给核心对照
PY
sed -n '63,79p' SKILL.md                      # SKILL §0 读写列
sed -n '354,367p' references/research-state-policy.md   # policy §5
grep -n '^| 读 |\|^| 写 |\|^| \*\*R9\*\*\|^| \*\*R10\*\*\|^| \*\*R11\*\*' \
  references/phase-*.md
grep -rn 'claims\[\]\.contract\|narrative_view\|`reviews\[\]`\|`decision`' --include=*.md .
```

**建议修法（需 Lead 裁决，二选一）：**
①**以 policy 为准**：删掉 `claims.contract`/`narrative_view`/`reviews`/`decision`，
SKILL §0 与 3 个 phase 文件的读写列改为 policy §5 的字段；
②**以 spec 为准扩 schema**：在 policy §3 增加对应字段定义（含 `claims[].contract`），
并同步 `research-state.template.json` 与 `state_check.py`，同时在 spec §9 记一行。
无论哪种，都要把 12 个阶段的读写列**逐行对齐**后再收工。

---

### M-4 `research-state-policy.md §5` 的「对应文件」列有 **3 个文件名不存在**

**现象：** policy §5 表最后一列自称「取自 spec §3 的文件地图」，但 3 个名字与 spec §3 不符，
其中 5 行指向不存在的文件。

| policy 行 | 写的文件 | 实际文件 | 存在？ |
|---|---|---|---|
| `:357` R2 | `phase-r2-field-mapping.md` | `phase-r2-r5-field-mapping-retrieval.md` | ❌ |
| `:360` R7 / `:361` R8 | `phase-r7-r8-assurance-contract.md` | `phase-r7-r10-r13-assurance-repair-review.md` + `phase-r8-evidence-contract.md` | ❌ |
| `:365` R12 / `:366` R13 / `:367` R14 | `phase-r12-r14-narrative-review-decision.md` | `phase-r12-narrative.md` | ❌ |

**证据（命令）：**

```bash
cd research-idea-pipeline/references
for f in phase-r2-field-mapping.md phase-r7-r8-assurance-contract.md \
         phase-r12-r14-narrative-review-decision.md; do
  [ -f "$f" ] && echo "EXISTS $f" || echo "MISSING $f"; done
#   MISSING ×3
grep -oE 'phase-[a-z0-9-]+\.md' ../../../research-idea-pipeline-dev/docs/r-architecture-wave1-spec.md | sort -u
#   phase-r0-contract.md / phase-r12-narrative.md / phase-r2-r5-field-mapping-retrieval.md /
#   phase-r3-r6-discovery.md / phase-r7-r10-r13-assurance-repair-review.md /
#   phase-r8-evidence-contract.md / phase-r9-r11-experiment-loop.md
```

**建议修法：** 5 行改为 spec §3 的实际文件名（R7 与 R8 各指自己的文件）。
**同时建议**在 policy §5 表下补一句：R4 / R5 不单独列行（该文件 `:350` 已有此说明 ✅）。

---

### M-5 旧机器状态路径在三处仍是「现行写法」，与 R1 的常驻路径互斥

**现象：** R1 的落盘契约是**单份常驻** `.research-idea-pipeline/<route>/research-state.json`
（policy §6:391、SKILL §5:768—769 并声明旧口径作废），但另外三处仍把
**旧的按阶段切分路径**写成现行规则。

| 位置 | 原文 | 冲突对象 |
|---|---|---|
| `research-idea-pipeline/SKILL.md:431` | 落盘三档表「机器状态」行 = `.research-idea-pipeline/state-*.json` | policy §6:391 |
| `research-idea-pipeline/references/project-layout.md:61` | `├── state-<mode>-<ts>.json   # Mode 间传递` | SKILL §5:769 |
| `research-idea-pipeline/references/project-layout.md:529` | 落盘职责表「机器状态」行 = `.research-idea-pipeline/state-<mode>-<ts>.json` | policy §6:391 |

**证据（命令）：**

```bash
cd research-idea-pipeline
sed -n '431p' SKILL.md
sed -n '61p;529p' references/project-layout.md
sed -n '768,769p' SKILL.md      # 「旧的 state-<mode>-<ts>.json 口径已作废」
sed -n '391p' references/research-state-policy.md
#   policy §6 明写该文件是「落盘三档」的接口权威 —— 权威自己指向了被作废的路径
```

**影响：** 执行者按 SKILL §1.4 或 project-layout §6 写状态，会写出被 policy 判为作废的
`state-*.json` 分片，R1「常驻对象」在文件层不成立。
**建议修法：** 三处统一为 `.research-idea-pipeline/<route>/research-state.json`（就地覆盖）；
project-layout §6 的「落盘三档」表与 §1 目录树一并改（project-layout 在 spec §3 的 UPDATE 清单里）。

---

### M-6 被删 schema 的键 `next_mode_suggestion` 仍在 **14 处**（含 SKILL 自检清单）

**现象：** `templates/state.template.json` 已删除，但它的字段 `next_mode_suggestion`
仍被 SKILL §6 自检项与 5 个 phase 文件、3 个示例要求输出；phase 文件还用它携带
**已退役的 A—E 字母**（`"C"` / `"D"` / `"E"`）。新 schema
（`research-state.template.json`）里没有这个键。

**文件:行号（14 处）：**

```bash
cd research-idea-pipeline
grep -rn 'next_mode_suggestion' --include=*.md .
#   SKILL.md:866                                   ← §6 执行自检清单
#   references/phase-r2-r5-field-mapping-retrieval.md:203
#   references/phase-r3-r6-discovery.md:261, :303
#   references/phase-r8-evidence-contract.md:176, :195
#   references/phase-r7-r10-r13-assurance-repair-review.md:321, :368
#   references/phase-r12-narrative.md:791
#   examples/example-d-narrative.md:468 / example-b-to-c-d-e.md:40,68,140 / example-followup-review.md:60
```

**影响：** spec §7 要求「全仓不再引用已删文件（`state.template.json`）」，此处引用的是
它的 schema 键；且 `phase-r8:176` 的 `next_mode_suggestion: "D"` 会让执行者回到字母入口。
**建议修法：** 全部删除或改为新 schema 的 `open_questions` / 下一阶段建议字段；
phase 文件改为「下一步：R12」「下一步：R7/R10/R13」这类阶段号建议。
若确实需要该键，则应在 policy §3 与模板中定义它（否则违反 policy §3 通用规则 3）。

---

### M-7 文档 frontmatter 的 `mode:` 字段枚举**整套保留 A|B|C|D|E**

**现象：** `project-layout.md` 的 frontmatter schema、类型表、目录树、示例都仍以
`A|B|C|D|E` 为 `mode` 取值；spec §1 硬规则 2 已宣布字母 A—E 退役，spec §3 又把
`project-layout.md` 列入 UPDATE（`Mode X → R<n>`）。

**文件:行号：**

| 位置 | 原文 |
|---|---|
| `references/project-layout.md:302` | `mode: C                     # A \| B \| C \| D \| E —— 产出该文档的 Mode` |
| `references/project-layout.md:111` | 类型表列头 `产出 Mode` |
| `references/project-layout.md:114—116` | 行值 `A` / `B` / `C` |
| `references/project-layout.md:61`、`:529` | `Mode 间传递`（另见 M-5） |
| `references/project-layout.md:414—420` | INDEX 示例表 `Mode` 列全是 `A/B/C/D/E` |
| `examples/example-project-layout.md:92` | `mode: C                 # A \| B \| C \| D \| E` |
| `examples/example-project-layout.md:131—135` | 文档表 `B/C/D/E` |

**证据（命令）：**

```bash
cd research-idea-pipeline
grep -nE 'mode: [A-E]|\| [ABCDE] \|' references/project-layout.md examples/example-project-layout.md
grep -rn 'mode:' --include=*.md . | head
```

**影响：** 每份落盘文档的 `mode` 字段会继续写退役字母；下游脚本按 `mode` 索引时
与 `phase=R<n>` 入口脱节（A4 类「规则 → 字段 → 枚举 → 模板 → 示例」五处不同步）。
**建议修法（需 Lead 先定字段语义）：** 把 frontmatter 的 `mode` 改为
`phase: R8`（单值）或 `phases: [R2, R8]`，并同步 `project-layout §2.1/§3/§4`、
`examples/example-project-layout.md`、`templates/INDEX*.md`。
**spec §3 只写了「`Mode X` → `R<n>`」没定义新字段名，建议先补 spec 再改。**

---

### M-8 R14 决策枚举跨层不一致：`archive|submit` vs `kill`

**现象：** spec 与 policy 的双循环图写 `continue | pivot | kill`，
SKILL 两处写 `continue | pivot | archive | submit`。

| 位置 | 原文 |
|---|---|
| `docs/r-architecture-wave1-spec.md:36` | `回 R3 / R9（continue \| pivot \| kill）` |
| `references/research-state-policy.md:40` | `回 R3 / R9（continue \| pivot \| kill）` |
| **`SKILL.md:60`** | `R14 决策（continue \| pivot \| archive \| submit）` |
| **`SKILL.md:762`** | `- **R14：** continue \| pivot \| archive \| submit，并回写 decision。` |

**证据（命令）：**

```bash
cd research-idea-pipeline
grep -rn 'continue | pivot' SKILL.md references/research-state-policy.md ../docs/r-architecture-wave1-spec.md
```

**影响：** 冻结枚举跨层漂移；且 `SKILL.md:762` 的「回写 `decision`」与 policy §5 R14
的写回集也不一致（见 M-3）。
**建议修法：** 以 spec 为准统一为 `continue | pivot | kill`（若确要 `archive|submit`，
先改 spec §1 与 policy §1 的图，再同步 SKILL 两处）。

---

## 2. MINOR

| # | 现象 | 文件:行号 | 证据（命令） | 建议修法 |
|---|---|---|---|---|
| m-1 | §1 声明「以下**五条**是硬约束」，实际有 §1.1—§1.6 **六**小节（本轮新增 §1.6）。SKILL §8 B2 自己规定「标题里的"N 条"必须与该节实际条目数一致」 | `SKILL.md:255`；小节 `:257/:313/:341/:365/:452/:525` | `grep -cE '^### 1\.[0-9]' SKILL.md` → 6 | 改成「以下六条」 |
| m-2 | 混合残留：新阶段号与退役字母同时出现在同一句（作用域/表述），读者无法解析「C / E」指什么 | `SKILL.md:565`（`B/C/E 用`）、`:812—813`（`仅 R3—R6 / C / E`；`R12 的 D6`）、`:588`（`B→C→D→E 串联`）、`claim-first-policy.md:71`（`R3—R6 / C / E 为 P1`）、`claim-first-policy.md:307`（`§0.1 的 D 行`）、`venue-standards.md:632`（`R3—R6/C/E 会议审稿人`）、`roles.md:15`（`R3—R6 / C / E`） | `grep -rn ' / C / E\|B/C/E\|C / E' --include=*.md .` | 全部改为 `R3—R6 / R8 / R7·R10·R13` |
| m-3 | 单字母指代旧阶段的正文句 | `SKILL.md:618`（`D 已无反向维度`）、`:725`（`**E 不是链条终点**`）、`:906`（`如 D 的维度向量规模、E 的八子代理分工`）、`:907—909`（`E 与 D 同样使用…与 D 的极性错误同类`） | `grep -nE '（D \|\*\*E \|D 的\|E 的' SKILL.md` | 改为 `R12` / `R7·R10·R13` |
| m-4 | 链接**标签**仍写旧文件名（URL 已指向新 phase 文件）约 25 处；spec §7 的 `mode-[abcde]-` 模式抓不到（标签是 `mode-b` 无尾连字符） | `SKILL.md:493/609/610/970`、`roles.md:194/298/322/325/326/498/499/501`、`scoring-policy.md:15`、`literature-policy.md:75`、`narrative-patterns.md:11/38/40/77/213/267/331`、`phase-r2-r5:148/151`、`phase-r7:11`、`phase-r8:41/44` | `grep -rnE '\[mode-[abcde]\]' --include=*.md .` | 标签改为 `R12` / `R3—R6` / `R8` / `R7·R10·R13`（保留 `phase-r2-r5:216` 的「旧 `mode-a` 迁移而来」历史说明） |
| m-5 | 「Mode」作为架构术语全仓仍在用（`所有 Mode`、`本 Mode`、`产出 Mode`…），spec §1 已把 A—E 架构整体作废 | `roles.md:3/5/255/497/500`、`scoring-policy.md:12/17/51/53`、`claim-first-policy.md:16/48`、`phase-r12-narrative.md:3/8/34/49/129/295/552/614/680`、`project-layout.md:3/189/263/267—268`、`evidence-policy.md:1/4`、`venue-standards.md:275` | `grep -rnw 'Mode' --include=*.md . \| wc -l` | 统一改为「R 阶段」；`Mode 字母 A/B/C/D/E 无关` 这类**消歧注**可保留 |
| m-6 | `research-state-policy.md §3.10` 被排在 **§6 之后**（文件末尾），与 §6 的「节号 §1—§6 冻结、按序」结构冲突 | `references/research-state-policy.md:405—421`（§6 结束于 `:403`） | `grep -nE '^#{2,3} ' references/research-state-policy.md \| tail -5` | 把 §3.10 移到 §3.9 之后；或改名为 §7 并更新引用点（本次验收已能解析 `§3.10`，不影响断链） |
| m-7 | 机械闸门未覆盖两条**结构性硬规则**：`X2` 不得承担 claim 判别（spec §2.2）、失败实验必须双写 `failures[]`（spec §4）。实测两者都能 exit 0 | spec §2.2（`:126—129`）、spec §4（`:195`）；实现 `scripts/state_check.py:113—125`（只有 V1—V10） | 见 §5.6 场景 A/B：自建 fixture 均 **exit 0** | 加 V11（`stage=X2` ⇒ `claim_targeted` 不得非空/不得有 `result`）与 V12（`status=failed` ⇒ 必须有 `failures[]` 条目 `referenced_by` 含该 `X`）；若本轮不加，应在 spec §8 登记 Wave 2 |
| m-8 | `Planned` 进 `supporting_evidence` 不被 V5 拦（V5 只否决 `Hypothesized`/`Unknown`），但 claim-first-policy §3 硬规则 3 把引用 `Planned` 定为「证据夸大，直接触发 `G4`」 | `references/research-state-policy.md:337—339`（边界 2 已**声明**该差）、`claim-first-policy.md:157—158`、`scripts/state_check.py:99—100` | 见 §5.6 场景 D：exit 0 | 二选一：V5 扩到 `Planned`；或在 policy §3.2 明确「`Planned` 可进 `supporting_evidence`，但措辞只能「待核实」」 |
| m-9 | 新机械闸门未登记进 SKILL §8 D（该节自己写「新规则若带机械闸门，也要挂进本节」） | `SKILL.md:999—1029`（D 节：refs_index / unittest / deprecated / linter）；对比 `:583` 已登记 `state_check.py` | `sed -n '999,1029p' SKILL.md \| grep -n 'state_check'` → 无 | 在 §8 D 第 3 项后补：`python3 scripts/state_check.py --check templates/research-state.template.json`（模板必须 exit 0） |

---

## 3. NIT

| # | 现象 | 文件:行号 | 证据 | 建议 |
|---|---|---|---|---|
| n-1 | 模板 `_usage` 说「字面量 `TBD` 只有两个合法位置」，模板自身却把 `code_commit` 写成 `"TBD"`（2 处） | `templates/research-state.template.json:3`（声明）、`:141`、`:158` | `grep -n '"TBD"' templates/research-state.template.json` | 要么把 `code_commit` 也列入合法位置，要么改成 `待补（示例占位）` |
| n-2 | `primary_anchor` 的模板取值是整串枚举（`performance \| theory \| …`），不是单值；与「英文枚举原样、单值」读起来冲突（其他字段同样是占位风格，故仅提示） | `templates/research-state.template.json:6`；policy §3.10 未声明为占位 | `sed -n '4,11p' templates/research-state.template.json` | 注释里标「示例占位：填一个值」 |
| n-3 | 历史注释里的旧文件名（`曾漏 mode-a 的 A2 标题`）——属追溯历史，spec 允许改写但未强制 | `SKILL.md:997` | `sed -n '995,998p' SKILL.md` | 可改为「曾漏旧文献阶段的 A2 标题」 |
| n-4 | README 的状态树注释仍写「键 = A—E」（README 属已知未重写项，仅登记） | `README.md:51` | `sed -n '51p' README.md` | 随 README 重写一起改 |
| n-5 | `phase-r12-narrative.md` 仍以「本 Mode」自称（约 10 处），与文件改名后的 R12 身份不一致 | `references/phase-r12-narrative.md:3/8/34/49/129/295/552/614/680` | `grep -n '本 Mode' references/phase-r12-narrative.md` | 改「本阶段（R12）」 |

---

## 4. spec §7 验收标准逐条判定

| # | 验收项（spec §7） | 判定 | 证据 |
|---|---|---|---|
| 1 | `state_check.py --selftest` 通过；`test_state_check.py` ≥14 用例全过；V1—V10 每条至少一个反例 | **达成** | `--selftest` → 31 ok / 0 FAIL / exit 0；`grep -c 'def test_' scripts/test_state_check.py` → **48**；V1—V10 逐条有 `test_v*`；我自建 16 个独立 fixture 全部 exit 3 且报出正确规则号（§5.3） |
| 2 | `research-state.template.json` 通过 `state_check.py` | **达成** | `python3 scripts/state_check.py templates/research-state.template.json` → `[ok] 0 处硬违规…` exit 0 |
| 3 | 全仓 `grep -rn 'Mode [ABCDE]\|mode=[ABCDE]\|mode-[abcde]-'` → 0 命中 | **字面达成、实质未达成** | 该 grep **exit 1（0 命中）**；但裸字母表行（M-1）、`mode-x` 链接标签（m-4）、"Mode" 术语（m-5）全在其盲区 |
| 4 | 全仓不再引用已删文件（`mode-a…e`、`state.template.json`） | **部分达成** | 旧文件名 `mode-*.md`：0；被删模板名：0；旧 **spec** 名 `mode-d-claim-first-spec`：0 ✅。但被删 **schema 键** `next_mode_suggestion` 仍 14 处（M-6）、旧**状态路径**仍 3 处（M-5）、frontmatter `mode` 枚举仍 A—E（M-7） |
| 5 | `deprecated-terms.txt` 追加：`mode=A\|B\|C\|D\|E` 类写法、`state.template.json` | **达成** | 文件末尾新增 3 条 `mode=[ABCDE]` / `Mode [ABCDE]` / `templates/state\.template\.json`；扫描 0 命中（§5.5） |
| 6 | 相对链接 0 断链；`§` 引用可解析；JSON 合法；unittest 全过 | **达成** | 链接 401/0 断链；phase 文件 § 引用 43 处 0 断链；新文件 § 引用 0 断链；JSON 全绿 + md 内 10 个 ```json 围栏合法；`unittest discover` → **104 tests OK** |
| 7 | `examples/` + `templates/` 默认档 linter 硬违规 0 | **达成** | 9 个文件逐个 rc=0；`--selftest` exit 0 |
| 8 | 每个 phase 文件写明 输入/动作/产物/**写回哪些字段** | **达成（内容有冲突）** | 7 个文件均有「读 / 写 World Model」段；但 R8/R7/R12 的写回字段与 R1 权威冲突（M-3） |
| 9 | R10 处置/关闭枚举逐字一致；V10 能拦「只写 flaw 不写 disposition」 | **达成** | 5+2 枚举在 `phase-r9-r11:94/108`、`policy:275/277`、`SKILL:533/535`、`template`、`state_check.py:103—106` 逐字一致；自建 fixture `{"flaw":"only flaw"}` → exit 3 + `V10` |
| 10 | 独立 verifier 对抗验收通过 | **未通过（本报告）** | 见 §0 / §1 |

---

## 5. 必做项复核（方法 + 命令 + 结果）

### 5.1 复核范围与只读纪律

- 只写 `docs/verify-r-wave1.md`；未改任何被审文件；未 `git commit`。
- 复核对象：15 个改动文件 + 3 个新文件 + 1 个被删文件 + 2 个新脚本（`wc -l` 全量读过核心件）。

### 5.2 内容不丢检查（重点项）——**通过**

**方法：** 对 5 组 `git mv` 文件，用 `git show f8cefdc:<旧文件>` 取旧文，
逐项比对 ①`##` 标题集合 ②`###` 标题集合 ③**段落级相似度**（`difflib.SequenceMatcher`，
低于 0.80 报警）④代码跨度/`§`引用/命令 token 集合 ⑤字符数增量。

| 旧 → 新 | 字符数 | `##` | `###` | 段落低相似 | 丢失 token |
|---|---|---|---|---|---|
| mode-a → phase-r2-r5 | 6391 → 7888 (+1497) | 8 → 10 | 3 → 6 | **0** | **0** |
| mode-b → phase-r3-r6 | 8378 → 10358 (+1980) | 10 → 12 | 5 → 8 | **1**（纯改名） | **0** |
| mode-c → phase-r8 | 5640 → 6376 (+736) | 8 → 10 | 1 → 1 | **0** | **0** |
| mode-d → phase-r12 | 28528 → 29046 (+518) | 13 → 15 | 15 → 15 | **0** | **0** |
| mode-e → phase-r7-r10-r13 | 10870 → 12239 (+1369) | 10 → 12 | 6 → 9 | **1**（纯改名） | **0** |

**独立确认「只有两处」**：全部标题增删中，**删除项只有 2 个**，且都是改名造成的假阳性：

```bash
git show f8cefdc:research-idea-pipeline/references/mode-b-idea-discovery.md | grep -n '^## B[01]'
#   ## B0. 与 Mode E 的分工（必须先明确，避免重复劳动）
#   ## B1. 基础文献调研（必须走 Mode A 或等价的脚本调用）
grep -n '^## B[01]' research-idea-pipeline/references/phase-r3-r6-discovery.md
#   ## B0. 与 R7 / R10 / R13 的分工（必须先明确，避免重复劳动）
#   ## B1. 基础文献调研（必须走 R2 / R5 或等价的脚本调用）
```

两处段落级低相似也**只有**改名差异（其余全部 ≥0.80）：
`**这是 Mode B 与 Mode E 的分界点…**` → `**这是 R3—R6 与 R7 / R10 / R13 的分界点…**`（sim 0.71）；
`**可接 Mode C，也可接上一次 Mode E 继续复核。**` → `**可接 R8，也可接上一次 R7 / R10 / R13 继续复核。**`（sim 0.80）。
**新增**全是规格要求的新骨架（field grammar / occupancy map / R5 共演化检索 / R3 双轨 / R4 种群 /
R6 进化 / Claim Contract / 修复门 / artifact 审计 / 读写段）。
**结论：迁移未吞节、未吞段、未吞枚举与命令。**脚本：`/tmp/verify/mvcheck.py`、`paracheck.py`、`tokcheck.py`。

### 5.3 V1—V10 独立反例（**不看作者测试**，自建）

**方法：** 自建一份合规基线（8 类对象 + assurance + repairs，共 12 条记录），
逐条注入违规 → 跑 CLI `--json` → 断言 `exit==3` 且 `counts` 命中该规则号。

```
基线（期望 0）                                          exit=0
V1  falsifier="   "                                    exit=3  rules=['V1']
V2  refuting_evidence=["E99"]                          exit=3  rules=['V2']
V3  无 E 却 supported                                   exit=3  rules=['V3']
V3b 有 E 却 ungrounded                                  exit=3  rules=['V3']
V4  F1 无人 known_flaws 引用                            exit=3  rules=['V4']
V5  epistemic_status="observed"（大小写）              exit=3  rules=['V5']
V5b supporting_evidence 收 Hypothesized 的 E4          exit=3  rules=['V5']
V6  niche="  "                                         exit=3  rules=['V6']
V7  cheapest_discriminating_test="X404"                exit=3  rules=['V7']
V8  parent="X404"                                      exit=3  rules=['V8']
V8b parent 自环 X2→X2                                   exit=3  rules=['V8']
V9  kill_condition=""                                  exit=3  rules=['V9']
V9b discriminating_test="X404"                          exit=3  rules=['V9']
V10 repairs=[{"flaw":"only flaw"}]                     exit=3  rules=['V10']
V10b disposition="fix"（小写）                          exit=3  rules=['V10']
V10c closure="DEFERRED"                                exit=3  rules=['V10']
```

**边界与容错（与 policy §4 逐条对齐）：** `tbd` → 3 ✅；`TBD 待定` → 3 ✅；
`"Observed | Supported"` 枚举提示串 → 3 ✅；`"E9 (文献)"` 带修饰引用 → 3 ✅；
`TBD` 精确字面量 → 0 ✅；缺 `assurance`/`repairs` 键 → 0 ✅；`world_model` 包装 → 0 ✅。

**exit 4（环境不满足）实测 6 种：**

```
缺文件 exit=4 (missing-file)      非法 JSON exit=4 (invalid-json)
根节点非对象 exit=4 (structure)    八类数组全缺失 exit=4 (structure)
数组字段非 list exit=4 (structure) 数组条目非对象 exit=4 (structure)
+ 目录路径 / 空文件由作者测试覆盖（test_directory_is_not_a_state_file / test_empty_file）
```

**注：** `claims` 单键缺失（其余七类在）→ exit 0。这与 policy §4 实现说明 3
（「**八类数组全部缺失** → 4」）一致，判**非缺陷**，仅记录口径。
脚本：`/tmp/verify/vfix/gen.py`、`env.py`。

### 5.4 跨层一致性（policy §5 vs SKILL §0 vs 6 个 phase 文件）

完整对照表见 **M-3**。要点：
- **只有 R0 三方一致**；
- R2 / R3 / R11：SKILL 与 phase 一致，policy 更宽 → 以谁为准未定；
- R6—R10、R12—R14：三方互不一致；
- 4 个写入目标（`claims.contract` / `narrative_view` / `reviews` / `decision`）在 R1 schema 中不存在。

**`contract` 字段三处一致性（本项要求的第二半）——通过 ✅：**

| 来源 | 字段 |
|---|---|
| `references/research-state-policy.md:409—416` | `goal` / `primary_anchor` / `constraints` / `resources` / `provisional_anchor_rationale` / `out_of_scope` |
| `references/phase-r0-contract.md:38—39` | 同上 6 键（同一顺序） |
| `templates/research-state.template.json:4—11` | 同上 6 键 |

三处的必填性也一致（`goal`/`primary_anchor`/`provisional_anchor_rationale`/`out_of_scope` 必填，
`constraints`/`resources` 可选）✅。**裁决一致性也通过 ✅**：spec §5:212—215、
policy §5:356（R0 行）、policy §3.10:421、`phase-r0-contract.md:6—7` 五处都写
「R0 只写 `contract`；`assurance[]` 由 R7 写」。

### 5.5 新枚举全仓 grep

| 枚举 | 命中分布 | 结论 |
|---|---|---|
| `REPAIR_CLAIM` / `RUN_TEST` / `FIX_IMPLEMENTATION` / `NARROW_SCOPE` / `KILL_BRANCH` | `phase-r9-r11` / `policy` / `SKILL` / `state_check.py` / `template`（部分） / `test_state_check.py`（部分） | ✅ 无自创变体（`REPAIR-CLAIM`/`repair_claim`/`FIX_IMPL` 0 命中；`PARTIAL` 只出现在**禁止句**里） |
| `RESOLVED` / `ACCEPTED_LIMITATION` | 同上 5 处 | ✅ 一致 |
| `X1`—`X6`（`stage`） | `grep -rnE '"stage"\s*:\s*"X[0-9]+"'` → 只有 `X1`/`X3` | ✅ 无越界 stage |
| `RS1` / `RS2` | `phase-r9-r11:135/136/138/141/205`、`SKILL.md:549—550` | ✅ **无 `R1`/`R2` 被误用作 regime-shift 条件**；两处都带显式命名警告 |
| ID 前缀 `C/E/AS/H/X/LIT/F/U` | `LIT` 出现于 policy/template/phase；`L1/L2/L3` 仅作两个既有等级 | ✅ 未见 `L<n>`/`Lit<n>` 冒充文献节点 |
| `epistemic_status` 五值 | 全仓仅五值；小写 `"Verified"` 只出现在**测试的非法值 fixture** | ✅ 无第六值 |

### 5.6 对抗性场景（5 个）

| # | 场景 | 结果 | 证据 |
|---|---|---|---|
| A | **R0 写了 `assurance[]`** | 文档层：禁止且四处一致（policy §5:356、§3.10:421、phase-r0:6、spec §5）✅；机械层：**无法检出**（validator 不知道写入者）→ spec §5 的裁决本就是「靠文档纪律」，判**设计内**，不记缺陷 | `grep -rn 'R0 只写\|不由 R0 写' references/ SKILL.md` |
| B | **`X2` 被用来做 claim 判别** | **可绕过**：自建 fixture `stage=X2, claim_targeted=[C1], result=...` → **exit 0**（spec §2.2 明文禁止） | §5.6 脚本；`state_check.py:113—125` 只有 V1—V10 → m-7 |
| C | **失败实验只在 `experiments[]`，没进 `failures[]`** | **可绕过**：`status:"failed"` 且无对应 `F` → **exit 0**（spec §4 要求双写） | 同上 → m-7 |
| D | **`Planned` 条目进 `supporting_evidence`** | **可绕过**：`C.supporting_evidence=["E3"]`（E3 `Planned`）→ **exit 0**（claim-first-policy §3 硬规则 3 判为 `G4` 夸大） | → m-8（policy §4 边界 2 已声明该差） |
| E | **旧状态路径 `.research-idea-pipeline/state-<ts>.json` 被继续使用** | **确实存在**：`SKILL.md:431` 与 `project-layout.md:61/529` 仍把它写成现行规则 | → M-5 |
| F | **SKILL §4 的 R 阶段顺序与实际双循环不符** | **属实**（已知未完成项）：`R2/R5 → R3—R6 → R8 → R12 → R7/R10/R13 → R0/R1 → R9/R10/R11 → R13/R14` | `grep -nE '^### .*—' SKILL.md`（`:655—762`） |

### 5.7 机械校验（自己跑）

| # | 项 | 命令 | 结果 |
|---|---|---|---|
| 1 | 相对链接（去围栏） | 自写 `/tmp/verify/links.py` | **401 条，0 断链** ✅ |
| 2 | 废弃词扫描（含新增 3 条） | spec §7 原命令 | **exit 1，0 命中** ✅ |
| 3 | `state.template.json` 旧名精确匹配 | `grep -rnE '(^\|[^-])state\.template\.json'` | **0 命中** ✅（另有 15 处是合法的 `research-state.template.json`） |
| 4 | JSON | `json.load` ×2 + md ```json 围栏 | 全部合法（10/10 围栏） ✅ |
| 5 | 索引 | `python3 scripts/refs_index.py --check` | exit 0 ✅ |
| 6 | 单测 | `python3 -m unittest discover -s scripts -p "test_*.py"` | **104 tests OK** ✅（含新 48） |
| 7 | `state_check` 自检/清单 | `--selftest` / `--list-rules` | exit 0；10 条规则 ✅ |
| 8 | 模板合规 | `state_check.py templates/research-state.template.json` | exit 0 ✅ |
| 9 | 受控中文 | `--selftest` + 9 个 examples/templates | 全绿 ✅ |
| 10 | `§D/§B/§C/§E` 前缀引用 | 自写解析器（含跨文件） | **43 处进 phase 文件 0 断链**；新文件 0 断链 ✅ |

---

## 6. 已知未完成项核对（**属实，不重复计为缺陷**）

| Lead 声明 | 核实 | 证据 |
|---|---|---|
| `README.md` 只做机械改名、未按 R 架构重写 | **属实** | `README.md:139—144` 仍是合并阶段行（`R2—R6`/`R7—R8`/`R12—R14`），与 SKILL §0 的 15 行不一致；`:51` 仍写「键 = A—E」；`:144` 用了 M-3 的 4 个未定义字段 |
| `templates/INDEX*.md` 只做机械改名 | **属实（且更干净）** | `templates/INDEX.md` / `INDEX.root.md` / `README.route.md` 已无 `Mode` 字面量（`grep -nE 'Mode\|mode: [A-E]' templates/*.md` → 0），但 §2.2 叙事追踪表仍是 claim-first 口径，未加 state / R 阶段列 |
| `SKILL.md §4` 小节顺序未按 R0→R14 | **属实** | `SKILL.md:655—762`：R2/R5 → R3—R6 → R8 → R12 → R7/R10/R13 → R0/R1 → R9/R10/R11 → R13/R14 |

---

## 7. 未覆盖项与验收限制

1. **未做外部事实核验**：spec 的「来源说明」已声明 Co-Scientist / FlowPIE / FunSearch 等
   由用户提供、未经仓库核实；本环境 `web_fetch`/`web_search` 不可用（域名解析到非公网 IP、
   search 401），故**未**尝试核实这些系统的设计归属。按 spec 的字面声明不构成缺陷。
2. **未评审 Wave 2 / Wave 3 骨架的内容正确性**：`phase-*` 里的 field grammar / QD archive /
   共演化检索 / artifact 审计骨架只核到「已写明、不冒充完成」；
   其科学内容属后续波次。
3. **未逐行评审 `scoring-policy.md` / `venue-standards.md` / `literature-policy.md` /
   `claim-first-policy.md` 的既有规则**（本轮只做改名与交叉引用），只核了它们的
   § 引用可解析性与 Mode/字母残留。
4. **`examples/*` 未按 R 架构重写**（spec §3 列为 UPDATE，但 Lead 未声明完成状态）：
   实测 `example-b-to-c-d-e.md`、`example-d-narrative.md`、`example-followup-review.md`
   仍以旧阶段口径与 `next_mode_suggestion` 组织（已并入 M-6 计数）。
5. 本报告未修改任何被审文件；未 `git commit` / `git push`。
   唯一写入：`docs/verify-r-wave1.md`。

---

## 8. 修复清单（按优先级）

| 优先级 | 动作 | 文件:行号 |
|---|---|---|
| 1 | 入口错误路径改回 `mode=A\|B\|C\|D\|E` | `SKILL.md:106` |
| 2 | 两张「R 阶段」表行改为 R 阶段号 | `SKILL.md:203—207`、`:601—605` |
| 3 | policy §5「对应文件」列改 3 个真实文件名 | `research-state-policy.md:357/360/361/365/366/367` |
| 4 | 统一读/写三方口径，处理 4 个未定义字段（需裁决） | `SKILL.md:63—79`、`research-state-policy.md:354—367`、`phase-r8:205—206`、`phase-r7:378—379`、`phase-r12:812—813` |
| 5 | 旧状态路径三处改为 `research-state.json` | `SKILL.md:431`、`project-layout.md:61/529` |
| 6 | 删/改 `next_mode_suggestion`（14 处） | `SKILL.md:866` + 5 个 phase 文件 + 3 个 examples |
| 7 | R14 决策枚举统一为 `continue\|pivot\|kill` | `SKILL.md:60/762`（或反向改 spec+policy） |
| 8 | frontmatter `mode` 字段改 R 阶段（需先定字段名） | `project-layout.md:111/114—116/302/414—420`、`example-project-layout.md:92/131—135` |
| 9 | MINOR m-1—m-9 | 见 §2 |
| 10 | NIT n-1—n-5 | 见 §3 |

**一句话总体结论：需修后交付** —— 新增件（validator / 模板 / policy / 两个新 phase 文件）
经独立 fixture 与模板自检验证可用，5 个 `git mv` 文件内容零丢失；
但改名只完成了「三种字面量清零」，仍有 **8 项 MAJOR**（2 张表未改、入口写反、
跨层读写三方互斥且含 4 个未定义字段、policy 指向 3 个不存在的文件、旧状态路径、
被删 schema 键、frontmatter 枚举、R14 枚举漂移），修完即可交付。

---

## 9. 增量复核（第二轮：修复验证）

**范围：** 只验证 Lead 本轮修复是否落地、三方读写口径是否一致、是否引入新矛盾，
以及 V11/V12 的建议编号与判据。不重跑第一轮的内容评审。
**快照：** 06:12 的文件状态（Lead 最后一笔编辑 06:10:25，其后无变动）。
命令默认在 `research-idea-pipeline/` 下执行。

### 9.1 逐条确认（8 MAJOR + 声称的 MINOR）

| # | Lead 声明 | 现值（文件:行号） | 判定 |
|---|---|---|---|
| M-1 | 两张表 A—E → R 阶段，并扫掉 project-layout/roles/INDEX*/example 同类残留 | `SKILL.md:202—207` = `R2 / R5`、`R3—R6`、`R8`、`R12`、`R7 / R10 / R13`；`SKILL.md:600—605` 同；`project-layout.md:531` 起落盘职责表首列已改 R 阶段；全仓 `^\| ?[ABCDE] ?\|` 仅剩 2 处**证据台账表头**（`project-layout.md:222`、`example-d-narrative.md:60` 的 `\| E \| 内容 \| …`），非阶段字母 | ✅ **达成** |
| M-2 | `SKILL.md:106` 改为旧 `mode=` 入口 | `SKILL.md:106`：「**旧的 `mode=` 参数入口不再接受**（旧 A—E 阶段字母已退役）。收到时**必须报错**并给出映射提示」，映射提示有对应对象；`deprecated-terms.txt:70` 登记 `mode=[ABCDE]` | ✅ **达成** |
| M-3 | 4 槽位补进模板 + policy §3.11 | 模板顶层新增 `contract`(:4)、`narrative_view`(:291)、`reviews`(:301)、`decision`(:309)，claim 下新增 `claims[].contract`(:31)；`research-state-policy.md:423` 新增 §3.11；模板 `state_check --check` 仍 exit 0 | ⚠️ **部分**：三方读写口径**未对齐**（§9.2）；policy §3 通用规则 3 未同步（§9.3a）；§3.11 与 §5 写集自相矛盾（§9.3b） |
| M-4 | policy §5 三个不存在文件名改为实际文件 | `:357` R2 → `phase-r2-r5-field-mapping-retrieval.md` ✅；`:360` R7 → `phase-r7-r10-r13-assurance-repair-review.md` ✅；`:365` R12 → `phase-r12-narrative.md` ✅；**`:361` R8 仍指 R7 的文件（应为 `phase-r8-evidence-contract.md`）**；**`:366` R13 指 `phase-r12-narrative.md`（应为 R7/R10/R13 文件）**；`:367` R14 同指 R12 文件（R14 无专属文件，需裁决写法） | ⚠️ **部分（R8 / R13 错配）** |
| M-5 | 旧状态路径三处改为单份常驻 | `SKILL.md:431` = `.research-idea-pipeline/<route>/research-state.json`；`project-layout.md:61`、`:529`、`:602` 同；`SKILL.md:769` 保留「旧的 `state-<mode>-<ts>.json` 口径已作废」的历史说明 | ✅ **达成** |
| M-6 | 14 处 `next_mode_suggestion` → `next_phase_suggestion`，取值改 R 阶段 | 14 处全部改名 ✅（`grep -rn 'next_mode_suggestion'` → 0）；取值 `"C"→"R8"`、`"D"→"R12"`、`"C \| E"→"R8 \| R7 / R10 / R13"` ✅；**但 3 处取值仍是 `"E"`**：`phase-r7-r10-r13-assurance-repair-review.md:321`、`phase-r8-evidence-contract.md:176`、`examples/example-followup-review.md:60` | ⚠️ **部分（3 处）** |
| M-7 | frontmatter `mode:` → `phase: R8` | `project-layout.md:302` = `phase: R8  # R0..R14 —— 产出该文档的阶段` ✅；`:268`、`:96` 字段名 ✅；5 个 phase 文件的 frontmatter 行 ✅（`phase-r2-r5:159`、`phase-r3-r6:249`、`phase-r8:161`、`phase-r7:293`、`phase-r12:697`）；`example-project-layout.md:92` ✅ **且其文档表值已改 R 阶段**（`:131—135`）；`templates/INDEX.md:57—65` 列头「阶段」+ 值 R 阶段 ✅。**但 `project-layout.md:114—119` 类型表与 `:414—420` INDEX 示例表的取值仍是 `A/B/C/D/E`**，列头 `:111`/`:411`/`:531` 与 `example-project-layout.md:129` 仍写「Mode」 | ⚠️ **部分（权威文件反而比示例旧）** |
| M-8 | R14 枚举统一为 `continue \| pivot \| archive \| submit` | `references/research-state-policy.md:40` 已改为 `archive \| submit`；`SKILL.md:60`/`:762` 本来就是；**但 `docs/r-architecture-wave1-spec.md:36` 仍是 `continue \| pivot \| kill`，spec §9 变更记录仍只有「初版」一行（mtime 05:35，本轮未动）** | ❌ **未达成（改在错误的一层）** |

**声称的 MINOR：**

| 项 | 现值 | 判定 |
|---|---|---|
| `SKILL §1`「五条」→「六条」 | `SKILL.md:255`：「以下**六条**是硬约束…」 | ✅ 达成 |
| 混合残留 `R3—R6 / C / E` 等 8 处 | `R3—R6 / C / E`、`R3—R6/C/E`、`R8/D`、`R2 / R5 / B`、`R3—R6—C` **全部 0 命中**；`SKILL.md:812—813` 已是「仅 R3—R6 / R8 / R7 / R10 / R13」；`venue-standards.md:72`/`:632`、`claim-first-policy.md:71` 已改。**但 `SKILL.md:323`「仍使用会议审稿人的 Mode（B / C / E）」与 `SKILL.md:565`「（**B/C/E 用**）」仍在** | ⚠️ 部分（2 处） |
| 链接标签 `[mode-b]` 等约 26 处 → phase 名 | SKILL 的 4 处已改（`:493`/`:609`/`:610` 已是 `[phase-r…]`）；**其余 22 处未改**：`roles.md`（8）、`narrative-patterns.md`（7）、`phase-r2-r5…md`（2）、`phase-r8…md`（2）、`scoring-policy.md`（1）、`literature-policy.md`（1）、`phase-r7-r10-r13…md`（1） | ❌ **未达成（22/26）** |

**命令：**

```bash
cd research-idea-pipeline
grep -rnE '\[mode-[abcde]\]' --include=*.md . | cut -d: -f1 | sort | uniq -c
grep -rn 'next_phase_suggestion' --include=*.md . | grep '"E"'
grep -nE '\| [ABCDE](（|\s*\|)' references/project-layout.md
grep -n 'continue | pivot' SKILL.md references/research-state-policy.md ../docs/r-architecture-wave1-spec.md
grep -nE '\| `phase-[a-z0-9-]+\.md` \|$' references/research-state-policy.md
```

### 9.2 三方读写口径现状（item 2）——**仍未一致：14 个阶段里只有 R0 三方相同**

`SKILL.md §0`（`:63—79`）与 `research-state-policy.md §5`（`:354—367`）**本轮一字未改**；
6 个 phase 文件的读写段也未改。具体差异（读 / 写分列）：

| 阶段 | SKILL §0 读 ｜ 写 | policy §5 读 ｜ 写 | phase 文件 读 ｜ 写 | 具体差异 |
|---|---|---|---|---|
| R0 | — ｜`contract` | 用户输入+INDEX+既有 state ｜`contract` | — ｜`contract` | ✅ 一致（仅 policy 多写了输入来源） |
| R2 | `literature` ｜`literature`、`assumptions` | `claims`、`assumptions`、`literature`、`uncertainties` ｜`literature`、`evidence`、`claims`、`uncertainties` | `literature`、`assumptions` ｜`literature`、`assumptions` | **读**：SKILL/phase 少 `claims`、`uncertainties`；**写**：policy 多 `evidence`、`claims`，SKILL/phase 多 `assumptions`（policy 把 `assumptions` 放在 R3 行） |
| R3 | `literature`、`assumptions`、`failures` ｜`hypotheses` | `claims`、`assumptions`、`literature`、`uncertainties` ｜`hypotheses`、`assumptions`、`uncertainties` | `literature`、`assumptions`、`failures` ｜`hypotheses` | **读**：`failures`（SKILL/phase）vs `claims`+`uncertainties`（policy），三方交集只有 2 项；**写**：policy 多 `assumptions`、`uncertainties` |
| R6 | `hypotheses` ｜`hypotheses` | `hypotheses`、`uncertainties`、`failures` ｜`hypotheses[].status`/EIG/`failures`/`uncertainties` | **无独立 R6 行**（只有合并段 `:313—314`） | 读少 2 项、写少 2 类；phase 缺行 |
| R7 | `claims`、`evidence` ｜`assurance` | `claims`、`evidence`、`hypotheses`、`assurance` ｜`assurance`、`failures`、`uncertainties` | `claims`、`evidence`、`hypotheses`、`experiments` ｜`assurance`、`reviews[]` | **读**：`experiments`（仅 phase）vs `assurance`（仅 policy）；**写**：三处各不同（policy 多 `failures`/`uncertainties`；phase 多 `reviews[]`） |
| R8 | `claims`、`uncertainties` ｜`claims.contract` | `claims`、`evidence`、`literature`、`assurance` ｜`evidence`、`claims[].supporting_evidence`/`refuting_evidence`/`scope`、`uncertainties` | `claims`、`evidence`、`uncertainties` ｜`claims[].contract`、`uncertainties` | **读**：三方只有 `claims` 共有；**写**：policy **不含** `claims[].contract`，SKILL/phase 不含 `evidence` 与 claim 的引用字段 → **互斥** |
| R9 | `uncertainties`、`claims` ｜`experiments` | `uncertainties`、`claims`、`evidence` ｜`experiments`、`failures`、`assurance[].discriminating_test` | `uncertainties`、`claims`、`hypotheses` ｜`experiments` | **读**：第 3 项三处各不同（无 / `evidence` / `hypotheses`）；**写**：policy 多 2 类 |
| R10 | 全部 ｜`repairs`、`claims`、`uncertainties` | 全 state + artifact ｜`repairs`、`claims[].status`/`scope`/`known_flaws`、`experiments[].status`、`uncertainties[].status`、`hypotheses[].status` | `claims`、`evidence`、`experiments`、`failures` ｜`repairs`、`claims[]`、`uncertainties[]`、必要时 `F<n>` | **读**：3 种；**写**：policy 多 `experiments[].status`、`hypotheses[].status` |
| R11 | `experiments` ｜全部 | 全 state ｜归并全 state | `experiments` ｜`evidence`、`claims`、`uncertainties`、`experiments` | **读**：SKILL/phase 只 1 项 vs policy 全 state；**写**：全部 vs 4 类 |
| R12 | `claims`、`evidence` ｜`narrative_view` | `claims`、`evidence`、`literature`、`assurance`、`uncertainties` ｜**默认零写入**（仅 `uncertainties`） | `claims`（含 `status`/`contract`）、`evidence`、`failures`、`uncertainties` ｜`narrative_view` | **写**：SKILL/phase 写 `narrative_view`，policy 说零写入 → **直接互斥**；**读**：3 种（policy 的 `literature`/`assurance`、phase 的 `failures` 互不覆盖） |
| R13 | 全部 ｜`reviews` | 全 state + artifact ｜`failures`、`experiments[].unexpected`/`interpretation`、`assurance` | 并入 R7 段（写 `assurance`、`reviews[]`） | **写**：三处各不同（`reviews` vs 3 类字段 vs `assurance`+`reviews[]`） |
| R14 | 全部 ｜`decision` | 全 state + 未闭环 ｜`repairs[].closure`、`claims[].status`、`uncertainties[].status`、`hypotheses[].status` | **无 R14 行** | **写**：`decision` vs 4 类字段；phase 缺行 |
| R4 / R5 | 有独立行（R4 写 `hypotheses.niche`；R5 写 `literature`） | policy `:350` 明确**不列行**（产出经 R6 落 `hypotheses`/`uncertainties`） | `phase-r2-r5` 读写段未区分 R5 | 说明口径不一致（policy 已解释；SKILL 未带同款说明） |

**小计：14 个阶段中 R0 三方一致；R2/R3/R6—R14 共 12 个阶段三方（或两方）不一致。**
**这是第一轮 M-3 的核心，本轮未处理。**

### 9.3 修复引入的新矛盾（item 3）

#### a. `policy §3 通用规则 3` 未随 §3.11 更正 → 同一文件内两条互斥规则

- `research-state-policy.md:129—130`（**仍在**）：「**未在本节出现的字段 = 未定义字段**，
  **不得**自行添加。确实需要新字段时，**必须**先报 Lead 改 spec，**不得**在本轮自行扩大字段表。」
- `research-state-policy.md:425—427`（新增）：「**⚠️ 更正：** 本节列出的槽位是 R 阶段的落盘目标，
  模板与 `state_check.py` 都承认它们。旧表述「不得自加字段」的**准确含义是**：
  **新加字段必须同时改本表、模板与 `state_check.py`**」
- **问题：** 更正只写在 §3.11（位于 §6 之后），**操作性的 §3 通用规则 3 原文未改**。
  执行者读到 §3 时会拒绝写 `claims[].contract`；读到文件末尾才知道被更正过。
- **建议：** 在 §3 通用规则 3 末尾加指向 §3.11 的一句（一行），或把 §3.11 移到 §3.9 之后。

#### b. `policy §3.11` 的「谁写」与 `policy §5` 的写集**互相矛盾**（同一权威文件内）

| 槽位 | §3.11 说谁写（`:429—437`） | §5 对应行的写集（`:361/365/366/367`） | 冲突 |
|---|---|---|---|
| `claims[].contract` | R8 | R8 写 `evidence[]` + `claims[].supporting_evidence`/`refuting_evidence`/`scope` + `uncertainties[]` —— **不含 `contract`** | ✅ 冲突 |
| `narrative_view` | R12 | R12「默认**零写入**」 | ✅ 冲突 |
| `reviews` | R7 / R13 | R7 写 `assurance`/`failures`/`uncertainties`；R13 写 `failures`/`experiments`/`assurance` —— **都不含 `reviews`** | ✅ 冲突 |
| `decision` | R14 | R14 写 `repairs[].closure`/`claims[].status`/`uncertainties[].status`/`hypotheses[].status` —— **不含 `decision`** | ✅ 冲突 |
| `assurance` / `repairs` | R7 / R10 | 与 §5 一致 | ✅ 一致 |

**这正是第一轮 M-3 的同一根因：补了 schema 槽位，但没有回写 §5 的写集。**
修法：把 §5 四行的写列补上对应槽位（R8 +`claims[].contract`；R12 改为
「写 `narrative_view`（视图），其余零写入」；R13 +`reviews[]`；R14 +`decision`），
**或**在 §3.11 注明「§5 的写集是字段级最小集，本节槽位为落盘容器」。

#### c. `phase:` 字段名与其它处：正文/示例已改，**权威文件的两张表没改**

- 一致处：`project-layout.md:96/268/302`、5 个 phase 文件 frontmatter 行、
  `example-project-layout.md:92`、`templates/INDEX.md:57—65`（列头「阶段」+ 值 R 阶段）✅。
- **未改处（取值为退役字母）**：`project-layout.md:114—119`（类型表「产出 Mode」列 = `A`/`B`/`C`/`D`/`E`）、
  `project-layout.md:414—420`（INDEX 示例表 Mode 列 = `A`…`E`）。
- **未改处（列头用词）**：`project-layout.md:111`「产出 Mode」、`:411`「Mode」、`:531`「Mode」、
  `example-project-layout.md:129`「Mode」。
- **方向性异常：** 示例（`example-project-layout.md:131—135` 已是 R 阶段）比权威
  （`project-layout.md:414—420` 仍是 A—E）新 —— 权威文件应带头。
- 命令：`grep -nE '\| [ABCDE](（|\s*\|)' references/project-layout.md`。

#### d. 「`state_check.py` 都承认它们」是**容忍**而非**识别**（措辞问题）

`scripts/state_check.py` 本轮未改（mtime 05:35）；`structure_error()`（`:291—327`）只检查
八类对象键是否存在、已登记键是否为数组，**未知顶层键与未知 claim 键一律忽略**。
因此这 4 个槽位能通过校验（模板 exit 0 ✅），但**没有任何一条规则读取或校验它们的形状**
（例如 `narrative_view` 给字符串也不会报错）。
**建议：** 把 §3.11 的措辞由「承认」改为「不拒绝（V1—V10 不覆盖形状校验）」，
否则读者会以为有闸门。

### 9.4 V11 / V12 闸门建议（item 4：编号 + 判据，供 Wave 2 登记）

两条规则目前**只有文档约束**，我上轮已实测可 exit 0。建议**顺延编号 V11 / V12**，
判据如下（已用脚本在模板与合规基线上验证**不误报**、在两个违规样例上**必报**）：

| # | 规则（建议逐字进 spec §2.3） | 判据（可机械执行） | 违规路径 | 反例（合法） |
|---|---|---|---|---|
| **V11** | `X2` 不得承担 claim 判别 | 对每个 `experiments[]` 条目：若 `stage` strip 后 == `"X2"`，则 `claim_targeted` 必须为空数组（键缺失按 `[]` 处理） | `experiments[i].claim_targeted` | `{"stage":"X2","claim_targeted":[],"result":"基线 PSNR 33.1"}` → pass |
| **V12** | `status: failed` 的实验必须进 `failures[]` | 对每个 `experiments[]` 条目：若 `status` strip 后 == `"failed"`，则 `failures[]` 中必须存在一条 `F`，其 `referenced_by` 含该 `X` 的**非空 id**；id 为空也算违规 | `experiments[i].status` | 存在 `F4.referenced_by` 含 `X9`（且 V4 由某个 `known_flaws` 指向 F4）→ pass |

**实测（`/tmp/verify` 脚本，本轮重跑）：**

```
模板             V11: []            V12: []
我的合规基线      V11: []            V12: []
场景A X2 判 claim V11: [('V11','experiments[1].claim_targeted',['C1'])]
场景B failed 无F  V12: [('V12','experiments[2].status','X3')]
合法反例1 X2 校准 V11: []   合法反例2 failed 双写 V12: []
```

**登记时必须同轮改的 5 处**（照 `research-state-policy.md:401—403` 自己的维护规则）：
① spec §2.3 表 + §9 变更记录；② `research-state-policy.md §4` 规则表与执行契约；
③ `state_check.py` 的 `RULES`（`:113—124`）与 `CHECKS`（`:666—669`）+ 两个 `_v11/_v12` 函数；
④ `templates/research-state.template.json`（确认不含 `X2`+非空 `claim_targeted`、不含无 F 的 failed —— 当前已满足）；
⑤ `test_state_check.py` 至少各 1 个反例用例（当前 48 个用例，加后 ≥50）。
**注：** V11 只管 `stage == "X2"`；spec §2.2 未对 `X1` 作同样禁止，不要顺手扩大（policy §4 边界 1）。

### 9.5 机械复跑（修复后，06:12 快照）

| # | 项 | 命令 | 结果 |
|---|---|---|---|
| 1 | 相对链接（去围栏） | `/tmp/verify/links.py` | **401 条，0 断链** ✅ |
| 2 | 废弃词（含 `mode=[ABCDE]` 等 3 条新增） | spec §7 原命令 | **exit 1，0 命中** ✅ |
| 3 | JSON | `json.load` ×2 | 全部合法 ✅ |
| 4 | 索引 | `python3 scripts/refs_index.py --check` | exit 0 ✅ |
| 5 | 单测 | `python3 -m unittest discover -s scripts -p "test_*.py"` | **104 tests OK** ✅ |
| 6 | `state_check --selftest` | — | exit 0 ✅ |
| 7 | 模板合规 | `state_check.py templates/research-state.template.json` | exit 0 ✅（新增 4 槽位未破坏 V1—V10） |
| 8 | examples + templates linter | 默认档逐文件 | 全绿 ✅ |
| 9 | 裸字母表行 | `grep -rnE '^\| ?[ABCDE] ?\|'` | 仅 2 处证据台账表头（非阶段字母）✅ |

### 9.6 第二轮总体结论

**仍需修。** 8 项 MAJOR 中 **3 项完整落地（M-1 / M-2 / M-5）**，**4 项部分落地
（M-3 / M-4 / M-6 / M-7）**，**1 项未落地且方向错误（M-8：改了 policy 而 spec 未改）**；
另有一项声称修掉的 MINOR（`[mode-x]` 链接标签）**22/26 未落地**。

| 待修 | 级别 | 位置 | 修法 |
|---|---|---|---|
| M-8 | **MAJOR** | `docs/r-architecture-wave1-spec.md:36` vs `policy:40` + `SKILL:60/762` | 二选一：把 spec 改成 `archive \| submit` 并在 spec §9 记一行；或把 policy/SKILL 改回 `kill` |
| M-3（§5 写集） | **MAJOR** | `research-state-policy.md:361/365/366/367` | §5 四行写列补 `claims[].contract` / `narrative_view` / `reviews[]` / `decision`（§9.3b 表） |
| M-3（三方读/写） | **MAJOR** | `SKILL.md:65—79`、`policy:356—367`、6 个 phase 文件读写段 | 按 §9.2 表逐阶段对齐（12 个阶段）；对齐前先定「以 policy 为准」还是「以 phase 为准」 |
| M-7 | **MAJOR** | `project-layout.md:114—119`、`:414—420` | 表值改 R 阶段；列头 `:111/:411/:531` 与 `example:129` 改「阶段」 |
| M-4 | **MAJOR** | `research-state-policy.md:361`（R8）、`:366`（R13）、`:367`（R14） | R8→`phase-r8-evidence-contract.md`；R13→`phase-r7-r10-r13-assurance-repair-review.md`；R14 需决定（建议写「—（无专属文件，决策写回 state）」） |
| M-6 | **MAJOR** | `phase-r7:321`、`phase-r8:176`、`example-followup-review:60` | 三处 `"E"` → `"R7 / R10 / R13"` |
| 链接标签 | **MAJOR**（按你的判定标准；实质 MINOR，链接本身可解析） | `roles.md`(8)、`narrative-patterns.md`(7)、`phase-r2-r5`(2)、`phase-r8`(2)、`scoring-policy`(1)、`literature-policy`(1)、`phase-r7`(1) | `[mode-x]` → `[phase-…]` 或 R 阶段名 |
| §3 通用规则 3 | MINOR | `policy:129—130` | 补一句指向 §3.11 |
| `B/C/E` 残留 | MINOR | `SKILL.md:323`、`:565` | 改 `R3—R6 / R8 / R7 / R10 / R13` |
| `state_check` 「承认」措辞 | NIT | `policy:425` | 改为「不拒绝（V1—V10 不覆盖形状校验）」 |
| V11 / V12 | 登记 | 见 §9.4 | Wave 2 实现（编号与判据已给） |

**一句话总体结论：仍需修** —— 3 项完整落地、4 项部分落地、1 项（R14 枚举）改在了错误的一层
（spec 未同步）；三方读写口径与第一轮完全一致地保持不一致；但新增件质量与机械面（401 链接 0 断链、
104 测试、模板 exit 0、deprecated 0 命中）保持全绿，剩余项仍是一到两行级修复。

---

## 10. 收官确认（第三轮：最终复核）

**范围：** 确认第二轮 4 项 MAJOR 残留（M-3/M-4/M-6/M-7）与 M-8 是否落地、三方读写是否逐字一致、
批量重写有没有误删、机械面复跑。**快照：06:18 的冻结状态**（Lead 末笔编辑 06:15:51，
之后 2 分钟无变动，`find -newermt '60 seconds ago'` 为空；所有命令在冻结后执行）。

### 10.1 上轮 5 项处置逐条确认

| 项 | 声明 | 现值（文件:行号） | 判定 |
|---|---|---|---|
| **M-3**（三方读写） | 口径改简写式并统一，14 阶段逐字相同；§5 表下有「不得当第二套口径」 | **独立脚本比对：14/14 阶段逐字相同**（§10.2）；`policy:373`「**不得**把它当成第二套口径」✅；`policy:447` 改为「模板与 `state_check.py` 都**不拒绝**它们（忽略未知键；V1—V10 不覆盖形状校验）」✅；§3.11 与 §5 写集矛盾消除（§5 R8 含 `claims[].contract`、R12 含 `narrative_view`、R13 含 `reviews`、R14 含 `decision`）✅ | ✅ **达成**（1 处措辞更正未落地 → §10.3 a） |
| **M-4** | R8/R13 各指自己的文件；R14 指向 `SKILL §4「R13 / R14」` | `policy:363` R8 → `phase-r8-evidence-contract.md` ✅；`policy:368` R13 → `phase-r7-r10-r13-assurance-repair-review.md` ✅；`policy:369` R14 → `../SKILL.md` §4「R13 / R14」✅（`SKILL.md:757` 确有该节）；`policy:362` R7 / `:367` R12 ✅。旧的不存在名 0 命中 ✅ | ✅ **达成**（单元格尾部残留 `( \` → §10.3 c） |
| **M-6** | 3 处 `"E"` 已改；另修 phase 文件里的 `"mode": "E",` | `grep -rn 'next_phase_suggestion' \| grep '"E"'` → **0**；`grep -rn '"mode"\s*:'` → **0**；14 处取值现为 `R8` / `R12` / `R7 / R10 / R13` / `R8 \| R7 / R10 / R13` ✅ | ✅ **达成** |
| **M-7** | 两张表列头 + 取值全改 | `project-layout.md:111` 列头「产出阶段」、`:114—119` 取值 `R2`/`R3—R6`/`R8`/`R9—R11`/`R12`/`R7 / R13` ✅；`:411` 列头「阶段」、`:414—420` 取值 `R2`/`R3—R6`/`R8`/`R9—R11`/`R12`/`R7 / R10 / R13` ✅；`grep -cE '\| [ABCDE](（\|\s*\|)' project-layout.md` → **1**（唯一命中是 `:222` 证据台账表头 `\| E \| 内容 \|`）✅ | ✅ **达成** |
| **M-8** | 改在正确一层：spec §1 图 + 变更记录；policy 同步 | `docs/r-architecture-wave1-spec.md:36` = `continue \| pivot \| archive \| submit` ✅；spec §9 变更记录新增第 2 行（「依 `docs/verify-r-wave1.md` §9 修 M-3/M-4/M-6/M-7/M-8 与 MINOR；R14 决策枚举统一…（本节 §1 的图同步）」）✅；`policy:40`、`SKILL.md:60/762` 同 ✅ | ✅ **达成** |
| MINOR（22 处 `[mode-x]`） | 全改 | `grep -rcE '\[mode-[abcde]\]' --include=*.md .` → **0** ✅ | ✅ **达成** |
| MINOR（`SKILL:323/565`） | 已改 | `SKILL.md:323` = 「仍使用会议审稿人的 **R 阶段（R3—R6 / R8 / R7 / R10 / R13）**」；`:565` = 「（**R3—R6 / R8 / R7 / R10 / R13 用**）」✅ | ✅ **达成** |

### 10.2 三方逐字一致性（独立脚本，非复述）

**方法：** 自写 `/tmp/verify/rw_compare.py`：解析 `SKILL.md §0` 表（5 列，取第 4/5 列）、
`research-state-policy.md §5` 表（4 列，取第 2/3 列）、7 个 `phase-*.md` 末尾读写段
（统一 3 列 `阶段 / 读 / 写`），按 `R<n>` 归并后**逐字比较单元格字符串**（不归一化、不去格式）。

```
逐字相同阶段: 14/14  不一致: ['R1']
```

- **R0—R14 全部逐字相同**，每阶段均有 3 个来源（SKILL + policy + 对应 phase 文件）：
  `R0`(phase-r0) `R2`(phase-r2-r5) `R3`/`R4`/`R6`(phase-r3-r6) `R5`(phase-r2-r5) `R7`/`R13`/`R14`(phase-r7-r10-r13)
  `R8`(phase-r8) `R9`/`R10`/`R11`(phase-r9-r11) `R12`(phase-r12)。
- **`R1` 只在 SKILL §0 出现**：policy §5 明确「R1 **不占行**」（`:350`）——设计选择，**非缺陷**。
- **R14 的「对应文件」= `../SKILL.md` §4「R13 / R14」**：`SKILL.md:757` 有该节，可解析 —— 设计选择，**非缺陷**。
- 抽样核对（读单元格）：`R2 = literature / assumptions / uncertainties`、`R8 = claims / evidence / assurance`、
  `R12 = claims / evidence / failures / uncertainties`、`R13 = 全 state + artifact`、
  `R14 = 全 state + 未闭环 repairs`，三处同形同字 ✅。

### 10.3 新发现（本轮 polish 引入）

| # | 级别 | 现象 | 文件:行号 | 证据 | 建议修法 |
|---|---|---|---|---|---|
| a | **MINOR** | **声称已改的「通用规则 3」实际未改**：仍写「未在本节出现的字段 = 未定义字段，**不得**自行添加…**必须**先报 Lead 改 spec」。更正句只存在于 §3.11（`:447—448`），且措辞是「旧表述…的**准确含义是**」——属**可调解**的表述，不是硬互斥，故定 MINOR（按 Lead「没改到即 MAJOR」的标准可升级处理） | `research-state-policy.md:129—130`（未改）vs `:447—448`（更正句） | `sed -n '129,130p'`；`grep -n '准确含义' references/research-state-policy.md` | 在 `:130` 末尾加一句回指：`（**本轮新增槽位见 §3.11**；新增字段必须同时更新本节、§3.10/§3.11 与模板）` |
| b | **MINOR** | **本轮正则重写误删了 5 个 phase 文件的「内部小节号保留」注**：第二轮这 5 个文件各有「> **内部小节号 `§A0—§A7` 保留自旧命名**（本文档由旧 `mode-a` 迁移而来）…**迁移不得丢节。**」，现在全仓 **0 命中**。删掉后，`§A7`/`§B8`/`§C7`/`§D9.5`/`§E8` 这些**保留的内部编号**失去唯一解释，读者会把它们误当退役字母残留（第一轮报告正是靠这条注才把 `§D4.4`/`§E2.1`/`§B5.2` 判为合规） | `phase-r2-r5-field-mapping-retrieval.md`、`phase-r3-r6-discovery.md`、`phase-r8-evidence-contract.md`、`phase-r7-r10-r13-assurance-repair-review.md`、`phase-r12-narrative.md`（原在第 2 轮文件末尾，现均在读写段之前被删） | `grep -rn '内部小节号\|保留自旧命名\|全量重编号\|迁移不得丢节' --include=*.md .` → **0**（第二轮为 5 条） | 各恢复一行：`> **内部小节号 §X0—§X<n> 保留自旧命名**（本文档由旧 phase 迁移而来）；全量重编号在 Wave 3 做。**迁移不得丢节。**` |
| c | NIT | R14 行「对应文件」单元格尾部有编辑残留 `( \` | `research-state-policy.md:369` 末：``…§4「R13 / R14」( \ |`` | `sed -n '369p' references/research-state-policy.md \| grep -o '( \\ *\|$'` | 删掉 `( \`（保留 `` `../SKILL.md` §4「R13 / R14」 ``） |
| d | NIT | §3.11 说 `reviews` 由「R7 / R13」写，但 §5 的 R7 写集里没有 `reviews`（只有 R13 有） | `research-state-policy.md:456` vs `:362` / `:368` | `sed -n '456p;362p;368p'` | §3.11 改为「R13（R7 亦可追加）」，或 §5 R7 写集补 `reviews` |

**误删排查结论（item 3 的第一半）：** 除 (b) 外**无其它误删**——
5 个 rename 文件对 `f8cefdc` 的 `##`/`###` 计数与第一轮**完全一致**（8→10/3→6、10→12/5→8、
8→10/1→1、13→15/15→15、10→12/6→9），段落级低相似项只有 3 处且**全是改名**
（`Mode C/D/E → R8/R12/R7·R10·R13`，sim 0.76/0.71/0.80），无段落消失。
7 个 phase 文件的读写小节**各只有 1 个**（无重复追加），`> 回写后跑 state_check.py …` 提示 7/7 都在。
**SKILL §0 无重复片段（item 3 第二半）：** 15 行、每个 `R<n>` 恰好出现 1 次，
表头 1 个（`awk` 提取 + `uniq -c` 核验）。

### 10.4 机械面复跑（冻结后）

| # | 项 | 结果 |
|---|---|---|
| 1 | `deprecated-terms`（含 `mode=[ABCDE]` 等） | **exit 1，0 命中** ✅ |
| 2 | 相对链接（去围栏） | **408 条，0 断链** ✅（含 `../SKILL.md` 等新链接） |
| 3 | JSON（模板 + refs 索引 + md 内围栏） | 全部合法 ✅ |
| 4 | `refs_index.py --check` | exit 0 ✅ |
| 5 | `python3 -m unittest discover -s scripts -p "test_*.py"` | **104 tests OK** ✅ |
| 6 | `state_check.py --selftest` | exit 0 ✅ |
| 7 | `state_check.py templates/research-state.template.json` | exit 0 ✅ |
| 8 | examples + templates 默认档 linter | 9 个文件，硬违规 0 ✅ |
| 9 | 裸字母表行 | 仅 2 处证据台账表头（`\| E \| 内容 \|`），非阶段字母 ✅ |

### 10.5 收官结论

- **第一轮的 8 项 MAJOR：全部落地**（M-3 有 1 处措辞更正未落地，见 §10.3 a）。
- **第二轮提出的 4 项 MAJOR 残留 + M-8：全部落地**（三方 14/14 逐字相同是独立脚本核验，不是复述）。
- **新发现：2 项 MINOR（各一行修复）+ 2 项 NIT**，均不构成互斥指令或断链。

**结论：仍需修（3 行）** —— 按你设定的闸门（「只剩 NIT 才可交付」），当前还差
§10.3 的 **(a) 通用规则 3 回指一行 + (b) 恢复 5 个 phase 文件的内部小节号注（各一行）+ (c) 删 `( \`**；
(d) 可选。**除此之外我这边没有其它阻断项**：8 项 MAJOR 全绿、三方读写逐字一致、
408 链接 0 断链、104 测试通过、模板与 validator 自检通过、deprecated 0 命中、linter 全绿。
若你判断 (a)/(b) 可延后到 Wave 2 首轮随 V11/V12 一起补，则**其余部分已具备提交条件**——
但那就不是「只剩 NIT」，我不替你做这个取舍。
