# Zotero Local API 使用规范

本文档约束 `research-idea-pipeline` 如何访问本机 Zotero 文献库。
它是 [literature-policy.md](literature-policy.md) §1.1 Step 1 的接口附录。

> **核验状态（Zotero 10.0.3 实测）**
> 本文档的端点、状态码与授权流程已逐条对照运行中的 Local API 与 Zotero 源码
> `server_localAPI.js` 核验。
> **一处更正：** `GET /api/items/new?itemType=...` 是 **Web API** 端点，
> Local API 未实现（实测 404）。本机取字段模板请用
> `GET /api/itemTypeFields?itemType=<type>`（实测 200）。
> 未核验项在文中标「待核实」。

## 1. 基本配置

- API Base URL：`http://127.0.0.1:23119/api`
- API Version：`3`
- 个人文献库前缀：`/api/users/0`
- Zotero 版本：10+（支持本地写入）
- 不需要 Zotero Cloud API Key。
- 不需要联网，但必须运行 Zotero 桌面客户端。

在 Zotero `Settings → Advanced` 中勾选：

`Allow other applications on this computer to communicate with Zotero`

对应偏好键为 `extensions.zotero.httpServer.localAPI.enabled`。
未勾选时 Local API 返回 `403`。

Local API 仅用于本机通信，不得暴露到公网。

## 2. 服务探测

先请求 `GET /api/`。
它返回 `200` 且带响应头 `Zotero-API-Version: 3`（正文为占位文本）。

再请求 `GET /api/users/0/items/top?limit=5`。
该请求成功即表示文献库可读。

`scripts/zotero_client.py` 的 `probe()` 只取响应头 `Zotero-Server-ID`。
取不到即判定不可用，交由调用方回落 `docs/refs/`。

注意：

- 文献库为空不代表服务不可用。
- `403` 表示 Local API 未启用。
- `Zotero-Server-ID` 用于识别数据库实例。
- Server ID 变化后必须清除旧缓存与对象版本信息。
- 不得读取或修改 `zotero.sqlite` 来代替 API。

## 3. 常用读取 API

以下路径以 `/api/users/0` 为前缀。

| 操作 | 方法与路径 |
|---|---|
| 查询顶层文献 | `GET /items/top` |
| 查询全部条目 | `GET /items` |
| 标题与作者搜索 | `GET /items?q=keyword` |
| 全文索引搜索 | `GET /items?q=keyword&qmode=everything` |
| 获取单篇论文 | `GET /items/{key}` |
| 获取子条目与附件 | `GET /items/{key}/children` |
| 获取 Collections | `GET /collections` |
| 获取指定 Collection 文献 | `GET /collections/{key}/items/top` |
| 获取 Tags | `GET /tags` |
| 执行已保存搜索 | `GET /searches/{key}/items` |
| 获取字段模板 | `GET /api/itemTypeFields?itemType=<type>` |
| 获取条目类型 | `GET /api/itemTypes` |

查询支持 `limit`、`start`、`sort`、`direction`、`tag`、`since` 等参数。
读请求不需要认证。

本地 API 默认返回全部匹配结果。
`limit` 缺省时取剩余全部。
大型文献库建议主动分页。

`qmode=everything` 走 Zotero 索引，不等于直接读 PDF 正文。

DOI 检索没有独立的精确查询端点。
应读取候选记录或使用本地索引，再对标准化 DOI 做精确比较。

`/api/itemTypes`、`/api/itemFields`、`/api/itemTypeFields`、`/api/creatorFields`
返回**本地化字段名**（中文环境下为中文）。
`locale` 参数不受支持。
需要稳定英文名时用 `GET /api/creatorFields`。

### 3.1 全文与附件端点（实测行为）

