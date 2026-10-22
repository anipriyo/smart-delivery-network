"""Take the report's screenshots of the running dashboard.

Drives a headless Chromium browser (Brave or Chrome) over the DevTools
protocol at desktop width (1440 px) in the light theme, and saves PNGs into
report/screenshots/. The browser runs with its own throwaway profile and is
closed again at the end.

1. Start the app (it must use the defaults: seed 42, 5 warehouses, 80 customers):
       ~/.venvs/analysis/bin/streamlit run app.py
2. From the project root:
       ~/.venvs/analysis/bin/python report/take_screenshots.py
   Options: --url http://localhost:8501  --browser "/path/to/Chrome"

The basemap tiles come from CARTO, so this needs internet.
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket  # websocket-client, installed with streamlit

OUT = Path(__file__).resolve().parent / "screenshots"
WIDTH = 1440
MAX_HEIGHT = 1700
BROWSERS = [
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]

# (file name, page path, JavaScript to run once the page is ready, or None)
SHOTS = [
    ("network_map.png", "/", None),
    ("river_crossing.png", "/river", None),  # default mode: delivery van, road bridges only
    ("coverage_planner.png", "/coverage", None),
    # KD-tree search walkthrough, final step: the default search area, which stops
    # were visited and which subtrees were skipped.
    ("walkthrough_kdtree_search.png", "/walkthrough",
     "[...document.querySelectorAll('button')].find(b => b.innerText.trim() === 'KD-tree search').click()"),
]


class Tab:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=120, suppress_origin=True)
        self.next_id = 0

    def call(self, method: str, **params) -> dict:
        self.next_id += 1
        self.ws.send(json.dumps({"id": self.next_id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.next_id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expression: str):
        res = self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        return res.get("result", {}).get("value")

    def resize(self, height: int) -> None:
        self.call("Emulation.setDeviceMetricsOverride", width=WIDTH, height=height, deviceScaleFactor=1, mobile=False)

    def wait_idle(self, settle: float = 6.0, timeout: float = 90.0) -> None:
        """Wait until the Streamlit script has finished and the maps have had time to load tiles."""
        start = time.time()
        idle_since = None
        while time.time() - start < timeout:
            idle = self.js(
                "(() => { const a = document.querySelector('[data-testid=\"stApp\"]');"
                " return !!a && a.dataset.testScriptState === 'notRunning'"
                " && a.dataset.testConnectionState === 'CONNECTED'"
                " && document.querySelectorAll('[data-testid=\"stDeckGlJsonChart\"] canvas').length > 0; })()"
            )
            if idle:
                idle_since = idle_since or time.time()
                if time.time() - idle_since >= settle:
                    return
            else:
                idle_since = None
            time.sleep(0.5)
        raise TimeoutError("the app did not finish rendering")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8501")
    ap.add_argument("--browser", default=next((b for b in BROWSERS if Path(b).exists()), None))
    ap.add_argument("--port", type=int, default=9333, help="DevTools port for the headless browser")
    args = ap.parse_args()
    if not args.browser:
        raise SystemExit("No Chromium browser found; pass --browser")

    OUT.mkdir(exist_ok=True)
    profile = tempfile.mkdtemp(prefix="sdn_shots_")
    proc = subprocess.Popen(
        [args.browser, "--headless=new", f"--remote-debugging-port={args.port}", "--remote-allow-origins=*",
         f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check", "--hide-scrollbars",
         f"--window-size={WIDTH},1000", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{args.port}/json/list"))
                pages = [t for t in targets if t.get("type") == "page"]
                if pages:
                    break
            except OSError:
                pass
            time.sleep(0.5)
        else:
            raise SystemExit("headless browser did not start")

        tab = Tab(pages[0]["webSocketDebuggerUrl"])
        tab.call("Page.enable")
        tab.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "light"}])
        for name, path, action in SHOTS:
            tab.resize(1000)
            tab.call("Page.navigate", url=args.url.rstrip("/") + path)
            time.sleep(1.5)
            tab.wait_idle()
            if action:
                tab.js(action)
                time.sleep(1.5)
                tab.wait_idle()
            # Grow the viewport to the page's content so nothing is cut off.
            height = tab.js("document.querySelector('[data-testid=\"stMain\"]').scrollHeight")
            tab.resize(min(int(height or 1000), MAX_HEIGHT))
            time.sleep(1.0)
            tab.wait_idle(settle=4.0)
            png = base64.b64decode(tab.call("Page.captureScreenshot", format="png")["data"])
            (OUT / name).write_bytes(png)
            print(f"saved {OUT / name} ({len(png) // 1024} KB)")
        tab.ws.close()
    finally:
        proc.terminate()  # only the browser this script started
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    main()
