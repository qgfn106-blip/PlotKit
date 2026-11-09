"""宿主集成公开接口（v1）。

netlab 等宿主只允许经本模块使用 PlotKit 的服务端能力，不得 import
``plotkit.store.*`` / ``plotkit.server.*`` 的内部符号（C-4 / R2④）。

稳定承诺：
- ``API_VERSION`` 为接口代次；``create_server`` / ``PlotRenderPort`` / ``probe`` /
  ``store_lock`` / ``index_html`` 的签名变更必须 bump 本包次版本号；
- 本模块内部可以引用私有实现，但宿主不应看到这些细节。
"""

from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path
from typing import Any

API_VERSION = "1"

_MIN_VERSION = (0, 2)
_MAX_VERSION = (0, 3)

# P0 契约冻结：schema/ 是兼容矩阵与能力矩阵的唯一主人（X5），宿主只读。
# 用 pathlib 直接读 JSON，避免 import 任何绘制后端，probe() 在缺依赖时依然能返回。
_SCHEMA_DIR = Path(__file__).resolve().parent / "schema"


def _version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in str(version).split(".")[:3]:
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits or 0))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def _load_declaration(filename: str) -> dict[str, Any]:
    try:
        raw = json.loads((_SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _module_available(name: str) -> bool:
    try:
        return find_spec(name) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def _distribution_installed(name: str) -> bool:
    """发行包是否有显式安装声明（importlib.metadata），不 import 模块本身。"""
    try:
        from importlib.metadata import PackageNotFoundError, version

        version(name)
    except PackageNotFoundError:
        return False
    except (ImportError, OSError, ValueError, TypeError):
        return False
    return True


def _optional_features() -> dict[str, bool]:
    """按 compat_matrix.json 的 extra_requirements 声明统一探测各 extra。

    裁定 ⑨-3：available 由「显式安装声明 + 依赖闭包」共同决定，不能只靠
    find_spec。三个 extra 走同一套口径：发行包用 importlib.metadata 判定，
    依赖闭包模块用 find_spec 判定，全部满足才算可用；factory 是声明里的契约，
    probe() 不实例化 Plotter（离屏/GUI 代价大且缺显示环境会失败）。
    """
    compat = _load_declaration("compat_matrix.json")
    declared = compat.get("extra_requirements") or {}
    result: dict[str, bool] = {}
    for name, req in declared.items():
        if not isinstance(req, dict):
            continue
        dists = req.get("distributions") or []
        modules = req.get("modules") or []
        declared_any = bool(dists) or bool(modules)
        # 用列表推导而非 all() 生成器：每个声明项都实际探测，便于机检
        # 「三个 extra 走同一套口径」，不因短路漏测依赖闭包。
        installed_states = [_distribution_installed(str(item)) for item in dists]
        closure_states = [_module_available(str(item)) for item in modules]
        result[name] = declared_any and all(installed_states) and all(closure_states)
    return result


def _additive_probe_fields(version: str) -> dict[str, Any]:
    """probe() 的纯追加字段；原有四键与三态一个都不改。

    裁定 ⑨-1：四个命名空间互不混淆——
    features：静态 P0 功能名（compat_matrix.json）；
    capabilities：静态后端能力名（capability_matrix 8 行 capabilities_used
      并集，绝不并入 extra 包名）；
    optional：动态 extra 安装状态（绝不并入 capabilities）；
    decisions：运行时按 optional 计算，只在 /api/capabilities 暴露。

    plan §4.7 的 ``api_version: 2`` / ``state: unavailable`` 属于破坏性契约
    变更，本轮不实施（列为需审批项），故这里只追加声明性键。
    """
    compat = _load_declaration("compat_matrix.json")
    matrix = _load_declaration("capability_matrix.json")
    rows = matrix.get("rows")
    row_list = rows if isinstance(rows, list) else []
    schema_versions = compat.get("schema_versions") or {
        "figure": ["plotkit.figure/v1"],
        "frame": ["plotkit.frame/v1"],
    }
    frame_versions = compat.get("frame_schema_versions") or ["plotkit.frame/v1"]
    features = list(compat.get("features") or [])
    used: set[str] = set()
    for row in row_list:
        if isinstance(row, dict):
            names = row.get("capabilities_used") or []
            used.update(str(item) for item in names)
    capabilities = sorted(used)
    return {
        "package_version": version,
        "schema_versions": schema_versions,
        "frame_schema_versions": frame_versions,
        "features": features,
        "capabilities": capabilities,
        "optional": _optional_features(),
        "compat": compat.get("compat")
        or {"min": "0.2", "max_exclusive": "0.3", "hosts": {}},
        "capability_matrix": {
            "schema": matrix.get("schema", "plotkit.capability_matrix/v1"),
            "revision": matrix.get("revision", 0),
            "rows": len(row_list),
        },
    }


def probe() -> dict[str, Any]:
    """返回 PlotKit 侧可用性判定（available / missing / incompatible）。

    missing 表示运行环境缺少 PlotKit 的必需后端（当前为 matplotlib）；宿主应把
    它映射为「未安装/不可用」而不是 500。三态是 C-4 契约的一部分。
    """
    from . import __version__

    version = str(__version__)
    declarations = _additive_probe_fields(version)
    try:
        import matplotlib  # noqa: F401
    except Exception as exc:  # pragma: no cover - 依赖缺失时走这里
        return {
            "state": "missing",
            "version": version,
            "api_version": API_VERSION,
            "detail": f"缺少 matplotlib 后端：{exc}",
            **declarations,
        }
    if _MIN_VERSION <= _version_tuple(version)[:2] < _MAX_VERSION:
        return {
            "state": "available",
            "version": version,
            "api_version": API_VERSION,
            "detail": "",
            **declarations,
        }
    return {
        "state": "incompatible",
        "version": version,
        "api_version": API_VERSION,
        "detail": f"PlotKit {version} 不在 >=0.2,<0.3 兼容范围内",
        **declarations,
    }


def create_server(
    figure: Any,
    *,
    title: str | None = None,
    layout_path: str | Path | None = None,
    ui_state_path: str | Path | None = None,
    with_ns: bool = False,
) -> Any:
    """创建可挂载的 ASGI 服务（宿主只依赖返回值可被 ``app.mount`` 使用）。

    ``ui_state_path`` 是 P0 新增的显式 UI 状态注入点；不传时走用户配置目录，
    不再落到 ``Path.cwd() / "layout.json"``（X3）。
    """
    from .server.app import create_app

    return create_app(
        figure,
        title=title,
        layout_path=layout_path,
        ui_state_path=ui_state_path,
        with_ns=with_ns,
    )


class PlotRenderPort:
    """最小渲染端口：宿主只依赖 ``.app`` 与 ``.probe()``。"""

    def __init__(
        self,
        figure: Any,
        *,
        title: str | None = None,
        layout_path: str | Path | None = None,
        ui_state_path: str | Path | None = None,
        with_ns: bool = False,
    ) -> None:
        self.app = create_server(
            figure,
            title=title,
            layout_path=layout_path,
            ui_state_path=ui_state_path,
            with_ns=with_ns,
        )

    @staticmethod
    def probe() -> dict[str, Any]:
        return probe()


def store_lock() -> Any:
    """数据锁：宿主同步线程与出图线程互斥用的公开锁对象。"""
    from .store.registry import DATA_LOCK

    return DATA_LOCK


def index_html() -> str:
    """读取 PlotKit 自带首页 HTML 原文（宿主需要在其上做同源包装时使用）。"""
    from .server.assets import STATIC_DIR

    return (Path(STATIC_DIR) / "index.html").read_text(encoding="utf-8")
