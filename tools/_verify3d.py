"""临时验证：WebGL 曲面视图（跑完即删）。"""
import sys, threading, time
import numpy as np
sys.path.insert(0, "src")
import plotkit as pk
from plotkit.server import create_app
from plotkit.desktop.server import serve
import webview

x = np.linspace(-2, 2, 60); y = np.linspace(-2, 2, 60)
X, Y = np.meshgrid(x, y)
Z = np.sin(np.sqrt(X**2 + Y**2)) * 2.0

fig = pk.figure(title="曲面视图")
fig.add_data("x", x, role="coord"); fig.add_data("y", y, role="coord")
fig.add_data("z", Z, role="field")
fig.add("surface", {"x": "x", "y": "y", "z": "z"})
fig.add_data("t", np.linspace(0, 1, 500), role="coord")
fig.add_data("s", np.sin(np.linspace(0, 6, 500)), role="series")
fig.add_plot("line", x="t", y="s", label="正弦")

handle = serve(create_app(fig))
out = {}

def probe():
    time.sleep(3.0)
    for _ in range(20):
        try:
            if window.evaluate_js("typeof PK3D !== 'undefined'"):
                break
        except Exception:
            pass
        time.sleep(0.5)
    window.evaluate_js("document.getElementById('btn-3d').click()")
    time.sleep(3.5)
    out["hud"] = window.evaluate_js("document.getElementById('plot3d-hud').textContent")
    out["err"] = window.evaluate_js("window.__err || null")
    out["layers"] = window.evaluate_js("(window.__view3d && window.__view3d.layers) ? window.__view3d.layers.map(l => l.mode + ':' + l.count) : 'n/a'")
    data = window.evaluate_js("document.getElementById('plot3d').toDataURL('image/png')")
    out["bytes"] = len(data or "")
    import base64
    if data and "," in data:
        open("docs/_verify3d.png", "wb").write(base64.b64decode(data.split(",", 1)[1]))
    print(out, flush=True)
    window.destroy()

window = webview.create_window("verify", handle.url, width=900, height=650, hidden=False)
threading.Thread(target=probe, daemon=True).start()
webview.start(gui="edgechromium", private_mode=True)
handle.server.should_exit = True
