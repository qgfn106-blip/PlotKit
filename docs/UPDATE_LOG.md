# PlotKit 更新记录

每次 github 上传前运行 `python tools/record_update.py --add --date ... --ref ... --summary ... --evidence ...`，滚动保留最近 10 条；CI 运行 `python tools/record_update.py --check`。

本表与 `PlotKit/README.md` 的 `<!-- UPDATE:LATEST:BEGIN -->` / `<!-- UPDATE:LATEST:END -->` 标记块联动：第 1 行的日期、版本/ref、更新内容、证据四字段须与标记块逐字一致。历史第 2–10 行取自实跑 `git -C PlotKit log --format='%h|%ad|%s' --date=short -n 12` 的最近 9 个提交，日期、短 sha、提交信息逐字照抄，未改写。

| # | 日期 | 版本/ref | 更新内容 | 证据 |
|---|---|---|---|---|
| 1 | 2026-11-09 | p0-freeze-2026-11-09 | P0 裁定书 11 项收口：capabilities 四字段拆分、X3 迁移接线、G0 collected 常量门禁、12 票入仓、README 更新记录机制、bench 数字表删除 | docs/specs/2026-11-09-p0-contract-freeze.md §实测 |
| 2 | 2026-11-09 | 1cf2570 | feat(host_api): probe 三态 + 性能声称标 unverified（严格审计 P0） | git -C PlotKit show 1cf2570 |
| 3 | 2026-11-08 | c563707 | feat(host-api): 最小稳定宿主接口 probe/create_server/PlotRenderPort | git -C PlotKit show c563707 |
| 4 | 2026-11-07 | 786c93a | docs: 复核更新 PlotKit 文档 + README 现状（D1-D38、470 基线、esbuild 产物） | git -C PlotKit show 786c93a |
| 5 | 2026-11-06 | 7f7f4c4 | style(p18): 清理 flake8 遗留并补配置（不改语义） | git -C PlotKit show 7f7f4c4 |
| 6 | 2026-11-06 | 8108c8c | docs: sync PlotKit docs to current architecture (TS/esbuild, 54 kinds, PEP8 done) | git -C PlotKit show 8108c8c |
| 7 | 2026-11-06 | f177ed5 | build(p17b): esbuild build for static TS->ESM JS; commit artifacts, lockfile, .nvmrc, CI drift guard | git -C PlotKit show f177ed5 |
| 8 | 2026-11-06 | 89040b5 | docs(plotkit): mark PK-R22 (TS migration) / PK-R23 (PEP8) completed | git -C PlotKit show 89040b5 |
| 9 | 2026-11-06 | 32587c4 | style(p18): apply black PEP8 formatting to PlotKit python (docstring normalization; no code semantics change) | git -C PlotKit show 32587c4 |
| 10 | 2026-11-06 | f18bbf6 | feat(p17): PlotKit frontend to native ES Modules (P17.2) | git -C PlotKit show f18bbf6 |

说明：第 1 行的版本/ref 是本轮冻结标签 `p0-freeze-2026-11-09`，不是已存在的 git commit；第 2–10 行是提交短 sha。新增记录由 `record_update.py --add` 插入第 1 行并裁掉第 11 行以后，编号由工具重排为 1..N 连续；本表手工落盘时已按 1..10 连续、日期非递增、无重复（日期, 更新内容）核对。
