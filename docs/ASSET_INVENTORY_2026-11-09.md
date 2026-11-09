# PlotKit docs/ 资产编目（2026-11-09）

本轮只编目：不删除、不移动、不改 `.gitattributes`、不启用 LFS；任何资产处置需单独审批。
> 2026-11-10 N4：按用户裁定完成**逐行标注**（决策证据 / 演示图 / 可归档候选），仍未做任何删除/迁移/LFS。

## 依据与范围

- 裁定：`docs/PLOTKIT_P0_DECISIONS_2026-11-09.md` ⑥「批准『编目 → 归档 → LFS/移出』，否决直接删，本轮不做」；第 1 步「先 `git ls-files docs/` 出全量清单，逐个标注『是否 D1–D38 / spec 的决策证据』；**未标注前不删任何 PNG**」。
- 清单命令全文：`git -C PlotKit ls-files docs/`（本表 102 行，全部为 tracked 文件）。
- 字节命令全文：`git -C PlotKit ls-files docs/ | while IFS= read -r f; do printf '%s|%s\n' "$f" "$(wc -c < "PlotKit/$f")"; done`，在仓库根 `E:/Python/MyPython/ProjectPoint` 执行；`wc -c` 取工作树当前字节。
- 汇总（实测，非编造）：tracked 文件 102 个，合计 `29930760` 字节；按扩展名 `76 png / 17 md / 2 svg / 2 json / 2 gif / 1 npy / 1 html / 1 gz`。
- 本表中 `docs/BENCHMARKS.md` 的 `2667` 字节是 ⑧ 数字表删除**改写后**的工作树字节；`docs/bench_baseline.json` 的 `2179` 字节是工作树当前值（该文件已被并行改动，属 lead / p0-gates 范围，本任务未碰）。
- 范围外：本轮新建且尚未 tracked 的 `docs/UPDATE_LOG.md`、`docs/tickets/`、`docs/decisions/`、`docs/specs/2026-11-09-p0-contract-freeze.md`、`docs/ASSET_INVENTORY_2026-11-09.md`（本文件自身）不在 `git ls-files docs/` 结果内，故不入表。
- 判定口径（2026-11-10 N4 更新，按用户裁定『仅逐行标注』）：`是否决策证据` 列——凡 `docs/adr/*.md`、`docs/DESIGN_v0.md`、`docs/REQUIREMENTS_AND_PROGRESS.md` 标「是」；其余标「否（技术文档/演示图/机器数据/归档包/生成物）」。`处置` 列——决策证据/技术文档/机器数据/生成物标「保留」；全部 `png/gif/svg` 演示图标「可归档候选（不删，需单独审批后处置）」。本轮**只标注、不删除、不移动、不改 `.gitattributes`、不启用 LFS**；任何实际处置（归档/LFS/移出）须另行单独审批。

## 全量清单

