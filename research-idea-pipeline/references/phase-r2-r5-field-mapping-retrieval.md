# R2 / R5 — 领域测绘与共演化检索（field-mapping + co-evolving retrieval）

补充文献、扩大检索范围。可被 B/C/D/E 调用，也可单独调用。

> **两条最容易被违反的规则，先记住：**
> 1. **禁止只停留在本地。** 本地检索命中不是终点；只要触发 §A2 的任一条件，
>    就必须查**全部启用源**并扩大范围。
> 2. **未达饱和不得停止。** 停止时必须能说出依据（§A4）。


> **小节号 `§A0`—`§A7` 是 R2 / R5 自己的流程序号**（不是旧命名残留）。

## 输入

| 输入 | 必填 | 说明 |
|---|---|---|
| 检索关键词或研究问题 | ✅ | 自然语言或布尔式 |
| 检索范围 | ❌ | 时间范围、会议范围、数量上限 |
| 尽职调查等级 | ❌ | L1 / L2 / L3；缺省时按触发条件自动判定（§A2） |
| 是否强制刷新缓存 | ❌ | **默认否** |

> **锚定点（核心目标）决定检索边界**（见 [../SKILL.md](../SKILL.md) §0.1）：
> **理论**锚点必须检索该问题是否已有**定理 / 反例 / 不可能性**与**负结果文献**；
> **性能**锚点必须检索 **SOTA 与评测协议**（数据集划分、指标定义、比较口径）；
> **现象 / 基准**锚点必须检索该现象的**已有解释**与**现有评测的已知缺陷**。
> 锚点未确认就做检索，容易漏掉决定成败的那一类文献。

---

## A0. 先尝试 web search

按 [literature-policy.md](literature-policy.md) §1.1 执行网页发现。
先搜索当前问题的论文、作者实现与官方资料，再进入 A1 / A2。
记录查询与实际打开的原始页面，将标题、DOI / arXiv ID 和机制术语传入后续检索。
工具不可用或失败时，记录状态并继续 A1 / A2。明确离线请求不调用 web search。
网页结果不替代多源、正文阅读或检索等级门槛。

## A1. 本地检索（起点，不是终点）

按 [literature-policy.md](literature-policy.md) §1 规范搜索本地文献库：

- 匹配字段：标题、摘要、关键词、全文（`.md` / `.json`）。
- 命中条目标注 `sources=["local"]`，**纳入结果集**。
- **本地命中不结束流程。** 继续执行 A2。

## A2. 在线源强制补充检索

**只要触发下列任一条件，就必须执行**在线源**检索，不得以"本地已有"为由跳过：**

| # | 触发条件 | 最低等级 |
|---|---|---|
| T1 | 创新性声明（"首次提出 / 没人做过 / 首个 / 该方向空白"） | **L3 穷尽** |
| T2 | 理论不清（证不出来、假设无法验证、收敛性说不清） | L2 强化 |
| T3 | 可行性不确定（能不能做、资源够不够、有无不可能性结果） | L2 强化 |
| T4 | 新颖性判定（供 **R7 / R12 的 `S-Lit`** 与 R7 / R10 / R13 的 `S-Nov` 使用） | **L3 穷尽**（**例外：R3—R6 的 §R3.7 概念级快筛 = L2**，见 §A5） |
| T5 | 本地命中不足（< 用户下限，或 < 5 条） | L2 强化 |
| T6 | 用户要求"尽可能多 / 彻底查" | **L3 穷尽** |
| T7 | 将写进文档的"现有工作尚未……"式论断 | L2 强化 |
| T8 | 方法瓶颈：已观察到性能平台、候选反复失败，或诊断不再改变方法决定且缺少新干预 | L2 强化 |

**执行要求：**

- 使用 **Python `arxiv` 包**，查询构造 = 关键词 + 会议过滤 + 时间范围。
- **先识别代理环境：** 解析 `arxiv.org` / `export.arxiv.org`。**若解析到本地 IP**
  （回环 / 私有网段 / 链路本地 / `0.0.0.0`，例如 Clash 的 `198.18.x.x` fake-IP），
  说明**可能存在代理环境**——DNS 已被 hosts 或本地代理接管，你访问的不是 arxiv 官方。
  此时必须：① 在报告中**单列「代理环境提示」段**并写明**具体 IP**；② **不得**据此
  判定"arxiv 不可用"或"无人在研究"；③ 代理链路上的 429 **未必**是 arxiv 官方限流，
  退避照常但结论须注明该不确定性。见
  [literature-policy.md](literature-policy.md) §6.1。
