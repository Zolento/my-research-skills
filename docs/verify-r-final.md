# R 架构三波总收官：跨波一致性审计报告

**验收对象：** 分支 `research-idea-pipeline-dev`，快照 `61ad5c3`（工作树干净）。
**审计范围：** Wave 1（状态载体/闸门）+ Wave 2（发现层）+ Wave 3（角色层）**波与波之间**的一致性。
**契约：** [`docs/r-architecture-wave1-spec.md`](r-architecture-wave1-spec.md)、[`wave2`](r-architecture-wave2-spec.md)、[`wave3`](r-architecture-wave3-spec.md)。
**验收者：** teammate `verifier`（只读；本文件是本次审计唯一写入的文件）。
**审计时间：** 2026-10-06 ｜ 行号相对仓库根 `research-idea-pipeline-dev/`。

**立场声明：** 不采信任何自述。每条结论附 文件:行号 与可重跑命令；
「扫过没问题」的项在 §4 逐条列出，以区分「真的没问题」与「没扫」。

---

## 0. 结论摘要

| 级别 | 条数 | 说明 |
|---|---|---|
| **MAJOR** | **2** | ①`claims[]`（claim graph）**无创建归属**，且 R7/R8 在 R12 之前就读它；②**V4 与 R6/R7/R13 的写集冲突**（写 `failures[]` 却无权写 `known_flaws`，收工清零不可能） |
| MINOR | 3 | `contract` 无读者；R9.4 双写 `failures[]` 但读写行缺该字段；R7 的审计对象由后置的 R8 产出 |
| NIT | 3 | `decision` 终端写无读者说明；五元组字面量 7 处复述（维护风险）；V11/V7「键缺失即不判」的宽松口径未写明 |

**总收官结论：仍需修（2 项 MAJOR，均为「文档级归属/写集」修复，非新功能缺陷）。**
三波各自的验收结论保持有效：Wave 1（状态与闸门）、Wave 2（发现机制）、Wave 3（角色层）
的**单波内部**均已达标 —— 机械面全绿（415 链接 0 断链、116 测试、deprecated 0、模板 0、
linter 0、`--list-rules` ↔ policy 15 条逐字一致、三方 14/14 逐字相同）；
**但把三波接起来看，状态机的「谁产出 claim」与「谁写 known_flaws」两个环节没有闭环**，
导致 V1—V4 这四条闸门在最坏情况下要么永不触发、要么必然触发（无论执行者怎么做都过不了收工检查）。

---

## 1. MAJOR

### M-1 `claims[]`（claim graph）**没有创建归属**，且第一个消费者排在唯一产出者之前

**现象（三段证据）：**

1. **唯一写明「写出 claim graph」的是 R12 的 D1**：
   `phase-r12-narrative.md:137—141`：「## D1. Claim Graph … **动作：** 按固定节点 ID 写出 claim graph。」
   但 **R12 的读写行只写 `narrative_view`**：`phase-r12:846`、`research-state-policy.md:374`、
   `SKILL.md:77`（三层逐字一致，14/14 检查器覆盖）。
2. **R12 自己的 pre/post 拆分把 claim graph 夹死了**：
   `phase-r12:824—845` 的 pre/post 表 —— **pre**「只写『若 `H` 被验证，可能成立的 thesis 是…』；
   产出一份预期叙事草稿」（`:830`）；**post**「**只读已核实**的 `claims[]` / `evidence[]` …」
   （`:831`）。**两处都没有授权创建 `claims[]`**；而且 `D0—D9` 与 pre/post 之间**没有任何映射说明**
   （`grep -nE 'pre.*D[0-9]|D[0-9].*pre' phase-r12-narrative.md` → 无）。
3. **消费者排在产出者之前**：`policy §5` 的 R7 行（`:369`）**读 `claims`**、R8 行（`:370`）
   **写 `claims[].contract`**（挂契约必须先有 claim），而按 spec §1 的双循环图与 `policy §1` 的
   顺序，**R7 / R8 都在 R12 之前**（assurance loop 挂在 R2 下 → 汇入 R9 → … → R12）。
   `phase-r8:227` 更进一步：「写不出可判定 kill rule 的 claim **不得进入 R9**」——
   即 R8 阶段就要对 claim 做判定。

**证据（命令）：**

```bash
cd research-idea-pipeline
grep -rn 'claims\[\]' references/phase-*.md | grep -E '新增|创建|建立|产出|生成'
#   仅 phase-r0-contract.md:69（禁止 R0 产出 claim）与 phase-r12:831（post 只读）
sed -n '137,142p' references/phase-r12-narrative.md
sed -n '824,846p' references/phase-r12-narrative.md
grep -n 'claims' references/research-state-policy.md | sed -n '1,3p'   # §5 R7/R8 行
grep -n '写出 claim graph' references/phase-r12-narrative.md
```

**影响（与 item 2 的联动）：** `V1`（`C.falsifier` 非空）、`V2`（`C` 的 E 引用必须存在）、
`V3`（无 E 引用必须 `ungrounded`）**在流程上没有产出者**：
执行者若严格按写表执行（R7 只写 assurance/failures/uncertainties、R8 只写 `claims[].contract`…），
`claims[]` 永远是空数组 → V1—V3 永不触发；一旦有人按 `phase-r12:141` 手写 claim graph，
又立刻落到 R7/R8 之前，与三层写表冲突。

**建议修法（二选一，一行到一节）：**
①**归 R8**：把 `claims[]` 的创建并入 R8（证据契约天然以 claim 为单位），三层读写表 R8 行补
「`claims[]`（新建条目 + `contract`）」，并在 `phase-r8` §C1 写明「claim graph 在此建立」，
同时把 `phase-r12:137—141` 的 D1 改为「**复核**（只读 + 校验）claim graph」；
②**归 R12-pre**：把 `D0—D9` 明确划给 pre（其中 D1 建 claim graph），并在 `phase-r12:830` 的
「只能做什么」列加入「写 `claims[]` / `evidence[]` 台账」，同时把 R7/R8 的读改为
「读上一轮 state（首轮 `claims[]` 可为空，则只审计划）」。

---

### M-2 **V4 与 R6 / R7 / R13 的写集冲突**：它们写 `failures[]`，却无权写 `known_flaws`

**现象：** `V4` 要求「每条 `F` 必须被至少一个 `claims[].known_flaws` 或 `experiments[].known_flaws`
引用」；而写 `failures[]` 的三个阶段，写集里**都没有** `known_flaws`。三层读写表逐字一致，
所以这不是某一层漏写，而是三波拼起来后的**规则/流程冲突**。

| 阶段 | 写集（policy §5，三层一致） | 会写 `F` 吗 | 能写 `known_flaws` 吗 |
|---|---|---|---|
| **R6** | `hypotheses[].generation` / `.status` / **`failures`**（`policy:368`） | ✅ `phase-r3-r6:413`「候选被 R6 判 `killed` → `status: killed` 并写 `failures[]`（`kind: deprioritized`）」 | ❌ 写集里没有 |
| **R7** | `assurance` / **`failures`** / `uncertainties`（`policy:369`） | ✅ 攻击面暴露的缺口 | ❌ |
| **R13** | `reviews` / **`failures`** / `experiments[].unexpected`（`policy:375`） | ✅ | ❌ |
| R9 | `experiments`（`policy:371`） | ✅（R9.4 双写） | ✅（经 `experiments[]` 整体写入，`phase-r9-r11:71`） |
| R10 | `repairs` + 执行 `state_delta`（`policy:372`） | — | ✅（`state_delta` 可改 `known_flaws`；`policy:284` 的 `ACCEPTED_LIMITATION` 落点） |
| R14 | `decision` / `repairs[].closure` / 各 `status`（`policy:376`） | — | ✅（同上规则） |

