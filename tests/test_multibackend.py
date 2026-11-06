"""D38 多后端框架：调度、注册表兼容、精度保持、可选后端。"""

from __future__ import annotations

import numpy as np
import pytest

import plotkit as pk
from plotkit.backends import dispatch, registry


def _surface_figure(points: int = 24):
    x = np.linspace(-2, 2, points)
    y = np.linspace(-2, 2, points)
    X, Y = np.meshgrid(x, y)
    fig = pk.figure(title="surface")
    fig.add("surface", {"x": X, "y": Y, "z": np.sin(np.hypot(X, Y))})
    return fig


def _line_figure():
    t = np.arange(200, dtype=float)
    fig = pk.figure()
    fig.add_data("t", t, role="coord")
    fig.add_data("y", np.sin(t / 10.0), role="series")
    fig.add_plot(x="t", y="y")
    return fig


# ---------------------------------------------------------------- 调度层


def test_available_backends_reports_mpl():
    table = dispatch.available_backends()
    assert table["mpl"] is True
    assert set(table) >= {"mpl", "pyvista"}


def test_choose_two_dimensional_uses_mpl():
    spec = _line_figure().spec
    assert dispatch.choose(spec) == "mpl"
    assert dispatch.choose(spec, "auto") == "mpl"


def test_choose_unknown_backend_raises():
    spec = _line_figure().spec
    with pytest.raises(dispatch.BackendUnavailable):
        dispatch.choose(spec, "no-such-backend")


def test_choose_unavailable_backend_raises(monkeypatch):
    monkeypatch.setattr(dispatch, "_has_module", lambda name: False)
    spec = _surface_figure().spec
    with pytest.raises(dispatch.BackendUnavailable):
        dispatch.choose(spec, "pyvista")


def test_choose_three_dimensional_auto():
    spec = _surface_figure().spec
    expected = "pyvista" if dispatch.available_backends().get("pyvista") else "mpl"
    assert dispatch.choose(spec, "auto") == expected


def test_render_result_shape_and_tuple():
    fig = _line_figure()
    result = fig.render_result(width=240, height=160)
    assert result.backend == "mpl"
    assert result.fmt == "png"
    assert (result.width, result.height) == (240, 160)
    assert len(result) == len(result.payload)
    payload, limits = result.as_tuple()
    assert payload is result.payload
    assert limits is None


