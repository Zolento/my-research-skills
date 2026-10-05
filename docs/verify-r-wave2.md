# R 架构 Wave 2（发现层）：独立对抗性验收报告

**验收对象：** 分支 `research-idea-pipeline-dev`，基线 `dfee183`，本次快照 `aec42b8`（工作树干净，已本地提交）。
**契约：** [`docs/r-architecture-wave2-spec.md`](r-architecture-wave2-spec.md)（下称「spec」）。
**验收者：** teammate `verifier`（只读；本文件是本次验收唯一写入的文件）。
**验收时间：** 2026-10-06 ｜ **工作目录：** `research-idea-pipeline-dev/`（文件行号相对仓库根）。

**立场声明：** 不采信任何写作者自述，包括「已知未做」清单 —— 本轮实测推翻了其中一条（见 M-1）。
所有结论附 文件:行号 与可重跑命令；机械面与「扫过没问题」的项在 §5 逐条列出。

---

## 0. 结论摘要

| 级别 | 条数 | 说明 |
|---|---|---|
| **MAJOR** | **6** | 被删章节、SKILL 未接线、新旧流程互斥、示例过不了闸门、字段表缺槽位、spec 自相矛盾 |
| MINOR | 6 | 规则表列错位/陈留、docstring 陈留、作用域冲突、测试硬编码下限 |
| NIT | 3 | 自检标签、缺显式合法反例、deprecated 未登记旧 niche 名 |

**总体结论：需修后交付。** Wave 2 的**新机制本体质量高**：V13—V15 + V6 扩展经我自建 25 个独立 fixture
全部正确（exit 3 + 规则号 + JSON 路径），三方 14 阶段仍逐字一致（独立脚本复跑 14/14），
测试期望值确实已从 `RULES`/`RULE_ORDER` 派生（我用「注入第 16 条规则」实验证明），机械面全绿
（114 测试、408 链接 0 断链、deprecated 0、模板 exit 0、linter 9/9）。
问题集中在**「新旧两代发现流程共存」**与**几处漏同步**：`phase-r3-r6` 里旧的 `B5.4`/`B6`/`B8`
仍在教「一轮 brainstorm → shortlist 3—5 个」，`phase-r2-r5` 的 field grammar / occupancy map
被整段删除，`SKILL §4` 的 R3—R6 速查段与 `§7` 设计依据未接 Wave 2，`policy §3.4` 没加
`island`/`generation`，且 spec 自己的 §1（P1—P6）与 §2/§3（4 islands）互相矛盾。

---

## 1. MAJOR

### M-1 `phase-r2-r5` 把 `field grammar` 与 `occupancy map` **整段删除**（「已知未做」清单与事实不符）

**现象：** Lead 的已知未做清单写「`phase-r2-r5` 的 field grammar / occupancy map **仍是骨架**」。
实测这两节**已不存在**：Wave 2 提交把 `## Wave 2 深化骨架` 整块换成 `## R5. 共演化检索`，
连同两节一起删掉，全仓无替代（`grep -rn 'field grammar\|occupancy map\|negative space'` 仅命中
SKILL 的一行宣称与两处 spec/验收记录）。

**文件:行号 / 证据（命令）：**

```bash
cd research-idea-pipeline-dev
git show f8dda53:research-idea-pipeline/references/phase-r2-r5-field-mapping-retrieval.md \
  | grep -nE '^#{2,3} ' | sed -n '12,18p'
#   214: ## Wave 2 深化骨架（本轮只落骨架，不假装完成）
#   216: ### field grammar `{P, A, R, D, O, M, T, E}`
#   231: ### occupancy map（占用图）
#   247: ### R5 共演化检索
grep -nE '^#{2,3} ' research-idea-pipeline/references/phase-r2-r5-field-mapping-retrieval.md | sed -n '11,14p'
#   214: ## R5. 共演化检索（**常驻服务**，不是一次性步骤）   ← 两节消失
grep -rn 'field grammar\|occupancy map\|negative space' --include=*.md research-idea-pipeline/
#   仅 SKILL.md:67（宣称 R2 = field grammar + occupancy map + 检索纪律）
```

**被删内容（f8dda53:216—246，约 31 行）：** 8 行 `{P, A, R, D, O, M, T, E}` 字段文法表 +
`occupancy map` 的拥挤度示意与「**negative space 是 R3 paradigm escape 的输入**」规则。

**影响：** ①内容丢失（spec §6 只授权「R5 从骨架转正式规则」，未授权删 field grammar / occupancy map）；
②`SKILL.md:67` 的 R2 职责描述（`field grammar + occupancy map + 检索纪律`）现在指向不存在的章节；
③Wave 3 若按「骨架已就位」继续深化，会找不到落点。

**建议修法：** 在 `phase-r2-r5` 的 `## R5.` 之前恢复两节（`### R2.1 field grammar` /
`### R2.2 occupancy map`），并将 `phase-r2-r5` 的读写段或 SKILL §0 的 R2 行注明它们属 R2；
或明确写入 spec §8「Wave 3 非目标」并同步删掉 `SKILL.md:67` 的宣称。

---

### M-2 `SKILL.md` 的 **§4 R3—R6 段与 §7 设计依据未接 Wave 2**（spec §6 明确要求）

**现象：** spec §6 文件地图对 SKILL 的要求是「UPDATE：§0 读/写列、**§4 的 R3—R6 段**、
**§7 设计依据（+「为什么两阶段 fitness」）**」。实测 Wave 2 提交只改了 §0 的两行（R4/R6 读写列）。

**文件:行号 / 证据（命令）：**

```bash
cd research-idea-pipeline-dev
git diff dfee183 aec42b8 -- research-idea-pipeline/SKILL.md | grep -E '^[+-]\| \*\*R'
#   只出现 §0 表的 R4/R6 两行改动
sed -n '666,684p' research-idea-pipeline/SKILL.md
#   ### R3—R6 — 双轨发现与种群进化
#   - **流程：** B1 基础文献调研 → B2 深度局限性分析 → B3 多子代理头脑风暴 → B4 发散策略约束
#     → **B5 idea 级创新性与可行性审核（强制）** → B6 输出 → B7 落盘
#   - **交付物：** … + **推荐 shortlist（3—5 个）+ 淘汰清单**
grep -n '两阶段\|fitness\|Search 期\|venue fit\|QD archive\|island' research-idea-pipeline/SKILL.md
#   无「两阶段 fitness」条目；island 只在 §0 表的 R4 写列出现
grep -n '^## 7\. 设计依据' -A 3 research-idea-pipeline/SKILL.md
#   §7 仍止于第 14 条（reviewer 按攻击面），没有 Wave 2 新增条目
```

**影响：** SKILL §4 是执行者最先读的「各 R 阶段速查」；它现在把 R3—R6 描述成旧流程，
且不含 4 islands × 3—6 / 进化 ≤2 轮 / QD archive / 两阶段 fitness —— 与 `phase-r3-r6` 的
新规则直接冲突（M-3）。§7 缺「为什么两阶段 fitness」使新纪律失去设计依据（Wave 1 的 A1 类漂移）。
**注：** spec §7 第 6 条（「两阶段 fitness 写明 Search 期不看 venue fit」）在 **phase 文件层已达成**，
因此这是 **spec §6 的接线义务缺失**，不是 §7 验收项失败。

**建议修法（Lead 自有项）：** 重写 `SKILL.md:666—685` 为 R3/R4/R5/R6 四段速查
（含 islands 预算、QD archive、共演化检索、两阶段 fitness）；在 §7 追加第 15 条
「为什么两阶段 fitness（Search 期不看 venue fit）」。

---

