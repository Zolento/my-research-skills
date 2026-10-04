# 文献检索规范（所有 Mode 强制遵守）

> **核心规则：先本地，后 arxiv；429 必须等待。**
>
> 可直接运行的实现见 [../scripts/literature_search.py](../scripts/literature_search.py)，
> 本文档是其行为规范与参考伪代码。

---

## 1. 检索优先级

```
Step 1: 搜索本地文献库
  - 路径：./local_literature/（可配置，见 §5）
  - 匹配：标题、摘要、关键词、全文（若为 Markdown/JSON）
  - 命中：直接返回，标注来源为 "local"

Step 2: 本地未命中 → 调用 arxiv
  - 使用 Python arxiv 包
  - 查询构造：关键词 + 会议过滤 + 时间范围
  - 命中：拉取元数据与摘要，缓存到本地库，标注来源为 "arxiv"

Step 3: 本地命中但信息不足 → 补充 arxiv 检索
  - 仅补充缺失字段，不重复拉取已有内容
```

**"信息不足"的判定**（满足任一即触发 Step 3）：

- 命中条数 < 用户要求的数量下限；
- 命中条目缺少字段（`abstract` / `year` / `venue` 缺失）；
- 本地命中没有与查询直接对应的**最接近先前工作**。

---

## 2. arxiv 调用规范（参考伪代码）

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
    # Step 1: 本地搜索
    local_hits = search_local(query)
    if local_hits:
        return local_hits

    # Step 2: arxiv 搜索
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

    # Step 3: 缓存到本地
    cache_results(query, results)
    return results

def search_local(query):
    # 遍历 LOCAL_DIR 下的 .json / .md / .pdf 元数据
    # 关键词匹配标题、摘要、关键词字段
    # 返回命中的文献列表，标注 source="local"
    ...

def extract_metadata(paper):
    return {
        "title": paper.title,
        "authors": [a.name for a in paper.authors],
        "abstract": paper.summary,
        "published": str(paper.published),
        "url": paper.entry_id,
        "source": "arxiv"
    }

def cache_results(query, results):
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = hash(query) % 10**8
    with open(f"{CACHE_DIR}/{key}.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
```

### 2.1 对伪代码的两点工程修正

1. **`arxiv.HTTPError` 并非 arxiv 包稳定导出的异常。** 实际触发 429 时抛出的多为
   `urllib.error.HTTPError`（带 `.code`）或 `arxiv.ArxivError`。实现脚本采用
   兼容捕获：检查异常的 `status` / `code` / `response.status_code` 属性，并在
   异常文本中匹配 `429`。
2. **`hash(query)` 在 Python 中每个进程随机化（PYTHONHASHSEED），不能作为缓存
   文件名。** 实现脚本改用 `hashlib.md5(query).hexdigest()[:16]`，保证跨进程稳定，
   cache 命中才真正有效。

---

## 3. 429 处理规则

- 捕获限流错误，若 `status == 429`，按**指数退避**等待：`10s → 20s → 40s → 80s → 160s`。
- **最多重试 5 次。**
- **重试期间不得发起新的 arxiv 请求。**
- 若 5 次后仍失败，**返回本地已有结果**，并标注：
  **"arxiv 暂时不可用，以下结果仅来自本地库"**。
- 非 429 的 HTTP 错误：不重试，直接向上抛出/报告。
- 必须输出**等待日志**（Mode D 交付物之一）。

---

## 4. 本地文献库格式约定

```
./local_literature/
  ├── papers/
  │   ├── {paper_id}.json      # 元数据：title/authors/abstract/year/venue/url
  │   └── {paper_id}.md        # 可选：全文或笔记
  ├── cache/
  │   └── {query_hash}.json    # arxiv 查询缓存
  └── index.json               # 本地索引（可选）
```

**单条元数据 JSON 约定：**

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

- `{paper_id}.md` 若存在，参与全文关键词匹配。
- `index.json` 可选；不存在时脚本直接遍历 `papers/`。

---

## 5. 路径与配置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `--local-dir` / `RESEARCH_LOCAL_LITERATURE` | `./local_literature/` | 本地文献库根目录（相对**用户工作目录**，不是 Skill 目录） |
| `--cache-dir` / `RESEARCH_LIT_CACHE` | `<local-dir>/cache/` | arxiv 查询缓存目录 |
| `--refresh` | 关 | 强制跳过本地命中，直接走 arxiv |
| `--max` | 20 | `max_results` |

> Skill 目录内自带的 `../local_literature/` 只是**格式示例**，实际运行时默认指向
> 用户当前工作目录下的 `./local_literature/`。

---

## 6. 来源标注（强制）

**每条文献结果都必须标注** `source="local"` 或 `source="arxiv"`，Mode D 输出表格中
体现为"来源"列。禁止输出不标来源的文献条目。

---

## 7. 命令行用法

```bash
# 本地优先，未命中走 arxiv
python scripts/literature_search.py --query "diffusion model combinatorial optimization" --max 20

# 限定时间范围 + 强制刷新本地缓存
python scripts/literature_search.py --query "diffusion model combinatorial optimization" \
    --from-year 2022 --to-year 2025 --refresh

# 指定本地库位置，输出 JSON
python scripts/literature_search.py --query "score-based generative model" \
    --local-dir ./local_literature --json
```

脚本输出包含：命中的文献列表（含 `source`）、检索过程记录、以及 429 等待日志
（stderr）。退出码：`0` 正常；`2` arxiv 不可用但已回退到本地结果；`1` 硬错误。