def test_render_backend_argument_is_used():
    fig = _line_figure()
    result = fig.render_result(width=200, height=140, backend="mpl")
    assert result.backend == "mpl"
    assert result.payload[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------- 注册表兼容


def test_layer_spec_builder_backwards_compatible():
    """老代码仍按 `spec.builder` 取用：它必须等于 builders["mpl"]。"""
    name = "_pk_test_builder_compat"
    builder = lambda layer, store: []  # noqa: E731
    try:
        registry.register(
            name,
            2,
            builder,
            defaults={},
            passthrough=(),
            description="兼容性测试",
            overwrite=True,
        )
        spec = registry.resolve(name)
        assert spec.builders and spec.builder is spec.builders["mpl"]
        assert spec.backend_names == ("mpl",)
        assert spec.as_dict()["backends"] == ["mpl"]
    finally:
        registry.LAYER_SPECS.pop(name, None)
        registry.ALIASES.pop(name, None)


def test_register_accepts_builders_mapping():
    name = "_pk_test_multi"
    try:
        registry.register(
            name,
            2,
            builders={"mpl": lambda layer, store: []},
            defaults={"marker": False},
            passthrough=(),
            description="测试用",
            overwrite=True,
        )
        spec = registry.resolve(name)
        assert spec.builder_for("mpl") is not None
        assert spec.builder_for("pyvista") is None
    finally:
        registry.LAYER_SPECS.pop(name, None)


def test_attach_builder_adds_backend():
    spec = registry.resolve("line")
    before = spec.builder_for("pyvista")
    try:
        registry.attach_builder("line", "pyvista", lambda layer, store: [])
        assert registry.resolve("line").builder_for("pyvista") is not None
    finally:
        # 还原：重挂回原来的（可能为 None）
        if before is None:
            current = registry.resolve("line")
            builders = dict(current.builders)
            builders.pop("pyvista", None)
            import dataclasses

            registry.LAYER_SPECS["line"] = dataclasses.replace(
                current, builders=builders
            )


# ---------------------------------------------------------------- 精度保持


def test_as_float_keep_preserves_float32():
    from plotkit.backends.mpl_backend import as_float_keep

    arr32 = np.arange(10, dtype=np.float32)
    assert as_float_keep(arr32).dtype == np.float32
    assert as_float_keep(np.arange(10, dtype=np.float64)).dtype == np.float64
    assert as_float_keep(np.arange(10, dtype=np.int32)).dtype == np.float64


# ---------------------------------------------------------------- 可选后端


pyvista = pytest.importorskip("pyvista", reason="未安装 pyvista")


def test_pyvista_renders_surface():
    fig = _surface_figure()
    result = fig.render_result(
        width=320, height=220, backend="pyvista", with_limits=True
    )
    assert result.backend == "pyvista"
    assert result.payload[:8] == b"\x89PNG\r\n\x1a\n"
    assert result.limits and "xlim" in result.limits and "zlim" in result.limits


def test_hybrid_svg_is_raster_scene_plus_vector_overlay(monkeypatch):
    """默认三维矢量出口 = 混合：一张位图 + 真矢量坐标轴/刻度/标题。"""
    monkeypatch.delenv("PLOTKIT_3D_SVG", raising=False)
    fig = _surface_figure()
    result = fig.render_result(width=320, height=240, backend="pyvista", fmt="svg")
    text = result.payload.decode("utf-8")
    assert result.backend == "pyvista"
    assert text.count("<image") == 1  # 只有三维场景是位图
    assert text.count("<path") > 30  # 轴/刻度/色块是真矢量
    assert 'id="text' in text  # 标题与刻度是文字对象，可检索


def test_hybrid_can_be_disabled_with_env(monkeypatch):
    monkeypatch.setenv("PLOTKIT_3D_SVG", "mpl")
    fig = _surface_figure()
    result = fig.render_result(width=200, height=140, backend="pyvista", fmt="svg")
    text = result.payload.decode("utf-8")
    assert result.backend == "mpl"
    # mpl 自己的色标条是 3.6pt 宽的窄位图，不算「整幅位图」；场景本体必须全是矢量
    assert text.count("<image") <= 1
    assert text.count("<path") > 50


def test_pyvista_svg_falls_back_to_mpl_when_hybrid_disabled(monkeypatch):
    """关掉混合后，SVG 走 mpl 纯矢量：VTK 9.x 的 GL2PS 在 OpenGL2 后端只会塞位图。"""
    monkeypatch.setenv("PLOTKIT_3D_SVG", "mpl")
    fig = _surface_figure()
    result = fig.render_result(width=200, height=140, backend="pyvista", fmt="svg")
    assert result.backend == "mpl"
    assert result.fmt == "svg"
    text = result.payload.decode("utf-8", "ignore")
    assert "<svg" in text and text.count("<path") > 50  # 真矢量路径，不是 <image>
    assert result.meta.get("fallback") == "mpl"


def test_pyvista_backend_rejects_svg_directly():
    """直接调后端（不经 dispatch）仍应明确拒绝，而不是悄悄出位图。"""
    from plotkit.backends import pyvista_backend

    fig = _surface_figure()
    with pytest.raises(dispatch.BackendUnsupported):
        pyvista_backend.render_result(
            fig.spec, fig.store, width=200, height=140, fmt="svg"
        )


def test_pyvista_auto_fallback_for_two_dimensional():
    fig = _line_figure()
    result = fig.render_result(width=200, height=140, backend="auto")
    assert result.backend == "mpl"


def test_pyvista_renders_from_foreign_thread():
    """离屏 OpenGL 上下文是线程亲和的：从别的线程调用必须也成功（内部会转到 VTK 线程）。"""
    import threading

    fig = _surface_figure()
    box: dict[str, object] = {}

    def work():
        try:
            result = fig.render_result(width=260, height=180, backend="pyvista")
            box["size"] = len(result.payload)
        except Exception as exc:  # noqa: BLE001
            box["error"] = f"{type(exc).__name__}: {exc}"

    thread = threading.Thread(target=work)
    thread.start()
    thread.join(timeout=120)
    assert "error" not in box, box.get("error")
    assert box.get("size", 0) > 1000


def test_close_plotters_is_safe():
    from plotkit.backends import pyvista_backend

    fig = _surface_figure()
    fig.render_result(width=200, height=140, backend="pyvista")
    pyvista_backend.close_plotters()  # 在主线程关必须转到 VTK 线程，否则段错误
    again = fig.render_result(width=200, height=140, backend="pyvista")
    assert again.payload[:8] == b"\x89PNG\r\n\x1a\n"


def test_stream3d_paths_shared_between_backends():
    """硬边界 §5.3：pyvista 的 stream3d 复用 mpl 的 RK2，轨迹必须同源。"""
    from plotkit.backends import mpl_backend

    x = np.linspace(-2, 2, 9)
    y = np.linspace(-2, 2, 9)
    z = np.linspace(-1, 1, 5)
    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")
    fig = pk.figure()
    fig.add(
        "stream3d",
        {
            "x": X,
            "y": Y,
            "z": Z,
            "u": np.ones_like(X),
            "v": np.zeros_like(Y),
            "w": np.zeros_like(Z),
        },
    )
    layer = fig.spec["layers"][0]
    paths, style = mpl_backend.stream3d_paths(layer, fig.store)
    assert paths, "应当积分出至少一条流线"
    assert np.asarray(paths[0]).shape[1] == 3


def test_vispy_is_only_a_reserved_name():
    """文档 §9：VisPy 只留名字，不实现——列出来但不可用、也选不中。"""
    assert "vispy" in pk.backends()
    assert pk.available_backends()["vispy"] is False
    with pytest.raises(dispatch.BackendUnavailable):
        pk.choose_backend(_line_figure().spec, "vispy")


def test_renderer_selector_two_dimensional():
    fig = _line_figure()
    selector = pk.RendererSelector(fig.spec, requested="auto")
    assert selector.backend == "mpl"
    info = selector.explain()
    assert info["requested"] == "auto" and info["chosen"] == "mpl"
    assert info["available"]["mpl"] is True
    result = selector.render(fig.store, width=220, height=150)
    assert isinstance(result, dispatch.RenderResult)
    assert result.backend == "mpl"
    assert result.payload[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.skipif(
    not dispatch.available_backends().get("pyvista"), reason="pyvista 未安装"
)
def test_renderer_selector_three_dimensional_auto():
    fig = _surface_figure()
    selector = pk.RendererSelector(fig.spec, requested="auto")
    assert selector.backend == "pyvista"
    result = selector.render(fig.store, width=260, height=180)
    assert result.backend == "pyvista"
    assert selector.backend == "pyvista"


def test_pyvista_scene_cache_separates_stores():
    """不同 DataStore 的版本号都从 0 开始；场景缓存不能把内容不同的图判成同一场景。"""

    def render(scale: float) -> bytes:
        n = 24
        x = np.linspace(0, 1, n)
        y = np.linspace(0, 1, n)
        X, Y = np.meshgrid(x, y)
        fig = pk.figure()
        fig.add("surface", {"x": X, "y": Y, "z": scale * np.sin(3 * X) * np.cos(3 * Y)})
        return fig.render(width=180, height=140, backend="pyvista")

    assert render(1.0) != render(2.0)
