# 文献检索规范（所有 R 阶段强制遵守）

> **三条铁律：**
> 1. **先本地，后多源——但本地命中不是终点。禁止只停留在本地。**
> 2. **429 必须等待**（指数退避，最多 5 次，期间不发新请求）。
> 3. **结果必须缓存，来源必须标注。**
>
> 可直接运行的实现见 [../scripts/literature_search.py](../scripts/literature_search.py)。

---

## 0. 本版对原规范的强化（重要）

原规范 §1.3.1 写的是"本地命中 → 直接返回，不再请求 arxiv"。**本版取消该终止条件。**

| 项 | 原规范 | 现规范 |
|---|---|---|
| 本地命中的含义 | 检索**终点** | 检索的**起点与排序依据** |
| 是否请求 arxiv | 本地命中即不请求 | **凡触发 §2 任一条件，必须请求并扩检** |
| "本地没有" 的含义 | 接近"不存在" | **仅表示"本地库没有"，不构成任何不存在性证据** |

**为什么改：** 本地库是历史缓存的子集，天然有偏（偏旧、偏热门、偏已读）。用它来支撑
"没人做过"或"理论不可行"这类结论，是把**检索工具的局限**误当成**世界的性质**。

**保留不变：** 顺序仍是先本地后 arxiv（本地零成本、零延迟、无 429 风险，且能避免重复
请求）；arxiv 结果的缓存、429 退避、来源标注规则全部不变。

---

## 1. 检索优先级

```
Step 1: 本地检索
  路径 ./docs/refs/（可配置，见 §8）
  匹配：标题、摘要、关键词、全文（若为 Markdown/JSON）
  命中：纳入结果集，标注 sources=["local"] —— 但流程继续，不得在此返回

Step 2: 在线源检索（**默认执行**；§2 的触发条件决定的是“要扩检到什么等级”，不是“要不要查”）
  默认启用全部已实现源（见 §9.1）：
    arxiv     管「新」  预印本，比索引快 6–12 个月；元数据**不含会议**
    openalex  管「关系」引文图（前向 cites: / 后向 referenced_works）+ venue 过滤
    crossref  管「出处」正式 venue 权威（container-title、DOI、卷期）
  查询构造：关键词 + 会议过滤（venue）+ 时间范围
  命中：拉取元数据与摘要，缓存到 docs/refs/cache/<source>/，标注 sources=[<source>]
  ★ 即使 Step 1 已命中，本步也必须执行（除非用户显式 --local-only / --offline）
  ★ 单源失败**不终止**检索：该源标记 unavailable，其余源照常执行

Step 3: 信息不足补齐
  仅补充缺失字段，不重复拉取已有内容

Step 4: 饱和判定（见 §3.3）
  未达饱和 → 按 A3 扩大策略继续检索
  已达饱和 → 合并去重、输出，并记录负检索证据
  ★ 饱和基于**当期可用源集合**：集合一变，之前的"零新增"证据作废
```

**"信息不足"的判定**（满足任一即触发 Step 3）：

- 命中条数 < 用户要求的数量下限；
- 命中条目缺少字段（`abstract` / `year` / `venue` 缺失）；
- 本地命中没有与查询直接对应的**最接近先前工作**。

---

## 2. 强制扩检触发条件（Mandatory Escalation Triggers）

**只要命中下列任一条件，就禁止只停留在本地，必须执行**在线源**检索并按要求扩大范围。**
这是一个**或**条件列表，命中一条即生效。

