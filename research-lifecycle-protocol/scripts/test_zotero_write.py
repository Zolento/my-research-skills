#!/usr/bin/env python3
"""`zotero_write.py` 的离线测试（stdlib unittest，**不联网、不写真实库**）。

为什么必须有这些测试
--------------------
写通道是本仓库唯一能改变用户真实文献库的代码。它的安全属性靠约束而不是靠
调用方自觉，所以每条约束都要被测试钉住：

1. 默认只读 —— 未授权时任何写方法都抛 `ZoteroForbidden`，**且不发 HTTP 请求**。
2. Key 不外泄 —— 不出现在 capability 输出与日志里。
3. 实例变化即失效 —— Server ID 变了必须清空 key。
4. 批上限 50 —— 超批必须自动分批。
5. 错误码映射 —— 401/403/412/428 各自对应明确异常，不吞错。

运行：
    python3 -m unittest scripts.test_zotero_write -v
"""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import zotero_client as zc  # noqa: E402
import zotero_write as zw  # noqa: E402


class _FakeResponse:
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


def _http_error(code: int, body: bytes = b"", headers=None) -> urllib.error.HTTPError:
    import email.message
    hdrs = email.message.Message()
    for k, v in (headers or {}).items():
        hdrs[k] = v
    return urllib.error.HTTPError(
        url="http://x", code=code, msg="err", hdrs=hdrs, fp=io.BytesIO(body))


