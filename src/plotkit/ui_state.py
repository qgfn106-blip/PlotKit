"""UI 状态落点（计划 §10 X3）：显式注入优先，默认走用户配置目录。

旧实现把面板布局写到 ``Path.cwd() / "layout.json"``：换目录起服务状态全丢，
宿主 ``app.mount("/plotkit", ...)`` 时还会把 layout.json 写进宿主仓库。
本模块把默认落点改成 ``~/.config/plotkit/ui.json``，并提供一次性只读迁移
（cwd 的旧文件只被读、永不作为写入落点），因此旧调用方不会丢状态。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

APP_DIR_NAME = "plotkit"
UI_STATE_FILENAME = "ui.json"
LEGACY_FILENAME = "layout.json"


def default_ui_state_path() -> Path:
    """用户配置目录；POSIX 尊重 XDG_CONFIG_HOME，Windows 用 ~/.config。"""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".config"
    return root / APP_DIR_NAME / UI_STATE_FILENAME


def legacy_cwd_layout_path() -> Path:
    """仅供一次性只读迁移；绝不作为写入落点。"""
    return Path.cwd() / LEGACY_FILENAME


def resolve_ui_state_path(explicit: str | os.PathLike[str] | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser()
    return default_ui_state_path()


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def migrate_legacy_layout(target: Path) -> bool:
    """把 cwd 的旧 layout.json 一次性导入到用户配置目录。

    Returns:
        是否真的执行了导入。目标已存在时直接返回 False（不覆盖用户数据）。
    """
    if target.exists():
        return False
    legacy = legacy_cwd_layout_path()
    if not legacy.is_file():
        return False
    try:
        payload = json.loads(legacy.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    _atomic_write_json(target, payload)
    return True
