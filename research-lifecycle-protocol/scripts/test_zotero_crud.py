#!/usr/bin/env python3
"""`zotero_crud` 离线回归测试（不联网、不依赖运行中的 Zotero）。

覆盖任务书 §9.1 的全部条目：

1. 首次授权 / 一次性 Key 失效 / 持久 Key / 授权被拒 / Server ID 变化
   （在真实 `WriteClient` 上以 mock 传输验证）。
2. DOI 去重创建（精确重复 + 预印本 vs 已发表版本）。
3. 创建后回读核对。
4. PATCH 保留未修改字段。
5. tags / collections 并集（浅合并下数组整体替换）。
6. 版本冲突（412）不盲目覆盖。
7. 写超时重试（仅幂等操作）与 POST 不重试。
8. 删除 dry-run、未授权拒绝、Research State `LIT<n>` 引用阻断。

所有 Zotero 交互由内存假客户端承担；`WriteClient` 的授权测试用
`unittest.mock` 替换 `urlopen` 与 `zotero_client.probe`，绝不触网。
"""
from __future__ import annotations

import copy
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import zotero_client as zc  # noqa: E402
import zotero_crud as crud  # noqa: E402
import zotero_write as zw  # noqa: E402

BASE_URL = "http://127.0.0.1:23119/api"


# ---------------------------------------------------------------------------
# 测试替身
# ---------------------------------------------------------------------------

class FakeClient:
    """内存假客户端：实现 `WriteClient` 的写面 + `zotero_client` 的读面。

    这样 `zotero_crud` 的 duck-typed 读适配（`get_item` / `get_children` /
    `fetch_items`）与写调用（`patch` / `post` / `delete` / `capability`）都不触网。
    """

    def __init__(self, *, key: str = "fake-key", server_id: str = "SRV-1",
                 items: list | None = None) -> None:
        self.user = zc.DEFAULT_USER
        self.base_url = BASE_URL
        self._key = key
        self._server_id = server_id
        self._items: dict = {}
        self._counter = 0
        self.calls: list = []
        self.fail_next: dict = {}
        self.hide_reads_after_post = False
        for item in items or []:
            self._items[item["key"]] = copy.deepcopy(item)

    # ---------------------------------------------------------------- 写面
    @property
    def has_key(self) -> bool:
        return bool(self._key)

    @property
    def server_id(self):
        return self._server_id

    def invalidate(self) -> None:
        self._key = None
        self._server_id = None

    def status(self) -> str:
        return zw.STATUS_RW if self._key else zw.STATUS_RO

    def capability(self) -> dict:
        status = self.status()
        return {"status": status, "writable": status == zw.STATUS_RW,
                "has_key": self.has_key, "server_id": self._server_id,
                "reason": "已授权，可读写" if self.has_key else "可读，未授权写入"}

    def _maybe_fail(self, method: str) -> None:
        pending = self.fail_next.get(method)
        if pending:
            raise pending.pop(0)

    def _next_key(self) -> str:
        self._counter += 1
        return f"NEWKEY{self._counter}"

    def _version_of(self, item: dict) -> int:
        return int(item.get("version") or 0)

    def patch(self, kind: str, key: str, payload: dict, *, version=None):
        self.calls.append({"method": "patch", "kind": kind, "key": key,
                           "payload": copy.deepcopy(payload), "version": version})
        self._maybe_fail("patch")
        item = self._items.get(key)
        if item is None:
            raise zw.ZoteroWriteError("404 not found")
        if version is not None and self._version_of(item) != int(version):
            raise zw.ZoteroConflict(
                f"version mismatch: expected {version}, found {self._version_of(item)}")
        merged = dict(item["data"])
        merged.update(payload)  # 浅合并：调用方必须给完整数组
        item["data"] = merged
        item["version"] = self._version_of(item) + 1
        return 204, None

    def post(self, kind: str, payloads: list):
        self.calls.append({"method": "post", "kind": kind,
                           "payloads": copy.deepcopy(payloads)})
        self._maybe_fail("post")
        successful = {}
        for index, payload in enumerate(payloads):
            key = self._next_key()
            obj = {"key": key, "version": 1, "data": copy.deepcopy(payload)}
            self._items[key] = obj
            if self.hide_reads_after_post:
                self.hidden = getattr(self, "hidden", set()) | {key}
            successful[str(index)] = copy.deepcopy(obj)
        return {"successful": successful, "failed": {}, "statuses": [200]}

    def delete(self, kind: str, key: str, *, version=None):
        self.calls.append({"method": "delete", "kind": kind, "key": key,
                           "version": version})
        self._maybe_fail("delete")
        item = self._items.get(key)
        if item is None:
            raise zw.ZoteroWriteError("404 not found")
        if version is not None and self._version_of(item) != int(version):
            raise zw.ZoteroConflict(
                f"version mismatch: expected {version}, found {self._version_of(item)}")
        del self._items[key]
        return 204, None

    # ---------------------------------------------------------------- 读面
    def get_item(self, key: str):
        if key in getattr(self, "hidden", set()):
            return None
        item = self._items.get(key)
        return copy.deepcopy(item) if item is not None else None

    def get_children(self, key: str):
        return [copy.deepcopy(i) for i in self._items.values()
                if (i.get("data") or {}).get("parentItem") == key]

    def fetch_items(self):
        return [copy.deepcopy(i) for i in self._items.values()]

    # ------------------------------------------------------------- 辅助断言
    def write_calls(self) -> list:
        return [c for c in self.calls if c["method"] in ("patch", "post", "delete")]

    def patch_calls(self) -> list:
        return [c for c in self.calls if c["method"] == "patch"]


