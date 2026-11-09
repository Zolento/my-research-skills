#!/usr/bin/env python3
"""`zotero_client` 纯函数回归测试（不联网、不依赖运行中的 Zotero）。

重点覆盖 arXiv 标识提取的边界：早期实现用无锚点正则匹配任意 URL，
把 `https://ieeexplore.ieee.org/document/10656634/` 误判成 `document/1065663`，
导致 744 条导出中有 151 条得到伪 `paper_id`。此处固定修复后的行为。
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import zotero_client as zc  # noqa: E402


class ArxivIdTests(unittest.TestCase):
    """arXiv 标识提取：既不能误判非 arXiv 内容，也不能漏掉真实标识。"""

    def test_non_arxiv_url_is_not_matched(self) -> None:
        for url in (
            "https://ieeexplore.ieee.org/document/10656634/",
            "https://www.sciencedirect.com/science/article/pii/S1361841523001234",
            "https://link.springer.com/chapter/10.1007/978-3-031-16446-0_45",
        ):
            with self.subTest(url=url):
                self.assertIsNone(zc.arxiv_id({"url": url}))

    def test_non_arxiv_doi_in_extra_is_not_matched(self) -> None:
        """`10.1109/TMI.2018.2820120` 曾被截成 `2018.28201`。"""
        self.assertIsNone(zc.arxiv_id({"extra": "IEEE Xplore, doi:10.1109/TMI.2018.2820120"}))
        self.assertIsNone(zc.arxiv_id({"DOI": "10.1109/TMI.2018.2820120"}))

    def test_arxiv_urls_still_match(self) -> None:
        cases = {
            "http://arxiv.org/abs/2410.02423": "2410.02423",
            "https://arxiv.org/pdf/2303.03982.pdf": "2303.03982",
            "https://arxiv.org/abs/cs.CV/0701001": "cs.CV/0701001",
        }
        for url, want in cases.items():
            with self.subTest(url=url):
                self.assertEqual(zc.arxiv_id({"url": url}), want)

    def test_explicit_and_bare_ids_in_extra(self) -> None:
        self.assertEqual(zc.arxiv_id({"extra": "arXiv:2111.00396"}), "2111.00396")
        self.assertEqual(zc.arxiv_id({"extra": "2303.03982"}), "2303.03982")
        self.assertEqual(zc.arxiv_id({"extra": "2303.03982v2"}), "2303.03982")
        self.assertEqual(zc.arxiv_id({"extra": "arXiv:cs.CV/0701001"}), "cs.CV/0701001")
        self.assertEqual(zc.arxiv_id({"extra": "10.48550/arXiv.2502.08040"}), "2502.08040")

    def test_arxiv_doi(self) -> None:
        self.assertEqual(zc.arxiv_id({"DOI": "10.48550/arXiv.2502.08040"}), "2502.08040")

    def test_unknown_old_style_archive_is_rejected(self) -> None:
        """旧式标识必须落在真实 archive 上。"""
        self.assertIsNone(zc.arxiv_id({"extra": "document/1065663"}))


class MappingTests(unittest.TestCase):
    """`item_to_record` / `item_to_sidecar` 的字段映射与 provenance。"""

    ITEM = {
        "key": "ABCD1234",
        "version": 0,
        "data": {
            "itemType": "journalArticle",
            "title": "A Test Paper",
            "abstractNote": "abstract text",
            "date": "2024-05-01",
            "publicationTitle": "Test Journal",
            "url": "https://arxiv.org/abs/2401.01234",
            "DOI": "10.1000/TEST.2024.001",
            "creators": [
                {"firstName": "Ada", "lastName": "Smith"},
                {"name": "Some Consortium"},
            ],
            "tags": [{"tag": "cs.CV"}],
            "dateAdded": "2024-06-01T00:00:00Z",
        },
    }

    def test_record_provenance_is_local(self) -> None:
        """Zotero 是本地库后端，provenance 必须是 local（源枚举不变）。"""
        record = zc.item_to_record(self.ITEM)
        self.assertEqual(record["sources"], ["local"])
        self.assertEqual(record["zotero_key"], "ABCD1234")

    def test_record_fields(self) -> None:
        record = zc.item_to_record(self.ITEM)
        self.assertEqual(record["title"], "A Test Paper")
        self.assertEqual(record["authors"], ["Ada Smith", "Some Consortium"])
        self.assertEqual(record["year"], 2024)
        self.assertEqual(record["venue"], "Test Journal")
        self.assertEqual(record["doi"], "10.1000/test.2024.001")
        self.assertEqual(record["arxiv_id"], "2401.01234")
        self.assertEqual(record["keywords"], ["cs.CV"])

    def test_sidecar_prefers_arxiv_id_as_paper_id(self) -> None:
        sidecar = zc.item_to_sidecar(self.ITEM)
        self.assertEqual(sidecar["paper_id"], "2401.01234")
        self.assertEqual(sidecar["source"], "zotero")
        self.assertEqual(sidecar["metadata_from"], "zotero")
        self.assertFalse(sidecar["needs_verification"])
        self.assertIsNone(sidecar["file"])

    def test_sidecar_flags_missing_metadata(self) -> None:
        item = {"key": "X", "data": {"itemType": "document", "title": ""}}
        sidecar = zc.item_to_sidecar(item)
        self.assertTrue(sidecar["needs_verification"])
        self.assertEqual(sidecar["paper_id"], "X")

    def test_bibliographic_filter_excludes_children(self) -> None:
        items = [
            self.ITEM,
            {"key": "ATT", "data": {"itemType": "attachment", "parentItem": "ABCD1234"}},
            {"key": "NOTE", "data": {"itemType": "note", "parentItem": "ABCD1234"}},
        ]
        keys = [i["key"] for i in zc.bibliographic_items(items)]
        self.assertEqual(keys, ["ABCD1234"])

    def test_pdf_children_indexing(self) -> None:
        items = [
            {"key": "P1", "data": {"itemType": "attachment", "parentItem": "ABCD1234",
                                   "contentType": "application/pdf"}},
            {"key": "P2", "data": {"itemType": "attachment", "parentItem": "ABCD1234",
                                   "contentType": "text/html"}},
        ]
        mapping = zc.pdf_children(items)
        self.assertEqual([i["key"] for i in mapping["ABCD1234"]], ["P1"])


class ProbeTests(unittest.TestCase):
    """探测失败必须返回 None（调用方据此回落 docs/refs/），不得抛异常。"""

    def test_unreachable_returns_none(self) -> None:
        self.assertIsNone(zc.probe("http://127.0.0.1:1/api", timeout=0.5))

    def test_fetch_raises_zotero_unavailable(self) -> None:
        with self.assertRaises(zc.ZoteroUnavailable):
            zc.fetch_items("http://127.0.0.1:1/api", timeout=0.5)


class _FakeResponse:
    """最小可用的 urlopen 替身。"""

    def __init__(self, body: bytes, headers=None, status: int = 200):
        self._body = body
        self.headers = headers or {}
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_urlopen(payload, headers=None, status=200):
    """把 urlopen 换成返回固定载荷的替身；返回 (patcher, captured)。"""
    captured = {"url": None}

    def fake_urlopen(request, timeout=None):
        captured["url"] = getattr(request, "full_url", str(request))
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        return _FakeResponse(body, headers=headers, status=status)

    return mock.patch.object(zc.urllib.request, "urlopen", fake_urlopen), captured


class ReadPrimitiveTests(unittest.TestCase):
    """P3/P4 依赖的只读原语。用替身隔离网络，不依赖运行中的 Zotero。"""

    ITEM = {"key": "AAA", "version": 0, "data": {"itemType": "preprint", "title": "T"}}

    def test_get_item_returns_none_for_empty_key(self) -> None:
        self.assertIsNone(zc.get_item(""))

    def test_get_item_builds_expected_url(self) -> None:
        patcher, captured = _patch_urlopen(self.ITEM)
        with patcher:
            item = zc.get_item("AAA")
        self.assertEqual(item["key"], "AAA")
        self.assertTrue(captured["url"].endswith("/api/users/0/items/AAA"))

    def test_get_children_returns_list(self) -> None:
        patcher, _ = _patch_urlopen([self.ITEM])
        with patcher:
            self.assertEqual(len(zc.get_children("AAA")), 1)

    def test_get_children_tolerates_non_list(self) -> None:
        patcher, _ = _patch_urlopen({"nope": 1})
        with patcher:
            self.assertEqual(zc.get_children("AAA"), [])

    def test_search_items_sends_qmode(self) -> None:
        patcher, captured = _patch_urlopen([self.ITEM])
        with patcher:
            zc.search_items("mri", qmode="everything", limit=5)
        self.assertIn("qmode=everything", captured["url"])
        self.assertIn("q=mri", captured["url"])

    def test_item_fulltext_shape(self) -> None:
        patcher, _ = _patch_urlopen({"content": "hello", "indexedPages": 3, "totalPages": 4})
        with patcher:
            ft = zc.item_fulltext("ATT")
        self.assertEqual(ft["content"], "hello")
        self.assertEqual(ft["indexedPages"], 3)
        self.assertEqual(ft["totalPages"], 4)

    def test_item_fulltext_returns_none_when_unavailable(self) -> None:
        with mock.patch.object(zc.urllib.request, "urlopen", side_effect=OSError("boom")):
            self.assertIsNone(zc.item_fulltext("ATT"))

    def test_fulltext_versions_parses_map(self) -> None:
        patcher, _ = _patch_urlopen({"A1": 12, "A2": 0})
        with patcher:
            self.assertEqual(zc.fulltext_versions(since=7), {"A1": 12, "A2": 0})

    def test_file_view_url_accepts_plain_text(self) -> None:
        """该端点是 text/plain 的裸 URL，不是 JSON（曾用 _get_json 而失败）。"""
        patcher, _ = _patch_urlopen(b"file:///tmp/x.pdf")
        with patcher:
            self.assertEqual(zc.file_view_url("ATT"), "file:///tmp/x.pdf")

    def test_file_view_url_rejects_non_file_scheme(self) -> None:
        patcher, _ = _patch_urlopen(b"https://example.com/x.pdf")
        with patcher:
            self.assertIsNone(zc.file_view_url("ATT"))

    def test_file_url_to_path_roundtrip(self) -> None:
        self.assertEqual(zc.file_url_to_path("file:///tmp/a%20b.pdf"), "/tmp/a b.pdf")
        self.assertIsNone(zc.file_url_to_path("https://example.com/a.pdf"))

    def test_local_attachment_path_prefers_api_then_storage(self) -> None:
        """Local API 优先（用户可能用第三方云盘），storage 仅作回退。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            real = os.path.join(tmp, "real.pdf")
            open(real, "wb").close()
            att = {"key": "ATT", "data": {"filename": "real.pdf"}}
            patcher, _ = _patch_urlopen(f"file://{real}".encode())
            with patcher:
                self.assertEqual(zc.local_attachment_path(att), real)

            fallback_root = os.path.join(tmp, "storage")
            os.makedirs(os.path.join(fallback_root, "ATT"))
            open(os.path.join(fallback_root, "ATT", "real.pdf"), "wb").close()
            with mock.patch.object(zc.urllib.request, "urlopen", side_effect=OSError("down")):
                got = zc.local_attachment_path(att, storage_dir=fallback_root)
            self.assertEqual(got, os.path.join(fallback_root, "ATT", "real.pdf"))

    def test_local_attachment_path_returns_none_when_missing(self) -> None:
        att = {"key": "ATT", "data": {"filename": "nope.pdf"}}
        with mock.patch.object(zc.urllib.request, "urlopen", side_effect=OSError("down")):
            self.assertIsNone(zc.local_attachment_path(att, storage_dir="/nonexistent-root"))

    def test_api_root_reads_version_headers(self) -> None:
        headers = {"Zotero-API-Version": "3", "Zotero-Schema-Version": "44",
                   "Zotero-Server-ID": "SID"}
        patcher, _ = _patch_urlopen(b"Nothing to see here.", headers=headers)
        with patcher:
            info = zc.api_root()
        self.assertEqual(info["api_version"], "3")
        self.assertEqual(info["schema_version"], "44")
        self.assertEqual(info["server_id"], "SID")

    def test_api_root_returns_none_when_down(self) -> None:
        with mock.patch.object(zc.urllib.request, "urlopen", side_effect=OSError("down")):
            self.assertIsNone(zc.api_root())


class OrphanAttachmentTests(unittest.TestCase):
    """搜索命中里存在**无父条目的孤立附件**，归并逻辑必须能识别。"""

    def test_orphan_attachment_detected(self) -> None:
        items = [
            {"key": "ORPHAN", "data": {"itemType": "attachment", "contentType": "application/pdf"}},
            {"key": "CHILD", "data": {"itemType": "attachment", "parentItem": "PAPER"}},
            {"key": "PAPER", "data": {"itemType": "preprint", "title": "P"}},
        ]
        bib = {i["key"] for i in zc.bibliographic_items(items)}
        orphans = [i for i in items
                   if (i["data"] or {}).get("itemType") == "attachment"
                   and not (i["data"] or {}).get("parentItem")]
        self.assertEqual([o["key"] for o in orphans], ["ORPHAN"])
        self.assertIn("PAPER", bib)
        self.assertNotIn("ORPHAN", bib)


if __name__ == "__main__":
    unittest.main()
