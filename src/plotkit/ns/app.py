"""NS 涡旋可视化应用入口：`python -m plotkit.ns.app [--port 8760] [--shot out.png]`。

页面是纯静态的 `static/ns.html` + `static/nsview.js`，数据全部走 `/api/ns/*`
（二进制帧，见 `plotkit.server.ns_app`）。`--shot` 会开一个 pywebview 窗口，
等页面渲染完成后截一张 PNG 再退出——用于自动核对渲染结果。
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from ..server.ns_app import router

STATIC = Path(__file__).resolve().parent.parent / "static"

__all__ = ["create_app", "main"]


def create_app() -> FastAPI:
    app = FastAPI(title="PlotKit · NS vortex", docs_url=None, redoc_url=None)
    app.include_router(router)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "ns.html", media_type="text/html")

    @app.get("/nsview.js")
    def nsview() -> FileResponse:
        return FileResponse(STATIC / "nsview.js", media_type="application/javascript")

    return app


def _serve(port: int) -> tuple[object, threading.Thread, int]:
    import uvicorn

    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while time.time() < deadline and not server.started:
        time.sleep(0.05)
    return server, thread, config.port


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NS 涡旋三维可视化")
    parser.add_argument("--port", type=int, default=8760)
    parser.add_argument("--shot", type=str, default="", help="截图到该 PNG 后退出")
    parser.add_argument("--seconds", type=float, default=6.0, help="截图前等待秒数")
    parser.add_argument("--t", type=float, default=None, help="打开时停在某个物理时间 t（0..1）")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=820)
    args = parser.parse_args(argv)

    server, _, port = _serve(args.port)
    url = f"http://127.0.0.1:{port}/"
    if args.t is not None:
        url += f"?t={args.t}"
    print(f"[ns] serving {url}", flush=True)

    if not args.shot:
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass
        return 0

    import base64

    import webview

    result: dict = {}
    window = webview.create_window("NS vortex", url, width=args.width, height=args.height,
                                   hidden=False, background_color="#05070b")

    def shoot() -> None:
        time.sleep(args.seconds)
        try:
            info = window.evaluate_js(
                "JSON.stringify({err: window.__nsErr || null,"
                " fps: (window.__ns && window.__ns.view.stats.fps) || 0,"
                " t: (window.__ns && window.__ns.S.t) || 0})")
            result["info"] = json.loads(info) if info else None
            data = window.evaluate_js("document.getElementById('gl').toDataURL('image/png')")
            if data and "," in data:
                blob = base64.b64decode(data.split(",", 1)[1])
                Path(args.shot).write_bytes(blob)
                result["bytes"] = len(blob)
            result["probe"] = json.loads(window.evaluate_js(
                "(() => { const v = window.__ns.view; const gl = v.gl;"
                " const px = new Uint8Array(4 * 4 * 4);"
                " gl.readPixels(Math.floor(gl.drawingBufferWidth*0.48), Math.floor(gl.drawingBufferHeight*0.5), 4, 4, gl.RGBA, gl.UNSIGNED_BYTE, px);"
                " return JSON.stringify({particles: v.particles ? v.particles.count : 0,"
                " vel: !!v.vel, tex: !!v.tex, center: Array.from(px.slice(0,8)),"
                " extent: v.extent, vmin: v.vmin, vmax: v.vmax}); })()"))
            result["overlay"] = json.loads(window.evaluate_js(
                "JSON.stringify({tau: document.getElementById('tau').textContent,"
                " diag: document.getElementById('diag').innerText.replace(/\s+/g,' ').slice(0,200),"
                " formulas: document.querySelectorAll('#fsvg').length,"
                " legend: !!document.getElementById('legend')})"))
        except Exception as exc:  # pragma: no cover
            result["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                window.destroy()
            except Exception:
                pass

    threading.Thread(target=shoot, daemon=True).start()
    webview.start(gui="edgechromium")
    try:
        server.should_exit = True
    except Exception:
        pass
    print(json.dumps(result, ensure_ascii=True), flush=True)
    return 0 if result.get("bytes") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