**为什么是硬冲突：** `research-state-policy.md:62`（§1 规则 6）：「**任何写回 state 的阶段，收工前
**必须**跑 `state_check.py`；硬违规未清零，该阶段**不得**宣告完成」；`:294`（§4 结论）：
「任何一条未清零，state 不得作为下一阶段的输入」。于是 **R6/R7/R13 各自收工时，
它们刚写的 `F` 还没被任何 `known_flaws` 引用 → V4 必报 → 这三个阶段永远无法宣告完成**，
除非执行者越权去写 `claims[].known_flaws`（写表没授权，属自创动作）。

**证据（命令）：**

```bash
cd research-idea-pipeline
grep -n 'known_flaws' references/phase-*.md references/research-state-policy.md | grep -E '新增|写入|追加|挂|填|加进'
#   仅 policy:284（ACCEPTED_LIMITATION 落点）—— 没有阶段把「创建 F 时同步挂 known_flaws」写进写集
python3 scripts/state_check.py --list-rules | sed -n '4p'    # V4 判据
sed -n '61,72p' references/phase-r9-r11-experiment-loop.md   # R9.4 双写
sed -n '62p;294p' references/research-state-policy.md        # 收工清零
```

**建议修法（二选一，各自一行）：**
①**扩写集**：在 `policy §5` 的 R6 / R7 / R13 行（连同 `SKILL §0` 与两个 phase 文件的同行）
写列补「+ 把新 `F` 的 id 挂到对应 `claims[].known_flaws` / `experiments[].known_flaws`」——
这与「assurance 不得改 `claims[].status`」不冲突（`known_flaws` 不是 `status`）；
②**改闸门口径**：在 `policy §4` 增一条口径说明「V4 的引用凭证在**同一轮 R10 `state_delta` 执行后**
复核；R6/R7/R13 的收工检查允许 `failures[]` 新增项暂未被引用，但必须在 R10 落 `repairs[]` 时闭合」
—— 并同步 `state_check.py` 的 `--check` 语义（否则脚本仍会判 3）。

---

## 2. MINOR

| # | 现象 | 文件:行号 | 证据（命令） | 建议修法 |
|---|---|---|---|---|
| m-1 | **`contract` 写了但没人读**：R0 写 `contract`，而**没有任何阶段的「读」列收录它**；全仓唯一的消费点是 `phase-r3-r6:362` 的一句 prose（「可在 R0 `contract.constraints` 里写明并降到 2 islands」）。SKILL §0 的 R1 行「读 全部」是唯一隐含覆盖，而 R1 不是阶段（policy §5 不占行） | `policy:363`（R0 写 `contract`）；读列全表见 `:363—376`；消费点 `phase-r3-r6:362` | `grep -rn 'contract' references/phase-*.md \| grep -vE 'phase-r0\|证据契约\|claim'` → 仅 `phase-r3-r6:362` | 在 R3（或 R4/R6）的读列补 `contract.constraints`（R3.1 的缩放到此读取），或在 policy §5 表下注「`contract` 由 R1 常驻读取，不逐阶段列」 |
| m-2 | **`R9.4` 强制双写 `failures[]`，但 R9 的读写行只写 `experiments`**（三层同款）：`phase-r9-r11:63`「失败的实验**必须双写**」、`:193` 自检「(status: failed) 与 `failures[]` 双写」，而 `:207` / `policy:371` / `SKILL:75` 的 R9 写列只有 `experiments` | `phase-r9-r11:61—72`、`:207`；`policy:371`；`SKILL:75` | `sed -n '61,72p;207p' references/phase-r9-r11-experiment-loop.md` | R9 写列补 `failures[]`（三处同改），与 R6/R7/R13 的写法对齐 |
| m-3 | **R7 的审计对象由后置的 R8 产出**：Wave 2/3 冻结的审计时机写「R7 / R8 没有 artifact，**只能审「计划中的证据契约」**」，而「证据契约」是 **R8** 的产物（`policy:370`），R7 在顺序上排在 R8 之前（spec §1 图、`policy §1` 图）→ **首轮的 R7 没有可审对象**，文档未给解释 | `phase-r7:433—437`（审计时机表）、`policy:369—370`；spec §1 图 | `sed -n '433,437p' references/phase-r7-r10-r13-assurance-repair-review.md` | 在 `phase-r7` 的作用域裁决里补一句：「**首轮 R7 审的是 R3—R6 的候选与计划（无契约）**；`claims[].contract` 由 R8 建立后，从第二轮起 R7 审契约」——或把 assurance loop 的顺序明确成 R8 → R7 |

---

## 3. NIT

| # | 现象 | 文件:行号 | 建议 |
|---|---|---|---|
| n-1 | `decision`（R14 写）没有任何下游读者（终端产物）；`narrative_view`（R12 写）也没有显式读者（R13/R14 只写「全 state」隐含覆盖）。这**符合设计**（视图 / 终局决策），但表里没有一句说明，机械比对会把它列为「僵尸字段」 | `policy:374`、`:376`、`:467—469`（§3.11 槽位表） | 在 §5 表下加一句：「`narrative_view` / `decision` 是**终端产物**，由 R13/R14 的『全 state』隐含读取，不要求显式读者」 |
| n-2 | 五元组字面量 `(Attack, Target Claim, Alternative, Discriminating Test, Kill Condition)` 在全仓**逐字复述 7 处**（spec、phase-r7、scoring-policy、roles、SKILL×2…）。当前**完全一致**，但这正是 SKILL §8 A5 的维护风险面 | `grep -rn 'Attack, Target Claim' --include=*.md .`（7 处） | 不必改；在下一次改枚举时按 A5 的三层扫描执行即可（已在 `claim-first-policy §7` 与 SKILL §8 A5 登记） |
| n-3 | **V11 / V7 的「键缺失即不判」口径未写进 policy §4**：`V11` 只在 `stage == "X2"` **且 `claim_targeted` 为非空数组**时触发；`V7` 在 `cheapest_discriminating_test` 键缺失时跳过。执行者若省略键，两条闸门都静默通过 | `scripts/state_check.py:747`(`_v11`) / `:620`(`_v7`)；`policy:329—345`（§4 口径补充与边界） | 在 §4「判据补充」里补一行：「`claim_targeted` / `cheapest_discriminating_test` **键缺失**按『未填写』处理，不触发对应规则；如需强制填写，另立字段齐备性规则（§3 层）」 |

---

## 4. 必做七项逐条结果

### 4.1 全链路读写闭环（item 1）

**方法：** 解析 `research-state-policy.md §5`（`:356—376`）的读/写列，建立「字段 → 写者/读者」图，
再与 6 个 phase 文件的同款表比对（三方 14/14 已逐字一致，故只需一份表）。

