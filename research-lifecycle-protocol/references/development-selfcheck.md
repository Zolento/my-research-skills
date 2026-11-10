# Development Self-check（维护本 Skill 时用）

> **读者是维护者，不是科研 Agent。** 常规科研动作**不加载**本文件。
>
> **加载条件：** 改任何规则、命名、枚举、计数、路径时；发布前；合并前。
> 内容：五类历史高频漏点（A）、计数与枚举（B）、路径与命名（C）、机械校验（D）、
> 内容丢失检查（D5）、清单自身（E）。

本文件由 v2.2.0 的 L0 精简产生：内容来自 `SKILL.md` §8，未改变任何检查项。
唯一的发布判据仍是 `python3 scripts/release_check.py` 的最后一行。
## 1. 规则变更自检清单（维护本 Skill 时用）

> **与 §6 的区别：** §6 是**执行时**的输出自检；本节是**改本 Skill 自身**时的自检。
> 触发条件：改动任何**规则、命名、枚举、计数、路径**。

**为什么需要它：** 本仓库的实际漂移记录显示，改了规则后**漏掉的从来不是规则本身**，
而是下面 A 组这五类"看起来不像规则"的位置。


### A. 五类高危位置（历史上反复漏）

| # | 位置 | 为什么危险 | 必做动作 |
|---|---|---|---|
| A1 | **设计依据 / 理由段**（§7、各文件开头的"为什么"） | 它在**论证旧设计**，读起来像权威依据。改规则后最容易整条漏掉，且在有人质疑设计时被当成正确论点引用 | **逐条读一遍 §7 与各"为什么"，问："这条还在支持当前规则吗？"** |
| A2 | **速查 / 汇总表**（§4 各 R 阶段 速查、`project-layout` §6 落盘职责表、`roles` §4.2 派遣矩阵、`phase-r12` §D5.5 汇总表） | 汇总表是规则的**复制品**。改规则不改它 = 仓库里有两份互相矛盾的规则 | **所有"表格式汇总"逐个核对** |
| A3 | **示例与模板**（`examples/*`、`templates/*`） | 示例会**示范旧写法**，且比正文更容易被照抄 | **示例里的文件名、路径、计数、命令逐个核对** |
| A4 | **语义字段与规则的一致性**（§0.1/§0.2 锚点体系、`project-layout` §2.1 类型枚举、§3 frontmatter schema、`research-state.template.json`、§4 INDEX 章节） | 规则写"**必须**有 X"，但 schema / 枚举里**没有 X 的槽位**，或强制项与枚举表脱节。这种漂移**不在计数上、在语义上**，比 A2 更难发现：执行者只能自创值或让 frontmatter 失真 | **规则 → 字段 → 枚举 → 模板 → 示例，五处同步。** 每条新规则都问两句：①「它要求落盘的东西，**字段表里有槽位吗**？」②「它要求存在的文档类型，**枚举里有值吗**？」 |
| A5 | **跨层漂移：claim 层 / 叙事层 / 评审层三层的耦合**（`claim-first-policy` 的枚举与门禁 ↔ `narrative-patterns` 的槽位与 preset ↔ `scoring-policy` 的门禁表与排序维度 ↔ `roles` 的攻击面角色 ↔ `research-state.template.json` 的 `claims` / `assurance` 段 ↔ `examples/example-d-narrative.md`） | 三层是**同一套规则的三种呈现**。改一层而不改另两层，就会出现"claim 要求 `Ci ← Ej`，但叙事槽位里没有 `S5`"或"门禁叫 `G1—G5`，但评分政策还在算 11 维中位数"这类**跨文件互斥指令** | **改 claim 层或评审层的任何枚举 / 门禁 / 维度，必须同时扫这三层。** 机械做法：`grep -rn '<被改的枚举名>' --include=*.md .` 逐个确认；并在 `docs/claim-first-spec.md` §10 记一行 |

