# P3 + P5：Zotero 原生全文检索 / PDF 页级抽取 / 缓存 —— 实现笔记（branch-local）

分支：`feat/zotero-library-ops-fulltext`；模块：`scripts/zotero_fulltext.py`（新）；
测试：`scripts/test_zotero_fulltext.py`（新）。本文件属开发过程记录，**不合并进 main**。

## 1. 归并规则（`search_indexed`）

`qmode=everything` 同时返回附件与父条目。实现按 **`data.parentItem` 归并到父条目 key**：

- 有 `parentItem` 的条目（attachment / note / annotation）→ 归入父条目分组；
  父条目也在结果里 → 直接用父条目元数据；不在 → `get_item` 补取；仍取不到 →
  占位记录（字段全 `None`，`parent_metadata_missing=True`），**绝不编造标题/年份**。
- **孤儿附件**（`itemType=attachment` 且无 `parentItem`，实测库里 68 个）→ 以附件自身
  key 独立成条，标 `orphan_attachment=True`，`attachments` 里包含它自己；
  **既不丢也不与父条目重复计数**（分组字典按 key 去重）。
- 独立 note / annotation 同样保留（`orphan_child=True`），不静默丢弃。

评分与 `literature_search.search_local` 语义一致（标题 3.0 / 关键词 2.5 / 摘要 1.5 /
全文 1.0 + 短语 5.0，`matched_terms` 排序，`_score` 三位小数，年份未知在过滤时排除）。
区别：`search_local` 丢弃 `score==0`，本模块**保留** Zotero 索引命中并标
`matched_via="zotero_index"`——否则会丢掉 Zotero 词干/字段索引匹配到的真实命中。

## 2. 页码纪律（硬要求 2）

- `GET /items/{key}/fulltext` 只有 `content/indexedPages/totalPages`，**没有页码边界**。
  索引命中一律 `verification="indexed_fulltext"`，记录里**没有** `page` / `pages` 字段。
- `page_verified` **只**由真实 PDF 页解析产生（`search_pdf_pages` /
  `search_extracted_pages`），并带 1 起算物理页 `page`、best-effort `printed_page`、
  真实文本片段 `snippet`。
- `search_two_layer(deep=True)`：索引命中即使深读没找到页命中，也**保持**
  `indexed_fulltext`，不升级、不给页码。
- `extract_pages` 的 `page` 是**物理页**，`printed_page` 是**印在页面上的标签**：
  优先用真实 `/PageLabels`（不等于默认 `1..N` 时），否则从页眉前 3 行 / 页脚后 5 行
  做保守解析；取不到就是 `None`。pypdf 在无 `/PageLabels` 时会**伪造** `["1","2",…]`，
  实现显式识别并拒绝它，避免「物理页 == 印刷页」的臆断。
- 每页 `quality`：`ok` / `low_text`（<100 去空白字符）/ `empty`（无文本无图）/
  `scanned`（无文本但有图像 XObject）/ `two_column_order`（疑似两栏阅读顺序错乱）。
  `char_offset` 索引到 `"\n".join(page.text)`，测试断言切片恒等。

## 3. 附件路径（硬要求 3）

`resolve_attachment_path` 顺序：Local API `file/view/url`（只接受 `file://`）→
`linked_file` 绝对 `path`（及可选 `ZOTERO_LINKED_ATTACHMENT_BASE`）→
`storage/<key>/<filename>`。`linked_url` 与任何 http(s) 一律返回 `None`
（测试用 `mock.patch` 断言 `urlopen` 从未被调用）。`filename` 做路径穿越校验。
不移动 / 重命名 / 删除任何文件。

## 4. 缓存身份（硬要求 6）

身份 = Server ID + Library ID + Item Key + Attachment Key + sha256 内容指纹；
路径 `<root>/<server_id>/<library_id>/<item_key>/<attachment_key>/<sha256|nofp>.json`，
原子写入、权限 0600。Server ID 是路径第一层 ⇒ Server ID 变化整库缓存自动失效；
PDF 变化 ⇒ 指纹变化 ⇒ 旧文本不被读取。指纹取不到时**跳过缓存**（宁可重抽不用旧文本）。
`invalidate_by_fingerprint(...)` 可显式清理指纹不匹配的旧记录。

缓存根默认 `research-idea-pipeline/.research-idea-pipeline/zotero-fulltext-cache/`，
`git check-ignore -v` 实测命中 `.gitignore:14:.research-idea-pipeline/`，
**无需**再改 `.gitignore`；仓库内未生成任何缓存文件。

## 5. 降级（硬要求 8）

`search_two_layer(deep=True)` 对每个附件单独 `try/except`：缺失 / 损坏 / 无文本 → 该条目
降级到 `insufficient_evidence`（有索引则保持 `indexed_fulltext`）并写 `warnings`，
不影响同批其它条目；索引检索整体失败时返回结构化空结果而非抛异常。

## 6. 接线提示（给 Lead）

`literature_search` 顶层 `import zotero_fulltext` 是安全的：本模块顶层**不**导入
`literature_search`（只在 `_tokenize` / `_in_year_range` 里惰性导入以复用语义），无循环导入。
`client` 传 `zotero_client` 模块（或 `None`）即可；显式传入的 client 缺方法时本模块
**不会**回落到真实网络。