| # | 触发条件 | 说明 | 最低要求 |
|---|---|---|---|
| **T1** | **创新性声明** | 任何形式的"首次提出 / 没人做过 / 首个 / first to / 该方向空白 / 无人研究" | §3.2 **L3 穷尽级** |
| **T2** | **理论不清** | 定理无法证明、证明有缺口、假设无法验证、收敛性/紧性说不清 | §3.2 **L2 强化级** |
| **T3** | **可行性不确定** | 不确定能不能做、算力/数据是否够、是否存在已知不可行结论 | §3.2 **L2 强化级** |
| **T4** | **新颖性判定** | **R7 / R12 的 `S-Lit`**、R7 / R10 / R13 的 `S-Nov` 环节；**例外：R3—R6 的 §R3.7 概念级快筛按 L2 执行**（见 [phase-r3-r6-discovery.md](phase-r3-r6-discovery.md) §R3.7.1） | §3.2 **L3 穷尽级** |
| **T5** | **本地命中不足** | 本地命中 < 用户下限，或 < 5 条 | §3.2 **L2 强化级** |
| **T6** | **用户要求** | 用户说"尽可能多""彻底查""查全" | §3.2 **L3 穷尽级** |
| **T7** | **结论依赖检索** | 任何将写进文档的"现有工作尚未……"式论断 | §3.2 **L2 强化级** |

### 2.1 T1/T4 的特别规定：创新性声明

- **禁止**在未完成 L3 穷尽检索前，在文档中出现"首次提出"类措辞；只能写
  **"据本次检索未见（检索式见附录 X）"**。
- "首次提出"最终定稿前，必须留存**负检索记录（Negative Search Record）**：
  检索式列表 + 每式命中数 + 为什么这些命中不足以否定该声明。
- 创新性声明必须由 **S-Lit 核实**，必要时由 **S-Nov 独立复核**（不得同源）。
- 若穷尽检索后仍无法确认，标注 **"待核实"**——**不得**默认属实，**不得**臆造引用。

### 2.2 T2/T3 的特别规定：卡住时必须先查文献

遇到理论说不清、证不出来、或不确定能不能做时，**第一动作是检索，不是硬推**：

1. 先检索该问题本身（是否已有定理/反例/不可能性结果）。
2. 再检索所用工具在其他领域的处理方式（同构问题往往已有答案）。
3. 再检索**负结果**（"X 不可行""X 的下界"这类文献最容易被漏掉，但最致命）。
4. 检索后仍无解 → 在 `STATUS.md` 的 **Critical uncertainties** 中记录"已知未知"，并标注待核实。

> ❌ 禁止行为：跳过检索直接写"我们假设该性质成立"。
> ❌ 禁止行为：因为本地库没有相关论文，就断言"该理论问题无人研究"。

---

## 3. 尽职调查等级与饱和判据

### 3.1 等级定义

| 等级 | 名称 | 适用 | 最少检索式 | 最少结果 | 是否必须 arxiv | 是否必须记录负检索 |
|---|---|---|---|---|---|---|
| **L1** | 快速 | 背景铺垫、非结论性调研 | 1—2 | 10 | 建议（本地是否命中都建议） | 否 |
| **L2** | 强化 | T2/T3/T5/T7 | ≥ 4（含同义词、上位词、相邻领域） | 30 | ✅ 必须 | 是 |
| **L3** | 穷尽 | T1/T4/T6（创新性声明） | ≥ 8（含否定式、跨会议、跨领域、负结果） | 60 | ✅ 必须 | 是（强制） |

> 结果数**不是**目标本身；达到数量但检索式家族单一，仍不算达标。判据是
> **检索式是否覆盖了不同词族、不同会议、不同时间窗**。
>
> **饱和（§3.3）是 L2/L3 的达成条件，不是 L1 的条件。** L1 不要求扩检索，
> 因此不因"未饱和"判定未达成；脚本按此实现。

### 3.2 各等级的动作要求

- **L2 强化：** 至少覆盖 ① 原关键词 ② 同义词 ③ 上位词 ④ 相邻领域术语；
  时间范围放宽不少于 3 年；会议范围至少加入 ICLR。
- **L3 穷尽：** 在 L2 基础上追加 ⑤ 否定式查询（如 `X without Y`、`limits of X`、
  `X is impossible`、`negative results X`）⑥ 最接近工作的**引文追溯**（其参考文献
  与被引文献）⑦ 至少一个**不同学科**的同构问题。检索过程全部留档。

### 3.3 饱和判据（Saturation）

**满足任一即可停止扩大**，并记录停止原因：

