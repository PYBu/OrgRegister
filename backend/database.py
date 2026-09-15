"""SQLite 持久化：邮箱池 + 注册任务 + 结果。"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from . import config

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init(_conn)
    return _conn


def _ensure_column(c: sqlite3.Connection, table: str, col: str, decl: str) -> None:
    cols = [r["name"] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
    if col not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def _init(c: sqlite3.Connection) -> None:
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ms_email TEXT UNIQUE NOT NULL,
            ms_password TEXT NOT NULL,
            ms_uuid TEXT NOT NULL,
            msa_token TEXT NOT NULL,
            temp_email TEXT NOT NULL,
            temp_password TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unused',  -- unused|running|done|registered|failed|banned
            session_token TEXT,
            access_token TEXT,
            session_json TEXT,
            account_name TEXT,
            account_age INTEGER,
            health_status TEXT,
            health_checked_at REAL,
            health_error TEXT,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            proxy TEXT,
            status TEXT NOT NULL DEFAULT 'pending',  -- pending|running|waiting_captcha|done|failed
            session_token TEXT,
            access_token TEXT,
            captcha_id TEXT,
            error TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS task_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            level TEXT NOT NULL DEFAULT 'info',
            message TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    # 旧库迁移：补充成功账号凭据与资料列
    _ensure_column(c, "emails", "session_token", "TEXT")
    _ensure_column(c, "emails", "access_token", "TEXT")
    _ensure_column(c, "emails", "session_json", "TEXT")
    _ensure_column(c, "emails", "account_name", "TEXT")
    _ensure_column(c, "emails", "account_age", "INTEGER")
    _ensure_column(c, "emails", "health_status", "TEXT")
    _ensure_column(c, "emails", "health_checked_at", "REAL")
    _ensure_column(c, "emails", "health_error", "TEXT")
    c.commit()


def now() -> float:
    return time.time()


# ── 邮箱池 ──────────────────────────────────────────────────────────

def upsert_emails(accounts) -> int:
    """批量插入邮箱（已存在则跳过）。返回新增数量。"""
    with _lock:
        c = _get_conn()
        added = 0
        for a in accounts:
            try:
                c.execute(
                    "INSERT INTO emails (ms_email, ms_password, ms_uuid, msa_token, temp_email, temp_password, status, created_at) "
                    "VALUES (?,?,?,?,?,?, 'unused', ?)",
                    (a.ms_email, a.ms_password, a.ms_uuid, a.msa_token, a.temp_email, a.temp_password, now()),
                )
                added += 1
            except sqlite3.IntegrityError:
                pass
        c.commit()
        return added


def list_emails(status: str | None = None) -> list[dict]:
    with _lock:
        c = _get_conn()
        if status:
            rows = c.execute("SELECT * FROM emails WHERE status=? ORDER BY id", (status,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM emails ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_unused_email() -> dict | None:
    with _lock:
        c = _get_conn()
        r = c.execute(
            "SELECT * FROM emails WHERE status='unused' ORDER BY id LIMIT 1"
        ).fetchone()
        return dict(r) if r else None


def set_email_status(ms_email: str, status: str) -> None:
    with _lock:
        c = _get_conn()
        c.execute("UPDATE emails SET status=? WHERE ms_email=?", (status, ms_email))
        c.commit()


def set_email_health(ms_email: str, status: str, checked_at: float | None = None, error: str | None = None) -> None:
    with _lock:
        c = _get_conn()
        c.execute(
            "UPDATE emails SET health_status=?, health_checked_at=?, health_error=? WHERE ms_email=?",
            (status, checked_at or now(), error, ms_email),
        )
        c.commit()


def get_email(email_id: int) -> dict | None:
    with _lock:
        c = _get_conn()
        row = c.execute("SELECT * FROM emails WHERE id=?", (email_id,)).fetchone()
        return dict(row) if row else None


def set_email_result(
    ms_email: str,
    status: str,
    session_token: str | None = None,
    access_token: str | None = None,
    session_json: str | None = None,
    account_name: str | None = None,
    account_age: int | None = None,
) -> None:
    """登记成功账号：状态、凭据、完整 session JSON 与资料。"""
    with _lock:
        c = _get_conn()
        c.execute(
            "UPDATE emails SET status=?, session_token=?, access_token=?, session_json=?, account_name=?, account_age=?, health_status='alive', health_error=NULL WHERE ms_email=?",
            (status, session_token, access_token, session_json, account_name, account_age, ms_email),
        )
        c.commit()


def delete_email(ms_email: str) -> None:
    with _lock:
        c = _get_conn()
        c.execute("DELETE FROM emails WHERE ms_email=?", (ms_email,))
        c.commit()


def count_emails() -> dict:
    with _lock:
        c = _get_conn()
        rows = c.execute("SELECT status, COUNT(*) n FROM emails GROUP BY status").fetchall()
        out = {"total": 0}
        for r in rows:
            out[r["status"]] = r["n"]
            out["total"] += r["n"]
        return out


# ── 任务 ────────────────────────────────────────────────────────────

def get_setting(key: str, default: str | None = None) -> str | None:
    with _lock:
        row = _get_conn().execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _lock:
        c = _get_conn()
        c.execute("INSERT INTO app_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        c.commit()


def get_settings() -> dict:
    with _lock:
        rows = _get_conn().execute("SELECT key,value FROM app_settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


def add_task_log(task_id: int, message: str, level: str = "info") -> None:
    with _lock:
        c = _get_conn()
        c.execute("INSERT INTO task_logs (task_id, level, message, created_at) VALUES (?,?,?,?)", (task_id, level, message, now()))
        c.commit()


def list_task_logs(task_id: int) -> list[dict]:
    with _lock:
        c = _get_conn()
        rows = c.execute("SELECT * FROM task_logs WHERE task_id=? ORDER BY id", (task_id,)).fetchall()
        return [dict(r) for r in rows]


def find_existing_emails(accounts) -> list[str]:
    with _lock:
        c = _get_conn()
        found = []
        for a in accounts:
            row = c.execute("SELECT 1 FROM emails WHERE ms_email=?", (a.ms_email,)).fetchone()
            if row:
                found.append(a.ms_email)
        return found


def create_task(email: str, proxy: str) -> int:
    with _lock:
        c = _get_conn()
        cur = c.execute(
            "INSERT INTO tasks (email, proxy, status, created_at, updated_at) VALUES (?,?, 'pending', ?, ?)",
            (email, proxy, now(), now()),
        )
        c.commit()
        return cur.lastrowid


def update_task(task_id: int, **fields) -> None:
    if not fields:
        return
    with _lock:
        c = _get_conn()
        fields["updated_at"] = now()
        cols = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [task_id]
        c.execute(f"UPDATE tasks SET {cols} WHERE id=?", vals)
        c.commit()


def get_task(task_id: int) -> dict | None:
    with _lock:
        c = _get_conn()
        r = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(r) if r else None


def list_tasks(limit: int = 200) -> list[dict]:
    with _lock:
        c = _get_conn()
        rows = c.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def clear_task_history() -> int:
    """Delete task logs and task rows, returning the number of tasks removed."""
    with _lock:
        c = _get_conn()
        count = c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        c.execute("DELETE FROM task_logs")
        c.execute("DELETE FROM tasks")
        c.commit()
        return int(count)


def count_tasks() -> dict:
    with _lock:
        c = _get_conn()
        rows = c.execute("SELECT status, COUNT(*) n FROM tasks GROUP BY status").fetchall()
        out = {"total": 0}
        for r in rows:
            out[r["status"]] = r["n"]
            out["total"] += r["n"]
        return out


def set_running_tasks_to_pending() -> None:
    """启动时把上次中断的 running/waiting_captcha 任务重置为 pending。"""
    with _lock:
        c = _get_conn()
        c.execute(
            "UPDATE tasks SET status='pending', error='interrupted', updated_at=? WHERE status IN ('running','waiting_captcha')",
            (now(),),
        )
        c.commit()
