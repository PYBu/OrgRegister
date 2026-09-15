"""全局配置。"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "reg.db"
EMAILS_FILE = DATA_DIR / "emails.txt"

# ── 代理默认值：本地 Clash 等 HTTP 代理 ──────────────────────────────
DEFAULT_PROXY = "127.0.0.1:7890"

# ── 人工打码 ────────────────────────────────────────────────────────
CAPTCHA_POLL_INTERVAL = 1.0   # 打码队列轮询间隔（秒）
CAPTCHA_TIMEOUT = 600          # 单个验证码等待操作员解决的超时（秒）

# ── 注册任务 ────────────────────────────────────────────────────────
MAX_CONCURRENT = 2             # 默认并发注册数
REGISTER_TIMEOUT = 300         # 单账号注册超时（秒）
MAIL_CODE_TIMEOUT = 240        # 取验证码等待超时（秒）
MAIL_CODE_SINCE_GRACE = 300    # 邮件服务与本机时钟/投递时间容差（秒）
# 验证码发件人（None = 不限发件人，取最近邮件中的 6 位数字）
# OpenAI 实际发件人为 noreply@tm.openai.com；微软验证码来自 accountprotection
OPENAI_CODE_SENDER = None

# ── 服务 ────────────────────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 8001