| 端点 | 返回 | 关键约束 |
|---|---|---|
| `GET /items/{attachmentKey}/fulltext` | `{content, indexedPages, totalPages}` | **`content` 是扁平文本，没有页码边界** |
| `GET /fulltext?since=N` | `{attachmentKey: <int>}` | 增量快照；用于判断索引是否有更新 |
| `GET /items/{key}/children` | 子条目数组 | 附件 / 笔记 / 标注 |
| `GET /items/{attachmentKey}/file/view/url` | `Content-Type: text/plain` 的裸 `file://` URL | **不是 JSON**，用 JSON 解析会失败 |

**页码纪律（强制）：**

Zotero 全文索引只给 `content / indexedPages / totalPages`，**不提供页码边界**。
因此：

- 索引命中只能标注为 `indexed_fulltext`；
- **不得**据索引文本推测页码；
- **不得**把索引命中升级为 `page_verified`；
- 页码级引用必须来自真实 PDF 的逐页解析。

**检索命中必须归并：**

`GET /items?q=...&qmode=everything` 会**同时**返回附件与其父条目
（实测同一短语既命中 `attachment`，也命中其 `preprint` 父条目）。
必须按 `data.parentItem` 归并回论文并去重。

库中还存在**无父条目的孤立附件**（实测本机 68 个）。
归并逻辑必须显式处理，不得静默丢弃或重复计数。

**附件路径解析顺序：**

1. 先用 `file/view/url`（用户可能用第三方云盘，PDF **不一定**在 `~/Zotero/storage/`）；
2. 再回退 `storage/<attachmentKey>/<filename>`；
3. 只接受 `file://`，**不跟随 http(s)**，避免附件地址触发非预期网络请求。

## 4. 写入授权

Local API 支持 `POST`、`PATCH`、`PUT`、`DELETE`。
本流水线默认只读，写入仅在明确需要时发生（见 §8、§9）。

写入前申请授权：

`POST /api/local/authorize`

Headers：

- `Content-Type: application/json`
- `Zotero-Server-ID: {server_id}`

Body：

`{"appName":"Research Idea Pipeline"}`

Zotero 弹出授权窗口，三个按钮对应三种结果：

| 选择 | 结果 |
|---|---|
| `Allow` | 返回一次性 Key，首次成功写入后失效 |
| `Always Allow` | 返回可重复使用的 Key |
| `Deny` | `403`，正文 `{"denied": true}` |

响应体含 `key` 与 `remember` 字段。

后续写入请求必须携带：

- `Zotero-API-Key: {local_key}`
- `Zotero-Server-ID: {server_id}`
- `Zotero-API-Version: 3`

缺少 `Zotero-Server-ID` 的写请求返回 `428`。
Server ID 不匹配返回 `412`。

授权弹窗有频率限制，超限返回 `429` 并带 `Retry-After`。
不得反复弹出授权窗口。

不得把 Key 写入 Git、日志或普通配置文件。

## 5. 常用写入 API

以下路径以 `/api/users/0` 为前缀。

| 操作 | 方法与路径 |
|---|---|
| 创建论文 | `POST /items` |
| 修改论文元数据 | `PATCH /items/{key}` |
| 创建 Collection | `POST /collections` |
| 修改 Collection | `PATCH /collections/{key}` |
| 创建 Note | `POST /items` |
| 修改 Note | `PATCH /items/{key}` |
| 管理 Tags | 更新对应 Item 的 `tags` 字段 |
| 管理 Collection 归属 | 更新 Item 的 `collections` 字段 |

创建条目前先用 `GET /api/itemTypeFields?itemType=<type>` 取字段模板。
注意模板中的字段名是本地化的。

批量创建传 JSON 数组。
单次写入上限为 50 个对象。

可用 `Zotero-Write-Token`（5–32 字符）防止重复提交。

修改已有对象必须带并发条件，二者取一：

- 请求头 `If-Unmodified-Since-Version: {version}`
- 对象 JSON 中的 `version` 字段

更新前先读最新版本。
遇到 `412` 重新读取并检查冲突，**不得**直接覆盖。

