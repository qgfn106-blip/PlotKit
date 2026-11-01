---
title: 三维流体场通用绘制 + 三维批量渲染接口
status: implemented
created: 2026-11-02
labels: [ready-for-agent, plotkit, three-d]
---

## Problem Statement

今天 PlotKit 的三维"流体场"能力是围绕 NS 涡旋这一个案例长出来的，有两处卡住了复用：

1. **只有一条专用入口**。想把别的三维流场（CFD 结果、粒子模拟、实验 PIV 数据）画出来，用户得自己拼 `volume` / `particles` / `segments` 三种图层的 `fig.add(...)`，还要自己决定采样网格、粒子种子、流线积分步长。这些逻辑现在都写死在 `pk.ns.scene.figure()` 里——它是"NS 场景"，不是"流体场场景"。
2. **三维渲染完全串行**。Windows 上 OpenGL 上下文绑线程（`wglMakeCurrent`），所以服务端三维只能一个 VTK 线程排队出图。批量场景（动画帧、参数扫描、多视角、多分辨率导出）只能一张一张等：40 帧 500×360 的曲面要 17.4 s。进程池代码（`pyvista_pool.render_many`）已经写好并验证过逐字节一致，但**没有暴露成任何接口**，前端和脚本都够不着。

结果是：用户要么继续用 NS 专用页，要么自己写脚本绕开 HTTP。两个需求（通用化、并发）都卡在"能力有、接口没有"。

## Solution

**A. 三维批量渲染接口（并发）**
把已有的进程池能力暴露成 HTTP 批量端点：一次请求提交 N 帧（同 spec 不同时间/不同视角，或不同 spec），服务端用 N 个 worker 进程并发渲染，返回一个 ZIP（`frame_0001.png` …）。前端"导出动画"和脚本"参数扫描出图"都改走它。串行与并发必须逐字节一致。

**B. 三维流体场通用化**
把"场 → 图层"的翻译从 NS 专用场景里抽出来，变成 `pk.field3d`：一个 **Field3D 数据契约** + 一个 **scene 构建器**。任何满足契约的场（NS 解析解、NS 数值解、npz 数组、未来的 VTK/HDF5 数据）都能一行得到可渲染的 `Figure`。NS 只是其中一个 provider，`pk.ns.scene.figure()` 退化成它的薄封装（行为不变）。

图层词汇表不扩张：仍然只用现有 `volume` / `particles` / `segments` 三种（必要时 `volume` 带 `mode=surface` 出等值面），不新造渲染器。

## User Stories

1. 作为做 CFD 的用户，我想把任意规则网格上的速度场喂给 PlotKit，就得到一张带体积、粒子、流线的三维图，这样我不用自己拼图层。
2. 作为做 CFD 的用户，我想只指定"我要粒子 + 流线，不要体积"，这样我能在弱显卡上快速看结构。
3. 作为做 CFD 的用户，我想指定采样分辨率与包围盒，这样我能在"看得清"和"跑得动"之间自己选。
4. 作为做 CFD 的用户，我想让粒子/流线跟着真实速度场走，而不是被随机撒点糊弄。
5. 作为做 CFD 的用户，我想在时间序列上取某一时刻，这样我能比较不同时刻的结构。
6. 作为做 CFD 的用户，我想一次导出整段时间的帧，这样我能直接做动画。
7. 作为做 CFD 的用户，我想把 npz 里的数组直接当场用，这样我不必先把数据转成 PlotKit 的内部结构。
8. 作为 NS 用户，我想继续用 `pk.ns.scene.figure()`，行为和现在完全一致，这样我已有的脚本不会坏。
9. 作为 NS 用户，我想在通用接口里选择解析场或数值解，这样两种数据源用同一套画图代码。
10. 作为前端用户，我想点"导出动画"就让服务端并发渲染，而不是浏览器一帧一帧等。
11. 作为前端用户，我想看到批量渲染的进度（已完成/总数），这样我知道还要等多久。
12. 作为前端用户，我想在批量渲染失败时拿到"哪一帧失败、为什么"，而不是整个请求 500。
13. 作为脚本用户，我想用一条命令把 100 组参数扫描出图，这样我不用写并发代码。
14. 作为脚本用户，我想控制用几个 worker，这样我不会把机器打满。
15. 作为脚本用户，我想确认并发结果和串行结果**逐字节一致**，这样我敢在论文里用。
16. 作为维护者，我想让批量端点和单帧端点共用同一套 spec 校验，这样不会出现"单帧能画、批量报错"。
17. 作为维护者，我想让进程池的 worker 数量有默认上限与显式覆盖，这样默认配置不会在 4 核机器上开 8 个进程。
18. 作为维护者，我想在 GPU/驱动不可用时优雅回退到单进程，这样批量请求不会整批失败。
19. 作为维护者，我想让 Field3D 契约只有一个必选方法（`velocity(points, t)`），这样第三方实现门槛最低。
20. 作为维护者，我想让 `bounds` / `times` 有合理默认，这样最简实现只写一个方法就能用。
21. 作为维护者，我想让 scene 构建器在数据退化时（全 NaN、零速度、只有 2 个点）返回可渲染的空场景而不是抛异常。
22. 作为维护者，我想让 NS 场景与通用场景共用同一份采样/播种/积分代码，这样修一个 bug 两边都好。
23. 作为用户，我想让三维批量渲染遵守已有的性能预算（单帧 ≤ 400 ms），这样"并发"不是"更慢的串行"。
24. 作为用户，我想让批量渲染的帧数有上限（例如 600 帧），这样一次请求不会把内存打爆。
25. 作为用户，我想让返回的 ZIP 里帧名有序，这样 ffmpeg 能直接吃。
26. 作为用户，我想在文档里看到"怎么把自己的数据变成 Field3D"的最小例子，这样我 5 分钟能上手。
27. 作为用户，我想让 `pk.field3d.scene()` 产出的 `Figure` 既能服务端出图，也能在浏览器 3D 视图里看，这样我不必选边站。
28. 作为用户，我想让体积等值面的水平（level）可调，这样我能从"实心团"调到"薄壳"。
29. 作为用户，我想让流线数量/步长可调，这样我能在细节和噪声之间权衡。
30. 作为用户，我想让粒子数量与点径可调，这样我能在低配机器上降到 2 万点。

