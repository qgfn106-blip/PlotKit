# P0 工单（12 张）

本目录是 12 张 P0 契约冻结工单**唯一权威（canonical）位置**。依 `docs/PLOTKIT_P0_DECISIONS_2026-11-09.md` ⑩ 裁定，工单由仓外移入仓内，随 PlotKit 一起版本化、可评审、可机检。

## canonical 位置

- 权威：`PlotKit/docs/tickets/01..12-*.md`（本目录，12 张）
- 索引：`PlotKit/docs/tickets/README.md`（本文件）
- 来源规格：`PlotKit/docs/specs/2026-11-09-p0-contract-freeze.md`
- 复核报告：`docs/PLOTKIT_ORIGIN_REFACTOR_REVIEW_2026-11-09.md`（`PlotKit/docs/` 同名归档指针，非原件；现行口径见 `docs/GOVERNANCE_SSOT_2026-11-10.md`）
- 签字表：`docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md`（`PlotKit/docs/` 同名归档指针，非原件；现行口径见 `docs/GOVERNANCE_SSOT_2026-11-10.md`）
- 裁定书：`docs/PLOTKIT_P0_DECISIONS_2026-11-09.md`（`PlotKit/docs/` 同名归档指针，非原件；现行口径见 `docs/GOVERNANCE_SSOT_2026-11-10.md`）

## 非权威归档

`E:/Python/MyPython/ProjectPoint/.scratch/plotkit-origin-refactor/issues/` 下的 12 张同名票是**入仓前的非权威归档副本**，不是权威来源，不得据此评审、改状态或引用；两处内容若出现差异，一律以本目录为准。该 `.scratch` 目录不随本仓库提交。

## 工单清单与依赖

| 编号 | 文件 | 标题要点 | Blocked by |
|---|---|---|---|
| 01 | `01-schema-contracts.md` | 四份 JSON 契约 + 加载器 + L0 纯标准库 | None（可立即开工） |
| 02 | `02-figure-document.md` | FigureDocument frozen dataclasses | 01 |
| 03 | `03-migrate-golden.md` | 0.1→v1 显式迁移 + 双向 golden | 01、02 |
| 04 | `04-frame-wire.md` | Frame v1 encode/decode + golden vector | 01 |
| 05 | `05-selector-decision.md` | RenderTarget/Decision/Backend Protocol + 8 行矩阵 | 01 |
| 06 | `06-capability-matrix.md` | capability.v1.json + 8 行机器可读矩阵 | 01、05 |
| 07 | `07-host-probe-compat.md` | compat_matrix.json + probe 追加键 | 01 |
| 08 | `08-http-doc-surface.md` | GET /api/doc + ETag + X-PlotKit-Revision（纯只读） | 02、03 |
| 09 | `09-http-frame-and-decision-header.md` | GET /api/frame + X-PlotKit-Decision | 04 |
| 10 | `10-ui-state-path.md` | X3 UI 状态默认路径（审批闸门） | 01、07 |
| 11 | `11-ci-and-tools.md` | python-tests.yml + 三个门禁 + 报告 | 07、08、09 |
| 12 | `12-three-layer-tests-and-doc-sync.md` | 三层测试 + 全量回归 + 文档同步（审批闸门） | 全部前序 |

## 三条统一修正（裁定 ⑩）

1. 「完工检测」判据不含任何数字下限：`pytest exit 0 且 collected == reports/test_baseline.json 的 pinned 常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`；pinned 常量以 `reports/test_baseline.json` 的 `collected` 为唯一来源（数值不在票面 / 文档写死），合法增量见 `docs/waivers.md` W-002，现行口径见 `docs/GOVERNANCE_SSOT_2026-11-10.md` §4。
2. 票 08：保留期内不得删除 `PUT /api/spec`；删除须 `PATCH /api/doc` 上线 + 双入口并存观察一个发布周期后单独审批。
3. 票 10：补三条 legacy 迁移接线验收（首次 GET 返回旧内容、目标已存在不覆盖、写入后 cwd legacy 字节不变）。

## 格式约定

每张票固定结构：`# NN: <title>` / `**What to build:**` / `**Blocked by:**` / `**Status:** ready-for-agent` / `- [ ]` 验收项 / `完工检测：...`；需审批的票另带 `**审批闸门:**` 行。状态变更须由 lead 依据签字表回填，票面不代填结论或数字。
