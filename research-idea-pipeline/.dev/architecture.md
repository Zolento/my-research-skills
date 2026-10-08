# Zotero CRUD / 全文检索 / 深读 —— 架构与接口契约（branch-local）

分支：`feat/zotero-library-ops-fulltext`
基线：`main` = `8882be5a57aa4f50d1c75b84417be8c97c5ee650`
worktree：`/home/lenovo/code/myproj/skills-dev/zotero-library-ops-fulltext`

## 0. 基线验证（P0 实测）

| 项目 | 结果 |
|---|---|
| `unittest discover -s scripts -p "test_*.py"` | **679 tests OK**（3 skipped） |
| `refs_index.py --check` | exit 0 |
| `state_check.py --selftest` | OK |
| `release_check.py` | **PASS** |

基线输出存于 `.dev/baseline-tests.txt` 与 `.dev/baseline-release.txt`。

## 1. 现有实现审计（禁止重复开发）

### 已有，必须复用
- `zotero_client.py`：`probe()` / `fetch_items()` / `item_to_record()` / `item_to_sidecar()` /
  `bibliographic_items()` / `pdf_children()` / DOI、arXiv 归一化。**只读**。
- `zotero_refs.py`：Zotero → `docs/refs/` 导出；`safe_paper_id()` / `attachment_path()` /
  `build_plan()` / `export()` / `run_check()`。
- `literature_search.py`：`resolve_local_entries()`（Zotero 优先，回落 refs）、
  `search_local()`、`query_source()`、合并层调用、CLI 与退出码
  （`EXIT_OK=0` / `EXIT_ERROR=1` / `EXIT_SOURCE_DOWN=2` / `EXIT_ENV=4`）。
- `literature_sources.py`：`Source` / `REGISTRY` / `ZoteroSource` / `merge_records`。
- `refs_index.py`：`docs/refs/index.json` 的 schema 与 `--check`。

### 实测得到的 API 事实（Zotero 10.0.3）
- `GET /items/{attachmentKey}/fulltext` → `{content, indexedPages, totalPages}`。
  **`content` 是扁平文本，没有页码边界** → 页码级引用**只能**来自真实 PDF 解析。
- `GET /fulltext?since=N` → dict：`{attachmentKey: <int>}`（索引版本/长度快照）。
- `GET /items?q=...&qmode=everything` 同时返回**附件**与**父条目** → 必须按
  `parentItem` 归并回论文。实测样本 12/12 有全文索引，`indexedPages == totalPages`。
- `GET /items/{key}/children`、`GET /items/{key}/file/view/url`（返回 `file://`）可用。
- 写入：`POST /api/local/authorize`（需 `Zotero-Server-ID`）→ `{key, remember}`；
  Deny → `403 {"denied":true}`；授权 429 限流。写入需 `Zotero-API-Key` +
  `Zotero-Server-ID` + `Zotero-API-Version: 3`；并发用 `If-Unmodified-Since-Version`
  或对象 `version`；单批上限 50；**PATCH 是浅合并，数组字段整体替换**。
- `/api/items/new` **不存在**（404）→ 字段模板用 `GET /api/itemTypeFields?itemType=`。
  该端点返回**本地化字段名**，不得当作内部字段名。

### 环境
- `pypdf 6.9.2` 可用；`pdftotext` / `pdfinfo`（poppler）可用；无 pymupdf。

### 待修正
- `references/research-state-policy.md:362` 写死 `docs/refs/index.json` 为元数据来源
  → 改为「按活动文献后端解析」（见 §5.4）。

## 2. 模块划分与写入范围（避免冲突）

| 模块 | 职责 | 负责 |
|---|---|---|
| `scripts/zotero_client.py` | 只读原语扩展（get_item / children / fulltext / file 解析） | Lead |
| `scripts/zotero_write.py` | 授权、写请求传输、能力状态、缓存失效 | Lead |
| `scripts/zotero_crud.py` | create/update/tags/collections/notes/delete | 子代理 A |
| `scripts/zotero_fulltext.py` | 原生全文检索 + 附件访问 + PDF 页级抽取 + 缓存 | 子代理 B |
| `scripts/zotero_deepread.py` | deep_read 模式 + 证据锚点 | 子代理 C |
| `scripts/literature_search.py` | 两层检索接线 | Lead |

## 3. 冻结接口

### 3.1 `zotero_write.py`（Lead 实现，A 只调用）

