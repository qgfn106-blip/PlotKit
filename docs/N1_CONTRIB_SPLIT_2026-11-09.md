# N1 · contrib 拆分（G1）阶段报告（2026-11-09）

> 阶段：N1（G1 分层闸门）。前阶段 N0（远端分支+main 双绿）已达成。
> 本阶段目标：把 `field3d` 与 `ns` 从主包拆到 `plotkit.contrib`，使 `import plotkit`
> 不再加载它们、不再拉 pyvista，而 `plotkit.contrib.ns` 仍可惰性访问。

## 1. 结论

- **本地已绿**：全量 `546 passed, 19 warnings`（测试从 544 增到 546，新增 2 条 import 隔离用例）。
- **G1 隔离已验证**：子进程 `import plotkit` 后 `sys.modules` 不含 `plotkit.contrib*` / `plotkit.ns*` / `plotkit.field3d`，也不含 `pyvista`；访问 `plotkit.field3d` / `plotkit.ns` 后才按需加载 `plotkit.contrib.*`。
- **远端分支首绿待授权推送**（按 X1，push 需用户对指定 HEAD 书面授权；本报告先落本地）。

## 2. 变更清单

- 迁移（`git mv`）：`src/plotkit/field3d.py` → `src/plotkit/contrib/field3d.py`；`src/plotkit/ns/` → `src/plotkit/contrib/ns/`。
- 新增 `src/plotkit/contrib/__init__.py`（可选扩展包说明，import 时不加载）。
- `src/plotkit/__init__.py`：移除顶层 `from . import field3d, ns`；新增模块级 `__getattr__`，用 `importlib.import_module` 惰性暴露 `field3d` / `ns`（不走 Import 语句，符合 `tools/check_layers.py` 的「`__init__.py` 不得导入 contrib」AST 规则）。
- `src/plotkit/server/ns_app.py`：`from ..ns` → `from ..contrib.ns`（8 处）+ docstring。
- `src/plotkit/cli.py`：`from plotkit.ns import app as ns_app` → `from plotkit.contrib.ns import app as ns_app`。
- `src/plotkit/contrib/ns/app.py`：`from ..server` → `from ...server`（2 处）+ docstring。
- 测试引用：`tests/test_ns_api.py` / `test_ns_field.py` / `test_ns_physical.py` / `test_ns_scene.py` 的 `plotkit.ns` → `plotkit.contrib.ns`。
- `tools/verify_ns.py`：`plotkit.ns.app` → `plotkit.contrib.ns.app`。
- 新增 `tests/contract/test_import_isolation.py`（2 用例，子进程验证 G1）。
- 机器报告重生成：`reports/architecture.json`（模块树变化）、`reports/test_baseline.json`（两 profile）。

## 3. 证据（本地，`cd PlotKit && export PYTHONPATH=src`）

| 命令 | 输出 |
|---|---|
| `python -m pytest -o addopts= --collect-only -q` | `546 tests collected` |
| `python -m pytest -o addopts= -q --disable-warnings -ra` | `546 passed, 19 warnings` exit 0 |
| `python tools/check_test_baseline.py` | `profile=dev_full collected=546 pinned=546 passed=546 failed=0 skipped=0 ok=True` |
| `python tools/check_layers.py` | `scanned=57 violations=0 ok=True` |
| `python tools/check_capability_matrix.py` | `rows=8 violations=0 ok=True` |
| `python tools/check_doc_sync.py` | `capability_rows=8 violations=0 ok=True` |
| `python tools/bench_regress.py --check` | `check=ok` |
| `python tools/record_update.py --check` | `entries=10 ok=True` |
| `python -m flake8 <改动文件>` | 零命中 |
| `python -m black --check <改动文件>` | 18 files unchanged |

基线两 profile（`reports/test_baseline.json`，schema `plotkit.test_baseline/v2`，`collected=546`）：
- `dev_full`：Windows / 3.13，extras 全可用（pywebview False），ffmpeg True，`skipped_total=0`。
- `ci_no_extras`：Linux / 3.11，extras 全 False，ffmpeg False，`skipped_total=29`（由 faithful shim 生成）。

## 4. 风险与边界

- 仅搬移 + 惰性暴露 + 引用改写，未改渲染逻辑；`plotkit.contrib.ns` 的 `..` 相对导入随同迁移仍正确。
- `plotkit.__all__` 若列 `field3d`/`ns`，`from plotkit import *` 会触发惰性加载；`import plotkit` 不受影响。
- 未改 `src/plotkit/api/native.py`、未改 optional 并回 capabilities（守 X5）。
- push（分支 → 远端 CI 首绿 → 合 main）需按 X1 取用户对具体 HEAD 的书面授权，授权不跨 HEAD 复用。

## 5. 后续

1. 授权后推送分支 `p1-contrib-split`，取远端 python-tests 首绿。
2. 绿后合并 main 并取 main 首绿（再次授权）。
3. 回填本报告与签字表、更新 PROGRESS；进入 N2。