- **严格处理 429**：指数退避 `10s → 20s → 40s → 80s → 160s`，最多 5 次；
  重试期间不发起新请求；5 次失败则回退本地结果并标注
  **"arxiv 暂时不可用，以下结果仅来自本地库"**，同时判定为**检索未达饱和**。
- 结果**必须缓存**到 `./docs/refs/cache/<source>/{query_hash}.json`。
- **结果集 = 本地 + 多源 的并集**，每条标注 `source`。
- 建议直接调用 [../scripts/literature_search.py](../scripts/literature_search.py)；
  创新性声明场景用 `--level L3 --exhaustive --also-query ...`。

**卡点场景（T2/T3）的检索顺序：**

1. 先检索该问题本身（是否已有定理 / 反例 / 不可能性结果）。
2. 再检索所用工具在其他领域的处理方式（同构问题往往已有答案）。
3. 再检索**负结果**（`limits of X`、`X is impossible`、`negative results X`）。
4. 仍无解 → 写入 `STATUS.md` 的 **Critical uncertainties**，标注"待核实"。

## A3. 范围扩大策略

若结果不足或未达饱和，**按以下顺序**逐级扩大，每轮扩大后**重新检索**，直至饱和或
达到用户设定的上限：

| 轮次 | 策略 | 工具支持 |
|---|---|---|
| 1 | **放宽关键词**（同义词、上位词） | 人工构造：`--also-query "同义词"`（可重复） |
| 2 | **扩大时间范围** | `--exhaustive` 自动放宽年份 |
| 3 | **扩大会议范围**（加入 ICLR / ACL / AAAI 等） | 人工构造：把会议名并入检索式，如 `--also-query "ICLR diffusion combinatorial optimization"` |
| 4 | **增加 max_results** | `--exhaustive` 自动倍增 |
| 5 | **引文追溯**（前向 `--cited-by` / 后向 `--references`） | 需 OpenAlex；种子可为 DOI / arXiv ID / OpenAlex ID |

> **⚠️ 脚本只自动执行第 ②、④ 级。** 第 ①、③ 级需要**人工构造检索式**：
> arxiv 元数据不含会议归属，脚本无法自行判断"某个会议是否已覆盖"，
> 因此会议维度的扩大只能由执行者把它写进 `--also-query`。
> 若只跑了 `--exhaustive` 而没有追加同义词/会议检索式，**不得声称已覆盖会议范围**。

**升级纪律：** 一次只升一级；每级记录检索式与命中数。`--exhaustive` 会自动执行
2—5 轮直到满足饱和判据。

### A3.1 三路检索（需要 Structural Equivalence 检查的候选强制）

对需要 Structural Equivalence 检查的 `H`，**除上面的通用扩检外**，还必须至少产生三类 query：

| query 类 | 用什么语言 | 例 |
|---|---|---|
| `surface` | 原领域语言 | `MRI cross-center reconstruction` |
| `facet` | `problem` / supervision-data regime / `observables` / `objective` / `mechanism` 等 scientific facets | `target population without paired targets` |
| `structure-stripped` | 去掉 domain / method / theory branding，只留 abstract scientific skeleton | `indirect observations` + `information-losing operator` + `target-only adaptation` |

最终 priors 取**并集**：

```text
retrieved priors = surface ∪ facet ∪ stripped
```

**重点避免：** 「MRI 文献里没人做，所以 idea 新」。一个 structural prior 可以来自
statistics / econometrics / causal inference / system identification / control /
inverse problems / optimization / information theory / 其它 ML 领域 ——
**只要 structural correspondence 成立**。

**本项与通用扩检的关系：** 三路检索**不替代** §A3 的五轮扩检，也不改变 L1/L2/L3 尽职调查等级。
它是**额外**要求的一类 query 构造，服务于 [structural-equivalence-policy.md](structural-equivalence-policy.md) §10.2。

**脚本支持：** 三路 query 与通用扩检一样，用 `--also-query` 逐条显式传入；
每路检索式与命中数记进 field-map 文档。**不得**只跑 `surface` 一路就声称已做结构检索。

