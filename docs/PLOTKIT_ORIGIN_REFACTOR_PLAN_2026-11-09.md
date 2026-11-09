# 归档指针（非原件）：PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md

> ⚠️ **本文件不是原件，也不是原件的逐字恢复。** 原件是工作区根 `E:\Python\MyPython\ProjectPoint\docs\PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md`（P0 起源重构规划，约 47118B），于 2026-11-09 23:55 清理删除，**从未提交进 PlotKit 仓**，当前不可逐字恢复（`.workbuddy/backup/docs-20261109-2355/` 备份目录亦已删除）。仓内多处历史文档以 `docs/PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md` 引用它；本文件仅作为**可解析的落点**，不得据此评审、签字或判定放行。

## 原件内容摘要（历史，非现行口径）
- §1–§3：复核取证（`server/app.py` 路由数、`mpl_backend.py` 的 `_draw_*` 数、`__init__.py` 的 `__all__` 数量、451 静态 `def test_` 计数等）。逐项核对值见 `docs/PLOTKIT_ORIGIN_REFACTOR_REVIEW_2026-11-09.md`（归档指针）与 `docs/GOVERNANCE_SSOT_2026-11-10.md`。
- §7.5 / §8 P0：契约冻结范围 —— 四份 JSON 契约、`FigureDocument` v1 双向 golden、`Frame` v1 wire、`Selector` 骨架、三层测试、CI 门禁。规格定稿见 `docs/specs/2026-11-09-p0-contract-freeze.md`；12 张工单见 `docs/tickets/`。
- §10 X1–X10：P0 红线（只做等价改进与纯新增、不删能力、不破坏对外行为、不吞产物等）。

## 引用解析
- 「PLAN §8 P0」→ `docs/specs/2026-11-09-p0-contract-freeze.md` + `docs/tickets/`
- 「PLAN §7.5 `:527-543`」→ `docs/decisions/2026-11-09-test-ui-scope.md`
- 两处**用户原话逐字引用**（`docs/REQUIREMENTS_AND_PROGRESS.md:39` 的 PK-R24 行、`docs/specs/2026-11-09-p0-contract-freeze.md:17`）保留原文不改写；其中 `@docs\PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md` 是用户当时输入的路径，属历史记录，本指针文件使其在仓内可解析。

## 现行唯一口径（以这些为准）
- `docs/GOVERNANCE_SSOT_2026-11-10.md` —— 准确状态、G0–G4 / C-4 闸门、W-001 / W-002、现行放行判据、五份治理文档权威替代映射。
- `reports/test_baseline.json` —— pinned 常量唯一来源；`reports/*.json` —— 机器证据。
- `docs/N0_REMOTE_FIRST_GREEN_2026-11-09.md` … `docs/N6_CROSS_REPO_CONTRACT_2026-11-10.md` —— 各阶段交付报告。
- 本文件所有「现行状态」表述一律以 `GOVERNANCE_SSOT` 为准；原件中 `>= 473 passed` / `470` / `473` / `544` 等数字均为历史点值，不是放行依据。
