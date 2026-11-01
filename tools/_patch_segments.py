"""一次性补丁：新增 `segments`（多段折线）图层，并把 NS 流线接进去。"""
import pathlib

# ---------------- 1) mpl 后端 ----------------
p = pathlib.Path("src/plotkit/backends/mpl_backend.py")
s = p.read_text(encoding="utf-8")

if "def _draw_segments" not in s:
    s = s.replace('''def _draw_scatter3d(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:''',
'''def _draw_segments(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    """多段折线：x/y/z 是**成对**的端点（第 2i、2i+1 个点连成一段）。"""
    from mpl_toolkits.mplot3d.art3d import Line3DCollection

    style = layer.get("style") or {}
    x, y, z = _xyz_arrays(layer, store)
    xs, ys, zs = np.ravel(x), np.ravel(y), np.ravel(z)
    n = (xs.size // 2) * 2
    if n < 2:
        return
    pts = np.stack([xs[:n], ys[:n], zs[:n]], axis=1).reshape(-1, 2, 3)
    coll = Line3DCollection(pts,
                            colors=str(style.get("color") or color_for(index)),
                            linewidths=float(style.get("width", 1.2) or 1.2))
    ax.add_collection3d(coll)
    ax.auto_scale_xyz(xs[:n], ys[:n], zs[:n])


def _draw_scatter3d(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:''', 1)

if 'reg.register("segments"' not in s:
    s = s.replace('''reg.register("bar", 2, None, defaults={"mode": "bars"}, description="柱状图")''',
'''reg.register("bar", 2, None, defaults={"mode": "bars"}, description="柱状图")
reg.register("segments", 3, None, defaults={"width": 1.2},
             description="多段折线（流线束 / 轨迹束，端点点对）")''', 1)

if '"segments": _draw_segments' not in s:
    s = s.replace('    "line3d": _draw_line3d,', '    "line3d": _draw_line3d,\n    "segments": _draw_segments,', 1)
p.write_text(s, encoding="utf-8")

# ---------------- 2) validate ----------------
p2 = pathlib.Path("src/plotkit/spec/validate.py")
s2 = p2.read_text(encoding="utf-8")
if '"segments"' not in s2:
    s2 = s2.replace('''    "line3d": {"x": ("coord", "series", "auto"), "y": ("coord", "series", "auto"),
               "z": ("series", "field", "auto")},''',
'''    "line3d": {"x": ("coord", "series", "auto"), "y": ("coord", "series", "auto"),
               "z": ("series", "field", "auto")},
    "segments": {"x": ("coord", "series", "auto"), "y": ("coord", "series", "auto"),
                 "z": ("series", "field", "auto")},''', 1)
p2.write_text(s2, encoding="utf-8")

# ---------------- 3) pyvista 后端 ----------------
p3 = pathlib.Path("src/plotkit/backends/pyvista_backend.py")
s3 = p3.read_text(encoding="utf-8")
if "def build_segments" not in s3:
    s3 = s3.replace("def build_scatter3d(layer, store)", '''def build_segments(layer, store) -> list[_Item]:
    """多段折线 → PolyData lines（每两行点构成一段）。"""
    import pyvista as pv

    data = layer.get("data") or {}
    x = _values(layer, store, "x")
    y = _values(layer, store, "y")
    z = _values(layer, store, "z")
    pts = np.column_stack([np.ravel(x), np.ravel(y), np.ravel(z)]).astype(float)
    n = (pts.shape[0] // 2) * 2
    if n < 2:
        return []
    pts = pts[:n]
    nseg = n // 2
    lines = np.empty((nseg, 3), dtype=np.int64)
    lines[:, 0] = 2
    lines[:, 1] = np.arange(0, n, 2)
    lines[:, 2] = np.arange(1, n, 2)
    poly = pv.PolyData(pts, lines=lines.ravel())
    style = layer.get("style") or {}
    color = style.get("color")
    return [_Item(mesh=poly, color=tuple(color) if color else None,
                  line_width=float(style.get("width", 1.2) or 1.2), mode="lines")]


def build_scatter3d(layer, store)''', 1)
    s3 = s3.replace('''    "text3d",
    "particles",
)''', '''    "text3d",
    "particles",
    "segments",
)''', 1)
    s3 = s3.replace('''    "particles": _build_particles,
}''', '''    "particles": _build_particles,
    "segments": build_segments,
}''', 1)
p3.write_text(s3, encoding="utf-8")

# ---------------- 4) 服务端出口 ----------------
p4 = pathlib.Path("src/plotkit/server/app.py")
s4 = p4.read_text(encoding="utf-8")
if "/api/segments" not in s4:
    anchor = '''    @app.get("/api/particles")'''
    s4 = s4.replace(anchor, '''    @app.get("/api/segments")
    def segments(x: str = Query(...), y: str = Query(...), z: str = Query(...),
                 stride: int = Query(1, ge=1, le=16)) -> Response:
        """多段折线的端点（第 2i、2i+1 个点连成一段），float32 平铺。"""
        try:
            xv = np.asarray(figure.store.values(x), dtype=np.float64).ravel()
            yv = np.asarray(figure.store.values(y), dtype=np.float64).ravel()
            zv = np.asarray(figure.store.values(z), dtype=np.float64).ravel()
        except (KeyError, IndexError) as exc:
            raise HTTPException(404, f"未知数据集：{exc}") from exc
        n = min(xv.size, yv.size, zv.size)
        step = max(1, int(stride))
        pts = np.stack([xv[:n], yv[:n], zv[:n]], axis=1)[::step]
        meta = {"x": x, "y": y, "z": z, "n": int(pts.shape[0]),
                "bbox": [pts.min(axis=0).tolist(), pts.max(axis=0).tolist()]}
        return Response(content=_binary_points(pts, None, meta),
                        media_type="application/octet-stream")

''' + anchor, 1)
p4.write_text(s4, encoding="utf-8")

# ---------------- 5) 前端绘制 ----------------
p5 = pathlib.Path("src/plotkit/static/view3d.js")
s5 = p5.read_text(encoding="utf-8")
s5 = s5.replace('''        if (layer.mode === "lines") {
          gl.uniform1f(this.uPointSize, 1);
          gl.drawArrays(gl.LINE_STRIP, 0, layer.count);
        } else {''', '''        if (layer.mode === "segments") {
          gl.uniform1f(this.uPointSize, 1);
          gl.drawArrays(gl.LINES, 0, layer.count);
        } else if (layer.mode === "lines") {
          gl.uniform1f(this.uPointSize, 1);
          gl.drawArrays(gl.LINE_STRIP, 0, layer.count);
        } else {''', 1)
p5.write_text(s5, encoding="utf-8")
print("segments layer wired end to end")
