"""临时验证脚本：在真实 WebView2 里检查三维装饰层是否画出来。用完即删。"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import plotkit as pk  # noqa: E402
from plotkit.desktop.server import serve  # noqa: E402
from plotkit.server import create_app  # noqa: E402


def make_figure() -> pk.Figure:
    x = np.linspace(-3, 3, 60)
    y = np.linspace(-3, 3, 60)
    X, Y = np.meshgrid(x, y)
    Z = np.sin(np.hypot(X, Y)) * 2.0
    fig = pk.figure(size=(6, 4.5), dpi=100)
    fig.add("surface", {"x": X, "y": Y, "z": Z})
    fig.set_view(0, elev=26, azim=-58)

    # 时间轴用的轨迹（带 t），绕表面跑一圈
    n = 600
    t = np.linspace(0, 6 * np.pi, n)
    fig.add_data("tt", t, role="coord")
    fig.add_data("tx", 2.2 * np.cos(t), role="series")
    fig.add_data("ty", 2.2 * np.sin(t), role="series")
    fig.add_data("tz", 1.4 + 0.9 * np.sin(2 * t), role="series")
    fig.add("line3d", {"x": "tx", "y": "ty", "z": "tz", "t": "tt"})
    return fig


def main() -> int:
    import webview

    fig = make_figure()
    app = create_app(fig, title="deco-check")
    handle = serve(app)
    print("url", handle.url, flush=True)

    window = webview.create_window(
        "deco-check", handle.url, width=1000, height=720, hidden=True
    )
    result: dict[str, object] = {}

    def probe() -> None:
        time.sleep(2.0)
        try:
            window.show()
            window.evaluate_js("document.getElementById('btn-3d').click()")
            time.sleep(2.5)
            stats = window.evaluate_js(
                """
                (function () {
                  const deco = document.getElementById('plot3d-deco');
                  const gl = document.getElementById('plot3d');
                  const ctx = deco.getContext('2d');
                  const d = ctx.getImageData(0, 0, deco.width, deco.height).data;
                  let painted = 0;
                  for (let i = 3; i < d.length; i += 4) if (d[i] > 0) painted++;
                  return JSON.stringify({
                    w: deco.width, h: deco.height,
                    painted: painted,
                    decoBytes: deco.toDataURL().length,
                    glBytes: gl.toDataURL().length,
                    err: window.__err || null,
                  });
                })()
                """
            )
            result["stats"] = stats
            # 模拟 Alt+拖 框选，验证区域统计
            window.evaluate_js(
                """
                (function () {
                  const c = document.getElementById('plot3d');
                  const r = c.getBoundingClientRect();
                  const mk = (type, x, y, extra) => new PointerEvent(type, Object.assign({
                    clientX: r.left + x, clientY: r.top + y, bubbles: true, pointerId: 1,
                  }, extra || {}));
                  c.dispatchEvent(mk('pointerdown', r.width * 0.3, r.height * 0.3, { altKey: true }));
                  c.dispatchEvent(mk('pointermove', r.width * 0.7, r.height * 0.7, { altKey: true }));
                  c.dispatchEvent(mk('pointerup', r.width * 0.7, r.height * 0.7, { altKey: true }));
                })()
                """
            )
            time.sleep(1.2)
            result["region"] = window.evaluate_js(
                "(document.getElementById('plot3d-region').textContent || '').slice(0, 160)"
            )
            window.evaluate_js(
                """
                (function () {
                  const sl = document.getElementById('plot3d-slider');
                  sl.value = String(Math.floor(sl.max * 0.5));
                  sl.dispatchEvent(new Event('input', { bubbles: true }));
                })()
                """
            )
            time.sleep(0.4)
            result["timeline_mid"] = window.evaluate_js(
                "(document.getElementById('plot3d-time').textContent || '') + ' | hidden=' + document.getElementById('plot3d-timeline').hidden"
            )
            window.evaluate_js("document.getElementById('btn-3d-play').click()")
            time.sleep(1.0)
            window.evaluate_js("document.getElementById('btn-3d-play').click()")
            result["timeline_play"] = window.evaluate_js(
                "document.getElementById('plot3d-time').textContent || ''"
            )
            shot = window.evaluate_js(
                "document.getElementById('plot3d').toDataURL('image/png')"
            )
            if isinstance(shot, str) and shot.startswith("data:image/png;base64,"):
                import base64

                out = (
                    Path(__file__).resolve().parents[1] / "docs" / "_deco_check_gl.png"
                )
                out.write_bytes(base64.b64decode(shot.split(",", 1)[1]))
                result["gl_png"] = str(out)
            deco_shot = window.evaluate_js(
                """
                (function () {
                  const gl = document.getElementById('plot3d');
                  const de = document.getElementById('plot3d-deco');
                  const c = document.createElement('canvas');
                  c.width = gl.width; c.height = gl.height;
                  const g = c.getContext('2d');
                  g.drawImage(gl, 0, 0);
                  g.drawImage(de, 0, 0, c.width, c.height);
                  return c.toDataURL('image/png');
                })()
                """
            )
            if isinstance(deco_shot, str) and deco_shot.startswith(
                "data:image/png;base64,"
            ):
                import base64

                out = (
                    Path(__file__).resolve().parents[1]
                    / "docs"
                    / "_deco_check_overlay.png"
                )
                out.write_bytes(base64.b64decode(deco_shot.split(",", 1)[1]))
                result["deco_png"] = str(out)
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                window.destroy()
            except Exception:
                pass

    threading.Thread(target=probe, daemon=True).start()
    webview.start(gui="edgechromium", private_mode=True)
    handle.server.should_exit = True
    print(result, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