| 路径 | 字节 | 是否决策证据(D1–D39/spec) | 建议动作 |
|---|---|---|---|
| docs/BENCHMARKS.md | 2667 | 否（技术文档） | 保留（技术文档） |
| docs/DESIGN_v0.md | 27072 | 是（需求/决策台账） | 保留（决策证据） |
| docs/INSTALL.md | 5296 | 否（技术文档） | 保留（技术文档） |
| docs/NS_INTEGRATION.md | 8634 | 否（技术文档） | 保留（技术文档） |
| docs/NS_VORTEX.md | 25419 | 否（技术文档） | 保留（技术文档） |
| docs/REQUIREMENTS_AND_PROGRESS.md | 65875 | 是（需求/决策台账） | 保留（决策证据） |
| docs/THREE_D_BACKENDS.md | 19750 | 否（技术文档） | 保留（技术文档） |
| docs/WEB3D_LAYERS.md | 3361 | 否（技术文档） | 保留（技术文档） |
| docs/_lic_kind.png | 217326 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/_lic_test.png | 891592 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/_lic_tex.npy | 1692928 | 否（机器数据/工具输入） | 保留（机器数据） |
| docs/_quick.png | 34570 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/_vol_test.png | 50370 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/adr/0001-log-tau-timeline.md | 1436 | 是（ADR 决策记录） | 保留（决策证据） |
| docs/adr/0002-particles-similarity-and-probe.md | 1856 | 是（ADR 决策记录） | 保留（决策证据） |
| docs/adr/0003-solver-mode-b.md | 1820 | 是（ADR 决策记录） | 保留（决策证据） |
| docs/anim3d_demo.gif | 1473302 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/anim3d_frame.png | 72473 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/archive/plotkit-pre-plotview-2026-11-02.tar.gz | 619142 | 否（归档包） | 保留（既有归档包） |
| docs/axes3d_mpl.png | 113737 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/axes3d_pyvista.png | 44209 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/bench_baseline.json | 2179 | 否（机器数据/工具输入） | 保留（机器数据） |
| docs/browser_inset.png | 113959 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/browser_paper.png | 97909 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/crop_arrow.png | 5306 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/hybrid_3d.svg | 239845 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/hybrid_3d_preview.png | 165826 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/menus.png | 105806 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/netlab_docked.png | 86706 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/netlab_docked_crop.png | 54029 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/netlab_float.png | 84223 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/netlab_replay.png | 89127 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/netlab_tab.png | 94016 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_after_fix.png | 562082 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_arrows.png | 546524 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_blowup/01_blowup_law.png | 30396 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_blowup/02_ns_blowup_3d.gif | 672719 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_blowup/03_last_frame.svg | 78334 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_blowup/04_last_frame.png | 51481 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_blowup/README.md | 2687 | 否（技术文档） | 保留（技术文档） |
| docs/ns_clean.png | 559565 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_env_disk.png | 517752 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_gpu_a.png | 295298 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_gpu_a2.png | 295298 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_gpu_a3.png | 295298 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_gpu_b.png | 295298 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_gpu_e.png | 387944 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_lod_1000000.png | 797387 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_lod_120000.png | 777702 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_lod_500000.png | 789609 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_particles.png | 734942 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_particles_v2.png | 794282 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_phys_default.png | 751104 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_scale.json | 275 | 否（机器数据/工具输入） | 保留（机器数据） |
| docs/ns_scene.png | 632613 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_sim_t05.png | 564341 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_sim_t0995.png | 511424 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_std_0.5.png | 545659 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_std_0.9.png | 571673 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_std_0.99.png | 386775 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_streak.png | 315214 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_streamlines.png | 697475 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_t099.png | 500927 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_t0999.png | 473542 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_tone.png | 743539 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_trail_fix.png | 406662 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_ui_fix.png | 775526 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_vortex_demo.png | 357813 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_vortex_final.png | 507928 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_vortex_t000.png | 572031 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_vortex_t095.png | 558709 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/ns_vortex_top.png | 645286 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/p13_3d.png | 217003 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/p13_field.png | 325273 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/p13_gaps.png | 181532 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/p13_kinds.png | 95411 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/p13_render.png | 93158 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/p13_stats.png | 151292 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/p13_vector.png | 434031 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/panel.png | 102501 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/panel_crop.png | 85946 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/paper_panel_b.png | 146383 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/proto/README.md | 1821 | 否（技术文档） | 保留（技术文档） |
| docs/proto/shot-lines.png | 99869 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/proto/shot-points.png | 306630 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/proto/shot-surface.png | 281809 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/proto/webgl3d.html | 15360 | 否（生成物） | 保留（生成物） |
| docs/shot-light.png | 64566 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/shot.png | 62787 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/specs/2026-11-02-3d-field-and-batch-render.md | 14224 | 否（技术文档） | 保留（技术文档） |
| docs/specs/2026-11-02-quick-plot-and-3d-export.md | 4313 | 否（技术文档） | 保留（技术文档） |
| docs/specs/2026-11-02-r5-quick-time-idw-gpu.md | 4095 | 否（技术文档） | 保留（技术文档） |
| docs/specs/2026-11-03-canvas-free-layout-annotations.md | 11356 | 否（技术文档） | 保留（技术文档） |
| docs/three_d_dual_mpl.png | 109764 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/three_d_dual_pyvista.png | 40452 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/undo.png | 108812 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/vector_field/01_lic_slice.png | 750709 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/vector_field/02_volume_3d.png | 140157 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/web3d_volume.png | 96571 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/webgl_3d_deco.png | 187153 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/webgl_3d_demo.png | 140881 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |
| docs/webgl_3d_surface.png | 142021 | 否（演示图） | 可归档候选（不删，需单独审批后处置） |

## 备注（候选类别，均未批准、本轮不执行）

- ⑥ 第 2 步给出的候选处置类别：`.md` 留 `docs/`；图片走 LFS 或移仓外；历史规格与 `proto` 移 `docs/history/` 并标失效；一次性数值产物（`.npy`、重复 `ns_gpu_a*.png`）删除。以上均为后续单独审批的对象，本表不把任何一行标为「可删」。
- ⑥ 第 3 步把 G4 判据改写为「tracked 文本 < 1 MB + 二进制资产 100% 走 LFS 且有 `.gitattributes` 校验」；本表只提供逐文件字节证据，不声明该判据达成。
- ⑧ 相关：`docs/bench_baseline.json` 为唯一机器基线，`docs/BENCHMARKS.md` 已删数字表；两者的处置同样需单独审批。
- 本表所有「待裁定」即为 ⑥ 所要求的「标注」结果；未逐张 PNG 与 D1–D39 / spec 正文逐条比对前，不把任何 PNG 判为「非证据」。