```python
DEFAULT_LOCAL_API, PROBE_TIMEOUT
STATUS_RW = "ZOTERO_RW"; STATUS_RO = "ZOTERO_RO"; STATUS_REFS = "REFS_FALLBACK"

class ZoteroForbidden(RuntimeError): ...      # 无权 / 用户拒绝
class ZoteroAuthDenied(ZoteroForbidden): ...
class ZoteroConflict(RuntimeError): ...       # 412

class WriteClient:
    def __init__(self, base_url=None, *, key=None, timeout=..., log=None): ...
    @property
    def server_id(self) -> Optional[str]: ...
    def status(self) -> str: ...              # RW / RO / REFS
    def capability(self) -> Dict[str, Any]: ...  # {status, server_id, writable, reason}
    def authorize(self, app_name=...) -> Dict[str, Any]:  # {key, remember}
    def request(self, method, path, *, body=None, version=None) -> Tuple[int, Any]: ...
    def patch(self, kind, key, payload, *, version=None) -> Dict[str, Any]: ...
    def post(self, kind, payloads) -> Dict[str, Any]: ...
    def delete(self, kind, key, *, version=None) -> Tuple[int, Any]: ...
    def invalidate(self) -> None: ...          # Server ID 变化时清空 key 与版本缓存
```

- key 只从内存/`authorize()` 拿，**绝不落盘、绝不进日志**。
- Server ID 变化 → `invalidate()`。
- 未授权时调用写方法 → 抛 `ZoteroForbidden`，**不得**静默回落 refs 写入。

### 3.2 `zotero_crud.py`（子代理 A）

```python
def find_by_identifiers(client, *, doi=None, arxiv_id=None, title=None, year=None) -> List[dict]
def create_paper(client, metadata, *, collections=None, tags=None, dry_run=False) -> dict
    # 返回 {created: bool, item_key, version, record, duplicate_of, dry_run}
def update_paper(client, item_key, patch, *, dry_run=False) -> dict
    # 返回 {updated: bool, item_key, version, before, after, changed_fields, dry_run}
def add_tags(client, item_key, tags) -> dict          # 集合合并
def remove_tags(client, item_key, tags) -> dict       # 只去关联，不删全局 tag
def add_to_collection(client, item_key, collection_key) -> dict
def remove_from_collection(client, item_key, collection_key) -> dict
def create_note(client, parent_key, note, *, tags=None) -> dict
def get_notes(client, parent_key) -> List[dict]
def delete_paper(client, item_key, *, dry_run=True, confirm=False, state=None) -> dict
```

### 3.3 `zotero_fulltext.py`（子代理 B）

```python
def search_indexed(client, query, *, limit=50, from_year=None, to_year=None) -> List[dict]
    # 原生 qmode=everything；按 parentItem 归并回论文；去重
def attachment_fulltext(client, attachment_key) -> Optional[dict]   # {content, indexedPages, totalPages}
def resolve_attachment_path(client, attachment) -> Optional[Path]   # 优先 file/view/url，回退 storage
def extract_pages(pdf_path, *, sha256=True) -> dict
    # {sha256, num_pages, pages: [{page, printed_page, text, char_offset, quality}]}
def search_pdf_pages(pdf_path, query, *, pages=None) -> List[dict]  # 页级命中
def get_text_cache(...) / invalidate_by_fingerprint(...)
```

**页码纪律**：`indexed` 命中一律标 `indexed_fulltext`，**不得**升级为 `page_verified`。

### 3.4 `zotero_deepread.py`（子代理 C）

```python
VERIFICATION_LEVELS = ("metadata_only","abstract_only","indexed_fulltext",
                       "pdf_text_verified","page_verified","insufficient_evidence")
def deep_read(client, item_key, *, mode="overview", sections=None, question=None,
              pages=None, budget=...) -> dict
def compare_papers(client, item_keys, *, aspect=...) -> dict
def make_evidence_anchor(...) -> dict
```

证据锚点结构见任务书 §5.3；**不得**扩展 Research State Schema。

## 4. 约束

- 不改 R0—R14、四个语义入口、L1/L2/L3、S1—S7 / V1—V24。
- 不改 `LIT<n>` 定义。
- 写操作默认 dry-run / 需显式确认；批量删除默认禁止。
- 不引入向量数据库或大型框架；仅标准库 + 既有 `pypdf`。
- 测试不得依赖运行中的 Zotero；真实 Zotero 测试单独标记。

## 5. 验收

- 全量 `test_*.py` + `refs_index.py --check` + `state_check.py --selftest` + `release_check.py` PASS。
- 只提交到本分支，**不 push、不 merge、不 release**。
