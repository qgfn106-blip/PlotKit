"""后端层：注册表 + plotly 交互后端 + matplotlib 静态后端。"""

from . import plotly_backend  # noqa: F401 - import 即注册 v0 图层
from .registry import LAYER_SPECS, LayerSpec, describe, kinds, register, resolve

__all__ = ["LAYER_SPECS", "LayerSpec", "register", "resolve", "kinds", "describe"]
