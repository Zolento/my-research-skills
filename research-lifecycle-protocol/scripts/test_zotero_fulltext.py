#!/usr/bin/env python3
"""`zotero_fulltext` 回归测试：真实 PDF 抽取 + 归并 + 缓存 + 两层检索。

纪律（与硬要求一一对应）：

- **不 mock PDF 解析**：用 `pypdf` 在临时目录里**真实生成**多页 PDF
  （已知文本在已知页、含无文本页、含分栏页），断言抽取在**正确的物理页**找到字符串。
- **不 mock API**：用鸭子类型的 `FakeClient`，**绝不**访问真实 Zotero。
- **页码纪律**：索引命中永远 `indexed_fulltext` 且无页码；只有真实页命中才 `page_verified`。
- **缓存纪律**：身份 = Server ID + Library ID + Item Key + Attachment Key + 指纹；
  PDF 变化 → 旧缓存不命中；Server ID 变化 → 整库不命中。
"""
from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import zotero_fulltext as zf  # noqa: E402

from pypdf import PdfWriter  # noqa: E402
from pypdf.constants import PageLabelStyle  # noqa: E402
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject  # noqa: E402


# ---------------------------------------------------------------------------
# 真实 PDF 生成
# ---------------------------------------------------------------------------

def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _attach_font(page) -> None:
    resources = DictionaryObject()
    fonts = DictionaryObject()
    fonts[NameObject("/F1")] = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    resources[NameObject("/Font")] = fonts
    page[NameObject("/Resources")] = resources


def build_pdf(path, pages, *, page_labels_start=None) -> str:
    """用 pypdf + 原生内容流写一个真实 PDF。

    `pages` 的每项：``None`` 表示空白页（无内容流）；
    或者是 item 列表，item 为 ``str``（自动排版到左上）或 ``(x, y, text)``。
    """
    writer = PdfWriter()
    for spec in pages:
        page = writer.add_blank_page(width=612, height=792)
        if spec is None:
            continue
        _attach_font(page)
        ops = ["BT", "/F1 12 Tf"]
        auto_y = 720
        for item in spec:
            if isinstance(item, str):
                x, y, text = 72, auto_y, item
                auto_y -= 18
            else:
                x, y, text = item
            ops.append(f"1 0 0 1 {x} {y} Tm ({_escape(text)}) Tj")
        ops.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(ops).encode("latin-1"))
        page[NameObject("/Contents")] = stream
    if page_labels_start is not None:
        writer.set_page_label(0, len(pages) - 1,
                              style=PageLabelStyle.DECIMAL, start=page_labels_start)
    target = Path(path)
    with target.open("wb") as fh:
        writer.write(fh)
    return str(target)


# ---------------------------------------------------------------------------
# 鸭子类型客户端
# ---------------------------------------------------------------------------

def parent_item(key, title, *, year=2020, abstract=None, doi=None):
    return {
        "key": key,
        "version": 1,
        "data": {
            "itemType": "journalArticle",
            "title": title,
            "date": str(year),
            "abstractNote": abstract,
            "DOI": doi,
            "creators": [{"firstName": "Ada", "lastName": "Smith"}],
            "tags": [{"tag": "diffusion"}],
        },
    }


def attachment_item(key, parent=None, *, filename="paper.pdf",
                    link_mode="imported_file", content_type="application/pdf",
                    path=None, title=None):
    data = {
        "itemType": "attachment",
        "filename": filename,
        "linkMode": link_mode,
        "contentType": content_type,
        "title": title if title is not None else filename,
    }
    if parent:
        data["parentItem"] = parent
    if path:
        data["path"] = path
    return {"key": key, "version": 1, "data": data}


