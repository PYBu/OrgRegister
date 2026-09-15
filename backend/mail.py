"""微软邮箱取件 —— 提取验证码（6 位数字）。

正确链路（实测验证）：
    MSA refresh_token（M.C539...）+ UUID(client_id)
        ↓ POST login.live.com/oauth20_token.srf  grant_type=refresh_token
        ↓ scope=Mail.Read offline_access
    access_token
        ↓ Bearer
    Microsoft Graph /me/messages 读收件箱 → 正则提取 6 位数字验证码

支持 since 时间过滤：只取 receivedDateTime >= since 的新邮件，
避免取到历史验证码。
"""
from __future__ import annotations

import email
import imaplib
import re
import time
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime

import requests

from . import config
from .parser import MailAccount
from .proxy import parse_proxy

_CODE_RE = re.compile(r"\b(\d{6})\b")
_TOKEN_ENDPOINT = "https://login.live.com/oauth20_token.srf"
_GRAPH_MESSAGES = "https://graph.microsoft.com/v1.0/me/messages"
_DEFAULT_SENDER = config.OPENAI_CODE_SENDER


def _proxies(proxy: str | None):
    """解析代理字符串为 requests proxies 字典；空则 None。"""
    if not proxy:
        return None
    p = parse_proxy(proxy)
    if not p.server:
        return None
    return p.to_requests()


def exchange_access_token(account: MailAccount, proxy: str | None = None) -> str | None:
    """用 MSA refresh_token + UUID(client_id) 换取 access token。"""
    try:
        r = requests.post(
            _TOKEN_ENDPOINT,
            data={
                "grant_type": "refresh_token",
                "client_id": account.ms_uuid,
                "refresh_token": account.msa_token,
                "scope": "Mail.Read offline_access",
            },
            proxies=_proxies(proxy),
            timeout=30,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception:
        pass
    return None


def _decode(s: str) -> str:
    try:
        parts = decode_header(s or "")
        out = []
        for txt, enc in parts:
            if isinstance(txt, bytes):
                out.append(txt.decode(enc or "utf-8", "ignore"))
            else:
                out.append(txt)
        return "".join(out)
    except Exception:
        return s or ""


def _extract_code(subject: str, body: str, sender: str, body_preview: str | None = None) -> str | None:
    # 优先用纯文本预览（bodyPreview），避免 HTML 模板数字干扰验证码提取
    blob = " ".join([subject, sender, body_preview or body])
    m = _CODE_RE.search(blob)
    return m.group(1) if m else None


def _after_grace(value: datetime | None, since: datetime | None) -> bool:
    """Apply a small clock/delivery grace window without accepting old mail."""
    if since is None or value is None:
        return True
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc) >= since.astimezone(timezone.utc) - timedelta(seconds=config.MAIL_CODE_SINCE_GRACE)


def _parse_graph_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _graph_code(values: list[dict], sender: str | None, since: datetime | None) -> str | None:
    for message in values:
        if sender:
            address = ((message.get("from") or {}).get("emailAddress") or {}).get("address", "")
            if address.lower() != sender.lower():
                continue
        if not _after_grace(_parse_graph_datetime(message.get("receivedDateTime")), since):
            continue
        code = _extract_code(
            message.get("subject", ""),
            (message.get("body") or {}).get("content", ""),
            ((message.get("from") or {}).get("emailAddress") or {}).get("address", ""),
            message.get("bodyPreview", ""),
        )
        if code:
            return code
    return None


