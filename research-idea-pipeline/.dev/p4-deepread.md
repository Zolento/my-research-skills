# P4 — deep_read + 证据锚点 + Research State 兼容（子代理 C）

状态：**完成**（branch `feat/zotero-library-ops-fulltext`）

## 交付物

| 文件 | 说明 |
|---|---|
| `scripts/zotero_deepread.py` | 新增。`deep_read` / `compare_papers` / `make_evidence_anchor` |
| `scripts/test_zotero_deepread.py` | 新增。29 条离线测试（stdlib unittest） |
| `references/research-state-policy.md` | 只改 §3.6 `literature[].ref` 一行（活动文献后端） |

未触碰 `zotero_client.py` / `zotero_write.py` / `literature_search.py` /
`zotero_fulltext.py` / `zotero_crud.py` / `SKILL.md` / `README.md` / 根 `AGENTS.md`。

## 验证等级强制点

- `_grade()` 是**唯一**定级入口；`used_index` 分支固定返回 `indexed_fulltext`，
  没有升级到 `page_verified` 的路径。
- `page_verified` 仅当 `used_pdf_pages and page_located`（真实 PDF 页文本 + 指到页）。
- 只有摘要 → `abstract_only`；只有元数据 → `metadata_only`。
- PDF 覆盖不完整 / 空白页 / `low_text` / `two_column_order` / `scanned`
  → 结果 `insufficient_evidence` + `availability.page_coverage` 如实写覆盖范围。
- `make_evidence_anchor()` 对非 `page_verified` 传 `page` **抛 ValueError**；
  `page_verified` 必须同时有 `page` + 非空 `quote`。
- PDF 指纹不匹配（`fingerprint_expected`）→ 锚点 `stale=True` + `needs-review`。

## 锚点形状

11 个契约字段 + 2 个 freshness 扩展：

```
library_backend, zotero_item_key, attachment_key, doi, pdf_sha256,
page, section, quote, claim, assessment, verification,
stale, fingerprint_expected
```

`page` 仅在 `verification == "page_verified"` 时非 None。

## 依赖降级

`zotero_fulltext` 惰性导入，调用优先级：
client 自带方法 → `zotero_fulltext` → `zotero_client` / 内建 pypdf 页级回退。
三条都不可用 → 报 `page_extraction_available=false`，不崩溃。
已用真实 `zotero_fulltext.extract_pages` 实测兼容（`page_verified` 与 scanned→insufficient 均通过）。

## novelty（E）

`mode="novelty"` **不裁决**，只抽取结构 facet + 暴露既有枚举
（`epistemic_status` 来自 claim-first-policy；`verdict` / `near_neighbor_verdict` /
`claimed_novelty_level` 来自 `structural_equivalence_check` 常量，缺失时用同值兜底）。
`verdict` 固定 `uncertain`，不新增 reviewer、不新增评分。
