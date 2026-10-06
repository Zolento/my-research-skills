# P0-4 clean-room 独立复验报告

> **执行者**：`venue-standards`（teammate，**全程未参与本套 R 架构的近期改动**）
> **方式**：只依据 skill 内部的 `SKILL.md` 与 `references/*.md` 判断；
> 未读 `docs/` 中"本轮改了什么"的内容；一切结论以亲自跑出的结果为准；只读，临时文件在 `/tmp/cleanroom/`。
> **交付中断说明**：该 teammate 在**写完本文之前**停止（本会话的系统性失败模式：分析完成、落盘失败）。
> 其完整发现已通过消息先行交付，本文按其原始发现**如实转录**，未增删结论。

## 总体裁决：**需修后交付**

**核心状态机真实可用**；但有**两条 headline 安全属性是"纸面保证"**，没有任何机械落点。

- `R0`→`R14` 逐阶段全部跑通，**14/14 exit=0** —— **未发现"按字面做完 → 校验器必然报错"的死锁**。
- `V1`—`V21` 机械闸门**是真的**：独立构造 5 条反例，校验器 **5/5 抓住**且规则号与路径正确。
- 但 ① §1.7「R14 不能杀真理主张」、② R13 的 Integrity Gate —— **零机械足迹**。

---

## 1. 找到的 invariants（16 条）

| # | invariant | 机械强制？ |
|---|---|---|
| I1 | claim 真值只由 R8（证据驱动单向升级）/ R10（`state_delta`）改变；**R14 写集合永不含 `claims[].status`** | ❌ **无**（MAJOR-1） |
| I2 | 每阶段只写自己那一行；跨阶段修改必须走 `repairs[].state_delta` | ❌ 无（MAJOR-1） |
| I3 | critical flaw ⇒ state 必须改变；只写 flaw 不闭环 = 未闭环 | ✅ 部分（V10 四键 + 枚举） |
| I4 | **失败不得消失**：failed X 必须被 `failures[].referenced_by` 引用 | ✅ 已验证（V12） |
| I5 | 每条 F 必须被 `known_flaws` 引用；**写 F 的阶段必须同时被授权写 `known_flaws`** | ✅ **写集合 1:1 对齐**（R6/R7/R9/R13 完全一致）—— **设计正确，应记功** |
| I6 | 每个 niche 至少留一条 elite | ✅ 已验证（V15） |
| I7 | 无 E 引用的 C 必须 `ungrounded`；双向判定 | ✅（V3） |
| I8 | 每个 C 必须有非空 `falsifier` | ✅（V1） |
| I9 | claim 升级须有达阈值 `verification_tier` | ✅ 已验证（V20） |
| I10 | 预注册优先：`running`/`done`/`failed` 须有 `preregistration`，`frozen ≤ result` | ✅（V21） |
| I11 | `invalid` 一跳传染；**`stale` 不传染**；多跳是 R11 的责任 | ✅ 已验证（V18/V19） |
| I12 | R12 叙事是视图、默认零写入；不得新增 `evidence` / 提高 `epistemic_status` | ❌ 无（MAJOR-1） |
| I13 | **Integrity Gate 阻断**（leakage / cherry-picking / metric misuse / post-hoc bias） | ❌ **无**（MAJOR-2） |
| I14 | 收工门槛：每阶段 `state_check` 退出码必须为 0 | ✅ 总闸 |
| I15 | 状态迁移只能取枚举值 | ⚠️ 部分（`decision.verdict` 未校验，MINOR-5） |
| I16 | 对象创建归属：claims 由 R3 创建，R7 攻击、R8 建契约、R12 只做视图 | ❌ 无（MAJOR-1） |
| I17 | `STATUS.md` 必须是 state 的投影、幂等、禁止手改 | ✅ 已验证（DI-4） |

---

## 2. 流程可执行性

| 阶段 | exit | 阶段 | exit |
|---|---|---|---|
| R0（只写 contract + 骨架） | **0** | R9b（失败实验 + F2） | **0** |
| R2 | **0** | R10（repairs 四键） | **0** |
| R3（hypotheses + claims seed） | **0** | R11（`state_version` +1） | **0** |
| R6（failures + known_flaws） | **0** | R12（`narrative_view`） | **0** |
| R7（assurance） | **0** | R13（reviews + failures） | **0** |
| R8（contract / 升级 / planned X） | **0** | R14（decision / closure） | **0** |
| R8b（冻结 preregistration） | **0** | **合计** | **14/14** |

