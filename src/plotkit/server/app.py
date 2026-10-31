"""HTTP 服务：把一份 Figure 暴露成浏览器可用的页面 + JSON/binary 接口。

接口一览（docs/DESIGN_v0.md §6）：
  GET  /                     页面
  GET  /api/meta             版本 / 可用 kind / 主题
  GET  /api/spec             当前 spec
  PUT  /api/spec             全量替换 spec（D10：默认回写方式）
  GET  /api/datasets         命名数据集目录（前端下拉用）
  GET  /api/series           float32 二进制列（ArrayBuffer 通道）
  GET  /api/png              matplotlib 渲染的静态图
  GET  /api/layout           界面布局（面板宽/折叠/分组），属于"软件怎么摆"
  PUT  /api/layout           全量替换布局
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from ..backends import registry as reg
from ..spec.validate import SpecError, validate_spec
from ..store.downsample import downsample_xy
from .assets import STATIC_DIR

MAGIC = b"PK01"


def _binary_xyz(x: np.ndarray, y: np.ndarray, z: np.ndarray, meta: Mapping[str, Any]) -> bytes:
    """帧格式：magic(4) + meta_len(4) + npoints(4) + meta json + float32 交错 (x,y,z)。

    三维视图直接把这段 buffer 传给 WebGL 的 ARRAY_BUFFER，不做任何解析。
    """
    meta_bytes = json.dumps(dict(meta), ensure_ascii=False).encode("utf-8")
    rows = np.empty((x.size, 3), dtype="<f4")
    rows[:, 0] = x.astype(np.float32, copy=False)
    rows[:, 1] = y.astype(np.float32, copy=False)
    rows[:, 2] = z.astype(np.float32, copy=False)
    header = MAGIC + struct.pack("<II", len(meta_bytes), int(x.size))
    return header + meta_bytes + rows.tobytes(order="C")


def _binary_series(x: np.ndarray, y: np.ndarray, meta: Mapping[str, Any]) -> bytes:
    """帧格式：magic(4) + meta_len(4) + npoints(4) + meta json + float32 交错 (x,y)。"""
    meta_bytes = json.dumps(dict(meta), ensure_ascii=False).encode("utf-8")
    pairs = np.empty((x.size, 2), dtype="<f4")
    pairs[:, 0] = x.astype(np.float32, copy=False)
    pairs[:, 1] = y.astype(np.float32, copy=False)
    header = MAGIC + struct.pack("<II", len(meta_bytes), int(x.size))
    return header + meta_bytes + pairs.tobytes(order="C")


MAX_LAYOUT_BYTES = 64 * 1024

#: 渲染结果缓存（D35）：键 = spec 摘要 + 数据集版本 + 尺寸 + 视窗 + 格式
_RENDER_CACHE: "OrderedDict[tuple, tuple[bytes, str, object]]" = OrderedDict()
_RENDER_CACHE_MAX = 8


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


def _parse_limits(raw: str | None) -> tuple[float, float] | None:
    if not raw:
        return None
    parts = [p for p in str(raw).replace(" ", "").split(",") if p]
    if len(parts) != 2:
        raise HTTPException(400, f"视窗参数必须是 \"lo,hi\"，收到 {raw!r}")
    lo, hi = float(parts[0]), float(parts[1])
    if not (lo < hi):
        raise HTTPException(400, f"视窗下界必须小于上界，收到 {raw!r}")
    return lo, hi


def _cached(request: Request, key: tuple, build, media_type: str) -> Response:
    """统一的"渲染 → 缓存 → ETag/304 → 响应"流程。

    `build()` 返回 `(payload, extra_headers)`；缓存键由调用方给出（含 spec 摘要与参数）。
    """
    cached = _RENDER_CACHE.get(key)
    hit = cached is not None
    if cached is None:
        try:
            payload, extra = build()
        except (SpecError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - 渲染失败直接回给前端看
            raise HTTPException(500, f"渲染失败: {exc}") from exc
        tag = _etag(payload)
        _RENDER_CACHE[key] = (payload, tag, extra)
        while len(_RENDER_CACHE) > _RENDER_CACHE_MAX:
            _RENDER_CACHE.popitem(last=False)
    else:
        payload, tag, extra = cached
        _RENDER_CACHE.move_to_end(key)

    headers = {"ETag": tag, "Cache-Control": "no-store, max-age=0",
               "X-PlotKit-Render": "hit" if hit else "miss"}
    headers.update(extra or {})
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers=headers)
    return Response(content=payload, media_type=media_type, headers=headers)


def _etag(payload: bytes) -> str:
    return '"' + hashlib.sha1(payload).hexdigest()[:16] + '"'



def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".layout-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def create_app(figure: Any, *, title: str | None = None, layout_path: str | Path | None = None) -> FastAPI:
    """`figure` 是 plotkit.api.native.Figure。"""
    app = FastAPI(title=title or "PlotKit", docs_url=None, redoc_url=None)
    # 图 JSON/spec 动辄几十 KB，压缩后 ~1/10；本地回环也受益于解析前的字节数
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # 开发期绕开浏览器缓存：静态资源一律 no-store（否则改完 JS 刷新还是旧页面）
    @app.middleware("http")
    async def _no_store(request, call_next):
        response = await call_next(request)
        # 挂在子路径（如 /plotkit/）时 request.url.path 会带前缀，不能只判 startswith("/static")
        path = request.url.path
        if "/static/" in path or path.endswith("/static") or path.endswith("/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response


    @app.get("/")
    def index() -> FileResponse:
        page = STATIC_DIR / "index.html"
        if not page.exists():
            raise HTTPException(500, "缺少 static/index.html")
        return FileResponse(page, media_type="text/html; charset=utf-8")

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        fig_cfg = figure.spec.get("figure", {})
        return {
            "app": "PlotKit",
            "spec_version": figure.spec.get("spec_version"),
            "title": title or fig_cfg.get("title"),
            "kinds": reg.describe(),
            "themes": ["default", "netlab-dark"],
            "datasets": len(figure.store),
            "warnings": figure.warnings,
            "window": fig_cfg.get("window"),
            "time": _time_info(),  # 回放滑杆要用的范围/样本数
        }

    @app.get("/api/spec")
    def get_spec() -> JSONResponse:
        return JSONResponse(figure.spec)

    @app.put("/api/spec")
    async def put_spec(request: Request) -> JSONResponse:
        payload = await request.json()
        report = validate_spec(payload, store=figure.store, known_kinds=reg.known_kind_names())
        if not report.ok:
            return JSONResponse({"ok": False, **report.as_dict()}, status_code=400)
        figure.spec = payload
        return JSONResponse({"ok": True, "warnings": [i.as_dict() for i in report.warnings]})

    def _time_info() -> dict[str, Any]:
        lo, hi = figure.time_bounds()
        count = 0
        for name in figure.store.names():
            if figure.store.meta(name).get("role") == "coord":
                count = max(count, int(figure.store.meta(name).get("length") or 0))
        return {"min": lo, "max": hi, "count": count}

    @app.post("/api/clear")
    def clear_history() -> dict[str, Any]:
        """清空轨迹：跟老画布的「清空轨迹」对齐——图层和数据都归零，宿主程序继续推就重新长出来。"""
        import numpy as np

        for name in list(figure.store.names()):
            meta = figure.store.meta(name)
            figure.store.add(name, np.zeros(0, dtype="float64"),
                             unit=meta.get("unit", ""), role=meta.get("role", "series"),
                             life=meta.get("life", "append"), overwrite=True)
        figure.clear()
        return {"ok": True, "datasets": len(figure.store)}

    @app.get("/api/datasets")
    def datasets() -> dict[str, Any]:
        return figure.store.catalog()

    @app.get("/api/series")
    def series(
        x: str,
        y: str,
        i0: int = 0,
        i1: int = -1,
        pixels: int | None = None,
        per_pixel: float = 2.0,
    ) -> Response:
        try:
            xv = np.asarray(figure.store.values(x)).ravel().astype(float)
            yv = np.asarray(figure.store.values(y)).ravel().astype(float)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        stop = None if i1 < 0 else min(i1, xv.size)
        xv, yv = xv[i0:stop], yv[i0:stop]
        if pixels:
            xv, yv = downsample_xy(xv, yv, pixels, per_pixel=per_pixel)
        meta = {"x": x, "y": y, "i0": i0, "i1": (stop if stop is not None else int(xv.size))}
        return Response(content=_binary_series(xv, yv, meta), media_type="application/octet-stream")

    @app.get("/api/xyz")
    def xyz(x: str, y: str, z: str, max: int = 200_000) -> Response:
        """三维视图的数据出口：float32 交错 (x,y,z)，前端直接塞进 WebGL 顶点缓冲。"""
        try:
            xv = np.asarray(figure.store.values(x)).ravel()
            yv = np.asarray(figure.store.values(y)).ravel()
            zv = np.asarray(figure.store.values(z)).ravel()
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        n = min(xv.size, yv.size, zv.size)
        xv, yv, zv = xv[:n], yv[:n], zv[:n]
        limit = _clamp(max, 1_000, 2_000_000)
        if n > limit:  # 均匀抽样：三维不按像素列抽稀，只控总量
            idx = np.linspace(0, n - 1, limit).astype(np.int64)
            xv, yv, zv = xv[idx], yv[idx], zv[idx]
        meta = {"x": x, "y": y, "z": z, "n": int(xv.size), "total": int(n)}
        return Response(content=_binary_xyz(xv, yv, zv, meta),
                        media_type="application/octet-stream")

    @app.get("/api/pick")
    def pick(x: float, y: float, sx: float = 1.0, sy: float = 1.0,
             tol: float = 0.03, layer: str | None = None) -> dict[str, Any]:
        """hover 精确拾取：在数据点上找最近邻（按视窗跨度归一化），而不是从像素反推。"""
        sx = abs(sx) or 1.0
        sy = abs(sy) or 1.0
        best: dict[str, Any] | None = None
        for item in figure.spec.get("layers") or []:
            if layer and item.get("id") != layer:
                continue
            data = item.get("data") or {}
            xn, yn = data.get("x"), data.get("y")
            if not xn or not yn:
                continue
            try:
                xv = np.asarray(figure.store.values(xn)).ravel()
                yv = np.asarray(figure.store.values(yn)).ravel()
            except KeyError:
                continue
            n = min(xv.size, yv.size)
            if not n:
                continue
            xv, yv = xv[:n].astype(float, copy=False), yv[:n].astype(float, copy=False)
            dist = ((xv - x) / sx) ** 2 + ((yv - y) / sy) ** 2
            i = int(np.argmin(dist))
            if best is None or dist[i] < best["d2"]:
                best = {"d2": float(dist[i]), "x": float(xv[i]), "y": float(yv[i]),
                        "i": i, "layer": item.get("id"),
                        "label": (item.get("label") or item.get("kind") or "")}
        if best is None or best["d2"] > tol * tol:
            return {"hit": False}
        best.pop("d2")
        best["hit"] = True
        return best

    layout_file = Path(layout_path) if layout_path else Path.cwd() / "layout.json"

    @app.get("/api/layout")
    def get_layout() -> JSONResponse:
        try:
            return JSONResponse(json.loads(layout_file.read_text(encoding="utf-8")))
        except (FileNotFoundError, json.JSONDecodeError):
            return JSONResponse({})

    @app.put("/api/layout")
    async def put_layout(request: Request) -> JSONResponse:
        raw = await request.body()
        if len(raw) > MAX_LAYOUT_BYTES:
            raise HTTPException(413, f"layout 超过 {MAX_LAYOUT_BYTES} 字节")
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(400, f"layout 不是合法 JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(400, "layout 顶层必须是对象")
        _write_json_atomic(layout_file, payload)
        return JSONResponse({"ok": True, "path": str(layout_file)})

    @app.get("/api/render")
    def render(
        request: Request,
        w: int = 900,
        h: int = 520,
        dpi: int = 100,
        fmt: str = "png",
        xlim: str | None = None,
        ylim: str | None = None,
        t: float | None = None,
        backend: str | None = None,
    ) -> Response:
        """按像素尺寸渲染（D33/D34）：网页呈现的唯一图片出口。

        - 支持 `xlim/ylim` 覆盖视窗（前端缩放/平移停手后带新范围来重绘）；
        - `backend` 可选 `mpl` / `pyvista` / `auto`（D37，默认走 figure 自己的选择）；
        - 同一 spec + 同一视窗走 ETag，命中返回 304；
        - `X-PlotKit-Render: hit|miss` 便于前端/验收区分。
        """
        fmt = (fmt or "png").lower()
        if fmt not in ("png", "svg"):
            raise HTTPException(400, f"不支持的格式 {fmt!r}（png / svg）")
        width, height, dpi = _clamp(w, 80, 4000), _clamp(h, 60, 4000), _clamp(dpi, 40, 400)
        xr, yr = _parse_limits(xlim), _parse_limits(ylim)
        backend = (backend or "").strip().lower() or None
        key = (figure.revision, "render", width, height, dpi, fmt, xr, yr, t, backend)

        def build():
            payload, limits = figure.render(width=width, height=height, dpi=dpi, fmt=fmt,
                                            xlim=xr, ylim=yr, with_limits=True, t_end=t,
                                            backend=backend)
            extra = {"X-PlotKit-Backend": str((limits or {}).get("backend") or backend or "mpl")}
            if limits:
                if limits.get("xlim") and limits.get("ylim"):
                    extra["X-PlotKit-Xlim"] = f"{limits['xlim'][0]:.6g},{limits['xlim'][1]:.6g}"
                    extra["X-PlotKit-Ylim"] = f"{limits['ylim'][0]:.6g},{limits['ylim'][1]:.6g}"
                if limits.get("box"):
                    extra["X-PlotKit-Box"] = ",".join(f"{v:.5f}" for v in limits["box"])
                if limits.get("px"):
                    extra["X-PlotKit-Px"] = f"{limits['px'][0]},{limits['px'][1]}"
                if limits.get("slots"):
                    extra["X-PlotKit-Axes"] = ";".join(
                        f"{s['slot']}," + ",".join(f"{v:.5f}" for v in s["box"]) for s in limits["slots"])
            return payload, extra

        return _cached(request, key, build, "image/png" if fmt == "png" else "image/svg+xml")

    @app.get("/api/anim")
    def anim(
        request: Request,
        w: int = 640,
        h: int = 400,
        dpi: int = 100,
        fps: float | None = None,
        fmt: str = "gif",
    ) -> Response:
        """动画（P13-06/07）：按 `figure.anim` 逐帧渲染，合成 GIF 或 MP4。"""
        width, height, dpi = _clamp(w, 80, 4000), _clamp(h, 60, 4000), _clamp(dpi, 40, 400)
        fmt = (fmt or "gif").lower()
        builders = {
            "gif": ("image/gif", lambda: (figure.animate_gif(width=width, height=height, dpi=dpi, fps=fps), {})),
            "mp4": ("video/mp4", lambda: (figure.animate_mp4(width=width, height=height, dpi=dpi, fps=fps), {})),
        }
        if fmt not in builders:
            raise HTTPException(400, f"不支持的动画格式 {fmt!r}（gif / mp4）")
        media_type, build = builders[fmt]
        return _cached(request, (figure.revision, "anim", width, height, dpi, fps, fmt), build, media_type)

    @app.get("/api/png")
    def png(dpi: int | None = None) -> Response:
        try:
            payload = figure.png(dpi=dpi)
        except Exception as exc:  # noqa: BLE001 - 直接回给前端看
            raise HTTPException(500, f"matplotlib 渲染失败: {exc}") from exc
        return Response(content=payload, media_type="image/png")

    return app