| 阶段 | 写 | 下游读者 | 闭环 |
|---|---|---|---|
| R0 | `contract` | **无显式读者**（仅 R1「全部」隐含 + `phase-r3-r6:362` prose） | ⚠️ m-1 |
| R2 | `literature` / `evidence`(lit) / `assumptions` / `uncertainties` | R3（literature、assumptions）、R7（evidence）、R8（evidence） | ✅ |
| R3 | `hypotheses` | R4 / R5 / R6 / R7（均读 `hypotheses`） | ✅ |
| R4 | `hypotheses[].niche/.island/.status` | R6（读 hypotheses）、V6/V13/V15 | ✅ |
| R5 | `literature` / `evidence`(lit) | R3（literature）、R7/R8（evidence） | ✅ |
| R6 | `hypotheses[].generation/.status` / `failures` | R7（hypotheses）、V4/V12 | ⚠️ M-2（F 无人挂引用） |
| R7 | `assurance` / `failures` / `uncertainties` | R8（assurance）、R12（failures/uncertainties）、R14（全 state） | ⚠️ M-2 |
| R8 | `claims[].contract` / `evidence` / `claims[].supporting_evidence`/`refuting_evidence` / `uncertainties` | R9（claims）、R12（claims/evidence） | ⚠️ **M-1**（无 claim 创建者） |
| R9 | `experiments`（`SKILL:74`、`policy:371`） | R10/R11/R13（全 state） | ⚠️ m-2（R9.4 还写 failures） |
| R10 | `repairs` + `state_delta` | R14（未闭环 `repairs`） | ✅ |
| R11 | 归并（无新字段） | — | ✅ |
| R12 | `narrative_view`（+`uncertainties`） | **无显式读者**（R13/R14 全 state 隐含） | ✅（设计内，n-1） |
| R13 | `reviews` / `failures` / `experiments[].unexpected` | R14（全 state） | ⚠️ M-2（F 无人挂引用） |
| R14 | `decision` / `closures` / 各 `status` | **无下游**（终局） | ✅（设计内，n-1） |

**反例（item 1 要求的）：**
- 「写了但没人读」：`contract`（m-1）、`decision`/`narrative_view`（n-1，设计内）。
- 「读了但没人写」：**`claims[]` 从未被任何阶段创建**（M-1）；`known_flaws` 在 R6/R7/R13 收工时无人写（M-2）。

### 4.2 门禁与流程的自洽（item 2）

**V1—V15 可达性：**

| 规则 | 依赖对象 | 谁创建 | 可达性 |
|---|---|---|---|
| V1 / V2 / V3 | `claims[]` | **无**（M-1） | ❌ **流程上无产出者**（写表执行则永不触发；手写则位置与写表冲突） |
| V4 | `failures[]` + `known_flaws` | R6/R7/R13 写 F；`known_flaws` 仅 R9/R10/R14 可写 | ❌ **必然触发**（M-2） |
| V5 / V6 / V7 / V8 / V9 / V10 | evidence / hypotheses / uncertainties / experiments / assurance / repairs | R2·R8·R11 / R3·R4·R6 / R8·R9 / R9 / R7 / R10 | ✅ 可达且可满足 |
| V11 / V12 | `experiments[]` | R9（同时写 experiments + failures） | ✅ |
| V13 / V14 / V15 | `hypotheses[].island`/`generation`/`niche`+`status` | R3 建、R4 归档 | ✅ |

**后果表述一致性：** `policy:62`（收工清零）与 `:294`（未清零不得作为下一阶段输入）在 phase 文件中
均有对应：`phase-r9-r11:182`「跑 `state_check.py`，退出码非 `0` **不得**进入 R12」、
`phase-r8:227`「不得进入 R9」、其余 5 个 phase 文件末尾「硬违规须为 0」✅ —— **表述本身一致**，
冲突来自 M-1/M-2（有些阶段无论如何都到不了 0）。

### 4.3 跨波枚举三处一致（item 3）—— ✅ 无第二份定义

| 枚举 | 规范值 | 扫描结果 |
|---|---|---|
| `(O,T,R)` | `Problem/Phenomenon/Theory/Method/Evaluation/Resource-System`；`hidden-assumption` 等 7 个 T；`prove/characterize/explain/reformulate/design-algorithm/build-benchmark/build-system` | 全仓**无**下划线/驼峰/空格变体；`claim-first-policy §5` 是唯一权威（spec §2.4 是契约层）✅ |
| `epistemic_status` 五值 | `Observed/Supported/Hypothesized/Planned/Unknown` | 无第六值、无小写值（小写命中均为 claim/experiment 的 `status` 或 refs_index 内部值）✅ |
| `N1—N10` | preset 名 = niche | 定义在 `narrative-patterns §1`；`state_check.NICHES` 是唯一镜像 ✅ |
| `P1`—`P6` / `local` | 7 值（默认开 P1—P4） | `state_check:120` 7 值、spec `:45/:65/:78`、`policy:194/:312`、`phase-r3-r6:344` 四处一致；**无 5 值残留**（命中的两处本身就是 7 值行）✅ |
| `G1—G5` | `Claim grounding / Prior-work distinction / Identification / Factual integrity / Venue scope` | 全仓只有这 5 个名字（其余命中是 `G1 fail` 等用法）✅ |
| `S1—S6` | `S1_Context … S6_Consequence_Boundary` | 只有这一套键名 ✅ |
| 六维 | `Significance / Originality / Soundness margin / Explanatory depth / Generality / Narrative compression` | 无大小写/空格变体 ✅ |
| 五元组五字段 | `(Attack, Target Claim, Alternative, Discriminating Test, Kill Condition)` | **逐字出现 7 处、全部一致**；示例里的 `Target:`/`Test:` 简写与 spec 自带示例同款（非规范位）✅ |

**结论：** 每个枚举家族都有**单一权威定义**（claim-first-policy §2/§5、narrative-patterns §1/§3、
scoring-policy §3/§4、policy §2/§4、spec §2/§3/§4），其余位置是引用或逐字复述；
**没有出现第二份语义不同的定义**。杂项风险：五元组被复述 7 次（n-2）。

### 4.4 角色与派遣闭环（item 4）—— ✅ 19/19 闭合

