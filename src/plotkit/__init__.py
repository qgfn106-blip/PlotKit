"""PlotKit：一套 spec，两种后端（plotly.js 交互 / matplotlib 静态）。

    import plotkit as pk
    fig = pk.figure(title="RC 充电")
    fig.add_data("t", t, unit="s", role="coord")
    fig.add_data("v_out", v_out, unit="V", role="series", tags=["输出"])
    fig.add_plot("line", x="t", y="v_out", label="V_out")
    fig.show()                 # inline / 原生窗口 / 浏览器 自动选
    fig.savefig("out.png")     # matplotlib 静态
    fig.save_spec("spec.json") # 唯一真相
"""

from __future__ import annotations

from typing import Any

from .api.native import Figure, default_store, figure, set_default_store, subplots
from .store.reclaim import Reclaimer
from .store.registry import DataStore

__version__ = "0.1.0"


class _DataProxy:
    """`pk.data` 始终指向**当前**默认 store（``set_default_store`` 之后也不会变成旧对象）。"""

    def __getattr__(self, name: str) -> Any:
        return getattr(default_store(), name)

    def __repr__(self) -> str:  # pragma: no cover
        return repr(default_store())


data = _DataProxy()

__all__ = [
    "Figure",
    "figure",
    "subplots",
    "data",
    "default_store",
    "set_default_store",
    "DataStore",
    "Reclaimer",
    "__version__",
]
