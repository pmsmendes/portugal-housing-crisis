"""Screenshot every dashboard page for the README, with headless Chrome driven over the DevTools protocol.

Usage (with the dashboard running, e.g. `uv run streamlit run app/Home.py --server.port 8502`):
    uv run python scripts/capture_dashboard.py [--url http://localhost:8502] [--chrome PATH]

Each page is captured once Streamlit reports it idle, at the height of its content (capped), into
reports/figures/dashboard/<page>.png. Thin script: needs Chrome or Chromium and nothing beyond the
project dependencies (it uses the websocket client that ships with Streamlit's tornado).
"""

import argparse
import asyncio
import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from tornado.websocket import websocket_connect

from pthousing.config import FIGURES

PAGES = {
    "home": "",
    "geographic": "Geographic",
    "trends": "Trends",
    "explanatory": "Explanatory",
    "simulator": "Simulator",
}
WIDTH, MIN_H, MAX_H = 1400, 900, 2600
DEBUG_PORT = 9333
CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
    "chromium-browser",
)
IDLE = """(() => {
  const running = document.querySelector('[data-testid="stStatusWidget"]');
  const skeleton = document.querySelector('[data-testid="stSkeleton"]');
  return !!document.querySelector('h1') && !running && !skeleton;
})()"""
HIDE_TOOLBAR = (
    "document.head.insertAdjacentHTML('beforeend', '<style>"
    "[data-testid=stToolbar],[data-testid=stDecoration],header{display:none!important}</style>')"
)
CONTENT_HEIGHT = "document.querySelector('[data-testid=stMain]').scrollHeight"


def find_chrome(given: str | None) -> str:
    for candidate in (given, *CHROME_CANDIDATES):
        if candidate and (Path(candidate).exists() or shutil.which(candidate)):
            return candidate
    raise SystemExit("Chrome or Chromium not found: pass --chrome PATH")


class Devtools:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    async def call(self, method: str, **params) -> dict:
        self.n += 1
        mid = self.n
        await self.ws.write_message(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.read_message())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    async def evaluate(self, expression: str):
        result = await self.call("Runtime.evaluate", expression=expression, returnByValue=True)
        return result.get("result", {}).get("value")

    async def wait_idle(self, timeout: float = 90) -> bool:
        start, stable = time.time(), 0
        while time.time() - start < timeout:
            stable = stable + 1 if await self.evaluate(IDLE) else 0
            if stable >= 4:
                return True
            await asyncio.sleep(1)
        return False

    async def resize(self, height: int) -> None:
        await self.call(
            "Emulation.setDeviceMetricsOverride",
            width=WIDTH,
            height=height,
            deviceScaleFactor=1,
            mobile=False,
        )


async def capture(url: str, chrome: str, out: Path) -> None:
    profile = tempfile.mkdtemp(prefix="pthousing-chrome-")
    proc = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={profile}",
            "--remote-allow-origins=*",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(40):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json"))
                break
            except OSError:
                time.sleep(0.5)
        else:
            raise SystemExit("Chrome did not start")
        page = next(t for t in targets if t["type"] == "page")
        tools = Devtools(
            await websocket_connect(page["webSocketDebuggerUrl"], max_message_size=2**26)
        )
        await tools.call("Page.enable")
        for name, path in PAGES.items():
            await tools.resize(1000)
            await tools.call("Page.navigate", url=f"{url.rstrip('/')}/{path}")
            await asyncio.sleep(3)
            idle = await tools.wait_idle()
            await asyncio.sleep(4)  # charts draw after the script has finished
            await tools.evaluate(HIDE_TOOLBAR)
            height = int(min(max(await tools.evaluate(CONTENT_HEIGHT) or MIN_H, MIN_H), MAX_H))
            await tools.resize(height)
            await asyncio.sleep(4)
            await tools.wait_idle(30)
            shot = await tools.call("Page.captureScreenshot", format="png")
            (out / f"{name}.png").write_bytes(base64.b64decode(shot["data"]))
            print(f"{name}: {'idle' if idle else 'NOT IDLE'}, {WIDTH}x{height}")
    finally:
        proc.terminate()
        shutil.rmtree(profile, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8502", help="where the dashboard runs")
    parser.add_argument(
        "--chrome", help="path to Chrome or Chromium (found automatically if omitted)"
    )
    args = parser.parse_args()
    out = FIGURES / "dashboard"
    out.mkdir(parents=True, exist_ok=True)
    asyncio.run(capture(args.url, find_chrome(args.chrome), out))


if __name__ == "__main__":
    main()
