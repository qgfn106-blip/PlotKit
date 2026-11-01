---
status: implemented
date: 2026-11-02
---

# R5：多序列 quick / 逐帧时间 / IDW 散点 / GPU 百万粒子

## Problem

上一轮留下的四件事：`pk.quick()` 只能画一条曲线；三维动画导出只有转台、没有数据时间轴；散点场用最近点求值，空间上不连续；GPU 粒子只到 20 万，50 万/100 万整层不可见（任务书要求 100 万 @30 fps）。

## Solution

1. **`quick()` 多序列**：`pk.quick(x, [y1, y2], labels=[...])`，也可以 `pk.quick([y1, y2])`（自动用下标作 x）。
2. **批量端点逐帧 `t`**：`frames: [{"spec":…, "t": 2.0}]`，用 `push_trange` 走与 `/api/render?t=` 同一套窗口语义；有 `t` 时强制进程内渲染（ContextVar 不跨进程）。
3. **散点改 IDW**：3×3×3 桶邻域内按 `1/d²` 加权，最近点距离 <1e-9 时退化为该点；`npz` 可用 `scattered=True` 显式声明。
4. **GPU 粒子修好并冲到百万**：根因是 GPU 点精灵程序的 uniform 全设在了 CPU 程序 `this.points` 上（`uW=0`、`uStride=0`、`uVP` 为单位阵），于是顶点着色器 `ivec2(id % 0, id / 0)` 直接算废，整层不可见。改为全部设在 `this.pointsGpu` 上；并按粒子数做 `countFade = sqrt(120000/count)` 压亮度。

## Implementation Decisions

- `quick()` 的多序列判定看"第二个参数是不是数组的序列"，因此 `quick(x, [y])` 与 `quick(x, y)` 语义明确；长度不一致抛 `ValueError`。
- 逐帧 `t` 只在进程内渲染：`workers` 显式指定时仍照办，但会丢掉 `t`（文档已注明）。
- IDW 权重只取 27 个桶，成本与总点数无关；不做全局 kNN。
- GPU 路径放弃顶点 LOD（`strideP = 1`）：纹理取点后抽稀只会让 id 映射更复杂，实测就是这么错的。
- 亮度随粒子数自适应（`sqrt` 而非线性），保证 12 万与 100 万的观感接近。

## Testing Decisions

- `tests/test_quick.py::test_quick_multi_series`、`::test_quick_multi_series_length_mismatch`。
- `tests/test_render3d_batch.py::test_frames_can_carry_time`（两帧不同 t → PNG 字节不同）。
- `tests/test_field3d.py::test_scattered_velocity_uses_inverse_distance_weighting`（近点更接近该点速度，远点更小）。
- GPU 路径无法单测（需要真实 WebGL），用 `python -m plotkit.ns.app --gpu --particles N --shot` 人工验收，数字记在 `docs/NS_VORTEX.md` §18。

## 实测

| 粒子数 | 帧率 | 备注 |
| --- | --- | --- |
| 12 万 | 63 fps | 修复前整层不可见 |
| 50 万 | 64 fps | |
| 100 万 | 47–50 fps | 任务书目标 30 fps，已超额 |

## Out of Scope

- GPU 路径的顶点 LOD（放弃，理由见上）。
- 数据时间轴的**导出**（批量端点已支持 `t`，前端按钮仍是转台）。
- 散点的 Delaunay/RBF 插值。

---

# R6（同日追加）：HDF5 读取 + 三维 LOD + netlab 仓库卫生

## 需求

| 编号 | 需求 | 结果 |
| --- | --- | --- |
| R6-1 | `ArrayField` 直接读 `.h5/.hdf5` | ✅ 有 `h5py` 时按组找 `x/y/z/u/v/w`（可传 `group=`），否则 `ImportError` 带安装提示 |
| R6-2 | 三维 LOD：按预算自动选采样分辨率 | ✅ `field3d.auto_n(field, budget=200_000)`；`scene(n="auto")` 生效，且不超过场的原生分辨率 |
| R6-3 | netlab 测试与文档纳入版本库 | ✅ `.gitignore` 去掉 `netlab/tests/`、`netlab/docs/`（46 + 62 个文件入库），`MyProject/`、`library/*` 仍排除 |

## 决策

- HDF5 是**可选依赖**：不装也能用 npz，装了才多一条路径；错误信息里直接给 `pip install h5py`。
- LOD 只做"分辨率选择"，不做多级金字塔缓存：三维体积按需重采（几十毫秒级），缓存收益远小于内存代价。
- 原生分辨率优先：对 32³ 的数值解硬采 96³ 只是放大插值误差，不产生信息。

## 验收

- `tests/test_field3d.py::test_array_field_reads_hdf5`（`importorskip("h5py")`）、`::test_auto_n_respects_budget_and_native`、`::test_auto_n_rejects_unknown_string`
- 全量 **436 passed**

