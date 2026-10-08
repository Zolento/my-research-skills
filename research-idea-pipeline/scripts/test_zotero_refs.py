#!/usr/bin/env python3
"""test_zotero_refs.py — `zotero_refs.py` 的离线测试（stdlib unittest，**不联网**）

运行：
    python -m unittest scripts.test_zotero_refs -v
    python scripts/test_zotero_refs.py

设计原则
--------
**全部离线、不依赖正在运行的 Zotero。** 用 `unittest.mock` 替换
`zotero_client.probe` / `zotero_client.fetch_items`，storage 目录用临时目录伪造。

覆盖点
------
1. 元数据模式：sidecar 文件名 = 确定且文件系统安全的 paper_id；§7.1 必填字段齐全；
   未链 PDF 时**不写** file/size_bytes/sha256，且**不碰 index.json**
2. 幂等：第二次运行 0 新建 / 0 更新，逐字节相同
3. `--dry-run`：一个文件都不写
4. `--link-pdfs`：软链指向真实文件，`refs_index.check_index` 无问题
5. ★ 关键：PDF 实体缺失时**绝不**产生索引条目（否则 `--check` 必挂）
6. `--check`：缺 sidecar / 内容漂移 / 孤儿 sidecar 都返回退出码 3
7. Zotero 不可达 / 拉取失败：非零退出码且不抛异常（无 traceback）
8. 导出的 sidecar 能被 `literature_search.search_local` 检索到
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import literature_search as ls  # noqa: E402
import refs_index as ri  # noqa: E402
import zotero_client as zc  # noqa: E402
import zotero_refs as zr  # noqa: E402


# ---------------------------------------------------------------------------
# 工具：构造 Zotero 形状的 fixture 条目
# ---------------------------------------------------------------------------

def bib_item(
    key: str,
    *,
    title: str = "Discrete Diffusion for Combinatorial Optimization",
    doi: Optional[str] = None,
    arxiv: Optional[str] = None,
    date: str = "2024-03-01",
    venue: str = "NeurIPS",
    abstract: str = "A diffusion model for combinatorial optimization.",
    keywords: Optional[List[str]] = None,
    date_added: str = "2025-01-02T03:04:05Z",
    item_type: str = "journalArticle",
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "itemType": item_type,
        "title": title,
        "creators": [
            {"firstName": "Ada", "lastName": "Smith", "creatorType": "author"},
            {"name": "Some Consortium", "creatorType": "author"},
        ],
        "date": date,
        "dateAdded": date_added,
        "abstractNote": abstract,
        "publicationTitle": venue,
        "url": f"https://example.org/{key}",
        "DOI": doi,
        "tags": [{"tag": t} for t in (keywords or ["diffusion", "optimization"])],
    }
    if arxiv:
        data["extra"] = f"arXiv:{arxiv}"
    return {"key": key, "version": 0, "data": data}


def pdf_att(key: str, parent: str, filename: str) -> Dict[str, Any]:
    """模拟 Local API 的 imported_file 附件：只有 filename，没有 path。"""
    return {
        "key": key,
        "version": 0,
        "data": {
            "itemType": "attachment",
            "contentType": "application/pdf",
            "parentItem": parent,
            "linkMode": "imported_file",
            "filename": filename,
        },
    }


class _Env:
    """临时 refs 目录 + 伪造的 Zotero storage。"""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.refs = self.root / "refs"
        self.storage = self.root / "storage"
        self.storage.mkdir(parents=True)

    def add_pdf(self, att_key: str, filename: str, body: bytes = b"%PDF-1.4 fake\n") -> Path:
        target = self.storage / att_key / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        return target

    def cleanup(self) -> None:
        self._tmp.cleanup()


@contextlib.contextmanager
def zotero(items: List[Dict[str, Any]], *, reachable: bool = True):
    """替换 zotero_client 的两个入口，保证测试不发任何 HTTP。"""
    with mock.patch.object(zr.zc, "probe", return_value=("FAKE-SERVER" if reachable else None)), \
            mock.patch.object(zr.zc, "fetch_items", return_value=list(items)):
        yield


def run_cli(env: _Env, *argv: str) -> Dict[str, Any]:
    """跑 main()，吞掉日志，返回 {code, stderr, stdout, json}。"""
    err, out = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        code = zr.main(["--refs-dir", str(env.refs), "--zotero-storage", str(env.storage), *argv])
    payload = None
    text = out.getvalue().strip()
    if text.startswith("{"):
        payload = json.loads(text)
    return {"code": code, "stderr": err.getvalue(), "stdout": out.getvalue(), "json": payload}


def read_sidecar(env: _Env, paper_id: str) -> Dict[str, Any]:
    path = env.refs / "papers" / f"{paper_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 单元：paper_id 归一
# ---------------------------------------------------------------------------

class TestSafePaperId(unittest.TestCase):
    def test_doi_slash_is_replaced(self) -> None:
        self.assertEqual(zr.safe_paper_id("10.1000/xyz.1"), "10.1000_xyz.1")

    def test_unsafe_chars_collapse(self) -> None:
        self.assertEqual(zr.safe_paper_id("a b/c?d"), "a_b_c_d")

    def test_rejects_empty_and_dots(self) -> None:
        for raw in (None, "", "   ", "..", "./"):
            self.assertIsNone(zr.safe_paper_id(raw), msg=repr(raw))

    def test_deterministic_and_length_capped(self) -> None:
        long_id = "x" * 500
        once, twice = zr.safe_paper_id(long_id), zr.safe_paper_id(long_id)
        self.assertEqual(once, twice)
        self.assertLessEqual(len(once), zr._MAX_PAPER_ID)

    def test_arxiv_preferred_over_key(self) -> None:
        item = bib_item("ABCD1234", arxiv="2401.00123")
        self.assertEqual(zr.safe_paper_id(zc.item_to_sidecar(item)["paper_id"]), "2401.00123")


# ---------------------------------------------------------------------------
# 元数据模式
# ---------------------------------------------------------------------------

class TestMetadataExport(unittest.TestCase):
    def setUp(self) -> None:
        self.env = _Env()
        self.items = [
            bib_item("AAAA1111", arxiv="2401.00123"),
            bib_item("BBBB2222", doi="10.1000/xyz.1", title="A DOI Only Paper"),
        ]

    def tearDown(self) -> None:
        self.env.cleanup()

    def test_creates_one_sidecar_per_item(self) -> None:
        with zotero(self.items):
            result = run_cli(self.env, "--json")
        self.assertEqual(result["code"], zr.EXIT_OK)
        self.assertEqual(result["json"]["created"], 2)
        self.assertTrue((self.env.refs / "papers" / "2401.00123.json").is_file())
        # DOI 里的 "/" 必须被替换，否则会当成子目录
        self.assertTrue((self.env.refs / "papers" / "10.1000_xyz.1.json").is_file())

    def test_required_fields_present(self) -> None:
        with zotero(self.items):
            run_cli(self.env)
        sidecar = read_sidecar(self.env, "2401.00123")
        for field in ("paper_id", "title", "authors", "year", "venue", "arxiv_id",
                      "doi", "url", "abstract", "keywords", "added_at", "source",
                      "metadata_from", "needs_verification"):
            self.assertIn(field, sidecar, msg=field)
        self.assertEqual(sidecar["paper_id"], "2401.00123")
        self.assertEqual(sidecar["year"], 2024)
        self.assertEqual(sidecar["authors"], ["Ada Smith", "Some Consortium"])
        self.assertEqual(sidecar["source"], "zotero")
        self.assertEqual(sidecar["added_at"], "2025-01-02")
        self.assertFalse(sidecar["needs_verification"])

    def test_pdf_only_fields_absent_without_link(self) -> None:
        with zotero(self.items):
            run_cli(self.env)
        sidecar = read_sidecar(self.env, "2401.00123")
        for field in zr.PDF_ONLY_FIELDS:
            self.assertNotIn(field, sidecar, msg=field)

    def test_does_not_touch_index(self) -> None:
        """默认模式不写 index：没有 PDF 就没有索引义务。"""
        with zotero(self.items):
            run_cli(self.env)
        self.assertFalse((self.env.refs / "index.json").exists())

    def test_idempotent(self) -> None:
        with zotero(self.items):
            first = run_cli(self.env, "--json")
            path = self.env.refs / "papers" / "2401.00123.json"
            before = path.read_bytes()
            second = run_cli(self.env, "--json")
        self.assertEqual(first["json"]["created"], 2)
        self.assertEqual(second["json"]["created"], 0)
        self.assertEqual(second["json"]["updated"], 0)
        self.assertEqual(second["json"]["unchanged"], 2)
        self.assertEqual(before, path.read_bytes())

    def test_dry_run_writes_nothing(self) -> None:
        with zotero(self.items):
            result = run_cli(self.env, "--dry-run")
        self.assertEqual(result["code"], zr.EXIT_OK)
        self.assertFalse(self.env.refs.exists())

    def test_limit(self) -> None:
        with zotero(self.items):
            result = run_cli(self.env, "--limit", "1", "--json")
        self.assertEqual(result["json"]["considered"], 1)
        self.assertEqual(result["json"]["created"], 1)
        self.assertFalse((self.env.refs / "papers" / "10.1000_xyz.1.json").exists())

    def test_needs_verification_when_year_missing(self) -> None:
        items = [bib_item("CCCC3333", date="", title="Undated")]
        with zotero(items):
            run_cli(self.env)
        sidecar = read_sidecar(self.env, "CCCC3333")
        self.assertIsNone(sidecar["year"])
        self.assertTrue(sidecar["needs_verification"])

    def test_exported_sidecar_is_searchable(self) -> None:
        """导出格式必须真的能被 search_local 命中（本脚本存在的理由）。"""
        with zotero(self.items):
            run_cli(self.env)
        entries = ls._read_paper_entries(self.env.refs / "papers")
        self.assertEqual(len(entries), 2)
        hits = ls.search_local("combinatorial optimization", self.env.refs, entries=entries)
        self.assertTrue(hits, "search_local 应命中导出的 sidecar")
        self.assertEqual(hits[0]["source"], "local")


# ---------------------------------------------------------------------------
# --link-pdfs
# ---------------------------------------------------------------------------

class TestLinkPdfs(unittest.TestCase):
    def setUp(self) -> None:
        self.env = _Env()
        self.pdf = self.env.add_pdf("ATT00001", "paper one.pdf")
        self.items = [
            bib_item("AAAA1111", arxiv="2401.00123"),
            pdf_att("ATT00001", "AAAA1111", "paper one.pdf"),
        ]

    def tearDown(self) -> None:
        self.env.cleanup()

    def test_symlink_and_index(self) -> None:
        with zotero(self.items):
            result = run_cli(self.env, "--link-pdfs", "--json")
        self.assertEqual(result["code"], zr.EXIT_OK)

        link = self.env.refs / "papers" / "2401.00123.pdf"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), self.pdf.resolve())
        # ★ 绝不复制：软链指向 6.3 GB 的原始库
        self.assertEqual(result["json"]["linked"], 1)

        index = json.loads((self.env.refs / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(ri.check_index(self.env.refs, index), [])
        self.assertEqual(index["count"], 1)

        sidecar = read_sidecar(self.env, "2401.00123")
        self.assertEqual(sidecar["file"], "papers/2401.00123.pdf")
        self.assertEqual(sidecar["size_bytes"], self.pdf.stat().st_size)
        self.assertEqual(len(sidecar["sha256"]), 64)

    def test_missing_pdf_never_gets_index_entry(self) -> None:
        """★ 关键约束：实体文件不存在时，既不建软链，也不写索引条目。"""
        items = [bib_item("DDDD4444", arxiv="2402.00222"),
                 pdf_att("ATT99999", "DDDD4444", "ghost.pdf")]
        with zotero(items):
            result = run_cli(self.env, "--link-pdfs", "--json")
        self.assertEqual(result["code"], zr.EXIT_OK)
        self.assertEqual(result["json"]["without_pdf"], 1)
        self.assertFalse((self.env.refs / "papers" / "2402.00222.pdf").is_symlink())
        self.assertFalse((self.env.refs / "papers" / "2402.00222.json").exists())
        index = json.loads((self.env.refs / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["count"], 0)
        self.assertEqual(ri.check_index(self.env.refs, index), [])
        self.assertEqual(ri.main(["--refs-dir", str(self.env.refs), "--check"]), ri.EXIT_OK)

    def test_include_without_pdf_writes_metadata_but_no_index(self) -> None:
        items = [bib_item("DDDD4444", arxiv="2402.00222")]
        with zotero(items):
            run_cli(self.env, "--link-pdfs", "--include-without-pdf")
        self.assertTrue((self.env.refs / "papers" / "2402.00222.json").is_file())
        self.assertFalse((self.env.refs / "papers" / "2402.00222.pdf").exists())
        index = json.loads((self.env.refs / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["count"], 0)
        self.assertEqual(ri.check_index(self.env.refs, index), [])

    def test_link_is_idempotent(self) -> None:
        with zotero(self.items):
            run_cli(self.env, "--link-pdfs")
            before = (self.env.refs / "papers" / "2401.00123.json").read_bytes()
            result = run_cli(self.env, "--link-pdfs", "--json")
        self.assertEqual(result["json"]["created"], 0)
        self.assertEqual(result["json"]["updated"], 0)
        self.assertEqual(before, (self.env.refs / "papers" / "2401.00123.json").read_bytes())
        self.assertTrue((self.env.refs / "papers" / "2401.00123.pdf").is_symlink())

    def test_dry_run_links_nothing(self) -> None:
        with zotero(self.items):
            run_cli(self.env, "--link-pdfs", "--dry-run")
        self.assertFalse(self.env.refs.exists())


# ---------------------------------------------------------------------------
# --check
# ---------------------------------------------------------------------------

class TestCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.env = _Env()
        self.items = [bib_item("AAAA1111", arxiv="2401.00123")]

    def tearDown(self) -> None:
        self.env.cleanup()

    def test_missing_sidecar_is_stale(self) -> None:
        with zotero(self.items):
            result = run_cli(self.env, "--check", "--json")
        self.assertEqual(result["code"], zr.EXIT_STALE)
        self.assertTrue(any("缺少 sidecar" in p for p in result["json"]["drift"]))

    def test_clean_export_passes_check(self) -> None:
        with zotero(self.items):
            run_cli(self.env)
            result = run_cli(self.env, "--check", "--json")
        self.assertEqual(result["code"], zr.EXIT_OK)
        self.assertEqual(result["json"]["drift"], [])

    def test_modified_sidecar_is_stale(self) -> None:
        with zotero(self.items):
            run_cli(self.env)
            path = self.env.refs / "papers" / "2401.00123.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["title"] = "被手改过的标题"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result = run_cli(self.env, "--check", "--json")
        self.assertEqual(result["code"], zr.EXIT_STALE)
        self.assertTrue(any("不一致" in p for p in result["json"]["drift"]))

    def test_orphan_sidecar_is_reported(self) -> None:
        with zotero(self.items):
            run_cli(self.env)
            # Zotero 里的条目被删掉 → 本地 sidecar 成为孤儿
            with zotero([bib_item("ZZZZ9999", arxiv="2409.99999")]):
                result = run_cli(self.env, "--check", "--json")
        self.assertEqual(result["code"], zr.EXIT_STALE)
        self.assertTrue(any("孤儿" in p for p in result["json"]["drift"]))

    def test_check_writes_nothing(self) -> None:
        with zotero(self.items):
            run_cli(self.env)
            path = self.env.refs / "papers" / "2401.00123.json"
            before = path.read_bytes()
            run_cli(self.env, "--check")
        self.assertEqual(before, path.read_bytes())


# ---------------------------------------------------------------------------
# 离线 / 容错
# ---------------------------------------------------------------------------

class TestUnreachable(unittest.TestCase):
    def setUp(self) -> None:
        self.env = _Env()

    def tearDown(self) -> None:
        self.env.cleanup()

    def test_probe_failure_returns_env_code_without_traceback(self) -> None:
        with zotero([], reachable=False):
            result = run_cli(self.env)  # 不抛异常 = 无 traceback
        self.assertEqual(result["code"], zr.EXIT_ENV)
        self.assertIn("不可达", result["stderr"])
        self.assertFalse(self.env.refs.exists())

    def test_fetch_failure_returns_env_code(self) -> None:
        with mock.patch.object(zr.zc, "probe", return_value="FAKE-SERVER"), \
                mock.patch.object(zr.zc, "fetch_items",
                                  side_effect=zc.ZoteroUnavailable("boom")):
            result = run_cli(self.env)
        self.assertEqual(result["code"], zr.EXIT_ENV)
        self.assertIn("拉取 Zotero 条目失败", result["stderr"])

    def test_unreachable_json_summary(self) -> None:
        with zotero([], reachable=False):
            result = run_cli(self.env, "--json")
        self.assertEqual(result["json"]["error"], "zotero_unreachable")
        self.assertEqual(result["json"]["exit"], zr.EXIT_ENV)


class TestArgErrors(unittest.TestCase):
    def test_negative_limit_exits_1(self) -> None:
        env = _Env()
        try:
            with zotero([]):
                result = run_cli(env, "--limit", "-1")
            self.assertEqual(result["code"], zr.EXIT_ERROR)
        finally:
            env.cleanup()

    def test_bad_flag_exits_1_not_stale(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            with contextlib.redirect_stderr(io.StringIO()):
                zr.main(["--nope"])
        self.assertEqual(ctx.exception.code, zr.EXIT_ERROR)


if __name__ == "__main__":
    unittest.main(verbosity=2)
