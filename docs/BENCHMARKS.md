# PlotKit 性能基准（阶段 F 回归基线）

> **状态：unverified（2026-11-09 严格审计）**。本页曾载有单机单次运行的性能数字，缺硬件指纹、缺 CI 复跑脚本门，且与机器基线口径不一致；依 `docs/PLOTKIT_P0_DECISIONS_2026-11-09.md` ⑧ 已删除全部性能数字表。在严格审计 §7.2 层 C 与 §8 基准门建立前，不得引用本页为性能证据。

> 最后更新：2026-11-09（裁定 ⑧：删除 MD 数字表；唯一机器基线改为 `docs/bench_baseline.json`）

**唯一机器基线**：`docs/bench_baseline.json`。所有性能数字只由该 JSON 承载，本页不复述任何数字；两份材料冲突时以该 JSON 为准。

**数字生成与 X10 解除判据**：数字须由 `tools/bench_regress.py --json` 生成，并带可复现脚本、采集 commit、采集时间与硬件指纹（CPU / Python / matplotlib / Agg / 分辨率）；X10 解除须「数字 → 可复现脚本 → 硬件指纹 → CI 门」四者齐全，缺一不解除。在此之前，文档不得写入任何性能数字。

**脚本**：`tools/bench_regress.py`（产品路径基准，不是孤立微基准）
**环境**：本机 Windows / Python 3.13 / matplotlib Agg / 1200×700 @100dpi / 6 通道 × 20k 点
**测定**：预热 2 次后取 5 次 p50（追加类 1 次，因为代价是累计的）
**数据形态**：`sine`（平滑正弦）与 `noise`（累计随机游走）两种。噪声形态在 Agg 下明显更慢，单测一种会误判。

```bash
python tools/bench_regress.py              # 打表
python tools/bench_regress.py --json docs/bench_baseline.json
python tools/bench_regress.py --check      # 超预算非零退出（CI 用）
```

## 对应改动

| 阶段 | 改动 | 文件 |
|---|---|---|
| B | 几何增长缓冲区替代 `np.concatenate` 追加 | `src/plotkit/store/registry.py`（`DataSet.append` / `capacity_bytes`） |
| C-1 | M4 抽稀（分桶 argmin/argmax，保 float32） | `src/plotkit/store/downsample.py`（`m4_envelope` / `downsample_xy`） |
| C-2 | 视窗零拷贝（先切片再降采样） | `src/plotkit/backends/plotly_backend.py`（已随 D33/P14-01 删除）、`src/plotkit/api/native.py` |
| D-1 | 持久 Figure + blit 热重绘 | `src/plotkit/backends/livecache.py` |
| D-2 | 统一 PNG 编码器（绕过 print_png 内部整图 draw） | `src/plotkit/backends/livecache.py`（`encode_png`） |

## 复现注意

- `PLOTKIT_RENDER_CACHE=0` 可关掉持久 Figure 缓存；关掉后冷导出走纯无状态路径。
- 数据形态须先固定（`sine` 或 `noise`）；热重绘场景含 `store.add(..., life="replace")` 换帧成本，贴近实时页面。