### M-3 `phase-r3-r6` 里**新旧两代发现流程同时可执行**：旧 `B5.4`/`B6`/`B8` 仍教 shortlist，与 R4.2 / R6.3 互斥

**现象：** 文件顶部加了「作用域裁决」注（`:15—18`），但旧的 `B0`—`B8` 流程**全文保留且语气更强**
（「强制，不可跳过」），而且出现在新规则**之前**（B 段 `:20—316`，R 段 `:317—440`）。

**会误读的具体段落（逐条）：**

| # | 位置 | 原文（节选） | 与哪条新规则冲突 |
|---|---|---|---|
| a | `phase-r3-r6-discovery.md:231` | **「推荐 shortlist（3—5 个）** —— 从"高/中"中挑选」 | `:382`「**禁止** `21 ideas → 打分 → Top-3 → 丢掉其余`。改为每个 niche 留一个 elite」 |
| b | `phase-r3-r6-discovery.md:209—218` | `B5.4 优先级判定规则`：按 **创新性 / 可行性 / 重叠度** 判 高/中/低/建议放弃 | `:428—438` 两阶段 fitness：Search 期只看 `representation_distance` / `structural_novelty` / `cross_domain_surprise` / `deductive_yield`，**不看 venue fit**，`EIG` 只作记录 |
| c | `phase-r3-r6-discovery.md:272` | 「建议用户从 **shortlist 中挑选 1—3 个** idea 进入 R8」 | `:349—351` 预算 4 islands × 3—6 候选；`:382` QD archive 全量保留 |
| d | `phase-r3-r6-discovery.md:32` | B0 表「**产出**：排序后的 shortlist + 淘汰理由」 | 同上 |
| e | `phase-r3-r6-discovery.md:177` | 「**进入 shortlist 的门槛 = 完成 L2**」 | shortlist 概念本身已被 QD archive 取代 |
| f | `phase-r3-r6-discovery.md:148` | 「## B5. Idea 创新性与可行性审核（**强制，不可跳过**）」 | 新流程里 R3 产出 population，R4 按 niche 归档，没有「强制审核后筛 3—5 个」这一步 |

**为什么「作用域裁决」不足：** 该注（`:15—18`）只声明「冲突以 R3—R6 为准；B2/B4/B5 作为 R3 的
输入约束保留」，但它 **① 没有逐节点名 B5.4/B6/B8 的 shortlist 机制作废；② 没有改这些节的语气
（仍写「强制」「不可跳过」「推荐」）；③ 位置在文件顶部，而 B 段的指令性文本有 300 行**。
执行者按顺序实现时，最自然的读法是「先跑 B1→B7，再看 R3—R6 补充」——正是 Wave 2 要消灭的顺序。

**证据（命令）：**

```bash
cd research-idea-pipeline/references
grep -nE 'shortlist|不可跳过|推荐 shortlist' phase-r3-r6-discovery.md
sed -n '15,18p;209,218p;231p;272p;382p;428,438p' phase-r3-r6-discovery.md
```

**建议修法（二选一，需 Lead 裁决）：**
①**归档**：把 `B0`—`B8` 整体移入文件末尾的「附录 A：旧 idea-discovery 流程（Wave 2 起被 R3—R6 取代）」，
每节首行加 `> ⚠️ 已归档 —— 现行规则见 R3/R4/R6`，并删除 `B5.4` 与 `B6` 的 shortlist 机制；
②**改写**：保留 B1/B2/B4/B5 的检索与审核纪律，但把 B5.4 的优先级规则、B6 的 shortlist、
B8 的「挑选 1—3 个」改成指向 R4.2 / R6.3 的表述。
无论哪种，**`B6` 的「3—5 个」与 `B5.4` 的排序表必须消失或明确标废**。

---

### M-4 `phase-r3-r6` 的 `B8` 给出的 `state.json` 片段是**已删 schema**，实测 `state_check.py` **exit 4**

**现象：** `## B8. 输出后` 要求「附 `state.json` 片段」，但片段用的还是 Wave 1 之前的旧 schema
（`idea_candidates` / `review{innovation, feasibility}` / `shortlist` / `rejected` / `innovation_boundary`），
**没有八类一等对象**，也没有 Wave 2 的 `island` / `generation`。

**证据（命令）：**

```bash
cd research-idea-pipeline
sed -n '/^## B8/,/^## R3/p' references/phase-r3-r6-discovery.md | sed -n '1,50p'
python3 - <<'PY'   # 把该片段抽出来直接喂 validator
import re,json
txt=open('references/phase-r3-r6-discovery.md',encoding='utf-8').read()
seg=txt[txt.index('## B8'):]
json.dump(json.loads(re.search(r'```json\n(.*?)\n```',seg,re.S).group(1)),
          open('/tmp/b8.json','w'),ensure_ascii=False)
PY
python3 scripts/state_check.py /tmp/b8.json --json | head -8
#   exit = 4 ; error_kind = structure
#   "未找到 Research World Model 的八类一等对象数组（claims / evidence / …）"
```

**影响：** 执行者按文件指示「附 state.json 片段」写出的文件**过不了本 Skill 自己的机械闸门**，
且与 `research-state-policy.md` §1/§2 冲突（R1 是唯一状态载体）。
**建议修法：** 把 B8 片段替换为 `research-state.json` 的最小片段（含 `hypotheses[]` 的
`island`/`generation`/`niche`，与模板同形），或标注「历史片段，现行格式见 policy §3.4 / 模板」。

---

### M-5 `research-state-policy.md §3.4` **未加** `island` / `generation`（spec §3 要求的「5 处同步」缺一）

**现象：** spec §3 明文：「Wave 2 新增两个字段（**必须同轮改 5 处**：本节 / `research-state-policy.md`
§3.4 / 模板 / `state_check.py` / 测试）」。实测 §3.4 的字段表仍是 Wave 1 的 10 行，
既没有 `island` 也没有 `generation`，`niche` 行仍写「字符串，非空」。

**文件:行号 / 证据（命令）：**

```bash
cd research-idea-pipeline
grep -n 'island\|generation' references/research-state-policy.md
#   310/311（§4 的 V13/V14 行）、364/366（§5 的 R4/R6 行）—— §3.4 内 0 命中
sed -n '/^### 3.4 /,/^### 3.5/p' references/research-state-policy.md | tail -6
#   | `status` | active|elite|archived|killed | ✅ | |
#   | `niche` | 字符串，非空 | ✅ | V6；QD archive 的前提 |     ← 无 island/generation；niche 未改 N1—N10
```

**影响：** policy §3 通用规则 3（`:129—130`）写「**未在本节出现的字段 = 未定义字段**，**不得**自行添加」
—— 而 `state_check.py` V13/V14 强制这两个字段、模板已填、spec §3 声明它们是冻结字段。
执行者若从 §3.4 出发，会得出「不该写 island/generation」的结论，随后被 V13/V14 判 exit 3。
这是 A4 类（规则 → 字段 → 枚举 → 模板 → 示例）漂移的典型形态。
**建议修法（一行级）：** §3.4 表补两行：
`| island | P1 \| P2 \| P3 \| P4 \| local | ✅ | V13；local = Local Search |`、
`| generation | 整数 ≥ 0 | ✅ | V14；0 = 初始候选，每次 R6 进化 +1 |`；
并把 `niche` 行改为 `N1—N10（V6 强制）`。

---

### M-6 spec 自身矛盾：§1 列 **P1—P6** 六条 escape 轨，§2/§3 只给 **4 islands（P1—P4）+ local**