class FakeClient:
    """只读方法齐全的鸭子类型客户端；不接触网络。"""

    def __init__(self, *, items=None, fulltexts=None, file_urls=None,
                 parent_items=None, server_id="SRV-A", search_error=None):
        self.items = list(items or [])
        self.fulltexts = dict(fulltexts or {})
        self.file_urls = dict(file_urls or {})
        self.parent_items = dict(parent_items or {})
        self._server_id = server_id
        self.search_error = search_error
        self.search_calls = []

    @property
    def server_id(self):
        return self._server_id

    def probe(self, *_args, **_kwargs):
        return self._server_id

    def search_items(self, query, **kwargs):
        if self.search_error is not None:
            raise self.search_error
        self.search_calls.append((query, kwargs))
        return [dict(item) for item in self.items]

    def item_fulltext(self, key, **kwargs):
        return self.fulltexts.get(key)

    def file_view_url(self, key, **kwargs):
        return self.file_urls.get(key)

    def get_item(self, key, **kwargs):
        return self.parent_items.get(key)


def file_url(path) -> str:
    return Path(path).resolve().as_uri()


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


# ---------------------------------------------------------------------------
# 归并规则
# ---------------------------------------------------------------------------

class SearchIndexedMergeTests(TempDirTestCase):
    def test_attachment_merges_back_to_parent(self):
        client = FakeClient(
            items=[parent_item("P1", "Diffusion Models for X", year=2021),
                   attachment_item("A1", "P1")],
            fulltexts={"A1": {"content": "diffusion model discrete optimization",
                              "indexedPages": 10, "totalPages": 10}},
        )
        results = zf.search_indexed(client, "diffusion model")
        self.assertEqual(len(results), 1)
        record = results[0]
        self.assertEqual(record["zotero_key"], "P1")
        self.assertEqual(record["title"], "Diffusion Models for X")
        self.assertEqual(len(record["attachments"]), 1)
        self.assertEqual(record["attachments"][0]["attachment_key"], "A1")
        self.assertTrue(record["attachments"][0]["indexed"])
        self.assertEqual(record["verification"], "indexed_fulltext")
        self.assertGreater(record["_score"], 0)
        # ★ 索引命中绝不带页码。
        self.assertNotIn("page", record)
        self.assertNotIn("pages", record)

    def test_parent_and_attachment_are_not_double_counted(self):
        client = FakeClient(
            items=[parent_item("P1", "Paper One"),
                   attachment_item("A1", "P1"),
                   attachment_item("A2", "P1")],
            fulltexts={"A1": {"content": "alpha", "indexedPages": 3, "totalPages": 3},
                       "A2": {"content": "beta", "indexedPages": 4, "totalPages": 4}},
        )
        results = zf.search_indexed(client, "alpha")
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]["attachments"]), 2)

    def test_orphan_attachment_is_kept_and_not_double_counted(self):
        client = FakeClient(
            items=[attachment_item("ORPH1", None, title="Standalone scan.pdf")],
            fulltexts={"ORPH1": {"content": "orphan fulltext body",
                                 "indexedPages": 2, "totalPages": 2}},
        )
        results = zf.search_indexed(client, "orphan fulltext")
        self.assertEqual(len(results), 1)
        record = results[0]
        self.assertEqual(record["zotero_key"], "ORPH1")
        self.assertTrue(record.get("orphan_attachment"))
        self.assertFalse(record.get("parent_metadata_missing"))
        self.assertEqual(record["verification"], "indexed_fulltext")

    def test_orphan_and_normal_paper_coexist(self):
        client = FakeClient(
            items=[parent_item("P1", "Normal Paper"),
                   attachment_item("A1", "P1"),
                   attachment_item("ORPH1", None)],
            fulltexts={"A1": {"content": "shared token", "indexedPages": 1, "totalPages": 1},
                       "ORPH1": {"content": "shared token", "indexedPages": 1, "totalPages": 1}},
        )
        results = zf.search_indexed(client, "shared token")
        keys = sorted(r["zotero_key"] for r in results)
        self.assertEqual(keys, ["ORPH1", "P1"])

    def test_parent_not_in_results_is_fetched_then_stubbed(self):
        client = FakeClient(
            items=[attachment_item("A1", "P9")],
            fulltexts={"A1": {"content": "text here", "indexedPages": 1, "totalPages": 1}},
            parent_items={"P9": parent_item("P9", "Recovered Title", year=2018)},
        )
        results = zf.search_indexed(client, "text here")
        self.assertEqual(results[0]["title"], "Recovered Title")

        client.parent_items = {}
        results = zf.search_indexed(client, "text here")
        record = results[0]
        self.assertIsNone(record["title"])          # 绝不编造标题
        self.assertTrue(record["parent_metadata_missing"])

    def test_partial_index_is_flagged(self):
        client = FakeClient(
            items=[parent_item("P1", "Partial Index Paper"),
                   attachment_item("A1", "P1")],
            fulltexts={"A1": {"content": "partial body", "indexedPages": 3, "totalPages": 10}},
        )
        record = zf.search_indexed(client, "partial body")[0]
        self.assertTrue(record["attachments"][0]["partial_index"])
        self.assertEqual(record["attachments"][0]["indexed_pages"], 3)
        self.assertEqual(record["attachments"][0]["total_pages"], 10)

    def test_no_index_degrades_to_abstract_or_metadata(self):
        client = FakeClient(
            items=[parent_item("P1", "No Index Paper", abstract="some abstract")],
            fulltexts={},
        )
        record = zf.search_indexed(client, "no index paper")[0]
        self.assertFalse(record["attachments"])
        self.assertEqual(record["verification"], "abstract_only")

        client = FakeClient(items=[parent_item("P2", "Bare Paper")], fulltexts={})
        record = zf.search_indexed(client, "bare paper")[0]
        self.assertEqual(record["verification"], "metadata_only")

    def test_year_filter_excludes_unknown_year(self):
        client = FakeClient(
            items=[parent_item("P1", "Old Paper", year=2019),
                   parent_item("P2", "No Date Paper")],
            fulltexts={},
        )
        client.items[1]["data"].pop("date", None)
        self.assertEqual(
            {r["zotero_key"] for r in zf.search_indexed(client, "paper", from_year=2020)},
            set())
        self.assertEqual(
            {r["zotero_key"] for r in zf.search_indexed(client, "paper", to_year=2020)},
            {"P1"})

        # 年份未知的条目在启用过滤时一律排除（与 search_local 语义一致）。
        client.items[1]["data"]["date"] = "2021"
        self.assertEqual(
            {r["zotero_key"] for r in zf.search_indexed(client, "paper", from_year=2020)},
            {"P2"})

    def test_non_overlapping_token_still_returns_zotero_hit(self):
        """命中来自 Zotero 索引，本模块分词未重合也**不能丢**。"""
        client = FakeClient(
            items=[parent_item("P1", "Completely Different Title")],
            fulltexts={},
        )
        results = zf.search_indexed(client, "zzz nonexistent")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["matched_via"], "zotero_index")


