"""成功账号 token 验活。"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import requests

from . import config
from .proxy import parse_proxy


def _proxies(proxy: str | None):
    if not proxy:
        return None
    p = parse_proxy(proxy)
    return p.to_requests() if p.server else None


def _probe(url: str, *, headers: dict, proxy: str | None) -> tuple[bool, int, str]:
    try:
        r = requests.get(url, headers=headers, proxies=_proxies(proxy), timeout=20)
        if r.status_code == 200:
            return True, r.status_code, "ok"
        return False, r.status_code, r.text[:180]
    except Exception as exc:
        return False, 0, f"{type(exc).__name__}: {exc}"


def check_account(row: dict, proxy: str | None = None) -> dict:
    """用 session cookie 和 access token 双通道验活。"""
    session_token = row.get("session_token")
    access_token = row.get("access_token")
    checks = []

    if session_token:
        ok, status, detail = _probe(
            "https://chatgpt.com/api/auth/session",
            headers={"Cookie": f"__Secure-next-auth.session-token={session_token}"},
            proxy=proxy,
        )
        checks.append({"method": "session", "alive": ok, "http_status": status, "detail": detail})

    if access_token:
        ok, status, detail = _probe(
            "https://chatgpt.com/backend-api/models",
            headers={"Authorization": f"Bearer {access_token}"},
            proxy=proxy,
        )
        checks.append({"method": "access", "alive": ok, "http_status": status, "detail": detail})

    alive = any(item["alive"] for item in checks)
    result = "alive" if alive else ("dead" if checks else "unknown")
    return {
        "status": result,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
