"""桌面壳对比基准：pywebview(WebView2) vs Qt WebEngine。

两边跑同一份 FastAPI 应用、同一份静态前端、同样的演示数据（6 通道 × 2 万点），
只换外壳，量三件事：进程内到窗口就绪、到页面 loaded、稳态内存（含渲染子进程）。

用法：
    python tools/bench_shell.py            # 两个壳各跑一次，输出对照表
    python tools/bench_shell.py --probe qt # 只跑某个壳（内部用）
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _rss_tree() -> float | None:
    """本进程 + 全部子孙进程 RSS（MB）：WebView2 / QtWebEngineProcess 都是独立进程。"""
    try:
        import psutil  # type: ignore
    except Exception:
        return None
    try:
        proc = psutil.Process()
        total = proc.memory_info().rss
        for child in proc.children(recursive=True):
            try:
                total += child.memory_info().rss
            except Exception:
                pass
        return round(total / 1048576, 1)
    except Exception:
        return None


def probe_qt() -> int:
    """Qt WebEngine 探针：与 desktop 壳走同一条链路，只是把窗口换成 QWebEngineView。"""
    import time

    from PySide6.QtCore import QUrl
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication

    t0 = time.perf_counter()
    from plotkit.desktop.app import demo_figure
    from plotkit.desktop.server import serve
    from plotkit.server.app import create_app

    figure = demo_figure(6, 20_000)
    app = create_app(figure, title="PlotKit Qt")
    handle = serve(app)
    t_serve = time.perf_counter()

    qapp = QApplication(sys.argv)
    view = QWebEngineView()
    view.resize(1280, 800)
    result: dict[str, object] = {
        "shell": "qt-webengine",
        "import_and_server_ms": round((t_serve - t0) * 1000, 1),
        "url": handle.url,
    }

    def on_load(ok: bool) -> None:
        result["page_loaded_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        result["load_ok"] = bool(ok)

        def _done(title) -> None:
            result["page_title"] = title
            result["rss_tree_mb"] = _rss_tree()
            print(json.dumps(result, ensure_ascii=False), flush=True)
            qapp.quit()

        view.page().runJavaScript("document.title", _done)

    view.loadFinished.connect(on_load)
    view.show()
    view.load(QUrl(handle.url))
    qapp.exec()
    handle.stop()
    return 0


def _run(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    for line in reversed(proc.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"error": (proc.stderr or proc.stdout)[-600:]}


def main(argv: list[str]) -> int:
    if "--probe" in argv:
        kind = argv[argv.index("--probe") + 1]
        return probe_qt() if kind == "qt" else 0

    py = sys.executable
    pywebview = _run([py, "-m", "plotkit.desktop", "--selftest"])
    qt = _run([py, str(Path(__file__).resolve()), "--probe", "qt"])

    rows = [
        ("壳", "pywebview + WebView2", "Qt WebEngine"),
        ("到窗口创建", f"{pywebview.get('window_create_ms')} ms + 导入 {pywebview.get('import_and_figure_ms')} ms", "见导入+服务"),
        ("到页面 loaded", f"{pywebview.get('page_loaded_ms')} ms", f"{qt.get('page_loaded_ms')} ms"),
        ("稳态内存（含子进程）", f"{pywebview.get('rss_mb')} MB", f"{qt.get('rss_tree_mb')} MB"),
        ("首帧渲染", f"{pywebview.get('render_roundtrip_ms')} ms", "—"),
        ("二次渲染（缓存）", f"{pywebview.get('render_roundtrip_hot_ms')} ms", "—"),
        ("页面标题", str(pywebview.get("page_title")), str(qt.get("page_title"))),
    ]
    width = max(len(r[0]) for r in rows) + 2
    for left, a, b in rows:
        print(f"{left:<{width}}{a:<28}{b}")
    if qt.get("error"):
        print("\nQt 探针错误：", qt["error"][-400:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
