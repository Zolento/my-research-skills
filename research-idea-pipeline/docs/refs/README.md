# docs/refs/ —— 参考文献库（格式示例）

> **这是给你自己项目用的格式示例。** 在真实项目里，参考文献统一放项目根目录的
> `docs/refs/`；本目录只是本 Skill 仓库内的骨架示范。

`docs/refs/` 同时就是**检索脚本的本地文献库根目录**（脚本默认
`--local-dir ./docs/refs`），因此无需额外配置。

```
docs/refs/
├── index.json               # ★ PDF 索引（强制，见下）
├── papers/
│   ├── {paper_id}.pdf       # PDF 原文（大文件，不进版本库）
│   ├── {paper_id}.json      # sidecar 元数据：title/authors/abstract/year/venue/url
│   └── {paper_id}.md        # 可选：全文或笔记（参与全文匹配）
└── cache/
    └── {query_hash}.json    # 查询缓存（**按源分目录**：<source>/<hash>.json）
```

---

## ★ PDF 索引（强制）

**`docs/refs/` 下的每一个 PDF，都必须在 `docs/refs/index.json` 里有一条记录。**

索引是**可进版本库的元数据**；PDF 本身是大文件、**不进版本库**。这样 clone 你项目的人
拿到的是完整的文献清单，而不必下载几十 GB 原文。

```bash
python3 scripts/refs_index.py            # 扫描 ./docs/refs，写入 ./docs/refs/index.json
python3 scripts/refs_index.py --check    # 只校验；不一致时退出码 3
```

索引长这样：

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

**元数据来源优先级：**

1. `papers/{paper_id}.json`（**sidecar**，最准 —— 检索脚本写入的元数据）
2. PDF 内嵌元数据（`pypdf`；缺失时回退命令行 `pdfinfo`）
3. 文件名解析（兜底；此时 `metadata_from = "filename"`、`needs_verification = true`）

**关键字段：** `file` 是唯一键（相对 `docs/refs/` 的路径）；`sha256` 用来发现文件被
替换；`added_at` 在文件内容不变时重建会保留原值；`needs_verification = true` 的条目
**不得**用于支撑创新性声明。

---

## sidecar 单条元数据示例

```json
{
  "paper_id": "2401.01234",
  "title": "…",
  "authors": ["…"],
  "abstract": "…",
  "year": 2024,
  "venue": "NeurIPS",
  "url": "https://arxiv.org/abs/2401.01234",
  "keywords": ["…"],
  "source": "local"
}
```

---

## 规则

1. 论文元数据/笔记/缓存**一律放这里**，不要散落到 `routeX/` 或项目根目录。
2. **每个 PDF 必须有索引条目**；未入索引的 PDF 视为不存在。
3. 新增 / 替换 / 删除 PDF 后**必须重建索引**（`refs_index.py`）；检索新下载 PDF 时，
   要在同一步写好 sidecar 并重建索引。
4. **检索结果**的来源必须标注 `sources=["local" | "arxiv" | "openalex" | "crossref"]`（`source` 是派生别名 = `sources[0]`）。注意 `index.json` 里的 `source` 是**PDF 来源**，含义不同。
5. 缓存与大文件（PDF）按需 `.gitignore`；**`index.json` 必须进版本库**。
6. 索引里**不得**写绝对路径——换机器、换用户目录后必须仍然有效。
7. 路径可用 `--local-dir` 或 `RESEARCH_LOCAL_LITERATURE` 覆盖，缓存目录用
   `--cache-dir` 或 `RESEARCH_LIT_CACHE` 覆盖。

详见 [../../references/literature-policy.md](../../references/literature-policy.md) §7。