class AttachmentFulltextTests(unittest.TestCase):
    def test_normalizes_payload(self):
        class C:
            def item_fulltext(self, key, **kwargs):
                return {"content": "abc", "indexedPages": 3, "totalPages": 10}

        got = zf.attachment_fulltext(C(), "A1")
        self.assertEqual(got["content"], "abc")
        self.assertTrue(got["indexed"])
        self.assertTrue(got["partial"])

    def test_none_and_failure_degrade(self):
        class C:
            def item_fulltext(self, key, **kwargs):
                return None

        class Boom:
            def item_fulltext(self, key, **kwargs):
                raise RuntimeError("timeout")

        self.assertIsNone(zf.attachment_fulltext(C(), "A1"))
        self.assertIsNone(zf.attachment_fulltext(Boom(), "A1"))
        self.assertIsNone(zf.attachment_fulltext(C(), ""))


# ---------------------------------------------------------------------------
# 附件路径解析
# ---------------------------------------------------------------------------

class ResolveAttachmentPathTests(TempDirTestCase):
    def test_file_view_url_wins_over_storage_fallback(self):
        via_api = self.tmp / "cloud" / "p.pdf"
        via_api.parent.mkdir(parents=True)
        via_api.write_bytes(b"%PDF-1.4 cloud")
        storage = self.tmp / "storage" / "A1"
        storage.mkdir(parents=True)
        (storage / "paper.pdf").write_bytes(b"%PDF-1.4 storage")

        client = FakeClient(file_urls={"A1": file_url(via_api)})
        got = zf.resolve_attachment_path(
            client, attachment_item("A1", "P1"), storage_dir=str(self.tmp / "storage"))
        self.assertEqual(got, str(via_api))

    def test_storage_fallback_for_imported_file(self):
        storage = self.tmp / "storage" / "A1"
        storage.mkdir(parents=True)
        target = storage / "paper.pdf"
        target.write_bytes(b"%PDF-1.4 storage")
        client = FakeClient()
        got = zf.resolve_attachment_path(
            client, attachment_item("A1", "P1"), storage_dir=str(self.tmp / "storage"))
        self.assertEqual(got, str(target))

    def test_storage_fallback_for_imported_url(self):
        storage = self.tmp / "storage" / "A2"
        storage.mkdir(parents=True)
        target = storage / "web.pdf"
        target.write_bytes(b"%PDF-1.4 web")
        att = attachment_item("A2", "P1", filename="web.pdf", link_mode="imported_url")
        got = zf.resolve_attachment_path(
            FakeClient(), att, storage_dir=str(self.tmp / "storage"))
        self.assertEqual(got, str(target))

    def test_http_url_is_never_followed(self):
        client = FakeClient(file_urls={"A1": "https://example.com/paper.pdf"})
        with mock.patch("urllib.request.urlopen",
                        side_effect=AssertionError("must not open network")):
            self.assertIsNone(zf.resolve_attachment_path(client, attachment_item("A1", "P1")))

    def test_linked_file_absolute_path(self):
        target = self.tmp / "linked.pdf"
        target.write_bytes(b"%PDF-1.4 linked")
        att = attachment_item("A1", "P1", link_mode="linked_file", path=str(target))
        self.assertEqual(zf.resolve_attachment_path(FakeClient(), att), str(target))

    def test_linked_url_returns_none(self):
        att = attachment_item("A1", "P1", link_mode="linked_url",
                              path="https://example.com/x.pdf")
        self.assertIsNone(zf.resolve_attachment_path(FakeClient(), att))

    def test_missing_file_returns_none(self):
        client = FakeClient(file_urls={"A1": file_url(self.tmp / "nope.pdf")})
        self.assertIsNone(zf.resolve_attachment_path(client, attachment_item("A1", "P1")))

    def test_path_traversal_filename_is_rejected(self):
        root = self.tmp / "storage"
        key_dir = root / "A1"
        key_dir.mkdir(parents=True)
        (root / "escape.pdf").write_bytes(b"x")
        att = attachment_item("A1", "P1", filename="../escape.pdf")
        self.assertIsNone(
            zf.resolve_attachment_path(FakeClient(), att, storage_dir=str(root)))


