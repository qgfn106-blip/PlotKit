"""开发自检：把 PlotKit 页面在 QtWebEngine 里真渲染一次并截图（不弹窗）。

    PYTHONPATH=src python tools/render_shot.py docs/shot.png

用途：CI/无头环境验证"前端真的画出图了"，而不是只验证接口返回 200。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

import plotkit as pk
from plotkit.server.live import LiveServer


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/shot.png").resolve()

    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWebEngineWidgets import QWebEngineView

    t = np.linspace(0, 1, 8001)
    fig = pk.figure(
        title="自检 · 双主题", size=(11, 6), theme="netlab-dark", ncols=2, subplots=2
    )
    fig.add_data("t", t, unit="s", role="coord")
    fig.add_data("vin", np.where(t < 0.05, 5.0, 0.0), unit="V", role="series")
    fig.add_data("vout", 5 * (1 - np.exp(-t / 0.09)), unit="V", role="series")
    fig.add_plot("line", x="t", y="vin", label="Vin", subplot=0, color="#ff8a65")
    fig.add_plot("line", x="t", y="vout", label="Vout", subplot=0, color="#4fc3f7")
    fig.add_plot(
        "scatter",
        x="t",
        y="vout",
        label="采样点",
        subplot=1,
        mode="markers",
        markersize=3,
    )
    fig.add_plot("bar", x=["a", "b", "c"], y=[3, 7, 5], label="柱", subplot=1)
    fig.set_view(0, xlabel="t / s", ylabel="V / V")
    fig.set_view(1, xlabel="t / s", ylabel="V / V")

    server = LiveServer(fig)
    url = server.start()

    app = QApplication(sys.argv[:1])
    view = QWebEngineView()
    view.resize(1400, 800)
    view.load(QUrl(url))

    def grab() -> None:
        pix = view.grab()
        out.parent.mkdir(parents=True, exist_ok=True)
        ok = pix.save(str(out))
        print(
            f"screenshot -> {out} ({'ok' if ok else 'FAILED'}, {pix.width()}x{pix.height()})"
        )
        server.stop()
        app.quit()

    QTimer.singleShot(3500, grab)
    app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