**R5 的结构审计产物 = closest structural prior set。** R5 **不下最终 verdict**（那是 R7 的）。
方法瓶颈检索另交付 §R5.1 的方法线索，供 R3/R6 改造与 R8/R9 实验设计。
R5 **不得**做 near-neighbor 淘汰。
定义见 [structural-equivalence-policy.md](structural-equivalence-policy.md) §25。

## A4. 饱和判定与输出

### A4.1 饱和判据

**满足任一即可停止扩大**，并记录停止原因：

1. **连续两轮扩大检索均无新增高度相关文献**（新增 = 0）；
2. 已达到用户设定的数量/轮次上限；
3. 已覆盖该等级要求的最少检索式数与结果数，且新增趋于 0。

**不满足饱和就停止属于违规。** 因在线源不可用被迫停止时，必须标注
"检索未达饱和，原因：<哪些源>不可用"。状态交接按 [literature-policy.md](literature-policy.md) §2.4 执行。

### A4.2 交付物

**文献列表（核心交付物，含来源标注）：**

| 论文 | 来源 | 会议/年份 | 核心思路 | 关键假设 | 理论工具 | 相关性 |
|---|---|---|---|---|---|---|
| [作者, 会议/年份] | local / arxiv | … | … | … | … | 高/中/低 |

**其他交付物：**

- **检索过程记录** —— web search 查询与发现 URL、原始页面核验位置；后续多源的检索式、命中数、扩大原因。
- **负检索记录（Negative Search Record）** —— L2/L3 必需：
  检索式列表 + 每式命中数 + **为什么这些命中不足以否定目标声明**。
  这是支撑"据本次检索未见"这一措辞的唯一依据。
- **429 等待日志** —— 无 429 时明确写"本轮无 429"。
- **本地缓存更新记录** —— 写入的 cache 文件名、条数、时间戳。
- **尽职调查等级达成情况** —— L1/L2/L3 是否达成，未达标项是什么。

### A4.3 措辞门禁

**证据等级 ↔ 允许/禁止表述的权威定义统一见 [evidence-policy.md](evidence-policy.md)**
（已核实 / 部分核实 / 据本次检索未见 / 待核实 / 待补证明）。
**本节不再重复定义措辞**；R2 / R5 达到 **L2 及以上**时，检索结论使用
「据本次检索未见（检索式见附录）」，且该措辞的唯一依据是上面的**负检索记录**；
**未达 L2 时只能写「待核实」**。

---

## A5. 被其他阶段调用的接口

| 调用方 | 传递内容 | 期望返回 |
|---|---|---|
| R3—R6 | `query` + `scope` | 技术路线归纳所需文献 + 创新性边界线索 |
| R8 | idea 涉及的**特定理论工具** | 该工具的代表工作、假设、局限 |
| R12 | S-Lit 标记的叙事**"待核实"项** | 该叙事核心思路是否已被提出 / 覆盖 |
| R7 / R10 / R13 | S-Lit 标记的**"待核实"项** | 针对该条目的定向核实证据 |

调用时只做**定向补充**，不重复拉取已有内容（Step 3 原则）。
若调用方处于**创新性判定场景**（**R7 / R12 的 `S-Lit`**、R13 的 `S-Integrity`）、
或需要支撑**「首次提出」类声称**，必须按 **L3 穷尽级**执行；**R3—R6 的 population
门槛为 L2**（仅「首次提出」声称要求 L3，见 [phase-r3-r6-discovery.md](phase-r3-r6-discovery.md) §R3.7.1）；
**R8 只引用该结论，不重做检索**（R7 已派 `S-Lit`）；
**§R3.7 快筛只达 L2 时不得把该结论升级为 L3 级证据**，见
[phase-r8-evidence-contract.md](phase-r8-evidence-contract.md) §R8.3）。

---

## A6. 文档落盘与状态更新（强制）

1. **写文档：** `routes/<R>/docs/<R>NNN-field-map.md`，内容 = 检索范围 +
   检索式与结果表 + 文献列表 + **负检索记录** + 429 日志 + 饱和判定。
2. **frontmatter：** `phase: R2 / R5 / type: field-map / status / created`。
3. **更新该路线 `INDEX.md`（资产目录）：** `Key Documents` 新增本文件行，
   `Recent Research Changes` 加一行。