**专项验证最容易死锁的 V4 义务链**（写 F 却不被授权写 `known_flaws`）：
写 `failures` 的阶段 = 写 `known_flaws` 的阶段 = **{R6, R7, R9, R13}，完全一致**。
**这一点作者做对了。**

---

## 3. MAJOR

### MAJOR-1 · §1.7 认识论权限 + 写集合纪律 **完全没有机械落点**

**根因**：**state 里没有任何 actor / provenance 字段**（`actor` / `writer` / `provenance` / `written_by` 均不存在）。
`state_check.py` 只看最终 JSON，**无法判断任何字段是谁写的**。

```
CE1  R14 越权把 claims[0].status 改成 killed（SKILL.md:634 明令禁止）
     → [ok] 0 处硬违规                    exit=0
CE2  改成 contradicted（同样明令禁止）      exit=0
CE3  R12 凭空新增 E99(Observed/T2) 并把 C1 升为 supported（policy:529 禁止）
     → [ok] 0 处硬违规                    exit=0
```

**影响**：`SKILL.md:630` 称此为本 Skill「**绝不让步**的一条」，其「机械体现」被写成
"三方读写表逐字一致" —— 即**只靠文档一致性 + 执行者自律**。
一个违反 §1.7 的 state 文件能通过全部机械闸门，且**事后无法从 artifact 追责**（无 provenance）。
**这是本次复验最重的发现。**

### MAJOR-2 · Integrity Gate **零机械足迹**

```
reviews[0].integrity_gate="fail" + findings=["leakage: 训练/测试同受试者"]
     → [ok] 0 处硬违规                    exit=0
整个 reviews 键删掉                        exit=0
decision.verdict="banana"                 exit=0
grep -n 'reviews|integrity_gate|narrative_view|decision' scripts/state_check.py  → 无命中
```

**证据**：`SKILL.md:849-850` 明写「**不通过即不得提交**，不是「记一条 warning」」；
`SKILL.md:882`「Integrity 检查…是 **Gate**」；`SKILL.md:943` 自检项「已逐项过闸」。

**影响**：这是守科研诚信（leakage / cherry-picking）的那道门，却是**唯一一道没有任何机械后果的 Gate**。
对比 V12（失败不得消失）、V4（F 必须被引用）都真机械化了。

**建议**：至少让 `integrity_gate == "fail"` 强制要求存在对应 `repairs[]`（`disposition` ∈ 五值）
或 `failures[]`，并纳入 V 规则。

---

## 4. MINOR

| # | 问题 | 证据 |
|---|---|---|
| **MINOR-1** | `assurance[]` 只出现在 **R7 写列**；但 R9/R13 的细节 bullet 要求写 `assurance[].discriminating_test` / `assurance[]`，而 bullet 明文「不参与逐字比对、不得当第二套口径」+ 硬规则 2「表中未列出的字段不得顺手改」→ 按权威表，`assurance[].discriminating_test` 在 R7 之后**永无合法写者**（R7 时 X 还不存在，只能写 `TBD`）。**出路是再次进入 R7（下轮自愈），非永久死锁。** | policy:505 / :526 / :530 / :515-516 / :538-539 |
| **MINOR-2** | `validity` / `verification_tier` / `depends_on` **不在任何写列**，却是八类对象必填公共字段，由 V18/V19/V20 强制。对照组：`known_flaws` 被**逐阶段精确列出**（R6/R7/R9/R13）→ 这三者更像是**遗漏**而非有意的对象级授权。 | policy:167-187 / :254 |
| **MINOR-3** | `policy:515` 声称读/写列与「**`SKILL.md` §0**、各 phase 文件」逐字相同，但 **`SKILL.md` 全文没有任何读/写表**；`SKILL.md:113`「读/写列**见上表**」也**悬空**（其上方是分工表，无读写列）。而 §1.7 的"机械体现"正依赖这个"三方"→ **三方里的一方不存在**。**另两方完美一致**（policy §5 ↔ 7 个 phase 文件：0 处不一致，14/14 覆盖）。 | SKILL.md:113 / :650；policy:515 |
| **MINOR-4** | `关闭该 niche` 这个补救措施**全仓库未实现**（无字段、无 V15 豁免、无流程）。最小复现：N2 只有 1 条候选且它是 elite，R14 归档它 → **V15 exit 3**；补救①无对象可升、②无机制、删候选被禁 → R14 收不了工。**但作者已在 phase-r3-r6:522 预告该交互，故非未文档化死锁**，且在 `decision=archive` 时不动 hypothesis 状态即可通过 → 下调为 MINOR。 | phase-r3-r6:522 |
| **MINOR-5** | `decision.verdict` 枚举（`continue/pivot/archive/submit`）**未校验**，填 `"banana"` 仍 exit 0。 | SKILL.md:884 |

