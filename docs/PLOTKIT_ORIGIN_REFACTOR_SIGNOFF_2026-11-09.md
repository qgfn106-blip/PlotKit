# 归档指针（非原件）：PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md

> ⚠️ **本文件不是原件，也不是原件的逐字恢复。** 原件是工作区根 `E:\Python\MyPython\ProjectPoint\docs\PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md`（P0 签字表，约 27398B，95 行），于 2026-11-09 23:55 清理删除，**从未提交进 PlotKit 仓**（`git log --all -- <该名>` 为空），当前不可逐字恢复。仓内 12 张工单与规格以「签字表 G0 钉定常量」/「签字表 G0 行」引用它；本文件仅作为**可解析的落点**，**不得据此代签闸门、回填「达成」或判定放行**（闸门 7 列禁代签，见 `docs/GOVERNANCE_SSOT_2026-11-10.md` §2/§6）。

## 原件内容摘要（历史，非现行口径）
- §0 钉桩：`c563707` / `470 passed`、`1cf2570` / `473 passed`、`116ec67`（P0 contract freeze，68 文件 +10454/−542）、轻量 tag `p0-freeze-2026-11-09`、additive `b45db0a`（规格覆盖声明）；未 push 原因 = 本机代理 `127.0.0.1:7897` 未开。
- §1 G0 证据（15 行命令 → 输出逐字）：`544 passed, 19 warnings in 56.13s`、`544 tests collected in 1.86s`、三层 `70 passed`、六门禁零 violations、三份 `reports/*.json` sha256、`files=30 black_rc=0 AST_EQUIV=OK`、前端三件套零漂移、reports 漂移闸门实证（rc 0→1→0）。**这些是 2026-11-09 当次历史实测点值**；现行 pinned=556，见 `reports/test_baseline.json` 与 `docs/waivers.md` W-002。
- §2 签字表 7 列（阶段 | HEAD | 命令全文 | 输出摘要 | 判据 | 结论 | 遗留）：G0 机器可判达成但「评审通过」签字与「CI 首次绿灯」待用户；**G3 = 不达成 / 未签**（Selector 是与实际渲染并行的第二套判断，`advisory_only: true` 未落地）；G1 / G2 / G4 留白。
- §3 X1–X10、§4 六问、§5 本轮交付与 11 项需审批项。

## 引用解析
- 12 张工单 `docs/tickets/01..12-*.md` 的「`collected == 签字表 G0 钉定常量` … 钉定常量见 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0」→ **现行 pinned 常量以 `reports/test_baseline.json` 的 `collected` 为唯一来源**，合法增量见 `docs/waivers.md` W-002；票面「不写数字下限」规则不变。
- 「签字表 G0 行 / 工作区根 `docs/`」→ `docs/GOVERNANCE_SSOT_2026-11-10.md` §2 闸门表 + §4 放行判据。

## 现行唯一口径
- `docs/GOVERNANCE_SSOT_2026-11-10.md`：准确状态、G0–G4 / C-4 真实状态、W-001 / W-002、现行放行判据。
- `docs/waivers.md`（W-001 已批准 / W-002 待追认）、`reports/test_baseline.json`、`reports/*.json`、远端 CI run `42662171282` / `42662171298`。
- **本指针不代签任何闸门**；G0「评审通过」签字仍待用户。