class _Recorder:
    """记录所有出站请求，便于断言"没有发请求"与批次数。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, request, timeout=None):
        self.calls.append({
            "url": getattr(request, "full_url", str(request)),
            "method": getattr(request, "method", "GET"),
            "headers": {k.lower(): v for k, v in (getattr(request, "headers", {}) or {}).items()},
            "data": getattr(request, "data", None),
        })
        item = self.responses.pop(0) if self.responses else _FakeResponse(b"{}")
        if isinstance(item, Exception):
            raise item
        return item


def _client_with_key(key: str = "SECRETKEY") -> zw.WriteClient:
    return zw.WriteClient(key=key)


class DefaultReadOnlyTests(unittest.TestCase):
    """默认只读是本模块最重要的属性。"""

    def test_status_is_ro_without_key(self) -> None:
        with mock.patch.object(zc, "probe", return_value="SID"):
            client = zw.WriteClient()
            self.assertEqual(client.status(), zw.STATUS_RO)
            self.assertFalse(client.capability()["writable"])

    def test_status_is_refs_when_unreachable(self) -> None:
        with mock.patch.object(zc, "probe", return_value=None):
            client = zw.WriteClient()
            self.assertEqual(client.status(), zw.STATUS_REFS)
            self.assertFalse(client.capability()["reachable"])

    def test_status_is_rw_with_key(self) -> None:
        with mock.patch.object(zc, "probe", return_value="SID"):
            self.assertEqual(_client_with_key().status(), zw.STATUS_RW)

    def test_unauthorized_write_raises_and_sends_nothing(self) -> None:
        recorder = _Recorder([_FakeResponse(b"{}")])
        with mock.patch.object(zc.urllib.request, "urlopen", recorder):
            client = zw.WriteClient()
            for call in (
                lambda: client.patch("item", "K", {"title": "x"}),
                lambda: client.post("item", [{"itemType": "note", "note": "n"}]),
                lambda: client.delete("item", "K"),
            ):
                with self.assertRaises(zw.ZoteroForbidden):
                    call()
        self.assertEqual(recorder.calls, [], "未授权时绝不能发出任何写请求")

    def test_require_key_does_not_fall_back_to_refs(self) -> None:
        """Zotero 可读但无写权限时，不得把写入静默改到 refs 后端。"""
        with mock.patch.object(zc, "probe", return_value="SID"):
            client = zw.WriteClient()
            with self.assertRaises(zw.ZoteroForbidden):
                client.patch("item", "K", {})


class SecretHygieneTests(unittest.TestCase):
    def test_key_not_exposed_in_capability(self) -> None:
        with mock.patch.object(zc, "probe", return_value="SID"):
            cap = json.dumps(_client_with_key("SECRETKEY").capability(), ensure_ascii=False)
        self.assertNotIn("SECRETKEY", cap)

    def test_key_not_exposed_in_labels(self) -> None:
        with mock.patch.object(zc, "probe", return_value="SID"):
            client = _client_with_key("SECRETKEY")
            self.assertNotIn("SECRETKEY", str(client.capability()))
            self.assertTrue(client.has_key)


class AuthorizationTests(unittest.TestCase):
    def test_authorize_stores_key_and_remember(self) -> None:
        recorder = _Recorder([_FakeResponse(json.dumps({"key": "NEWKEY", "remember": True}).encode())])
        with mock.patch.object(zc.urllib.request, "urlopen", recorder), \
             mock.patch.object(zc, "probe", return_value="SID"):
            client = zw.WriteClient()
            result = client.authorize("Test App")
        self.assertEqual(result, {"key": "NEWKEY", "remember": True})
        self.assertTrue(client.has_key)
        # 授权请求必须带 Server-ID（否则 428）且不能带 API key
        headers = recorder.calls[0]["headers"]
        self.assertEqual(headers.get("zotero-server-id"), "SID")
        self.assertNotIn("zotero-api-key", headers)

    def test_denied_authorization_raises(self) -> None:
        denied = _http_error(403, b'{"denied": true}')
        recorder = _Recorder([denied])
        with mock.patch.object(zc.urllib.request, "urlopen", recorder), \
             mock.patch.object(zc, "probe", return_value="SID"):
            client = zw.WriteClient()
            with self.assertRaises(zw.ZoteroAuthDenied):
                client.authorize()
        self.assertFalse(client.has_key)

    def test_authorize_429_reports_rate_limit(self) -> None:
        limited = _http_error(429, b"too many", headers={"Retry-After": "60"})
        recorder = _Recorder([limited])
        with mock.patch.object(zc.urllib.request, "urlopen", recorder), \
             mock.patch.object(zc, "probe", return_value="SID"):
            with self.assertRaises(zw.ZoteroWriteError):
                zw.WriteClient().authorize()

    def test_authorize_when_unreachable_raises(self) -> None:
        with mock.patch.object(zc, "probe", return_value=None):
            with self.assertRaises(zw.ZoteroWriteError):
                zw.WriteClient().authorize()


class ServerIdInvalidationTests(unittest.TestCase):
    def test_server_id_change_clears_key(self) -> None:
        client = _client_with_key("SECRETKEY")
        with mock.patch.object(zc, "probe", return_value="SID1"):
            self.assertEqual(client.ensure_server_id(), "SID1")
        self.assertTrue(client.has_key)
        with mock.patch.object(zc, "probe", return_value="SID2"):
            self.assertEqual(client.ensure_server_id(), "SID2")
        self.assertFalse(client.has_key, "Server ID 变化必须清空 key")

    def test_connection_loss_clears_key(self) -> None:
        client = _client_with_key("SECRETKEY")
        with mock.patch.object(zc, "probe", return_value="SID1"):
            client.ensure_server_id()
        with mock.patch.object(zc, "probe", return_value=None):
            self.assertIsNone(client.ensure_server_id())
        self.assertFalse(client.has_key)

    def test_invalidate_resets_all(self) -> None:
        client = _client_with_key("K")
        with mock.patch.object(zc, "probe", return_value="SID"):
            client.ensure_server_id()
        client.invalidate()
        self.assertFalse(client.has_key)
        self.assertIsNone(client._server_id, "invalidate 后 Server-ID 缓存必须清空")


class ErrorMappingTests(unittest.TestCase):
    def _write(self, exc):
        """保持 mock 在整个测试期间生效（用 addCleanup，避免泄漏真实请求）。"""
        recorder = _Recorder([exc])
        patcher_http = mock.patch.object(zc.urllib.request, "urlopen", recorder)
        patcher_probe = mock.patch.object(zc, "probe", return_value="SID")
        patcher_http.start()
        patcher_probe.start()
        self.addCleanup(patcher_probe.stop)
        self.addCleanup(patcher_http.stop)
        return _client_with_key(), recorder

    def test_401_maps_to_auth_required_and_drops_key(self) -> None:
        client, _ = self._write(_http_error(401, b"API key required"))
        with self.assertRaises(zw.ZoteroAuthRequired):
            client.patch("item", "K", {})
        self.assertFalse(client.has_key, "401 后必须丢弃失效 key")

    def test_403_maps_to_forbidden(self) -> None:
        client, _ = self._write(_http_error(403, b"denied"))
        with self.assertRaises(zw.ZoteroForbidden):
            client.patch("item", "K", {})

    def test_412_maps_to_conflict(self) -> None:
        client, _ = self._write(_http_error(412, b"version mismatch"))
        with self.assertRaises(zw.ZoteroConflict):
            client.patch("item", "K", {}, version=1)

    def test_428_maps_to_precondition(self) -> None:
        client, _ = self._write(_http_error(428, b"need version"))
        with self.assertRaises(zw.ZoteroPrecondition):
            client.patch("item", "K", {})

    def test_500_maps_to_write_error(self) -> None:
        client, _ = self._write(_http_error(500, b"boom"))
        with self.assertRaises(zw.ZoteroWriteError):
            client.patch("item", "K", {})


class RequestShapeTests(unittest.TestCase):
    def test_patch_sends_required_headers_and_version(self) -> None:
        recorder = _Recorder([_FakeResponse(b"{}")])
        with mock.patch.object(zc.urllib.request, "urlopen", recorder), \
             mock.patch.object(zc, "probe", return_value="SID"):
            client = _client_with_key("SECRETKEY")
            client.patch("item", "ABC", {"title": "T"}, version=3)
        call = recorder.calls[0]
        self.assertEqual(call["method"], "PATCH")
        self.assertTrue(call["url"].endswith("/api/users/0/items/ABC"))
        self.assertEqual(call["headers"].get("zotero-api-key"), "SECRETKEY")
        self.assertEqual(call["headers"].get("zotero-api-version"), "3")
        self.assertEqual(call["headers"].get("if-unmodified-since-version"), "3")
        self.assertEqual(json.loads(call["data"]), {"title": "T"})

    def test_batch_limit_splits_at_50(self) -> None:
        recorder = _Recorder([_FakeResponse(b"{}"), _FakeResponse(b"{}")])
        with mock.patch.object(zc.urllib.request, "urlopen", recorder), \
             mock.patch.object(zc, "probe", return_value="SID"):
            client = _client_with_key()
            client.post("item", [{"itemType": "note", "note": str(i)} for i in range(51)])
        self.assertEqual(len(recorder.calls), 2, "51 个对象必须分成 2 批")
        self.assertEqual(len(json.loads(recorder.calls[0]["data"])), zw.MAX_WRITE_OBJECTS)
        self.assertEqual(len(json.loads(recorder.calls[1]["data"])), 1)

    def test_unknown_kind_rejected(self) -> None:
        with mock.patch.object(zc, "probe", return_value="SID"):
            client = _client_with_key()
            with self.assertRaises(zw.ZoteroWriteError):
                client.post("bogus", [{"x": 1}])
            with self.assertRaises(zw.ZoteroWriteError):
                client.patch("bogus", "K", {})

    def test_empty_post_rejected(self) -> None:
        with mock.patch.object(zc, "probe", return_value="SID"):
            with self.assertRaises(zw.ZoteroWriteError):
                _client_with_key().post("item", [])


if __name__ == "__main__":
    unittest.main()
