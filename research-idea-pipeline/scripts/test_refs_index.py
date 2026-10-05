#!/usr/bin/env python3
"""test_refs_index.py — refs_index.py 的离线测试（stdlib unittest，**不联网**）

运行：
    python -m unittest discover -s scripts -p "test_*.py" -v
    python scripts/test_refs_index.py

为什么需要它
------------
`--migrate`（B8）是为了让**旧 schema 的既有索引**有迁移路径，而不是只能"重建"。
重建会丢旧字段，所以「保留旧字段」这条必须被测试钉住 —— 否则它只是一句注释。

覆盖点
------
1. `harvest_legacy` 的三种旧形状（平铺列表 / 具名列表 / 以文件名为键的字典）
2. `harvest_legacy` 对垃圾输入返回空
3. `legacy_schema_of`
4. 端到端 `--migrate`：旧字段（title / venue / year）被保留，顶层写 `migrated_from`
5. `--check` 对旧 schema 返回退出码 3，且提示指向 `--migrate`
6. `--migrate` 之后 `--check` 通过
7. 已是当前 schema 时 `--migrate` 不重复迁移
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import refs_index as ri  # noqa: E402


class _TmpRefs:
    """建一个临时 refs 目录，塞进 N 个假 PDF（内容不是真 PDF，走文件名兜底即可）。"""

    def __init__(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.refs = Path(self._dir.name) / "refs"
        self.refs.mkdir(parents=True)

    def add_pdf(self, name: str) -> Path:
        path = self.refs / name
        path.write_bytes(b"%PDF-1.4 dummy\n")
        return path

    def write_index(self, payload: Any) -> None:
        (self.refs / "index.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
        )

    def read_index(self) -> Dict[str, Any]:
        return json.loads((self.refs / "index.json").read_text(encoding="utf-8"))

    def cleanup(self) -> None:
        self._dir.cleanup()


def _run(*argv: str) -> int:
    """跑 main()，吞掉 stderr 日志。"""
    with contextlib.redirect_stderr(io.StringIO()):
        return ri.main(list(argv))


class TestHarvestLegacy(unittest.TestCase):
    def test_flat_list(self) -> None:
        got = ri.harvest_legacy([{"file": "a.pdf", "title": "A"}, {"path": "b.pdf"}])
        self.assertEqual(set(got), {"a.pdf", "b.pdf"})
        self.assertEqual(got["a.pdf"]["title"], "A")

    def test_named_list(self) -> None:
        got = ri.harvest_legacy({"records": [{"filename": "c.pdf", "year": 2024}]})
        self.assertEqual(set(got), {"c.pdf"})
        self.assertEqual(got["c.pdf"]["year"], 2024)

    def test_dict_keyed_by_filename(self) -> None:
        got = ri.harvest_legacy({"d.pdf": {"title": "D"}, "schema": "refs@0"})
        self.assertEqual(set(got), {"d.pdf"})
        self.assertNotIn("schema", got)

    def test_current_schema_also_harvestable(self) -> None:
        got = ri.harvest_legacy({"schema": ri.SCHEMA, "pdfs": [{"file": "e.pdf"}]})
        self.assertEqual(set(got), {"e.pdf"})

    def test_garbage_returns_empty(self) -> None:
        for payload in (None, 42, "nope", {}, [1, 2, 3]):
            self.assertEqual(ri.harvest_legacy(payload), {}, msg=repr(payload))

    def test_leading_dot_slash_stripped(self) -> None:
        got = ri.harvest_legacy([{"file": "./papers/x.pdf"}])
        self.assertEqual(set(got), {"papers/x.pdf"})


class TestLegacySchemaOf(unittest.TestCase):
    def test_reads_schema_key(self) -> None:
        self.assertEqual(ri.legacy_schema_of({"schema": "refs@0"}), "refs@0")

    def test_unknown_but_nonempty(self) -> None:
        self.assertEqual(ri.legacy_schema_of([{"file": "a.pdf"}]), "unknown")

    def test_none_for_empty(self) -> None:
        self.assertIsNone(ri.legacy_schema_of(None))
        self.assertIsNone(ri.legacy_schema_of({}))


class TestMigrateEndToEnd(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = _TmpRefs()
        self.pdf = self.tmp.add_pdf("2401.00123_diffusion_for_co.pdf")
        self.other = self.tmp.add_pdf("another.pdf")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_legacy_fields_are_preserved(self) -> None:
        """★ 这条是 --migrate 存在的理由：重建会丢字段，迁移不能丢。"""
        self.tmp.write_index([{
            "file": "2401.00123_diffusion_for_co.pdf",
            "title": "Legacy Title Kept",
            "authors": ["A B"],
            "year": 2024,
            "venue": "NeurIPS",
            "needs_verification": False,
        }])
        self.assertEqual(_run("--refs-dir", str(self.tmp.refs), "--migrate", "--no-hash"), ri.EXIT_OK)

        index = self.tmp.read_index()
        entry = next(e for e in index["pdfs"] if "00123" in e["file"])
        self.assertEqual(entry["title"], "Legacy Title Kept")
        self.assertEqual(entry["venue"], "NeurIPS")
        self.assertEqual(entry["year"], 2024)
        self.assertEqual(entry["metadata_from"], "legacy")
        # 旧条目自己声明已核实 → 迁移后不应被降级成"待核实"
        self.assertFalse(entry["needs_verification"])

    def test_inherited_metadata_defaults_to_needing_verification(self) -> None:
        self.tmp.write_index([{"file": "another.pdf", "title": "Unknown Provenance"}])
        _run("--refs-dir", str(self.tmp.refs), "--migrate", "--no-hash")
        entry = next(e for e in self.tmp.read_index()["pdfs"] if "another" in e["file"])
        self.assertEqual(entry["title"], "Unknown Provenance")
        self.assertTrue(entry["needs_verification"])

    def test_dict_keyed_legacy_shape(self) -> None:
        self.tmp.write_index({"another.pdf": {"title": "Dict Keyed", "year": 2023},
                              "schema": "refs@0"})
        self.assertEqual(_run("--refs-dir", str(self.tmp.refs), "--migrate", "--no-hash"), ri.EXIT_OK)
        index = self.tmp.read_index()
        self.assertEqual(index["migrated_from"], "refs@0")
        self.assertIn("migrated_at", index)
        entry = next(e for e in index["pdfs"] if "another" in e["file"])
        self.assertEqual(entry["title"], "Dict Keyed")

    def test_check_on_legacy_is_stale_and_points_to_migrate(self) -> None:
        self.tmp.write_index([{"file": "another.pdf", "title": "x"}])
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code = ri.main(["--refs-dir", str(self.tmp.refs), "--check"])
        self.assertEqual(code, ri.EXIT_STALE)
        self.assertIn("pdfs 数组", buf.getvalue())
        self.assertIn("--migrate", buf.getvalue())

    def test_check_passes_after_migrate(self) -> None:
        self.tmp.write_index([{"file": "another.pdf", "title": "x"}])
        _run("--refs-dir", str(self.tmp.refs), "--migrate")  # 带 hash，--check 需要
        self.assertEqual(_run("--refs-dir", str(self.tmp.refs), "--check"), ri.EXIT_OK)

    def test_migrate_is_idempotent_when_already_current(self) -> None:
        _run("--refs-dir", str(self.tmp.refs), "--migrate", "--no-hash")
        before = self.tmp.read_index()
        self.assertEqual(_run("--refs-dir", str(self.tmp.refs), "--migrate", "--no-hash"), ri.EXIT_OK)
        after = self.tmp.read_index()
        self.assertNotIn("migrated_from", after)  # 第二次不再标记迁移
        self.assertEqual(before["count"], after["count"])

    def test_migrate_on_empty_dir_creates_index(self) -> None:
        self.assertEqual(_run("--refs-dir", str(self.tmp.refs), "--migrate", "--no-hash"), ri.EXIT_OK)
        index = self.tmp.read_index()
        self.assertEqual(index["count"], 2)
        self.assertEqual(index["schema"], ri.SCHEMA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
