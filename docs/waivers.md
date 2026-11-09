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
   - `reports/test_baseline.json` 升 `schema: plotkit.test_baseline/v2`，新增 `environment_fingerprint` 与**按指纹的两套 profile**：`ci_no_extras` 与 `dev_full`，各自记录 `collected`（= `reports/test_baseline.json` 的 pinned 常量）与 `skipped`（该环境应有的 skip 用例清单 + 计数）。
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

- `collected` 严格等于 `reports/test_baseline.json` 的 pinned 常量（数值只在该 JSON 维护；合法增量见 W-002），放宽为 `>=` 一律禁止；不删任何断言；不用 `pytest -k`；`workflow` 的 `.[dev,web]` 一行不动（不把 extras 装进 CI）。
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
- **门禁判据**：`collected == pinned`（值见 `reports/test_baseline.json` 的 `collected`）、`failed == 0`、`collected == passed + failed + skipped`、`skipped_ids` 集合与 `skipped_total` 均与 profile 一致、禁 xfail/xpass/deselected、pytest exit 0；指纹不匹配 → 红（return 1）。
- **本地验证**：dev（全 extras）`544 collected / 544 passed / 0 failed`，`check_test_baseline: profile=dev_full ... ok=True`；无 extras 仿真（faithful shim：`importlib.util.find_spec` 与真实 import 双屏蔽）`544 collected / 517 passed / 27 skipped / 0 failed`，ci profile `evaluate` → OK。
- **反向验证（先红→复原，baseline `cmp` 复原一致）**：V1 `collected` 钉 545 vs 实 544 → rc=1 红（等价于删除非 3D 用例致 collected 下降）；V2 profile skipped 集合/总数不符 → rc=1 红；V3 伪造 fingerprint 不匹配 → rc=1 红；V4 无 extras 下 `test_volume_surface_rejects_empty_level`（`level=5.0`）→ **1 passed**（返回 400，非 500）。

## 九、跨 OS / ffmpeg 修正（2026-11-09 第二次推送后补）

- `ci_no_extras` profile 现为 `skipped_total=29`（原 27 + `tests/test_anim.py:125` / `:139` 两个 ffmpeg-gated mp4 用例）。
- 生成用 faithful shim：同时屏蔽 `importlib.util.find_spec(<blocked>)` → None 与真实 import（shim 模块 raise ImportError），并在生成期令 `shutil.which("ffmpeg")` 返回 None，使「未安装」判定与真实 import 一致（避免只在 find_spec 层面假可用导致 selector 用例误跑）。
- 环境指纹新增 `ffmpeg` 布尔（`shutil.which("ffmpeg") is not None`），dev_full=True / ci_no_extras=False。
- 门禁失败时除 `::error::<violation>` 外，另把 `FAILED <nodeid>` 列表并入注解，便于无 token 定位具体失败用例。此为诊断可观测性增强，不放宽任何判据。

---

## W-002 · 2026-11-10 · pinned 常量演进的事后如实记录与前瞻规则（状态：待用户追认，非事前豁免）

> **性质声明**：X11 规定红线动作必须**事前**写入 `docs/waivers.md` 并获批、**不得事后补豁免**。`544→546→556` 的 pinned 常量变更已随 N1 / N5 阶段实际发生；本条**不是**对这些既成变更的事后豁免，**不伪称**曾用过事前批准，只做三件事：如实记录、声明判据从未放宽、订立前瞻规则。状态为「**待用户追认**」，在用户追认前不得当作已批准豁免使用。

### 一、如实记录：pinned 常量的三次取值（数值一律以 `reports/test_baseline.json` 的 `collected` 为准）

| 取值 | commit（PlotKit `main`） | 增量来源 | collected |
| --- | --- | --- | --- |
| 544（基线） | `116ec67` → `4bab632` → `2e0ed2b` → `73494f6` → `96e5a80` | P0 契约冻结基线；N0 门禁加固未增删用例 | 544 |
| 546 | `f30b593`（N1 contrib 拆分） | 新增 2 条 contrib 隔离相关测试 | 546 |
| 556 | `3942419`（N5 行为保持型薄适配） | 新增 `tests/contract/test_decision_consistency.py` 10 条对照用例 | 556 |

依据：`git log --oneline -- reports/test_baseline.json` 与各 commit 的 `"collected"` 字段。三次均为**新增真实用例**导致 collected 上升，未删任何断言、未用 `pytest -k`、未把 `.[dev,web]` 改成装 extras、未把等号判据放宽为 `>=`。

### 二、判据从未放宽（对应用户 2026-11-10 复核 ①）

- 现行唯一放行判据恒为合取式：`pytest exit 0 AND collected == reports/test_baseline.json 的 pinned 常量 AND failed == 0 AND skipped 显式且与 profile 一致 AND 门禁 violations == 0 AND reports 二次生成 sha256 不变`。由 `tests/contract/test_ci_gate.py` 与 `tools/check_test_baseline.py` 机检。
- 缺陷（用户指出）：`docs/waivers.md` §五曾硬写「`collected` 保持 **544**」、`tools/check_test_baseline.py:5` docstring 曾写「本轮 544」、`docs/specs/2026-11-09-p0-contract-freeze.md:13` 覆盖声明曾写 `collected == 常量 544`、`docs/REQUIREMENTS_AND_PROGRESS.md:85` D40 曾写 `collected=544`、`docs/tickets/README.md:37` 曾以「签字表 G0 钉定常量」为准 —— 把某一时点的点值当成永久判据，与后来合法增长的 pinned 冲突，观感上像「静默改判据」。
- 修复：上述**判据性**表述全部改为「引用 `reports/test_baseline.json` 的 pinned 常量」，不再写死数值；W-001 的**不变约束**（严格相等、不删断言、不装 extras、不改 probe 三态 / API_VERSION、不删 `PUT /api/spec`、不 rebase / force-push / amend / reset、push 需 X1 授权等）逐字保留，只把「544」换成常量引用。
- 本文件 §一/§二/§八/§九 与 `docs/specs/2026-11-09-p0-contract-freeze.md` §实测 中保留的 `544` / `27` / `29` / `70` 等，是**各次实测的历史点值**，不是现行判据；本节即为其历史声明。

### 三、前瞻规则（今后生效）

1. 任何 `reports/test_baseline.json` 的 `collected` 变更，须**事前**在 `docs/waivers.md` 新开 `W-00N` 条，写明增量来源（新增 / 删除了哪些真实用例、对应哪个阶段与 commit）、`--collect-only` 前后数值、两 profile 的 `skipped_ids` 变化，经用户批准后才改基线并 push。
2. 禁止在任何文档 / 注释 / 判据里写死 collected 数值；一律引用 `reports/test_baseline.json` 的 `collected`。
3. 禁止把 `== pinned 常量` 放宽为 `>=`、禁止用测试数上升当放行依据（X7）、禁止删断言凑数。
4. 现行口径以 `docs/GOVERNANCE_SSOT_2026-11-10.md` §4 为准；本条与该 SSOT 冲突时以 SSOT 为准。

### 四、状态

- **状态：待用户追认（不是「已批准」）**。本条不授予任何新豁免、不追认既往红线动作；若用户认为 544→546→556 需另行审批，请在复核时逐条裁定。
- 关联：`docs/GOVERNANCE_SSOT_2026-11-10.md` §3/§4/§6、`docs/specs/2026-11-09-p0-contract-freeze.md` 覆盖声明、`reports/test_baseline.json`。