def item(key: str, *, version: int = 1, **data):
    payload = {"itemType": "journalArticle", "title": f"Title {key}"}
    payload.update(data)
    return {"key": key, "version": version, "data": payload}


class _FakeResponse:
    """`urlopen` 的最小替身。"""

    def __init__(self, payload, *, status: int = 200, headers=None) -> None:
        self._payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.status = status
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeHTTPError(urllib.error.HTTPError):
    """带可读正文、且已关闭的 HTTPError 替身。

    `urllib.error.HTTPError` 在 CPython 3.14 上混入 `tempfile._TemporaryFileWrapper`，
    未关闭时会在析构阶段抛 `ResourceWarning`。这里先 `close()` 避免测试输出噪声。
    """

    def __init__(self, code: int, text: str) -> None:
        super().__init__("http://127.0.0.1:23119/api", code, "err", {}, None)
        self._body = text.encode("utf-8")
        self.close()

    def read(self, *_args, **_kwargs) -> bytes:
        return self._body


def _http_error(code: int, text: str) -> urllib.error.HTTPError:
    return _FakeHTTPError(code, text)


def _raise(exc):
    def raiser(*_args, **_kwargs):
        raise exc
    return raiser


# ---------------------------------------------------------------------------
# §9.1 授权相关（真实 WriteClient + mock 传输）
# ---------------------------------------------------------------------------