**现象：** 同一个契约里，§1 的图列出 **P1 Reframe / P2 Assumption destruction / P3 Remote
structural analogy / P4 Theory lens / P5 Measurement inversion / P6 Counterexample & impossibility**，
而 §2 写「islands 数 **4** —— 固定四轨：`P1`/`P2`/`P3`/`P4`（**见 §1 图**）」，
§3 的 `island` 枚举是 `P1`/`P2`/`P3`/`P4`/`local`（**5 值**）。
于是 **P5 / P6 两个轨道没有对应的 `island` 值**：由「测量反转」或「反例/不可能性」产生的候选，
在 V13 下只能被标成 P1—P4 之一或 `local`，**provenance 丢失**。

**文件:行号 / 证据（命令）：**

```bash
sed -n '17,27p;45p' docs/r-architecture-wave2-spec.md
#   20—23: P1 … / P4 Theory lens / P5 Measurement inversion / P6 Counterexample & impossibility
#   45:    | **islands 数** | **4** | 固定四轨：`P1` / `P2` / `P3` / `P4`（见 §1 图） |
sed -n '63,66p' docs/r-architecture-wave2-spec.md
#   65:    | `island` | `P1` / `P2` / `P3` / `P4` / `local` | 该候选由哪条轨产生；local = Local Search |
grep -n 'P1.*P4\|P5\|P6' research-idea-pipeline/references/phase-r3-r6-discovery.md | sed -n '1,8p'
#   322—327: 图里同时列出 P1—P6 轨；:349 「islands 数 | 4（P1—P4）+ Local Search」
```

**影响：** 冻结枚举（V13）与冻结流程（§1 图）不自洽；phase 文件把六条轨与四个 island 并排画出，
却没有一句映射规则。Wave 2 的「保多样性」正是在这条轴上，provenance 缺失会直接削弱 R4 的聚类解释。
**建议修法（需用户/Lead 裁决，二选一）：**
①**保留 4 islands**：把 §1 图改成「六条 escape **提问法** P1—P6，归入 4 个 island：P1+P6→`P1`、
P2→`P2`、P3→`P3`、P4+P5→`P4`」这类**显式映射**，并在 `phase-r3-r6` 的 R3 图下写出同一映射；
②**扩枚举**：`island ∈ P1—P6 + local`（7 值），同步 spec §2 预算（6 islands）——但这要推翻
用户「4 islands」的拍板，需用户同意。

---

## 2. MINOR

| # | 现象 | 文件:行号 | 证据（命令） | 建议修法 |
|---|---|---|---|---|
| m-1 | `policy §4` 的 **V6 行未扩展**：仍写「每条 `H` 的 `niche` 非空」，而 `state_check.py` 已强制 `N1—N10`。policy 自己声明「规则文本逐字取自 spec；`state_check.py` 与该表一一对应」 | `references/research-state-policy.md:303`（V6 行）、`:294`（对齐声明） | `sed -n '294p;303p' references/research-state-policy.md`；`grep -n 'NICHES' scripts/state_check.py` | V6 行改为「`niche` 非空**且 ∈ `N1—N10`**（QD archive 复用 preset 名）」 |
| m-2 | `policy §4` 新增的 **V11—V15 行整列错位**：表头是 `# / 规则（逐字） / 违规 / 典型反例`，新行写成「V13 \| 硬 \| <规则文本> \| <反例>」—— 「硬」占了规则列，规则文本落到违规列 | `references/research-state-policy.md:308—312` | `awk -F'\|' '/^\| V/{print $2,NF-2}' …`；`sed -n '306,311p'` | 五行的第 2/3 列互换为「V13 \| <规则文本> \| 硬 \| <反例>」 |
| m-3 | `policy §4` 的**执行契约块陈留**：`--list-rules` 写「列出 V1—V10 与判据」、`--selftest` 写「V1—V10 全覆盖」 | `references/research-state-policy.md:321—322` | `sed -n '/执行契约/,/与 .state_check/p' references/research-state-policy.md` | 改为 `V1—V15`（或「全部已登记规则」） |
| m-4 | `state_check.py` 模块 docstring **陈留**：只列 V1—V10，且判据补充写「**V1—V10 之外不新增硬规则**」；契约来源只引 `r-architecture-wave1-spec.md` | `scripts/state_check.py:6`、`:21—32`（规则清单）、`:46` | `sed -n '6p;21,32p;46p' scripts/state_check.py`；`python3 scripts/state_check.py --list-rules \| wc -l` → 15 | docstring 补 V11—V15 并改引 Wave 1 §4 + Wave 2 §4；删掉「不新增硬规则」或改为「新增必须同时改 policy §4 与 spec」 |
| m-5 | `R6.3` 的括注与三处派遣规则**冲突**：phase 说「`venue-standards` **只在 R12/R13 生效**」，而 roles / venue-standards / SKILL 都说四个会议审稿人在 **R3—R6** 就参与 | `references/phase-r3-r6-discovery.md:436` vs `references/roles.md:15`、`references/venue-standards.md:72`、`SKILL.md:323` | `sed -n '436p' references/phase-r3-r6-discovery.md`；`sed -n '15p' references/roles.md`；`sed -n '72p' references/venue-standards.md` | 括注改为「**venue 校准 / preset 选择**只在 R12—R13 生效；会议审稿人视角在 R3—R6 仍可用于 challenge，但**不得进入 Search 期排序**」 |
| m-6 | `test_state_check.py` 仍硬编码规则数下限：`self.assertTrue(len(sc.RULES) >= 12)`（spec §4 要求「测试里的规则数不得再硬编码 —— 期望值从 `RULES`/`RULE_ORDER` 派生」） | `scripts/test_state_check.py:612` | `grep -n 'len(sc.RULES)' scripts/test_state_check.py` | 改为与 `CHECKS` 一致：`self.assertEqual(set(sc.RULES), set(sc.CHECKS))` 或直接删掉计数断言（下一行已逐条校验文本非空） |

---

## 3. NIT

| # | 现象 | 文件:行号 | 证据 | 建议 |
|---|---|---|---|---|
| n-1 | 自检覆盖标签按**字典序**取末位，渲染成 `自检覆盖 V1—V9`（应是 V1—V15）。断言本身正确（`set(RULE_ORDER) - detected == set()`），只是标签字符串错 | `scripts/state_check.py:1114` | `python3 scripts/state_check.py --selftest \| grep 自检覆盖` → `ok 自检覆盖 V1—V9` | 改用 `f"V1—V{RULE_ORDER[-1][1:]}"`（与 `summary()` 同款） |
| n-2 | V15 **缺显式合法反例测试**：只有 `test_v15_niche_without_elite_is_hard`；「两个 niche 各有 elite → 0」只由 `valid_state()` 隐含覆盖 | `scripts/test_state_check.py:449—482` | `grep -n 'def test_v1[345]' scripts/test_state_check.py` | 补一条 `test_v15_every_niche_has_elite_is_legal`（我已在 fixture 中验证该场景 exit 0） |
| n-3 | `deprecated-terms.txt` 未登记被替换的**旧 niche 名**（`assumption-breaking` / `new-formulation` / `remote-theory-transfer` / `impossibility` / `benchmark-inversion`）；spec 未强制，但 Wave 1 的 D4 维护规则要求「被替换的旧表述追加进来」 | `references/deprecated-terms.txt`（全文未含这些词） | `grep -c 'assumption-breaking' references/deprecated-terms.txt` → 0 | 随 Wave 3 追加 5 条旧 niche 名（当前它们只作为 `novelty_source` 与测试非法值出现，不构成违规） |

---

## 4. spec §7 验收标准逐条判定

