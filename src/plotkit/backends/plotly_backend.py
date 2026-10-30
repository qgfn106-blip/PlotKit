"""plotly 后端：spec + store → plotly 图对象（纯 dict，前端直接 `Plotly.react`）。"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence

import numpy as np

from ..spec.model import DEFAULT_FONTS
from ..spec.model import layers as spec_layers
from ..spec.model import nrows, subplot_xy
from ..store.downsample import minmax_envelope
from ..store.registry import DataStore
from . import registry as reg

PALETTE = (
    "#4fc3f7", "#ff8a65", "#aed581", "#ba68c8", "#ffd54f",
    "#4db6ac", "#f06292", "#7986cb", "#a1887f", "#90a4ae",
)

THEMES: dict[str, dict[str, str]] = {
    "default": {"paper": "#ffffff", "plot": "#ffffff", "text": "#1f2937", "grid": "#e5e7eb"},
    "netlab-dark": {"paper": "#0f172a", "plot": "#111827", "text": "#e2e8f0", "grid": "#1f2937"},
}

MODE_MAP = {"lines": "lines", "markers": "markers", "lines+markers": "lines+markers"}


GREEK = {
    "theta": "θ", "Delta": "Δ", "delta": "δ", "rho": "ρ", "beta": "β", "mu": "µ",
    "sigma": "σ", "alpha": "α", "gamma": "γ", "phi": "φ", "omega": "ω", "Omega": "Ω",
    "lambda": "λ", "pi": "π", "cdot": "·", "times": "×", "langle": "⟨", "rangle": "⟩",
}


def math_text(value: Any) -> str:
    """把 `$D_{eff}^{\theta}$` 这类 mathtext 降级成 plotly 认识的 HTML。

    plotly 不支持 LaTeX（B 决策：浏览器做预览、matplotlib 出正式图），
    所以这里只做够用的替换：希腊字母、上下标 → `<sub>`/`<sup>`，并去掉 `$`。
    """
    text = str(value)
    if "\\" in text:
        for name, char in GREEK.items():
            text = text.replace("\\" + name, char)
    text = text.replace("$", "")
    text = re.sub(r"\^\{([^}]*)\}", r"<sup>\g<1></sup>", text)
    text = re.sub(r"_\{([^}]*)\}", r"<sub>\g<1></sub>", text)
    text = re.sub(r"\^(\w)", r"<sup>\g<1></sup>", text)
    text = re.sub(r"_(\w)", r"<sub>\g<1></sub>", text)
    return text


def color_for(index: int) -> str:
    return PALETTE[index % len(PALETTE)]


def _plain(values: np.ndarray) -> list[Any]:
    """numpy → JSON 可序列化列表；非有限值（NaN/Inf）→ None，前端跳过不画断线。"""
    array = np.asarray(values)
    if array.ndim == 0:
        array = array.reshape(1)
    out: list[Any] = []
    for value in array.tolist():
        if isinstance(value, float) and not math.isfinite(value):
            out.append(None)
        else:
            out.append(value)
    return out


def _window_slice(x: np.ndarray, trange) -> tuple[int, int]:
    """按 [t0, t1] 截取下标区间；数据是单调追加的，优先用 searchsorted。"""
    if trange is None or x.size == 0:
        return 0, x.size
    t0, t1 = float(trange[0]), float(trange[1])
    if x.size > 1 and np.all(np.diff(x) >= 0):
        i0 = int(np.searchsorted(x, t0, side="left"))
        i1 = int(np.searchsorted(x, t1, side="right"))
        return i0, max(i1, i0)
    mask = (x >= t0) & (x <= t1)
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return 0, 0
    return int(idx[0]), int(idx[-1]) + 1


def _xy(layer: Mapping[str, Any], store: DataStore, *, pixels: int | None, per_pixel: float,
        trange=None):
    data = layer.get("data", {})
    x = np.asarray(store.values(data["x"])).ravel().astype(float)
    y = np.asarray(store.values(data["y"])).ravel().astype(float)
    if x.size != y.size:
        raise ValueError(
            f"图层 {layer.get('id')} 的 x/y 长度不一致: {x.size} vs {y.size}"
            f"（x={data['x']!r}, y={data['y']!r}）"
        )
    i0, i1 = _window_slice(x, trange)
    x, y = x[i0:i1], y[i0:i1]
    has_error = any(k.startswith("error_") for k in data)
    if pixels and not has_error:
        x, y = minmax_envelope(x, y, pixels, per_pixel=per_pixel)
    return x, y


def _error_bars(layer: Mapping[str, Any], store: DataStore, *, trange=None) -> dict[str, Any]:
    """误差棒：data.error_x / error_y（+ *_minus）指向数据集，样式取自 style.error。"""
    data = layer.get("data", {})
    if not any(key in data for key in ("error_x", "error_y")):
        return {}
    cfg = dict((layer.get("style") or {}).get("error") or {})
    color = cfg.get("color")
    thickness = float(cfg.get("thickness", 1.2))
    out: dict[str, Any] = {}
    for axis in ("x", "y"):
        plus_name = data.get(f"error_{axis}")
        if not plus_name:
            continue
        series = np.asarray(store.values(plus_name)).ravel().astype(float)
        i0, i1 = _window_slice(np.asarray(store.values(data["x"])).ravel().astype(float), trange)
        plus = _plain(series[i0:i1])
        item: dict[str, Any] = {
            "type": "data",
            "array": plus,
            "visible": True,
            "thickness": thickness,
            "width": cfg.get("width"),      # None = 不给端帽
            "opacity": float(cfg.get("opacity", 1.0)),
        }
        minus_name = data.get(f"error_{axis}_minus")
        if minus_name:
            item["symmetric"] = False
            minus_series = np.asarray(store.values(minus_name)).ravel().astype(float)
            item["arrayminus"] = _plain(minus_series[i0:i1])
        if color:
            item["color"] = color
        out[f"error_{axis}"] = item
    return out


def _trace_style(layer: Mapping[str, Any], index: int) -> dict[str, Any]:
    style = layer.get("style") or {}
    color = style.get("color") or color_for(index)
    opacity = float(style.get("opacity", 1.0))
    return {
        "color": color,
        "width": float(style.get("width", 1.6)),
        "dash": style.get("dash", "solid"),
        "opacity": opacity,
        "marker": dict(style.get("marker") or {}),
        "fill": style.get("fill"),
        "mode": style.get("mode", "lines"),
    }


def _build_line(layer, store, index, *, pixels, per_pixel, trange=None) -> dict[str, Any]:
    x, y = _xy(layer, store, pixels=pixels, per_pixel=per_pixel, trange=trange)
    st = _trace_style(layer, index)
    trace: dict[str, Any] = {
        "type": "scatter",
        "mode": MODE_MAP.get(st["mode"], "lines"),
        "x": _plain(x),
        "y": _plain(y),
        "name": layer.get("label") or layer.get("data", {}).get("y", ""),
        "line": {"color": st["color"], "width": st["width"], "dash": st["dash"]},
        "marker": {
            "color": st["color"],
            "size": float(st["marker"].get("size", 6)),
            "symbol": st["marker"].get("symbol", "circle"),
            "opacity": float(st["marker"].get("opacity", 1.0)),
        },
        "opacity": st["opacity"],
        "hovertemplate": "%{x:.6g}<br>%{y:.6g}<extra>%{fullData.name}</extra>",
        "cliponaxis": False,
    }
    marker_line = dict(st["marker"].get("line") or {})
    if marker_line.get("width"):
        trace["marker"]["line"] = {
            "color": marker_line.get("color") or st["color"],
            "width": float(marker_line["width"]),
        }
    sizes = st["marker"].get("sizes")
    if sizes is not None:
        trace["marker"]["size"] = [float(v) for v in sizes]
    trace.update(_error_bars(layer, store, trange=trange))
    if st["fill"]:
        trace["fill"] = st["fill"]
    return trace


def _build_scatter(layer, store, index, *, pixels, per_pixel, trange=None) -> dict[str, Any]:
    trace = _build_line(layer, store, index, pixels=pixels, per_pixel=per_pixel, trange=trange)
    trace["mode"] = "markers" if trace["mode"] == "lines" else trace["mode"]
    trace["line"] = {"width": 0}
    return trace


def _build_bar(layer, store, index, *, pixels, per_pixel, trange=None) -> dict[str, Any]:
    x, y = _xy(layer, store, pixels=pixels, per_pixel=per_pixel, trange=trange)
    st = _trace_style(layer, index)
    trace = {
        "type": "bar",
        "x": _plain(x),
        "y": _plain(y),
        "name": layer.get("label") or layer.get("data", {}).get("y", ""),
        "marker": {"color": st["color"], "opacity": st["opacity"]},
        "width": float(layer.get("style", {}).get("bar_width", 0.6)),
        "hovertemplate": "%{x}<br>%{y:.6g}<extra>%{fullData.name}</extra>",
    }
    trace.update(_error_bars(layer, store, trange=trange))
    return trace


def _layer_decorations(
    layer: Mapping[str, Any], subplot: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """图层的 annotations → (文字 trace 列表, shape 列表)。

    文字不用 plotly 的 `layout.annotations`：那条路径在部分 bundle/配置下整组不渲染
    （实测一个非法 annotation 会让同一数组里的文字全部消失），改用 `mode="text"` 的 trace
    更稳，还能跟着缩放走。
    """
    texts: list[dict[str, Any]] = []
    shapes: list[dict[str, Any]] = []
    xref, yref = _axis_ref(subplot, "x"), _axis_ref(subplot, "y")
    for ann in layer.get("annotations") or []:
        kind = ann.get("type")
        if kind == "text":
            texts.append({
                "x": ann.get("x", 0.5),
                "y": ann.get("y", 0.5),
                "text": math_text(ann.get("text", "")),
                "position": ann.get("pos", "top center"),
                "size": float(ann.get("size", 11)),
                "color": ann.get("color"),
            })
        elif kind == "hline":
            shapes.append({"type": "line", "xref": "paper", "x0": 0, "x1": 1,
                           "y0": ann.get("y"), "y1": ann.get("y"), "yref": yref,
                           "line": {"color": ann.get("color", "#94a3b8"), "dash": "dot"}})
        elif kind == "vline":
            shapes.append({"type": "line", "yref": "paper", "y0": 0, "y1": 1,
                           "x0": ann.get("x"), "x1": ann.get("x"), "xref": xref,
                           "line": {"color": ann.get("color", "#94a3b8"), "dash": "dot"}})
        elif kind == "band":
            shapes.append({"type": "rect", "xref": "paper", "yref": yref,
                           "x0": 0, "x1": 1,
                           "y0": ann.get("from"), "y1": ann.get("to"),
                           "fillcolor": ann.get("color", "rgba(148,163,184,0.15)"),
                           "line": {"width": 0}})
    return texts, shapes


def _text_trace(
    x: float,
    y: float,
    text: str,
    *,
    subplot: int,
    size: float,
    color: str | None,
    position: str = "top center",
) -> dict[str, Any]:
    font: dict[str, Any] = {"size": float(size)}
    if color:
        font["color"] = color
    return {
        "type": "scatter",
        "mode": "text",
        "x": [x],
        "y": [y],
        "text": [math_text(text)],
        "textposition": position,
        "xaxis": _axis_ref(subplot, "x"),
        "yaxis": _axis_ref(subplot, "y"),
        "showlegend": False,
        "hoverinfo": "skip",
        "cliponaxis": False,
        "textfont": font,
    }


def _axis_name(subplot: int, kind: str) -> str:
    """layout 里的轴键：xaxis / xaxis2 / yaxis3 ……"""
    return f"{kind}axis" if subplot == 0 else f"{kind}axis{subplot + 1}"


def _axis_ref(subplot: int, kind: str) -> str:
    """trace/annotation 里的轴引用：x / x2 / y3 ……

    注意这跟 layout 键不是一回事：trace.xaxis 只认 "x" / "x2"，写成 "xaxis2"
    会被 plotly 静默忽略并回落到第一个轴（表现为所有子图叠在一起）。
    """
    return kind if subplot == 0 else f"{kind}{subplot + 1}"


def _axis_layout(
    view: Mapping[str, Any],
    *,
    axis: str,
    subplot: int,
    fonts: Mapping[str, float],
) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    xlim = view.get("xlim") if axis == "x" else view.get("ylim")
    scale = view.get("yscale" if axis == "y" else "xscale", "linear")
    if xlim:
        lo, hi = float(xlim[0]), float(xlim[1])
        if scale == "log":
            # plotly 的对数轴 range 用的是"指数"，不是数据值
            if lo <= 0 or hi <= 0:
                raise ValueError(f"{axis}lim 在对数轴上必须为正数: {xlim!r}")
            lo, hi = math.log10(lo), math.log10(hi)
        cfg["range"] = [lo, hi]
    title = view.get(f"{axis}label")
    if title:
        cfg["title"] = {"text": math_text(title), "font": {"size": float(fonts.get("axis", 12))}}
    if scale == "log":
        cfg["type"] = "log"
        cfg["exponentformat"] = "power"   # 10^-1 而不是 1e-1
        mode = str(view.get("loglabels", "sci"))
        plain = mode == "plain" or mode == f"plain-{axis}"
        if not plain:
            cfg["dtick"] = 1              # 只标整数量级，避免 2/5 混排
    cfg["showgrid"] = bool(view.get("grid", True))
    if axis == "y" and view.get("invert_y") and "range" not in cfg:
        cfg["autorange"] = "reversed"
    cfg["zeroline"] = bool(view.get("zero_line", False))
    cfg["tickfont"] = {"size": float(fonts.get("tick", 11))}
    ticks = dict(view.get("ticks") or {})
    cfg["ticks"] = "inside" if ticks.get("inside") else "outside"
    if ticks.get("mirror"):
        cfg["mirror"] = "all"
    if ticks.get("minor"):
        cfg["minor"] = {"ticks": "inside", "ticklen": 3, "showgrid": False}
    return cfg


def _step(value: float, scale: str, decades: float) -> float:
    """沿某个轴的"数量级台阶"走一步：log 轴乘 10^n，线性轴加 n。"""
    return float(value) * (10.0 ** decades) if scale == "log" else float(value) + decades


def _decorations(
    fig_cfg: Mapping[str, Any],
    views: Mapping[int, Mapping[str, Any]],
    fonts: Mapping[str, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """figure.shapes → plotly 的 shapes + 文字 trace（斜率三角、箭头、线/框）。

    箭头不能用 plotly 的 annotation arrow：`axref/ayref` 在**对数轴**上算不出路径
    （实测 path 数为 0），所以拆成"线 + 三角 marker"两件画。
    """
    shapes: list[dict[str, Any]] = []
    extra: list[dict[str, Any]] = []
    for shape in fig_cfg.get("shapes") or []:
        kind = shape.get("type")
        subplot = int(shape.get("subplot", 0))
        view = views.get(subplot, {})
        xref, yref = _axis_ref(subplot, "x"), _axis_ref(subplot, "y")
        line = {
            "color": shape.get("color", "#94a3b8"),
            "width": float(shape.get("width", 1.4)),
            "dash": shape.get("dash", "solid"),
        }
        base = {"xref": xref, "yref": yref, "line": line}

        if kind == "line":
            shapes.append({**base, "type": "line",
                           "x0": shape["x0"], "y0": shape["y0"],
                           "x1": shape["x1"], "y1": shape["y1"]})
        elif kind == "rect":
            shapes.append({**base, "type": "rect",
                           "x0": shape["x0"], "y0": shape["y0"],
                           "x1": shape["x1"], "y1": shape["y1"],
                           "fillcolor": shape.get("fill") or "rgba(148,163,184,0.12)"})
        elif kind == "path":
            shapes.append({**base, "type": "path", "path": shape["d"]})
        elif kind == "arrow":
            sx, sy = shape["start"]
            ex, ey = shape["end"]
            color = shape.get("color", "#94a3b8")
            shapes.append({**base, "type": "line", "x0": sx, "y0": sy, "x1": ex, "y1": ey})
            extra.append({
                "type": "scatter", "mode": "markers",
                "x": [ex], "y": [ey],
                "xaxis": xref, "yaxis": yref,
                "marker": {"symbol": "triangle-up", "size": 11, "color": color},
                "showlegend": False, "hoverinfo": "skip", "cliponaxis": False,
                "_axis_slot": subplot,
            })
            if shape.get("text"):
                extra.append(_text_trace(
                    ex, ey, str(shape["text"]),
                    subplot=subplot, size=float(fonts.get("annotation", 11)),
                    color=color, position="middle right",
                ))
        elif kind == "triangle":
            x0, y0 = shape.get("anchor", (1.0, 1.0))
            decades = float(shape.get("decades", 1.0))
            slope = float(shape.get("slope", -3.0))
            x1 = _step(x0, str(view.get("xscale", "linear")), decades)
            y1 = _step(y0, str(view.get("yscale", "linear")), slope * decades)
            for a, b in (((x0, y0), (x1, y1)), ((x1, y1), (x1, y0)), ((x0, y0), (x1, y0))):
                shapes.append({**base, "type": "line",
                               "x0": a[0], "y0": a[1], "x1": b[0], "y1": b[1]})
            if shape.get("text"):
                extra.append(_text_trace(
                    (x0 + x1) / 2, y0, str(shape["text"]),
                    subplot=subplot, size=float(fonts.get("annotation", 11)),
                    color=shape.get("color"), position="bottom center",
                ))
    return shapes, extra


def time_bounds(spec: Mapping[str, Any], store: DataStore) -> tuple[float | None, float | None]:
    """所有图层的 x 数据的 (最小, 最大)，用来实现"最近 N 秒"窗口。"""
    lo: float | None = None
    hi: float | None = None
    for layer in spec_layers(spec):
        data = layer.get("data", {})
        name = data.get("x")
        if not name or name not in store:
            continue
        values = np.asarray(store.values(name)).ravel()
        if values.size == 0:
            continue
        try:
            numeric = values.astype(float)
        except (TypeError, ValueError):
            continue
        numeric = numeric[np.isfinite(numeric)]
        if numeric.size == 0:
            continue
        low, high = float(numeric.min()), float(numeric.max())
        lo = low if lo is None else min(lo, low)
        hi = high if hi is None else max(hi, high)
    return lo, hi


def to_figure(
    spec: Mapping[str, Any],
    store: DataStore,
    *,
    pixels: int | None = None,
    per_pixel: float = 2.0,
    t_end: float | None = None,
) -> dict[str, Any]:
    """把 spec 转成 plotly 的 {data, layout}。"""
    if not spec_layers(spec) and not spec.get("figure", {}).get("subplots"):
        return {"data": [], "layout": {}}

    fig_cfg = spec.get("figure", {})
    theme_name = str(fig_cfg.get("theme", "default"))
    theme = THEMES.get(theme_name, THEMES["default"])
    fonts: dict[str, float] = {**DEFAULT_FONTS, **dict(fig_cfg.get("fonts") or {})}
    ncols = int(fig_cfg.get("ncols", 1))
    subplots = int(fig_cfg.get("subplots", 1))
    rows = nrows(ncols, subplots)

    # "最近 N 秒"窗口：窗口跟着右端走，右端默认是数据里的最新时刻
    window = fig_cfg.get("window")
    trange: tuple[float, float] | None = None
    if window:
        lo, hi = time_bounds(spec, store)
        if hi is not None:
            right = float(t_end) if t_end is not None else hi
            # 数据还不够长时从数据起点开始画，别给个负时间轴
            left = max(right - float(window), lo if lo is not None else right - float(window))
            trange = (left, right)

    data: list[dict[str, Any]] = []
    shapes: list[dict[str, Any]] = []
    axis_titles: dict[int, dict[str, Any]] = {}

    for index, layer in enumerate(spec_layers(spec)):
        if layer.get("kind") not in reg.LAYER_SPECS:
            continue
        builder = reg.LAYER_SPECS[layer["kind"]].builder
        if builder is None:
            # D33 起 plotly 只是遗留出口：新图层（hist/heatmap/3D…）没有 plotly builder，
            # 这里跳过而不是让整张图 500——正式渲染走 /api/render（matplotlib）。
            continue
        trace = builder(layer, store, index, pixels=pixels, per_pixel=per_pixel, trange=trange)
        subplot = int(layer.get("subplot", 0))
        trace["xaxis"] = _axis_ref(subplot, "x")
        trace["yaxis"] = _axis_ref(subplot, "y")
        trace["showlegend"] = bool(layer.get("legend", True))
        data.append(trace)
        layer_texts, layer_shapes = _layer_decorations(layer, subplot)
        for item in layer_texts:
            data.append(_text_trace(
                item["x"], item["y"], item["text"],
                subplot=subplot, size=item["size"], color=item["color"],
                position=item["position"],
            ))
        shapes.extend(layer_shapes)
        view = layer.get("view") or {}
        axis_titles.setdefault(subplot, {}).update(
            {k: v for k, v in view.items() if v is not None and v != ""}
        )

    all_views: dict[int, dict[str, Any]] = dict(axis_titles)
    fig_shapes, extra_traces = _decorations(fig_cfg, all_views, fonts)
    shapes.extend(fig_shapes)
    for trace in extra_traces:
        trace.pop("_axis_slot", None)
    data.extend(extra_traces)

    layout: dict[str, Any] = {
        "title": {
            "text": math_text(fig_cfg.get("title") or ""),
            "font": {"size": float(fonts.get("title", 14))},
        },
        "paper_bgcolor": theme["paper"],
        "plot_bgcolor": theme["plot"],
        "font": {"color": theme["text"], "size": float(fonts.get("tick", 11))},
        "showlegend": any(layer.get("legend", True) for layer in spec_layers(spec)),
        "hovermode": "x unified" if fig_cfg.get("link_x") else "closest",
        "margin": {"l": 56, "r": 18, "t": 48 if fig_cfg.get("title") else 18, "b": 44},
        "shapes": shapes,
        "legend": {"font": {"size": float(fonts.get("legend", 11))}},
        # size/dpi 只对静态导出（matplotlib）有意义；浏览器里必须自适应容器，
        # 否则一台 1100px 宽的画布会把右侧面板挤出屏幕。
        "autosize": True,
    }

    gap = 0.08 if (rows > 1 or ncols > 1) else 0.0
    # inset 槽位不参与网格，它的位置由父轴绘图区的比例决定
    insets = {int(ins.get("subplot", -1)): ins for ins in (fig_cfg.get("insets") or [])}
    grid_slots = [i for i in range(subplots) if i not in insets]

    for subplot in range(subplots):
        view = dict(axis_titles.get(subplot, {}))
        # 滚动窗口：没显式设 xlim 的普通子图跟着窗口走；内嵌图有自己的坐标不跟
        if trange and subplot not in insets and not view.get("xlim"):
            view["xlim"] = [trange[0], trange[1]]
        slot_fonts = {**fonts, **dict((insets.get(subplot) or {}).get("fonts") or {})}
        xaxis = _axis_layout(view, axis="x", subplot=subplot, fonts=slot_fonts)
        yaxis = _axis_layout(view, axis="y", subplot=subplot, fonts=slot_fonts)
        if subplot in insets:
            # 先占位，等父轴 domain 算完再覆盖（父轴可能排在后面）
            xaxis["domain"] = [0.0, 0.0]
            yaxis["domain"] = [0.0, 0.0]
            xaxis["anchor"] = _axis_ref(subplot, "y")
            yaxis["anchor"] = _axis_ref(subplot, "x")
            layout[_axis_name(subplot, "x")] = xaxis
            layout[_axis_name(subplot, "y")] = yaxis
            continue
        row, col = subplot_xy(subplot, ncols) if subplot in grid_slots else (0, 0)
        slot_index = grid_slots.index(subplot) if subplot in grid_slots else 0
        gcols = max(1, min(ncols, len(grid_slots)))
        grows = max(1, -(-len(grid_slots) // gcols))
        row, col = slot_index // gcols, slot_index % gcols
        xaxis["domain"] = [col / gcols, (col + 1) / gcols - gap / gcols]
        yaxis["domain"] = [1 - (row + 1) / grows, 1 - row / grows - gap / grows]
        # 每个子图的 x/y 必须显式互锚，否则 plotly 把 axis2 当成"叠加轴"画在同一块区域
        # anchor 的值同样只认 "x"/"x2" 形式的轴 id，不认 layout 键名
        xaxis["anchor"] = _axis_ref(subplot, "y")
        yaxis["anchor"] = _axis_ref(subplot, "x")
        xaxis.setdefault("gridcolor", theme["grid"])
        yaxis.setdefault("gridcolor", theme["grid"])
        layout[_axis_name(subplot, "x")] = xaxis
        layout[_axis_name(subplot, "y")] = yaxis

    # inset：rect 是父轴绘图区的比例，映射到 figure 的归一化坐标
    for slot, ins in insets.items():
        parent = int(ins.get("parent", 0))
        pw = layout.get(_axis_name(parent, "x"), {}).get("domain", [0.0, 1.0])
        ph = layout.get(_axis_name(parent, "y"), {}).get("domain", [0.0, 1.0])
        rx, ry, rw, rh = [float(v) for v in ins.get("rect", (0.62, 0.62, 0.35, 0.34))]
        layout[_axis_name(slot, "x")]["domain"] = [pw[0] + rx * (pw[1] - pw[0]),
                                                   pw[0] + (rx + rw) * (pw[1] - pw[0])]
        layout[_axis_name(slot, "y")]["domain"] = [ph[0] + ry * (ph[1] - ph[0]),
                                                   ph[0] + (ry + rh) * (ph[1] - ph[0])]
        # inset 自己要画框、不画网格，视觉上才像"图里的小图"
        layout[_axis_name(slot, "x")].setdefault("showline", True)
        layout[_axis_name(slot, "y")].setdefault("showline", True)
        layout[_axis_name(slot, "x")]["showgrid"] = bool(axis_titles.get(slot, {}).get("grid", False))
        layout[_axis_name(slot, "y")]["showgrid"] = bool(axis_titles.get(slot, {}).get("grid", False))

    return {"data": data, "layout": layout}


# ---------------- 注册 v0 三种图层 ----------------
reg.register(
    "line", 2, _build_line,
    defaults={"mode": "lines", "width": 1.6},
    description="折线 / 曲线（时间序列主力）",
)
reg.register(
    "marker", 2, _build_scatter,
    defaults={"mode": "markers"},
    aliases=("scatter", "points"),
    description="散点",
)
reg.register(
    "bar", 2, _build_bar,
    defaults={"mode": "bars"},
    description="柱状图",
)
