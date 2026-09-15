"""FastAPI 后端：REST + WebSocket + 注册任务调度。"""
from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path
from typing import Literal

import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from . import config, database as db
from . import health, register
from .parser import MailAccount, parse_line
from .proxy import parse_proxy

app = FastAPI(title="OrgRegister")

# ── WebSocket 连接管理 ──────────────────────────────────────────────
_ws_clients: set[WebSocket] = set()


async def broadcast(msg: dict) -> None:
    dead = []
    for ws in list(_ws_clients):
        try:
            await ws.send_text(json.dumps(msg, ensure_ascii=False, default=str))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


# ── 运行状态 ────────────────────────────────────────────────────────
_run_state = {"running": False, "stop": False, "workers": []}
_health_task: asyncio.Task | None = None


async def _health_loop():
    while True:
        try:
            settings = db.get_settings()
            enabled = settings.get("health_enabled", "false") == "true"
            interval = max(1, int(settings.get("health_interval_minutes", "30")))
            if enabled:
                for row in db.list_emails():
                    if row["status"] in ("done", "registered") and (row.get("session_token") or row.get("access_token")):
                        result = await asyncio.to_thread(health.check_account, row, config.DEFAULT_PROXY)
                        detail = "; ".join(f"{x['method']}={x['http_status']}" for x in result["checks"])
                        db.set_email_health(row["ms_email"], result["status"], error=detail or "没有可用 token")
                        await broadcast({"type": "account_health", "email": row["ms_email"], "status": result["status"], "automatic": True})
                await asyncio.sleep(interval * 60)
            else:
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(10)



# ── 模型 ────────────────────────────────────────────────────────────

class EmailsIn(BaseModel):
    text: str = Field(min_length=1, max_length=2_000_000)


class RunIn(BaseModel):
    proxy: str = config.DEFAULT_PROXY
    concurrency: int = Field(default=1, ge=1, le=config.MAX_CONCURRENT)
    headless: bool = False
    limit: int = Field(default=0, ge=0)  # 0 = 全部未使用


class SettingsIn(BaseModel):
    headless: bool = True
    health_enabled: bool = False
    health_interval_minutes: int = Field(default=30, ge=1, le=24 * 60)
    locale: Literal["zh-CN", "zh-TW", "en-US", "ja-JP", "sv-SE"] = "zh-CN"


# ── 邮箱池 ──────────────────────────────────────────────────────────

@app.get("/api/emails")
async def api_emails(status: str | None = None):
    rows = db.list_emails(status)
    return [
        {
            "id": e["id"],
            "ms_email": e["ms_email"],
            "temp_email": e["temp_email"],
            "status": e["status"],
            "account_name": e.get("account_name"),
            "account_age": e.get("account_age"),
        }
        for e in rows
    ]


@app.get("/api/accounts")
async def api_accounts():
    """成功号池：凭据只在此接口返回。"""
    return [
        {
            "id": e["id"],
            "ms_email": e["ms_email"],
            "account_name": e.get("account_name"),
            "account_age": e.get("account_age"),
            "created_at": e.get("created_at"),
            "status": e["status"],
            "session_token": e.get("session_token"),
            "access_token": e.get("access_token"),
            "session_json": e.get("session_json"),
            "health_status": e.get("health_status") or "unknown",
            "health_checked_at": e.get("health_checked_at"),
            "health_error": e.get("health_error"),
        }
        for e in db.list_emails()
        if e["status"] in ("done", "registered") and (e.get("session_token") or e.get("access_token"))
    ]


@app.post("/api/accounts/{email_id}/check")
async def api_account_check(email_id: int):
    row = db.get_email(email_id)
    if not row:
        return JSONResponse({"error": "账号不存在"}, status_code=404)
    result = await asyncio.to_thread(health.check_account, row, config.DEFAULT_PROXY)
    detail = "; ".join(f"{x['method']}={x['http_status']}" for x in result["checks"])
    db.set_email_health(row["ms_email"], result["status"], error=detail or "没有可用 token")
    await broadcast({"type": "account_health", "email_id": email_id, "status": result["status"]})
    return {"id": email_id, **result}


