# 05: RenderTarget/Decision/Backend Protocol + 8 行能力矩阵 + select() 唯一决策点 + X6

**What to build:** 调用方拿到一个可声明、可枚举、可序列化的「为什么选这个后端」的答案：给定 FigureDocument、RenderTarget、policy 与可用后端集合，`Selector.select()` 返回一条 Decision；8 行能力矩阵每行各有一条可机检的选择断言，降级绝不静默。

**Blocked by:** 01（四份 JSON 契约 + 加载器）
**Status:** ready-for-agent

- [ ] `RenderTarget` 含 `xlim` / `ylim` / `quality: Literal["draft","balanced","publication"]`（计划 §4 :284-286）。
- [ ] `Decision` 为 frozen dataclass，字段 `backend` / `reason`（人可读）/ `fallback` / `capabilities_used` / `degraded`（计划 §4 :288-294），可序列化为 JSON。
- [ ] `Backend` Protocol 声明 `name` / `version` / `capabilities` / `supports()` / `render()`（计划 §4 :296-300）。
- [ ] `Selector.select()` 是新增状况判断的**唯一**落点；环境变量只允许覆盖 `policy`，调试指定后端名必须同时置 `degraded=True`（X6）。
- [ ] 8 行矩阵各一条选择断言：2D 出版矢量→mpl；3D 出版矢量→hybrid3d；3D 交互/大规模→pyvista（未装 `three` 时 `degraded=True` 且不崩）；百万点时序→canvas 抽稀；矢量场→lic/quiver/streamplot；实时流式→Frame v1；动画/批渲染→anim3d/render3d；NS 涡旋教学→ns/*（计划 §4.4 :311-320）。
- [ ] 不删任何能力；`src/plotkit/backends/dispatch.py:21-23` `BACKEND_VISPY` 恒不可用与 `:179-186` `_hybrid_3d(fmt)` 保留原状，既有隐式分支不在本票删除（X1；P3 收敛属 Out of Scope）。
- [ ] 不改 `src/plotkit/backends/mpl_backend.py` 的 52 个 `_draw_*` 绘制语义（CODE_STANDARDS §0 等价性要求）。
- [ ] `Decision.reason` 可直接写入 `X-PlotKit-Decision` 响应头，不留第二份人可读解释。
- [ ] 等价性证据为命令输出留痕，不是「脚本存在」；不以测试数量上升作放行条件（X2 / X7）。
- [ ] 旧基线不退化：`python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（最终钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准）。

完工检测：8 行矩阵逐行 `select()` 行为断言全绿并留命令输出；机检调试指定后端的每条路径均带 `degraded=True`（X6）；`cd PlotKit && python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`。
