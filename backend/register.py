"""ChatGPT 注册核心流程（邮箱注册）。

实测流程：
    chatgpt.com/auth/login
      → 填邮箱 input[type=email] → 点「继续」button[type=submit]
      → 邮箱验证码（发到微软邮箱，自动取件回填）→ 点「继续」
      → 名字（随机）+ 年龄（随机 20-30）→ 点「继续」
      → 登录完成 → 提取 __Secure-next-auth.session-token + accessToken。
"""
from __future__ import annotations

import asyncio
import datetime
import random
import time
from typing import Awaitable, Callable

from patchright.async_api import async_playwright

from . import captcha, config, fingerprint, mail
from .parser import MailAccount
from .proxy import parse_proxy

Progress = Callable[[str], Awaitable[None] | None]

FIRST_NAMES = [
    "James", "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia",
    "Lucas", "Mia", "Mason", "Isabella", "Logan", "Amelia", "Aiden", "Harper",
    "Elijah", "Charlotte", "Oliver", "Evelyn", "William", "Abigail", "Benjamin", "Emily",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Martinez", "Wilson", "Anderson", "Taylor", "Thomas", "Moore",
    "Jackson", "Martin", "Lee", "Thompson", "White", "Harris",
]

EMAIL_INPUT = 'input[type="email"]'
SUBMIT_BTN = 'button[type="submit"]'
CODE_INPUT = (
    'input[inputmode="numeric"], input[autocomplete="one-time-code"], '
    'input[name="code"], input[aria-label*="code" i], input[aria-label*="Code" i]'
)
NAME_INPUT = (
    'input[name="name"], input[name="full_name"], input[autocomplete="given-name"], '
    'input[placeholder*="name" i], input[aria-label*="name" i], input[aria-label*="名字"]'
)
AGE_INPUT = (
    'input[name="age"], input[name="birthdate"], input[type="number"], '
    'input[inputmode="numeric"], input[aria-label*="age" i], input[aria-label*="年龄"]'
)


async def _safe_progress(progress: Progress | None, msg: str):
    if not progress:
        return
    r = progress(msg)
    if asyncio.iscoroutine(r):
        await r


def _random_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _random_age() -> int:
    return random.randint(20, 30)


def _random_birthdate() -> tuple[int, int, int]:
    """20-30 岁对应的随机生日 (年, 月, 日)。"""
    year = datetime.date.today().year - random.randint(20, 30)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return year, month, day


async def extract_tokens(context, page) -> tuple[str | None, str | None, str | None]:
    """提取 session cookie、完整 session JSON 与 access token。"""
    session_token = None
    for c in await context.cookies():
        if c["name"] == "__Secure-next-auth.session-token" and c["value"]:
            session_token = c["value"]
            break
    session_json = None
    access_token = None
    try:
        data = await page.evaluate(
            "async () => { const r = await fetch('https://chatgpt.com/api/auth/session', "
            "{credentials:'include'}); return await r.json(); }"
        )
        session_json = __import__("json").dumps(data, ensure_ascii=False, separators=(",", ":"))
        access_token = (data or {}).get("accessToken")
    except Exception:
        pass
    return session_token, access_token, session_json


async def _click_submit(page):
    btn = page.locator(SUBMIT_BTN).first
    await btn.wait_for(state="visible", timeout=20_000)
    await btn.click()


async def _code_inputs(page):
    """Return visible verification inputs across the auth page variants."""
    selectors = (
        CODE_INPUT,
        'input[type="tel"]',
        'input[type="text"]',
        'input:not([type="hidden"]):not([type="email"]):not([type="password"])',
    )
    seen = set()
    matches = []
    for selector in selectors:
        loc = page.locator(selector)
        for index in range(await loc.count()):
            item = loc.nth(index)
            try:
                if not await item.is_visible():
                    continue
                handle = await item.element_handle()
                if handle is None or id(handle) in seen:
                    continue
                seen.add(id(handle))
                matches.append(item)
            except Exception:
                continue
    return matches


async def _fill_code(page, code: str, progress: Progress | None = None):
    inputs = await _code_inputs(page)
    if not inputs:
        try:
            visible = page.locator('input:visible')
            details = []
            for index in range(min(await visible.count(), 8)):
                item = visible.nth(index)
                details.append(await item.evaluate("el => ({type: el.type, name: el.name, inputmode: el.inputMode, autocomplete: el.autocomplete, aria: el.getAttribute('aria-label'), maxlength: el.maxLength})"))
            body = (await page.inner_text("body"))[:240].replace("\n", " ")
            await _safe_progress(progress, f"验证码输入框未找到 visible={len(details)} inputs={details} body={body}")
        except Exception:
            await _safe_progress(progress, "验证码输入框未找到，页面结构无法读取")
        return False

    # Auth has used both one six-digit input and six one-character inputs.
    if len(inputs) >= len(code):
        for item, digit in zip(inputs[: len(code)], code):
            await item.fill(digit)
    else:
        await inputs[0].fill(code)
    return True


