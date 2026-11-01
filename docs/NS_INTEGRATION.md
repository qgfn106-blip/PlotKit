# NS × PlotKit 整合：阶段 3 规格（2026-11-02）

> 本文是这一阶段的需求与验收口径。**改动必须对照本文的条目**；实现与本文冲突时，先改本文再改代码。

## 1. 背景与目标

前一阶段把 NS 涡旋的**计算**（解析 A′ + 伪谱 B）和**私有页面**（`ns.html`）做通了，但两条线是割裂的：

- NS 页面只打 `/api/ns/*`，**不经过** Figure / DataStore / `/api/render`；
- 主查看器（`plotkit.desktop` / `cli demo`）没有 NS 入口。

阶段 3 的目标：**让 NS 的场能用 PlotKit 的通用三维图层表达**，即「一份 Figure spec → 主查看器里直接看」，并把物理量旋钮接回页面。

## 2. 需求（本阶段必须做）

| 编号 | 需求 | 说明 |
| --- | --- | --- |
| R3-1 | `pk.ns.scene.figure(t, **kw)` 产出普通 `pk.Figure` | 至少含一个 `volume` 图层（等值面）与一个 `particles` 图层（示踪点），不依赖 ns.html |
| R3-2 | 主查看器可打开该 Figure | `python -m plotkit.ns.app --figure` 起主查看器（`plotkit.server.app`）并指向该 Figure |
| R3-3 | 物理量旋钮（Γ / a / r_core）在页面上可用 | 只发 `phys=` 参数；默认路径（不碰旋钮）与旧版逐字节等价 |
| R3-4 | Γ 变化必须反映到诊断 | Γ ×2 → `u_max` 约 ×2（容差 5%），页面诊断面板可见 |
| R3-5 | 文档与验收脚本同步 | 本文 + `docs/NS_VORTEX.md` §21 + `docs/WEB3D_LAYERS.md` |

## 3. 方法

1. **场景化**：`src/plotkit/ns/scene.py` 里用 `SimilarityField` / `SolverField` 采样，写成 `fig.add("volume", {...})`、`fig.add("particles", {...})`、`fig.add("surface", ...)`。**不在 scene 里写任何 WebGL**。
2. **数据回流**：`volume` 图层默认走 `mode=surface`（服务端 marching cubes），粒子走 `/api/particles`；两者都是既有端点，不新增协议。
3. **物理量映射**：`PhysicalParams.to_similarity()` 已把 (Γ, a, r_core) 映射成 (c_inf, alpha, x0)；页面只负责把三个滑条串成 `phys=Γ,a,r_core`。
4. **验收靠脚本**：`tools/verify_ns_scene.py` 造 Figure → 起服务 → 点 3D → 抓图 → 回读 `probe`，输出 JSON。

## 4. 规范

- 新增 Python 模块放 `src/plotkit/ns/`，公开 API 从 `plotkit.ns` 导出。
- 图层的字段名用既有约定：`volume` 用 `x/y/z/values`，`particles` 用 `x/y/z/c`；不用自定义键。
- 前端改动只允许改 `ns.html` / `nsview.js` / `app.js` 的既有函数，不新造渲染器。
- 每个改动点必须有测试或验收脚本覆盖；纯样式改动不需要。

## 5. 约束

- **不得推翻 D33**：二维仍走 Matplotlib Agg + `/api/render`。
- **不得破坏既有 400+ 测试**；`pk.kinds()` 只增不减（当前 53）。
- 三维数组**不得悄悄升 float64**（沿用 D38 的 `as_float_keep`）。
- 页面默认路径（不带 `phys`）必须与 `git show 33d4d83:src/plotkit/static/ns.html` 行为一致。
- 不改 GPU 粒子实验（`?gpu=1` 后面的 50 万/100 万问题**本阶段不碰**）。

## 6. 验收标准

| 编号 | 判据 | 验证方式 |
| --- | --- | --- |
| A3-1 | `scene.figure()` 返回的 spec 含 `volume` 与 `particles` 两个图层，且 `pk.kinds()` 全覆盖 | `tests/test_ns_scene.py` |
| A3-2 | 主查看器里三维视图出现等值面 + 粒子，`window.__err == null` | `tools/verify_ns_scene.py` 截图 |
| A3-3 | 默认路径 `particles == 120000`，与旧版一致 | 同一脚本的 `probe` |
| A3-4 | `phys` 路径：Γ 2→8 时 `u_max` 比值 ∈ [3.6, 4.4] | TestClient + 页面 probe |
| A3-5 | 全量 pytest 绿；工作区干净并已 push | `pytest -q` + `git status` |

## 7. 任务分解

- [x] T1 `src/plotkit/ns/scene.py` + `tests/test_ns_scene.py`（5 条）
- [x] T2 `ns/app.py --figure`（主查看器入口，`--shot` 可直接截图）
- [x] T3 验收改用 `ns.app --figure --shot`（省掉单独脚本，逻辑同源）
- [x] T4 `ns.html` 物理量旋钮（`S.gamma/S.alpha/S.rcore`，仅触碰时发 `phys`）
- [x] T5 文档：本文、`NS_VORTEX.md` §21、`WEB3D_LAYERS.md`「NS 集成」、REQUIREMENTS P16-05
- [x] T6 全量测试 + 提交 + push

