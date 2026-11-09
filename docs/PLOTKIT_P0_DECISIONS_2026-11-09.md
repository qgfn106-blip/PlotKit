# 归档指针（非原件）：PLOTKIT_P0_DECISIONS_2026-11-09.md

> ⚠️ **本文件不是原件，也不是原件的逐字恢复。** 原件是工作区根 `E:\Python\MyPython\ProjectPoint\docs\PLOTKIT_P0_DECISIONS_2026-11-09.md`（P0 复核审批决定书，25107B，sha256 `9c55daea…`，裁决时间 2026-11-09 10:19–10:2x GMT+8），于 2026-11-09 23:55 清理删除，**从未提交进 PlotKit 仓**。仓内历史文档以「裁定书 §二 第 N 项」「裁定书 §四」「裁定书 §一」引用它；本文件仅作为**可解析的落点**。
>
> 原件的**逐字副本仍存在于 dsh 附件**（在仓外，本轮不擅自恢复入仓以免重新引入过期数字）：`C:/Users/weijiewang/.dsh/attachments/v1/files/9c/9c55daeaae6d14cb7f546a7faf1202827bf4b728b8425e6d2e0bb2108e14d18a/PLOTKIT_P0_DECISIONS_2026-11-09.md`。是否恢复入仓属需用户裁定的决策项，见 `docs/GOVERNANCE_SSOT_2026-11-10.md` §5/§6。

## 原件内容摘要（历史裁定，结论仍有效）
- §一 三缺口 → **G0 不能签**：capabilities 混命名空间且随环境漂移、`migrate_legacy_layout()` 在 `src/` 零调用方、全部 P0 产物 UNTRACKED 且 Python CI 从未运行。Selector 是与实际渲染并行的第二套判断 → **G3 应为「不达成」**（骨架须标 `advisory_only: true`）。
- §二 11 项裁定：①**否决** probe 三态改名 / `api_version` bump 2；②**批准新增 PATCH、否决现在删** `PUT /api/spec`；③**批准切默认但判定未完工** → `get_layout()` lazy `migrate_legacy_layout()`（仅 `using_default`）；④**批准立项、G1 不具开工条件** → 只做 P1-0 测量；⑤前半**否决**（TS/JS 不入库会白屏）后半**批准**（`test:ui` 先定义）；⑥**批准编目→归档→LFS、否决直接删**；⑦批准 P4 重钉基线；⑧ `docs/bench_baseline.json` 唯一机器基线 + 删数字表 + `bench_regress.py --check`；⑨**必须动刀** 四字段拆分 + `capability.v1.json` 收紧 + `reports/decisions.json` 加 `environment`；⑩接缝与粒度复核通过附 3 修正、12 票入 `docs/tickets/`；⑪**否决 `>= 473 passed`** → `pytest exit 0 AND collected == 常量 AND failed == 0 AND skipped 显式 AND 门禁 violations == 0 AND reports 二次生成 sha256 不变`；`git add` 附 3 条件；tag 建在本轮 commit，禁止 rebase / force-push / amend / reset。
- §四 执行顺序（不得跳步）：1 修⑨ → 2 修③ → 3 修⑪ + ⑩工单 + 12 票入仓 → 4 `git add`+commit+tag + CI 首绿 → 5 ②设计评审 + ④P1-0 测量 → 6 ⑤/⑥/⑧ → 7 G1–G4 留白。

## 引用解析
- 「裁定书 §二② `:71-81`」→ `docs/decisions/2026-11-09-patch-api-design.md`（已 `status: decided` = 方案 B）+ `docs/N2_PATCH_DEFERRED_2026-11-09.md`。
- 「裁定书 §二⑤ `:125-133`」→ `docs/decisions/2026-11-09-test-ui-scope.md`（已 `status: decided`）+ `docs/N3_TEST_UI_2026-11-09.md`。
- 「裁定书 §二 11 项 / §四 执行顺序」→ `docs/REQUIREMENTS_AND_PROGRESS.md:85` D40、`docs/tickets/README.md:3`、spec 覆盖声明。
- 「N5 文档『裁定书 §一 指出』」→ 本文件 §一 + `docs/GOVERNANCE_SSOT_2026-11-10.md` §2（G3 仍不达成）。

## 现行唯一口径
- `docs/GOVERNANCE_SSOT_2026-11-10.md` §3/§4：11 项裁定的执行结果、W-001 / W-002、现行放行判据（判据中的「常量」= `reports/test_baseline.json` 的 pinned，数值不硬编码）。
- `docs/waivers.md`、`reports/test_baseline.json`、`docs/decisions/`、`docs/tickets/`。
