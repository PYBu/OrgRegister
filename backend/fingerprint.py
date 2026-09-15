"""随机浏览器指纹 —— 每次注册随机化，降低风控关联。

patchright 本身抹掉 webdriver 痕迹；这里再叠加：
- 随机 User-Agent（Chrome 版本池）
- 随机 viewport / 语言 / 时区 / 平台
- 随机硬件参数（CPU 核数、内存）
- WebGL renderer / canvas 噪声注入
"""
from __future__ import annotations

import random
import secrets

_UA_CHROME = [
    "Chrome/124.0.0.0",
    "Chrome/125.0.0.0",
    "Chrome/126.0.0.0",
    "Chrome/127.0.0.0",
    "Chrome/128.0.0.0",
]

# The bundled Chromium runs on Windows in this deployment. Keep the reported
# platform coherent with the UA; mixing a Linux UA with Win32 is an immediate
# automation/fraud signal and can break the auth challenge in headless mode.
_UA_OS = [
    ("Windows NT 10.0; Win64; x64", "Windows", "Win32"),
]

_VIEWPORTS = [
    (1920, 1080),
    (1366, 768),
    (1536, 864),
    (1440, 900),
    (2560, 1440),
    (1680, 1050),
]

_LANGS = ["en-US,en;q=0.9", "en-US,en;q=0.9,zh-CN;q=0.8", "en-US,en;q=0.8"]
_LOCALES = ["en-US", "en-GB", "en-US"]
_TZ = ["America/Los_Angeles", "America/Chicago", "America/New_York", "Europe/London"]

_GPU = [
    "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)",
    "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Ti Direct3D11 vs_5_0 ps_5_0)",
    "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)",
    "ANGLE (AMD, AMD Radeon RX 5700 XT Direct3D11 vs_5_0 ps_5_0)",
]


def _rand_canvas_noise() -> str:
    return secrets.token_hex(4)


def generate() -> dict:
    os_str, os_name, platform = random.choice(_UA_OS)
    chrome = random.choice(_UA_CHROME)
    vw, vh = random.choice(_VIEWPORTS)
    ua = (
        f"Mozilla/5.0 ({os_str}) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) {chrome} Safari/537.36"
    )
    locale = random.choice(_LOCALES)
    tz = random.choice(_TZ)
    hw_concurrency = random.choice([4, 6, 8, 12, 16])
    device_memory = random.choice([4, 8, 16])
    gpu = random.choice(_GPU)

    init_script = f"""
(() => {{
  // navigator 硬件/语言
  const define = (target, key, value) => {{
    // Chromium's Navigator getters can reject a replacement getter in headless
    // mode. A concrete value works on both the prototype and the instance.
    try {{ Object.defineProperty(target, key, {{ value, configurable: true, enumerable: true }}); }} catch (_) {{}}
  }};
  // Chromium exposes these on Navigator.prototype; defining only on the
  // instance silently fails on some headless builds.
  define(Navigator.prototype, 'hardwareConcurrency', {hw_concurrency});
  define(Navigator.prototype, 'deviceMemory', {device_memory});
  define(Navigator.prototype, 'platform', '{platform}');
  define(Navigator.prototype, 'webdriver', undefined);
  define(navigator, 'hardwareConcurrency', {hw_concurrency});
  define(navigator, 'deviceMemory', {device_memory});
  define(navigator, 'platform', '{platform}');
  define(navigator, 'webdriver', undefined);
  window.chrome = {{ runtime: {{}}, loadTimes: () => ({{}}) }};
  window.navigator.permissions = window.navigator.permissions || {{ query: async () => ({{ state: 'granted' }}) }};
  // WebGL 指纹
  const getParam = (gl, p) => {{
    const e = gl.getExtension('WEBGL_debug_renderer_info');
    if (p === 'UNMASKED_VENDOR_WEBGL' || p === 'UNMASKED_RENDERER_WEBGL') {{
      return e ? gl.getParameter(e[p]) : gl.getParameter(p);
    }}
    return gl.getParameter(p);
  }};
  const origGetParameter = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function(p) {{
    if (p === 37445) return 'Google Inc. (NVIDIA)';
    if (p === 37446) return '{gpu}';
    return origGetParameter.call(this, p);
  }};
  WebGL2RenderingContext.prototype.getParameter = function(p) {{
    if (p === 37445) return 'Google Inc. (NVIDIA)';
    if (p === 37446) return '{gpu}';
    return origGetParameter.call(this, p);
  }};
  // canvas 噪声
  const noise = '{_rand_canvas_noise()}';
  const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
  HTMLCanvasElement.prototype.toDataURL = function(type, ...args) {{
    if (type === 'image/png' && this.width === 220 && this.height === 30) return origToDataURL.apply(this, [type, ...args]);
    return origToDataURL.apply(this, [type, ...args]);
  }};
}})();
"""

    return {
        "user_agent": ua,
        "viewport": {"width": vw, "height": vh},
        "locale": locale,
        "timezone_id": tz,
        "os": os_name,
        "platform": platform,
        "hardware_concurrency": hw_concurrency,
        "device_memory": device_memory,
        "init_script": init_script,
    }
