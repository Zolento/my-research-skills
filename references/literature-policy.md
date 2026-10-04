# 文献检索规范（所有 Mode 强制遵守）

> **三条铁律：**
> 1. **先本地，后 arxiv——但本地命中不是终点。禁止只停留在本地。**
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
  路径 ./local_literature/（可配置，见 §8）
  匹配：标题、摘要、关键词、全文（若为 Markdown/JSON）
  命中：纳入结果集，标注 source="local" —— 但流程继续，不得在此返回

Step 2: arxiv 检索（触发条件见 §2）
  使用 Python arxiv 包
  查询构造：关键词 + 会议过滤 + 时间范围
  命中：拉取元数据与摘要，缓存到本地库，标注 source="arxiv"
  ★ 即使 Step 1 已命中，只要触发 §2 任一条件，本步必须执行

Step 3: 信息不足补齐
  仅补充缺失字段，不重复拉取已有内容

Step 4: 饱和判定（见 §3.3）
  未达饱和 → 按 D3 扩大策略继续检索
  已达饱和 → 合并去重、输出，并记录负检索证据
```

**"信息不足"的判定**（满足任一即触发 Step 3）：

- 命中条数 < 用户要求的数量下限；
- 命中条目缺少字段（`abstract` / `year` / `venue` 缺失）；
- 本地命中没有与查询直接对应的**最接近先前工作**。

---

## 2. 强制扩检触发条件（Mandatory Escalation Triggers）

**只要命中下列任一条件，就禁止只停留在本地，必须执行 arxiv 检索并按要求扩大范围。**
这是一个**或**条件列表，命中一条即生效。

| # | 触发条件 | 说明 | 最低要求 |
|---|---|---|---|
| **T1** | **创新性声明** | 任何形式的"首次提出 / 没人做过 / 首个 / first to / 该方向空白 / 无人研究" | §3.2 **L3 穷尽级** |
| **T2** | **理论不清** | 定理无法证明、证明有缺口、假设无法验证、收敛性/紧性说不清 | §3.2 **L2 强化级** |
| **T3** | **可行性不确定** | 不确定能不能做、算力/数据是否够、是否存在已知不可行结论 | §3.2 **L2 强化级** |
| **T4** | **新颖性判定** | Mode B 的 B1、Mode C 的 S-Lit/S-Nov 环节 | §3.2 **L3 穷尽级** |
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
4. 检索后仍无解 → 在 INDEX.md 的 **Warnings** 中记录"已知未知"，并标注待核实。

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

> **不满足饱和就停止，属于违规。** 若因 arxiv 不可用而被迫停止，必须显式标注
> "检索未达饱和，原因：arxiv 不可用"，并写入 INDEX.md 的 **Warnings**。

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

---

## 5. arxiv 调用规范

### 5.1 参考伪代码（原规范保留，含工程修正）

```python
import arxiv
import time
import os
import json

LOCAL_DIR = "./local_literature/"
CACHE_DIR = "./local_literature/cache/"
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

### 5.2 对伪代码的两点工程修正

1. **`arxiv.HTTPError` 并非 arxiv 包稳定导出的异常。** 实际 429 多为
   `urllib.error.HTTPError`（`.code`）或带 `.response.status_code` 的异常。实现脚本
   兼容捕获 `status` / `code` / `status_code` 及异常文本中的 `429`。
2. **`hash(query)` 跨进程不稳定**（受 `PYTHONHASHSEED` 影响），不能作缓存文件名。
   实现脚本改用 `hashlib.md5(query)[:16]`。

### 5.3 本版新增的行为变更

| 变更 | 说明 |
|---|---|
| arxiv 成为**默认执行** | 脚本默认同时查本地与 arxiv，不再因本地命中而短路 |
| 新增 `--local-only` | **显式**声明只用本地（离线场景）；使用时必须提示"违反默认检索规则" |
| 新增 `--exhaustive` | 自动执行多轮扩大检索，直到饱和（§3.3） |
| 新增 `--also-query` | 追加同义词/上位词/否定式检索式（D3 第 ① 级） |
| 新增 `--level {L1,L2,L3}` | 按 §3.1 校验并记录尽职调查等级 |

---

## 6. 429 处理规则

- 捕获限流错误，若 `status == 429`，按**指数退避**等待：`10s → 20s → 40s → 80s → 160s`。
- **最多重试 5 次。**
- **重试期间不得发起新的 arxiv 请求。**
- 若 5 次后仍失败，**返回本地已有结果**，并标注：
  **"arxiv 暂时不可用，以下结果仅来自本地库"**。
  **同时**在 INDEX.md 的 **Warnings** 记录"检索未达饱和"。
- 非 429 的 HTTP 错误：不重试，直接报告。
- 必须输出**等待日志**。

---

## 7. 本地文献库格式约定

```
./local_literature/
  ├── papers/
  │   ├── {paper_id}.json      # 元数据：title/authors/abstract/year/venue/url
  │   └── {paper_id}.md        # 可选：全文或笔记
  ├── cache/
  │   └── {query_hash}.json    # arxiv 查询缓存
  └── index.json               # 本地索引（可选）
```

单条元数据 JSON：

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
| `--local-dir` / `RESEARCH_LOCAL_LITERATURE` | `./local_literature/` | 本地文献库根目录（相对**用户工作目录**） |
| `--cache-dir` / `RESEARCH_LIT_CACHE` | `<local-dir>/cache/` | arxiv 查询缓存目录 |
| `--refresh` | 关 | 强制跳过缓存（仍查本地与 arxiv） |
| `--max` | 20 | `max_results` |

> 公用文献库属于**跨路线公用资源**，按 [project-layout.md](project-layout.md) 应放在
> 项目根目录的 `shared/` 下管理，并在 AGENTS.md 中声明。

---

## 9. 来源标注（强制）

每条文献结果都必须标注 `source="local"` 或 `source="arxiv"`（缓存命中另标
`cache_hit: true`）。**结果集默认是本地 + arxiv 的并集**，不是二选一。

---

## 10. 命令行用法

```bash
# 默认：本地 + arxiv 合并（arxiv 不会因本地命中而被跳过）
python3 scripts/literature_search.py --query "diffusion model combinatorial optimization" --max 20

# 创新性声明：L3 穷尽级 + 追加同义词/否定式检索式
python3 scripts/literature_search.py --query "discrete diffusion combinatorial optimization" \
    --level L3 --exhaustive \
    --also-query "score-based generative model discrete optimization" \
    --also-query "limit of diffusion model combinatorial optimization" \
    --from-year 2019 --json

# 离线/无网：显式只用本地（会打印规则违反提示）
python3 scripts/literature_search.py --query "..." --local-only
```

**退出码：** `0` 正常；`1` 硬错误；`2` arxiv 不可用、已回退本地结果（检索视为未饱和）。

**输出：** 文献列表（含 `source`）+ 检索过程记录（每轮检索式与命中）+ 429 等待日志
+ 缓存更新记录 + **尽职调查等级达成情况**（§3）。
