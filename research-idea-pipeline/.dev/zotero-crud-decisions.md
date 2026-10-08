# zotero_crud 实现决策（branch-local）

分支：`feat/zotero-library-ops-fulltext`；模块：`scripts/zotero_crud.py`。

## 1. Local API 写语义（源码核实）

对照 `Zotero_linux-x86_64/app/omni.ja` 内的
`chrome/content/zotero/xpcom/server/server_localAPI.js` 逐行核实，纠正了
Web API 的若干直觉：

| 事实 | 依据 | 影响 |
|---|---|---|
| 写请求体是**条目数据字段本身**，**不带 `{"data": ...}` 包装** | `writeSingleObject` 用 `obj.toJSON()` 做顶层 `mergePatchJSON`，再 `obj.fromJSON(json)`；`writeMultipleObjects` 读 `entry.itemType` | payload 必须扁平 |
| `PATCH` 是**顶层浅合并，数组整体替换** | `mergePatchJSON()` 逐键覆盖 | `tags` / `collections` 必须提交完整并集 |
| 单对象 `DELETE` 调用 **`obj.eraseTx()`** | `deleteSingleObject()` | **永久抹除，不是回收站**；不可逆 |
| `DELETE` / 单对象 `PATCH` 缺版本条件 → `428` | `If-Unmodified-Since-Version` 检查 | 必须先 GET 再写 |
| `POST` 响应：`successful[idx]` = 完整 `{key, version, data}`；`unchanged` / `failed` 另列 | `MultiWriteResults` | 创建后可用响应 + 回读双重核对 |
| 单批上限 50；批量删除上限 50，且会直接 `eraseTx()` | `MAX_WRITE_OBJECTS` / `MAX_DELETE_OBJECTS` | 本模块**只用单对象写**，永不批量删除 |

`zotero_write.WriteClient.patch/delete` 把 payload 原样作为 JSON 体发送，故 payload
形状由本模块决定 —— 这是「扁平而非 data 包装」能生效的前提。

## 2. 关键设计决定

1. **读面 duck-typing。** `WriteClient` 没有读方法，本模块的读适配优先调用
   client 上的 `get_item` / `get_children` / `fetch_items`，缺失时才回落
   `zotero_client`（按 `client.base_url`）。测试用内存假客户端补齐读面即可完全离线。
2. **版本安全。** 所有更新 / 删除都先 GET 取 `version`，经
   `client.patch(..., version=)` / `client.delete(..., version=)` 走
   `If-Unmodified-Since-Version`；`412` → 重新读取并报告，绝不覆盖。
3. **`tags` / `collections` 并集。** `update_paper` 与 add/remove 系列都提交完整结果
   数组；`remove_tags` 只改条目上的关联，从不触碰 `/tags` 端点（不删全局 tag 定义）。
4. **POST 不重试。** `WriteClient` 不暴露 `Zotero-Write-Token`，盲目重试可能制造重复
   条目。POST 失败后改为**重新去重核对**：若发现新增命中则报告 `recovered_after_failure`，
   否则明确报告「未确认」。重试只用于幂等的 PATCH / DELETE。
5. **删除失败即拒绝。** Research State 形状不可信（`literature` / `claims` 等字段
   类型异常）时记 `scan_error` 并**失败即拒绝**，因为无法证明「没有引用」。
   `state=None` 时才明确报告「未检查」。
6. **笔记只新增。** 代理笔记带专用 tag `agent-note` 与正文标记 `[agent-note]`；
   `update_paper` 对 note 条目的正文写入一律拒绝（`reason="user-note-protected"`）。

## 3. 删除闸门

`dry_run=True`（默认）→ 预览影响报告（附件 / 笔记 / 标注 / 集合 / `LIT<n>` 引用）。

真实删除需**同时**满足：`dry_run=False` + `confirm=True` + 客户端确实可写
（`capability().writable` 或 `has_key`）；被 `LIT<n>` 引用时额外需要 `force=True`。
任一不满足即返回 `deleted=False, refused=True` 并说明原因，且不发起写请求。

## 4. 后续（不属本模块）

- 若要在真实库验证，建议先 `--probe`，再对**测试用条目**跑 dry-run 影响报告。
- `literature_search.py` 接线（Lead 负责）可在 `ZOTERO_RW` 下选用本模块的
  `create_paper` / `add_tags`；写前应先 `find_by_identifiers`。
