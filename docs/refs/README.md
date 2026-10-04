# docs/refs/ —— 参考文献库（格式示例）

> **这是给你自己项目用的格式示例。** 在真实项目里，参考文献统一放项目根目录的
> `docs/refs/`；本目录只是本 Skill 仓库内的骨架示范。

`docs/refs/` 同时就是**检索脚本的本地文献库根目录**（脚本默认
`--local-dir ./docs/refs`），因此无需额外配置。

```
docs/refs/
├── papers/
│   ├── {paper_id}.json      # 元数据：title/authors/abstract/year/venue/url/keywords
│   └── {paper_id}.md        # 可选：全文或笔记（参与全文匹配）
├── cache/
│   └── {query_hash}.json    # arxiv 查询缓存（键含 max_results 与年份）
└── index.json               # 本地索引（可选）
```

单条元数据示例：

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

**规则：**

1. 论文元数据/笔记/缓存**一律放这里**，不要散落到 `routeX/` 或项目根目录。
2. 检索结果的来源必须标注 `source="local"` 或 `source="arxiv"`。
3. 缓存是生成物，按需 `.gitignore`；论文 PDF 等大文件不要进版本库。
4. 路径可用 `--local-dir` 或 `RESEARCH_LOCAL_LITERATURE` 覆盖，缓存目录用
   `--cache-dir` 或 `RESEARCH_LIT_CACHE` 覆盖。

详见 [../../references/literature-policy.md](../../references/literature-policy.md)。
