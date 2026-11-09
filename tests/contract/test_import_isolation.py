"""G1 分层闸门：`import plotkit` 不得加载可选扩展 contrib（field3d / ns）。

对齐 tools/check_layers.py 的「plotkit/__init__.py 不得导入 contrib」规则，
用子进程在全新解释器里验证，避免测试上下文已 import 的污染。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _run(code: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env
    )


def test_import_plotkit_does_not_load_contrib():
    code = (
        "import sys, plotkit\n"
        "bad = sorted(m for m in sys.modules if m == 'plotkit.contrib'"
        " or m.startswith('plotkit.contrib.') or m == 'plotkit.ns'"
        " or m.startswith('plotkit.ns.') or m == 'plotkit.field3d')\n"
        "assert not bad, bad\n"
        "assert 'pyvista' not in sys.modules, 'pyvista loaded eagerly'\n"
        "print('OK')\n"
    )
    r = _run(code)
    assert r.returncode == 0, r.stderr


def test_lazy_access_and_contrib_layout():
    code = (
        "import sys, plotkit\n"
        "assert 'plotkit.contrib.field3d' not in sys.modules\n"
        "fd = plotkit.field3d\n"
        "assert 'plotkit.contrib.field3d' in sys.modules\n"
        "ns = plotkit.ns\n"
        "assert 'plotkit.contrib.ns' in sys.modules\n"
        "assert hasattr(ns, 'SimilarityField')\n"
        "assert hasattr(fd, 'scene')\n"
        "print('OK')\n"
    )
    r = _run(code)
    assert r.returncode == 0, r.stderr
