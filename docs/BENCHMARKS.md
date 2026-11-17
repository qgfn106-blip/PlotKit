# PlotKit 性能基准（WP-4 分层回归基线）

> 最后更新：2026-11-18（WP-4：统一指纹、四态判定与渲染分层 runner）。
> 本页不载任何性能数字；唯一机器基线是 `docs/bench_baseline.json`（产品路径）与
> `docs/bench_layers_baseline.json`（渲染分层）。两份材料冲突时以 JSON 为准。

## 基线文件

| 文件 | 内容 | 生成方式 |
|---|---|---|
| `docs/bench_baseline.json` | 产品路径：cool PNG/SVG、hot blit/autoscale、downsample、append、add_2m | `python tools/bench_regress.py --json docs/bench_baseline.json` |
| `docs/bench_layers_baseline.json` | 渲染分层：重建构图 vs 复用 artist，100/500/1000/5000 点 | `python tools/bench_layers.py --out docs/bench_layers_baseline.json` |
| `docs/bench_config.json` | 退化带、内存带、退出码与判定说明 | 手工维护，受版本控制 |

## 判定契约

两个 runner 均输出四态，退出码来自 `docs/bench_config.json`：

| 状态 | 含义 | 退出码 |
|---|---|---|
| `PASS` | 指纹、输入契约和线程配置一致，且未超出退化带 | 0 |
| `DRIFT` | 同一契约下 p50 或内存朝退化方向超出阈值 | 1 |
| `INCOMPARABLE` | 硬件/OS/Python/依赖/线程/输入契约/runner 版本不同 | 2 |
| `ERROR` | 基线缺失、不可读或测量失败 | 3 |

只有相同指纹、相同输入契约和相同线程配置才允许性能 PASS；指纹不同必须
INCOMPARABLE，禁止把不同机器的数字当作回归。指纹覆盖 CPU、machine、CPU 数、
OS、Python 实现、NumPy/SciPy/matplotlib 版本、BLAS/MKL 线程变量、后端、分辨率、
输入契约 SHA-256 与 runner 版本。

## 统计与内存口径

- 每案固定输入、随机种子、预热次数和重复次数；计时边界是单次操作
  `time.perf_counter()`，报告 `p50/p95/min/max/n/samples/mean/stdev`。
- 内存同时记录 `tracemalloc_peak_mb` 与可选 `rss_before/after/delta/peak`
  （psutil 可用时）；缺失字段如实为 null，不伪造。
- 阈值只写在 `docs/bench_config.json`，不得在文档或测试里硬编码毫秒数。

## 命令

```bash
python tools/bench_regress.py                 # 产品路径打表
python tools/bench_regress.py --check         # CI 闸门：PASS/DRIFT/INCOMPARABLE/ERROR
python tools/bench_layers.py                  # 渲染分层打表
python tools/bench_layers.py --check          # 渲染分层闸门
```

## 复现注意

- `PLOTKIT_RENDER_CACHE=0` 可关掉持久 Figure 缓存；关掉后冷导出走纯无状态路径。
- 数据形态须先固定（`sine` 或 `noise`）；热重绘场景含 `store.add(..., life="replace")` 换帧成本，贴近实时页面。
- 不同并发负载会污染微基准：生成基线或复跑 `--check` 时应单独运行，不要与其他基准并行。
