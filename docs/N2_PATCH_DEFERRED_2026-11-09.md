---
status: decided
date: 2026-11-09
stage: N2 (G2)
decision: B（只读、推迟 PATCH）
evidence_head: b1f300cf3892c54b22aac7e13f8e98c8e80043c6
scope: 只落决策文档，不改代码/测试/接口
---

# N2 阶段报告：PATCH /api/doc 裁定为「方案 B（只读、推迟）」

## 1. 结论

用户 2026-11-09 拍板 **方案 B**：本轮**不开放写 PATCH**。

- `GET /api/doc` 维持 `cls.migrate(figure.spec)` 的**只读现场视图**（带 `ETag` / `X-PlotKit-Revision`）。
- `PUT /api/spec` 按既定保留策略**不删**（X4）。
- v1 文档存储、`to_v0()` 派生规则、`PUT /api/spec` 与 `PATCH /api/doc` 双入口写序，
  作为**独立议题另批**，不在本轮实施。

## 2. 依据

- `docs/PLOTKIT_P0_DECISIONS_2026-11-09.md` §二②（要求「写回 v0 还是 v1」由用户拍板，
  不接受「先加写接口、存储模型以后再说」）。
- `docs/decisions/2026-11-09-patch-api-design.md` §3 方案 A / B 代价对比 —— A 是存储模型切换
  （唯一 v1 存储 + 派生视图 + 双入口写序 + 7 op parity），工作量大、回归面大；B 风险最小、
  不改现有 outward behavior。该稿 `status` 已由 `proposed` 改为 `decided`，并在 §6 记录本裁定。

## 3. 本轮做了什么 / 没做什么

- **做**：把 `patch-api-design` 决策稿状态落为 `decided`（方案 B）；出本阶段报告。
- **没做（且不得顺手做）**：未新增 `PATCH /api/doc` 路由；未改 `src/plotkit/server/app.py`、
  `src/plotkit/host_api.py`；未删 `PUT /api/spec`；未改 `figure.spec` 为派生视图；
  未引入 v1 文档存储；未加任何写接口测试桩。

## 4. 对闸门的影响

- **G2（PATCH /api/doc）留白 / 不实施**，不因本轮推进而标记「达成」。
- 后续如需启动：须先单独审批「写回 v0 还是 v1」并完成 `patch-api-design` §2/§3 前置
  （写回目标唯一、7 个白名单 op 行为测试、409 冲突索引、`replace_doc` 拒绝、
  成功 revision/ETag、双入口 parity）。

## 5. 下一个阶段

按计划串行进入 **N3（test:ui）**，其前置为前端 `app.ts` 六模块拆分；届时另出 N3 阶段报告。
