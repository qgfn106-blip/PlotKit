---
title: P1-0 只读测量轮报告
status: measured
date: 2026-11-09
evidence_head: 1cf2570844c533cb2eb3ef44f352caa7d82fe764
scope: 只测量、只设计、不实施、不搬文件
---

# P1-0 只读测量轮报告（裁定书 §二④ / §四步骤 5）

> 本轮性质：**只测量、只设计、不实施、不搬文件**，属于 G0 签字范围之外的准备工作。
> 本文所有测量数字均来自 `PlotKit/reports/p1_baseline.json` 中实跑命令的逐字输出；
> 未实跑的数字只作为裁定书原文引用，不当作本轮测量结论。完整原始输出、
> `sha256`、AST dump 哈希与合成探针结果均留在 JSON 内，作为 X2 要求的输出留痕。

## 1. 证据基线（date + HEAD + 命令全文）

| 项 | 实跑结果 |
| --- | --- |
| 测量时间 | `2026-11-09T12:35:33.027529+08:00` |
| HEAD | `1cf2570844c533cb2eb3ef44f352caa7d82fe764` |
| Python | `Python 3.13.9` |
| 平台 | `Windows-11-10.0.26300-SP0` |
| 工作目录 | `E:/Python/MyPython/ProjectPoint/PlotKit` |
| 解释器 | `E:/anaconda3/python.exe` |
| `plotkit.__file__` | `E:/Python/MyPython/ProjectPoint/PlotKit/src/plotkit/__init__.py` |
| 绝对 `PYTHONPATH` | `E:/Python/MyPython/ProjectPoint/PlotKit/src` |
| `C:/Windows/Temp` 可写 | `true` |

证据基线命令全文：

```bash
git rev-parse HEAD
python -V
python -c "import datetime; print(datetime.datetime.now().astimezone().isoformat())"
python -c "import os; print(os.access('C:/Windows/Temp', os.W_OK))"
PYTHONPATH=src python -c "import plotkit; print(plotkit.__file__)"
```

为避免写用户目录，子进程统一设置环境护栏：

```text
PYTHONDONTWRITEBYTECODE=1
MPLCONFIGDIR=C:/Windows/Temp
XDG_CACHE_HOME=C:/Windows/Temp
TMP=C:/Windows/Temp
TEMP=C:/Windows/Temp
PYVISTA_USERDATA_PATH=C:/Windows/Temp
```

JSON 的 `measurement_commands` 逐字记录了全部测量命令文本；其中脚本体命令按
裁定书写成 `PYTHONPATH=src python -X importtime ...`，实际执行以 `sys.executable`
作为 `python`，并把 `PYTHONPATH` 设为上面的绝对 `src` 路径，避免 shell 差异。

```text
PYTHONPATH=src python -X importtime -c "import plotkit" 2>&1
python -c "import sys; before=set(sys.modules); import plotkit; print(sorted(set(sys.modules)-before))"
python - <<'PY'  # sha256(raw bytes) + sha256(ast.dump(ast.parse(...), include_attributes=False))
python -c "import importlib.util, json; ..."
python -c "import importlib.metadata as md, json; ..."
python -c "ast 静态扫描 src/plotkit 目标文件 import"
python -c "monkeypatch plotkit.host_api._module_available"
python -c "读取 static/*.ts 与 static/*.js 行数"
python -c "遍历 PlotKit 下所有 .ts/.js（排除 build/node_modules/.git）并计行"
```

> 上面含 `...` 的字符串是 `p1_baseline.json` 内逐字记录的命令摘要键；完整执行
> 脚本体、逐字输出、哈希和结果字段都在 JSON 各小节 `raw_stdout` / 结果字段中。

## 2. 五类测量的方法与结论

### 2.1 模块清单、累计耗时与 `sys.modules` 差集

方法：分别实跑两条命令，并解析 `importtime` 的 `self [us] | cumulative | imported package`
行与 `sys.modules` 新增集合。

`PYTHONPATH=src python -X importtime -c "import plotkit" 2>&1` 逐字输出摘要：

- `returncode=0`，`line_count=244`，`parsed_module_count=243`；
- `total_self_us=193112`，`max_cumulative_us=153260`；
- 根模块 `plotkit`：`root_cumulative_us=153260`、`root_self_us=944`；
- `plotkit_module_count=26`；
- 首行逐字：`import time: self [us] | cumulative | imported package`；
- 末行逐字：`import time:       944 |     153260 | plotkit`；
- `stdout_sha256=ec00189fde7564e6e4756b653e44debc973c15ce29cc9a49966aa4d4f9487700`；
- 累计耗时最高项含 `plotkit` 153260、`plotkit.field3d` 98417、`numpy` 97661，
  完整 top-10 见 JSON 的 `importtime.top_10_by_cumulative_us`。

