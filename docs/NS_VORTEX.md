# 三维 NS 涡旋可视化（模式 A′：前导阶自相似解）

> 目标：把「Navier–Stokes 涡旋内旋、轴向拉伸、有限时间奇异性演化」做成 PlotKit 里一个**由真实场驱动**的三维可视化模块，而不是演示动画。
> 状态：2026-11-01 首版。渲染 98–120 fps，诊断与公式同屏，参数可实时调。

## 1. 数学来源与模式声明

- 论文：**Finite time blowup for Navier–Stokes**（2026-09-08，166 页，附 Lean 形式化仓库 `openai/NavierStokesAndEuler`）。§3.1 给出显式相似坐标，剖面 `E/U` 由 §4 隐式构造，**没有闭式解**。
- 本模块实现的是 **A′：前导阶相似场复现**。相似坐标与标度照搬论文：

```
τ = 1 − t
r = √(2qX)              z = q^{1/2−h} η
q = τ / (1 − η²)
u_θ = q^{−(1/2+h)} E(X, η)
u_z = q^{−(1/2+h)} U(X, η)
u_r = V₀(X) / r         （由不可压条件积出）
‖u‖_L∞ ~ τ^{−(1/2+h)}   ‖ω‖_L∞ ~ τ^{−1}
```

- 剖面（论文没有闭式，这里自选并**显式标注**）：

```
E = c∞ · sech²(η/η₀) · √X / (1 + (X/X₀)^{h+1})
U = c∞ · α · η · sech²(η/η₀) · √X / (1 + (X/X₀)^{h+1})
```

近轴 `E ≈ c∞√X`（轴上光滑，无 1/r 奇点），远场 `E ~ X^{−1/2−h}`（与论文尾部一致）；`U ∝ η` 保证 `z=0` 两侧轴向速度反向。
**不复现**：环带脉冲初始数据、光滑紧支外力（论文 §4 的构造工具），因此本模块**不声称**给出爆破解。

界面左下常驻标注：`Mode A-prime - Leading-order similarity field (not a verified blow-up solution)`。

## 2. 代码结构

| 文件 | 职责 |
| --- | --- |
| `src/plotkit/ns/field.py` | `SimilarityParams` / `inverse_map` / `profile_table` / `velocity_at` / `SimilarityField`（`NSField` 协议）/ `ArrayField`（`.npz` 外部场） |
| `src/plotkit/ns/diagnostics.py` | `VortexStats` / `analyze`（连续场积分）/ `grid_stats`（N³ 网格）/ `convergence`（32³/64³/128³） |
| `src/plotkit/server/ns_app.py` | `/api/ns/{meta,field,slice,velocity,pathlines,diagnostics,formula.svg}`，二进制帧 `PKNS + meta_len + meta + float32` |
| `src/plotkit/static/ns.html` | 页面：公式 / 时钟 / 诊断双表 / 旋钮 / 时间轴 / 色标 / 模式标签 |
| `src/plotkit/static/nsview.js` | WebGL2：体积 raymarch + instanced 粒子 + 轨迹线 + 相机 |
| `src/plotkit/ns/app.py` | 启动器：`python -m plotkit.ns.app`，`--shot` 出图自检 |

## 3. 关键决策（Q1–Q11 逐轮确认）

| 编号 | 决策 |
| --- | --- |
| Q1 | A′ 前导场复现，剖面自选并标注，不复现的部分写清 |
| Q2 | 自研 WebGL2 扩展（复用既有相机/装饰/二进制协议），高质量出图仍走服务端 PyVista |
| Q3 | CPU 算剖面表 → 浮点纹理，GPU 每帧只更新 τ |
| Q4 | 单参数核 + 幂律尾；三个旋钮 `h / X₀ / η₀` |
| Q5 | raymarching 体积 + 半透明粒子，渲染顺序 体积 → 粒子 → 轨迹 → 叠层 |
| Q6 | 双层粒子：预积分 pathline（静态 VBO，按 τ 生长）+ 活动粒子（GPU 每帧 RK4） |
| Q7 | 公式用 mpl mathtext 出 SVG，数值用等宽文本实时覆盖 |
| Q8 | 参数全局即时生效（改参数整个时间轴重算），另加快照对比 |
| Q9 | 诊断双轨：解析（连续场）+ 网格 N³ + 32³/64³/128³ 收敛趋势 |
| Q10 | 通用 `NSField` 接口，解析场是首个实现，另支持 `.npz` 外部场 |
| Q11 | 一次做完再汇报；把案例中暴露的问题回灌 PlotKit |

## 4. 实测

场（`SimilarityParams()`，`h=0.005`）：

| 量 | τ=0.2 | τ=0.05 | τ=0.02 | τ=0.005 |
| --- | --- | --- | --- | --- |
| `u_max` | 0.840 | 1.834 | 2.909 | 5.818 |
| `ω_max` | 9.72 | 39.1 | 98.0 | 391.4 |
| 涡核半径 | 0.350 | 0.321 | 0.204 | 0.103 |

- 轴上角速度 `Ω = u_θ/r` 在 `r = 1e-4 … 1e-2` 恒定 → 刚体旋转核，无 1/r 奇点。
- 不可压残差 `‖∇·u‖/‖u‖`：t=0.2/0.5/0.9 → **2.5% / 2.3% / 2.1%**。
- 标度自洽：`u_max` 比值 6.9 ≈ 40^0.505，`ω_max` 比值 40.2 ≈ 40^1.0。

渲染（1280×820 窗口，2217×1372 canvas）：**98–120 fps**；粒子 24 000；体积 raymarch 每像素最多 220 步。

## 5. 已知限制

1. **不是爆破解**：只复现前导阶相似结构；论文的环带脉冲与紧支外力未实现，`h` 的严格区间是 `0<h<1/100`（界面放宽到 0.5 仅作视觉演示，`paper_compliant` 会标注）。
2. **剖面是自选的**：论文的 `E/U` 是隐式构造，没有闭式解，本模块用的是「sech² 核 + 幂律尾」近似族。
3. **视觉与参考视频有差距**：参考图那种「细亮丝 + 湍流状纹理」来自更陡的径向剖面与更多粒子；本场是光滑轴对称解，观感是「发光柱 + 螺旋粒子流」。
4. 网格列的散度残差（0.26）明显大于解析列（0.03），这是方位角离散误差，面板已如实展示。

## 6. 怎么跑

```bash
PYTHONPATH=src python -m plotkit.ns.app                # 打开窗口
PYTHONPATH=src python -m plotkit.ns.app --shot out.png --seconds 10   # 自检截图
```