## Implementation Decisions

### 数据契约（新增模块 `field3d`）

- 定义 `Field3D` 协议（Python `Protocol`），**唯一必选方法**：`velocity(points: (N,3) float array, t: float) -> (N,3)`。可选：`bounds -> (lo(3), hi(3))`（默认 `[-0.5,-0.5,-1.2]…[0.5,0.5,1.2]`）、`times -> list[float]`（默认 `[0.0]`）、`scalar(name, points, t)`（默认用 `|velocity|`）、`grid()`（规则网格快路径，没有就按 `bounds` 采样）。
- 提供三个内置实现：
  - `SimilarityField`（已有，NS 解析场）——改为显式实现该协议；
  - `SolverField`（已有，NS 数值解）——同上；
  - `ArrayField(path)`（已有 npz）——补上 `bounds`/`times`，并让 `velocity()` 真正可用（当前是 `NotImplementedError`）。
- `pk.field3d.load(path)` 作为工厂：按扩展名选实现（`.npz` → `ArrayField`；未来 `.vtk/.h5` 再扩）。

### 场景构建器（新增模块 `field3d.scene`）

- `scene(field, *, t=0.0, layers=("volume","particles","streamlines"), n=48, extent=None, z_extent=None, particles=12000, streamlines=28, level=None, seed=7, title=None) -> pk.Figure`。
- 内部三件事，全部复用现有代码（从 `ns/scene.py` 搬出来，NS 侧改为 import）：
  1. `sample_velocity(field, t, n, extent, z_extent) -> (xs, ys, zs, speed(nz,ny,nx))`；
  2. `seed_points(field, t, count, extent, z_extent, seed)`（85% 赤道盘 + 15% 轴向柱，确定性）；
  3. `streamline_segments(field, t, seeds, steps, extent, z_extent)`（RK4，单步位移 > 2% 域长自动缩步长）。
- 产出只使用现有图层：`volume`（`values` + `x/y/z`，`style.level` 控制等值面水平）、`particles`（`x/y/z` + `scalar`）、`segments`（端点点对）。不新增 kind。
- `pk.ns.scene.figure()` 变成：构造 `SimilarityField`/`SolverField` → 调 `field3d.scene(...)`，参数映射保持现有默认值（保证 NS 页面与 `--figure` 截图不变）。

### 批量渲染接口

- `POST /api/render3d/batch`，请求体：
  ```json
  {"width": 800, "height": 600, "backend": "pyvista",
   "workers": 4, "format": "zip",
   "frames": [{"spec": {...}}, {"spec": {...}}]}
  ```
  每帧可携带完整 spec（服务端不保存会话状态）；`frames` 上限 600，`workers` 默认 `min(4, cpu-1)`，上限 8。
- 响应：`application/zip`，内含 `frame_0001.png` …（零填充、按请求顺序）；响应头带 `X-PlotKit-Frames`、`X-PlotKit-Workers`、`X-PlotKit-Elapsed-Ms`。
- 失败语义（实现后修订）：**任何一帧失败 → 整批 500**，错误消息带异常类型；不做"部分成功"的 zip——动画缺帧比整批失败更难查。
- 池实现复用 `pyvista_pool.render_many(jobs, workers=...)`；worker 首帧要 import VTK（约 2 s），因此**帧数 < 8 时自动退化为串行**（实测交叉点 15–20 帧，取 8 作保守阈值）。
- 单帧端点 `/api/render` 不变；批量端点内部对每帧复用同一套 `Figure` 构建与校验路径，不另写一份。

