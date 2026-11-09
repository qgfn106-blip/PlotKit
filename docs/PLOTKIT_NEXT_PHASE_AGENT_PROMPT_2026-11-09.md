# 归档指针（非原件）：PLOTKIT_NEXT_PHASE_AGENT_PROMPT_2026-11-09.md

> ⚠️ **本文件不是原件，也不是原件的逐字恢复。** 原件是工作区根 `E:\Python\MyPython\ProjectPoint\docs\PLOTKIT_NEXT_PHASE_AGENT_PROMPT_2026-11-09.md`（《PlotKit P0 冻结之后 —— 先拿远端首绿，再按闸门启动 P1–P5》任务计划，205 行 / 14130B，2026-11-09 17:24），于 2026-11-09 23:55 清理删除，**从未提交进 PlotKit 仓**。仓内 `docs/N0_REMOTE_FIRST_GREEN_2026-11-09.md:6` 以「NEXT_PHASE §0–§2」引用它；本文件仅作为**可解析的落点**。
>
> 原件的**逐字副本仍存在于 dsh 附件**（仓外）：`C:/Users/weijiewang/.dsh/attachments/v1/files/17/179648c28beede306fa8e4fe47b27d84fe4e00dd5b2091713b14a13564effcc8/PLOTKIT_NEXT_PHASE_AGENT_PROMPT_2026-11-09.md`。是否恢复入仓属需用户裁定的决策项，见 `docs/GOVERNANCE_SSOT_2026-11-10.md` §5/§6。

## 原件内容摘要（历史计划）
- §0 证据基线：P0 已提交但 `python-tests` 从未在 GitHub CI 真跑过；第一目标是把「本机全绿」变成「远端可复现的绿」，把所有破坏性动作锁在闸门之后。
- 阶段严格串行（前阶段未绿不得开下一阶段）：**N0 远端首绿**（唯一硬阻塞）→ **N1 contrib 拆分**（G1，根因 `PlotKit/src/plotkit/__init__.py:25 from . import field3d, ns`）→ **N2 PATCH /api/doc**（G2，先由用户裁定方案 A/B）→ **N3 test:ui**（前置 `app.ts` 六模块拆分）→ **N4 docs 资产**（`ASSET_INVENTORY` 102 行 / 29,930,760 字节全待裁定）→ **N5 G3 单一决策点**（`Decision` 加 `advisory_only:true`、`dispatch.choose()` → `Selector.select()` 薄适配）→ **N6 跨仓**（`NetlabHome/pyproject.toml:26` 与 `plotkit_bridge.py:122` 硬编码 `>=0.2,<0.3`）。
- 红线 X1–X12（要点）：X1 不自 push / 不改 `.git/config` / 代理 / 网络 / 不 rebase / force-push / amend / reset / 删移 tag，push 须用户对指定 HEAD 书面授权且不跨 HEAD 复用；X2 CI 首绿前 G0 不回填「达成」、不自签「评审通过」，G1/G2/G4 留白、G3「不达成」；X3 不改 probe 三态 / 不升 API_VERSION 2；X4 不删 `PUT /api/spec`；X5 不改 `src/plotkit/api/native.py`、optional 不并回 capabilities；X6 TS/JS 产物不移出 git、不删 committed `.js`；X7 不用 numstat / 测试数上升 / 本机全绿当放行判据、`collected==544` 不放宽成 `>=544`；X8 不放宽 schema、四字段不混用；X9 无脚本 / 硬件指纹不写性能数字；X10 不删 docs 资产 / 不改 `.gitattributes` / 不启用 LFS（除非单独审批且编目逐行标注）；X11 不事后补豁免、红线动作须事前写 `docs/waivers.md` 获批；X12 NetlabHome status 非空或与并行会话冲突时禁改 `plotkit_bridge.py`。
- 闸门表 G0–G4（7 列，禁代签）；自检六问；交付 = 每阶段报告（基线 → 命令全文 → 输出逐字 → 判据逐条 → 结论 → 遗留）+ `reports/` 可重放 JSON；不产出空脚本 / 无调用方 shim / 只写不验的性能数字。

## 引用解析
- 「NEXT_PHASE §0–§2 N0」→ `docs/N0_REMOTE_FIRST_GREEN_2026-11-09.md`。
- 阶段执行结果 → `docs/GOVERNANCE_SSOT_2026-11-10.md` §1/§2 + `docs/N0..N6_*.md` 各阶段报告。

## 现行唯一口径
- `docs/GOVERNANCE_SSOT_2026-11-10.md`：准确状态（「N0–N6 六阶段任务交付完毕、远端 CI 稳定双绿；G3 / C-4 / G4 未达成，签字表待签」）、G0–G4 / C-4 真实状态、需审批项清单。
- X1–X12 红线在本轮收口任务中仍逐条适用（尤其 X1 不 push、X10 不删资产、X11 不事后补豁免、X12 不碰 Netlab）。