> **`PATCH` 的合并是浅合并。**
> `tags`、`collections` 等数组字段会被整体替换。
> 提交时必须包含需要继续存在的**全部**成员。
> 这是本仓库最容易出错的写入点。

### 5.1 ⚠️ DELETE 是**永久抹除**，不是移入回收站

已核对 Zotero 10.0.3 源码 `server_localAPI.js`：
单对象删除与批量删除**都**调用 `obj.eraseTx()`（第 2335 行与第 2269 行）。

- `eraseTx()` 是**永久擦除**；`deleteTx()` 才是移入回收站。
- Local API 走的是前者。
- 因此**不得**假定删除可恢复，也**不得**假定它只是"放进垃圾箱"。

删除闸门（本项目强制，见 `zotero_crud.delete_paper`）：

1. `dry_run=False` —— 显式要求真实删除（默认 `True`）；
2. `confirm=True` —— 显式确认；
3. 客户端**确实可写**；
4. 未被 Research State 的 `LIT<n>` 引用（被引用则默认拒绝）。

另外：**永不批量删除**；删除前必须能给出准确的 Item Key；
只删除由测试自身创建的临时数据。

## 6. PDF 附件管理

查询某篇论文的附件：

`GET /api/users/0/items/{key}/children`

识别 `itemType=attachment`，检查 `linkMode` 与 `contentType`。

附件类型：

- `imported_file`：Zotero 存储的文件
- `imported_url`：由网页导入的存储附件
- `linked_file`：链接到本地文件
- `linked_url`：链接到网页

取本地文件 URL：

`GET /api/users/0/items/{attachmentKey}/file/view/url`

返回 `file://` 地址（已实测）。

仅对真实可访问的本地附件做 PDF 解析。

新增存储型 PDF 需先创建附件条目。
随后按 Zotero 官方三阶段 File Upload 协议上传。
`linked_file` **不得**使用该协议。

用户用第三方云盘管理附件时：

- 保留既有 Stored / Linked Attachment 关系。
- 不修改云盘配置。
- 不直接移动或删除 PDF。
- 不自行同步 Zotero 数据库。
- 不把元数据存储与 PDF 物理存储混为一谈。

## 7. 错误处理

| 状态 | 含义与处理 |
|---|---|
| `200` / `201` / `204` | 成功。批量写入仍需检查逐项结果 |
| `400` | 参数或请求格式错误 |
| `401` | 写入 Key 缺失或无效，必要时重新授权 |
| `403` | API 未启用、授权被拒或权限不足 |
| `404` | 资源不存在 |
| `409` | 资源冲突或文献库被锁定 |
| `412` | Server ID、版本或 Write Token 冲突 |
| `428` | 缺少必需的前置条件 |
| `429` | 请求过于频繁，遵守 `Retry-After` |
| `500` / `503` | 服务端错误，有限重试 |

`412` 不得盲目重试原写入请求。

Local API 一般无 Web API 式速率限制。
但授权弹窗受限，返回值见 §4。

## 8. 与 Research Idea Pipeline 的集成规则

后端优先级：

`Zotero Local API → 原有 docs/refs 后端`

初始化时：

1. 探测 Zotero 服务。
2. 验证文献库可读。
3. 判断是否拥有写入授权。
4. 按状态选择后端。

后端状态：

- `ZOTERO_RW`：可读写
- `ZOTERO_RO`：可读但未授权写入
- `REFS_FALLBACK`：服务不可访问

规则：

- `ZOTERO_RO` 不得静默回退到 refs 执行写入。
- 运行中 Zotero 断开，不自动切换写入目标。
- 下一次运行重新探测后端。
- Zotero 命中不代表可以跳过在线检索。
- Zotero 中存在条目不代表 PDF 已获取或全文已审阅。

