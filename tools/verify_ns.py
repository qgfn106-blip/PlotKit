"""NS 页面的规模与动画一致性验收（任务书 §12）。

用法：
    python tools/verify_ns.py                 # 全跑（规模 + 一致性）
    python tools/verify_ns.py --scale-only     # 只跑规模
    python tools/verify_ns.py --counts 100000,500000

为什么要开真窗口：WebGL 的 requestAnimationFrame 在隐藏窗口里会被挂起，
fps 与时间轴都不会动，测出来全是 0。所以这里用可见窗口。
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plotkit.desktop.server import serve  # noqa: E402
from plotkit.ns.app import create_app  # noqa: E402

READ_FPS = "JSON.stringify({fps: (window.__ns && __ns.S.fps) || 0, n: __ns.S.particles, err: (window.__nsErr||[]).join('|')})"
READ_DIAG = "JSON.stringify({t: __ns.S.t, diag: document.getElementById('diag').innerText.replace(/\\s+/g, ' ').trim()})"
SEED = (
    "(function(n){ __ns.S.particles = n; __ns.view.seedParticles(n); return n; })(%d)"
)
SET_T = (
    "(function(v){ const k = document.getElementById('scrub'); "
    "k.value = String(Math.round(sliderOfT(v) * 1000)); "
    "k.dispatchEvent(new Event('input', {bubbles:true})); return __ns.S.t; })(%s)"
)


def _js(window, code: str):
    try:
        raw = window.evaluate_js(code)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
    return {"raw": raw}


def main(argv: list[str] | None = None) -> int:
    import webview

    ap = argparse.ArgumentParser()
    ap.add_argument("--counts", default="100000,500000,1000000,2000000")
    ap.add_argument("--scale-only", action="store_true")
    ap.add_argument("--seconds", type=float, default=3.0, help="每档稳定时间")
    ap.add_argument("--out", default="docs/ns_scale.json")
    args = ap.parse_args(argv)

    counts = [int(c) for c in args.counts.split(",") if c.strip()]
    app = create_app()
    handle = serve(app)
    window = webview.create_window(
        "ns-verify", handle.url + "?t=0.5", width=1280, height=820, hidden=True
    )
    out: dict = {"url": handle.url, "scale": [], "consistency": {}}

    def _step(name, fn):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            out.setdefault("errors", {})[name] = f"{type(exc).__name__}: {exc}"[:160]
            return None

    def job() -> None:
        time.sleep(2.0)
        window.show()  # 必须可见，否则 rAF 停摆
        time.sleep(4.0)

        for n in counts:
            _js(window, SEED % n)
            time.sleep(args.seconds)
            row = _js(window, READ_FPS)
            row["requested"] = n
            out["scale"].append(row)

        if not args.scale_only:
            # 1) 跳转确定性：同一 t 读两次诊断应完全一致
            _js(window, SET_T % "0.7")
            time.sleep(1.2)
            a = _js(window, READ_DIAG)
            time.sleep(1.2)
            b = _js(window, READ_DIAG)
            out["consistency"]["jump_is_deterministic"] = a.get("diag") == b.get("diag")

            # 2) 倍速不改物理：换倍速后回到同一 t，诊断必须一致
            _js(
                window,
                "(function(){const r=document.getElementById('kr'); if(r){r.value='8'; r.dispatchEvent(new Event('input',{bubbles:true}));}})()",
            )
            time.sleep(0.4)
            _js(window, SET_T % "0.2")
            time.sleep(1.0)
            _js(window, SET_T % "0.7")
            time.sleep(1.2)
            c = _js(window, READ_DIAG)
            out["consistency"]["speed_does_not_change_physics"] = a.get(
                "diag"
            ) == c.get("diag")

            # 3) 暂停/继续：时间只能前进，不能跳回
            _js(window, "document.getElementById('play').click()")
            time.sleep(1.0)
            _js(window, "document.getElementById('play').click()")
            t1 = _js(window, READ_DIAG).get("t")
            time.sleep(0.3)
            _js(window, "document.getElementById('play').click()")
            time.sleep(0.6)
            _js(window, "document.getElementById('play').click()")
            t2 = _js(window, READ_DIAG).get("t")
            out["consistency"]["resume_moves_forward"] = bool(
                isinstance(t1, (int, float))
                and isinstance(t2, (int, float))
                and t2 >= t1
            )

            # 4) 相机旋转不改数据（必须先暂停：播放时 diag 本来就随时间变）
            if _js(window, "JSON.stringify({p: __ns.S.playing})").get("p"):
                _js(window, "document.getElementById('play').click()")
                time.sleep(0.4)
            before = _js(window, READ_DIAG).get("diag")
            window.evaluate_js(
                """
                (function(){
                  const c = document.getElementById('gl');
                  const r = c.getBoundingClientRect();
                  const ev = (type, dx, dy) => new PointerEvent(type, {clientX: r.left+dx, clientY: r.top+dy, bubbles:true, pointerId:1});
                  c.dispatchEvent(ev('pointerdown', r.width*0.5, r.height*0.5));
                  c.dispatchEvent(ev('pointermove', r.width*0.7, r.height*0.4));
                  c.dispatchEvent(ev('pointerup', r.width*0.7, r.height*0.4));
                })()
                """
            )
            time.sleep(0.8)
            after = _js(window, READ_DIAG).get("diag")
            out["consistency"]["camera_does_not_change_data"] = before == after

        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(out, ensure_ascii=False), flush=True)
        try:
            window.destroy()
        except Exception:
            pass

    threading.Thread(target=job, daemon=True).start()
    webview.start(
        gui="edgechromium",
        private_mode=False,
        storage_path=str(Path.home() / f".plotkit-nsverify-{int(time.time())}"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