4. **按阶段权限写回 state，再生成 STATUS。** R5 仅写 literature / evidence。
   - 检索缺口先写 field-map 的局限与交接小节。
   - R2 的科学未知按其契约登记；R5 的科学影响交 R11，负向主张处置交 R10。
   - 只要求检索时交付待交接项，不越权写 claim / hypothesis / uncertainty。
   - 不手改 STATUS，也不把源不可用自动登记为 critical 科学未知。
   - 归属权威定义见 [literature-policy.md](literature-policy.md) §2.4。
5. **下载了 PDF 就必须建索引：** 本次调研若把任何 PDF 存进 `docs/refs/papers/`，
   必须在**同一步**写好 sidecar 元数据并重建索引：

   ```bash
   python3 scripts/refs_index.py --refs-dir docs/refs          # 重建
   python3 scripts/refs_index.py --refs-dir docs/refs --check   # 校验（不一致退出码 3）
   ```

   `docs/refs/index.json` **进版本库**，PDF **不进**。未入索引的 PDF 视为不存在。
   见 [literature-policy.md](literature-policy.md) §7.1。
5. **机器状态**写入 `.research-idea-pipeline/routes/A/research-state.json`（就地覆盖），不入 docs。

## A7. 输出后

附 `state.json` 片段：

```json
{
  "phase": "R2 / R5",
  "timestamp": "2025-01-01T00:00:00Z",
  "route": "A",
  "doc_id": "A001",
  "query": "diffusion model combinatorial optimization",
  "scope": {"from_year": 2022, "to_year": 2025, "venues": ["NeurIPS"], "max_results": 20},
  "level": "L3",
  "level_achieved": false,
  "saturation": {"saturated": false, "reason": "arxiv 暂时不可用"},
  "literature_used": [{"title": "…", "sources": ["arxiv"], "url": "…", "ref": "[作者, 会议/年份]"}],
  "retrieval_log": [{"round": 1, "query": "…", "hits": 12, "escalation": null}],
  "negative_search_record": [
    {"query": "…", "total_hits": 12, "by_source": {"local": 2, "arxiv": 10}, "why_not_conclusive": "命中均针对连续空间，未覆盖离散置换约束"}
  ],
  "rate_limit_log": ["[429] 限流，等待 10s 后重试（第 1 次）"],
  "cache_updates": ["docs/refs/cache/arxiv/ab12cd34ef56.json (12 条)"],
  "called_by": "standalone | B | C | D | E",
  "open_questions": ["arxiv 未命中的会议论文需人工补充"],
  "next_action_recommendation": null
}
```

---


## R2.1 field grammar `{P, A, R, D, O, M, T, E}`

目的：抽取「**这个领域通常怎么想问题**」，而不是列 gap。

| 代号 | 含义 | 本项目要填什么 |
|---|---|---|
| `P` | Problem | 领域公认的问题表述 |
| `A` | Assumptions | 显式 + **默会**假设（默会项直接进 `assumptions[]`） |
| `R` | Representation | 用什么数学对象表示 |
| `D` | Data / Supervision | 数据与监督形式 |
| `O` | Objective | 优化目标 |
| `M` | Mechanism | 机制解释 |
| `T` | Theory | 理论工具 |
| `E` | Evaluation | 评测协议 |

## R2.2 occupancy map（Wave 3 深化）（占用图）

不问「哪些工作做过」，而问「**设计空间的哪些区域已经拥挤**」：

```text
parameter adaptation        ███████████   拥挤
feature alignment           █████████
solver adaptation           ███
measurement adaptation      █
identifiability framing     █
causal framing              0             ← negative space
quotient representation     0             ← negative space
```

**negative space（计数为 0 或极低的区域）是 R3 paradigm escape 的输入**，不是直接结论。

---

## R5. 共演化检索（**常驻服务**，不是一次性步骤）

**检索轨迹必须由当前候选反向驱动，而不是沿着初始关键词越搜越窄。**

```text
I_t → Q_{t+1} → L_{t+1} → I_{t+1}
```

**硬规则：**

1. **每轮 R5 必须至少有一条 query 来自最新候选或当前瓶颈**，注明来源候选或观察记录。
   候选耗尽时，以调度器传入的失败上下文构造 query，不得为满足输入而编造候选。
   例：候选把问题重述为「partial identifiability」，下一轮就该搜
   `partial identification under indirect observations`，**不是**继续搜 `prior adaptation`。
