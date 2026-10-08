#!/usr/bin/env python3
"""`zotero_deepread.py` 的离线回归测试（stdlib unittest，**不联网、不依赖 Zotero**）。

运行：
    python -m unittest scripts.test_zotero_deepread -v
    python scripts/test_zotero_deepread.py

设计原则
--------
全部离线。注入 `FakeClient`（自带 `get_item` / `get_children` / `item_fulltext` /
`resolve_attachment_path` / `page_texts_for`），因此**不依赖**并行开发的
`zotero_fulltext.py` 是否存在。

断言基准是**夹具的 ground truth**，不是任何自动「研究质量分」：
夹具包含一段 method 描述、一条显式 assumption、一个 metric、一条 limitation，
以及一条弱相关干扰句。

覆盖点
------
1. overview 只到 abstract_only，且「有 PDF ≠ 深读过」
2. section 模式定位 method 并给出正确页码
3. evidence 模式：找到 assumption / metric / limitation，引文与页码正确
4. 支持句与无关句分离
5. 文本里没有的主张 —— **拒绝**断言
6. 不完整 PDF —— `insufficient_evidence` + 覆盖范围，未覆盖章节不编造
7. 等级升级规则：索引命中**永远**不升级为 `page_verified`；indexed 锚点 page 恒为 None
8. 锚点纪律：`page` 仅 `page_verified` 允许非 None；指纹不匹配 → stale
9. 真实 PDF（pypdf 内建回退）端到端 page_verified
10. compare_papers 跨论文对比
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import zotero_deepread as dr  # noqa: E402


# ---------------------------------------------------------------------------
# 夹具：一篇合成论文（4 页）+ 可选索引全文
# ---------------------------------------------------------------------------

PAGE_1 = "\n".join([
    "Discrete Diffusion for Combinatorial Optimization",
    "Abstract",
    "We propose a discrete diffusion method for combinatorial optimization.",
    "1. Introduction",
    "Combinatorial optimization is important in logistics and scheduling.",
])

PAGE_2 = "\n".join([
    "2. Method",
    "We propose a discrete diffusion sampler for combinatorial optimization.",
    "The sampler iteratively denoises a binary mask over the decision variables.",
    "We assume the noise process is independent across variables and that the "
    "transition kernel is reversible.",
])

PAGE_3 = "\n".join([
    "3. Experiments",
    "We evaluate the method on the traveling salesman benchmark.",
    "We report accuracy and optimality gap as the primary evaluation metric.",
    "The benchmark was collected in a different country.",
])

PAGE_4 = "\n".join([
    "4. Limitations",
    "A limitation of our approach is that it requires paired training data and "
    "does not scale beyond 100 nodes.",
])

ABSTRACT = "We propose a discrete diffusion method for combinatorial optimization."

#: 索引全文（扁平、无页码）：故意包含 method / assumption 文本。
INDEX_CONTENT = "\n".join([
    "Abstract",
    ABSTRACT,
    "2. Method",
    "We propose a discrete diffusion sampler for combinatorial optimization.",
    "We assume the noise process is independent across variables.",
    "3. Experiments",
    "We report accuracy and optimality gap as the primary evaluation metric.",
])

METHOD_QUOTE = "We propose a discrete diffusion sampler for combinatorial optimization."
ASSUMPTION_QUOTE = ("We assume the noise process is independent across variables and "
                    "that the transition kernel is reversible.")
METRIC_QUOTE = "We report accuracy and optimality gap as the primary evaluation metric."
LIMITATION_QUOTE = ("A limitation of our approach is that it requires paired training "
                    "data and does not scale beyond 100 nodes.")
DISTRACTOR_QUOTE = "The benchmark was collected in a different country."


def _page(number: int, text: str, quality: str = "good") -> Dict[str, Any]:
    return {"page": number, "printed_page": number, "text": text, "quality": quality}


def _pages_payload(pages: List[Dict[str, Any]], *, total: int,
                   sha256: str = "sha-full-4pages") -> Dict[str, Any]:
    return {"sha256": sha256, "num_pages": len(pages), "total_pages": total,
            "pages": pages}


FULL_PAGES = _pages_payload([_page(1, PAGE_1), _page(2, PAGE_2),
                             _page(3, PAGE_3), _page(4, PAGE_4)], total=4)

#: 只抽到前两页 / 共四页 —— 不完整。
PARTIAL_PAGES = _pages_payload([_page(1, PAGE_1), _page(2, PAGE_2)], total=4,
                               sha256="sha-partial")


def bib_item(key: str, *, title: str = "Discrete Diffusion for Combinatorial Optimization",
             doi: Optional[str] = "10.1234/ddco.2024", abstract: Optional[str] = ABSTRACT,
             date: str = "2024-03-01") -> Dict[str, Any]:
    return {
        "key": key,
        "version": 1,
        "data": {
            "key": key,
            "itemType": "journalArticle",
            "title": title,
            "creators": [{"firstName": "Ada", "lastName": "Smith",
                          "creatorType": "author"}],
            "date": date,
            "publicationTitle": "NeurIPS",
            "DOI": doi,
            "abstractNote": abstract,
        },
    }


def note_child(key: str, parent: str, note: str) -> Dict[str, Any]:
    return {"key": key, "version": 1,
            "data": {"key": key, "itemType": "note", "parentItem": parent,
                     "note": note}}


def pdf_child(key: str, parent: str, filename: str = "paper.pdf") -> Dict[str, Any]:
    return {"key": key, "version": 1,
            "data": {"key": key, "itemType": "attachment", "parentItem": parent,
                     "contentType": "application/pdf", "filename": filename,
                     "linkMode": "imported_file"}}


class FakeClient:
    """最小只读 client：暴露与 `_Bridge` 期望一致的方法，全部离线。"""

    def __init__(self, *, items: Dict[str, Any], children: Dict[str, List[Dict[str, Any]]],
                 fulltexts: Optional[Dict[str, Any]] = None,
                 page_texts: Optional[Dict[str, Any]] = None,
                 pdf_paths: Optional[Dict[str, str]] = None,
                 backend: str = "zotero"):
        self.items = items
        self.children = children
        self.fulltexts = fulltexts or {}
        self.page_texts = page_texts or {}
        self.pdf_paths = pdf_paths or {}
        self.library_backend = backend
        self.base_url = "http://fake-zotero.invalid/api"

    def get_item(self, key: str) -> Optional[Dict[str, Any]]:
        return self.items.get(key)

    def get_children(self, key: str) -> List[Dict[str, Any]]:
        return self.children.get(key, [])

    def item_fulltext(self, attachment_key: str) -> Optional[Dict[str, Any]]:
        return self.fulltexts.get(attachment_key)

    def resolve_attachment_path(self, attachment: Dict[str, Any]) -> Optional[str]:
        key = attachment.get("key") or (attachment.get("data") or {}).get("key")
        return self.pdf_paths.get(key)

    def page_texts_for(self, attachment_key: str,
                       pdf_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return self.page_texts.get(attachment_key)


def make_full_client(**overrides: Any) -> FakeClient:
    items = {"ITEM1": bib_item("ITEM1")}
    children = {"ITEM1": [
        note_child("NOTE1", "ITEM1", "<p>Key note: uses a reversible kernel.</p>"),
        pdf_child("ATT1", "ITEM1"),
    ]}
    kwargs: Dict[str, Any] = {
        "items": items, "children": children,
        "page_texts": {"ATT1": FULL_PAGES},
        "pdf_paths": {"ATT1": os.path.join(tempfile.gettempdir(), "fake-DDCO.pdf")},
    }
    kwargs.update(overrides)
    return FakeClient(**kwargs)


# ---------------------------------------------------------------------------
# 真实 PDF 生成（pypdf 可解析的最小 PDF，不依赖 reportlab）
# ---------------------------------------------------------------------------


def write_text_pdf(path: str, pages_text: List[str]) -> None:
    """写出一个含可抽取文本的多页 PDF（仅标准库 + pypdf 可读）。"""
    out = bytearray(b"%PDF-1.4\n")
    offsets: Dict[int, int] = {}
    sequences: List[Any] = []
    next_id = 4
    for text in pages_text:
        content = "BT /F1 11 Tf 50 750 Td 14 TL\n"
        for line in text.splitlines():
            escaped = (line.replace("\\", r"\\").replace("(", r"\(")
                       .replace(")", r"\)"))
            content += f"({escaped}) Tj T*\n"
        content += "ET"
        sequences.append((next_id, next_id + 1, content))
        next_id += 2

    def add(obj_id: int, body: bytes) -> None:
        offsets[obj_id] = len(out)
        out.extend(f"{obj_id} 0 obj\n".encode())
        out.extend(body)
        out.extend(b"\nendobj\n")

    add(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{page_id} 0 R" for _c, page_id, _t in sequences)
    add(2, f"<< /Type /Pages /Count {len(sequences)} /Kids [{kids}] >>".encode())
    add(3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for content_id, page_id, text in sequences:
        data = text.encode("latin-1")
        add(content_id, f"<< /Length {len(data)} >>\nstream\n".encode()
            + data + b"\nendstream")
        add(page_id,
            (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
             f"/Resources << /Font << /F1 3 0 R >> >> "
             f"/Contents {content_id} 0 R >>").encode())

    max_id = max(offsets)
    xref_offset = len(out)
    out.extend(f"xref\n0 {max_id + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for obj_id in range(1, max_id + 1):
        out.extend(f"{offsets[obj_id]:010d} 00000 n \n".encode())
    out.extend((f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_offset}\n%%EOF\n").encode())
    Path(path).write_bytes(bytes(out))


# ---------------------------------------------------------------------------
# 1. overview
# ---------------------------------------------------------------------------


class OverviewTests(unittest.TestCase):
    def test_overview_is_abstract_only_even_with_pdf(self) -> None:
        """有 PDF ≠ 深读过；overview 只到 abstract_only。"""
        result = dr.deep_read(make_full_client(), "ITEM1", mode="overview")
        self.assertEqual(result["verification"], "abstract_only")
        self.assertEqual(result["detail"]["abstract"], ABSTRACT)
        self.assertTrue(result["availability"]["has_pdf"])
        # overview 不抽取 PDF。
        self.assertIsNone(result["availability"]["page_extraction_available"])
        self.assertTrue(any("有 PDF" in w for w in result["warnings"]))

    def test_overview_metadata_only_without_abstract(self) -> None:
        client = FakeClient(
            items={"ITEM2": bib_item("ITEM2", abstract=None)},
            children={"ITEM2": []})
        result = dr.deep_read(client, "ITEM2", mode="overview")
        self.assertEqual(result["verification"], "metadata_only")
        self.assertFalse(result["availability"]["has_abstract"])

    def test_missing_item_reports_insufficient_evidence(self) -> None:
        result = dr.deep_read(make_full_client(), "NOPE", mode="overview")
        self.assertEqual(result["verification"], "insufficient_evidence")
        self.assertTrue(result["warnings"])


# ---------------------------------------------------------------------------
# 2. section
# ---------------------------------------------------------------------------


class SectionTests(unittest.TestCase):
    def test_method_section_found_with_correct_page(self) -> None:
        result = dr.deep_read(make_full_client(), "ITEM1", mode="section",
                              sections=["method"])
        self.assertEqual(result["verification"], "page_verified")
        method = result["sections"]["method"]
        self.assertTrue(method["found"])
        self.assertEqual(method["page"], 2)
        self.assertEqual(method["source"], "pdf_page")
        self.assertIn("discrete diffusion sampler", method["text"])

    def test_all_known_sections_located(self) -> None:
        result = dr.deep_read(make_full_client(), "ITEM1", mode="section",
                              sections=list(dr.SECTIONS))
        expected_pages = {"introduction": 1, "method": 2,
                          "experiments": 3, "limitations": 4}
        for name, page in expected_pages.items():
            with self.subTest(section=name):
                self.assertTrue(result["sections"][name]["found"])
                self.assertEqual(result["sections"][name]["page"], page)

    def test_page_filter_excludes_other_pages(self) -> None:
        result = dr.deep_read(make_full_client(), "ITEM1", mode="section",
                              sections=["method", "limitations"], pages=[1, 2])
        self.assertTrue(result["sections"]["method"]["found"])
        self.assertFalse(result["sections"]["limitations"]["found"])

    def test_unknown_section_is_reported(self) -> None:
        result = dr.deep_read(make_full_client(), "ITEM1", mode="section",
                              sections=["method", "bogus"])
        self.assertEqual(result["detail"]["unknown_sections"], ["bogus"])

    def test_section_anchors_respect_page_discipline(self) -> None:
        result = dr.deep_read(make_full_client(), "ITEM1", mode="section",
                              sections=["method"])
        self.assertTrue(result["anchors"])
        for anchor in result["anchors"]:
            if anchor["verification"] != "page_verified":
                self.assertIsNone(anchor["page"])


# ---------------------------------------------------------------------------
# 3-5. evidence
# ---------------------------------------------------------------------------


class EvidenceTests(unittest.TestCase):
    def test_finds_assumption_with_page_and_quote(self) -> None:
        result = dr.deep_read(
            make_full_client(), "ITEM1", mode="evidence",
            question="What assumption does the method make about the noise process?")
        self.assertEqual(result["verification"], "page_verified")
        self.assertTrue(result["detail"]["matched"])
        quote = result["evidence"][0]["quote"]
        self.assertIn("We assume the noise process is independent", quote)
        self.assertEqual(result["evidence"][0]["page"], 2)
        self.assertEqual(result["evidence"][0]["section"], "method")
        self.assertEqual(result["anchors"][0]["page"], 2)
        self.assertEqual(result["anchors"][0]["verification"], "page_verified")

    def test_finds_metric_with_correct_page(self) -> None:
        result = dr.deep_read(
            make_full_client(), "ITEM1", mode="evidence",
            question="What evaluation metric is used to measure accuracy on the benchmark?")
        self.assertEqual(result["verification"], "page_verified")
        quote = result["evidence"][0]["quote"]
        self.assertIn("accuracy and optimality gap", quote)
        self.assertEqual(result["evidence"][0]["page"], 3)

    def test_finds_limitation_with_correct_page(self) -> None:
        result = dr.deep_read(
            make_full_client(), "ITEM1", mode="evidence",
            question="What is the main limitation of the approach?")
        self.assertEqual(result["verification"], "page_verified")
        quote = result["evidence"][0]["quote"]
        self.assertIn("limitation of our approach", quote)
        self.assertEqual(result["evidence"][0]["page"], 4)

    def test_separates_supporting_from_irrelevant(self) -> None:
        result = dr.deep_read(
            make_full_client(), "ITEM1", mode="evidence",
            question="What evaluation metric is used to measure accuracy on the benchmark?")
        supporting = [item["quote"] for item in result["evidence"]]
        irrelevant = [item["quote"] for item in result["irrelevant"]]
        self.assertTrue(any("optimality gap" in q for q in supporting))
        self.assertTrue(any(DISTRACTOR_QUOTE in q for q in irrelevant))
        self.assertFalse(any(DISTRACTOR_QUOTE in q for q in supporting))

    def test_refuses_claim_absent_from_text(self) -> None:
        result = dr.deep_read(
            make_full_client(), "ITEM1", mode="evidence",
            question="Does the method use quantum annealing?")
        self.assertFalse(result["detail"]["matched"])
        self.assertEqual(result["detail"]["assessment"], "not_in_text")
        self.assertEqual(result["detail"]["conclusion"],
                         "claim_not_supported_by_source")
        self.assertEqual(result["evidence"], [])
        self.assertEqual(result["anchors"], [])
        self.assertTrue(any("拒绝" in w for w in result["warnings"]))

    def test_evidence_falls_back_to_abstract_when_no_fulltext(self) -> None:
        items = {"ITEM3": bib_item("ITEM3")}
        client = FakeClient(items=items, children={"ITEM3": []})
        result = dr.deep_read(client, "ITEM3", mode="evidence",
                              question="discrete diffusion method combinatorial optimization")
        self.assertEqual(result["verification"], "abstract_only")
        self.assertEqual(result["evidence"][0]["page"], None)


# ---------------------------------------------------------------------------
# 6. 不完整 PDF
# ---------------------------------------------------------------------------


class IncompletePdfTests(unittest.TestCase):
    def test_partial_pdf_is_insufficient_evidence_with_coverage(self) -> None:
        client = make_full_client(page_texts={"ATT1": PARTIAL_PAGES})
        result = dr.deep_read(client, "ITEM1", mode="section",
                              sections=["method", "limitations"])
        self.assertEqual(result["verification"], "insufficient_evidence")
        self.assertIs(result["availability"]["pdf_complete"], False)
        self.assertEqual(result["availability"]["page_coverage"], "1-2 / 4")
        # 已覆盖页可用，未覆盖页**不编造**。
        self.assertTrue(result["sections"]["method"]["found"])
        self.assertEqual(result["sections"]["method"]["page"], 2)
        self.assertFalse(result["sections"]["limitations"]["found"])
        self.assertIsNone(result["sections"]["limitations"]["text"])
        self.assertTrue(any("覆盖范围" in w for w in result["warnings"]))

    def test_scanned_pdf_without_text_layer_is_insufficient(self) -> None:
        scanned = _pages_payload(
            [_page(1, "", quality="empty"), _page(2, "", quality="empty")], total=2,
            sha256="sha-scan")
        client = make_full_client(page_texts={"ATT1": scanned})
        result = dr.deep_read(client, "ITEM1", mode="section", sections=["method"])
        self.assertEqual(result["verification"], "insufficient_evidence")
        self.assertEqual(result["availability"]["page_coverage"],
                         "0 页（疑为扫描件或无文本层）")

    def test_pdf_present_but_extractor_unavailable_degrades(self) -> None:
        """页级抽取不可用 → 如实降级，不崩溃、不冒充 page_verified。"""
        items = {"ITEM4": bib_item("ITEM4")}
        children = {"ITEM4": [pdf_child("ATT4", "ITEM4")]}
        client = FakeClient(
            items=items, children=children, page_texts={},
            pdf_paths={"ATT4": "/nonexistent/path/definitely-missing.pdf"})
        result = dr.deep_read(client, "ITEM4", mode="section",
                              sections=["method", "abstract"])
        self.assertNotEqual(result["verification"], "page_verified")
        self.assertIs(result["availability"]["page_extraction_available"], False)
        self.assertTrue(any("页级抽取不可用" in w for w in result["warnings"]))
        self.assertTrue(result["sections"]["abstract"]["found"])
        self.assertEqual(result["sections"]["abstract"]["source"], "abstract")


# ---------------------------------------------------------------------------
# 7-8. 等级升级规则与锚点纪律
# ---------------------------------------------------------------------------


class VerificationDisciplineTests(unittest.TestCase):
    def test_index_hit_is_indexed_fulltext_and_never_page_verified(self) -> None:
        items = {"ITEM5": bib_item("ITEM5")}
        children = {"ITEM5": [pdf_child("ATT5", "ITEM5")]}
        client = FakeClient(
            items=items, children=children,
            fulltexts={"ATT5": {"content": INDEX_CONTENT, "indexedPages": 3,
                                "totalPages": 3}},
            page_texts={}, pdf_paths={})  # 无页级抽取 → 只能走索引
        for mode, kwargs in (
            ("evidence", {"question": "What assumption is made about the noise process?"}),
            ("section", {"sections": ["method"]}),
        ):
            with self.subTest(mode=mode):
                result = dr.deep_read(client, "ITEM5", mode=mode, **kwargs)
                self.assertEqual(result["verification"], "indexed_fulltext")
                for anchor in result["anchors"]:
                    self.assertEqual(anchor["verification"], "indexed_fulltext")
                    self.assertIsNone(anchor["page"])
        evidence = dr.deep_read(
            client, "ITEM5", mode="evidence",
            question="What assumption is made about the noise process?")
        self.assertTrue(evidence["detail"]["matched"])
        self.assertIsNone(evidence["evidence"][0]["page"])
        self.assertTrue(any("indexed_fulltext" in w for w in evidence["warnings"]))

    def test_anchor_builder_rejects_page_on_indexed(self) -> None:
        with self.assertRaises(ValueError):
            dr.make_evidence_anchor(verification="indexed_fulltext", page=7,
                                    quote="x", zotero_item_key="ITEM1")
        with self.assertRaises(ValueError):
            dr.make_evidence_anchor(verification="abstract_only", page=1)
        with self.assertRaises(ValueError):
            dr.make_evidence_anchor(verification="pdf_text_verified", page=2)

    def test_anchor_builder_requires_page_and_quote_for_page_verified(self) -> None:
        with self.assertRaises(ValueError):
            dr.make_evidence_anchor(verification="page_verified", page=None,
                                    quote="x")
        with self.assertRaises(ValueError):
            dr.make_evidence_anchor(verification="page_verified", page=2, quote="")

    def test_anchor_shape_and_stale_on_fingerprint_mismatch(self) -> None:
        anchor = dr.make_evidence_anchor(
            library_backend="zotero", zotero_item_key="ITEM1", attachment_key="ATT1",
            doi="10.1234/x", pdf_sha256="sha-new", page=2, section="method",
            quote=METHOD_QUOTE, claim="method is a diffusion sampler",
            assessment="supported", verification="page_verified",
            fingerprint_expected="sha-old")
        self.assertEqual(set(anchor), {
            "library_backend", "zotero_item_key", "attachment_key", "doi",
            "pdf_sha256", "page", "section", "quote", "claim", "assessment",
            "verification", "stale", "fingerprint_expected"})
        self.assertTrue(anchor["stale"])
        self.assertIn("needs-review", anchor["assessment"])

    def test_anchor_not_stale_when_fingerprint_matches(self) -> None:
        anchor = dr.make_evidence_anchor(
            verification="page_verified", page=2, quote=METHOD_QUOTE,
            pdf_sha256="sha-same", fingerprint_expected="sha-same")
        self.assertFalse(anchor["stale"])

    def test_result_pages_are_none_unless_page_verified(self) -> None:
        result = dr.deep_read(make_full_client(), "ITEM1", mode="section",
                              sections=list(dr.SECTIONS))
        for anchor in result["anchors"]:
            if anchor["verification"] != "page_verified":
                self.assertIsNone(anchor["page"])
            else:
                self.assertIsNotNone(anchor["page"])


# ---------------------------------------------------------------------------
# 9. 真实 PDF（内建 pypdf 回退）
# ---------------------------------------------------------------------------


class RealPdfTests(unittest.TestCase):
    def test_real_pdf_end_to_end_page_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = os.path.join(tmp, "paper.pdf")
            write_text_pdf(pdf_path, [PAGE_1, PAGE_2, PAGE_3, PAGE_4])

            items = {"ITEMP": bib_item("ITEMP")}
            children = {"ITEMP": [pdf_child("ATTP", "ITEMP")]}

            class PdfClient(FakeClient):
                def page_texts_for(self, attachment_key: str,
                                   pdf_path_arg: Optional[str] = None
                                   ) -> Optional[Dict[str, Any]]:
                    # 明确注入内建 pypdf 回退，测试不依赖 zotero_fulltext。
                    return dr._extract_pages_pypdf(pdf_path)

            client = PdfClient(items=items, children=children,
                               pdf_paths={"ATTP": pdf_path})
            result = dr.deep_read(client, "ITEMP", mode="section",
                                  sections=["method", "limitations"])
            self.assertEqual(result["verification"], "page_verified")
            self.assertIn("discrete diffusion sampler",
                          result["sections"]["method"]["text"])
            self.assertEqual(result["sections"]["method"]["page"], 2)
            self.assertIn("limitation of our approach",
                          result["sections"]["limitations"]["text"])
            self.assertEqual(result["sections"]["limitations"]["page"], 4)
            self.assertTrue(result["availability"]["pdf_sha256"])


# ---------------------------------------------------------------------------
# 10. compare_papers
# ---------------------------------------------------------------------------


class CompareTests(unittest.TestCase):
    def _client(self) -> FakeClient:
        items = {
            "ITEM1": bib_item("ITEM1", title="Paper One",
                              doi="10.1234/one"),
            "ITEM2": bib_item("ITEM2", title="Paper Two",
                              doi="10.1234/two"),
        }
        children = {
            "ITEM1": [pdf_child("ATT1", "ITEM1")],
            "ITEM2": [pdf_child("ATT2", "ITEM2")],
        }
        page_two = _pages_payload([
            _page(1, PAGE_1),
            _page(2, PAGE_2.replace("reversible", "symmetric")),
            _page(3, PAGE_3), _page(4, PAGE_4)], total=4, sha256="sha-two")
        return FakeClient(items=items, children=children,
                          page_texts={"ATT1": FULL_PAGES, "ATT2": page_two},
                          pdf_paths={"ATT1": "/tmp/a.pdf", "ATT2": "/tmp/b.pdf"})

    def test_compare_method_across_two_papers(self) -> None:
        result = dr.compare_papers(self._client(), ["ITEM1", "ITEM2"], aspect="method")
        self.assertEqual(result["mode"], "compare")
        self.assertEqual(result["aspect"], "method")
        self.assertEqual(result["verification"], "page_verified")
        self.assertEqual(len(result["papers"]), 2)
        for entry in result["papers"]:
            self.assertTrue(entry["found"])
            self.assertEqual(entry["page"], 2)
            self.assertIn("discrete diffusion sampler", entry["text"])
        self.assertEqual(result["differences"], [])  # 不编造差异

    def test_compare_weakest_level_wins(self) -> None:
        client = self._client()
        client.page_texts["ATT2"] = PARTIAL_PAGES
        result = dr.compare_papers(client, ["ITEM1", "ITEM2"], aspect="method")
        self.assertEqual(result["verification"], "insufficient_evidence")

    def test_compare_rejects_unknown_aspect(self) -> None:
        with self.assertRaises(ValueError):
            dr.compare_papers(self._client(), ["ITEM1"], aspect="banana")


# ---------------------------------------------------------------------------
# 11. novelty（E）：复用既有词表，不裁决
# ---------------------------------------------------------------------------


class NoveltyTests(unittest.TestCase):
    def test_novelty_mode_reuses_existing_vocabulary_without_judging(self) -> None:
        result = dr.deep_read(make_full_client(), "ITEM1", mode="novelty")
        detail = result["detail"]
        self.assertFalse(detail["judgement_performed"])
        self.assertEqual(detail["verdict"], "uncertain")
        self.assertEqual(detail["near_neighbor_verdict"], "uncertain")
        self.assertEqual(detail["claimed_novelty_level"], "none")
        vocab = detail["vocabulary"]
        self.assertIn("component-delta", vocab["verdict_values"])
        self.assertIn("structural-delta-strong",
                      vocab["near_neighbor_verdict_values"])
        self.assertIn("Observed", vocab["epistemic_status_values"])
        # 抽取的 facet 引文必须能指到原文。
        assumption = detail["facets"]["assumptions"]
        self.assertIn("discrete diffusion", assumption["quote"] or "")
        self.assertEqual(assumption["provenance"], "EXPLICIT")

    def test_deep_read_rejects_unknown_mode(self) -> None:
        with self.assertRaises(ValueError):
            dr.deep_read(make_full_client(), "ITEM1", mode="banana")


if __name__ == "__main__":
    unittest.main(verbosity=2)
