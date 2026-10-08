#!/usr/bin/env python3
"""`zotero_client` 纯函数回归测试（不联网、不依赖运行中的 Zotero）。

重点覆盖 arXiv 标识提取的边界：早期实现用无锚点正则匹配任意 URL，
把 `https://ieeexplore.ieee.org/document/10656634/` 误判成 `document/1065663`，
导致 744 条导出中有 151 条得到伪 `paper_id`。此处固定修复后的行为。
"""
from __future__ import annotations

import os
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