class AuthorizationTests(unittest.TestCase):
    """写授权：首次 / 一次性 Key 失效 / 持久 Key / 被拒 / Server ID 变化。"""

    def test_first_authorization_returns_one_shot_key(self) -> None:
        client = zw.WriteClient(BASE_URL)
        with mock.patch.object(zc, "probe", return_value="SRV-1"), \
             mock.patch.object(zw.urllib.request, "urlopen",
                               return_value=_FakeResponse({"key": "k1", "remember": False})):
            result = client.authorize()
        self.assertEqual(result, {"key": "k1", "remember": False})
        self.assertTrue(client.has_key)

    def test_one_shot_key_expires_after_successful_write(self) -> None:
        """一次性 Key 在 401 后必须清空，不得继续当作有效凭据。"""

        def fake_urlopen(request, timeout=None):
            if request.full_url.endswith("/local/authorize"):
                return _FakeResponse({"key": "one-shot", "remember": False})
            raise _http_error(401, '{"error":"key expired"}')

        client = zw.WriteClient(BASE_URL)
        with mock.patch.object(zc, "probe", return_value="SRV-1"), \
             mock.patch.object(zw.urllib.request, "urlopen", side_effect=fake_urlopen):
            client.authorize()
            self.assertTrue(client.has_key)
            with self.assertRaises(zw.ZoteroAuthRequired):
                client.request("PATCH", "items/ABCD1234", body={"title": "x"})
        self.assertFalse(client.has_key)

    def test_persistent_key_survives_write(self) -> None:
        def fake_urlopen(request, timeout=None):
            if request.full_url.endswith("/local/authorize"):
                return _FakeResponse({"key": "persist", "remember": True})
            return _FakeResponse("", status=204)

        client = zw.WriteClient(BASE_URL)
        with mock.patch.object(zc, "probe", return_value="SRV-1"), \
             mock.patch.object(zw.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = client.authorize()
            self.assertTrue(result["remember"])
            status, _payload = client.request("PATCH", "items/ABCD1234", body={"title": "x"})
        self.assertEqual(status, 204)
        self.assertTrue(client.has_key)

    def test_denied_authorization_raises(self) -> None:
        client = zw.WriteClient(BASE_URL)
        with mock.patch.object(zc, "probe", return_value="SRV-1"), \
             mock.patch.object(zw.urllib.request, "urlopen",
                               side_effect=_raise(_http_error(403, '{"denied":true}'))):
            with self.assertRaises(zw.ZoteroAuthDenied):
                client.authorize()
        self.assertFalse(client.has_key)

    def test_server_id_change_invalidates_key(self) -> None:
        client = zw.WriteClient(BASE_URL, key="k1")
        with mock.patch.object(zc, "probe", return_value="SRV-1"):
            self.assertEqual(client.ensure_server_id(), "SRV-1")
        self.assertTrue(client.has_key)

        with mock.patch.object(zc, "probe", return_value="SRV-2"):
            self.assertEqual(client.ensure_server_id(), "SRV-2")
        self.assertFalse(client.has_key, "Server ID 变化后必须清空旧 Key")
        self.assertEqual(client.server_id, "SRV-2")

    def test_real_writeclient_without_key_raises_forbidden(self) -> None:
        """未授权客户端调写方法必须抛 ZoteroForbidden（不发网络请求）。"""
        client = zw.WriteClient(BASE_URL)
        with self.assertRaises(zw.ZoteroForbidden):
            client.delete("item", "ABCD1234")


# ---------------------------------------------------------------------------
# §9.1 检索与去重
# ---------------------------------------------------------------------------

class FindByIdentifiersTests(unittest.TestCase):
    """DOI → arXiv → 标题+年份 的命中优先级。"""

    def setUp(self) -> None:
        self.client = FakeClient(items=[
            item("P1", DOI="10.1000/ABC.1", title="First Paper", date="2024"),
            item("P2", itemType="preprint", title="Preprint Paper",
                 archiveID="2401.01234", libraryCatalog="arXiv.org", date="2024"),
        ])

    def test_match_by_normalized_doi(self) -> None:
        found = crud.find_by_identifiers(self.client, doi="https://doi.org/10.1000/abc.1")
        self.assertEqual([r["item_key"] for r in found], ["P1"])
        self.assertIn("doi", found[0]["matched_on"])

    def test_match_by_arxiv_and_title(self) -> None:
        by_arxiv = crud.find_by_identifiers(self.client, arxiv_id="arXiv:2401.01234v2")
        self.assertEqual([r["item_key"] for r in by_arxiv], ["P2"])
        by_title = crud.find_by_identifiers(self.client, title="first  paper!", year=2024)
        self.assertEqual([r["item_key"] for r in by_title], ["P1"])

    def test_no_match_returns_empty(self) -> None:
        self.assertEqual(crud.find_by_identifiers(self.client, doi="10.9999/nope"), [])

    def test_doi_match_ranks_before_title_match(self) -> None:
        client = FakeClient(items=[
            item("TITLEONLY", title="Shared Title", date="2024"),
            item("DOIITEM", title="Other", DOI="10.1000/prio"),
        ])
        found = crud.find_by_identifiers(client, doi="10.1000/prio",
                                         title="Shared Title", year=2024)
        self.assertEqual(found[0]["item_key"], "DOIITEM")

    def test_unreadable_library_returns_empty(self) -> None:
        broken = FakeClient()
        broken.fetch_items = lambda: (_ for _ in ()).throw(zc.ZoteroUnavailable("down"))
        self.assertEqual(crud.find_by_identifiers(broken, doi="10.1000/x"), [])


# ---------------------------------------------------------------------------
# §9.1 创建 + 去重（精确 / 不同版本）
# ---------------------------------------------------------------------------

class CreatePaperTests(unittest.TestCase):
    """create_paper：DOI 去重、版本关系、dry-run、创建后核对。"""

    def test_duplicate_doi_refuses_creation(self) -> None:
        client = FakeClient(items=[item("OLD1", DOI="10.1000/ABC.1", title="Known")])
        result = crud.create_paper(client, {"title": "Known", "doi": "10.1000/abc.1"})
        self.assertFalse(result["created"])
        self.assertEqual(result["duplicate_of"], "OLD1")
        self.assertEqual(result["version_relation"], crud.VERSION_EXACT)
        self.assertEqual(client.write_calls(), [], "命中重复时不得发起任何写请求")

    def test_preprint_vs_journal_is_not_exact_duplicate(self) -> None:
        client = FakeClient(items=[item(
            "PRE1", itemType="preprint", title="Deep Thing",
            DOI="10.48550/arxiv.2401.01234", archiveID="2401.01234",
            libraryCatalog="arXiv.org", date="2024")])
        result = crud.create_paper(client, {
            "title": "Deep Thing", "doi": "10.1000/journal.42",
            "arxiv_id": "2401.01234", "venue": "Nature", "date": "2024"})
        self.assertFalse(result["created"])
        self.assertEqual(result["version_relation"], crud.VERSION_NEW_IS_PUBLISHED)
        self.assertNotEqual(result["version_relation"], crud.VERSION_EXACT)
        self.assertTrue(result["needs_review"])
        self.assertEqual(client.write_calls(), [])

    def test_allow_related_version_creates_new_record(self) -> None:
        client = FakeClient(items=[item(
            "PRE1", itemType="preprint", title="Deep Thing",
            archiveID="2401.01234", libraryCatalog="arXiv.org", date="2024")])
        result = crud.create_paper(
            client,
            {"title": "Deep Thing", "arxiv_id": "2401.01234",
             "itemType": "journalArticle", "venue": "Nature", "doi": "10.1000/journal.42"},
            allow_related_version=True)
        self.assertTrue(result["created"])
        self.assertEqual(result["related_to"], "PRE1")
        self.assertEqual(len(client.calls), 1)

    def test_same_arxiv_id_is_exact_duplicate(self) -> None:
        client = FakeClient(items=[item(
            "PRE1", itemType="preprint", title="Deep Thing",
            archiveID="2401.01234", libraryCatalog="arXiv.org")])
        result = crud.create_paper(client, {"title": "Deep Thing",
                                            "arxiv_id": "2401.01234"})
        self.assertFalse(result["created"])
        self.assertEqual(result["version_relation"], crud.VERSION_EXACT)

    def test_dry_run_does_not_write(self) -> None:
        client = FakeClient()
        result = crud.create_paper(client, {"title": "New", "doi": "10.1000/new"},
                                   dry_run=True)
        self.assertFalse(result["created"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["payload"]["itemType"], "journalArticle")
        self.assertEqual(client.write_calls(), [])

    def test_create_then_verify_by_re_read(self) -> None:
        client = FakeClient()
        result = crud.create_paper(client, {
            "title": "Brand New", "authors": ["Ada Smith", "Bob Lee"],
            "year": 2025, "doi": "https://doi.org/10.1000/brand.new",
            "venue": "Journal of Tests", "arxiv_id": "2501.00001"})
        self.assertTrue(result["created"])
        self.assertTrue(result["verified"])
        self.assertTrue(result["verification"]["ok"])
        self.assertTrue(result["item_key"])
        self.assertEqual(result["record"]["title"], "Brand New")
        self.assertEqual(result["record"]["authors"], ["Ada Smith", "Bob Lee"])
        self.assertEqual(result["record"]["doi"], "10.1000/brand.new")
        self.assertEqual(result["record"]["year"], 2025)

    def test_create_reports_failed_verification(self) -> None:
        client = FakeClient()
        client.hide_reads_after_post = True
        result = crud.create_paper(client, {"title": "Ghost", "doi": "10.1000/ghost"})
        self.assertTrue(result["created"])
        self.assertFalse(result["verified"])
        self.assertFalse(result["verification"]["ok"])

    def test_post_timeout_is_not_retried(self) -> None:
        """POST 无幂等键：不得盲目重试，失败后重新去重核对。"""
        client = FakeClient()
        client.fail_next["post"] = [zw.ZoteroWriteError("timeout")]
        result = crud.create_paper(client, {"title": "Timeout", "doi": "10.1000/timeout"})
        self.assertFalse(result["created"])
        self.assertEqual(len([c for c in client.calls if c["method"] == "post"]), 1)
        self.assertIn("未确认", result["error"])

    def test_post_failure_recovers_if_item_actually_landed(self) -> None:
        client = FakeClient()

        def post_then_raise(kind, payloads):
            client.calls.append({"method": "post", "kind": kind,
                                 "payloads": copy.deepcopy(payloads)})
            key = "LANDED1"
            client._items[key] = {"key": key, "version": 1,
                                  "data": copy.deepcopy(payloads[0])}
            raise zw.ZoteroWriteError("timeout after write")

        client.post = post_then_raise
        result = crud.create_paper(client, {"title": "Landed", "doi": "10.1000/landed"})
        self.assertTrue(result["created"])
        self.assertTrue(result.get("recovered_after_failure"))
        self.assertEqual(result["item_key"], "LANDED1")

    def test_failed_result_map_is_reported(self) -> None:
        client = FakeClient()
        client.post = lambda kind, payloads: {"successful": {},
                                              "failed": {"0": {"code": 400,
                                                               "message": "bad field"}}}
        result = crud.create_paper(client, {"title": "Bad", "doi": "10.1000/bad"})
        self.assertFalse(result["created"])
        self.assertIn("error", result)


# ---------------------------------------------------------------------------
# §9.1 更新：保留字段 / 并集 / 412 / 重试
# ---------------------------------------------------------------------------

class UpdatePaperTests(unittest.TestCase):
    """update_paper：浅合并下的字段保留、并集、版本安全与重试。"""

    def _client(self) -> FakeClient:
        return FakeClient(items=[item(
            "AAAA1111", version=7, title="Old Title", abstractNote="keep me",
            DOI="10.1000/keep", extra="custom", tags=[{"tag": "alpha"}],
            collections=["COLL1"], date="2020")])

    def test_patch_preserves_unmodified_fields(self) -> None:
        client = self._client()
        result = crud.update_paper(client, "AAAA1111", {"title": "New Title"})
        self.assertTrue(result["updated"])
        self.assertEqual(result["changed_fields"], ["title"])
        payload = client.patch_calls()[-1]["payload"]
        self.assertEqual(payload, {"title": "New Title"},
                         "只提交调用方点名的字段")
        stored = client._items["AAAA1111"]["data"]
        self.assertEqual(stored["abstractNote"], "keep me")
        self.assertEqual(stored["extra"], "custom")
        self.assertEqual(stored["tags"], [{"tag": "alpha"}])
        self.assertEqual(stored["collections"], ["COLL1"])
        self.assertEqual(stored["DOI"], "10.1000/keep")

    def test_patch_sends_fresh_version(self) -> None:
        client = self._client()
        crud.update_paper(client, "AAAA1111", {"title": "X"})
        self.assertEqual(client.patch_calls()[-1]["version"], 7)

    def test_tags_are_union_not_replacement(self) -> None:
        client = self._client()
        result = crud.update_paper(client, "AAAA1111", {"tags": ["beta", "alpha"]})
        self.assertTrue(result["updated"])
        self.assertEqual(client._items["AAAA1111"]["data"]["tags"],
                         [{"tag": "alpha"}, {"tag": "beta"}])

    def test_collections_are_union_not_replacement(self) -> None:
        client = self._client()
        crud.update_paper(client, "AAAA1111", {"collections": ["COLL2", "COLL1"]})
        self.assertEqual(client._items["AAAA1111"]["data"]["collections"],
                         ["COLL1", "COLL2"])

    def test_no_op_patch_does_not_write(self) -> None:
        client = self._client()
        result = crud.update_paper(client, "AAAA1111", {"title": "Old Title"})
        self.assertFalse(result["updated"])
        self.assertTrue(result["no_op"])
        self.assertEqual(client.write_calls(), [])

    def test_version_conflict_412_does_not_overwrite(self) -> None:
        client = self._client()
        client.fail_next["patch"] = [zw.ZoteroConflict("version mismatch")]
        result = crud.update_paper(client, "AAAA1111", {"title": "Racing"})
        self.assertFalse(result["updated"])
        self.assertTrue(result["conflict"])
        self.assertEqual(len(client.patch_calls()), 1, "412 不得盲目重试/覆盖")
        self.assertEqual(client._items["AAAA1111"]["data"]["title"], "Old Title")

    def test_timeout_is_retried_for_idempotent_patch(self) -> None:
        client = self._client()
        client.fail_next["patch"] = [zw.ZoteroWriteError("timeout")]
        with mock.patch.object(crud, "_sleep", lambda _seconds: None):
            result = crud.update_paper(client, "AAAA1111", {"title": "Retried"})
        self.assertTrue(result["updated"])
        self.assertEqual(len(client.patch_calls()), 2)
        self.assertEqual(client._items["AAAA1111"]["data"]["title"], "Retried")

    def test_conflict_is_not_retried(self) -> None:
        client = self._client()
        client.fail_next["patch"] = [zw.ZoteroConflict("boom")]
        with mock.patch.object(crud, "_sleep", lambda _seconds: None):
            crud.update_paper(client, "AAAA1111", {"title": "Nope"})
        self.assertEqual(len(client.patch_calls()), 1)

    def test_missing_item_is_reported(self) -> None:
        client = FakeClient()
        result = crud.update_paper(client, "MISSING", {"title": "x"})
        self.assertFalse(result["updated"])
        self.assertIn("error", result)

    def test_user_note_body_is_protected(self) -> None:
        client = FakeClient(items=[{
            "key": "NOTE0001", "version": 2,
            "data": {"itemType": "note", "parentItem": "AAAA1111",
                     "note": "<p>user wrote this</p>"}}])
        result = crud.update_paper(client, "NOTE0001", {"note": "<p>overwrite</p>"})
        self.assertFalse(result["updated"])
        self.assertTrue(result["refused"])
        self.assertEqual(result["reason"], "user-note-protected")
        self.assertEqual(client.write_calls(), [])

    def test_dry_run_does_not_write(self) -> None:
        client = self._client()
        result = crud.update_paper(client, "AAAA1111", {"title": "Planned"}, dry_run=True)
        self.assertFalse(result["updated"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(client.write_calls(), [])


# ---------------------------------------------------------------------------
# §9.1 标签 / 集合
# ---------------------------------------------------------------------------

class TagCollectionTests(unittest.TestCase):
    """add_tags / remove_tags / add_to_collection / remove_from_collection。"""

    def _client(self) -> FakeClient:
        return FakeClient(items=[item(
            "BBBB2222", version=3, tags=[{"tag": "alpha"}, {"tag": "beta"}],
            collections=["COLL1"])])

    def test_add_tags_union(self) -> None:
        client = self._client()
        result = crud.add_tags(client, "BBBB2222", ["beta", "gamma"])
        self.assertTrue(result["updated"])
        self.assertEqual(result["tags"], ["alpha", "beta", "gamma"])
        self.assertEqual(client.patch_calls()[-1]["payload"]["tags"],
                         [{"tag": "alpha"}, {"tag": "beta"}, {"tag": "gamma"}])

    def test_remove_tags_only_removes_association(self) -> None:
        client = self._client()
        result = crud.remove_tags(client, "BBBB2222", ["alpha"])
        self.assertTrue(result["updated"])
        self.assertEqual(result["tags"], ["beta"])
        self.assertTrue(result["tag_definitions_untouched"])
        # 只 PATCH 条目本身，绝不触碰 /tags 端点。
        self.assertTrue(all(c["method"] in ("patch", "post", "delete")
                            for c in client.calls))
        self.assertEqual([c["method"] for c in client.calls], ["patch"])

    def test_remove_tags_no_op_when_absent(self) -> None:
        client = self._client()
        result = crud.remove_tags(client, "BBBB2222", ["not-there"])
        self.assertFalse(result["updated"])
        self.assertTrue(result["no_op"])
        self.assertEqual(client.write_calls(), [])

    def test_add_and_remove_collection_union_semantics(self) -> None:
        client = self._client()
        added = crud.add_to_collection(client, "BBBB2222", "COLL2")
        self.assertTrue(added["updated"])
        self.assertEqual(client._items["BBBB2222"]["data"]["collections"],
                         ["COLL1", "COLL2"])
        removed = crud.remove_from_collection(client, "BBBB2222", "COLL1")
        self.assertTrue(removed["updated"])
        self.assertEqual(client._items["BBBB2222"]["data"]["collections"], ["COLL2"])

    def test_tag_conflict_reported(self) -> None:
        client = self._client()
        client.fail_next["patch"] = [zw.ZoteroConflict("stale")]
        result = crud.add_tags(client, "BBBB2222", ["gamma"])
        self.assertFalse(result["updated"])
        self.assertTrue(result["conflict"])


# ---------------------------------------------------------------------------
# §9.1 笔记：只新增，不改写
# ---------------------------------------------------------------------------

class NoteTests(unittest.TestCase):
    """create_note 追加新笔记；既有用户笔记保持原样。"""

    def test_create_note_is_marked_and_tagged(self) -> None:
        client = FakeClient(items=[item("CCCC3333", version=1)])
        result = crud.create_note(client, "CCCC3333", "Agent summary", tags=["reviewed"])
        self.assertTrue(result["created"])
        self.assertTrue(result["note_key"])
        self.assertIn(crud.AGENT_NOTE_MARKER, result["note"])
        self.assertIn(crud.AGENT_NOTE_TAG, result["tags"])
        self.assertIn("reviewed", result["tags"])
        post = [c for c in client.calls if c["method"] == "post"][-1]
        self.assertEqual(post["payloads"][0]["itemType"], "note")
        self.assertEqual(post["payloads"][0]["parentItem"], "CCCC3333")

    def test_create_note_never_edits_existing_note(self) -> None:
        client = FakeClient(items=[
            item("CCCC3333", version=1),
            {"key": "USERNOTE", "version": 5,
             "data": {"itemType": "note", "parentItem": "CCCC3333",
                      "note": "<p>human text</p>"}},
        ])
        crud.create_note(client, "CCCC3333", "second note")
        self.assertNotIn("NOTE", [c["method"] for c in client.calls])
        self.assertEqual(client._items["USERNOTE"]["data"]["note"], "<p>human text</p>")
        self.assertTrue(all(c["method"] == "post" for c in client.calls))

    def test_get_notes_classifies_agent_notes(self) -> None:
        client = FakeClient()
        crud.create_note(client, "PARENT", "agent text")
        client._items["USERNOTE"] = {
            "key": "USERNOTE", "version": 1,
            "data": {"itemType": "note", "parentItem": "PARENT",
                     "note": "<p>human</p>"}}
        notes = crud.get_notes(client, "PARENT")
        self.assertEqual(len(notes), 2)
        flags = {n["note_key"]: n["is_agent_note"] for n in notes}
        self.assertTrue(any(flags.values()))
        self.assertFalse(flags["USERNOTE"])

    def test_create_note_rejects_empty_body(self) -> None:
        client = FakeClient()
        result = crud.create_note(client, "PARENT", "   ")
        self.assertFalse(result["created"])
        self.assertEqual(client.write_calls(), [])


# ---------------------------------------------------------------------------
# §9.1 安全删除
# ---------------------------------------------------------------------------

class DeletePaperTests(unittest.TestCase):
    """delete_paper：dry-run、三重凭据、LIT 引用阻断、永不批量。"""

    def _client(self, **kwargs) -> FakeClient:
        parent = item("DDDD4444", version=9, title="Doomed Paper",
                      DOI="10.1000/doomed", tags=[{"tag": "x"}])
        children = [
            {"key": "ATTACH01", "version": 1,
             "data": {"itemType": "attachment", "parentItem": "DDDD4444",
                      "contentType": "application/pdf", "filename": "paper.pdf"}},
            {"key": "NOTEX", "version": 1,
             "data": {"itemType": "note", "parentItem": "DDDD4444",
                      "note": "<p>human note</p>"}},
            {"key": "ANNOT01", "version": 1,
             "data": {"itemType": "annotation", "parentItem": "DDDD4444"}},
        ]
        return FakeClient(items=[parent, *children], **kwargs)

    def test_dry_run_is_default_and_lists_impact(self) -> None:
        client = self._client()
        result = crud.delete_paper(client, "DDDD4444")
        self.assertFalse(result["deleted"])
        self.assertTrue(result["dry_run"])
        impact = result["impact"]
        self.assertEqual(impact["counts"]["attachments"], 1)
        self.assertEqual(impact["counts"]["notes"], 1)
        self.assertEqual(impact["counts"]["annotations"], 1)
        self.assertTrue(impact["irreversible"])
        self.assertEqual(client.write_calls(), [], "dry-run 不得发起删除")

    def test_real_delete_requires_confirm(self) -> None:
        client = self._client()
        result = crud.delete_paper(client, "DDDD4444", dry_run=False, confirm=False)
        self.assertFalse(result["deleted"])
        self.assertTrue(result["refused"])
        self.assertEqual(result["reason"], "needs-confirm")
        self.assertEqual(client.write_calls(), [])

    def test_unauthorized_delete_is_refused(self) -> None:
        client = self._client(key=None)
        result = crud.delete_paper(client, "DDDD4444", dry_run=False, confirm=True)
        self.assertFalse(result["deleted"])
        self.assertTrue(result["refused"])
        self.assertEqual(result["reason"], "not-writable")
        self.assertEqual(client.write_calls(), [])
        self.assertIn("DDDD4444", client._items)

    def test_existing_lit_reference_blocks_delete(self) -> None:
        client = self._client()
        state = {
            "literature": [
                {"id": "LIT1", "ref": "[Smith, 2024]", "relation": "supports",
                 "zotero_item_key": "DDDD4444"},
            ],
            "evidence": [{"id": "E1", "kind": "literature", "source_ref": "LIT1"}],
            "claims": [{"id": "C1", "supporting_evidence": ["E1"], "ref": "LIT1"}],
        }
        result = crud.delete_paper(client, "DDDD4444", dry_run=False, confirm=True,
                                   state=state)
        self.assertFalse(result["deleted"])
        self.assertTrue(result["refused"])
        self.assertEqual(result["reason"], "research-state-reference")
        scan = result["impact"]["research_state"]
        self.assertEqual(scan["referenced_lit_ids"], ["LIT1"])
        # 1 条 literature 命中 + E1 与 C1 两处下游引用。
        self.assertEqual(scan["total_references"], 3)
        self.assertEqual(client.write_calls(), [])
        self.assertIn("DDDD4444", client._items)

    def test_reference_by_doi_in_state_blocks_delete(self) -> None:
        client = self._client()
        state = {"literature": [{"id": "LIT7", "ref": "[Doe, 2023]",
                                 "doi": "https://doi.org/10.1000/DOOMED"}]}
        result = crud.delete_paper(client, "DDDD4444", dry_run=False, confirm=True,
                                   state=state)
        self.assertTrue(result["refused"])
        self.assertEqual(result["impact"]["research_state"]["referenced_lit_ids"], ["LIT7"])

    def test_force_overrides_state_reference(self) -> None:
        client = self._client()
        state = {"literature": [{"id": "LIT1", "zotero_item_key": "DDDD4444"}]}
        result = crud.delete_paper(client, "DDDD4444", dry_run=False, confirm=True,
                                   state=state, force=True)
        self.assertTrue(result["deleted"])
        self.assertTrue(result["verified"])
        self.assertNotIn("DDDD4444", client._items)

    def test_malformed_state_never_crashes_and_blocks(self) -> None:
        client = self._client()
        for bad in (123, "nonsense", {"literature": "not-a-list"},
                    {"literature": [None, 7, {"id": None}],
                     "claims": {"weird": True}}):
            with self.subTest(state=bad):
                result = crud.delete_paper(client, "DDDD4444", dry_run=False,
                                           confirm=True, state=bad)
                self.assertFalse(result["deleted"])
                self.assertTrue(result["refused"])

    def test_successful_delete_is_single_and_verified(self) -> None:
        client = self._client()
        result = crud.delete_paper(client, "DDDD4444", dry_run=False, confirm=True)
        self.assertTrue(result["deleted"])
        self.assertFalse(result["batch"])
        self.assertTrue(result["verified"])
        deletes = [c for c in client.calls if c["method"] == "delete"]
        self.assertEqual(len(deletes), 1, "永不批量删除")
        self.assertEqual(deletes[0]["key"], "DDDD4444")
        self.assertEqual(deletes[0]["version"], 9)

    def test_delete_conflict_is_reported(self) -> None:
        client = self._client()
        client.fail_next["delete"] = [zw.ZoteroConflict("stale version")]
        result = crud.delete_paper(client, "DDDD4444", dry_run=False, confirm=True)
        self.assertFalse(result["deleted"])
        self.assertTrue(result["conflict"])
        self.assertIn("DDDD4444", client._items)

    def test_delete_timeout_is_retried(self) -> None:
        client = self._client()
        client.fail_next["delete"] = [zw.ZoteroWriteError("timeout")]
        with mock.patch.object(crud, "_sleep", lambda _seconds: None):
            result = crud.delete_paper(client, "DDDD4444", dry_run=False, confirm=True)
        self.assertTrue(result["deleted"])
        self.assertEqual(len([c for c in client.calls if c["method"] == "delete"]), 2)

    def test_missing_item_reported(self) -> None:
        client = FakeClient()
        result = crud.delete_paper(client, "NOPE")
        self.assertFalse(result["deleted"])
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