### 前端与脚本

- 前端「导出动画」改为一次 POST 批量端点，显示 `已渲染 k/N`（用 `X-PlotKit-Frames` + 轮询 `/api/render3d/progress` 不必要——直接在响应里等，进度用 fetch 的 `onprogress` 估算，够用）。
- CLI：`python -m plotkit.cli render3d --spec frames.json --out frames.zip --workers 4`。
- `tools/bench_pool.py` 的结论（8 帧串行 3.26 s / 40 帧 4 worker 8.93 s ≈ 1.95×）写进文档作为预算依据。

### 兼容与约束

- 不改 `Figure.render()` / `/api/render` 的签名与返回；不新增 kind（保持 54）。
- 不得推翻 D33（二维仍走 Matplotlib Agg + `/api/render`）。
- 三维并发只在 pyvista 后端有意义；mpl 三维批量走串行（明确记录）。

## Testing Decisions

好测试只断言**外部行为**：给一份场/一份 spec，断言"产出了什么"（图层种类、数据长度、帧数、字节一致），不断言内部函数怎么切分、不 mock 私有方法。

接缝（按"尽可能高"取两个，不新增更多）：

1. **场景接缝**：`field3d.scene(field, ...) -> Figure`。断言 `spec["layers"]` 的 kind 顺序、每层 `data` 键存在、`store.values()` 长度成对（segments）、退化输入（零速度/全 NaN/单点）不抛异常。
2. **HTTP 接缝**：`TestClient(create_app(fig))` 打 `/api/render3d/batch`。断言 ZIP 内文件名有序、帧数与请求一致、`Content-Type`、单帧失败降级为 `.error.txt`、超上限 400、`workers` 越界被夹紧。

先例：`tests/test_web3d_layers.py`（二进制帧布局）、`tests/test_ns_scene.py`（场景图层断言）、`tests/test_pyvista_pool.py`（串行/并发逐字节一致）——新测试照这三个的写法走，不引入新框架。

另加一条**一致性测试**：同一组帧，`workers=1` 与 `workers=4` 产出的 ZIP 内 PNG 逐字节相同（复用 `test_pyvista_pool.py` 的比对方式）。

## Out of Scope

- NS 页面与主查看器的 UI 合并（用户明确说不用合并，两套都留着）。
- GPU 粒子推进的 50 万/100 万可见性问题（仍停在 `?gpu=1`）。
- VisPy 后端、Blender 接入、HDF5 存储、三维 LOD。
- 三维真矢量（SVG/PDF）出口——仍是混合或回退 mpl。
- 分布式渲染（跨机器）；本 spec 只做单机多进程。

## Further Notes

- 用户原话（2026-11-02）："完成①三维并发接 HTTP（`pyvista_pool` 已实现但没暴露成接口，②NS 两套 UI 不用合并完全一致，并且不只专门做 ns，能扩展到各种三维流体力学绘制才是关键"。
- 现有可复用资产：`pyvista_pool.render_many`（已实测 40 帧 1.95×、逐字节一致）、`ns/scene.py` 的采样/播种/积分三段（搬出来即可）、`/api/volume` `/api/particles` `/api/segments` 三个二进制出口（批量端点不需要它们，但前端仍需）。
- 风险：worker 进程各自 import VTK ≈ 2 s，帧数少时并发反而更慢；文档里必须写清"少于 8 帧别开并发"。
- 风险：`ArrayField` 目前 `velocity()` 未实现，先补它才能证明"任意数据能进来"；这是通用化的第一块试金石。

---

## 实现结果（2026-11-02）

| 项 | 结果 |
| --- | --- |
| `pk.field3d`（Field3D 协议 + `scene()` + 采样/播种/流线三段） | ✅ 新增 `src/plotkit/field3d.py`；`pk.ns.scene.figure()` 退化成薄封装，行为不变 |
| `ArrayField.velocity` | ✅ 规则网格三线性插值（越界夹住），补 `bounds`/`times` |
| `POST /api/render3d/batch` | ✅ 二维帧进程内 mpl、三维帧走 `pyvista_pool`，按请求顺序打 zip；`frames` 上限 600 |
| CLI `plotkit render3d` | ✅ `--payload frames.json --out out.zip --url … --workers N` |
| 测试 | ✅ `test_field3d.py`(8) + `test_render3d_batch.py`(5) + `test_cli_render3d.py`(4)；全量 **421 passed** |

接缝与规格一致：场景接缝（`field3d.scene`）、HTTP 接缝（`/api/render3d/batch`）、CLI 接缝（`post_batch` + `_cmd_render3d`）。

