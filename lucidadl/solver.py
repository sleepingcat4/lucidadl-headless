"""Optional Camoufox clearance backend.

Challenge interaction adapted from art3m4ik3/cloudflare-solver (MIT).
Upstream revision: 162b70aad8d81781fd32ab14f15dfbd21566e615
https://github.com/art3m4ik3/cloudflare-solver
"""

import asyncio
import os
import random
import sys
import time

# Upstream license (retained in packaged source):
# MIT License
# 
# Copyright (c) 2025 art3m4ik3
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


def _camoufox():
    try:
        from camoufox.async_api import AsyncCamoufox
        return AsyncCamoufox
    except ImportError as exc:
        raise RuntimeError(
            'Optional solver missing. Install: pip install "lucidadl[solver]"; '
            'then run: python -m camoufox fetch'
        ) from exc


async def installed():
    try:
        _camoufox()
        from camoufox.pkgman import camoufox_path, LAUNCH_FILE, OS_NAME
        root = camoufox_path(download_if_missing=False)
        if OS_NAME == "mac":
            root = root / "Camoufox.app" / "Contents" / "Resources"
        return os.path.isfile(root / LAUNCH_FILE[OS_NAME])
    except Exception:
        return False


async def install():
    _camoufox()
    proc = await asyncio.create_subprocess_exec(sys.executable, "-m", "camoufox", "fetch")
    return await proc.wait() == 0


async def _click_challenge(page):
    for frame in page.frames:
        if frame.url.startswith("https://challenges.cloudflare.com/"):
            element = await frame.frame_element()
            box = await element.bounding_box()
            if not box:
                continue
            x = box["x"] + box["width"] / 9 + random.uniform(-5, 5)
            y = box["y"] + box["height"] / 2 + random.uniform(-5, 5)
            await page.mouse.move(x, y, steps=random.randint(10, 25))
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.mouse.click(x, y)
            return True
    return False


async def acquire(timeout=180):
    from .session import LUCIDA, is_challenged

    async def solve():
        async with _camoufox()(headless=True, os=["linux"]) as browser:
            ctx = await browser.new_context()
            try:
                page = await ctx.new_page()
                response = await page.goto(LUCIDA + "/", wait_until="domcontentloaded")
                if response is None:
                    raise RuntimeError("Lucida did not return a page")
                if not response.ok and not await is_challenged(page):
                    raise RuntimeError(f"Lucida returned HTTP {response.status}")
                next_click = time.monotonic() + 5
                while True:
                    if not await is_challenged(page):
                        from urllib.parse import urlsplit
                        if urlsplit(page.url).netloc != urlsplit(LUCIDA).netloc:
                            raise RuntimeError("Solver navigated away from lucida.to")
                        cookies = await ctx.cookies(LUCIDA)
                        cf = next((c["value"] for c in cookies
                                   if c["name"] == "cf_clearance"), None)
                        ua = await page.evaluate("() => navigator.userAgent")
                        if not ua:
                            raise RuntimeError("Solver returned no browser user agent")
                        return cf, ua
                    if time.monotonic() >= next_click:
                        await _click_challenge(page)
                        next_click = time.monotonic() + 5
                    await page.wait_for_timeout(1000)
            finally:
                await ctx.close()

    try:
        return await asyncio.wait_for(solve(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise RuntimeError("Cloudflare solver timed out; clearance was not saved") from exc
