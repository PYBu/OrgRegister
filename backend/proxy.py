"""代理解析。

支持两种格式：
    ip:port                 -> 无认证（默认 http）
    ip:port:username:password -> 带用户名密码认证
默认 127.0.0.1:7890。
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote


@dataclass
class Proxy:
    server: str
    username: str | None = None
    password: str | None = None

    def to_patchright(self) -> dict:
        """转换成 patchright/playwright launch 的 proxy 参数。"""
        d: dict = {"server": self.server}
        if self.username:
            d["username"] = self.username
            d["password"] = self.password or ""
        return d

    def to_requests(self) -> dict:
        """转换成 requests 可用的 proxies 字典。"""
        if self.username:
            auth = f"{quote(self.username, safe='')}:{quote(self.password or '', safe='')}@"
            host = self.server.replace("http://", "").replace("https://", "")
            scheme = self.server.split(":", 1)[0]
            url = f"{scheme}://{auth}{host}"
        else:
            url = self.server
        return {"http": url, "https": url}


def parse_proxy(raw: str | None) -> Proxy:
    """解析代理字符串。空则返回 None 语义由调用方处理。"""
    s = (raw or "").strip()
    if not s:
        return Proxy(server="")  # 表示不使用代理
    if "://" not in s:
        s = "http://" + s
    parts = s.split(":")
    # 形如 http://ip:port:user:pass
    if s.startswith("http://") or s.startswith("https://"):
        scheme, rest = s.split("://", 1)
        tokens = rest.split(":")
    else:
        scheme, tokens = "http", s.split(":")
    if len(tokens) >= 4:
        # ip : port : user : pass（pass 可能含冒号，取剩余拼接）
        ip = tokens[0]
        port = tokens[1]
        user = tokens[2]
        pwd = ":".join(tokens[3:])
        return Proxy(server=f"{scheme}://{ip}:{port}", username=user, password=pwd)
    elif len(tokens) >= 2:
        return Proxy(server=f"{scheme}://{tokens[0]}:{tokens[1]}")
    return Proxy(server=s)