`python -c "import sys; before=set(sys.modules); import plotkit; print(sorted(set(sys.modules)-before))"`
逐字输出摘要：

- `returncode=0`，`diff_count=175`，`plotkit_module_count=24`；
- `stdout_sha256=486f2fea1b5383ffc01f7c129cec149ad601e8ded686afc9f7b9947b6034f86c`；
- `raw_stdout` 开头逐字：
  `['_ast', '_bisect', '_blake2', '_bz2', '_compat_pickle', '_compression', '_contextvars', '_csv', '_ctypes', '_cython_3_1...`；
- 两次测量都命中裁定书要求的 5 个模块：
  `plotkit.ns`、`plotkit.ns.field`、`plotkit.ns.diagnostics`、`plotkit.ns.scene`、
  `plotkit.field3d`。

结论：根因与裁定书一致，为
`PlotKit/src/plotkit/__init__.py:25` 的 `from . import field3d, ns`。
当前 `import plotkit` 仍未满足 G1 判据「不加载 ns/three」。

### 2.2 依赖闭包与两种环境下的 `probe().optional`

方法：`importlib.util.find_spec` 实测 7 个模块；`importlib.metadata.requires`
读取发行包依赖；AST 静态扫描 23 个目标 `.py` 文件的 import 根；再在子进程中
monkeypatch `plotkit.host_api._module_available`，模拟「全部 extra 已装」与
「只装 dev,web」两种环境。**该探针明确标注 synthetic，未真实 pip install，
不假装本机装了全部 extra。**

`find_spec` 实测结果：

- `pyvista`：found=true，`E:/anaconda3/Lib/site-packages/pyvista/__init__.py`；
- `vtk`：found=true，`E:/anaconda3/Lib/site-packages/vtk.py`；
- `scipy`：found=true，`E:/anaconda3/Lib/site-packages/scipy/__init__.py`；
- `pywebview`：found=false；
- `plotkit.contrib.ns`：found=false，错误逐字为
  `ModuleNotFoundError: No module named 'plotkit.contrib'`；
- `plotkit.ns`：found=true，
  `E:/Python/MyPython/ProjectPoint/PlotKit/src/plotkit/ns/__init__.py`；
- `plotkit.field3d`：found=true，
  `E:/Python/MyPython/ProjectPoint/PlotKit/src/plotkit/field3d.py`。

`metadata_requires` 关键闭包：

- `pyvista` → `matplotlib>=3.0.0`、`numpy>=1.21`、`pillow`、`pooch`、
  `scooby>=0.5.1`、`typing-extensions`、
  `vtk>=9.3.1,<9.8.0,!=9.4.0,!=9.4.1`；
- `vtk` → `matplotlib>=2.0.0`、`wslink>=2.0`；
- `scipy` → `numpy<2.6,>=1.25.2`；
- `pywebview` → Windows 下 `pythonnet`，另有 Qt/CEF/macOS 条件依赖、
  `proxy_tools`、`bottle`、`typing-extensions`；
- `plotkit` → `numpy>=1.23`、`matplotlib>=3.6`、`pillow>=9.0` 及 extra 标记依赖。

AST 静态扫描发现的第三方/外部 import 根包含：
`PIL`、`matplotlib`、`numpy`、`psutil`、`pyvista`、`scipy`、`vtk`、`webview`、
`fastapi`、`httpx`、`uvicorn`、`h5py`，以及多个标准库根。

合成 `probe().optional` 两种环境（synthetic）：

- `all_extras_available_(synthetic)`：`flags` 全 true；
  `probe().optional={"three":true,"ns":true}`；
  `capabilities` 为 10 项（8 项 `compat_matrix.json` 基础能力 + `three` + `ns`）；
  `state=available`、`api_version="1"`、`package_version="0.2.1"`。
- `dev_web_only_(synthetic)`：`flags` 全 false；
  `probe().optional={"three":false,"ns":false}`；
  `capabilities` 为 8 项（仅基础能力）；
  `state=available`、`api_version="1"`、`package_version="0.2.1"`。