# ---------------------------------------------------------------------------
# 真实 PDF 抽取
# ---------------------------------------------------------------------------

class ExtractPagesTests(TempDirTestCase):
    def _three_page(self):
        return build_pdf(self.tmp / "three.pdf", [
            ["UniqueMarker AlphaBeta99 lives on physical page one.",
             "Second line with enough words to be extracted cleanly."],
            None,                                    # 无文本页（空白）
            ["Page three carries GammaDelta77 token.",
             "Another line so the page has real content."],
        ])

    def test_known_string_on_correct_physical_page(self):
        extracted = zf.extract_pages(self._three_page())
        self.assertEqual(extracted["num_pages"], 3)
        self.assertEqual(len(extracted["pages"]), 3)
        self.assertIn("AlphaBeta99", extracted["pages"][0]["text"])
        self.assertNotIn("GammaDelta77", extracted["pages"][0]["text"])
        self.assertEqual(extracted["pages"][1]["text"].strip(), "")
        self.assertIn("GammaDelta77", extracted["pages"][2]["text"])

        hits = zf.search_pdf_pages(self._three_page(), "GammaDelta77")
        self.assertEqual([h["page"] for h in hits], [3])
        self.assertEqual(hits[0]["verification"], "page_verified")
        self.assertIn("GammaDelta77", hits[0]["snippet"])

    def test_char_offsets_index_the_concatenation(self):
        extracted = zf.extract_pages(self._three_page())
        concat = "\n".join(p["text"] for p in extracted["pages"])
        for page in extracted["pages"]:
            start = page["char_offset"]
            self.assertEqual(concat[start:start + len(page["text"])], page["text"])

    def test_empty_page_flagged_without_inventing_text(self):
        extracted = zf.extract_pages(self._three_page())
        blank = extracted["pages"][1]
        self.assertEqual(blank["quality"], "empty")
        self.assertIn("empty", blank["flags"])
        self.assertEqual(blank["text"], "")

    def test_sha256_toggle_computes_file_fingerprint(self):
        import hashlib

        path = Path(self._three_page())
        with_fp = zf.extract_pages(path, sha256=True)
        self.assertEqual(with_fp["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertIsNone(zf.extract_pages(path, sha256=False)["sha256"])

    def test_scanned_classification_when_image_present(self):
        quality, flags = zf.page_quality("", has_image=True)
        self.assertEqual(quality, "scanned")
        self.assertIn("scanned", flags)

    def test_missing_and_corrupt_file(self):
        with self.assertRaises(FileNotFoundError):
            zf.extract_pages(self.tmp / "nope.pdf")

        corrupt = self.tmp / "corrupt.pdf"
        corrupt.write_bytes(b"this is definitely not a pdf")
        with self.assertRaises(zf.PdfUnavailable):
            zf.extract_pages(corrupt)

    @unittest.skipIf(os.geteuid() == 0, "root 无视文件权限")
    def test_unreadable_file_raises(self):
        path = self.tmp / "locked.pdf"
        build_pdf(path, [["locked content"]])
        os.chmod(path, 0)
        try:
            with self.assertRaises((zf.PdfUnavailable, FileNotFoundError, PermissionError)):
                zf.extract_pages(path)
        finally:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


class PrintedPageTests(TempDirTestCase):
    def test_printed_page_differs_from_physical_page(self):
        path = build_pdf(self.tmp / "printed.pdf", [
            ["Body of physical page one with a long enough line."],
            ["Body of physical page two with a long enough line.",
             (300, 60, "- 7 -")],
        ])
        extracted = zf.extract_pages(path)
        self.assertEqual(extracted["pages"][0]["page"], 1)
        self.assertEqual(extracted["pages"][1]["page"], 2)          # 物理页
        self.assertEqual(extracted["pages"][1]["printed_page"], "7")  # 印刷页码
        self.assertNotEqual(extracted["pages"][1]["printed_page"],
                            str(extracted["pages"][1]["page"]))

    def test_printed_page_is_none_when_absent(self):
        """pypdf 会伪造 page_labels=["1","2"]；绝不能拿它冒充印刷页码。"""
        path = build_pdf(self.tmp / "nolabel.pdf", [
            ["No standalone page number appears on this page at all."],
            ["Still no printed label on the second page either."],
        ])
        extracted = zf.extract_pages(path)
        self.assertIsNone(extracted["pages"][0]["printed_page"])
        self.assertIsNone(extracted["pages"][1]["printed_page"])

    def test_explicit_pdf_page_labels_are_used(self):
        path = build_pdf(self.tmp / "labels.pdf", [
            ["First page body text long enough for extraction."],
            ["Second page body text long enough for extraction."],
        ], page_labels_start=7)
        extracted = zf.extract_pages(path)
        self.assertEqual([p["printed_page"] for p in extracted["pages"]], ["7", "8"])

    def test_label_token_parsing_is_conservative(self):
        self.assertEqual(zf._printed_page_token("- 7 -"), "7")
        self.assertEqual(zf._printed_page_token("Page 12"), "12")
        self.assertEqual(zf._printed_page_token("5 / 12"), "5")
        self.assertEqual(zf._printed_page_token("vii"), "vii")
        self.assertIsNone(zf._printed_page_token("2024"))   # 年份，不是页码
        self.assertIsNone(zf._printed_page_token("civil"))  # 罗马字母拼成的单词


class TwoColumnTests(TempDirTestCase):
    def test_interleaved_columns_are_flagged(self):
        ops = []
        for index in range(6):
            y = 700 - index * 22
            ops.append((72, y, f"Left column sentence number {index} has words."))
            ops.append((330, y, f"Right column sentence number {index} has words."))
        path = build_pdf(self.tmp / "twocol.pdf", [ops])
        page = zf.extract_pages(path)["pages"][0]
        self.assertEqual(page["columns"], 2)
        self.assertEqual(page["quality"], "two_column_order")
        self.assertIn("two_column_order", page["flags"])

    def test_single_column_is_not_flagged(self):
        ops = [(72, 700 - i * 20, f"Single column line {i} with several words here.")
               for i in range(8)]
        path = build_pdf(self.tmp / "onecol.pdf", [ops])
        page = zf.extract_pages(path)["pages"][0]
        self.assertEqual(page["columns"], 1)
        self.assertEqual(page["quality"], "ok")


class SearchPdfPagesTests(TempDirTestCase):
    def test_page_filter_restricts_results(self):
        path = build_pdf(self.tmp / "multi.pdf", [
            ["shared token appears on page one with extra words."],
            ["nothing relevant on this middle page at all really."],
            ["shared token appears again on page three with words."],
        ])
        hits = zf.search_pdf_pages(path, "shared token")
        self.assertEqual(sorted(h["page"] for h in hits), [1, 3])
        only_three = zf.search_pdf_pages(path, "shared token", pages=[3])
        self.assertEqual([h["page"] for h in only_three], [3])

    def test_no_match_returns_empty(self):
        path = build_pdf(self.tmp / "nomatch.pdf", [["Totally unrelated content here."]])
        self.assertEqual(zf.search_pdf_pages(path, "absent phrase xyzzy"), [])


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------

class CacheTests(TempDirTestCase):
    def _root(self):
        return self.tmp / "cache"

    def test_roundtrip_and_location(self):
        path = zf.cache_put(self._root(), server_id="S1", library_id="0",
                            item_key="P1", attachment_key="A1", fingerprint="fp1",
                            payload={"pages": [{"page": 1, "text": "hi"}], "num_pages": 1})
        self.assertIsNotNone(path)
        self.assertEqual(zf.cache_get(self._root(), server_id="S1", library_id="0",
                                      item_key="P1", attachment_key="A1",
                                      fingerprint="fp1")["num_pages"], 1)
        # Server ID 必须是路径第一层。
        rel = Path(path).relative_to(self._root())
        self.assertEqual(rel.parts[0], "S1")
        self.assertEqual(stat.S_IMODE(Path(path).stat().st_mode), 0o600)
        self.assertIs(zf.get_text_cache, zf.cache_get)

    def test_server_id_change_invalidates_whole_cache(self):
        zf.cache_put(self._root(), server_id="S1", item_key="P1",
                     attachment_key="A1", fingerprint="fp1", payload={"num_pages": 1})
        self.assertIsNone(zf.cache_get(self._root(), server_id="S2", item_key="P1",
                                       attachment_key="A1", fingerprint="fp1"))

    def test_changed_fingerprint_misses(self):
        zf.cache_put(self._root(), server_id="S1", item_key="P1",
                     attachment_key="A1", fingerprint="fp1", payload={"num_pages": 1})
        self.assertIsNone(zf.cache_get(self._root(), server_id="S1", item_key="P1",
                                       attachment_key="A1", fingerprint="fp2"))

    def test_invalidate_by_fingerprint(self):
        zf.cache_put(self._root(), server_id="S1", item_key="P1",
                     attachment_key="A1", fingerprint="fp1", payload={"num_pages": 1})
        zf.cache_put(self._root(), server_id="S1", item_key="P1",
                     attachment_key="A1", fingerprint="fp2", payload={"num_pages": 2})
        removed = zf.invalidate_by_fingerprint(
            self._root(), server_id="S1", item_key="P1",
            attachment_key="A1", fingerprint="fp1")
        self.assertEqual(removed, 1)
        self.assertIsNotNone(zf.cache_get(self._root(), server_id="S1", item_key="P1",
                                          attachment_key="A1", fingerprint="fp1"))
        self.assertIsNone(zf.cache_get(self._root(), server_id="S1", item_key="P1",
                                       attachment_key="A1", fingerprint="fp2"))
        self.assertEqual(zf.invalidate_by_fingerprint(self._root()), 1)

    def test_default_cache_root_is_gitignored(self):
        parts = zf.default_cache_root().parts
        self.assertIn(".research-idea-pipeline", parts)
        self.assertEqual(parts[-1], "zotero-fulltext-cache")

        gitignore = Path(__file__).resolve().parent.parent / ".gitignore"
        if gitignore.is_file():
            text = gitignore.read_text(encoding="utf-8")
            self.assertIn(".research-idea-pipeline/", text)

    def test_env_override(self):
        with mock.patch.dict(os.environ, {zf.CACHE_ROOT_ENV: str(self.tmp / "alt")}):
            self.assertEqual(zf.default_cache_root(), self.tmp / "alt")


# ---------------------------------------------------------------------------
# 两层检索（deep）
# ---------------------------------------------------------------------------

class SearchTwoLayerTests(TempDirTestCase):
    def _cache(self):
        return self.tmp / "cache"

    def test_shallow_keeps_indexed_level_without_pages(self):
        client = FakeClient(
            items=[parent_item("P1", "Deep Paper"),
                   attachment_item("A1", "P1")],
            fulltexts={"A1": {"content": "needle in indexed text",
                              "indexedPages": 5, "totalPages": 5}},
        )
        out = zf.search_two_layer(client, "needle", deep=False)
        self.assertEqual(len(out["results"]), 1)
        self.assertEqual(out["results"][0]["verification"], "indexed_fulltext")
        self.assertEqual(out["page_hits"], [])
        self.assertNotIn("page_evidence", out["results"][0])

    def test_deep_upgrades_only_on_real_page_hit(self):
        pdf = build_pdf(self.tmp / "real.pdf", [
            ["Introduction without the target phrase."],
            ["The needle phrase lives on the second physical page here."],
        ])
        client = FakeClient(
            items=[parent_item("P1", "Deep Paper"),
                   attachment_item("A1", "P1")],
            fulltexts={"A1": {"content": "needle indexed",
                              "indexedPages": 2, "totalPages": 2}},
            file_urls={"A1": file_url(pdf)},
        )
        out = zf.search_two_layer(client, "needle", deep=True,
                                  cache_root=self._cache())
        record = out["results"][0]
        self.assertEqual(record["verification"], "page_verified")
        self.assertEqual([h["page"] for h in record["page_evidence"]], [2])
        self.assertEqual(record["page_evidence"][0]["verification"], "page_verified")
        self.assertEqual(out["stats"]["page_verified"], 1)
        self.assertEqual(out["cache"]["misses"], 1)
        # 深读后仍不得出现「只有索引却给出页码」的情况。
        self.assertTrue(record["page_evidence"][0]["snippet"])

    def test_deep_without_page_hit_stays_indexed(self):
        pdf = build_pdf(self.tmp / "other.pdf", [
            ["This page has unrelated words only."],
        ])
        client = FakeClient(
            items=[parent_item("P1", "Deep Paper"),
                   attachment_item("A1", "P1")],
            fulltexts={"A1": {"content": "needle phrase indexed",
                              "indexedPages": 1, "totalPages": 1}},
            file_urls={"A1": file_url(pdf)},
        )
        out = zf.search_two_layer(client, "needle phrase", deep=True,
                                  cache_root=self._cache())
        record = out["results"][0]
        self.assertEqual(record["verification"], "indexed_fulltext")
        self.assertEqual(record["page_evidence"], [])
        self.assertGreater(record["pdf"]["text_chars"], 0)

    def test_scanned_pdf_yields_insufficient_not_invented_text(self):
        pdf = build_pdf(self.tmp / "scanned.pdf", [None, None])
        client = FakeClient(
            items=[parent_item("P1", "Scanned Paper"),
                   attachment_item("A1", "P1")],
            fulltexts={},                       # 无索引
            file_urls={"A1": file_url(pdf)},
        )
        out = zf.search_two_layer(client, "anything", deep=True,
                                  cache_root=self._cache())
        record = out["results"][0]
        self.assertEqual(record["verification"], "insufficient_evidence")
        self.assertEqual(record["page_evidence"], [])
        self.assertEqual(record["pdf"]["text_chars"], 0)
        self.assertTrue(out["warnings"])

    def test_multiple_pdfs_for_one_paper(self):
        good = build_pdf(self.tmp / "good.pdf", [["needle token here on page one."]])
        second = build_pdf(self.tmp / "second.pdf", [["needle token also in supplement."]])
        client = FakeClient(
            items=[parent_item("P1", "Multi PDF Paper"),
                   attachment_item("A1", "P1", filename="main.pdf"),
                   attachment_item("A2", "P1", filename="supp.pdf")],
            fulltexts={"A1": {"content": "needle token", "indexedPages": 1, "totalPages": 1},
                       "A2": {"content": "needle token", "indexedPages": 1, "totalPages": 1}},
            file_urls={"A1": file_url(good), "A2": file_url(second)},
        )
        out = zf.search_two_layer(client, "needle token", deep=True,
                                  cache_root=self._cache())
        record = out["results"][0]
        self.assertEqual(len(record["attachments"]), 2)
        self.assertEqual(len(record["page_evidence"]), 2)
        self.assertEqual({h["attachment_key"] for h in record["page_evidence"]},
                         {"A1", "A2"})

    def test_pdf_change_invalidates_cached_text(self):
        first = build_pdf(self.tmp / "v1.pdf", [["needle token in version one."]])
        second = build_pdf(self.tmp / "v2.pdf", [["completely different content now."]])
        client = FakeClient(
            items=[parent_item("P1", "Changing PDF"),
                   attachment_item("A1", "P1")],
            fulltexts={"A1": {"content": "needle token", "indexedPages": 1, "totalPages": 1}},
            file_urls={"A1": file_url(first)},
        )
        out = zf.search_two_layer(client, "needle token", deep=True,
                                  cache_root=self._cache())
        self.assertEqual(out["results"][0]["verification"], "page_verified")

        # 同一文件再查 → 命中缓存。
        again = zf.search_two_layer(client, "needle token", deep=True,
                                    cache_root=self._cache())
        self.assertEqual(again["cache"]["hits"], 1)
        self.assertEqual(again["results"][0]["verification"], "page_verified")

        # PDF 内容变了（同 item/attachment key）→ 指纹变化 → 旧缓存不命中。
        client.file_urls["A1"] = file_url(second)
        changed = zf.search_two_layer(client, "needle token", deep=True,
                                      cache_root=self._cache())
        record = changed["results"][0]
        self.assertEqual(changed["cache"]["hits"], 0)
        self.assertEqual(record["page_evidence"], [])
        self.assertEqual(record["verification"], "indexed_fulltext")
        self.assertEqual(Path(record["attachments"][0]["path"]).resolve(),
                         Path(second).resolve())

    def test_partial_failure_does_not_crash_batch(self):
        good = build_pdf(self.tmp / "ok.pdf", [["needle token on the good paper."]])
        client = FakeClient(
            items=[parent_item("P1", "Good Paper"),
                   attachment_item("A1", "P1"),
                   parent_item("P2", "Broken Paper"),
                   attachment_item("A2", "P2")],
            fulltexts={"A1": {"content": "needle token", "indexedPages": 1, "totalPages": 1}},
            file_urls={"A1": file_url(good),
                       "A2": file_url(self.tmp / "missing.pdf")},
        )
        out = zf.search_two_layer(client, "needle token", deep=True,
                                  cache_root=self._cache())
        by_key = {r["zotero_key"]: r for r in out["results"]}
        self.assertEqual(by_key["P1"]["verification"], "page_verified")
        self.assertEqual(by_key["P2"]["verification"], "insufficient_evidence")
        self.assertTrue(out["warnings"])
        self.assertEqual(out["stats"]["attachments_unreadable"], 1)

    def test_index_search_failure_returns_structured_result(self):
        client = FakeClient(search_error=RuntimeError("local API down"))
        out = zf.search_two_layer(client, "q", deep=True)
        self.assertEqual(out["results"], [])
        self.assertTrue(out["warnings"])


if __name__ == "__main__":
    unittest.main()