> **A4 的现实教训（计数与枚举类 B1—B5 那一批）：** 规则要求"锚点必须落盘"，但 frontmatter 没有
> `anchor_role` / `serves` 的槽位；强制"锚点文档"，但类型枚举里没有 `anchor`；
> 允许"主+次锚点"，但 `core_goal` 只有一个槽；实际路线必然产出枚举外的派生物，
> 但除自创 slug 外无处安放。**全都是"规则有、载体无"** —— 只查计数与链接是查不出来的。

### B. 计数与枚举（每轮都漏）

| # | 对象 | 历史改动 | 分布位置 |
|---|---|---|---|
| B1 | **子代理数** | 会议审稿人 `3→4`；R12 `5→6`；**R7 / R10 / R13 由「八子代理」改为「六个攻击面 + `S-Lit` + `S-Devil`」** | 标题、正文、汇总表、速查节、`roles` 矩阵 |
| B2 | **规则条数** | §1 `四→五`；§1.4 布局规则 `四→五→六` | **标题里的"N 条"必须与该节实际条目数一致** |
| B3 | **会议枚举** | `CVPR/ICML/NeurIPS` → `+MICCAI` | 约 13 处 |
| B4 | **源枚举** | `local\|arxiv` → `+openalex\|crossref` | 约 15 处（注意 `index.json` 的 `source` 是**另一种含义**，不要改） |
| B5 | **slug 枚举** | 叙事从「每个 idea 一个后缀式 slug」改为单一 slug | 类型表、规则表、示例、模板 |
| B6 | **退出码** | `0/1/2` → `0/1/2/4` | CLI 表、退出码表、各 R 阶段 输出说明 |

### C. 路径与命名

| # | 对象 | 历史改动 |
|---|---|---|
| C1 | **落盘路径** | `docs/` → `routes/<R>/docs/`（**含 §4 速查节** —— 曾漏 5 处） |
| C2 | **审阅命名** | `<ID>-review.md` → `<ID>-review-r01.md` |
| C3 | **标题里的旧词** | 曾漏 `phase-r2-r5` 的 A2 标题（正文早已改为多源，标题仍写旧源名） |

### D. 机械校验（先跑，再人工）

```bash
# 1) 相对链接可达（排除代码围栏内的示例路径与模板占位路径）
# 2) §X<n> 与 §<数字> 引用可解析
# 3) JSON 文件与 md 内 ```json 围栏块合法
python3 scripts/refs_index.py --check
python3 -m unittest discover -s scripts -p "test_*.py"

# 4) 陈旧措辞扫描 —— 必须为 0
# 废弃词清单在 references/deprecated-terms.txt（.txt 天然被 --include=*.md 排除，
# 因此扫描结果才能真的为 0）；以后新增废弃表述就追加到那个文件。
PAT=$(grep -vhE '^\s*(#|$)' references/deprecated-terms.txt | paste -sd'|')
grep -rnE "$PAT" --include=*.md .          # 期望：0 命中（exit 1）

# 5) 落盘路径必须带 routes/<R>/ 前缀 —— 正确的写法以 `routes/<R>/docs/ 开头，
#    所以「反引号紧跟 docs/」就是缺前缀（§1.4 规则 1）
grep -rnE '`docs/<' --include=*.md . | grep -vE 'templates/INDEX\.md|grep -rnE'
#    ↑ 排除 templates/INDEX.md：路线 INDEX 本身就在 routes/<R>/ 内，
#      它的 `docs/` 相对链接是正确写法，不算缺前缀