注意：只有 `pyvista` 与 `plotkit.contrib.ns` 会影响现有
`host_api._optional_features()` 的 `probe().optional`；
`vtk` / `scipy` / `pywebview` 的 flags 用于描述场景，不是 `optional` 的探测口径。
当前 `host_api.py` 的 `three` 用 `find_spec("pyvista")`、`ns` 用
`find_spec("plotkit.contrib.ns")`，两套口径不一致；这属于裁定书 §三/§四⑨
指出的契约问题，本轮只记录，不修。

### 2.3 逐文件 SHA256 + AST dump 基线（X2 输出留痕）

方法：以 `src/plotkit` 为根，对 23 个目标文件逐个计算
`sha256(raw file bytes)`；对 `.py` 再计算
`sha256(ast.dump(ast.parse(source, type_comments=False), include_attributes=False).encode("utf-8"))`；
`.ts` / `.js` / `.html` 只计算字节哈希，`ast_sha256=null`。

结论：

- `file_baselines_count=23`，`file_baselines_meta.count=23`；
- `python_file_count=16`、`asset_file_count=7`；
- 每条含 `bytes_sha256`、`size_bytes`、`has_bom`、`kind`、`ast_sha256`；
- `file_baselines_meta.x2_equivalent_evidence=true`，因为哈希输出已嵌入 JSON，
  满足「X2 要求的是输出留痕，不是脚本存在」；
- 23 个键相对 `src/plotkit`：`backends/pyvista_backend.py`、
  `backends/pyvista_pool.py`、`backends/hybrid3d.py`、`field3d.py`、
  `anim3d.py`、`ns/__init__.py`、`ns/app.py`、`ns/diagnostics.py`、
  `ns/field.py`、`ns/iso.py`、`ns/scene.py`、`ns/solver.py`、
  `server/ns_app.py`、`static/view3d.ts`、`static/view3d.js`、
  `static/nsview.ts`、`static/nsview.js`、`static/ns.html`、
  `static/plot3d.utils.ts`、`static/plot3d.utils.js`、`cli.py`、
  `desktop/app.py`、`desktop/server.py`；
- 裁定书列出的 `pyvista_backend.py` / `pyvista_pool.py` / `hybrid3d.py`
  实际位于 `src/plotkit/backends/` 下，故键带 `backends/` 前缀；
- `tools/generate_reports.py` 只重生成 `architecture.json`、`decisions.json`、
  `schema.json`，不会覆盖 `p1_baseline.json`。

JSON 以 `json.dumps(sort_keys=True, ensure_ascii=False, indent=2)` 加尾随换行写出，
二次 `json.loads` 后重新 dump 与原文件逐字一致。

### 2.4 expand–contract 批次划分（本轮不执行任何一批）

方法：把实际搬运拆成 3 个独立 commit 批次，均记录
`involved_files` / `preconditions` / `verification_commands` /
`commit_convention` / `executed_this_round=false`。

| 批次 | 名称 | 涉及文件 | 前置 | 验证命令 | 独立 commit 约定 |
| --- | --- | --- | --- | --- | --- |
| P1-1 | 先建 `contrib/` 双导入保持旧路径 | `src/plotkit/contrib/__init__.py`、`src/plotkit/contrib/ns/__init__.py`、`src/plotkit/contrib/ns/*.py`、`src/plotkit/contrib/field3d.py` | P1-0 交付并复核通过；用户/lead 审批实际搬运并钉定 HEAD 与签字表 G1 行；与并行会话确认无同文件写冲突 | `PYTHONPATH=src python -c "import plotkit.contrib.ns as n; import plotkit.ns as old; print(n.__name__, old.__name__)"`；`python -m pytest -o addopts= -q tests/contract --disable-warnings`；`python tools/check_layers.py` | `P1-1: add contrib/ns dual-import shims` |
| P1-2 | 切 `__init__.py` 顶层导入 | `src/plotkit/__init__.py`（去掉 `from . import field3d, ns`）、`src/plotkit/host_api.py`（optional ns 探测改为 contrib 路径）、`pyproject.toml`（新增 ns extra） | P1-1 独立 commit 通过且旧路径仍可导入；`api/native.py` 不改（裁定书 §二④ 明确 P1/P2 均不得改） | 两条 import 测量命令、`python -c "from plotkit.host_api import probe; print(probe()['optional'])"`、contract 测试 | `P1-2: stop eager ns/three imports` |
| P1-3 | 删旧顶层导入/删旧路径 | `src/plotkit/ns/`、`src/plotkit/field3d.py`、`src/plotkit/server/ns_app.py` 等引用按 P1-2 结果收敛 | P1-2 独立 commit 通过；双导入观察一个发布周期且 parity/回归无旧路径依赖；单独审批删除，不与 P1-2 混在同一 commit | `PYTHONPATH=src python -c "import plotkit; print('ok')"`；contract 测试；parity 测试 | `P1-3: remove legacy ns/field3d paths` |