当前实现只使用只读路径（`ZOTERO_RO` / `REFS_FALLBACK`）。
`ZOTERO_RW` 属预留能力，未在本流水线中启用。

文献身份建议包含：

- DOI（跨源主要标识）
- Zotero Item Key
- Library ID
- Server ID
- Research State 的文献引用 ID

**不得**把 Zotero Item Key 直接当作 Research State 的 `LIT<n>` ID。

命中 provenance 仍标 `sources=["local"]`。
源枚举 `local|arxiv|openalex|crossref` 不变（见 [literature-policy.md](literature-policy.md) §1.1）。

## 9. 安全规则

- 默认优先读取，写入只在明确需要时发生。
- 创建条目前按 DOI 去重。
- 不自动合并或删除重复文献。
- 不批量删除 Collections 或 Tags。
- 不覆盖用户人工笔记。
- 不直接修改 Zotero SQLite。
- 不将 Local API 端口暴露到公网。
- 大规模修改前先生成审计报告与备份。
- 对实际写入保留 Item Key、修改前后状态与结果日志。
- 未授权或不可用的功能必须明确报告，不得伪造成功。

## 10. 本仓库的实现入口

| 脚本 | 职责 | 默认语义 |
|---|---|---|
| `scripts/zotero_client.py` | 只读客户端：`probe` / `fetch_items` / `get_item` / `get_children` / `search_items` / `item_fulltext` / `file_view_url` / `local_attachment_path` / `item_to_record` / `item_to_sidecar` | 只读 |
| `scripts/zotero_write.py` | 写通道：`WriteClient`（授权、能力状态 `ZOTERO_RW/RO/REFS_FALLBACK`、受控 `post/patch/delete`、`Zotero-Write-Token`）；同时委托全部只读原语 | **不发写请求，除非显式授权** |
| `scripts/zotero_crud.py` | 文献 CRUD：`create_paper` / `update_paper` / `add_tags` / `remove_tags` / `add_to_collection` / `remove_from_collection` / `create_note` / `get_notes` / `delete_paper` | 写需显式调用；`delete_paper` 默认 dry-run |
| `scripts/zotero_fulltext.py` | 原生全文检索、附件解析、PDF 逐页抽取、文本缓存、`search_two_layer` | 只读 |
| `scripts/zotero_deepread.py` | `deep_read` / `compare_papers` / 证据锚点（六档 verification） | 只读 |
| `scripts/zotero_refs.py` | 把 Zotero 导出为 `docs/refs/` 格式 | 只读 + 本地写文件 |
| `scripts/literature_search.py` | `resolve_local_entries()`：Zotero 优先，失败回落 refs；`--zotero-fulltext` 启用第二层 | 只读 |

**写入纪律（本项目强制）：**

- 检索、全文、深读**全部只读**，且是四个语义入口的默认行为。
- 任何写入都必须由用户明确请求触发。
- 未授权时写方法抛 `ZoteroForbidden`，**不得**静默改到 refs 后端。
- `delete_paper` 默认 `dry_run=True`；真实删除需 `dry_run=False` + `confirm=True` + 客户端确实可写，
  且被 Research State 引用时默认拒绝。

自检命令：

```sh
python3 scripts/zotero_client.py --probe
python3 scripts/zotero_client.py --dump-records 3
python3 scripts/zotero_write.py                 # 能力状态（不授权、不写入）
python3 scripts/zotero_refs.py --check
python3 scripts/literature_search.py -q "..." --local-only --zotero-fulltext
```

## 11. 官方参考

- Local API：<https://www.zotero.org/support/dev/web_api/v3/local_api>
- API Basics：<https://www.zotero.org/support/dev/web_api/v3/basics>
- Write Requests：<https://www.zotero.org/support/dev/web_api/v3/write_requests>
- File Uploads：<https://www.zotero.org/support/dev/web_api/v3/file_upload>

涉及授权、写入冲突、附件或版本兼容时，以官方文档为最终依据。