@app.post("/api/accounts/{email_id}/reauth")
async def api_account_reauth(email_id: int):
    if _run_state["running"]:
        return JSONResponse({"error": "已有任务在运行"}, status_code=409)
    row = db.get_email(email_id)
    if not row:
        return JSONResponse({"error": "账号不存在"}, status_code=404)
    account = MailAccount(**{k: row[k] for k in ("ms_email", "ms_password", "ms_uuid", "msa_token", "temp_email", "temp_password")})
    settings = await api_settings()
    reauth_proxy = config.DEFAULT_PROXY
    reauth_headless = settings["headless"]
    task_id = db.create_task(account.ms_email, reauth_proxy)
    _run_state["running"] = True
    _run_state["stop"] = False

    async def rerun():
        try:
            await _worker(account, task_id, reauth_proxy, reauth_headless)
        except asyncio.CancelledError:
            db.update_task(task_id, status="failed", error="任务已停止")
            db.set_email_status(account.ms_email, "failed")
            db.add_task_log(task_id, "任务已停止", "warning")
            raise
        except Exception as exc:
            db.update_task(task_id, status="failed", error=f"{type(exc).__name__}: {exc}")
            db.set_email_health(account.ms_email, "unknown", error=str(exc))
        finally:
            _run_state["running"] = False
            await broadcast({"type": "run_finished"})

    task = asyncio.create_task(rerun())
    _run_state["workers"] = [task]
    return {"started": True, "task_id": task_id}