| # | 验收项（spec §7） | 判定 | 证据 |
|---|---|---|---|
| 1 | V13—V15 各 ≥1 反例 + ≥1 合法反例；**测试不再硬编码规则数**（从 `RULES` 派生） | **部分达成** | 作者用例：V13 非法+合法（`:452/:457`）、V14 字符串/负数（`:461/:466`）、V15 非法（`:471`）、V6 旧名（`:477`）；我自建 25 fixture 全对（§5.2）。**但** `test_state_check.py:612` 仍有 `>= 12` 下限（m-6）；派生性我用「注入 V16」实验证明（§5.3） |
| 2 | `state_check.py --selftest` 覆盖 V1—V15；模板 `--check` exit 0 | **达成** | `--selftest` exit 0（自检 `set(RULE_ORDER)-detected == set()`）；`state_check templates/research-state.template.json` → `[ok] … V1—V15 全部通过` exit 0；模板含 `island: P2` / `generation: 0`（`:165—167`） |
| 3 | 三方口径 14 阶段仍逐字一致（Wave 1 检查器复跑 0 不一致） | **达成** | 独立脚本（§5.4）：**14/14 逐字相同，不一致 `['R1']`**（R1 只在 SKILL，policy §5 明写「R1 不占行」= 设计选择） |
| 4 | `hypotheses[].niche` 取值 ∈ `N1—N10`（V6 扩展） | **部分达成** | 实现 ✅（`state_check.py:108` NICHES、`_v6` 两段判定）；**但** policy §3.4 `niche` 行与 §4 V6 行未同步（M-5 / m-1） |
| 5 | 双轨**上下文隔离**写成硬规则 | **达成** | `phase-r3-r6-discovery.md:320`（标题）+ `:335`「**两轨在产生候选之前不得互相看到内容。** … **隔离是机制，不是建议。**」 |
| 6 | 两阶段 fitness 写明 **Search 期不看 venue fit** | **达成（phase 层）** | `phase-r3-r6-discovery.md:428—438`：Search 只看 `representation_distance`/`structural_novelty`/`cross_domain_surprise`/`deductive_yield`，**不看 venue fit**；「`venue-standards` 只在 R12/R13 生效」；`EIG` 在 Search 期只作记录。**但** SKILL §4/§7 未同步（M-2），且括注与派遣规则冲突（m-5） |
| 7 | 预算默认值（4 islands × 3—6 候选，进化 ≤2 轮）写进 phase 文件 + 可缩放条件 | **达成** | `phase-r3-r6-discovery.md:344—353`：`islands 数 4`、`每 island 候选数 下限 3 上限 6`、`进化轮数上限 2`、**可缩放**「降到 2 islands × ≥2 候选；上调需用户同意」 |
| 8 | 全量机械校验：链接 / § 引用 / JSON / 单测 / linter / deprecated-terms 全绿 | **达成** | §5.5：408 链接 0 断链、deprecated exit 1（0 命中）、JSON 合法、**114 tests OK**、`--selftest` 0、模板 0、linter 9/9 |
| 9 | 独立 verifier 对抗验收通过 | **未通过（本报告）** | 见 §1 — §3 |

---

## 5. 必做项复核（方法 + 命令 + 结果）

### 5.1 复核范围与只读纪律

- 只写 `docs/verify-r-wave2.md`；未改任何被审文件；未 `git commit`。
- 「注入第 16 条规则」实验在 **`/tmp/verify/w2/rc/` 的副本**上进行（`cp state_check.py test_state_check.py
  + templates/`），**被审文件零改动**（`git status --short` 全程为空）。

### 5.2 V13—V15 + V6 扩展独立反例（**不看作者测试**，自建 25 fixture）

**方法：** 自建合规基线（八类对象 + `island:"P2"` + `generation:0` + `niche:"N2"` + `status:"elite"`），
逐项注入违规 → CLI `--json` → 断言 `exit==3`、规则号命中、JSON 路径正确。

```
基线 exit=0 ✅（合法）
V13  island=PX / 缺失 / '' / 'p1' / 3 / 'P5'        → exit 3 · V13 · hypotheses[0].island   ✅×6
V14  generation='1' / -1 / True / 1.0 / 缺失 / None → exit 3 · V14 · hypotheses[0].generation ✅×6
V6   niche='assumption-breaking' / 'N0' / 'N11' / 'n2' / ''  → exit 3 · V6 · hypotheses[0].niche ✅×5
V15  两个 niche 第二个全 active                       → exit 3 · V15 · hypotheses[1].niche    ✅
     首 niche 全非 elite（killed）                    → exit 3 · V15                          ✅
合法反例（全部 exit 0）：island=local；generation=0；niche='N2 '（尾空格）；两个 niche 各有 elite；
     同 niche 一 elite 一 active；hypotheses=[]；niche 非法时不产生幽灵 V15（只报 V6）        ✅×7
```

脚本：`/tmp/verify/w2/gen.py`。**结论：V13/V14/V15 与 V6 扩展逐条可拦，路径与规则号正确；
`generation` 的布尔与浮点也被正确拒绝（`isinstance(value,bool)` 守卫有效）。**

### 5.3 「测试不再硬编码规则数」——注入第 16 条规则的实验

**方法：** 副本目录注入可触发的 `V16`（`literature[]` 显式为空即违规），并按其语义补一个自检 fixture。

| 步骤 | 结果 |
|---|---|
| 副本基线 `python3 -m unittest` | `Ran 58 tests … OK` |
| 注入 V16（**不加** selftest fixture） | `FAILED (failures=1)` —— 唯一失败是 `test_selftest_passes`，因为自检要求「每条注册规则都有反例」（`set(RULE_ORDER) - detected == set()`）→ **这是完整性闸门，不是硬编码** |
| 注入 V16 + 对应 selftest fixture | **`Ran 58 tests … OK`（16 条规则）** ⇒ 期望值确实从 `RULES`/`RULE_ORDER` 派生 ✅ |

**结论：** 派生 ✅；残留的硬编码只有 `test_state_check.py:612` 的下限 `>= 12`（m-6）。
Lead 指定的 grep 结果：`grep -n 'range(1\|len(sc.RULES)\|== 1[0-9]' scripts/test_state_check.py`
→ 仅 `612: self.assertTrue(len(sc.RULES) >= 12)`。

### 5.4 三方 14 阶段逐字一致性（独立脚本，非复述）

`/tmp/verify/rw_compare.py`：解析 `SKILL.md §0`（取第 4/5 列）、`policy §5`（第 2/3 列）、
7 个 `phase-*.md` 的读写表（3 列），按 `R<n>` 归并后**逐字比较**：

```
逐字相同阶段: 14/14  不一致: ['R1']
```

- `R1` 只在 SKILL §0（policy §5`:350`「R1 不占行」）—— 设计选择。
- **R4/R6 本轮改动的新值三处一致、且没有错位到「读」列**：
  `R4 读=hypotheses ｜ 写=hypotheses[].niche / hypotheses[].island / hypotheses[].status`；
  `R6 读=hypotheses / uncertainties / failures ｜ 写=hypotheses[].generation / hypotheses[].status / failures`
  （`SKILL.md:69—71`、`policy:364—366`、`phase-r3-r6:446—448`）。
- R5 新值三处一致：`读=hypotheses ｜ 写=literature / evidence(kind=literature)`。

### 5.5 机械校验（自己跑，快照 `aec42b8`）