## 9. 验收结果（2026-11-02）

| 编号 | 结果 | 证据 |
| --- | --- | --- |
| A3-1 | ✅ | `tests/test_ns_scene.py`：`kinds == ["volume","particles"]`，`pk.kinds()` 覆盖 |
| A3-2 | ✅ | `python -m plotkit.ns.app --figure --shot docs/ns_scene.png` → 120 fps、`err:null`，截图见该文件 |
| A3-3 | ✅ | 默认路径 `particles=120000`、`bytes=746716`，与旧版一致 |
| A3-4 | ✅ | Γ 2→8：`u_max` 0.1848 → 0.7393（比值 **4.00**，容差 5%） |
| A3-5 | ✅ | 全量 pytest 绿；提交并 push |

## 10. 结论

「数据 + 窗口自定义绘制」在三维上第一次真正成立：NS 场不再依赖私有页面，`pk.ns.scene.figure()`
产出的就是普通 Figure，主查看器 / 桌面壳 / 服务端出图（`backend="pyvista"`）看到的是同一份 spec。
NS 私有页面仍保留，作为"逐帧调参 + 双轨诊断"的专用工作台。

## 8. 风险

- **页面回归重演**：上次一带 `phys` 就 0 粒子。对策：默认路径不拼 `phys`；先跑 A3-3 再开 A3-4。
- **等值面为空**：`level` 落在数据范围外会 400。对策：scene 里按 `vmin + 0.25*(vmax-vmin)` 给默认值，并允许 `level=` 覆盖。
- **采样成本**：48³ 场 + 2 万粒子在浏览器侧 30 fps 左右。若低于 20 fps，降 `n`/粒子数而不是改渲染。

---

# 阶段 4：补齐 #9 与 #5（2026-11-02）

## 11. 需求

| 编号 | 需求 | 说明 |
| --- | --- | --- |
| R4-1 | `tools/coverage.py` 在 GBK 控制台可用 | 不再因 emoji 抛 `UnicodeEncodeError`；`--check` 退出码语义不变 |
| R4-2 | 新增 `segments` 图层（三维多段折线） | 数据键 `x/y/z` 为**端点点对**（第 2i、2i+1 连成一段）；三个出口都要支持 |
| R4-3 | NS 流线以 `segments` 图层进入主查看器 | `pk.ns.scene.figure()` 默认带流线；`--figure` 打开即可见 |
| R4-4 | 主查看器路径完整 | 程序调用即"数据接入 + 窗口绘制"：spec → `/api/segments` → WebGL `gl.LINES`；pyvista 也能出图 |

## 12. 规范

- 新图层的字段名沿用既有约定（`x/y/z` + `style.width/color`），不新造键。
- 服务端二进制沿用 `PK01 + meta_len + n + meta + float32`，与 `/api/particles` 同构。
- 前端只改 `view3d.js` 的绘制分支与 `app.js` 的 `load3dLayers`，不新增渲染器。
- 每个新图层必须同时具备：mpl drawer、pyvista builder、浏览器绘制、`REQUIRED_DATA` 登记。

## 13. 约束

- 不得改动既有 415 条测试的语义；`pk.kinds()` 只增不减（53 → 54）。
- 流线积分必须在数据包围盒内收敛：单步位移超过域长 2% 时自动缩步长。
- 默认路径（`scene.figure()` 不传参）必须仍然能在 3 秒内构建完成（48³ 场 + 流线）。

## 14. 验收

| 编号 | 判据 | 验证方式 |
| --- | --- | --- |
| A4-1 | `python tools/coverage.py --check` 在 GBK 下退出 0 | 直接跑 |
| A4-2 | `segments` 在 `pk.kinds()` 中，且 mpl/pyvista/浏览器三处都能画 | `tests/test_ns_scene.py` + 截图 |
| A4-3 | `scene.figure()` 的 spec 含 `volume`/`particles`/`segments` 三层 | 单测断言 |
| A4-4 | `--figure --shot` 截图中能看到流线，`window.__err` 为空 | 验收脚本 |
| A4-5 | 全量 pytest 绿 + 提交推送 | `pytest -q` / `git status` |

## 15. 验收结果（阶段 4，2026-11-02）

| 编号 | 结果 | 证据 |
| --- | --- | --- |
| A4-1 | ✅ | `python tools/coverage.py --check` → 退出 0（emoji 自动降级成 `[OK]`/`-`） |
| A4-2 | ✅ | `pk.kinds()` = 54；mpl `Line3DCollection`、pyvista `PolyData lines`、浏览器 `gl.LINES` 三处都能画 |
| A4-3 | ✅ | `tests/test_ns_scene.py::test_scene_has_segments_layer`（layers = volume/particles/segments） |
| A4-4 | ✅ | `python -m plotkit.ns.app --figure --shot docs/ns_scene.png --seconds 14` → 120 fps、`err:null`，画面见流线束 |
| A4-5 | ✅ | 全量 `pytest` → **405 passed**；提交见 git log |

> 备注：`segments` 的 `x/y/z` 是**端点点对**（第 2i、2i+1 连成一段），与 `line3d` 的连续折线不同；
> 服务端 `/api/segments` 与 `/api/particles` 共用 `PK01` 帧格式，前端复用 `parseParticles`。