def _graph_fetch(account: MailAccount, sender: str | None, proxy: str | None, since: datetime | None = None) -> str | None:
    token = exchange_access_token(account, proxy)
    if not token:
        return None
    params = {
        "$top": 25,
        "$orderby": "receivedDateTime desc",
        "$select": "subject,from,body,bodyPreview,receivedDateTime",
    }
    filters = []
    if sender:
        filters.append(f"from/emailAddress/address eq '{sender}'")
    if since:
        # Graph can compare against a server timestamp that is a little ahead
        # of the local submit time. Query with grace, then validate locally.
        query_since = since.astimezone(timezone.utc) - timedelta(seconds=config.MAIL_CODE_SINCE_GRACE)
        iso = query_since.strftime("%Y-%m-%dT%H:%M:%SZ")
        filters.append(f"receivedDateTime ge {iso}")
    if filters:
        params["$filter"] = " and ".join(filters)
    request_kwargs = {
        "headers": {"Authorization": f"Bearer {token}"},
        "proxies": _proxies(proxy),
        "timeout": 30,
    }
    r = requests.get(_GRAPH_MESSAGES, params=params, **request_kwargs)
    # Some Graph tenants reject combined $filter/$orderby queries. Retry the
    # same mailbox without the server-side time filter and filter locally.
    if r.status_code != 200 and "$filter" in params:
        fallback = dict(params)
        fallback.pop("$filter", None)
        r = requests.get(_GRAPH_MESSAGES, params=fallback, **request_kwargs)
    if r.status_code != 200:
        return None
    values = r.json().get("value", [])
    code = _graph_code(values, sender, since)
    if code:
        return code
    # A valid 200 response can still omit a just-delivered message because the
    # server-side receivedDateTime index lags. Retry without $filter and apply
    # the same checks locally before accepting a code.
    if "$filter" in params:
        fallback = dict(params)
        fallback.pop("$filter", None)
        fallback_response = requests.get(_GRAPH_MESSAGES, params=fallback, **request_kwargs)
        if fallback_response.status_code == 200:
            return _graph_code(fallback_response.json().get("value", []), sender, since)
    return None


def _xoauth2_string(user: str, token: str) -> str:
    return f"user={user}\x01auth=Bearer {token}\x01\x01"


def _imap_xoauth2_fetch(account: MailAccount, sender: str | None, proxy: str | None, since: datetime | None = None) -> str | None:
    token = exchange_access_token(account, proxy)
    if not token:
        return None
    try:
        im = imaplib.IMAP4_SSL("outlook.office365.com", 993, timeout=30)
        im.authenticate("XOAUTH2", lambda _: _xoauth2_string(account.ms_email, token).encode())
        im.select("INBOX")
        criteria = "ALL"
        if sender:
            criteria = f'(FROM "{sender}")'
        if since:
            date_str = since.strftime("%d-%b-%Y")
            if sender:
                criteria = f'(FROM "{sender}" SINCE "{date_str}")'
            else:
                criteria = f'(SINCE "{date_str}")'
        status, data = im.search(None, criteria)
        if status != "OK":
            im.logout()
            return None
        ids = data[0].split()
        for num in reversed(ids[-5:]):
            _, raw = im.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(raw[0][1])
            msg_date = None
            try:
                msg_date = parsedate_to_datetime(msg.get("Date", ""))
            except (TypeError, ValueError, IndexError, OverflowError):
                pass
            if not _after_grace(msg_date, since):
                continue
            subj = _decode(str(msg.get("Subject", "")))
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body += part.get_payload(decode=True).decode("utf-8", "ignore")
            else:
                body = msg.get_payload(decode=True).decode("utf-8", "ignore")
            code = _extract_code(subj, body, msg.get("From", ""))
            if code:
                im.logout()
                return code
        im.logout()
    except Exception:
        pass
    return None


_FETCHERS = [
    _graph_fetch,
    _imap_xoauth2_fetch,
]


def fetch_code_once(
    account: MailAccount,
    sender: str | None = _DEFAULT_SENDER,
    proxy: str | None = None,
    since: datetime | None = None,
) -> str | None:
    for fn in _FETCHERS:
        try:
            code = fn(account, sender, proxy, since)
            if code:
                return code
        except Exception:
            continue
    return None


def fetch_code(
    account: MailAccount,
    sender: str | None = _DEFAULT_SENDER,
    proxy: str | None = None,
    timeout: float = config.MAIL_CODE_TIMEOUT,
    interval: float = 8.0,
    since: datetime | None = None,
) -> str:
    """轮询等待验证码直到超时。sender=None 表示不限发件人；since 只取该时间后的邮件。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        code = fetch_code_once(account, sender, proxy, since)
        if code:
            return code
        time.sleep(interval)
    raise TimeoutError(f"{account.ms_email} 在 {timeout}s 内未收到验证码")
