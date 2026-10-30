"""matplotlib 后端：静态图 / 论文级导出 / 浏览器无等价物时的兜底。

用 `Figure` 对象直接构图（不碰 pyplot 全局状态，不改 rcParams），因此可在服务端多线程里安全调用。

论文级（pub）要素在这里是"原生长出来"的：误差棒、双对数 + 次刻度、内侧/镜像刻度、
逐级字号、真正的 LaTeX 上下标、inset 轴、箭头与斜率参考三角。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ..spec.model import DEFAULT_FONTS
from ..spec.model import layers as spec_layers
from ..spec.model import nrows, subplot_xy
from ..store.registry import DataStore
from . import registry as reg
from .plotly_backend import PALETTE, THEMES, _step, color_for  # noqa: F401

FONT_FALLBACK = ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans", "Arial")

MODE_STYLE = {
    "lines": {"linestyle": "-", "marker": None},
    "markers": {"linestyle": "None", "marker": "o"},
    "lines+markers": {"linestyle": "-", "marker": "o"},
}

DASH_MPL = {"solid": "-", "dot": ":", "dash": "--", "longdash": (0, (6, 3)), "dashdot": "-.", "longdashdot": (0, (8, 3, 2, 3))}

# plotly 的 symbol 名 → matplotlib 的 marker 简写
SYMBOL_MPL = {
    "circle": "o", "square": "s", "diamond": "D", "cross": "+", "x": "x",
    "triangle-up": "^", "triangle-down": "v", "triangle-left": "<", "triangle-right": ">",
    "star": "*", "hexagon": "h", "pentagon": "p", "hourglass": "d", "bowtie": "d",
    "line-ew": "_", "line-ns": "|",
}


def _marker_symbol(style: Mapping[str, Any]) -> str:
    return SYMBOL_MPL.get(str((style.get("marker") or {}).get("symbol", "circle")), "o")


def _error_bars(ax, layer, store, *, color: str) -> None:
    """误差棒：xerr/yerr 用 [minus, plus] 形式，支持非对称。"""
    data = layer.get("data") or {}
    if not any(k.startswith("error_") for k in data):
        return
    from ..backends.plotly_backend import _xy

    x, y = _xy(layer, store, pixels=None, per_pixel=2.0)
    cfg = dict((layer.get("style") or {}).get("error") or {})
    ecolor = cfg.get("color") or color
    width = cfg.get("width")
    capsize = (float(width) / 2.0) if width else 0.0

    def _band(axis: str):
        plus = np.asarray(store.values(data[f"error_{axis}"])).ravel().astype(float)
        minus_name = data.get(f"error_{axis}_minus")
        minus = np.asarray(store.values(minus_name)).ravel().astype(float) if minus_name else plus
        return np.vstack([minus, plus])

    yerr = _band("y") if data.get("error_y") else None
    xerr = _band("x") if data.get("error_x") else None
    ax.errorbar(
        x, y, yerr=yerr, xerr=xerr,
        fmt="none", ecolor=ecolor,
        elinewidth=float(cfg.get("thickness", 1.2)),
        capsize=capsize, capthick=float(cfg.get("thickness", 1.2)),
        alpha=float(cfg.get("opacity", 1.0)),
        zorder=1,
    )


def _draw_line(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    from ..backends.plotly_backend import _xy

    x, y = _xy(layer, store, pixels=pixels, per_pixel=per_pixel)
    style = layer.get("style") or {}
    mode = style.get("mode", "lines")
    kwargs = MODE_STYLE.get(mode, MODE_STYLE["lines"])
    marker = dict(style.get("marker") or {})
    color = style.get("color") or color_for(index)
    marker_line = dict(marker.get("line") or {})
    line = ax.plot(
        x, y,
        color=color,
        linewidth=float(style.get("width", 1.6)),
        linestyle=DASH_MPL.get(style.get("dash", "solid"), "-"),
        marker=_marker_symbol(style) if kwargs["marker"] or marker.get("symbol") else None,
        markersize=float(marker.get("size", 6)) * 0.7,
        markeredgecolor=marker_line.get("color") or color,
        markeredgewidth=float(marker_line.get("width", 0.0)),
        alpha=float(style.get("opacity", 1.0)),
        label=layer.get("label") or layer.get("data", {}).get("y"),
    )[0]
    _ = line
    if mode == "lines+markers":
        # marker 默认使用 line 的 color；描边单独给
        line.set_markerfacecolor(color)
    _error_bars(ax, layer, store, color=color)


def _draw_scatter(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    from ..backends.plotly_backend import _xy

    x, y = _xy(layer, store, pixels=pixels, per_pixel=per_pixel)
    style = layer.get("style") or {}
    marker = dict(style.get("marker") or {})
    marker_line = dict(marker.get("line") or {})
    color = style.get("color") or color_for(index)
    sizes = marker.get("sizes")
    ax.scatter(
        x, y,
        color=color,
        s=np.asarray(sizes, dtype=float) ** 2 if sizes is not None else float(marker.get("size", 6)) ** 2,
        marker=_marker_symbol(style),
        edgecolors=marker_line.get("color") or color,
        linewidths=float(marker_line.get("width", 0.0)),
        alpha=float(marker.get("opacity", style.get("opacity", 1.0))),
        label=layer.get("label") or layer.get("data", {}).get("y"),
        zorder=3,
    )
    _error_bars(ax, layer, store, color=color)


def _draw_bar(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    from ..backends.plotly_backend import _xy

    x, y = _xy(layer, store, pixels=pixels, per_pixel=per_pixel)
    style = layer.get("style") or {}
    color = style.get("color") or color_for(index)
    ax.bar(
        x, y,
        width=float(style.get("width", 0.8)) or 0.8,
        color=color,
        alpha=float(style.get("opacity", 1.0)),
        label=layer.get("label") or layer.get("data", {}).get("y"),
    )
    _error_bars(ax, layer, store, color=color)


def hist_counts(layer: Mapping[str, Any], store: DataStore) -> tuple[np.ndarray, np.ndarray]:
    """直方图分箱（服务端算，D31）。单独暴露出来，测试可以直接与 `np.histogram` 对拍。"""
    data = layer.get("data") or {}
    style = layer.get("style") or {}
    x = np.asarray(store.values(data["x"])).ravel().astype(float)
    x = x[np.isfinite(x)]
    return np.histogram(x, bins=style.get("bins", 30), density=bool(style.get("density")))


def _draw_hist(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    """直方图：分箱在服务端做（D31），前端只画柱子。"""
    data = layer.get("data") or {}
    style = layer.get("style") or {}
    counts, edges = hist_counts(layer, store)
    color = style.get("color") or color_for(index)
    ax.bar(edges[:-1], counts, width=np.diff(edges), align="edge", color=color,
           alpha=float(style.get("opacity", 1.0)),
           label=layer.get("label") or data.get("x"))


def _draw_pie(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    data = layer.get("data") or {}
    style = layer.get("style") or {}
    values = np.asarray(store.values(data["values"])).ravel().astype(float)
    labels = None
    if data.get("labels"):
        labels = [str(v) for v in np.asarray(store.values(data["labels"])).ravel()]
    ax.pie(values, labels=labels, autopct=str(style.get("autopct") or "") or None,
           startangle=90, counterclock=False)
    ax.set_axis_off()


def _draw_image(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    data = layer.get("data") or {}
    style = layer.get("style") or {}
    arr = np.asarray(store.values(data["image"]))
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    im = ax.imshow(arr, cmap=str(style.get("cmap") or "viridis"),
                   origin=str(style.get("origin") or "upper"),
                   aspect=str(style.get("aspect") or "auto"),
                   vmin=style.get("vmin"), vmax=style.get("vmax"),
                   interpolation="nearest")
    if style.get("colorbar", True):
        ax.figure.colorbar(im, ax=ax, **COLORBAR_KW)


def _draw_table(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    data = layer.get("data") or {}
    style = layer.get("style") or {}
    cells = np.asarray(store.values(data["cells"]))
    if cells.ndim == 1:
        cells = cells.reshape(-1, 1)
    header = None
    if data.get("header"):
        header = [str(v) for v in np.asarray(store.values(data["header"])).ravel()]
    ax.set_axis_off()
    table = ax.table(cellText=cells, colLabels=header, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(float(style.get("fontsize", 10)))
    table.scale(1.0, 1.4)




#: colorbar 的统一摆位（三处共用，别各写一份魔数）
COLORBAR_KW = {"fraction": 0.046, "pad": 0.02}


def _maybe_colorbar(ax, mappable, style: Mapping[str, Any], *, default: bool = True) -> None:
    """按 `style.colorbar` 决定是否加色条（六处共用，别各写一份判断）。"""
    if style.get("colorbar", default):
        ax.figure.colorbar(mappable, ax=ax, **COLORBAR_KW)


def _field_arrays(layer: Mapping[str, Any], store: DataStore):
    """取 z（必需）与可选的 x/y 坐标；z 至少二维，一维自动补成 1 行。"""
    data = layer.get("data") or {}
    z = np.asarray(store.values(data["z"]), dtype=float)
    if z.ndim == 1:
        z = z.reshape(1, -1)
    x = np.asarray(store.values(data["x"])).ravel().astype(float) if data.get("x") else None
    y = np.asarray(store.values(data["y"])).ravel().astype(float) if data.get("y") else None
    return x, y, z


def _mesh(ax, layer, store, *, cmap_default: str = "viridis"):
    style = layer.get("style") or {}
    x, y, z = _field_arrays(layer, store)
    cmap = str(style.get("cmap") or cmap_default)
    vmin, vmax = style.get("vmin"), style.get("vmax")
    if x is not None and y is not None and x.size == z.shape[1] and y.size == z.shape[0]:
        return ax.pcolormesh(x, y, z, cmap=cmap, vmin=vmin, vmax=vmax,
                             shading=str(style.get("shading") or "auto"))
    return ax.imshow(z, cmap=cmap, vmin=vmin, vmax=vmax, origin="lower",
                     aspect=str(style.get("aspect") or "auto"), interpolation="nearest")


def _draw_heatmap(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    mesh = _mesh(ax, layer, store)
    _maybe_colorbar(ax, mesh, layer.get("style") or {})


def _contour_args(layer, store):
    style = layer.get("style") or {}
    x, y, z = _field_arrays(layer, store)
    levels = style.get("levels") or 8
    kwargs = {"levels": levels, "cmap": str(style.get("cmap") or "viridis")}
    if style.get("vmin") is not None:
        kwargs["vmin"] = style["vmin"]
    if style.get("vmax") is not None:
        kwargs["vmax"] = style["vmax"]
    args = (x, y, z) if x is not None and y is not None else (z,)
    return args, kwargs


def _draw_contour(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    args, kwargs = _contour_args(layer, store)
    cs = ax.contour(*args, **kwargs)
    style = layer.get("style") or {}
    if style.get("labels"):
        ax.clabel(cs, inline=True, fontsize=8)
    if style.get("colorbar"):
        ax.figure.colorbar(cs, ax=ax, **COLORBAR_KW)


def _draw_contourf(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    args, kwargs = _contour_args(layer, store)
    cs = ax.contourf(*args, **kwargs)
    if (layer.get("style") or {}).get("colorbar", True):
        ax.figure.colorbar(cs, ax=ax, **COLORBAR_KW)


def _draw_correlation(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    _draw_heatmap(ax, layer, store, index, pixels=pixels, per_pixel=per_pixel)
    # 列名存在数据集的 note 里（add_correlation 写入），有就画成刻度标签
    name = (layer.get("data") or {}).get("z")
    try:
        names = [s for s in str(store.meta(name).get("note") or "").split(",") if s]
    except KeyError:
        names = []
    if names:
        ticks = np.arange(len(names))
        ax.set_xticks(ticks)
        ax.set_yticks(ticks)
        ax.set_xticklabels(names, rotation=45, ha="right")
        ax.set_yticklabels(names)



def _vector_arrays(layer: Mapping[str, Any], store: DataStore):
    data = layer.get("data") or {}
    return tuple(np.asarray(store.values(data[k]), dtype=float) for k in ("x", "y", "u", "v"))


COLOR_BY_CHOICES = ("magnitude", "x", "y", "u", "v")


def _color_norm(style: Mapping[str, Any]):
    """vmin/vmax → matplotlib 的 Normalize（quiver/barbs/streamplot 只认 norm，不认 vmin/vmax）。"""
    vmin, vmax = style.get("vmin"), style.get("vmax")
    if vmin is None and vmax is None:
        return None
    from matplotlib.colors import Normalize

    return Normalize(vmin=None if vmin is None else float(vmin),
                     vmax=None if vmax is None else float(vmax))


def _color_values(style: Mapping[str, Any], x, y, u, v):
    """按 `color_by` 取上色用的标量：magnitude（默认）/ x / y / u / v。"""
    mode = str(style.get("color_by") or "magnitude")
    if mode not in COLOR_BY_CHOICES:
        raise ValueError(f"color_by={mode!r} 不支持（可用: {', '.join(COLOR_BY_CHOICES)}）")
    if mode == "x":
        return x
    if mode == "y":
        return y
    if mode == "u":
        return u
    if mode == "v":
        return v
    return np.hypot(u, v)


def quiver_scale(x, y, u, v, *, fraction: float = 0.06) -> float:
    """把"中位箭头长度 ≈ 画布跨度的 6%"换算成 quiver 的 scale（数据单位）。

    mpl 自带的 auto-scale 在 `angles="xy"` 下按 axes 宽度归一，网格密时箭头会长到糊满全图
    （2026-10-31 实测：整幅图变成一片渐变）。这里显式给 scale + `scale_units="xy"`，
    箭头长度就只由数据决定，换分辨率/换尺寸都不会变。
    """
    mag = np.hypot(np.asarray(u, dtype=float), np.asarray(v, dtype=float))
    finite = mag[np.isfinite(mag)]
    base = float(np.median(finite)) if finite.size else 1.0
    xs = np.asarray(x, dtype=float)
    ys = np.asarray(y, dtype=float)
    span = max(float(np.ptp(xs[np.isfinite(xs)])), float(np.ptp(ys[np.isfinite(ys)]))) or 1.0
    return max(base / (max(fraction, 1e-3) * span), 1e-12)


def _draw_quiver(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    style = layer.get("style") or {}
    x, y, u, v = _vector_arrays(layer, store)
    c = _color_values(style, x, y, u, v)
    cmap = str(style.get("cmap") or "viridis")
    kwargs = {
        "angles": "xy",
        # quiver 没有 arrowsize，用箭头头部尺寸换算（streamplot 才有 arrowsize）
        "headwidth": 3.0 * float(style.get("arrowsize", 1.0) or 1.0),
        "headlength": 5.0 * float(style.get("arrowsize", 1.0) or 1.0),
        "headaxislength": 4.5 * float(style.get("arrowsize", 1.0) or 1.0),
        # 注意：不能复用通用的 style["width"]（那是线宽 1.6，在 quiver 里表示
        # "箭杆宽度 = 1.6 个 axes 宽度"，会把整幅图糊满）。箭杆用独立键 shaft。
        "width": float(style.get("shaft", 0.0035) or 0.0035),
    }
    # 显式给 scale 才按数据单位缩放；否则按"中位箭头 ≈ 跨度 6%"自动算（见 quiver_scale）
    scale = style.get("scale")
    if scale in (None, 0, "auto"):
        kwargs["scale"] = quiver_scale(x, y, u, v)
    else:
        kwargs["scale"] = float(scale)
    kwargs["scale_units"] = "xy"
    norm = _color_norm(style)
    if norm is not None:
        kwargs["norm"] = norm
    if style.get("color"):
        kwargs["color"] = str(style["color"])
    else:
        kwargs["cmap"] = cmap
    q = ax.quiver(x, y, u, v, c, **kwargs)
    if style.get("key"):
        # quiverkey：给一个"这个箭头代表多少"的图例（对应 mpl 的 quiverkey）
        mag = np.hypot(u, v)
        ref = float(np.nanmax(mag) or 1.0)
        ax.quiverkey(q, 0.9, 1.02, ref, f"{ref:.3g}", labelpos="E", coordinates="axes",
                     fontproperties={"size": 8})
    if not style.get("color"):  # 纯色箭头时色条会误导（色条画的是模长，箭头是单色）
        _maybe_colorbar(ax, q, style, default=False)


def _draw_barbs(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    """风羽图（mpl `barbs`）：每个点一根带旗的杆，长度编码风速。"""
    style = layer.get("style") or {}
    x, y, u, v = _vector_arrays(layer, store)
    c = _color_values(style, x, y, u, v)
    kwargs = {
        "length": float(style.get("arrowsize", 6.0) or 6.0),
        "linewidth": float(style.get("width", 0.8) or 0.8),
        "cmap": str(style.get("cmap") or "viridis"),
    }
    norm = _color_norm(style)
    if norm is not None:
        kwargs["norm"] = norm
    b = ax.barbs(x, y, u, v, c, **kwargs)
    if not style.get("color"):
        _maybe_colorbar(ax, b, style, default=False)


def _draw_streamplot(ax, layer, store, index: int, *, pixels=None, per_pixel=2.0) -> None:
    style = layer.get("style") or {}
    x, y, u, v = _vector_arrays(layer, store)
    if x.ndim != 2 or u.ndim != 2:
        raise ValueError("streamplot 需要二维网格：x/y 与 u/v 都要是 2D 数组（一维请改用 quiver）")
    density = style.get("density")
    density = 1.0 if density is None else float(density)
    color = style.get("color")
    if color:
        # 纯色流线：color 直接给字符串，此时不传 cmap（两者互斥）
        color_arg = str(color)
        cmap_arg = None
    else:
        color_arg = _color_values(style, x, y, u, v)
        cmap_arg = str(style.get("cmap") or "viridis")
    kwargs = {
        "density": density,
        "color": color_arg,
        "arrowsize": float(style.get("arrowsize", 1.0) or 1.0),
        "linewidth": float(style.get("width", 1.0) or 1.0),
    }
    if cmap_arg:
        kwargs["cmap"] = cmap_arg
        norm = _color_norm(style)
        if norm is not None:
            kwargs["norm"] = norm
    strm = ax.streamplot(x, y, u, v, **kwargs)
    if not style.get("color"):
        _maybe_colorbar(ax, strm.lines, style, default=False)

DRAWERS = {
    "line": _draw_line, "marker": _draw_scatter, "bar": _draw_bar,
    "hist": _draw_hist, "pie": _draw_pie, "image": _draw_image, "table": _draw_table,
    "heatmap": _draw_heatmap, "contour": _draw_contour, "contourf": _draw_contourf,
    "correlation": _draw_correlation,
    "quiver": _draw_quiver, "streamplot": _draw_streamplot, "barbs": _draw_barbs,
}


def _apply_view(ax, view: Mapping[str, Any], *, theme, fonts) -> None:
    if view.get("xlim"):
        ax.set_xlim(*[float(v) for v in view["xlim"]])
    if view.get("ylim"):
        ax.set_ylim(*[float(v) for v in view["ylim"]])
    from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

    if view.get("xscale") == "log":
        ax.set_xscale("log")
    if view.get("yscale") == "log":
        ax.set_yscale("log")
    if view.get("invert_y"):
        ax.invert_yaxis()

    ticks = dict(view.get("ticks") or {})
    mirror = bool(ticks.get("mirror"))
    ax.tick_params(
        axis="both", which="major",
        direction="in" if ticks.get("inside") else "out",
        top=mirror, right=mirror,
        colors=theme["text"], labelsize=float(fonts.get("tick", 11)),
        width=0.9, length=4.0,
    )
    if ticks.get("minor"):
        ax.minorticks_on()
        ax.tick_params(axis="both", which="minor", direction="in", top=mirror, right=mirror,
                       colors=theme["text"], width=0.6, length=2.2)
    else:
        ax.minorticks_off()

    for spine in ("top", "right"):
        ax.spines[spine].set_visible(mirror)
        ax.spines[spine].set_color(theme["text"] if mirror else theme["grid"])
    for spine in ("bottom", "left"):
        ax.spines[spine].set_color(theme["text"] if mirror else theme["grid"])

    if view.get("grid", True):
        ax.grid(True, color=theme["grid"], linewidth=0.6)
    else:
        ax.grid(False)
    if view.get("xlabel"):
        ax.set_xlabel(str(view["xlabel"]), color=theme["text"], fontsize=float(fonts.get("axis", 12)))
    if view.get("ylabel"):
        ax.set_ylabel(str(view["ylabel"]), color=theme["text"], fontsize=float(fonts.get("axis", 12)))
    if view.get("title"):
        ax.set_title(str(view["title"]), color=theme["text"], fontsize=float(fonts.get("axis", 12)))

    mode = str(view.get("loglabels", "sci"))
    plain_axes = {"plain": ("x", "y"), "plain-x": ("x",), "plain-y": ("y",)}.get(mode, ())
    # 论文里更常见的写法：对数轴直接标 2 4 6 8 10，而不是 2×10^0
    for name, axis, scale in (("x", ax.xaxis, view.get("xscale")), ("y", ax.yaxis, view.get("yscale"))):
        if name not in plain_axes or scale != "log":
            continue
        # 对数轴上 2/4/6/8 原本是"次刻度"，论文里恰恰要给它们标数字
        formatter = FuncFormatter(lambda value, _pos: f"{value:g}")
        axis.set_major_locator(LogLocator(base=10.0))
        axis.set_major_formatter(formatter)
        axis.set_minor_locator(LogLocator(base=10.0, subs=(2.0, 4.0, 6.0, 8.0)))
        axis.set_minor_formatter(formatter)
        for tick in list(axis.get_major_ticks()) + list(axis.get_minor_ticks()):
            tick.label1.set_fontsize(float(fonts.get("tick", 11)))



def _draw_decorations(fig, spec, axes: Mapping[int, Any], views: Mapping[int, Mapping[str, Any]],
                      *, theme, fonts) -> None:
    from matplotlib.patches import Rectangle

    for shape in spec.get("figure", {}).get("shapes") or []:
        kind = shape.get("type")
        subplot = int(shape.get("subplot", 0))
        target = axes.get(subplot)
        if target is None:
            continue
        view = views.get(subplot, {})
        color = shape.get("color", "#94a3b8")
        lw = float(shape.get("width", 1.4))
        ls = DASH_MPL.get(shape.get("dash", "solid"), "-")
        if kind == "line":
            target.plot([shape["x0"], shape["x1"]], [shape["y0"], shape["y1"]],
                        color=color, lw=lw, ls=ls, zorder=2, scalex=False, scaley=False)
        elif kind == "rect":
            patch = Rectangle((shape["x0"], shape["y0"]), shape["x1"] - shape["x0"], shape["y1"] - shape["y0"],
                              facecolor=shape.get("fill") or color, alpha=0.15, edgecolor=color, lw=lw, ls=ls)
            target.add_patch(patch)
        elif kind == "arrow":
            target.annotate(
                str(shape.get("text", "")),
                xy=tuple(shape["end"]), xytext=tuple(shape["start"]),
                xycoords="data", textcoords="data",
                color=color, fontsize=float(fonts.get("annotation", 11)),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, shrinkA=2, shrinkB=2),
            )
        elif kind == "triangle":
            x0, y0 = shape.get("anchor", (1.0, 1.0))
            decades = float(shape.get("decades", 1.0))
            slope = float(shape.get("slope", -3.0))
            x1 = _step(x0, str(view.get("xscale", "linear")), decades)
            y1 = _step(y0, str(view.get("yscale", "linear")), slope * decades)
            for a, b in (((x0, y0), (x1, y1)), ((x1, y1), (x1, y0)), ((x0, y0), (x1, y0))):
                target.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=lw, ls=ls, zorder=2,
                            scalex=False, scaley=False)
            if shape.get("text"):
                target.annotate(
                    str(shape["text"]), xy=((x0 + x1) / 2, y0), xycoords="data",
                    textcoords="offset points", xytext=(0, 4), ha="center",
                    color=theme["text"], fontsize=float(fonts.get("annotation", 11)),
                )
        # path（任意 SVG 路径）在 matplotlib 侧没有等价物，静默跳过


def to_figure(
    spec: Mapping[str, Any],
    store: DataStore,
    *,
    dpi: int | None = None,
    pixels: int | None = None,
):
    """构建 matplotlib Figure（调用方负责 savefig / show）。"""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig_cfg = spec.get("figure", {})
    theme = THEMES.get(str(fig_cfg.get("theme", "default")), THEMES["default"])
    fonts = {**DEFAULT_FONTS, **dict(fig_cfg.get("fonts") or {})}
    size = fig_cfg.get("size", [12.8, 8.4])
    ncols = int(fig_cfg.get("ncols", 1))
    subplots = int(fig_cfg.get("subplots", 1))
    rows = nrows(ncols, subplots)

    fig = Figure(figsize=(float(size[0]), float(size[1])), dpi=int(dpi or fig_cfg.get("dpi", 100)),
                 constrained_layout=True, facecolor=theme["paper"])
    FigureCanvasAgg(fig)
    fig.patch.set_facecolor(theme["paper"])
    if fig_cfg.get("title"):
        fig.suptitle(str(fig_cfg["title"]), color=theme["text"], fontsize=float(fonts.get("title", 14)))

    insets = {int(ins.get("subplot", -1)): ins for ins in (fig_cfg.get("insets") or [])}
    grid_slots = [i for i in range(subplots) if i not in insets]
    gcols = max(1, min(ncols, len(grid_slots)))
    grows = max(1, -(-len(grid_slots) // gcols))

    axes: dict[int, Any] = {}
    grid = fig.subplots(grows, gcols, squeeze=False).ravel()
    for index, slot in enumerate(grid_slots):
        axes[slot] = grid[index]
    for ax in grid[len(grid_slots):]:
        ax.set_visible(False)

    # inset 轴：位置按父轴绘图区的比例给（与 plotly 后端同一套 rect 语义）
    for slot, ins in insets.items():
        parent = axes.get(int(ins.get("parent", 0)))
        if parent is None:
            continue
        rx, ry, rw, rh = [float(v) for v in ins.get("rect", (0.62, 0.62, 0.35, 0.34))]
        axes[slot] = parent.inset_axes([rx, ry, rw, rh])

    by_subplot: dict[int, list[Mapping[str, Any]]] = {}
    for layer in spec_layers(spec):
        by_subplot.setdefault(int(layer.get("subplot", 0)), []).append(layer)

    views: dict[int, dict[str, Any]] = {}
    for subplot, group in by_subplot.items():
        ax = axes.get(subplot)
        if ax is None:
            raise ValueError(f"subplot 越界: {subplot}（共 {len(axes)} 个可用槽位）")
        view = group[0].get("view") or {}
        views[subplot] = view
        slot_fonts = {**fonts, **dict((insets.get(subplot) or {}).get("fonts") or {})}
        ax.set_facecolor(theme["plot"])
        _apply_view(ax, view, theme=theme, fonts=slot_fonts)
        for index, layer in enumerate(group):
            kind = layer.get("kind")
            drawer = DRAWERS.get(kind)
            if drawer is None:
                raise ValueError(f"matplotlib 后端暂不支持 kind={kind}（图层 {layer.get('id')}）")
            drawer(ax, layer, store, index, pixels=pixels)

    for subplot, ax in axes.items():
        group = by_subplot.get(subplot, [])
        view = views.get(subplot, {})
        for layer in group:
            for ann in layer.get("annotations") or []:
                kind = ann.get("type")
                if kind == "hline":
                    ax.axhline(float(ann["y"]), color=ann.get("color", "#94a3b8"), linestyle=":", linewidth=1.0)
                elif kind == "vline":
                    ax.axvline(float(ann["x"]), color=ann.get("color", "#94a3b8"), linestyle=":", linewidth=1.0)
                elif kind == "band":
                    ax.axhspan(float(ann["from"]), float(ann["to"]),
                               color=ann.get("color", "#94a3b8"), alpha=0.15, linewidth=0)
                elif kind == "text":
                    ax.text(ann.get("x", 0.5), ann.get("y", 0.5), str(ann.get("text", "")),
                            transform=ax.transAxes, color=theme["text"],
                            fontsize=float(fonts.get("annotation", 11)))
        if any(layer.get("legend", True) and layer.get("label") for layer in group):
            handles, labels = ax.get_legend_handles_labels()
            keep = [
                (h, lab) for h, lab in zip(handles, labels)
                if any(layer.get("legend", True) and layer.get("label") == lab for layer in group)
            ]
            legend = ax.legend([h for h, _ in keep], [lab for _, lab in keep],
                               fontsize=float(fonts.get("legend", 11)), frameon=False)
            if legend is not None:
                for text in legend.get_texts():
                    text.set_color(theme["text"])
        # 刻度标签在 set_xscale 之后才刷新，这里补一次颜色
        ax.tick_params(axis="both", which="both", colors=theme["text"])
        for text in ax.get_xticklabels() + ax.get_yticklabels():
            text.set_fontsize(float(fonts.get("tick", 11)))
        _ = view

    _draw_decorations(fig, spec, axes, views, theme=theme, fonts=fonts)
    return fig


def savefig(
    spec: Mapping[str, Any],
    store: DataStore,
    path: str | Path,
    *,
    dpi: int | None = None,
    pixels: int | None = None,
) -> Path:
    """把 spec 存成静态图（PNG/SVG/PDF，按扩展名）。"""
    from matplotlib import rc_context

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with rc_context({"font.sans-serif": list(FONT_FALLBACK), "axes.unicode_minus": False}):
        figure = to_figure(spec, store, dpi=dpi, pixels=pixels)
        figure.savefig(target, dpi=dpi or int(spec.get("figure", {}).get("dpi", 100)))
    return target


def render_bytes(
    spec: Mapping[str, Any],
    store: DataStore,
    *,
    width: int = 900,
    height: int = 520,
    dpi: int = 100,
    fmt: str = "png",
    xlim: tuple[float, float] | None = None,
    ylim: tuple[float, float] | None = None,
    with_limits: bool = False,
):

    """按**像素尺寸**渲染，返回图片字节（D33：网页呈现的唯一出口）。

    与 `savefig` 的区别：
    - 尺寸以像素给定（交互窗口按容器大小要图），内部换算成英寸；
    - 可临时覆盖视窗 `xlim/ylim`（前端缩放/平移后请求重绘）；
    - 输出固定 metadata，保证同一 spec + 同一视窗两次渲染**逐字节一致**（像素快照可做回归）。
    """
    import copy as _copy
    import io as _io

    from matplotlib import rc_context

    fmt = (fmt or "png").lower()
    if fmt not in ("png", "svg"):
        raise ValueError(f"不支持的格式 {fmt!r}，只支持 png / svg")
    width = max(80, min(4000, int(width)))
    height = max(60, min(4000, int(height)))
    dpi = max(40, min(400, int(dpi)))

    work = _copy.deepcopy(dict(spec))
    fig_cfg = work.setdefault("figure", {})
    fig_cfg["size"] = [width / dpi, height / dpi]
    if xlim or ylim:
        for layer in work.get("layers") or []:
            view = layer.setdefault("view", {})
            if xlim:
                view["xlim"] = [float(xlim[0]), float(xlim[1])]
            if ylim:
                view["ylim"] = [float(ylim[0]), float(ylim[1])]

    buffer = _io.BytesIO()
    with rc_context({"font.sans-serif": list(FONT_FALLBACK), "axes.unicode_minus": False}):
        # 按像素宽度抽稀（D35）：6×20k 点直接画会到 300–400 ms，抽到 ≤2 点/列后回到百毫秒内
        figure = to_figure(work, store, dpi=dpi, pixels=width)
        meta = {"Software": None} if fmt == "png" else {"Date": None}
        figure.savefig(buffer, format=fmt, dpi=dpi, metadata=meta, bbox_inches=None)
        payload = buffer.getvalue()
        limits = None
        if with_limits and figure.axes:
            main = figure.axes[0]
            box = [float(v) for v in main.get_position().bounds]  # x0, y0, w, h（figure 比例）
            inset_slots = {int(i.get("subplot", -1)) for i in (fig_cfg.get("insets") or [])}
            grid_slots = [i for i in range(int(fig_cfg.get("subplots", 1))) if i not in inset_slots]
            slots = []
            for slot, ax in zip(grid_slots, figure.axes):
                slots.append({"slot": int(slot),
                              "box": [round(float(v), 5) for v in ax.get_position().bounds]})
            limits = {"xlim": [float(v) for v in main.get_xlim()],
                      "ylim": [float(v) for v in main.get_ylim()],
                      "box": box,
                      "slots": slots,
                      "px": [int(width), int(height)]}
    return (payload, limits) if with_limits else payload


# ---------------- 注册 P13-01 的四种图层（渲染统一走 mpl，builder 留空） ----------------
reg.register("hist", 2, None, defaults={"bins": 30}, description="直方图（服务端分箱）")
reg.register("pie", 2, None, defaults={"autopct": "%1.1f%%"}, description="饼图")
reg.register("image", 2, None, defaults={"cmap": "viridis", "colorbar": True}, description="图像 / 热图")
reg.register("table", 2, None, defaults={"fontsize": 10}, description="表格")

# ---------------- 注册 P13-02 的场类图层 ----------------
reg.register("heatmap", 2, None, defaults={"cmap": "viridis"}, description="热图（z 或 x/y/z）")
reg.register("contour", 2, None, defaults={"levels": 8}, description="等值线（可 clabel）")
reg.register("contourf", 2, None, defaults={"levels": 8}, description="填充等值线")
reg.register("correlation", 2, None, defaults={"cmap": "RdBu_r", "vmin": -1.0, "vmax": 1.0},
             aliases=("corr", "correlation_matrix"), description="相关系数矩阵（init-only 聚合）")

# ---------------- 注册 P13-03 的矢量场图层 ----------------
reg.register("quiver", 2, None, defaults={"color_by": "magnitude"}, description="矢量箭头图")
reg.register("streamplot", 2, None, defaults={"density": 1.0}, description="流线图（需二维网格）")
reg.register("barbs", 2, None, defaults={"color_by": "magnitude"}, description="风羽图（barbs）")
