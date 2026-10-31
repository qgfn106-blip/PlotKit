# PlotKit 性能基准（阶段 F 回归基线）

**脚本**：`tools/bench_regress.py`（产品路径基准，不是孤立微基准）
**环境**：本机 Windows / Python 3.13 / matplotlib Agg / 1200×700 @100dpi / 6 通道 × 20k 点
**测定**：预热 2 次后取 5 次 p50（追加类 1 次，因为代价是累计的）
**数据形态**：`sine`（平滑正弦）与 `noise`（累计随机游走）两种。噪声形态在 Agg 下明显更慢，单测一种会误判。

```bash
python tools/bench_regress.py              # 打表
python tools/bench_regress.py --json docs/bench_baseline.json
python tools/bench_regress.py --check      # 超预算非零退出（CI 用）
```

## 当前基线（2026-10-31，阶段 B–D 优化后）

| 场景 | sine p50 | noise p50 | 优化前 |
|---|---|---|---|
| 冷导出 PNG（每帧重建） | **111.3 ms** | **106.6 ms** | 232.3 ms |
| 冷导出 SVG | 263.9 ms | 262.5 ms | 351.4 ms |
| 热重绘 blit（固定视窗） | **48.4 ms** | **45.4 ms** | 122.1 ms |
| 热重绘整张重画（自动缩放） | 89.8 ms | 104.6 ms | 165.7 ms |
| 抽稀 2M 点 | **8.9 ms** | 9.3 ms | 82.2 ms |
| 追加 2000×1000 点 | **35.4 ms** | 33.2 ms | 5345.4 ms |

内存峰值（tracemalloc）：

| 项 | 峰值 |
|---|---|
| 抽稀 2M 点 | 10.8 MB（旧 34.2 MB） |
| 追加 2000×1000（累计 2M 点） | 60.2 MB |
| 入库 2M float64 | 16.0 MB（= 数据本身，无多余副本） |

## 预算（`--check` 用，宽松上限，只防大退化）

`cold_png ≤ 400ms`、`cold_svg ≤ 700ms`、`hot_blit ≤ 120ms`、`hot_autoscale ≤ 220ms`、
`downsample_2m ≤ 60ms`、`append_total ≤ 200ms`。

## 对应改动

| 阶段 | 改动 | 文件 |
|---|---|---|
| B | 几何增长缓冲区替代 `np.concatenate` 追加 | `src/plotkit/store/registry.py`（`DataSet.append` / `capacity_bytes`） |
| C-1 | M4 抽稀（分桶 argmin/argmax，保 float32） | `src/plotkit/store/downsample.py`（`m4_envelope` / `downsample_xy`） |
| C-2 | 视窗零拷贝（先切片再降采样） | `src/plotkit/backends/plotly_backend.py`、`src/plotkit/api/native.py` |
| D-1 | 持久 Figure + blit 热重绘 | `src/plotkit/backends/livecache.py` |
| D-2 | 统一 PNG 编码器（绕过 print_png 内部整图 draw） | `src/plotkit/backends/livecache.py`（`encode_png`） |

## 复现注意

- 别在未固定的数据形态上比数字：正弦 vs 噪声差约 4.9 倍（Agg 的 `draw_path` 占 92%）。
- `PLOTKIT_RENDER_CACHE=0` 可关掉持久 Figure 缓存；关掉后「冷导出」那两行才是纯无状态路径。
- 热重绘两行都含「`store.add(..., life="replace")` 换一帧数据」的成本，贴近实时页面。

## 三维双后端（D38）

`python tools/bench_3d.py`（本机，700×450，预热后 p50，3 次中位）：

| 场景 | matplotlib | PyVista | 倍数 |
|---|---|---|---|
| surface 30×30 | 181ms | 179ms | 1.0× |
| surface 60×60 | 328ms | 183ms | 1.8× |
| surface 100×100 | 714ms | 173ms | 4.1× |
| scatter3d 1 万 | 242ms | 167ms | 1.5× |
| scatter3d 10 万 | 1375ms | 218ms | 6.3× |
| voxels 15³ | 1578ms | 148ms | 10.7× |
| voxels 25³ | 5966ms | 164ms | 36.5× |

PyVista 侧的两个前提：**复用离屏 Plotter**（新建窗口每帧固定 450–600ms，复用后 12–30ms）和**专用 VTK 线程**（线程漂移会 `wglMakeCurrent failed` 出黑图）。内存：首次三维渲染后 RSS ≈297MB，`close_plotters()` 后 260MB（VTK/驱动常驻约 165MB 不归还）。
