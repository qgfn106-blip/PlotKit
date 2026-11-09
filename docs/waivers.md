# PlotKit 任务豁免记录（docs/waivers.md）

> 本文件记录对既定红线/冻结禁令的**事前**豁免请求与批准状态。依据 X11：红线动作必须**事前**写入本文件并获用户批准，**不得事后补豁免**。未获批前，不得执行被豁免动作。

---

## W-001 · 2026-11-09 · N0 远端首绿：解除「禁止改测试/基线」中的三项

- **状态：已批准（2026-11-09，用户经交互问答确认执行 W-001；认可 3D 用例分配——3 个真实 3D 用例逐用例守卫 skip、`test_volume_surface_rejects_empty_level` 靠生产修复不 skip）。实现与验证结果见第八节。**
- **触发**：上一轮 P0 冻结与红线 X7 含「禁止改测试/基线」「collected==544 不放宽为 >=」。用户裁定 R-b′（2026-11-09，m02485）已批准方向，并要求按本文件事前记录、获批后执行。

### 一、根因与取证（可复现）

- CI（`python-tests.yml`）只装 `pip install -e ".[dev,web]"`，**无 pyvista/vtk/psutil/pywebview/h5py**；而 `reports/test_baseline.json` 钉 `collected=544, skipped=[]` 是**全 extras 本机值**，故 `python tools/check_test_baseline.py`（step5）必红。
- 本机用 import-shim 模拟无 extras：`collected=509 / 4 failed / 7 skipped`；`delta 35 = test_anim3d.py 8 + test_multibackend.py 24 + test_pyvista_pool.py 3`，全部来自这三个文件的**模块级** `pytest.importorskip("pyvista")`，在 collection 阶段整段消失（故不进 collected）。
- 4 个红用例：`tests/test_ns_physical.py::test_iso_returns_triangles`、`::test_streamlines_returns_polylines`、`tests/test_web3d_layers.py::test_volume_surface_returns_mesh`、`::test_volume_surface_rejects_empty_level`。前三个是真实 3D 用例（需要 pyvista 出几何）；第四个是纯参数校验（`level=5.0` 应 400），但因 `server/app.py:472`（`mode=="surface"` 分支内 `import pyvista as pv` 位于校验之前）与 `ns/iso.py:41/:120`（`_image_data` / `streamlines` 内）**在参数校验前 import pyvista**，缺 extras 时先 `ImportError/500`，是**真实 API 契约缺陷**。
- 门禁自身缺陷：`tools/check_test_baseline.py:136` 用 `collected == passed + skipped` 守恒却**不计 failed** → 缺失 extras 时 `509 != 501+7` 必报伪 violation；`_SKIPPED_RE` 抓 `path:line` **去重集合**，而 `skipped` 是**用例数量**，参数化同处多行会口径打架。

### 二、批准范围（仅此三项被解除；其余红线不动）

1. **测试守卫（模块级 → 逐用例）**
   - 将 `tests/test_anim3d.py`、`tests/test_multibackend.py`、`tests/test_pyvista_pool.py` 的**模块级** `pytest.importorskip("pyvista")` 改为**逐用例守卫**，使用例仍被收集、仅在运行时跳过（collected 回升到 544）。
   - `tests/test_anim3d.py:8` 的 `pk = pytest.importorskip("plotkit")` 改为正常 `import plotkit`（主包导入失败必须报错，不得静默跳过 8 例）。
   - 对三个真实 3D 用例（`test_iso_returns_triangles`、`test_streamlines_returns_polylines`、`test_volume_surface_returns_mesh`）加逐用例 pyvista 守卫：无 extras 时 skip（仍收集），有 extras 时正常跑并断言。
   - `test_volume_surface_rejects_empty_level` **不加守卫**——它是纯参数校验，靠第三节的生产代码修复使其在无 extras 下也返回 400。
2. **基线 skipped 字段（schema v2）**
   - `reports/test_baseline.json` 升 `schema: plotkit.test_baseline/v2`，新增 `environment_fingerprint` 与**按指纹的两套 profile**：`ci_no_extras` 与 `dev_full`，各自记录 `collected`（恒 544）与 `skipped`（该环境应有的 skip 用例清单 + 计数）。
3. **门禁判据公式**
   - `check_test_baseline.py` 守恒式改为 `collected == passed + failed + skipped`。
   - 统一 `skipped` 口径：以 `_SKIPPED_RE` 解析出的 `path:line` **去重集合**为准，并同时比对**总 skip 数**（`sum(每条 [n])`），二者都要与所选 profile 的基线一致；消除「集合 vs 用例数」不一致导致的伪 violation。

### 三、环境指纹定义（schema v2）

```
environment_fingerprint = {
  "python": "<major.minor>",                 # e.g. "3.11"
  "os": "<platform.system()>",               # e.g. "Linux", "Windows"
  "extras": {                                 # find_spec 是否为 None 的向量
    "pyvista": bool, "vtk": bool,
    "psutil": bool, "pywebview": bool, "h5py": bool
  }
}
```