独立 commit 约定：P1-1 / P1-2 / P1-3 各自独立 commit，每批只含该批文件；
P1-3 删除旧路径须单独审批。**本轮不执行任何一批。**
顺序上 `P1 ∥ P2` 可并行，但两者都不得改 `api/native.py`。

### 2.5 `ns` extra 命名与 `three` 的依赖关系

方法：实读 `PlotKit/pyproject.toml` 的 `[project.optional-dependencies]`，
并与 `metadata_requires` / `source_imports` 结果对齐。

结论：

- 当前已有 `three = ["pyvista>=0.44"]`、`desktop = ["pywebview>=5.0"]`；
- **没有 `ns` extra**（`ns=null`）；
- `vtk` 由 `pyvista` 带入，不单独 pin；
- `pywebview` 属于 `desktop`，不属于 `ns`；
- `scipy>=1.10` 当前未在任何 extra 声明。

`ns_extra_naming.proposal`（状态 `proposed`）：

```json
{
  "depends_on_three": true,
  "ns": ["plotkit[three]", "scipy>=1.10"]
}
```

即 `ns` 依赖 `three` 产品线，并需要显式 `scipy>=1.10`；本轮只提出命名与
依赖关系，不改 `pyproject.toml`。

## 3. G1 当前为何不具开工条件

G1 判据：`import plotkit 不加载 ns/three`。当前 `g1_readiness.status="not_ready"`，
原因来自裁定书与实跑输出：

1. **X2 等价留痕此前没有**：逐文件 SHA256 + AST dump 基线在本轮才产出；
   此前只有「须先做」，没有输出留痕。
2. **签字表 G1 行整行为空**：裁定书 §二④ 明确指出这一点。
3. **本轮 importtime / sys.modules 差集仍命中 ns/three 模块**：
   `plotkit.ns`、`plotkit.ns.field`、`plotkit.ns.diagnostics`、
   `plotkit.ns.scene`、`plotkit.field3d` 全部出现。
4. **本轮只测量、不搬文件、不执行任何 `expand_contract_batches`**。

因此 G1 当前不具备开工条件。下一闸门逐字为：
`P1-0 交付并复核后，才审批实际搬运（裁定书 §二④ / §四步骤 5）`。

## 4. P1-0 交付复核后才审批实际搬运

本轮交付物为 `PlotKit/reports/p1_baseline.json` 与三份 `docs/decisions/*.md`。
**P1-0 交付复核后，才审批实际搬运**；复核前不建 `contrib/`、不改
`src/plotkit/__init__.py`、不改 `pyproject.toml`、不删旧路径、不执行任何批次。

## 5. 附：前端行数与裁定书「双份 13990 行」差异

本轮实读：`src/plotkit/static` 下 6 对 TS/JS 共 `12624` 行
（`ts_total_lines=6569`、`js_total_lines=6055`；`app_ts_lines=3042`、
`app_js_lines=2713`）；全仓 18 个 `.ts` / `.js` 共 `13217` 行。
裁定书 §二⑤ 以「双份 13990 行」描述现状；该数字差异不在此稿裁定，
`p1_baseline.json` 同时记录 static 与全仓计数，不把任何未实跑数字当测量结果。

## 6. 约束复核

- 未改任何现有文件；未创建 `capability_matrix.json`；未运行全量 pytest；
- 未执行 `git add/commit/tag/push/reset/checkout/rebase`；
- 未运行会写用户目录的命令，子进程统一指向 `C:/Windows/Temp`；
- synthetic probe 明确标注，不假装真实安装了全部 extra；
- 前端 TS/JS 产物仍入库并保留 drift guard；`test:ui` 仅为设计稿；
- `p1_baseline.json` 的 17 个顶层键为：`deliverables`、`dependency_closure`、
  `evidence`、`expand_contract_batches`、`file_baselines`、
  `file_baselines_count`、`file_baselines_meta`、`frontend_line_counts`、
  `g1_readiness`、`importtime`、`json_dump_options`、`measurement_commands`、
  `notes`、`ns_extra_naming`、`report_schema`、`sys_modules_diff`、
  `top_level_keys`。