---

## 5. 测试可信度评估

```
python3 -m unittest discover -s scripts -p "test_*.py"  → Ran 175 tests, OK
python3 scripts/state_check.py --selftest                → selftest OK
模板 --check                                             → 0 违规，exit 0
```

**"自己写的测试证明自己写的实现"？—— 部分是，但不是套套逻辑。**

- 复验者**不看测试**、独立构造 5 条反例（V11/V12/V15/V19/V20）→ **校验器 5/5 抓住**，
  规则号与路径均正确。**核心规则是真实功能。**
- 覆盖度：108 个 test 函数 / 175 tests，V1—V21 每条至少 1 个测试；
  但 **V7/V11/V12/V15 各只有 1 个测试**（回归风险高）。
- **结构性盲区**：`grep -iE '写集合|actor|越权|认识论' scripts/test_state_check.py` → **0 命中**。
  测试**无法覆盖** actor 权限模型——因为该模型**本身没有机械表示**（MAJOR-1/2）。
  **175 个全绿的测试会对 I1/I2/I12/I13/I16 造成虚假信心**，这是可信度的主要问题。
- `--selftest` 内嵌在 `state_check.py` 自身（同源自证），属正常 smoke test，**不作为独立证据**。

---

## 6. 复验者**无法**验证的（不编造通过）

1. **在线文献检索链路**（arxiv/openalex/crossref）：只有离线测试，网络未跑通，
   **无法确认强制扩检实际生效**（它是散文规则，脚本里没有闸门）。
2. **R2/R5 饱和判定**（连续两轮零新增）在真实检索下的行为。
3. **G1—G5 硬门禁**：`scripts/` 内**无任何机械实现**（与文档一致），R12「先过硬门禁」完全依赖执行者判断。
4. roles.md / narrative-patterns.md / scoring-policy.md 的语义正确性（超出本次范围）。
5. `ste_lint_zh.py` / `refs_index.py` 只跑了 unittest，未做端到端产物验证。

---

## 7. 建议修复优先级

| 优先级 | 项 |
|---|---|
| **P0** | **MAJOR-1**：给 state 加 provenance（哪怕只在 `repairs[]` / `narrative_view` 记 stage），或把「R14 不得改 `claims[].status`」变成可校验约束（例如要求 `claims[].status` 变更必须伴随一条覆盖它的 `repairs[]`） |
| **P0** | **MAJOR-2**：让 `integrity_gate == "fail"` 强制产生 `repairs[]` / `failures[]` |
| **P1** | MINOR-3：`SKILL.md` §0 补回读/写表（或把「三方」改为「两方」，并修 :113 悬空引用） |
| **P1** | MINOR-2：写表补 `validity` / `verification_tier` / `depends_on` 的授权说明 |
| **P2** | MINOR-1 / 4 / 5：修表行与 bullet 矛盾；为「关闭 niche」定义机制或删掉该措辞；校验 `decision.verdict` |

---

## 8. 与本轮其他工作的交叉印证

本报告的两项观察**被 Lead 独立复现**：

1. **MINOR-4（V15 与归档唯一 elite 的冲突）**：Lead 在写 `scripts/test_golden_path.py` 时，
   最初让 `R4` 把 niche `N2` 唯一的 elite 降级 → **当场触发 V15**。这独立证实了该交互真实存在。
   修法是让 R4 只在**同 niche 有替代者**时重排归属（golden path 已改为 3 条候选）。

