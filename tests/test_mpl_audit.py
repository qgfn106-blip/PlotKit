"""PK-R12 对账的机器可校验断言：所有 mpl 绘图方法均已归属、引用 kind 均存在。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_TOOL = Path(__file__).resolve().parents[1] / "tools" / "mpl_method_audit.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("mpl_method_audit", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass 需要能按 __module__ 找回模块
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_every_mpl_method_is_attributed():
    audit = _load_tool()
    problems = audit.audit()
    assert problems == [], "对账问题: " + "; ".join(problems)
    assert len(audit.MPL_METHODS) >= 55


def test_kind_and_reuse_targets_reference_registered_kinds():
    audit = _load_tool()
    kinds = audit._kinds()
    for m in audit.MPL_METHODS:
        if m.form in (audit.FORM_KIND, audit.FORM_REUSE):
            assert m.target in kinds, f"{m.name} -> {m.target} 未注册"


def test_no_duplicate_methods():
    audit = _load_tool()
    names = [m.name for m in audit.MPL_METHODS]
    assert len(names) == len(set(names))
