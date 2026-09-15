"""邮箱池解析。

每行格式（6 段，以 ---- 分隔）：
    微软邮箱----微软密码----UUID----MSA_Token----临时邮箱----临时邮箱密码
示例：
    MS_EMAIL----MS_PASSWORD----MS_UUID----MSA_REFRESH_TOKEN----TEMP_EMAIL----TEMP_PASSWORD
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, fields
from pathlib import Path

_SEP = "----"


@dataclass
class MailAccount:
    ms_email: str
    ms_password: str
    ms_uuid: str          # 微软账号关联 UUID（client_id/设备标识，取件备用）
    msa_token: str
    temp_email: str
    temp_password: str

    def to_dict(self) -> dict:
        return asdict(self)


def parse_line(line: str) -> MailAccount | None:
    """解析单行。格式不对返回 None。"""
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    parts = [p.strip() for p in s.split(_SEP)]
    if len(parts) != 6:
        return None
    if any(not p for p in parts):
        return None
    return MailAccount(*parts)


def load_pool(path: str | Path) -> list[MailAccount]:
    """从文件加载邮箱池，跳过空行/注释/格式错误行。"""
    p = Path(path)
    if not p.exists():
        return []
    out: list[MailAccount] = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        acc = parse_line(line)
        if acc is None and line.strip() and not line.strip().startswith("#"):
            print(f"[parser] 第 {i} 行格式错误（应为 6 段），已跳过: {line[:60]!r}")
        elif acc is not None:
            out.append(acc)
    return out


def append_line(path: str | Path, line: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")