# 6) 受控中文 linter —— 自检 + 受管文件必须全绿
python3 scripts/ste_lint_zh.py --selftest
for f in examples/*.md templates/*.md; do
  python3 scripts/ste_lint_zh.py --disable synonym-rotation "$f" || exit 1
done
#    注意：**不要**拿它扫本 Skill 自己的规范文本（SKILL.md / references/*.md）——
#    范围只包含「落盘文档 / 对话返回 / 子代理意见」+ examples/ + templates/，
#    见 writing-policy.md §0
#    这里固定跑**默认档**：examples/ 与 templates/ 是存量样例，不按 asd-ste100 追溯改写。
#    asd-ste100 是**当次调用**的可选档（--max-chars 25），不是仓库级闸门。

# 7) Structural Equivalence 检查器 —— 自检 + 模板 + 四份 fixture 必须全绿
python3 scripts/structural_equivalence_check.py --selftest
python3 scripts/structural_equivalence_check.py --artifact templates/structural-equivalence-audit.template.json
for f in examples/structural-equivalence/*.json; do
  python3 scripts/structural_equivalence_check.py --artifact "$f" || exit 1
done
#    真实项目里还要跑路线级交叉校验：
#    python3 scripts/structural_equivalence_check.py --route .research-lifecycle-protocol/routes/<R>

# 8) Rhetorical Realization —— 受限算子与 adversarial counterexamples
python3 -m unittest discover -s scripts -p 'test_rhetorical_realization.py'
```

> **唯一的发布判据是 `scripts/release_check.py` 的最后一行**（`PASS` / `FAIL`）。
> 上面的逐条命令只用于**诊断**；其中 1—8 项已全部收进那一个闸门。
> 手动逐条跑不能替代 `release_check.py`（AGENTS.md Rule 10）。

> **D4 的"已废弃措辞"清单要持续维护**：每次改规则时，把**被替换掉的旧表述**
> 追加进来。这份 grep 清单是防漂移最省力的一道闸。
>
> **新规则若带机械闸门，也要挂进本节。** 例：受控中文政策（
> [writing-policy.md](../references/writing-policy.md)）带来的 `ste_lint_zh.py`
> 已挂为第 6 项；它的默认口径（`--disable synonym-rotation`）与其理由写在政策 §7，
> 不要在这里重复。

### D5. **内容丢失检查（本次真实教训）**

用「按区间替换」改动大段文本时，很容易**把夹在区间内的其它章节整节吞掉**。
本次真实发生过：重写 §1.4 时替换区间取到 `## 2.`，**把夹在中间的 §1.5 整节删除**
（一个用户明确要求的规则）——而当时的链接/引用检查**完全测不出来**，
因为引用处写的是 `§1.5` 这个**字符串**，字符串还在。

**必做：** 任何按区间替换的编辑，都要检查被替换区间内是否含其它标题：

```bash
git diff -U0 -- SKILL.md | grep -E '^[-+]## '     # 标题增删一眼可见
git log --oneline -S"<被删章节的关键词>" -- SKILL.md
```

### E. 清单自身

**改完后问一句：这次漏掉的位置，属于 A/B/C 里的哪一类？**
如果是**新的一类**，把它加进上表 —— 否则下一轮还会漏在同一处。

### Execution gate within R8/R9 and bounded R10 diagnosis

Read [execution-identifiability.md](../references/execution-identifiability.md) before
managed experiments or diagnostic repairs. Use `scripts/experiment_execute.py`
issue/run with a current scheduler and content-bound manifest. Formal X3/X4
requires PEIG PASS; prospectively bounded exploration/X1/X2/pilots use PILOT_ONLY.
HOLD affects the named claim validation. Record R7 attacks and real arm/control
values; a control ID or reviewer score is not mechanical evidence of validity.

Use diagnose for R10 decision-bearing repairs. The finite shared route ledger
prevents rewording, repeated R10, new IDs/seeds, scope edits, extra U or documents
from manufacturing progress. After the configured limit, stop diagnosis and use
existing REDESIGN/T8/R14 authority. Do not iterate experiment cards to make PEIG
pass indefinitely. Post-hoc explanations are exploratory; confirm them with an
independent identifying protocol. Scientific uncertainty remains uncertainty.

The runner covers only its managed entrypoint, not arbitrary external GPU paths.
It never grants global GPU control. Legacy states remain compatible, with no
retrospective execution PASS. R9.O retains and verifies managed execution_record;
R11 uses scheduler-check to source-check actual EIG. Full tests use mock/dry-run.