1. **连续两轮扩大检索均无新增高度相关文献**（新增高相关 = 0）；
2. 已达到用户设定的数量/轮次上限；
3. 已覆盖 §3.1 该等级要求的最少检索式数与结果数，且新增趋于 0。

> **不满足饱和就停止，属于违规。** 若因在线源不可用而被迫停止，必须显式标注
> "检索未达饱和，原因：<哪些源>不可用"，并写入 `STATUS.md` 的 **Critical uncertainties**。

---

## 4. 局部检索的效力边界（禁止推断）

| 观察 | 允许的结论 | 禁止的结论 |
|---|---|---|
| 本地库未命中 | "本地库没有" | ❌ "该工作不存在" |
| arxiv 本轮未命中 | "本次检索式未见" | ❌ "无人研究过" |
| 检索仅覆盖 arXiv | "arXiv 预印本范围内未见" | ❌ "该方向空白"（会议论文/journal 未覆盖） |
| 429 导致中断 | "检索未完成" | ❌ 任何完整性声称 |

**强制写法：**

- ✅ "据本次检索（检索式见 §附录，覆盖 arXiv 2019—2025）未见直接对应工作，**仍需
  会议论文集核实**"
- ❌ "目前没有人做过这件事"

> **完整的证据等级与措辞见 [evidence-policy.md](evidence-policy.md)**（已核实 / 部分
> 核实 / 据本次检索未见 / 待核实 / 待补证明）；上表是其在**检索场景**下的具体化，
> 各 R 阶段 一律引用该文件，不再各自定义措辞。

---

## 5. 在线源调用规范

### 5.1 参考伪代码（原规范保留，含工程修正）

```python
import arxiv
import time
import os
import json

LOCAL_DIR = "./docs/refs/"
CACHE_DIR = "./docs/refs/cache/"
MAX_RETRIES = 5
BASE_WAIT = 10  # 秒

def search_literature(query, max_results=20, conference_filter=None):
    # Step 1: 本地搜索（纳入结果，但不返回）
    local_hits = search_local(query)

    # Step 2: arxiv 搜索 —— 只要触发 §2 条件就必须执行
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )

    results = []
    for attempt in range(MAX_RETRIES):
        try:
            for paper in client.results(search):
                results.append(extract_metadata(paper))
            break
        except arxiv.HTTPError as e:
            if e.status == 429:
                wait = BASE_WAIT * (2 ** attempt)
                print(f"[429] 限流，等待 {wait}s 后重试（第 {attempt+1} 次）")
                time.sleep(wait)
            else:
                raise
    else:
        raise RuntimeError("arxiv 重试次数耗尽，请稍后再试")

    # Step 3: 合并 + 缓存
    cache_results(query, results)
    return merge_unique(local_hits, results)

def search_local(query): ...
def extract_metadata(paper): ...
def cache_results(query, results): ...
```

### 5.2 对伪代码的三点工程修正

1. **`arxiv.HTTPError` 并非 arxiv 包稳定导出的异常。** 实际 429 多为
   `urllib.error.HTTPError`（`.code`）或带 `.response.status_code` 的异常。实现脚本
   兼容捕获 `status` / `code` / `status_code` 及异常文本中的 `429`。
2. **`hash(query)` 跨进程不稳定**（受 `PYTHONHASHSEED` 影响），不能作缓存文件名。
   实现脚本改用 `hashlib.md5(query | max_results | from_year | to_year)[:16]`。
3. **缓存键必须包含检索参数。** 伪代码只按 `query` 建键，会导致"先用 `--max 20`
   跑一次，再用 `--max 100` 复跑却命中旧的 20 条"，直接损害 L3 与扩检索的质量。
   实现脚本的缓存键为 `md5(query | max_results | from_year | to_year)`。

### 5.3 本版新增的行为变更