| # | 项 | 命令 | 结果 |
|---|---|---|---|
| 1 | 相对链接（去围栏） | `/tmp/verify/links.py` | **408 条，0 断链** ✅ |
| 2 | 废弃词 | spec/仓库既有命令（`deprecated-terms.txt` 全量正则） | **exit 1，0 命中** ✅ |
| 3 | JSON | `json.load(templates/research-state.template.json)`、`docs/refs/index.json` | 合法 ✅ |
| 4 | 索引 | `python3 scripts/refs_index.py --check` | exit 0 ✅ |
| 5 | 单测 | `python3 -m unittest discover -s scripts -p "test_*.py"` | **114 tests OK** ✅（Wave 1 为 104，+10） |
| 6 | validator 自检 | `python3 scripts/state_check.py --selftest` | exit 0 ✅（标签见 n-1） |
| 7 | 模板 | `state_check.py templates/research-state.template.json --check` | exit 0 ·「V1—V15 全部通过」✅ |
| 8 | 规则清单 | `state_check.py --list-rules \| wc -l` | **15** ✅ |
| 9 | examples + templates linter | 默认档逐文件 | 9/9 硬违规 0 ✅ |

### 5.6 找碴项（Lead 指定的四项）

| 项 | 结论 | 证据 |
|---|---|---|
| **①B0—B8 与 R3—R6 双流程，作用域裁决是否够** | **不够** → M-3。给出 6 个会误读的段落（`:231`「推荐 shortlist（3—5 个）」、`:209—218` B5.4 优先级表、`:272`「挑选 1—3 个进入 R8」、`:32` B0 产出列、`:177` shortlist 门槛、`:148`「强制，不可跳过」），全部出现在 R 段之前 | §1 M-3 表 |
| **②Search 期不看 venue fit 是否有漏洞** | **有两处**：㈠ `SKILL §4:666—685` 仍把 R3—R6 描述成含 B5「创新性/可行性/重叠度 + 推荐优先级」的旧流程（M-2）；㈡ `phase-r3-r6:436` 的括注「`venue-standards` 只在 R12/R13 生效」与 `roles.md:15` / `venue-standards.md:72` / `SKILL.md:323`（会议审稿人在 **R3—R6** 生效）冲突（m-5）。未发现「优先做更容易中的」这类字面表述 | §2 m-5、§1 M-2 |
| **③QD archive 与 B5 shortlist 是否互斥** | **互斥，且 B5/B6 仍在做「筛选到 3—5 个」**：`:231`「推荐 shortlist（3—5 个）」 vs `:382`「**禁止** 21 ideas → 打分 → Top-3 → 丢掉其余。改为每个 niche 留一个 elite」 | §1 M-3 a |
| **④`island` 五值与 spec §1 图 P1—P4 是否一一对应** | **不对应**：spec §1 图有 **P1—P6**，§2 只给 4 islands，§3 枚举 5 值（P1—P4+local）→ P5/P6 无 island 值；phase 图同样并排画出 P1—P6 与「islands 4（P1—P4）」 | §1 M-6 |

### 5.7 「已知未做」清单核对

| Lead 声明 | 核实 |
|---|---|
| Wave 3：角色库替换 / venue 全量后移 / R12 拆 pre-post / R13 artifact 审计 | **属实**，未计缺陷（本轮只核到它们未被提前动） |
| 「`phase-r2-r5` 的 field grammar / occupancy map **仍是骨架**」 | **不属实** —— 两节已被删除（§1 M-1） |

---

## 6. 未覆盖项与验收限制

1. **未评审发现层的科学正确性**（六条 escape 轨的提问法是否真的能产生范式 idea、五维距离的度量是否合理）——
   本轮只核「契约 → 实现 → 文档」一致性。
2. **未核 spec 引用的外部系统**（Co-Scientist / FunSearch / AlphaEvolve 等）：Wave 1 spec 已声明
   由用户提供、未经仓库核实；本环境无外网（`web_fetch`/`web_search` 不可用），不做外部核验。
3. **未逐行评审 `B0`—`B8` 的检索纪律内容**（spec §6 声明「B5 审核与文献纪律一字不动」），
   只核它与新流程的互斥性。
4. 本报告未修改任何被审文件；未 `git commit`。唯一写入：`docs/verify-r-wave2.md`。

---

## 7. 修复清单（按优先级）

| 优先级 | 动作 | 文件:行号 |
|---|---|---|
| 1 | 恢复 `field grammar` / `occupancy map`，或改 `SKILL.md:67` 的 R2 宣称 | `phase-r2-r5:214`（插入点）、`SKILL.md:67` |
| 2 | 补 `island` / `generation` 到 §3.4，`niche` 行改 N1—N10 | `research-state-policy.md:189—193`（在 `:193` 后插入两行） |
| 3 | 重写 SKILL §4 的 R3—R6 段 + §7 追加「为什么两阶段 fitness」 | `SKILL.md:666—685`、`§7` |
| 4 | 归档 / 改写 `B5.4`、`B6`、`B8` 的 shortlist 机制 | `phase-r3-r6:209—218 / :231 / :272` |
| 5 | 替换 `B8` 的旧 schema state 片段为 `research-state.json` 同形片段 | `phase-r3-r6` §B8 |
| 6 | 裁决 P1—P6 vs 4 islands 并写出映射（或扩枚举） | `docs/r-architecture-wave2-spec.md:20—23 / :45 / :65`、`phase-r3-r6:322—327 / :349` |
| 7 | MINOR m-1—m-6 | 见 §2 |
| 8 | NIT n-1—n-3 | 见 §3 |

**一句话总体结论：需修后交付** —— 新增闸门（V13—V15 + V6 扩展）与三方口径经独立 fixture/脚本验证**全部达标**，
但 Wave 2 的**接线层有两处空洞（SKILL §4/§7、policy §3.4）**、**旧发现流程仍与新流程同时可执行**
（含一个过不了 `state_check` 的示例 state 片段）、**少了一整节 R2 内容**，且 spec 自身的
P1—P6 与 4 islands 互相矛盾；这些都是行级到段落级修复，修完即可交付。

---

## 8. 增量复核（修复后收官确认）

**快照：** `4fccc32`（工作树干净；`docs/verify-r-wave2.md` 已被该提交一并提交）。
下面所有命令在该快照上执行。**只读**：本次仅向本文件追加本节。

### 8.1 逐条确认（6 MAJOR + 6 MINOR + 3 NIT）

