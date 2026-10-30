"""排障用：抓页面控制台日志 + DOM 状态（确认是渲染失败还是 JS 报错）。"""

from __future__ import annotations

import sys

import numpy as np

import plotkit as pk
from plotkit.server.live import LiveServer

PROBES = [
    "document.title",
    "document.querySelectorAll('.js-plotly-plot').length",
    "document.querySelectorAll('#plot canvas').length",
    "document.body.innerText.slice(0,400)",
]


def main() -> int:
    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView

    class DiagPage(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
            print(f"[console {level}] {message} ({source}:{line})")

    t = np.linspace(0, 1, 801)
    fig = pk.figure(title="diag", theme="netlab-dark")
    fig.add_data("t", t, role="coord")
    fig.add_data("v", np.sin(t), role="series")
    fig.add_plot("line", x="t", y="v", label="v")

    server = LiveServer(fig)
    url = server.start()
    print("url", url)

    app = QApplication(sys.argv[:1])
    view = QWebEngineView()
    page = DiagPage(view)
    view.setPage(page)
    view.resize(1200, 760)
    view.loadFinished.connect(lambda ok: print("loadFinished", ok))
    view.load(QUrl(url))

    def ask(i: int = 0) -> None:
        if i >= len(PROBES):
            pix = view.grab()
            pix.save("docs/shot.png")
            print("saved docs/shot.png", pix.width(), pix.height())
            server.stop()
            app.quit()
            return
        probe = PROBES[i]

        def done(res, probe=probe, i=i):
            print("PROBE:", probe, "=>", res)
            QTimer.singleShot(500, lambda: ask(i + 1))

        page.runJavaScript(probe, done)

    QTimer.singleShot(2500, ask)
    app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