| 变更 | 说明 |
|---|---|
| arxiv 成为**默认执行** | 脚本默认同时查本地与 arxiv，不再因本地命中而短路 |
| 新增 `--local-only` | **显式**声明只用本地（离线场景）；使用时必须提示"违反默认检索规则" |
| 新增 `--exhaustive` | 自动执行多轮扩大检索，直到饱和（§3.3） |
| 新增 `--also-query` | 追加同义词/上位词/否定式检索式（A3 第 ① 级） |
| 新增 `--level {L1,L2,L3}` | 按 §3.1 校验并记录尽职调查等级（饱和只对 L2/L3 是硬要求） |
| 新增 `--limit` | 控制**最终返回**条数（`--max` 只控制每次 arxiv 查询条数） |
| 缓存键含检索参数 | 见 §5.2 第 3 条 |
| 扩检索结果按轮缓存 | 每轮按其 `max_results`/年份参数单独缓存，避免下次 `--exhaustive` 命中更小的集合 |
| 零结果也缓存 | 否则冷门检索式每次都要重打 arxiv |
| 缓存写入失败不致命 | 缓存目录不可写时只告警，不影响本次检索结果 |
| `--local-only` 不得支撑创新性声明 | 该模式下 L2/L3 必然未达成；不得用于 T1 类声称 |
| `--refresh` 与 `--exhaustive` 可同时使用 | 早前版本在 `--refresh` 下会静默跳过扩大检索，已修正 |
| 中文检索受支持 | 本地匹配对中文走"整段 + 二元组"分词（早期版本只匹配 ASCII，中文检索恒为空） |

---

### 5.4 按源限速与退避（多源后新增）

| 源 | 退避 | 礼貌间隔 | 说明 |
|---|---|---|---|
| `arxiv` | `10 → 20 → 40 → 80 → 160s`，最多 5 次 | **两次请求至少间隔 3s** | 429 退避期间**不得**发起任何新的 arXiv 请求 |
| `openalex` | `3 → 6 → 12s`，最多 3 次 | 无硬性要求 | 命中 403/429/503 时退避；**强烈建议带 `--mailto`** 进 polite pool |
| `crossref` | `3 → 6 → 12s`，最多 3 次 | 无硬性要求 | 命中 429/503 时退避；建议带 `--mailto` |

**全局不变：** 任一源在退避等待期间，**不得**向任何源发起新请求。

> ⚠️ **"paper 2401.429 missing" 这类无关数字不得触发退避。** 状态码提取必须要求
> `status` / `code` / `http` 前缀，否则会凭空等待 5 轮共 310 秒。

## 6. 限速与 429 处理规则（按源）

- 捕获限流错误，若 `status == 429`，按**指数退避**等待：`10s → 20s → 40s → 80s → 160s`。
- **最多重试 5 次。**
- **重试期间不得发起新的 arxiv 请求。**
- 若 5 次后仍失败，**返回本地已有结果**，并标注：
  **"arxiv 暂时不可用，以下结果仅来自本地库"**。
  **同时**在 `STATUS.md` 的 **Critical uncertainties** 记录"检索未达饱和"。
- 非 429 的 HTTP 错误：不重试，直接报告。
- 必须输出**等待日志**。

### 6.1 代理环境识别（arxiv 解析到本地 IP）

**发起 arxiv 请求前，先解析 `arxiv.org` / `export.arxiv.org`。若解析结果是回环、
私有网段、链路本地、`0.0.0.0` 或其他非公网地址，即判定"可能存在代理环境"。**

```
arxiv.org → 127.0.0.1 / ::1 / 0.0.0.0      ← 直接指向本机
          → 198.18.0.30 / 192.168.x.x / 10.x.x.x / 172.16-31.x.x
                                             ← Clash fake-IP、内网镜像、hosts 劫持
```

> **本地 IP 意味着 DNS 已被 hosts 文件或本地代理（Clash / Surge / 镜像站）接管。**
> 此时你访问的不是 arxiv 官方，而是代理链路。

命中时必须做到：