| 项 | 声明 | 现值（文件:行号） | 判定 |
|---|---|---|---|
| **M-1** | 从 `git show f8dda53:…` 取回被吞的 31 行，恢复为 `## R2.1` / `## R2.2` | `phase-r2-r5-field-mapping-retrieval.md:214`（`## R2.1 field grammar …`）、`:229`（`## R2.2 occupancy map（Wave 3 深化）（占用图）`），位置在 `:247` 的 `## R5.` 之前 | ✅ **达成**，且**逐行等于原文**（见 §8.2） |
| **M-2** | SKILL §4 R3—R6 重写；§7 新增第 15 条 | `SKILL.md:666—685`：R3 双轨（两轨产生候选前不得互看）→ R4 五维聚类 → **QD archive** → R5 共演化 → R6 进化；含「预算：默认 4 islands（P1—P4；P5/P6 按需）× 每岛 3—6；进化 ≤2 轮」与「两阶段 fitness：Search 期不看 venue fit」；**明写「不再产出 shortlist（3—5 个）——该概念在 Wave 2 起作废」**（`:680`）。`§7` 新增 `:956`「15. 为什么两阶段 fitness？」（含 QD archive / V15 / EIG 只作记录） | ✅ **达成** |
| **M-3** | 作用域裁决注点名 B5.4/B6/B8；三节各加横幅 | 注 `:16—22` 点名 `B5.4`/`B6`/`B8` 并指向 R4.2/R6.3 与模板；横幅：`:154`（**B5 节**）、`:232`（B6）、`:283`（B8），B6 横幅含「shortlist 这个概念在 Wave 2 起作废」（`:233`） | ⚠️ **基本达成**：横幅挂在 **B5 父节**（`:152`）而非 `### B5.4`（`:217`）本身 → §8.6 MINOR-1 |
| **M-4** | B8 片段整块换成 Research World Model 片段，「再喂一次 validator，**应为 exit 0**」 | 片段 `:293—305`（围栏内 `:294—304`）顶层键 `phase / hypotheses / failures / literature / uncertainties`，`hypotheses` 带 `niche=N2 / island=P2 / generation=0 / status=elite` ✅；**但实测 `exit=3`，规则 `V4`（`failures[0]` 未被任何 `claims[].known_flaws` / `experiments[].known_flaws` 引用）**；且 `F1.referenced_by=["H2"]` 用了 **H id**，而 policy §3.7 规定该字段只收 `C` / `X` id | ❌ **未达成（exit 3 ≠ 0）→ MAJOR（见 §8.3）** |
| **M-5** | policy §3.4 补 `island` / `generation`；`niche` 行改 N1—N10 | `research-state-policy.md:193`（`niche` = `N1`—`N10` 之一，V6 强制）、`:194`（`island` = `P1`—`P6` / `local`）、`:195`（`generation` = 整数 ≥ 0） | ⚠️ **达成**，但两行**缺「必填」列**（3 列 vs 表头 4 列）→ §8.6 MINOR-2 |
| **M-6** | `island` 澄清为 `P1`—`P6`/`local`，`P1`—`P4` 默认、`P5`/`P6` 按需；三处同步；**不改用户默认预算** | `state_check.py:109` `ISLANDS=("P1"…"P6","local")`、`:129` RULES 文本；spec `:45`（**默认 4** + P5/P6 按需说明）、`:65`、`:78`（V13 `{P1..P6, local}`）；`policy:194`、`:312`；`phase-r3-r6:344` 预算表；`SKILL.md:681` 段；模板 `:166` `island="P2"`（新枚举下合法） | ✅ **达成**（五处一致，默认值未动）——残留两处 5 值旧写法见 §8.4 |
| m-1 | policy §4 **V6 行扩展** | `policy:305` **仍是**「每条 `H` 的 `niche` 非空」——未扩展（只有 §3.4 `:193` 改了） | ❌ **未达成** → MINOR |
| m-2 | V11—V15 行列归位 | `policy:310—314`：规则文本回到「规则（逐字）」列，「硬」回到「违规」列 ✅ | ✅ 达成 |
| m-3 | 执行契约同步 V1—V15 | `policy:323—324` **仍是**「列出 V1—V10 与判据」「内置自检，V1—V10 全覆盖」 | ❌ **未达成** → MINOR |
| m-4 | `state_check.py` docstring 同步 V1—V15 | docstring **三个范围并存**：`:2` 标题「V1—**V12**」、`:18`「V1—**V12** 全覆盖」、`:22—32` 规则清单仍只到 **V10**、`:46` 判据补充写「V1—**V15** 之外不新增」；`:6` 契约来源仍只引 `r-architecture-wave1-spec.md` | ⚠️ **部分** → MINOR |
| m-5 | R6.3 venue 措辞消歧 | `phase-r3-r6:432—437`：「**消歧：** 会议审稿人角色在 R3—R6 仍可用于 concept 级快筛，但**不得**用「会议适配度」排序候选；`venue-standards` 作为**排序依据**只在 R12/R13 生效」 | ✅ 达成 |
| m-6 | 测试下限改为 `RULES` 与 `CHECKS` 集合相等 | `test_state_check.py:622—623`：`assertTrue(len(sc.RULES) >= len(sc.CHECKS))` + **`assertEqual(set(sc.RULES), set(sc.CHECKS))`** | ✅ 达成（`:622` 冗余但无害） |
| n-1 | selftest 标签按数值排序 | `state_check.py:1114`：`max(RULE_ORDER, key=lambda r: int(r[1:]))` | ✅ 达成 |
| n-2 | V15 补 2 个显式合法反例 | `test_state_check.py:477` `test_v15_two_niches_each_with_elite_is_clean`、`:482` `test_v15_elite_counts_even_with_active_sibling` | ✅ 达成 |
| n-3 | 旧 niche 名登记 deprecated | `deprecated-terms.txt` 末节新增 `assumption-breaking` / `new-formulation` / `remote-theory-transfer` / `benchmark-inversion` 四条；扫描仍 exit 1（0 命中） | ✅ 达成（**故意不登记 `impossibility` 是对的**：它作为 P6 的合法标签出现在 `phase-r3-r6:344`，登记会造成假阳性） |

### 8.2 M-1：恢复块与原文逐行比对（不只是「标题回来了」）

**方法：** `git show f8dda53:<file>` 取 `### field grammar` 到 `### R5 共演化检索` 之间
（原文 31 行），与当前文件 `## R2.1` 到 `## R5.` 之间的块（33 行）做 `difflib` 逐行比对；
标题行单列（因为要求改名）。

```
原文块行数=31  恢复块行数=33   序列相似度=0.9845
diff：
  - ### field grammar `{P, A, R, D, O, M, T, E}`   →  + ## R2.1 field grammar `{P, A, R, D, O, M, T, E}`
  - ### occupancy map（占用图）                     →  + ## R2.2 occupancy map（Wave 3 深化）（占用图）
  +（块尾追加 `---` + 空行，共 2 行）
```

**结论：正文 28 行（field grammar 说明 + 8 行文法表 + occupancy map 说明 + 拥挤度代码块 +
negative space 规则）逐字一致；差异仅为两处标题改名与 2 行分隔符。** ✅ 恢复无二次损失。

### 8.3 M-4：B8 片段喂 validator 的实测结果

```bash
cd research-idea-pipeline
python3 - <<'PY'
import re,json,subprocess,sys
txt=open('references/phase-r3-r6-discovery.md',encoding='utf-8').read()
seg=txt[txt.index('## B8'):]
json.dump(json.loads(re.findall(r'```json\n(.*?)\n```',seg,re.S)[0]),
          open('/tmp/b8_new.json','w'),ensure_ascii=False)
PY
python3 scripts/state_check.py /tmp/b8_new.json --json
#   exit = 3
#   violations = [("V4", "failures[0]", "未被任何 claims[].known_flaws 或 experiments[].known_flaws 引用")]
#   顶层键 = ['phase','hypotheses','failures','literature','uncertainties']（无 claims / experiments）
```

**为什么**：片段含 `failures[F1]` 却没有 `claims[]` / `experiments[]`，V4 要求每条 `F` 被
`claims[].known_flaws` 或 `experiments[].known_flaws` 引用 → 必判 3。另外
`F1.referenced_by: ["H2"]` 用的是 Hypothesis id，policy §3.7 规定该数组只收 `C`/`X` id。
**修法（二选一，一行级）：**
①把片段补成**可跑的最小完整 state**：加 `claims:[{…, "known_flaws":["F1"]}]` 与
`experiments:[{…, "known_flaws":["F1"]}]`，并把 `referenced_by` 改成 `["C1","X1"]`；
②或删掉片段里的 `failures` 条目，并在片段上方标注「**节选，不可直接跑 validator**；
完整骨架见模板（模板 exit 0 已实测）」。

### 8.4 M-6：枚举五处一致性 + 残留旧写法

| 位置 | 现值 | 一致 |
|---|---|---|
| spec §2 表 | `:45`「**默认 4**；P5/P6 按需启用…不占默认预算」 | ✅ |
| spec §2.3 V13 | `:78` `{P1..P6, local}` | ✅ |
| `state_check.py` | `:109` `("P1","P2","P3","P4","P5","P6","local")`；`:129` RULES 文本同 | ✅ |
| policy §3.4 / §4 V13 | `:194`、`:312` 同 | ✅ |
| phase 预算表 | `:344`「**默认 4**（P1—P4…）+ P5/P6 按需启用…启用即上调，须说明理由」 | ✅ |
| SKILL §4 R3—R6 | `:678`「默认 4 islands（P1—P4；P5/P6 按需启用）× 每岛 3—6」 | ✅ |
| 模板 | `:166` `"island": "P2"`（新枚举下合法） | ✅ |