- 门禁运行时计算当前指纹 → 选匹配的 profile；**不匹配任何 profile → 显式报错并返回 1（红）**，禁止静默回退到某个默认 profile。
- profile 的 `skipped` 清单必须由机器生成（新增/扩展 `tools/` 下的基线写入器），不得手写猜测。

### 四、生产代码修复（属修真实缺陷，不属「放宽」）

- 仅调整**可选依赖导入顺序**：`src/plotkit/server/app.py` 的 `/api/volume`（`mode=="surface"`）与 `src/plotkit/ns/iso.py` 的 `isosurface` / `streamlines`——把 `import pyvista as pv` 移到参数/取值范围校验**之后**；`level` 超出 `[vmin, vmax]` 时在 import 之前返回 `HTTPException(400, ...)`。
- **不做纯 numpy 几何 fallback**（几何仍由 pyvista/VTK 产出；无 extras 时真正需要几何的路径返回明确错误或由测试守卫跳过）。

### 五、不变约束（与 R-a 的分界线，必须逐字遵守）

- `collected` 保持 **544**，放宽为 `>=` 一律禁止；不删任何断言；不用 `pytest -k`；`workflow` 的 `.[dev,web]` 一行不动（不把 extras 装进 CI）。
- 不改 probe 三态/API_VERSION；不删 `PUT /api/spec`；不改 `src/plotkit/api/native.py`；`optional` 不并回 `capabilities`。
- 不 rebase / force-push / amend / reset；push 需按 X1 另行取得书面授权（授权不跨 HEAD）。

### 六、放行前四张反向验证（必须逐条「先红→再复原」）

- **V1**：删除任一**非 3D** 用例 → gate 变红。
- **V2**：给任一**核心（非 3D）**用例加 skip → gate 变红。
- **V3**：伪造 fingerprint 使之不匹配任何 profile → gate 变红。
- **V4**：无 extras 环境下 `GET /api/volume?mode=surface&level=5.0` 仍返回 **400**（不是 500）。

### 七、批准签署

- 用户批准：**2026-11-09 经交互问答确认执行 W-001**（三项解除 + 生产导入顺序修复 + 四张反向验证），并认可 3D 用例分配：3 个真实 3D 用例（`test_iso_returns_triangles` / `test_streamlines_returns_polylines` / `test_volume_surface_returns_mesh`）逐用例守卫 skip 且仍被收集；`test_volume_surface_rejects_empty_level` 不加守卫、靠生产修复在无 extras 下也返回 400。
- 随后本地 commit；push 另取 X1 授权。

### 八、实现与验证结果（2026-11-09，机器化）

- **生产修复**：`src/plotkit/server/app.py` `/api/volume`（`mode=="surface"`）先算 `lv` 并在 `level` 越界时 `raise HTTPException(400, "该等值面在数据范围内没有交点，换一个 level")`，之后才 `import pyvista as pv`；`src/plotkit/ns/iso.py` `isosurface()` 先 `_grid_info`（纯 numpy）→ 空结果早返回，之后才 `_image_data`（内部 import pyvista）。
- **测试守卫**：`test_anim3d.py`（`import plotkit as pk` + `pytestmark=requires_pyvista` 8 例）、`test_pyvista_pool.py`（3 例）、`test_multibackend.py`（删模块级 importorskip + 8 例 `@requires_pyvista`）、`test_ns_physical.py`（2 例）、`test_web3d_layers.py`（1 例）；共 22 个 pyvista 用例改为逐用例守卫（另 3 个既存 per-test importorskip：field3d h5py、lic_volume 2 例、ns_scene 1 例，自动进入 ci skip 集合）。
- **基线 v2**：`reports/test_baseline.json` → `schema: plotkit.test_baseline/v2`，`collected=544`，两 profile：`dev_full`（Windows/3.13，全 extras，skipped=0）、`ci_no_extras`（Linux/3.11，五 extras 全 false，`skipped_total=27 / skipped_locations=27`）。均由 `python tools/check_test_baseline.py --write` 机器生成、断言 `failed==0`。
- **门禁判据**：`collected == pinned(544)`、`failed == 0`、`collected == passed + failed + skipped`、`skipped_ids` 集合与 `skipped_total` 均与 profile 一致、禁 xfail/xpass/deselected、pytest exit 0；指纹不匹配 → 红（return 1）。
- **本地验证**：dev（全 extras）`544 collected / 544 passed / 0 failed`，`check_test_baseline: profile=dev_full ... ok=True`；无 extras 仿真（faithful shim：`importlib.util.find_spec` 与真实 import 双屏蔽）`544 collected / 517 passed / 27 skipped / 0 failed`，ci profile `evaluate` → OK。
- **反向验证（先红→复原，baseline `cmp` 复原一致）**：V1 `collected` 钉 545 vs 实 544 → rc=1 红（等价于删除非 3D 用例致 collected 下降）；V2 profile skipped 集合/总数不符 → rc=1 红；V3 伪造 fingerprint 不匹配 → rc=1 红；V4 无 extras 下 `test_volume_surface_rejects_empty_level`（`level=5.0`）→ **1 passed**（返回 400，非 500）。