| 要求 | 说明 |
|---|---|
| **输出代理提示** | 检索报告里单列「代理环境提示」段，写明解析到的**具体 IP 与判定类型**（回环 / 私有网段 / 链路本地 / 未指定） |
| **不得据此判定"在线源不可用"** | 代理只改变链路，不代表源宕机；退出码 `2` 表示**存在降级**（任一源 unavailable/partial），仍需真实失败证据 |
| **不得据此判定"无人在研究"** | 代理缓存/镜像可能不完整，见 §2.1 的禁止推断 |
| **429 语义降级** | 代理链路上的 429 可能来自代理自身限流，**不必然**代表 arxiv 官方限流。退避照常执行，但结论中必须注明该不确定性 |
| **记入 Critical uncertainties** | 若本次检索要支撑创新性声明，把"经代理环境检索"记入 `STATUS.md` 的 Critical uncertainties |

**实现：** [../scripts/literature_search.py](../scripts/literature_search.py) 的
`detect_proxy_environment()`，结果写入输出的 `proxy_env` 字段
（`{"detected", "resolved", "notes", "unresolved"}`）。

> ⚠️ **只告警，不阻断。** 代理环境下的结果依然可用，但**可信度需重新评估**：
> 更应依赖 §3.3 的饱和判据（连续两轮零新增）与 §2.1 的负检索记录来支撑结论。

---

## 7. 本地文献库格式约定

```
./docs/refs/
  ├── index.json               # ★ PDF 索引（强制，见 §7.1）
  ├── papers/
  │   ├── {paper_id}.pdf       # PDF 原文（大文件，不进版本库）
  │   ├── {paper_id}.json      # sidecar 元数据（title/authors/abstract/year/venue/url）
  │   └── {paper_id}.md        # 可选：全文或笔记（参与全文匹配）
  └── cache/
      └── <source>/
          └── {query_hash}.json   # 查询缓存（按源分目录）
```

### 7.1 PDF 索引（强制）

**`docs/refs/` 下的每一个 PDF，都必须在 `docs/refs/index.json` 里有一条记录。**
索引是**可进版本库的元数据**，PDF 本身是大文件、不进版本库——这样别人拿到的是
你的文献清单，而不必下载几十 GB 的原文。

索引结构：

```json
{
  "schema": "research-idea-pipeline/refs-index@1",
  "generated_at": "2025-01-01T00:00:00+08:00",
  "count": 1,
  "pdfs": [
    {
      "file": "papers/2401.01234.pdf",
      "paper_id": "2401.01234",
      "title": "Discrete Diffusion for Combinatorial Optimization",
      "authors": ["Ada Smith", "Bob Jones"],
      "year": 2024,
      "venue": "NeurIPS",
      "arxiv_id": "2401.01234",
      "doi": null,
      "url": "https://arxiv.org/abs/2401.01234",
      "abstract": null,
      "keywords": ["diffusion", "combinatorial optimization"],
      "pages": 12,
      "size_bytes": 1234567,
      "sha256": "…",
      "added_at": "2025-01-01",
      "source": "arxiv",
      "metadata_from": "sidecar",
      "needs_verification": false,
      "sidecar_path": "papers/2401.01234.json",
      "notes_path": "papers/2401.01234.md"
    }
  ]
}
```

**字段约定：**

| 字段 | 必填 | 说明 |
|---|---|---|
| `file` | ✅ | 相对 `docs/refs/` 的路径，POSIX 分隔符；**索引以它作唯一键** |
| `paper_id` | ✅ | 优先取 sidecar 的 `paper_id`，否则 arXiv ID，否则文件名主干 |
| `title` | ✅ | 取不到时用文件名兜底，并把 `needs_verification` 置 `true` |
| `authors` | ✅ | 字符串数组；无法拆分时保留为单元素 |
| `year` | ✅ | 取不到为 `null`，且 `needs_verification = true` |
| `arxiv_id` | ❌ | 新式 `YYMM.NNNNN` 或旧式 `category/NNNNNNN` |
| `url` | ❌ | 缺失但有 `arxiv_id` 时自动补 `https://arxiv.org/abs/<id>` |
| `sha256` | ✅ | 用于检测文件被替换；`--no-hash` 产出的索引无法通过 `--check` |
| `added_at` | ✅ | 首次入库日期；文件内容不变时重建会保留原值 |
| `metadata_from` | ✅ | `sidecar` / `pdf` / `filename`，说明元数据来自哪一层 |
| `needs_verification` | ✅ | `metadata_from == "filename"` 或 `year is null` 时为 `true` |