**默认值未被改动** ✅（用户拍板的「4 islands × 3—6」在三处（spec/policy/phase）都保留为默认）。
**残留的两处 5 值旧写法（新发现）：**

| # | 位置 | 原文 | 影响 |
|---|---|---|---|
| 甲 | `phase-r3-r6-discovery.md:338` | 「5. 每轨的候选都写 `island`（**`P1`—`P4` / `local`**）与 `generation: 0`（V13/V14 强制）」 | 同一文件内与 `:344` 的预算表（含 P5/P6）**自相矛盾**；按此写，P5/P6 候选会被误标 |
| 乙 | `state_check.py:545` | `def _v13(...): """V13：island ∈ {P1, P2, P3, P4, local}。"""` | docstring 与 `:109` 的 `ISLANDS` 不一致（代码正确，文档滞后） |

### 8.5 机械面复跑（快照 `4fccc32`）

| # | 项 | 结果 |
|---|---|---|
| 1 | 相对链接（去围栏） | **410 条，0 断链** ✅ |
| 2 | deprecated（含新增 4 条旧 niche 名） | **exit 1，0 命中** ✅（`assumption-breaking` 等仅存在于 `.py` 测试/自检，不在扫描范围） |
| 3 | JSON（模板 + refs 索引） | 合法 ✅ |
| 4 | 单测 `unittest discover -s scripts` | **116 tests OK** ✅（上一轮 114，+2 = V15 两个合法反例） |
| 5 | `state_check --selftest` | exit 0 ✅（标签已按数值排序） |
| 6 | 模板 `--check` | exit 0 ✅ |
| 7 | `--list-rules` | 15 条 ✅ |
| 8 | examples + templates linter | 9/9 硬违规 0 ✅ |

### 8.6 新发现（本轮修复引入 / 未覆盖）

| # | 级别 | 现象 | 文件:行号 | 修法 |
|---|---|---|---|---|
| 1 | **MAJOR** | **M-4 未达成**：B8 的新 state 片段实测 **exit 3（V4）**，而该节同时写「写回后**必须**跑 `state_check.py`，硬违规须为 0」；且 `referenced_by` 用了 H id | `phase-r3-r6-discovery.md:293—305`（片段，含围栏）、`:308—309`（强制跑闸门） | 见 §8.3 的两个修法 |
| 2 | MINOR | `island` 硬规则仍是 5 值写法，与同文件 `:344` 及 spec/policy/validator 的 7 值枚举矛盾 | `phase-r3-r6-discovery.md:338` | 改为「`island`（`P1`—`P6` / `local`；`P1`—`P4` 默认，`P5`/`P6` 按需）」 |
| 3 | MINOR | **policy §4 的 V6 行未扩展**（仍是「非空」），而 §3.4 `:193` 与 `state_check.py` 已强制 N1—N10；policy §4 自称「该表与 `state_check.py` 一一对应」 | `research-state-policy.md:305`（对照 `:294` 的对齐声明） | 改为「`niche` 非空**且 ∈ `N1`—`N10`**（V6 强制）」 |
| 4 | MINOR | **执行契约仍写 V1—V10**（`--list-rules` / `--selftest` 两行） | `research-state-policy.md:323—324` | 改为 `V1—V15` |
| 5 | MINOR | `state_check.py` docstring **三个范围并存**（标题 V1—V12、清单 V1—V10、判据 V1—V15），契约来源仍只引 Wave 1 spec | `scripts/state_check.py:2`、`:18`、`:22—32`、`:46`、`:6` | 统一为 V1—V15；契约来源补 `r-architecture-wave2-spec.md` §4 |
| 6 | MINOR | `policy §3.4` 新增的 `island` / `generation` 两行**缺「必填」列**（3 列 vs 表头 4 列），渲染时说明文字落到必填列 | `research-state-policy.md:194—195` | 补 `✅` 列（与 `:193` 的 4 列对齐） |
| 7 | MINOR | **B5.4 自身无横幅**：横幅挂在 B5 父节（`:154`），而 `### B5.4 优先级判定规则`（`:217`）——本轮最冲突的排名表——读者可能只看到排名表 | `phase-r3-r6-discovery.md:154`、`:217` | 在 `### B5.4` 下再加一行同名横幅 |
| 8 | MINOR | 现行规则仍出现「shortlist」（Wave 2 已宣布作废）：SKILL §0.1 锚点表 R3—R6 行与 §6 自检项 | `SKILL.md:204`、`:818`（`:680` 是「已作废」声明，正确） | 改为「population / QD archive」 |
| 9 | NIT | 其它文件的 shortlist 残留：`phase-r2-r5:151`（A 段检索门槛）、`project-layout.md:534`（落盘职责表）、`phase-r8-evidence-contract.md:48`（B5 门槛继承）、`examples/example-b-to-c-d-e.md:27/29`、`templates/INDEX.md:90` | 见左 | 前两处建议本轮顺手改；examples / templates 未列入 Wave 2 §6 文件地图，可登记 Wave 3 |
| 10 | NIT | `_v13` docstring 仍是 5 值 | `scripts/state_check.py:545` | 与 `:109` 对齐 |

### 8.7 收官结论

**仍需修（1 项 MAJOR + 6 项 MINOR，均行级）。** 6 项 MAJOR 中 **5 项完整落地**
（M-1 逐行等于原文、M-2 §4/§7 已接 Wave 2、M-3 点名+横幅、M-5 §3.4 已补、M-6 五处一致且默认预算未动），
**M-4 未达成**（片段 exit 3 ≠ 0）；MINOR/NIT 清单中 **V11—V15 列归位、R6.3 消歧、测试集合相等、
selftest 数值标签、V15 合法反例、deprecated 旧 niche 名 6 项已落地**，
**V6 行扩展、执行契约 V1—V15、docstring 同步 3 项未落地或部分落地**。
机械面全绿（410 链接 0 断链、116 测试、deprecated 0、模板 0、linter 0）。

按你的闸门（「只剩 NIT 才可直接说可交付」），当前**还差 M-4（必须修，否则示例照抄会被自己的闸门判 3）
与 6 项 MINOR**；其中 MINOR-2/3/4/5/6/7 各自都是一行到一行半。**修完这 7 处即可交付。**

---

## 9. 最后一轮增量确认（7 处待修 + NIT 的收官核验）

**快照：** `8ef4737`（工作树干净；其上还有 `716dc02`、`d3e3ddc` 两个 shortlist 口径提交）。
> **行号口径说明：** 本节行号对应 `8ef4737`；§2 / §8 的行号对应它们各自的快照
> （`aec42b8` / `4fccc32`），修复过程中行号有位移属正常（例如 policy 的 V6 行 `:303`→`:305`、
> 「一一对应」声明行 `:294`→`:296`）。
**纪律：** 本次仅向本文件追加本节；未改任何被审文件、未 commit。

### 9.1 七处待修 + NIT 逐条确认

