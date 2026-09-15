"""人工打码桥接。

采用 headful（有头）浏览器：遇到 Arkose FunCaptcha 时，注册流程停在
验证码页面，通过 notify() 回调让 Web 面板提示操作员；操作员直接在
弹出的浏览器窗口里人工完成挑战，脚本轮询页面直到挑战完成（token
就绪 / iframe 消失 / URL 跳转），随后自动继续。
"""
from __future__ import annotations

import asyncio
import time

from . import config

# Arkose FunCaptcha 典型特征
_ARKOSE_SELECTORS = [
    'iframe[src*="funcaptcha"]',
    'iframe[src*="arkose"]',
    'iframe[src*="arkoselabs"]',
    'iframe[src*="chat.openai.com/fc"]',
    'div[class*="arkose"]',
    'iframe[title*="FunCaptcha"]',
]


async def _arkose_present(page) -> bool:
    for sel in _ARKOSE_SELECTORS:
        try:
            if await page.locator(sel).count() > 0:
                return True
        except Exception:
            continue
    return False


async def _arkose_token_ready(page) -> bool:
    """检测 Arkose 是否已完成：token 出现，或挑战 iframe 消失。"""
    try:
        has_token = await page.evaluate(
            "() => !!window.arkoseToken || !!window.__arkoseToken || "
            "!!document.querySelector('input[name=\"arkoseToken\"]')?.value"
        )
        if has_token:
            return True
    except Exception:
        pass
    # 挑战 iframe 消失 + 页面已不再有 arkose 且 URL 变化，视为完成
    return not await _arkose_present(page)


async def wait_for_arkose(page, notify=None, timeout: float = config.CAPTCHA_TIMEOUT) -> bool:
    """等待操作员人工完成 Arkose。返回是否成功（未超时）。"""
    deadline = time.time() + timeout
    notified = False
    while time.time() < deadline:
        if not await _arkose_present(page):
            # 可能还没加载出来，等一小会再判断
            await asyncio.sleep(1.0)
            if await _arkose_token_ready(page):
                return True
            # 尚未出现验证码，继续等
            if not await _arkose_present(page):
                continue
        if not notified:
            if notify:
                try:
                    r = notify()
                    if asyncio.iscoroutine(r):
                        await r
                except Exception:
                    pass
            notified = True
        await asyncio.sleep(config.CAPTCHA_POLL_INTERVAL)
    return False