**元数据来源优先级：** `papers/{paper_id}.json`（sidecar，最准）→ PDF 内嵌元数据
（`pypdf`，缺失时回退命令行 `pdfinfo`）→ 文件名解析（兜底，必然标记待核实）。

**更新时机（强制）：** 新增 / 替换 / 删除 PDF 后**必须重建索引**；检索新下载的
PDF，要在**同一步**写好 sidecar 并重建索引。

```bash
python3 scripts/refs_index.py            # 扫描 ./docs/refs 并写入 index.json
python3 scripts/refs_index.py --check    # 只校验；不一致时退出码 3
python3 scripts/refs_index.py --migrate  # 旧 schema → 当前 schema（保留旧字段）
```

**约束：**

- **未入索引的 PDF 视为不存在。** 任何"本地已有该文献"的论断都必须能指向索引条目。
- `needs_verification = true` 的条目**不得**用于支撑创新性声明（含「首次提出 / 未见前作 /
  复现风险低」），除非已人工补齐；**其数量计入根 `INDEX.md` 的全局 Warnings，超过 5
  触发补元数据 TODO**（见 [evidence-policy.md](evidence-policy.md) §2 规则 7）。
- 索引里**不得**写 PDF 绝对路径——换机器、换用户目录后必须仍然有效。

**旧 schema 的迁移路径（别只会"重建"）：**

`--check` 报 **「索引缺少 pdfs 数组（schema 不符）」** 时，说明索引是旧版形状
（平铺列表，或以文件名为键的字典）。**直接重建会丢掉旧条目里已有的
title / venue / year 等字段**，因此必须用：

```bash
python3 scripts/refs_index.py --migrate   # 保留旧字段 + 补齐 schema，顶层写 migrated_from
python3 scripts/refs_index.py --check     # 迁移后确认一致
```

迁移会把继承来的元数据标 `metadata_from = "legacy"`。**它同样不算"已核实"**——
除非旧条目自己声明过 `needs_verification: false`。迁移完请按上面的 Warnings 规则
清点 `needs_verification` 条数并补 sidecar。

### 7.2 sidecar 单条元数据格式

```json
{
  "paper_id": "2401.01234",
  "title": "...",
  "authors": ["..."],
  "abstract": "...",
  "year": 2024,
  "venue": "NeurIPS",
  "url": "https://arxiv.org/abs/2401.01234",
  "keywords": ["..."],
  "source": "local",
  "notes_path": "papers/2401.01234.md"
}
```

---

## 8. 路径与配置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `--local-dir` / `RESEARCH_LOCAL_LITERATURE` | `./docs/refs/` | 本地文献库根目录（相对**用户工作目录**） |
| `--cache-dir` / `RESEARCH_LIT_CACHE` | `<local-dir>/cache/` | 查询缓存目录。**按源分目录**：`cache/<source>/<hash>.json`，一源失败不污染他源 |
| `--refresh` | 关 | 强制跳过缓存（仍查本地与 arxiv） |
| `--no-cache` | 关 | 不读缓存，但结果仍写入缓存 |
| `--max` | 20 | 每次**每个源**查询的条数上限 |
| `--limit` | 不截断 | 最终返回条数上限（截断保留本地优先顺序） |

> 参考文献属于**跨路线公用资源**，统一放项目根目录的 **`docs/refs/`** 下
> （见 [project-layout.md](project-layout.md) §1）；不要散落到 `routes/<R>/` 或项目根目录。
> 脚本默认 `--local-dir ./docs/refs`，因此无需额外配置。

---

## 9. 来源标注（强制）

**`sources` 是列表，不是单值。** 每条文献结果标注它被哪些源命中：

```json
{"sources": ["crossref", "openalex", "arxiv"], "source": "crossref"}
```

- `sources`：**权威字段**，取并集，按权威序 `crossref > openalex > arxiv > local` 排序。
- `source`：**派生别名** = `sources[0]`，仅为兼容旧消费方（如 sidecar 元数据）。
- 缓存命中另标 `cache_hit: true`。