async def _handle_arkose(page, notify, progress) -> bool:
    """如出现 Arkose 验证码，等待操作员人工完成。"""
    if await captcha._arkose_present(page):
        await _safe_progress(progress, "需要人工打码")
        ok = await captcha.wait_for_arkose(page, notify=notify)
        if not ok:
            return False
        await _safe_progress(progress, "验证码已完成")
    return True


def _account_banned(text: str) -> bool:
    markers = ("account banned", "account is banned", "account suspended", "账号被封", "账号已被封", "suspended account", "利用政策")
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


async def _abort_if_banned(page, progress) -> bool:
    try:
        body = await page.inner_text("body")
    except Exception:
        return False
    if _account_banned(body):
        await _safe_progress(progress, "检测到账号被封，已终止注册流程")
        return True
    return False


async def register_account(
    account: MailAccount,
    proxy: str | None = None,
    notify: Callable[[], Awaitable[None] | None] | None = None,
    progress: Progress | None = None,
    headless: bool = False,
) -> dict:
    fp = fingerprint.generate()
    proxy_cfg = parse_proxy(proxy)
    result = {"email": account.ms_email, "status": "failed", "session_token": None, "access_token": None, "session_json": None, "account_name": None, "account_age": None, "error": None}
    existing_account = False
    account_name = None
    account_age = None

    async with async_playwright() as p:
        # Patchright's Windows build can ignore custom init scripts in true
        # headless mode, which leaves an obvious native headless fingerprint
        # and causes the auth OTP endpoint to return 403. Keep the requested
        # hidden mode unattended by running a real headed browser off-screen.
        effective_headless = False
        launch_kwargs = dict(
            headless=effective_headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
            ],
        )
        if headless:
            launch_kwargs["args"].extend(["--window-position=-32000,-32000", "--window-size=1280,720"])
        if proxy_cfg.server:
            launch_kwargs["proxy"] = proxy_cfg.to_patchright()
        browser = await p.chromium.launch(**launch_kwargs)

        context = await browser.new_context(
            user_agent=fp["user_agent"],
            viewport=fp["viewport"],
            locale=fp["locale"],
            timezone_id=fp["timezone_id"],
        )
        await context.add_init_script(fp["init_script"])
        page = await context.new_page()
        traced_responses: set[tuple[int, str]] = set()
        otp_validation_status: int | None = None
        otp_validation_body: str | None = None

        async def trace_response(response):
            nonlocal otp_validation_status, otp_validation_body
            url = response.url.split("?", 1)[0]
            if not (
                "/api/auth/" in url
                or url.endswith("/auth/login")
                or url.endswith("/email-verification")
                or url.endswith("/about-you")
                or "/api/accounts/" in url
            ):
                return
            key = (response.status, url)
            if key in traced_responses:
                return
            traced_responses.add(key)
            try:
                headers = await response.all_headers()
                content_type = headers.get("content-type", "-").split(";", 1)[0]
            except Exception:
                content_type = "-"
            await _safe_progress(progress, f"HTTP {response.status} {content_type} | {url}")
            if url.endswith("/api/accounts/email-otp/validate"):
                otp_validation_status = response.status
                if response.status >= 400:
                    try:
                        otp_validation_body = (await response.text())[:300].replace("\n", " ")
                    except Exception:
                        otp_validation_body = "<unreadable response>"
                    await _safe_progress(progress, f"OTP 验证响应 {response.status}: {otp_validation_body}")

        def on_response(response):
            asyncio.create_task(trace_response(response))

        page.on("response", on_response)
        try:
            # 1. 打开登录页
            await _safe_progress(progress, "打开登录页")
            await page.goto("https://chatgpt.com/auth/login", wait_until="domcontentloaded", timeout=60_000)
            await _safe_progress(
                progress,
                f"浏览器环境 hidden={headless} effective_headless={effective_headless} | UA={fp['user_agent']} | platform={fp['platform']} | viewport={fp['viewport']['width']}x{fp['viewport']['height']} | locale={fp['locale']} | timezone={fp['timezone_id']} | cpu={fp['hardware_concurrency']} memory={fp['device_memory']}",
            )
            try:
                browser_fp = await page.evaluate(
                    """() => ({webdriver: navigator.webdriver, platform: navigator.platform,
                        language: navigator.language, hardwareConcurrency: navigator.hardwareConcurrency,
                        deviceMemory: navigator.deviceMemory})"""
                )
                await _safe_progress(progress, f"页面指纹 webdriver={browser_fp.get('webdriver')} platform={browser_fp.get('platform')} language={browser_fp.get('language')} cpu={browser_fp.get('hardwareConcurrency')} memory={browser_fp.get('deviceMemory')}")
            except Exception:
                pass
            if await _abort_if_banned(page, progress):
                result["status"] = "banned"
                result["error"] = "account_banned"
                return result

            # 2. 填邮箱
            await _safe_progress(progress, "输入邮箱")
            email = page.locator(EMAIL_INPUT).first
            await email.wait_for(state="visible", timeout=30_000)
            await email.fill(account.ms_email)
            await page.wait_for_timeout(500)
            submit_time = datetime.datetime.now(datetime.timezone.utc)
            await _click_submit(page)
            await _safe_progress(progress, "邮箱已提交，等待验证码")

            # 3. 验证码：取件回填（只取提交后的新码，失败重试）
            code = await asyncio.to_thread(
                mail.fetch_code, account, None, proxy, config.MAIL_CODE_TIMEOUT, 8.0, submit_time
            )
            await _safe_progress(progress, f"取到验证码 {code}")
            for attempt in range(4):
                if not await _fill_code(page, code, progress):
                    await page.wait_for_timeout(2_000)
                    if not await _fill_code(page, code, progress):
                        raise TimeoutError("verification code input not found")
                await page.wait_for_timeout(500)
                await _click_submit(page)
                await _safe_progress(progress, f"验证码已提交（第 {attempt + 1} 次）")
                await page.wait_for_timeout(4000)
                if otp_validation_status is not None and otp_validation_status >= 400:
                    detail = otp_validation_body or f"HTTP {otp_validation_status}"
                    await _safe_progress(progress, f"验证码被服务器拒绝：{detail}")
                    result["error"] = f"otp_rejected | {detail}"
                    return result
                if await _abort_if_banned(page, progress):
                    result["status"] = "banned"
                    result["error"] = "account_banned"
                    return result
                body = await page.inner_text("body")
                if "verification code" not in body and "Check your inbox" not in body:
                    break
                await _safe_progress(progress, "验证码未通过，重新取码")
                code = await asyncio.to_thread(
                    mail.fetch_code, account, None, proxy, config.MAIL_CODE_TIMEOUT, 8.0, submit_time
                )

            # 4. 名字 + 年龄（已注册邮箱登录时无此步，直接跳过）
            await page.wait_for_timeout(3000)
            name = _random_name()
            age = _random_age()
            account_name = name
            account_age = age
            name_loc = page.locator(NAME_INPUT).first
            age_loc = page.locator(AGE_INPUT).first
            filled = False
            if await name_loc.count() > 0:
                await _safe_progress(progress, "填写名字与年龄")
                await name_loc.wait_for(state="visible", timeout=15_000)
                await name_loc.fill(name)
                filled = True
            if await age_loc.count() > 0:
                await age_loc.wait_for(state="visible", timeout=15_000)
                await age_loc.fill(str(age))
                filled = True
            if filled:
                await page.wait_for_timeout(500)
                await _click_submit(page)
                await _safe_progress(progress, f"资料已提交，当前 URL: {page.url}")
            else:
                existing_account = True
                await _safe_progress(progress, f"未出现资料填写（已注册邮箱登录），当前 URL: {page.url}")

            # 5. Arkose（如触发）
            await page.wait_for_timeout(3000)
            if not await _handle_arkose(page, notify, progress):
                result["error"] = "captcha_timeout"
                return result

            # 6. 等待登录完成
            await _safe_progress(progress, "等待登录完成")
            last_url = None
            for _ in range(60):
                if page.url != last_url:
                    last_url = page.url
                    await _safe_progress(progress, f"当前 URL: {last_url}")
                if "chatgpt.com" in page.url and "/auth" not in page.url:
                    break
                await page.wait_for_timeout(1000)

            session_token, access_token, session_json = await extract_tokens(context, page)
            await _safe_progress(progress, f"会话检查 URL={page.url} | session_cookie={'yes' if session_token else 'no'} | access_token={'yes' if access_token else 'no'}")
            # The auth frontend can leave an authenticated browser on an
            # `/email-verification` route error. Refresh the ChatGPT origin
            # before declaring the session unusable.
            if not session_token and not access_token and "auth.openai.com" in page.url:
                await _safe_progress(progress, "认证页未跳转，尝试恢复 ChatGPT 会话")
                try:
                    await page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=30_000)
                    await page.wait_for_timeout(5_000)
                    session_token, access_token, session_json = await extract_tokens(context, page)
                except Exception as exc:
                    await _safe_progress(progress, f"会话恢复失败：{type(exc).__name__}")
            if not session_token and not access_token:
                try:
                    url = page.url
                    body = await page.inner_text("body")
                    result["error"] = f"no_token | url={url} | body={body[:500]}"
                except Exception:
                    result["error"] = "no_token"
                return result

            result["status"] = "registered" if existing_account else "done"
            result["session_token"] = session_token
            result["access_token"] = access_token
            result["session_json"] = session_json
            result["account_name"] = account_name
            result["account_age"] = account_age
            return result
        except Exception as e:
            try:
                body = await page.inner_text("body")
            except Exception:
                body = ""
            if _account_banned(body):
                result["status"] = "banned"
                result["error"] = "account_banned"
            else:
                result["error"] = f"{type(e).__name__}: {e}"
            return result
        finally:
            try:
                await browser.close()
            except Exception:
                pass
