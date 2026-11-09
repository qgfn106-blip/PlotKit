# 归档指针（非原件）：PLOTKIT_ORIGIN_REFACTOR_REVIEW_2026-11-09.md

> ⚠️ **本文件不是原件，也不是原件的逐字恢复。** 原件是工作区根 `E:\Python\MyPython\ProjectPoint\docs\PLOTKIT_ORIGIN_REFACTOR_REVIEW_2026-11-09.md`（P0 复核报告，约 47658B，175 行），于 2026-11-09 23:55 清理删除，**从未提交进 PlotKit 仓**，当前不可逐字恢复。仓内历史文档以 `docs/PLOTKIT_ORIGIN_REFACTOR_REVIEW_2026-11-09.md` / 「复核报告 §七」引用它；本文件仅作为**可解析的落点**，不得据此评审、签字或判定放行。

## 原件内容摘要（历史，非现行口径）
- §一–§六：规划复核结论 —— 规划成立，但 §1 三处数字高估：`PlotKit/src/plotkit/server/app.py` 实际 23 路由（非 24）、`PlotKit/src/plotkit/backends/mpl_backend.py` 实际 52 个 `_draw_*`（非 60+）、`PlotKit/src/plotkit/__init__.py` 的 `__all__` 实际 31（非 32）；`ns_app.py` 用 `@router.` 非 `@app.`；451 是静态 `def test_` 计数而非 451 passed。
- §七 **需审批 / 复核 / 决策的 11 项**：① probe 三态改名 + `api_version` bump 2；② 删 `PUT /api/spec` / 新增 `PATCH /api/doc`；③ `cwd/layout.json` 兼容性；④ contrib 拆分 ns extra；⑤ TS/JS CI 生成 + `test:ui`；⑥ docs 29MB LFS；⑦ NetlabHome 并行基线重钉；⑧ `BENCHMARKS.md` 冲突 X10；⑨ `/to-spec` 接缝；⑩ `/to-tickets` 粒度；⑪ G0 判据 `451→470→>= 473 passed`。**这 11 项已由 `docs/PLOTKIT_P0_DECISIONS_2026-11-09.md`（裁定书，归档指针）§二逐项裁定**；执行结果与追加的「裁定书执行状态」段见 `docs/GOVERNANCE_SSOT_2026-11-10.md` §2/§3。
- §八 证据索引：`c563707` / `470 passed, 19 warnings in 51.34s` / `470 tests collected in 2.44s`、P1-9 grep 7 文件、「零命中的坏 grep 作废」教训 —— 均为**复核阶段历史点值**，现行基线见 `reports/test_baseline.json`（556）与 `docs/GOVERNANCE_SSOT_2026-11-10.md` §4。

## 引用解析
- 「复核报告 §七 第 9、10 项」→ `docs/specs/2026-11-09-p0-contract-freeze.md` 的接缝 / 粒度确认项；裁定结论见 `docs/GOVERNANCE_SSOT_2026-11-10.md` §3。
- 「复核报告（工作区根 `docs/`）」→ `docs/tickets/README.md:10` 已改注为「仓内归档指针，非原件」。

## 现行唯一口径
- `docs/GOVERNANCE_SSOT_2026-11-10.md`（闸门状态、放行判据、W-001 / W-002、权威替代映射）
- `docs/waivers.md`、`reports/*.json`、各阶段报告 `docs/N0..N6_*.md`
- 注意：§七第 11 项建议写入的 `>= 473 passed` 下限判据**已被裁定书 §二第 11 项否决**（X7 镜像漏洞），现行判据为 `collected == reports/test_baseline.json 的 pinned 常量` 的合取式，见 `GOVERNANCE_SSOT` §4。