2. **`literature[].relation` 六值关系必填**（`supports` / `contradicts` / `shares-assumption` /
   `shares-structure` / `solves-analogous-problem` / `uses-same-theory`；**六值封冻，不得新增**）——
   这是把「按关键词最近邻找」升级为「按结构关系找」的落点。
   结构等价特有的细粒度关系落在 audit artifact 里，再映射到六值之一，见
   [structural-equivalence-policy.md](structural-equivalence-policy.md) §10.3。
3. **三路检索强制**：需要 Structural Equivalence 检查的候选必须做
   `surface ∪ facet ∪ structure-stripped`（§A3.1）。
4. **检索纪律一字不动**：禁止只停留在本地、T1—T8 强制扩检、L1/L2/L3 尽职调查等级、
   429 退避 `10→20→40→80→160s`、代理环境识别、饱和判据、负检索记录 —— 全部见本文档正文与
   [literature-policy.md](literature-policy.md)。
5. **R5 可以随时被 R3/R6 调用**（它是常驻服务）；它的产物只写 `literature[]` / `evidence[]`
   （`kind: literature`），**不得**直接写 `hypotheses[]`。

---

### R5.1 方法瓶颈检索与交接

**触发与刷新权威定义见 [literature-policy.md](literature-policy.md) §2.3。**
本节不新增阶段。R5 只登记文献与文献证据，方法写回仍由 R3/R6 执行。
每轮开始前说明检索范围、预算与停止条件；无需为常规检索重复请求已有授权。

**输入：** 当前瓶颈、来源候选或观察记录、失败范围、已试干预、约束和本轮预算。
在 field-map 中关联瓶颈来源文件与记录 ID、查询日志、正文阅读位置和方法交接行。
证据快照由相关结果、代码版本及配置确定；可以记录哈希或已有版本引用。
状态版本变化或文档排版变化本身不是新证据。
调度器或 R11 提供该上下文。不要更改本文末尾的 state 读写契约。

**检索顺序：**

1. 把失败现象改写成机制问题，说明尚未解释的是哪一部分。先按 A0 尝试 web search。
2. 查询问题本身的解决方法、适用条件和已知失败模式。
3. 查询相邻领域处理同类约束或信息结构的方法，不只重复项目名称。
4. 从关键工作追溯前后引文，检查方法正文、附录及作者实现资料。
5. 优先核对原论文、作者仓库和官方接口文档。记录资料位置与版本或日期。

满足 Structural Equivalence 条件时，仍执行 §A3.1 的三路检索。
本轮以解决瓶颈为目标，不要求在生成方法之前证明 novelty。

**交付：** 在现有 field-map 的交接小节填写下表，不另建评分或状态对象。

| 方法线索 | 来源与证据位置 | 适用条件及当前不匹配项 | 可改动构件与预期后果 | 最小对照及否证条件 | 下一步决定 |
|---|---|---|---|---|---|
| 已核实机制或待核实线索 | 论文节/式、代码路径与版本、官方资料页 | 当前设定满足什么、缺什么 | 相对现有方法具体改什么 | 如何区分简单替代解释 | 交 R3/R6 改造、交 R8/R9 设计或暂不采用 |

来源事实、迁移推断和待验证假设必须分开写。
只有摘要或搜索片段时，标注未核实正文。代码存在不代表机制已经验证。
不能核验适用条件时，不得直接采用或宣称有效；可交给后续可行性检验。
不得把作者数值当作当前项目的预期收益。

每个采用或排除的方法线索都要说明它改变了哪个方法决定。
未找到可用线索时，记录查过的问题族、无解原因及下一条搜索假设。
不强制凑足候选数量，也不把相关文献列表当作突破口。

**停止与回流：** 按 §A4 或预算停止检索，说明达成等级和缺口。
持续执行授权下，交接后重选 R3/R6 或可执行实验，不能停在资料整理。
同一证据下不重复相同查询。无新增线索时，重构问题或测试剩余假设。
只要求检索、建议或审计时，完成本次范围后停止，不顺带实施方法。

---

## 读 / 写 World Model（强制）

| 阶段 | 读 | 写 |
|---|---|---|
| **R2** | `literature` / `assumptions` / `uncertainties` | `literature` / `evidence`(kind=literature) / `assumptions` / `uncertainties` |
| **R5** | `hypotheses` | `literature` / `evidence`(kind=literature) |

> 权威定义见 [research-state-policy.md](research-state-policy.md) §5；本节与它**必须逐字一致**。
> 回写后跑 `python3 scripts/state_check.py --check .research-idea-pipeline/routes/<R>/research-state.json`，**硬违规须为 0**。