| # | 声明 | 现值（文件:行号） | 判定 |
|---|---|---|---|
| 1 | **M-4**：B8 片段补 `claims` + `experiments`（各带 `known_flaws:["F1"]`，`referenced_by` 改 `["C1","X1"]`），`state_check --check` → exit 0 | 片段 `phase-r3-r6-discovery.md:293—305` 顶层键 = `phase / claims / hypotheses / experiments / failures / literature / uncertainties`；`claims[0].known_flaws=["F1"]`、`experiments[0].known_flaws=["F1"]`、`failures[0].referenced_by=["C1","X1"]`。**我自己复跑（不采信自述）：`--check` exit 0、`--json` exit 0**，汇总行「`[ok] 0 处硬违规：V1—V15 全部通过；claims=1…experiments=1…failures=1…`」 | ✅ **达成** |
| 2 | `phase` 硬规则 5 的 island 枚举 → `P1`—`P6`/`local` | `phase-r3-r6-discovery.md:348`：「每轨的候选都写 `island`（`P1`—`P6` / `local`；**默认启用 `P1`—`P4`，`P5`/`P6` 按需**）与 `generation: 0`（V13/V14 强制）」 | ✅ **达成** |
| 3 | `B5.4` **自己**加横幅（不落到父节） | `:217` `### B5.4 优先级判定规则` → `:219` 横幅「⚠️ **本节已被 R4.2 取代**：这张排名表**不得**用来筛到 3—5 个候选；筛选动作走 **QD archive**（每个 niche 留一个 elite）。它只作为 **R3 的 concept 级快筛**输入。」→ `:223` 排名表。横幅在 **B5.4 节内**，且在排名表**之前**；父节 B5 的横幅（`:154`）保留 | ✅ **达成** |
| 4 | `policy` 的 **V6 行** → 「非空**且 ∈ N1—N10**」 | `research-state-policy.md:305` **仍是**「每条 `H` 的 `niche` 非空」；典型反例列也只有 `"niche": ""` | ❌ **未达成 → MINOR-A** |
| 5 | `policy` **执行契约** → `V1—V15` | `research-state-policy.md:323`「列出 **V1—V10** 与判据（本表与它逐字一致）」、`:324`「内置自检，**V1—V10** 全覆盖」 | ❌ **未达成 → MINOR-B** |
| 6 | `policy §3.4` 的 `island`/`generation` 补「必填 ✅」列 | `:194` island、`:195` generation 均为 **4 列**（与表头 `字段/取值或类型/必填/说明` 对齐），必填列为 `✅` | ✅ **达成** |
| 7 | `state_check.py` docstring 统一 `V1—V15`；`_v13` docstring → 7 值 | 范围串已统一：`:2` 标题、`:18` usage、`:46` 判据、`:398` 节注释、`:880` argparse description、`:889—890` `--selftest`/`--list-rules` help、`:933` 自检注释 **全部 V1—V15**；`_v13` docstring `:545` = `island ∈ {P1..P6, local}（默认开启 P1—P4，P5/P6 按需）` ✅。**但规则清单块 `:23—32` 仍只列 V1—V10**（其 V6 行 `:28` 仍写「非空」） | ⚠️ **达成（范围串）/ 部分（清单块）→ 见 MINOR-A 证据 3、NIT-2** |
| NIT | `shortlist` 操作句全部改成 population / QD archive；只保留「已作废/被取代/点名」引用；`deprecated-terms.txt` 登记保留 | Lead 指定的过滤 grep `grep -rn 'shortlist' --include='*.md' . \| grep -vE '作废\|被取代\|点名\|本节已被\|deprecated'` → **0 行输出**；全仓只剩 `phase-r3-r6-discovery.md` 2 处，均为「shortlist 这个概念在 Wave 2 起作废」类说明 | ✅ **达成** |

### 9.2 机械面复跑（快照 `8ef4737`）

| # | 项 | 结果 |
|---|---|---|
| 1 | 相对链接（去围栏） | **410 条，0 断链** ✅ |
| 2 | deprecated-terms | **exit 1，0 命中** ✅ |
| 3 | JSON（模板 + refs 索引） | 合法 ✅ |
| 4 | `python3 -m unittest discover -s scripts -p "test_*.py"` | **116 tests OK** ✅ |
| 5 | `state_check --selftest` | exit 0 ✅ |
| 6 | 模板 `--check` | exit 0 ✅ |
| 7 | examples + templates 默认档 linter | 9/9 硬违规 0 ✅ |
| 8 | `--list-rules` | 15 行 ✅（第 6 行文本见 MINOR-A） |
| 9 | B8 片段（独立复跑） | `--check` exit 0 / `--json` exit 0 ✅ |

### 9.3 剩余项（0 MAJOR）

| # | 级别 | 现象 | 文件:行号 | 修法（一行级） |
|---|---|---|---|---|
| A | **MINOR** | **V6 规则文本三处未同步**（声明已扩展，实际未改）：㈠ `policy §4:305` 仍「非空」；㈡ `state_check.py` 的 `RULES["V6"]` 仍「每条 H 的 niche 非空」——**`--list-rules` 第 6 行就打印这个旧文本**；㈢ docstring 规则清单 `:28` 同旧文本。而 policy §4`:296` 声明「`state_check.py` 与该表一一对应」、`§4` 执行契约声明「本表与它逐字一致」——两处声明因此不成立；Wave 2 spec `§6:116` 明确要求「§4 … 扩展 V6」 | `research-state-policy.md:305`、`scripts/state_check.py:28`（docstring）、`scripts/state_check.py` 的 `RULES["V6"]` | 三处文本统一为「`niche` 非空**且 ∈ `N1`—`N10`**（V6 强制）」，反例列补 `"niche": "assumption-breaking"` |
| B | **MINOR** | **policy 执行契约两行仍 `V1—V10`**，与脚本实际行为（`--list-rules` 15 条、help 文本已写 V1—V15）矛盾 | `research-state-policy.md:323—324` | 改为 `V1—V15` |
| C | NIT | policy 另有 **9 处 `V1—V10` 范围标签**：文件标题、导言、`:17` 模板句、`:342—343` 边界 1、`:422` 接口表、`:423` 模板行、`:430` 维护规则 3、`:454` §3.11 更正句 | `research-state-policy.md:1 / :4 / :17 / :342 / :343 / :422 / :423 / :430 / :454` | 批量替换为 `V1—V15`（纯文本，无行为影响） |
| D | NIT | `state_check.py` docstring 规则清单块仍止于 V10，与同一 docstring 的 V1—V15 标题并存（清单块从未扩写，不是本轮引入） | `scripts/state_check.py:23—32` | 补 V11—V15 五行 |
| E | NIT | 契约来源只引 Wave 1 spec（V1—V12 在其中），未引 Wave 2 spec §4（V13—V15 的定义处） | `scripts/state_check.py:6—7` | 补一行 `docs/r-architecture-wave2-spec.md` §4 |

### 9.4 收官结论

**0 MAJOR。** 7 处待修中 **5 处完整落地**（M-4 已独立复跑 exit 0、phase 硬规则 5、B5.4 节内横幅、
§3.4 四列对齐、docstring 范围串统一 + `_v13` 7 值），**2 处未落地**（policy V6 行、policy 执行契约），
另有 3 项 NIT（policy 范围标签 / docstring 清单块 / 契约来源）。`shortlist` 操作句已清零，
机械面全绿（410 链接 0 断链、116 测试、deprecated 0、模板 0、linter 0）。

**按你的闸门（「只剩 NIT 才能直接说可交付」）：仍需修 —— 2 项 MINOR（A、B 合计 3 行文本）+ 3 项 NIT。**
但这 2 项 MINOR 是**纯文档文本同步**：V6 的**实际闸门行为正确**（我复跑 `niche="assumption-breaking"`
→ exit 3 · V6 · `hypotheses[0].niche`；`niche="N7"` → exit 0），模板/测试/CLI 行为均无缺陷。
因此：**机制层已可收口**；若你把这 3 行并入 Wave 3 首轮（或现在顺手改掉），
Wave 2 就可以标记完成并开 Wave 3 —— 我这边没有其它阻断项。
