"""验收：主查看器里 volume + particles 两个新图层的真机渲染。"""
import base64
import json
import pathlib
import threading
import time

import numpy as np
import webview

import plotkit as pk
from plotkit.server.app import create_app

OUT = pathlib.Path("docs/web3d_volume.png")

STATE = (
    "JSON.stringify({cls: document.body.className, "
    "cw: (document.getElementById('plot3d') || {}).width, "
    "ch: (document.getElementById('plot3d') || {}).height, "
    "hud: (document.getElementById('plot3d-hud') || {}).textContent, "
    "volErr: window.__volErr || null, "
    "vol: window.__vol || null, "
    "layers: (window.__pk3d && 0) || null, "
    "nl: (window.__ns3dN || null), "
    "lay: window.__volLayer || null, "
    "err: window.__err || null})"
)


def build_figure():
    n = 40
    xs = np.linspace(-1, 1, n)
    X, Y, Z = np.meshgrid(xs, xs, xs, indexing="ij")
    r = np.sqrt(X ** 2 + Y ** 2)
    field = np.exp(-(r ** 2) / 0.18) * np.exp(-(Z ** 2) / 0.5) * (1.0 + 0.3 * np.sin(8 * Z))
    fig = pk.figure(size=(7, 5.4), dpi=110, title="volume + particles")
    for name, arr in (("x", xs), ("y", xs), ("z", xs), ("f", field)):
        fig.add_data(name, arr)
    fig.add("volume", {"x": "x", "y": "y", "z": "z", "values": "f"})
    t = np.linspace(0, 6 * np.pi, 20000)
    rad = 0.12 + 0.55 * t / t.max()
    fig.add_data("px", rad * np.cos(t))
    fig.add_data("py", rad * np.sin(t))
    fig.add_data("pz", -0.9 + 1.8 * t / t.max())
    fig.add_data("pc", rad)
    fig.add("particles", {"x": "px", "y": "py", "z": "pz", "c": "pc"},
            style={"markersize": 3.4, "opacity": 0.30})
    return fig


def main() -> int:
    import uvicorn

    app = create_app(build_figure())
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.time() + 20
    while time.time() < deadline and not server.started:
        time.sleep(0.05)
    port = config.port or server.servers[0].sockets[0].getsockname()[1]
    url = f"http://127.0.0.1:{port}/"

    info = {}

    def probe(win):
        time.sleep(6)
        try:
            win.evaluate_js("window.__err = null;")
            win.evaluate_js("window.onerror = function (m) { window.__err = String(m); };")
            win.evaluate_js(
                "window.addEventListener('unhandledrejection', function (e) {"
                " window.__err = String((e.reason && e.reason.message) || e.reason); });")
            info["page"] = win.evaluate_js(
                "JSON.stringify({ready: document.readyState, title: document.title,"
                " btns: document.querySelectorAll('button').length})")
            win.evaluate_js("(document.getElementById('btn-3d') || {click: function () {}}).click()")
            time.sleep(8)
            info["state"] = win.evaluate_js(STATE)
            data = win.evaluate_js("document.getElementById('plot3d').toDataURL('image/png')")
            info["bytes"] = len(data or "")
            if data and data.startswith("data:image/png;base64,"):
                OUT.write_bytes(base64.b64decode(data.split(",", 1)[1]))
        except Exception as exc:  # noqa: BLE001
            info["error"] = f"{type(exc).__name__}: {exc}"[:300]
        try:
            win.destroy()
        except Exception:
            pass

    win = webview.create_window("verify3d", url, width=1100, height=760)
    threading.Thread(target=probe, args=(win,), daemon=True).start()
    try:
        webview.start(gui="edgechromium", private_mode=True,
                      storage_path=str(pathlib.Path.home() / f".pk-vol-{int(time.time())}"))
    finally:
        try:
            server.should_exit = True
        except Exception:
            pass
    print(json.dumps(info, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