@app.post("/api/emails")
async def api_emails_add(body: EmailsIn):
    accounts: list[MailAccount] = []
    invalid_lines: list[int] = []
    for line_no, line in enumerate(body.text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        acc = parse_line(line)
        if acc:
            accounts.append(acc)
        else:
            invalid_lines.append(line_no)
    duplicates = db.find_existing_emails(accounts)
    seen = set()
    for account in accounts:
        if account.ms_email in seen and account.ms_email not in duplicates:
            duplicates.append(account.ms_email)
        seen.add(account.ms_email)
    added = db.upsert_emails(accounts)
    await broadcast({"type": "emails_updated", "stats": db.count_emails()})
    return {
        "added": added,
        "parsed": len(accounts),
        "duplicates": duplicates,
        "duplicate_count": len(duplicates),
        "invalid_count": len(invalid_lines),
        "invalid_lines": invalid_lines,
    }


@app.delete("/api/emails/{ms_email:path}")
async def api_email_delete(ms_email: str):
    db.delete_email(ms_email)
    await broadcast({"type": "emails_updated", "stats": db.count_emails()})
    return {"ok": True}


@app.delete("/api/accounts/{email_id}")
async def api_account_delete(email_id: int):
    row = db.get_email(email_id)
    if not row:
        return JSONResponse({"error": "账号不存在"}, status_code=404)
    if _run_state["running"]:
        return JSONResponse({"error": "任务运行中，暂时不能删除账号"}, status_code=409)
    db.delete_email(row["ms_email"])
    await broadcast({"type": "emails_updated", "stats": db.count_emails()})
    return {"ok": True, "email": row["ms_email"]}


# ── 任务 ────────────────────────────────────────────────────────────

@app.get("/api/tasks")
async def api_tasks(limit: int = 200):
    return [_public_task(t) for t in db.list_tasks(limit)]


@app.delete("/api/tasks")
async def api_tasks_clear():
    if _run_state["running"]:
        return JSONResponse({"error": "任务运行中，暂时不能清空记录"}, status_code=409)
    removed = db.clear_task_history()
    await broadcast({"type": "tasks_cleared", "removed": removed})
    return {"ok": True, "removed": removed}


def _public_task(task: dict | None) -> dict | None:
    if task is None:
        return None
    return {
        "id": task["id"],
        "email": task["email"],
        "proxy": task.get("proxy"),
        "status": task["status"],
        "captcha_id": task.get("captcha_id"),
        "error": task.get("error"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
    }


@app.get("/api/task/{task_id}/logs")
async def api_task_logs(task_id: int):
    return db.list_task_logs(task_id)


@app.get("/api/task/{task_id}")
async def api_task(task_id: int):
    return _public_task(db.get_task(task_id))


@app.get("/api/settings")
async def api_settings():
    s = db.get_settings()
    return {
        "headless": s.get("headless", "true") == "true",
        "health_enabled": s.get("health_enabled", "false") == "true",
        "health_interval_minutes": max(1, int(s.get("health_interval_minutes", "30"))),
        "locale": s.get("locale", "zh-CN") if s.get("locale", "zh-CN") in {"zh-CN", "zh-TW", "en-US", "ja-JP", "sv-SE"} else "zh-CN",
    }


@app.post("/api/settings")
async def api_settings_save(body: SettingsIn):
    db.set_setting("headless", str(body.headless).lower())
    db.set_setting("health_enabled", str(body.health_enabled).lower())
    db.set_setting("health_interval_minutes", str(max(1, body.health_interval_minutes)))
    db.set_setting("locale", body.locale)
    await broadcast({"type": "settings_updated"})
    return await api_settings()


@app.post("/api/proxy/test")
async def api_proxy_test(body: dict):
    raw = str(body.get("proxy") or "").strip()
    proxy_cfg = parse_proxy(raw)
    proxies = proxy_cfg.to_requests() if proxy_cfg.server else None
    # Use the same origin as the browser workflow. IP-info services are often
    # rate-limited and a 429 there does not mean the proxy is unusable.
    target = "https://chatgpt.com/"
    try:
        r = await asyncio.to_thread(
            requests.get,
            target,
            proxies=proxies,
            headers={"User-Agent": "OrgRegister proxy check"},
            timeout=15,
            allow_redirects=True,
        )
        result = {
            "ok": 200 <= r.status_code < 400,
            "status": r.status_code,
            "target": target,
            "url": r.url,
        }
        # Fetch location data separately. This endpoint is informational only;
        # rate limits here must not turn a working proxy into a failed test.
        if result["ok"]:
            try:
                geo = await asyncio.to_thread(
                    requests.get,
                    "https://ipwho.is/",
                    proxies=proxies,
                    headers={"User-Agent": "OrgRegister proxy check"},
                    timeout=10,
                )
                if geo.ok:
                    data = geo.json()
                    result.update(
                        {
                            "ip": data.get("ip"),
                            "country": data.get("country"),
                            "region": data.get("region"),
                            "city": data.get("city"),
                            "timezone": (data.get("timezone") or {}).get("id")
                            if isinstance(data.get("timezone"), dict)
                            else data.get("timezone"),
                            "org": data.get("connection", {}).get("org")
                            if isinstance(data.get("connection"), dict)
                            else None,
                        }
                    )
            except Exception as exc:
                result["geo_error"] = f"{type(exc).__name__}: {exc}"
        return result
    except Exception as exc:
        return {"ok": False, "target": target, "error": f"{type(exc).__name__}: {exc}"}


@app.get("/api/stats")
async def api_stats():
    return {"emails": db.count_emails(), "tasks": db.count_tasks(), "running": _run_state["running"]}


async def _worker(account: MailAccount, task_id: int, proxy: str, headless: bool):
    db.set_email_status(account.ms_email, "running")
    db.update_task(task_id, status="running", error=None)
    db.add_task_log(task_id, f"任务开始：{account.ms_email}")
    await broadcast({"type": "task_update", "task": _public_task(db.get_task(task_id))})

    async def notify():
        db.update_task(task_id, status="waiting_captcha")
        db.add_task_log(task_id, "等待人工验证码", "warning")
        await broadcast({"type": "captcha", "task_id": task_id, "email": account.ms_email})

    async def progress(msg: str):
        db.update_task(task_id, error=msg)
        db.add_task_log(task_id, msg)
        await broadcast({"type": "progress", "task_id": task_id, "email": account.ms_email, "msg": msg})

    result = await register.register_account(account, proxy=proxy, notify=notify, progress=progress, headless=headless)

    if result["status"] in ("done", "registered"):
        db.update_task(
            task_id,
            status=result["status"],
            session_token=result["session_token"],
            access_token=result["access_token"],
            error=None,
        )
        db.set_email_result(
            account.ms_email,
            result["status"],
            result["session_token"],
            result["access_token"],
            result.get("session_json"),
            result.get("account_name"),
            result.get("account_age"),
        )
        db.add_task_log(task_id, f"任务完成：{result['status']}", "success")
    else:
        final_status = "banned" if result["status"] == "banned" or result["error"] == "account_banned" else "failed"
        db.update_task(task_id, status=final_status, error=result["error"])
        db.set_email_status(account.ms_email, final_status)
        db.add_task_log(task_id, f"任务结束：{final_status}，{result['error']}", "error")
    await broadcast({"type": "task_update", "task": _public_task(db.get_task(task_id))})


async def _run_loop(accounts: list[MailAccount], proxy: str, headless: bool, concurrency: int):
    sem = asyncio.Semaphore(concurrency)

    async def guarded(account: MailAccount):
        async with sem:
            if _run_state["stop"]:
                return
            task_id = db.create_task(account.ms_email, proxy)
            try:
                await _worker(account, task_id, proxy, headless)
            except asyncio.CancelledError:
                db.update_task(task_id, status="failed", error="任务已停止")
                db.set_email_status(account.ms_email, "failed")
                db.add_task_log(task_id, "任务已停止", "warning")
                await broadcast({"type": "task_update", "task": _public_task(db.get_task(task_id))})
                raise
            except Exception as e:
                db.update_task(task_id, status="failed", error=f"{type(e).__name__}: {e}")
                db.set_email_status(account.ms_email, "failed")
                await broadcast({"type": "task_update", "task": _public_task(db.get_task(task_id))})

    await asyncio.gather(*(guarded(a) for a in accounts))


@app.post("/api/tasks/run")
async def api_run(body: RunIn):
    if _run_state["running"]:
        return JSONResponse({"error": "已有任务在运行"}, status_code=409)

    candidates = db.list_emails()
    unused = [e for e in candidates if e["status"] in ("unused", "failed") and e["status"] != "banned"]
    if body.limit > 0:
        unused = unused[: body.limit]
    if not unused:
        return JSONResponse({"error": "没有可用的未使用邮箱"}, status_code=400)

    accounts = [MailAccount(**{k: e[k] for k in ("ms_email", "ms_password", "ms_uuid", "msa_token", "temp_email", "temp_password")}) for e in unused]

    _run_state["running"] = True
    _run_state["stop"] = False
    _run_state["workers"] = []

    async def _main():
        try:
            await _run_loop(accounts, body.proxy, body.headless, max(1, body.concurrency))
        finally:
            _run_state["running"] = False
            _run_state["stop"] = False
            _run_state["workers"] = []
            await broadcast({"type": "run_finished"})

    task = asyncio.create_task(_main())
    _run_state["workers"].append(task)
    await broadcast({"type": "run_started", "count": len(accounts)})
    return {"started": len(accounts)}


@app.post("/api/tasks/stop")
async def api_stop():
    if not _run_state["running"]:
        return {"ok": True, "stopping": False}
    _run_state["stop"] = True
    workers = list(_run_state.get("workers", []))
    for task in workers:
        if not task.done():
            task.cancel()
    return {"ok": True, "stopping": True, "cancelled": len(workers)}


# ── WebSocket ───────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # 客户端心跳
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


@app.on_event("startup")
async def startup_event():
    global _health_task
    _health_task = asyncio.create_task(_health_loop())


@app.on_event("shutdown")
async def shutdown_event():
    global _health_task
    if _health_task:
        _health_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _health_task
        _health_task = None


# ── 静态资源 ────────────────────────────────────────────────────────

_frontend = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/")
async def index():
    html = (_frontend / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/{path:path}")
async def static_assets(path: str):
    fp = _frontend / path
    if fp.exists() and fp.is_file():
        return FileResponse(fp)
    return JSONResponse({"error": "not found"}, status_code=404)


def start():
    import uvicorn

    db.set_running_tasks_to_pending()
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")


if __name__ == "__main__":
    start()