```bash
python3 - <<'PY'   # 定义标题（§1A/§1B/§2/§3 的 `### X — …`）vs §4.2 矩阵行
PY
#   定义的角色数: 19   矩阵出现的角色数: 19
#   矩阵有但未定义: 无
#   定义但矩阵没有: 无
```

- 19 个角色 = §1A 四个会议审稿人（矩阵中合并为一行「仅校准表」）+ §1B 六个攻击面审稿人 +
  §2 两个作者角色 + §3 七个核验/审计角色（含 `S-Integrity`）。
- **无死角色**（每个定义都在矩阵出现），**无未定义角色**（矩阵每个名字都有定义段）。

### 4.5 R12 的视图性（item 5）—— ✅ 达成

```bash
grep -rn 'narrative_view' --include=*.md .
```

只有 7 处：R12 的写入口（`phase-r12:846`、`policy:374`、`SKILL:77`）、R12-post 的落盘
（`phase-r12:831`）、R12-pre 的**禁写**（`:830`）、policy §3.11 槽位定义（`:462`）、README 概述。
**没有任何 phase 把它当输入读**（R13/R14 读的是「全 state + artifact / 未闭环 repairs」，
属隐含覆盖而非依赖）。与「叙事是视图、不是独立 artifact」一致 ✅。

### 4.6 三个已知未做项的当前状态（item 6）—— 三项属实

| 声明 | 核实 | 证据 |
|---|---|---|
| `R2.2 occupancy map` 仍是 Wave 3 深化标记 | **属实** | `phase-r2-r5:229`「## R2.2 occupancy map（**Wave 3 深化**）（占用图）」 |
| `README.md` 仍有 1 处 `R-CVPR` | **属实** | `grep -c 'R-CVPR' README.md` → **1**；位于 `README.md:232`（作用域串仍是「仅 R3—R6 / R8 / R7 / R10 / R13」，属 venue 扫尾） |
| `example-d-narrative.md` 是否仍与 claim-first 结构一致 | **属实（未被破坏）** | claim-first 关键词命中 **21**；结构完整：`摘要`（`:37`）→ `idea I1`（`:56`）→ `攻击面评审`（`:312`）→ `门禁判定 G1—G5`（`:364`）→ `六维排序`（`:388`）→ `缺失证据清单`（`:430`）→ 落盘（`:459`） |

### 4.7 机械面（item 7）—— 全绿

| # | 项 | 结果 |
|---|---|---|
| 1 | 相对链接（去围栏） | **415 条，0 断链** ✅ |
| 2 | deprecated-terms | **exit 1，0 命中** ✅ |
| 3 | JSON（模板 + refs 索引） | 合法 ✅ |
| 4 | `python3 -m unittest discover -s scripts -p "test_*.py"` | **116 tests OK** ✅ |
| 5 | `state_check --selftest` | exit 0 ✅ |
| 6 | 模板 `--check` | exit 0 ✅ |
| 7 | examples + templates linter | 9/9 硬违规 0 ✅（含 `61ad5c3` 修掉的两处分号） |
| 8 | `--list-rules` ↔ `policy §4` | **15 条逐字一致，无缺失** ✅ |
| 9 | 三方口径 14 阶段 | **14/14 逐字相同**（唯一「不一致」= R1，policy §5 明写 R1 不占行） ✅ |
| 10 | 波次提交完整性 | `9d63395 → 61ad5c3`：examples 非空（`example-b-to-c-d-e.md` +4/−2、`example-followup-review.md` +1/−1）；旧指示以删除线保留 ✅ |

---

## 5. 总收官结论与修复清单

**三波各自的内部质量已被独立验证**（Wave 1：状态与 V1—V15；Wave 2：发现层与 V6/V13—V15；
Wave 3：角色层后移与五元组）—— 单波验收的 MAJOR 全部清零，机械面全绿。
**跨波仍有 2 处状态机闭环缺口**，都是「谁写」的归属问题，不是新功能缺陷：

| 优先级 | 动作 | 文件:行号 | 量级 |
|---|---|---|---|
| 1 | **M-1** 给 `claims[]` 指定创建者：把 D0—D9 划给 R12-pre（并授权写 `claims[]`/台账），或把 claim graph 创建并入 R8；同步三层写表 + `phase-r12:137—141` 的 D1 措辞 | `phase-r12:137—141`、`:824—845`、`policy:370`、`policy:374`、`SKILL:75/77`、`phase-r8` §C1 | 一节 + 3 行表 |
| 2 | **M-2** 让 V4 可闭合：R6/R7/R13 的写列补「把新 `F` 挂到 `known_flaws`」，或在 `policy §4` 写明 V4 的复核时机在 R10 `state_delta` 之后（并同步脚本语义） | `policy:368/369/375`、`SKILL §0` 同行、`phase-r3-r6:413`、`phase-r7` R7 节、`phase-r7` R13 节 | 3 行表 ×3 层 |
| 3 | m-1 `contract` 补读者；m-2 R9 写列补 `failures[]`；m-3 R7 首轮审计对象说明 | 见 §2 | 各一行 |
| 4 | n-1/n-2/n-3（终端产物说明、五元组复述风险、闸门宽松口径） | 见 §3 | 可选 |

**总收官结论：仍需修 —— 2 项 MAJOR（跨波状态机闭环）必须处理，3 项 MINOR 建议同批，
3 项 NIT 可选。** 修完这 2 项 MAJOR 后，三波即可交付：届时 `claims[]` 有明确产出者、
V1—V4 可达且可满足，R0→R14 的读写在文档层形成闭环。
**不建议在 M-1/M-2 未修的情况下向用户宣布「三波完成」** —— 这两处会让执行者在
R6/R7/R13 的收工检查上卡死（V4），或写出一个没有 claim 的 world model（V1—V3 空转）。

---

## 6. 未覆盖项与限制

1. **未重跑单波验收**（Wave 1/2/3 的各自报告仍然有效，本报告只查波间耦合）。
2. **未做外部事实核验**（spec §1 引用的 Co-Scientist 等系统由用户提供、未经仓库核实；本环境无外网）。
3. **未评审 `README.md` / `project-layout.md` / `example-d-narrative.md` 的 venue 扫尾内容**
   （Lead 已登记为已知未做；本报告只确认其当前状态属实）。
4. **未评审 Wave 2/3 的科学实质**（island 划分、八攻击面的覆盖面、`S-Integrity` 的四类命中是否穷尽）。
5. 本报告未修改任何被审文件；未 `git commit`。唯一写入：`docs/verify-r-final.md`。

---

## 7. 增量复核（最后一轮确认，快照 `7f6e043`）

**本轮改动：** 7 个文件（`git diff --stat 61ad5c3 7f6e043`）：SKILL +10、phase-r12 +10、
phase-r3-r6 +21、phase-r7 +7、phase-r9-r11 +2、policy +24、本报告 +282。
**快照：** `7f6e043`，被审文件末次 mtime 07:21 前后，其后冻结。**只读**：本次仅追加本节。

### 7.1 M-2（V4 与写集冲突）—— ✅ **完全闭环**

**独立验证方法：** 按三层写表构造**各阶段收工态**（R3 种子 → R6 淘汰 → R7 assurance →
R8 挂证据 → R9 实验树 → R13 审计），逐个喂 `state_check.py --json`。

```
post-R3（seed：ungrounded + falsifier）        exit=0  ✅
post-R6（H2 killed → F1 挂 C2.known_flaws）    exit=0  ✅   ← 原先被 V4 卡死
post-R7（F2 挂 C1.known_flaws + assurance）    exit=0  ✅   ← 原先被 V4 卡死
post-R9（X2 failed 双写 + F3 挂 X2）           exit=0  ✅
post-R13（reviews + experiments[].unexpected） exit=0  ✅   ← 原先被 V4 卡死
```

`policy §5.0` 规则 2（`:358—361`）＋三层写表给 R6/R7/R9/R13 补的 `known_flaws（把新 `F` 挂上）`
（`policy:382/383/385/389`、`SKILL:71/72/74/78`、`phase-r3-r6:475`、`phase-r7:457/458`、`phase-r9-r11:207`）
使 V4 在**每个写 `F` 的阶段内部**即可满足 → **R6/R7/R13 的收工检查现在可以到 0** ✅。

### 7.2 M-1（claims 创建归属）—— ⚠️ **只闭环了一半：V1—V3 可达，但 R8 的 status 转换无合法归属**

**已闭环的部分 ✅：** R3 创建 seed（`phase-r3-r6:356/361`、`policy:355—357`、三层写表 R3 行
`policy:379` / `SKILL:68` / `phase-r3-r6:473`），seed 要求 `falsifier` 必填 → **V1 可满足**；
seed 的 `supporting_evidence`/`refuting_evidence` 为空 → **V2 可满足**；seed `status: ungrounded`
且无 E 引用 → **V3 可满足**（实测 post-R3 exit 0）。`phase-r12:103—110` 新增映射并明写
「**`claims[]` 不由本文件创建**」✅。

**未闭环的部分 ❌（新 MAJOR）：** `policy §5.0` 规则 1（`:355—357`）写
「**R8 建契约并更新 status**」，但 R8 的写表**没有 `claims[].status`**
（`policy:384` / `SKILL:73` / `phase-r8:235` 三层同款），而：
- `policy:416`：「**只写本阶段的行。** 表中未列出的字段**不得**顺手改」；
- `SKILL:548`（§1.6）：「改 `claims[].status` **只能经 R10**。Discovery 与 Assurance 都不得直接改」。

**实证（冲突可复现）：**

```
post-R8（status 保持 ungrounded，仅挂 supporting_evidence=[E1]）  exit=3  rules=['V3']
post-R8'（status 同步改为 partially-supported）                  exit=0  ✅
```

即：**R8 若不改 status → V3 报错（收工不了）；若改 status → 违 §1.6 与「只写本阶段的行」**。
M-1 把「没人创建 claim」修好了，但把阻塞点从 R3 前移到了 R8。
**建议修法（二选一，一行到两行）：**
①在 R8 写列补 `claims[].status`（限定为**证据驱动的单向转换**：`ungrounded → supported /
partially-supported / contradicted`），并在 §1.6 注明「R8 的这一转换是唯一例外，且不得写 `killed`」；
②或在 `policy §5.0` 规则 1 改为「R8 建契约；`status` 转换在**同一轮 R10** 的 `state_delta` 里完成，
R8 的收工检查允许 `supporting_evidence` 已挂、`status` 暂未同步」—— 但需同步 `state_check.py` 的 V3
语义（否则脚本仍判 3）。

### 7.3 本轮编辑留下的**半成品单元格**（新 MAJOR ×2）

Lead 说明「第一遍用正则时单元格被 `|` 截断，改用按单元格定位才成功」——**两处副本仍有残留**，
而且**三方一致性检查器看不见它们**（它只比较读/写单元格）：

**N-1｜`SKILL.md §0` 五行丢了「作用」列**（被「读」值覆盖）：

```bash
awk '/^\| Phase \| 名称 \| 作用 \| 读 state \| 写 state \|/{f=1} f&&/^\|/{n=split($0,a,"|");printf "cols=%d %s\n",n-2,substr($0,1,70)}' SKILL.md
#  R3/R6/R7/R9/R13 五行为 cols=5，但第 3 格 = 读值
```

| 行 | 作用列现值（错） | 应为 |
|---|---|---|
| `SKILL.md:68` R3 | `` `literature` / `assumptions` / `failures` / `contract.constraints` `` | 双轨发现：local search ‖ paradigm escape（**上下文隔离**） |
| `SKILL.md:71` R6 | `` `hypotheses` / `uncertainties` / `failures` `` | mutation / crossover / simplification / 新 niche |
| `SKILL.md:72` R7 | `` `claims` / `evidence` / `hypotheses` `` | 六攻击面审核 + 硬门禁 `G1—G5` |
| `SKILL.md:74` R9 | `` `uncertainties`(critical, high 且 high) / `claims` `` | 实验树 `X1—X6` + EIG 选择 + provenance |
| `SKILL.md:78` R13 | `全 state + artifact` | artifact-aware 审查（code / logs / failed runs） |

**N-2｜`research-state-policy.md §5` 五行丢了「对应文件」列**（被「写」值覆盖）
—— 这是 **Wave 2 M-4 修复的回退**（那轮刚把 5 个不存在的文件名改对）：

```python
# 逐单元格 dump（行 379/382/383/385/389）：
[0] **R3**  [1] 读  [2] 写  [3] = 写（重复）   ← 原应为 phase-r3-r6-discovery.md
```

| 行 | 对应文件列现值（错） | 应为 |
|---|---|---|
| `policy:379` R3 | 写值重复 | `phase-r3-r6-discovery.md` |
| `policy:382` R6 | 写值重复 | `phase-r3-r6-discovery.md` |
| `policy:383` R7 | 写值重复 | `phase-r7-r10-r13-assurance-repair-review.md` |
| `policy:385` R9 | 写值重复 | `phase-r9-r11-experiment-loop.md` |
| `policy:389` R13 | 写值重复 | `phase-r7-r10-r13-assurance-repair-review.md` |

**修复动作：** 把这两张表的 10 个单元格按上表回填即可（phase 文件的 3 列表**未被破坏** ✅）。

### 7.4 你指定的四件核验

**① 2 项 MAJOR 是否真闭环：** M-2 ✅ 完全闭环（§7.1 五个探针全 0）；
M-1 ⚠️ **一半**（创建 ✅ + V1—V3 可达 ✅，但 R8 的 status 转换冲突未解 → §7.2）。

**② 三方 14 阶段读写表逐字一致：** **14/14 ✅**（独立脚本 `rw_compare.py`；唯一「不一致」= R1，
policy §5 明写 R1 不占行）。
> ⚠️ 但请连同 §7.3 一起看：**三方检查器只比较「读/写」两格**，所以
> `SKILL §0` 被覆盖的「作用」格、`policy §5` 被覆盖的「对应文件」格**不在它的检查范围内** ——
> 这正是两处半成品能存活到本轮的原因。建议把检查器扩成**逐单元格列数 + 关键列非空**。

**③ `phase-r12` 的 D0—D9 ↔ pre/post 映射 vs `SKILL §4`：** **不一致（MINOR-m）**
- `phase-r12:103—110` 已写明：**D0—D3（证据台账 / claim graph / 科学分类 / anchor eligibility）→ R12-pre**
  「只**复核与展开**，**不创建**」；**D4—D9 → R12-post**；并有「`claims[]` 不由本文件创建」警告 ✅。
- `SKILL.md:705` 的 R12 段仍写「**R12-pre**（R8 后、R9 前）**只写**『若 `H` 被验证，可能成立的 thesis 是…』」
  —— 未提 pre 还负责 **D0—D3 的复核**，也未提「claim 由 R3 创建」；
  `SKILL.md:712` 的流程行仍以「D0 证据台账 → D1 Claim Graph（`C0—C5`）→ …」开头，
  读者容易误以为台账 / claim graph 由 R12 创建（与 `policy §5.0` 冲突）。
- **修法：** 把 `SKILL.md:705—712` 与 `phase-r12:103—110` 对齐（pre 行补「+ 复核 D0—D3；
  `claims[]` 由 R3 创建，本段只读与标注」）。

**④ 机械面（自跑）：**

| # | 项 | 结果 |
|---|---|---|
| 1 | 相对链接（去围栏） | **416 条，0 断链** ✅ |
| 2 | deprecated-terms | **exit 1，0 命中** ✅ |
| 3 | JSON（模板 + refs 索引） | 合法 ✅ |
| 4 | `unittest discover -s scripts -p "test_*.py"` | **116 tests OK** ✅ |
| 5 | `state_check --selftest` | exit 0 ✅ |
| 6 | 模板 `--check` | exit 0 ✅ |
| 7 | examples + templates linter | 9/9 硬违规 0 ✅ |
| 8 | `--list-rules` ↔ `policy §4` | **15 条逐字一致** ✅ |

**本轮 MINOR 声明核验（4/4 落地）：**
① R3 读列含 `contract.constraints`（`policy:379`/`SKILL:68`/`phase-r3-r6:473`）✅；
② R9 写列含 `failures`（三层同款）✅；③ `phase-r7:15`「**首轮 R7 审什么**」已补 ✅；
④ `policy:363`「**终端产物**（无显式读者，不是僵尸字段）」已补 ✅。

### 7.5 最后一轮结论

**仍需修：3 项 MAJOR + 1 项 MINOR，全部是局部修复（10 个表格单元格 + R8 status 归属二选一 + SKILL §4 一段对齐）。**

| 优先级 | 动作 | 位置 |
|---|---|---|
| 1 | 回填 `SKILL §0` 五行的「作用」列 | `SKILL.md:68/71/72/74/78` |
| 2 | 回填 `policy §5` 五行的「对应文件」列（Wave 2 M-4 回退） | `research-state-policy.md:379/382/383/385/389` |
| 3 | 决定 R8 的 `claims[].status` 转换归属：① 写列补 status + §1.6 例外，或 ② 声明「转换在 R10 完成」并同步 V3 语义 | `policy:355—357`、`policy:384`、`SKILL:73/548`、`phase-r8:235`、`scripts/state_check.py` V3 |
| 4 | `SKILL §4` 的 R12 段与 `phase-r12:103—110` 对齐 | `SKILL.md:705—712` |

**按你的闸门（「只剩 NIT 才能直接说可交付」）：现在**不能说「三波可交付」** ——
两处表格单元格损坏是**这一轮新引入**的（其中一处还是 Wave 2 已修内容的回退），
R8 的 status 归属则是 M-1 修复的收尾。**修完这 4 项（预计 20 分钟内）后，我这边
没有其它阻断项**：M-2 已完全闭环、V1—V15 全部可达且可满足、三方 14/14、机械面全绿。

---

## 8. 收口确认（快照 `95a62c5`）

**本轮改动：** 4 个文件（`git diff --stat 7f6e043 95a62c5`）：SKILL +20/−16、phase-r8 +1/−1、
policy +12/−6、本报告 +148。**快照 `95a62c5`，只读复核**（本次仅追加本节）。

### 8.1 逐项确认（15 行重建 + R8 语义 + SKILL §4）

| 项 | 声明 | 我自己的逐单元格复核 | 判定 |
|---|---|---|---|
| **10 个被覆盖单元格** | `SKILL §0` 五行「作用」列、`policy §5` 五行「对应文件」列已逐行重建 | **逐单元格 dump**：`SKILL.md:68` 作用=「双轨发现：local search ‖ paradigm escape（**上下文隔离**）」、`:71`「mutation / crossover / simplification / 新 niche」、`:72`「六攻击面审核 + 硬门禁 `G1—G5`」、`:74`「实验树 `X1—X6` + EIG 选择 + provenance」、`:78`「artifact-aware 审查（code / logs / failed runs）」；**SKILL §0 全 15 行 cols=5** ✅。`policy:379/382` 对应文件=`phase-r3-r6-discovery.md`、`:383/389`=`phase-r7-r10-r13-assurance-repair-review.md`、`:385`=`phase-r9-r11-experiment-loop.md`；**policy §5 全 14 行 cols=4** ✅ | ✅ **达成** |
| **phase-r8 读写两格写反** | 已归位 | `phase-r8:235`：读=`claims` / `evidence` / `assurance`；写=`claims[].contract` / `claims[].status`（仅证据驱动的单向升级） / `evidence` / … —— 与 `SKILL:73`、`policy:384` **三层逐字一致** ✅ | ✅ **达成** |
| **R8 status 细分（选项①）** | 升级由 R8、降级/否决只能经 R10；三层写列 + `SKILL §1.6` 已同步 | 三层写列 ✅ 均含「`claims[].status`（**仅证据驱动的单向升级**：`ungrounded` → `partially-supported` / `supported`）」。**实证**：`post-R8（升级 partially-supported + E1）→ exit 0` ✅；`post-R8（升级 supported + E1）→ exit 0` ✅；`post-R8（挂 E1 但 status 仍 ungrounded）→ exit 3 · V3` ✅（正确地仍报）。**但 `SKILL §1.6` 与其他 7 处未同步 → 见 §8.2 MAJOR** | ⚠️ **部分** |
| **MINOR：`SKILL §4` 的 R12 段对齐** | pre 覆盖 D0—D3、明写「claims 不由本文件创建」；post 覆盖 D4—D9 | `SKILL.md:705—712`：pre 行已写「**R12-pre 覆盖 D0—D3**（证据台账 / claim graph **复核** / 科学分类 / anchor eligibility）…**`claims[]` 的创建在 R3，不由本阶段创建**」；post 行写「**R12-post 覆盖 D4—D9**（叙事实现 / 攻击面审核 / venue 校准 / 门禁 / 排序 / 输出）」；流程行改为「D1 claim graph **复核**（**不创建**）」——与 `phase-r12:103—110` 一致 ✅ | ✅ **达成** |

### 8.2 MAJOR：R8 的新授权与**八处旧规则互斥**（`SKILL §1.6` 未同步）

**现象：** 写表已授权 R8 做 `claims[].status` 的**单向升级**，但全仓仍有 **8 处**明文禁止任何
Assurance/非 R10 阶段改 status —— 包括本轮 M-1 自己新增的归属表。

| # | 位置 | 原文 | 与新授权的关系 |
|---|---|---|---|
| 1 | `SKILL.md:99` | 「改 claim 状态**只能经 R10**，这是防"自己给自己判分"的结构性措施」 | ❌ 互斥 |
| 2 | **`SKILL.md:549`（§1.6）** | 「**改 `claims[].status` 只能经 R10。** Discovery 与 Assurance 都不得直接改」 | ❌ 互斥（**Lead 声明已同步，实际未改**：本提交的 SKILL diff 只含 §0 五行与 §4 R12 段） |
| 3 | `SKILL.md:738`（§4 R7/R10/R13 段） | 「**assurance 不得直接改 `claims[].status`** —— 只能经 R10」 | ❌ 互斥 |
| 4 | `SKILL.md:782`（§5） | 「改 `claims[].status` 只能经 R10。Discovery（R3—R6）与 Assurance（**R7**）都不得直接改」 | ❌ 互斥 |
| 5 | `references/roles.md:111`（§1B 硬规则 3） | 「**不得直接改 `claims[].status`** —— 只能经 R10」 | ❌ 互斥 |
| 6 | `references/phase-r7-r10-r13-…md:423`（R7 硬规则 3） | 「**assurance 不得直接改 `claims[].status`** —— 只能经 **R10**」 | ❌ 互斥 |
| 7 | **`references/phase-r3-r6-discovery.md:364`（§R3.0 归属表）** | 「\| R10 \| **唯一能改** `claims[].status` 的阶段 \|」 | ❌ 互斥（与本轮新增的 R8 授权直接对撞） |
| 8 | `references/phase-r9-r11-experiment-loop.md:179` | 「…改 `claims[].status` —— 这是防「自己给自己判分」的结构性措施」 | ❌ 互斥（上下文同 §1.6） |

**另：** 你声明「降级与否决（`contradicted` / `killed`）只能经 R10」这一**细分规则在我复核时全仓找不到**
（`grep -rn '降级与否决\|contradicted.*只能\|killed.*只能'` → 0 命中；三层写列只在括号里写了升级箭头）。
**影响（可复现）：** 执行者若按 §1.6 / §1B / R7 规则 / R3.0 表执行 → **R8 不敢升级 status** →
`post-R8` 回到 **exit 3 · V3**（§8.1 已实证）；若按写表升级 → 违反 4 处明文禁令。
**建议修法（本轮只需措辞，不需再改机制）：**
①把 `SKILL.md:549`（§1.6）改为「改 `claims[].status` **默认只能经 R10**；**唯一例外**：R8 可在
挂证据时做**证据驱动的单向升级**（`ungrounded` → `partially-supported` / `supported`），
**降级与否决（`contradicted` / `killed`）仍只能经 R10**」；
②在 `SKILL.md:99/738/782`、`roles.md:111`、`phase-r7:423`、`phase-r9-r11:179` 六处各加半句回指 §1.6 的该例外；
③`phase-r3-r6:364` 的 R3.0 表把 R10 行改为「R10（**降级与否决的唯一阶段**）」并列一行
「R8（**仅单向升级**）」；
④把「降级与否决只能经 R10」这句**补进** `policy §5.0` 规则 1（现在只有一句「R8 建契约并更新 status」）。

### 8.3 MINOR：声明的「逐单元格检查器」**未进仓库**

**现象：** 你写「我按你的建议把检查器扩了：现在是『逐单元格列数 + 关键列非空』」。
实测 **`95a62c5` 只改了 4 个文件，`scripts/` 零改动**；全仓 grep「关键列非空」只命中**我自己的报告**。

```bash
git diff --name-only 7f6e043 95a62c5
#   docs/verify-r-final.md / research-idea-pipeline/SKILL.md /
#   research-idea-pipeline/references/phase-r8-evidence-contract.md /
#   research-idea-pipeline/references/research-state-policy.md
grep -rln '关键列非空' .        # → 只有 docs/verify-r-final.md
python3 -m unittest discover -s scripts -p "test_*.py" | tail -1   # 116 tests（未新增）
```

**影响：** 我上一轮指出的「10 个坏单元格对三方检查器不可见」这个**盲区仍然存在** ——
下一次同类批量编辑仍不会有任何机械闸门报警。
**建议：** 把该检查器落成 `scripts/` 下的一个可跑项（例如并入 `test_state_check.py` 的
「表格完整性」用例，或在 SKILL §8 D 的第 6 项后追加 `python3 scripts/check_tables.py`），
检查内容建议固定为：①三张读写表逐行**列数**等于表头；②`SKILL §0` 的「作用」列不等于「读」列、
`policy §5` 的「对应文件」列匹配 `phase-*.md` 且文件存在；③关键列非空。
（我的临时实现 `/tmp/verify/rw_compare.py` 只覆盖读/写格，可直接删。）

### 8.4 机械面（自跑，快照 `95a62c5`）

| # | 项 | 结果 |
|---|---|---|
| 1 | 相对链接（去围栏） | **417 条，0 断链** ✅ |
| 2 | deprecated-terms | **exit 1，0 命中** ✅ |
| 3 | JSON（模板 + refs 索引） | 合法 ✅ |
| 4 | `unittest discover -s scripts -p "test_*.py"` | **116 tests OK** ✅ |
| 5 | `state_check --selftest` | exit 0 ✅ |
| 6 | 模板 `--check` | exit 0 ✅ |
| 7 | examples + templates linter | 9/9 硬违规 0 ✅ |
| 8 | `--list-rules` ↔ `policy §4` | **15 条逐字一致** ✅ |
| 9 | 三方 14 阶段读/写格 | **14/14 逐字一致**（唯一「不一致」= R1）✅ |
| 10 | 我自己的逐单元格检查 | SKILL §0 15 行全 5 列；policy §5 14 行全 4 列；phase 表 3 列 ✅ |

### 8.5 收口结论

**仍需修：1 项 MAJOR + 1 项 MINOR —— 不能说「三波可交付」。**

| 优先级 | 动作 | 位置 | 量级 |
|---|---|---|---|
| 1 | **同步 R8 status 授权的 8 处旧规则**（§1.6 为头，加「唯一例外：R8 单向升级；降级与否决仍属 R10」；并补上「降级与否决只能经 R10」这句） | `SKILL.md:99/549/738/782`、`roles.md:111`、`phase-r7:423`、`phase-r9-r11:179`、`phase-r3-r6:364`、`policy §5.0:355—357` | 8 处半句到一句 |
| 2 | 把「逐单元格列数 + 关键列非空」检查器落进 `scripts/`（否则该盲区仍在） | 新增脚本 或 `test_state_check.py` + `SKILL §8 D` | 一个小脚本 + 1 行登记 |

**已确认关闭的项（本轮）：** 10 个单元格（逐单元格复核 ✅）、`phase-r8` 读写归位 ✅、
M-2（V4 全阶段可闭环 ✅）、M-1 的**创建**归属 ✅ 与 **R8 升级路径** ✅（实证 exit 0）、
`SKILL §4` 的 R12 段 ✅、上一轮 4 项 MINOR ✅、机械面全绿 ✅。

**一句话：** 机制层面三波已经全部打通（V1—V15 可达可满足、读写闭环、枚举单源、角色闭合、
视图性正确）；**只剩「新授权与八处旧禁令的措辞同步」这一处自相矛盾**，加上把检查器真正落盘。
这 9 处改完，我认为可以宣布三波完成并交付用户总结。

---

## 9. 收口确认（快照 `9fc4c66`）

**本轮改动：** 8 个文件（`git diff --stat 95a62c5 9fc4c66`）：
**6 个被审内容文件**（SKILL +10/−?、roles、phase-r3-r6、phase-r7-r10-r13、phase-r9-r11、policy +4）
＋ `scripts/test_state_check.py` **+64**（新增 `TestTableIntegrity`）＋ 本报告。**只读复核。**

### 9.1 八处 status 禁令例外 —— ✅ **8/8 全部落地**（逐处现值，`git diff` 自证成立）

| # | 位置 | 现值（节选） |
|---|---|---|
| 1 | `SKILL.md:549`（§1.6） | 「改 `claims[].status` **默认只能经 R10**。**唯一例外**：R8 挂证据时可做**证据驱动的单向升级**（`ungrounded` → `partially-supported` / `supported`）；**降级与否决**（`contradicted` / `killed`）**仍只能经 R10**」 |
| 2 | `SKILL.md:99` | 「改 claim 状态**默认只能经 R10**（**例外见 §1.6**：R8 的证据驱动单向升级）」 |
| 3 | `SKILL.md:739`（§4 R7 段） | 「**assurance 不得直接改 `claims[].status`** —— 只能经 R10（**例外见 §1.6**）」 |
| 4 | `SKILL.md:783`（§5 回写规则 2） | 同 §1.6 全文（默认 + 唯一例外 + 降级与否决） |
| 5 | `roles.md:111`（§1B 硬规则 3） | 「不得直接改 `claims[].status` —— 只能经 R10（**例外见 SKILL §1.6**：R8 证据驱动的单向升级）」 |
| 6 | `phase-r7-…md:423`（R7 硬规则 3） | 「只能经 **R10**（**例外见 ../SKILL.md §1.6**：R8 证据驱动的单向升级）」 |
| 7 | `phase-r9-r11-…md:178` | 「**`status` 变更只能在这里（经 R10）** —— **例外：R8 的证据驱动单向升级**（见 ../SKILL.md §1.6）」 |
| 8 | `phase-r3-r6-…md:364—365`（§R3.0 归属表） | 新增 `\| **R8** \| 挂证据时做**证据驱动的单向升级**…\|`；`\| R10 \| **降级与否决的唯一阶段**（`contradicted` / `killed`）\|` |
| ＋ | `policy §5.0:359—361` | 新增第 3 条：「**升级**由 **R8** 按证据驱动执行；**降级与否决**只能经 R10…八处提及该禁令的地方都已回指本条」 |

`git diff --name-only 95a62c5 9fc4c66` 确实包含 **6 个内容文件**（与你的自证一致）——
上一轮的「声明已同步、实际只改 SKILL」这次不成立 ✅。

### 9.2 落盘的检查器 —— ❌ **存在，但抓不住它要防的那类损坏（MAJOR）**

**我的独立验证方式：** 把整个 `research-idea-pipeline/` 复制到 `/tmp/verify/tc`，
在副本里**原样复现本轮的真实损坏**（`SKILL` 的「作用」列 ← 读列；`policy` 的「对应文件」列 ← 写列），
再跑新增的 4 个用例：

```
干净副本：        Ran 4 tests … OK
复现原始损坏后：  Ran 4 tests … OK        ← ❌ 4/4 全过，一处都没报
你用的反向验证（把文件列改成 phase-nope.md）：FAILED (failures=1) ← ✅ 这条路有效
```

**根因（两行测试代码）：**

| 位置 | 现值 | 问题 |
|---|---|---|
| `scripts/test_state_check.py:690` | `effect, read = cells[2].strip(), cells[4].strip()` | 5 列表格按 `\|` 切分后 **`cells[2]` 是「名称」列**（`dual-discovery`），**`cells[3]` 才是「作用」列**；所以 `:692` 的 `assertNotEqual(effect, read)` 比的是「名称 ≠ 读」，**永远不会触发** |
| `scripts/test_state_check.py:699` | `if target.startswith("phase-"):` | 真实损坏是「文件列被写值覆盖」——写值不以 `phase-` 开头 → **存在性断言被跳过**；只有人为写成 `phase-nope.md` 才会命中（这正是你的反向验证能过、真实损坏过不了的原因） |

**证明修法有效（我在副本里打补丁后重跑同一处损坏）：**

```
把 :690 改为 cells[3]，并把 :699 的守卫改为先 assertRegex(target, r"^`?phase-[\w-]+\.md`?$")
→ Ran 4 tests, FAILED (failures=2)：
   AssertionError: '`hypotheses` / `uncertainties` / `failures`' == '…' : SKILL R6 作用列被读列覆盖
   AssertionError: policy R6 对应文件列不是 phase-*.md：…