2. **支持边 ≠ 传播边（本报告未覆盖，由 golden path 发现）**：
   `V19` 沿 `depends_on` 传播，而证据支持走 `supporting_evidence` —— **两者不是同一条边**。
   因此「E 失效 ⇒ 依赖它的 C 变 stale」**不会自动发生**，除非 claim 显式把该证据写进 `depends_on`。
   已在 `test_golden_path.py` 以 `skipTest` 登记为**已知缺口**。
   建议二选一：① 规范要求"把支持证据一并写进 `depends_on`"；② 让 V19 把
   `supporting_evidence` / `refuting_evidence` 也视为传播边。


---

# 附录：修复状态（Round 5）

| 原发现 | 状态 | 修法 |
|---|---|---|
| **MAJOR-1** §1.7 零机械落点 | ✅ **已修** | 新增 **V22**：`claims[].status ∈ {killed, contradicted}` 必须被一条 `repairs[]` 覆盖，且该条 `targets` 含此 claim 的 id、`disposition` ∈ 五值。**决策层越权写 `killed` 现在会被校验器拦下。** 为做精确核对，`repairs[]` 新增必填字段 `targets`（id 数组）—— 见下方"实现过程中的两处自我修正" |
| **MAJOR-2** Integrity Gate 零机械足迹 | ✅ **已修** | 新增 **V23**：`reviews[].integrity_gate == "fail"` 时必须存在 `repairs[]`（`disposition` ∈ 五值）或 `failures[]`（`kind` ∈ 六值） |
| **MINOR-5** `decision.verdict` 未校验 | ✅ **已修** | 新增 **V24**：`decision.verdict` 必须是 `continue / pivot / archive / submit` 之一 |
| **MINOR-3** SKILL §0 无读写表 | ❌ **假阳性** | `SKILL.md:63` **确实有**读写表（表头为 `| Phase | 名称 | 作用 | 读 state | 写 state |`）。复验者按 policy/phase 的表头 `| 阶段 | 读` 去 grep，自然搜不到。三方比较器始终 0 不一致 |
| MINOR-1 `assurance[]` 只在 R7 写列 | ⏳ 未修 | 涉及写表增列，留待下一轮 |
| MINOR-2 `validity`/`verification_tier`/`depends_on` 不在写列 | ⏳ 未修 | 同上 |
| MINOR-4「关闭 niche」未实现 | ⏳ 未修 | 需要在字段/C15 豁免/流程三者选一 |
| 支持边 ≠ 传播边（golden path 发现） | ⏳ 未修 | `V19` 沿 `depends_on` 传播，而证据支持走 `supporting_evidence` |

## 实现过程中的两处**自我修正**（值得记录）

1. **V22 最初用子串匹配 `state_delta` 里的 claim id** —— 结果基线 state 里一条无关的 repair
   恰好提到 `C0`，就把 `killed` **误判为"已覆盖"**。子串匹配同时会漏报与误报，**这本身是 bug**。
   已改为显式 `repairs[].targets` 字段（精确、可机械核对）。
2. **V24 的规则文本在 policy 里为表格转义写成 `\|`，脚本里是裸 `|`** → 逐字比较器立刻报不一致。
   本仓库约定规则文本避免用 `|`，已统一为 `/` 分隔。

> 这两处都由**机械比较器/自检**当场抓住，而不是靠人读文档。

## 新增的机械闸门

| 规则 | 内容 |
|---|---|
| **V22** | `claims[].status ∈ {killed, contradicted}` 必须被至少一条 `repairs[]` 覆盖（该条 `repairs[].targets` 含此 claim 的 id，且 `disposition` ∈ 五值） |
| **V23** | `reviews[].integrity_gate == "fail"` 时必须存在 `repairs[]`（`disposition` ∈ 五值）或 `failures[]`（`kind` ∈ 六值） |
| **V24** | `decision.verdict` 存在时必须是 `continue / pivot / archive / submit` 之一 |

**闸门快照（Round 5 末）**：
```
187 tests OK（+1 为 Path D 升级为真实断言）    selftest V1—V24 全覆盖
模板 --check exit 0                          规则表 24/24 逐字不一致 0
三方读写 14 阶段不一致 0                      链接 469 断链 0
deprecated 0 命中                            linter 全绿
```

**Golden Path 的 3 条 skipTest 缺口**（仍如实登记，不假装覆盖）：
Path A 支持边不是传播边｜Path C 假范式新颖性｜Path E 叙事幻觉不得创建 claim。
