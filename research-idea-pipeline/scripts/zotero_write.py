#!/usr/bin/env python3
"""Zotero Local API 写通道：授权、能力状态、受控写请求。

安全纪律（本仓库强制）：

1. **只读是默认。** 本模块不主动授权。只有调用方显式 `authorize()` 才弹授权窗口。
2. **Key 不落盘。** 只存在内存；不进日志、不进报告、不进 Git。
3. **不回退写。** 未授权时写方法抛 `ZoteroForbidden`；**绝不**把写入静默改到 refs。
4. **实例变化即失效。** `Zotero-Server-ID` 变化 → `invalidate()` 清空 key 与版本缓存。
5. **批上限 50。** 由 `MAX_WRITE_OBJECTS` 强制。

协议事实（Zotero 10.0.3，`server_localAPI.js` 核实）：

- 写请求需 `Zotero-API-Key` + `Zotero-Server-ID` + `Zotero-API-Version: 3`。
- 缺 Server-ID → `428`；Server-ID 不符 → `412`；Key 缺失/失效 → `401`。
- `POST /api/local/authorize` 弹窗：Allow（一次性 Key）/ Always Allow（持久）/
  Deny（`403 {"denied":true}`）。授权本身也受 429 限流。
- keyed 写必须带并发条件：对象 `version` 或 `If-Unmodified-Since-Version`。
- **`PATCH` 是浅合并，数组字段整体替换** —— 调用方必须提交完整数组。
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import zotero_client as zc

#: 后端能力状态。
STATUS_RW = "ZOTERO_RW"        # 可读写
STATUS_RO = "ZOTERO_RO"        # 可读，未授权写入
STATUS_REFS = "REFS_FALLBACK"  # Zotero 不可访问

#: 单次写入对象上限（服务端 `MAX_WRITE_OBJECTS`）。
MAX_WRITE_OBJECTS = 50

WRITE_TIMEOUT = 60.0
AUTHORIZE_TIMEOUT = 600.0  # 等用户点弹窗


def new_write_token() -> str:
    """生成符合 Zotero 要求的 `Zotero-Write-Token`（5–32 字符）。

    服务端在 12 小时内对同一 token 去重，重复使用会返回 412。
    因此 token 是**每次逻辑写入**一个，不可跨批复用。
    """
    import secrets
    return secrets.token_hex(8)


class ZoteroWriteError(RuntimeError):
    """写请求失败的基类。"""


class ZoteroAuthRequired(ZoteroWriteError):
    """需要授权（401）。"""


class ZoteroAuthDenied(ZoteroWriteError):
    """用户在弹窗中拒绝授权（403 denied）。"""


class ZoteroForbidden(ZoteroWriteError):
    """无写权限（未授权 / API 未启用 / 权限不足）。"""


class ZoteroConflict(ZoteroWriteError):
    """并发冲突（412）：对象版本或 Server ID 不符。"""


class ZoteroPrecondition(ZoteroWriteError):
    """缺少前置条件（428）。"""


def _noop_log(_message: str) -> None:
    return None


class WriteClient:
    """受控写客户端。所有写方法都要求已授权，否则抛 `ZoteroForbidden`。"""

    def __init__(self, base_url: Optional[str] = None, *, key: Optional[str] = None,
                 timeout: float = WRITE_TIMEOUT, user: str = zc.DEFAULT_USER,
                 log=_noop_log) -> None:
        self.base_url = (base_url or zc.DEFAULT_LOCAL_API).rstrip("/")
        self.user = user
        self.timeout = timeout
        self.log = log
        self._key = key or None
        self._server_id: Optional[str] = None
        self._status: Optional[str] = None

    # ------------------------------------------------------------------ 状态
    @property
    def server_id(self) -> Optional[str]:
        """当前实例 Server-ID（懒探测）。"""
        if self._server_id is None:
            self._server_id = zc.probe(self.base_url)
        return self._server_id

    @property
    def has_key(self) -> bool:
        return bool(self._key)

    def status(self, *, timeout: float = zc.PROBE_TIMEOUT) -> str:
        """探测后端能力。`REFS_FALLBACK` 表示 Zotero 不可访问。

        注意：**可读但无写权限**返回 `ZOTERO_RO`，要让调用方显式决定是否授权。
        """
        if self.server_id is None:
            self._status = STATUS_REFS
        elif self._key:
            self._status = STATUS_RW
        else:
            self._status = STATUS_RO
        return self._status

    def capability(self) -> Dict[str, Any]:
        """能力快照，供报告使用（**不含 key**）。"""
        status = self.status()
        return {
            "status": status,
            "base_url": self.base_url,
            "server_id": self.server_id,
            "reachable": self.server_id is not None,
            "writable": status == STATUS_RW,
            "has_key": self.has_key,
            "reason": {
                STATUS_RW: "已授权，可读写",
                STATUS_RO: "可读，未授权写入（写入需显式 authorize）",
                STATUS_REFS: "Zotero 本地 API 不可访问",
            }[status],
        }

    def invalidate(self) -> None:
        """Server-ID 变化或连接中断时调用：清空 key 与版本缓存。"""
        self._key = None
        self._server_id = None
        self._status = None
        self.log("[zotero-write] 已失效授权与缓存（Server ID 变化或连接中断）")

    def ensure_server_id(self) -> Optional[str]:
        """确认实例未变化；变化则自动失效并返回 None。"""
        current = zc.probe(self.base_url)
        if current is None:
            if self._server_id is not None:
                self.invalidate()
            return None
        if self._server_id is not None and current != self._server_id:
            self.invalidate()
            self._server_id = current
        else:
            self._server_id = current
        return current

    # ------------------------------------------------------------- 授权
    def authorize(self, app_name: str = "Research Idea Pipeline") -> Dict[str, Any]:
        """走官方授权流程。**会弹出 Zotero 窗口**，只在用户明确要求写入时调用。

        Returns:
            `{"key": str, "remember": bool}`

        Raises:
            ZoteroAuthDenied: 用户点了 Deny。
            ZoteroWriteError: 其它失败（含 429 限流）。
        """
        server_id = self.ensure_server_id()
        if server_id is None:
            raise ZoteroWriteError("Zotero 本地 API 不可访问，无法申请授权")

        body = json.dumps({"appName": app_name}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/local/authorize", data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "Zotero-API-Version": "3",
                "Zotero-Server-ID": server_id,
            })
        try:
            with urllib.request.urlopen(request, timeout=AUTHORIZE_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
            if exc.code == 403:
                raise ZoteroAuthDenied("用户拒绝了授权请求") from exc
            if exc.code == 429:
                raise ZoteroWriteError(
                    f"授权请求过于频繁（Retry-After={exc.headers.get('Retry-After')}）") from exc
            raise ZoteroWriteError(f"授权失败：HTTP {exc.code} {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ZoteroWriteError(f"授权请求失败：{type(exc).__name__}: {exc}") from exc

        key = payload.get("key")
        if not key:
            raise ZoteroAuthDenied("授权未返回 key（可能被拒绝）")
        self._key = key
        self._status = STATUS_RW
        self.log(f"[zotero-write] 已授权（remember={bool(payload.get('remember'))}）")
        return {"key": key, "remember": bool(payload.get("remember"))}

    # ------------------------------------------------------------- 传输
    def _require_key(self) -> str:
        if not self._key:
            raise ZoteroForbidden(
                "写操作需要授权：请先显式调用 authorize()（只读模式不会自动写入）")
        return self._key

    def _url(self, path: str) -> str:
        return f"{self.base_url}/users/{self.user}/{path.lstrip('/')}"

    def request(self, method: str, path: str, *, body: Any = None,
                version: Optional[int] = None, timeout: Optional[float] = None,
                raw_path: bool = False,
                write_token: Optional[str] = None) -> Tuple[int, Any]:
        """发一个写请求。返回 `(status, payload)`。

        `raw_path=True` 时 `path` 直接相对 `/api`（用于 `/items/new` 之类的非 users 路径）。

        Raises:
            ZoteroForbidden / ZoteroAuthRequired / ZoteroConflict / ZoteroPrecondition
        """
        key = self._require_key()
        server_id = self.ensure_server_id()
        if server_id is None:
            raise ZoteroWriteError("Zotero 本地 API 不可访问（写请求不切换后端）")

        url = f"{self.base_url}/{path.lstrip('/')}" if raw_path else self._url(path)
        headers = {
            "Zotero-API-Version": "3",
            "Zotero-Server-ID": server_id,
            "Zotero-API-Key": key,
            "Content-Type": "application/json",
        }
        if version is not None:
            headers["If-Unmodified-Since-Version"] = str(int(version))
        if write_token:
            if not 5 <= len(write_token) <= 32:
                raise ZoteroWriteError("Zotero-Write-Token 必须为 5–32 字符")
            headers["Zotero-Write-Token"] = write_token

        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                text = response.read().decode("utf-8", errors="replace")
                return response.status, (json.loads(text) if text.strip() else None)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            if exc.code == 401:
                self._key = None
                raise ZoteroAuthRequired(f"写入 Key 失效，需重新授权：{detail}") from exc
            if exc.code == 403:
                raise ZoteroForbidden(f"写权限不足或被拒绝：{detail}") from exc
            if exc.code == 412:
                raise ZoteroConflict(f"并发冲突（版本或 Server ID 不符）：{detail}") from exc
            if exc.code == 428:
                raise ZoteroPrecondition(f"缺少前置条件：{detail}") from exc
            raise ZoteroWriteError(f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ZoteroWriteError(f"写请求失败：{type(exc).__name__}: {exc}") from exc

    # --------------------------------------------------------- 类型化封装
    def post(self, kind: str, payloads: List[Dict[str, Any]], *,
             write_token: Optional[str] = None) -> Dict[str, Any]:
        """批量创建。`kind` ∈ item / collection / search / tag。

        自动按 `MAX_WRITE_OBJECTS` 分批。
        """
        if not isinstance(payloads, list) or not payloads:
            raise ZoteroWriteError("post 需要一个非空列表")
        results: Dict[str, Any] = {"successful": {}, "failed": {}, "statuses": []}
        path = {"item": "items", "collection": "collections",
                "search": "searches"}.get(kind)
        if not path:
            raise ZoteroWriteError(f"不支持的 kind：{kind}")
        if write_token and len(payloads) > MAX_WRITE_OBJECTS:
            raise ZoteroWriteError(
                "write_token 只能用于单批（≤50 个对象）：跨批复用同一 token 会被 412 去重")
        for start in range(0, len(payloads), MAX_WRITE_OBJECTS):
            batch = payloads[start:start + MAX_WRITE_OBJECTS]
            status, payload = self.request("POST", path, body=batch,
                                           write_token=write_token)
            results["statuses"].append(status)
            if isinstance(payload, dict):
                for idx, obj in (payload.get("successful") or {}).items():
                    results["successful"][str(start + int(idx))] = obj
                for idx, obj in (payload.get("failed") or {}).items():
                    results["failed"][str(start + int(idx))] = obj
        return results

    def patch(self, kind: str, key: str, payload: Dict[str, Any], *,
              version: Optional[int] = None) -> Tuple[int, Any]:
        """单对象 PATCH。

        调用方负责提交**完整**的数组字段（`tags` / `collections`）——服务端是浅合并。
        """
        path = {"item": f"items/{key}", "collection": f"collections/{key}",
                "search": f"searches/{key}"}.get(kind)
        if not path:
            raise ZoteroWriteError(f"不支持的 kind：{kind}")
        return self.request("PATCH", path, body=payload, version=version)

    def delete(self, kind: str, key: str, *, version: Optional[int] = None) -> Tuple[int, Any]:
        """单对象 DELETE。

        ★ 不假定它只是移入回收站，也不假定可自动恢复。调用方必须先 dry-run 并确认。
        """
        path = {"item": f"items/{key}", "collection": f"collections/{key}",
                "search": f"searches/{key}"}.get(kind)
        if not path:
            raise ZoteroWriteError(f"不支持的 kind：{kind}")
        return self.request("DELETE", path, version=version)

    # ------------------------------------------------------- 只读委托
    # 让 WriteClient 成为**完整客户端**：P3/P4 的模块按鸭子类型要求
    # client 暴露这些只读方法（见 zotero_fulltext._client_fn）。
    # 全部转调 zotero_client，本模块不重复实现 HTTP。
    def probe(self, base_url: Optional[str] = None, **kw) -> Optional[str]:
        return zc.probe(base_url or self.base_url, **kw)

    def search_items(self, query: str, **kw):
        return zc.search_items(query, base_url=self.base_url, **kw)

    def get_item(self, key: str, **kw):
        return zc.get_item(key, base_url=self.base_url, **kw)

    def get_children(self, key: str, **kw):
        return zc.get_children(key, base_url=self.base_url, **kw)

    def item_fulltext(self, attachment_key: str, **kw):
        return zc.item_fulltext(attachment_key, base_url=self.base_url, **kw)

    def file_view_url(self, attachment_key: str, **kw):
        return zc.file_view_url(attachment_key, base_url=self.base_url, **kw)

    def resolve_attachment_path(self, attachment, **kw):
        return zc.local_attachment_path(attachment, base_url=self.base_url, **kw)

    def item_version(self, key: str) -> Optional[int]:
        """读对象当前版本，用于并发条件。"""
        item = zc.get_item(key, base_url=self.base_url)
        if not item:
            return None
        version = item.get("version")
        return int(version) if isinstance(version, int) else None


def open_client(base_url: Optional[str] = None, *, key: Optional[str] = None,
                log=_noop_log) -> WriteClient:
    """构造写客户端（**不授权**）。"""
    return WriteClient(base_url, key=key, log=log)


def _main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Zotero 写通道能力自检（默认只读，不授权）")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--authorize", action="store_true",
                        help="显式申请写入授权（会弹出 Zotero 窗口）")
    args = parser.parse_args(argv)

    client = WriteClient(args.base_url, log=lambda m: print(m, file=sys.stderr))
    print(json.dumps(client.capability(), ensure_ascii=False, indent=1))
    if args.authorize:
        try:
            result = client.authorize()
            print(f"授权成功：remember={result['remember']}")
            print(json.dumps(client.capability(), ensure_ascii=False, indent=1))
        except ZoteroWriteError as exc:
            print(f"授权失败：{exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