```
即：**两行改动就能让检查器真正覆盖这个盲区**（其余两个用例——列数=6/7/5——保留，它们防的是另一类损坏，仍有效）。
**注：** `test_policy_readwrite_table_columns` 与 `test_phase_tables_three_columns` 只查列数，
而本轮真实损坏**列数是正确的**（4/5 列都没变），所以它们同样不会报——这是设计取舍，不算缺陷。

### 9.3 MINOR：`policy §5` 的「补充说明」仍与新归属规则冲突

该段自带免责声明（「不参与逐字比对…**不得**把它当成第二套口径」），但内容与**本轮刚冻结的归属规则**冲突：

| 行 | 现值（节选） | 冲突点 |
|---|---|---|
| `policy:401` | 「**R2**：读 `claims[]`、`assumptions[]`、`literature[]`、`uncertainties[]`；写 `literature[]`…、`evidence[]`…、**`claims[]`（缺口类主张 + `supporting_evidence`）**、`uncertainties[]`」 | **给了 `claims[]` 第二个创建者（R2）**，与 §5.0 规则 1「**创建归属 = R3**」冲突；且 R2 的读列表比上表多 `claims[]` |
| `policy:402` | 「**R3**：读 `claims[]`、`assumptions[]`、`literature[]`、`uncertainties[]`」 | 上表 R3 读 = `literature` / `assumptions` / `failures` / `contract.constraints`（**没有 claims / uncertainties，有 failures**）→ 同阶段两套读口径 |

**修法（两行）：** `:401` 删掉读、写两处 `claims[]`（保留「缺口类主张」的语义可改写为「落 `uncertainties[]`，
由 R3 转成 `C`」）；`:402` 的读列表与上表逐字对齐。**否则执行者按这段理解，会在 R2 建 claim。**

### 9.4 NIT

| # | 现象 | 位置 | 建议 |
|---|---|---|---|
| n-1 | 小节标题写「**两条**归属规则」，正文已是 **3 条** | `policy:353` | 改「三条归属规则」 |
| n-2 | §R3.0 归属表里 **R8 占两行**（建契约 / 单向升级） | `phase-r3-r6:363—364` | 合并为「建 `claims[].contract`；挂证据时做**证据驱动的单向升级**」 |

### 9.5 机械面（自跑，仓库本体，快照 `9fc4c66`）

| # | 项 | 结果 |
|---|---|---|
| 1 | 相对链接（去围栏） | **418 条，0 断链** ✅ |
| 2 | deprecated-terms | **exit 1，0 命中** ✅ |
| 3 | JSON（模板 + refs 索引） | 合法 ✅ |
| 4 | `unittest discover -s scripts -p "test_*.py"` | **120 tests OK** ✅（116 + 4，与你的数字一致） |
| 5 | `state_check --selftest` | exit 0 ✅ |
| 6 | 模板 `--check` | exit 0 ✅ |
| 7 | examples + templates linter | 9/9 硬违规 0 ✅ |
| 8 | `--list-rules` ↔ `policy §4` | **15 条逐字一致** ✅ |
| 9 | 三方 14 阶段读/写格 | **14/14 逐字一致** ✅ |

### 9.6 收口结论

**仍需修：1 项 MAJOR（检查器两行断言）+ 1 项 MINOR（§5 补充说明的 claims 归属）+ 2 项 NIT —— 不能说「三波可交付」。**

| 优先级 | 动作 | 位置 | 量级 |
|---|---|---|---|
| 1 | **把检查器修到真能报警**：`cells[2]` → `cells[3]`；文件列改为「必须匹配 `^`?phase-[\w-]+\.md`?$` **且** 文件存在」 | `scripts/test_state_check.py:690`、`:699` | 2 行（我已实证：改后同一处损坏立即报 2 处失败） |
| 2 | `policy §5` 补充说明：`:401` 去掉 `claims[]`（读+写）、`:402` 读列表与上表对齐 | `policy:401—402` | 2 行 |
| 3 | NIT：标题「两条」→「三条」；R3.0 表合并 R8 两行 | `policy:353`、`phase-r3-r6:363—364` | 2 行 |

**已确认关闭：** 8/8 status 例外同步 ✅（含 §1.6，这次 `git diff` 自证成立）、`policy §5.0` 第 3 条 ✅、
`TestTableIntegrity` 已落盘且 120 用例全绿 ✅（但见 §9.2 的有效性缺陷）、
机械面 9 项全绿 ✅。**除上述 1 MAJOR + 1 MINOR，机制层三波没有其它阻断项。**
