---
status: implemented
date: 2026-11-02
---

# 编程时的即时出图 + 三维动画导出 + 等值面开关 + 散点场

## Problem

写仿真/调试代码时，手上有一串数组想看长什么样，现有路径是「建 Figure → add_data → add_plot → render → 存文件」五步，十几行代码，节奏被打断。另外三处遗留：`field3d.scene` 只能整体开关图层，不能单独关等值面；`ArrayField` 只认规则网格，散点/非结构数据进不来；前端三维场景没有「导出动画」入口，只有二维的 GIF 动画按钮。

## Solution

1. **`pk.quick()`**：一行出图。`pk.quick(y)` / `pk.quick(x, y)`，返回 PNG 字节；给 `path=` 就写文件并返回路径；`show=True` 用系统看图器打开。可选 `kind`/`style`/`width`/`height`/`dpi`/`fmt`，内部仍走 `Figure` + `add_plot`，与正式出图同一条管线。
2. **`field3d.scene(iso=…)`**：`True` 强制带等值面层、`False` 强制去掉、`None` 跟随 `layers`。
3. **`ArrayField` 支持散点/非结构**：`x/y/z` 为点表（长度 N）、`u/v/w` 形状 `(N,)` 或 `(nt, N)` 时进入 `scattered` 模式，用均匀桶网格 + 3×3×3 邻域最近点求值。
4. **三维「导出动画」走批量端点**：主查看器三维工具条新增按钮，按 24 帧转台（只改 `figure.azim`）POST 到 `/api/render3d/batch`，浏览器直接下载 zip。

## User Stories

- 作为调试者，我想 `pk.quick(y)` 一行看到波形，不用建 Figure。
- 作为调试者，我想把图直接存到指定路径并返回路径，方便接着 `print` 或打开。
- 作为调试者，我想在 `quick()` 里直接传 `kind="marker"`、`color=`，不用查文档。
- 作为三维使用者，我想单独关掉等值面，只留粒子/流线。
- 作为三维使用者，我想把散点速度场（CFD 输出、粒子数据）直接喂给 `field3d.scene`。
- 作为演示者，我想在浏览器里把当前三维场景导出成一组 PNG，交给 ffmpeg 合成视频。

## Implementation Decisions

- `quick()` 不做静默兜底：长度不一致抛 `ValueError`，参数个数不对抛 `TypeError`——调试工具吞异常比崩掉更难查。
- `quick()` 的 `style` 与 `**kwargs` 合并后交给既有样式白名单，未知键沿用 warn/strict 语义。
- 散点求值用**最近点**而非反距离加权：无参数、可预测、O(1) 期望复杂度；需要平滑时应先插值到规则网格（已在 Out of Scope 写明）。
- 桶网格边长取 `2·cbrt(体积/N)`，下限为包围盒最长边的 1/64，避免退化。
- 三维动画导出只做**转台**（相机方位角），因为批量端点按帧吃完整 spec；数据时间轴动画需要 spec 支持逐帧 `t`，列入 Out of Scope。
- 导出走 `Blob` + `<a download>`，与既有导出路径一致，不引入新依赖。

## Testing Decisions

三个接缝：

1. **`pk.quick()`**（模块接缝）：`tests/test_quick.py` 6 条——字节魔数、写文件返回路径、`kind`/样式透传、长度不一致、参数个数、SVG 出口。
2. **`field3d.scene(iso=)`**（场景接缝）：`tests/test_field3d.py::test_iso_switch_toggles_volume_layer`——三种取值下的图层集合，且 `volume` 不重复。
3. **`ArrayField` 散点**（数据接缝）：`tests/test_field3d.py::test_array_field_supports_scattered_points`——`scattered` 判定 + 常量场逐点求值。

前端导出按钮不做自动化（需要真实 WebView2 + 下载对话框），改为手工验收：点按钮后检查 zip 内 24 张 PNG 且尺寸为 900×620。

## Out of Scope

- 数据时间轴动画（需要 spec 逐帧 `t` 与后端的 `t_end` 传递）。
- 散点的反距离加权 / RBF 插值 / Delaunay 线性插值。
- `quick()` 的多子图、图例、误差棒等复杂版式（用完整 API）。
- GPU 粒子 50 万/100 万档（仍停在 `?gpu=1`）。
- VisPy、Blender、HDF5、三维 LOD。

## Further Notes

- `quick()` 的默认尺寸 900×520 与文档里的示例图一致，避免"调试图"和"正式图"观感割裂。
- 三维导出默认 24 帧是折中：转台一圈 24 帧在 15 fps 下 1.6 s，zip 约 3–6 MB。
- 若后续要让批量端点支持数据时间轴，建议在 frame 里加 `t` 字段并透传给 `render_bytes(t_end=…)`，改动面很小。