**结果集默认是「本地 + 全部启用源」的并集**，不是二选一。

> ⚠️ **别混淆：** `docs/refs/index.json` 里的 `source` 是**另一种含义** —— 那是
> **PDF 文件的来源**（`local` / `arxiv`），与"检索命中了哪些源"不是一回事。

### 9.1 源清单与「尽可能多」原则

| 源 | 管什么 | 需要 key | 备注 |
|---|---|---|---|
| `arxiv` | **新** | 否 | Python 包为主；缺包时回退 Atom HTTP 接口。**元数据不含会议** |
| `openalex` | **关系** | 否 | 引文图（前向 `cites:` / 后向 `referenced_works`）+ venue 过滤；建议带 `--mailto` |
| `crossref` | **出处** | 否 | 正式 venue 权威（`container-title`）；建议带 `--mailto` |

**已排除的源及实测原因：** DBLP（上线 Anubis JS 反爬，带浏览器 UA 也挡，程序化不可用）；
Semantic Scholar（无 key 时直接 429；用户提供 key 后可加）。

**「尽可能多」原则（强制）：**

1. 默认启用**全部已实现源**；用 `--sources` 少指定时**必须显式给出理由**并写入报告。
2. 缺源（不可控）**不阻止** L3 达成，但必须：① 报告列出**启用 / 成功 / 失败**三类源；
   ② 结论措辞降级为「据本次检索未见（检索式与源见附录）」；③ **不得**写"首次提出"；
   ④ 记入 `STATUS.md` 的 Critical uncertainties。

### 9.2 单源状态与退出码

每个源有独立状态 `ok` / `partial` / `unavailable` / `skipped`（见 §10 退出码表）。

---

## 10. 命令行用法

```bash
# 默认：本地 + 全部已实现源（arxiv / openalex / crossref）合并
python3 scripts/literature_search.py -q "diffusion model combinatorial optimization" --max 20

# 环境自检（建议先跑）：确认工作解释器与依赖 —— 依赖缺失不等于源不可用
python3 scripts/literature_search.py --check-env

# 创新性声明：L3 穷尽级 + 追加同义词/否定式
python3 scripts/literature_search.py -q "discrete diffusion combinatorial optimization" \
    --level L3 --exhaustive \
    --also-query "score-based generative model discrete optimization" \
    --also-query "limit of diffusion model combinatorial optimization" \
    --from-year 2019 --mailto you@example.com --json

# 会议过滤（A3 第 ③ 级自动化；★ 只在 OpenAlex 上服务端生效）
python3 scripts/literature_search.py -q "..." --venue "Neural Information Processing Systems"

# 引文追溯（A3 第 ⑤ 级）：前向 / 后向
python3 scripts/literature_search.py -q "..." --cited-by "10.1109/TPAMI.2023.3261988"
python3 scripts/literature_search.py -q "..." --references "2209.04747"

# 只用部分源（会打印覆盖警告，须在报告中写明理由）
python3 scripts/literature_search.py -q "..." --sources arxiv,crossref

# 离线：不查任何在线源（会打印规则违反提示；不得支撑创新性声明）
python3 scripts/literature_search.py -q "..." --local-only    # 或 --offline
```

**退出码：**

| 码 | 含义 |
|---|---|
| `0` | 全部启用源成功 |
| `1` | 硬错误（参数、本地库不可读、渲染失败） |
| **`2`** | **存在降级** —— **任一**启用源为 `unavailable` 或 `partial`；结果不完整，检索视为未饱和 |
| **`4`** | **环境不满足** —— 依赖缺失或找不到可用解释器（**依赖缺失 ≠ 源不可用 ≠ 没人做过**） |

**输出：** 文献列表（含 `sources`）+ **每源状态** + 检索过程记录 + **源日志**（429 /
失败 / 代理）+ 缓存更新记录 + 范围扩大记录 + **逐检索式的负检索记录** +
**饱和判定与尽职调查等级达成情况**（§3）。

