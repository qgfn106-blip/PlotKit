---
status: done
stage: N5（G3 单一决策点）
decision: 行为保持型薄适配（用户裁定）
date: 2026-11-10
evidence_head: d82870f
---

# N5 — G3 单一决策点（行为保持型薄适配）

## 1. 背景：G3 为何「不达成」

裁定书 §一 指出：`Selector` 是与实际渲染**并行**的第二套判断——`dispatch.choose()`
才是真实渲染决策点，`Selector` 只喂 `/api/capabilities` 与 `X-PlotKit-Decision` 响应头。
因此 G3 结论必须是「不达成／未签」，骨架须标 `advisory_only: true`。

计划 N5 要求：① `Decision` 增**显式** `advisory_only` 字段（不能只靠注释）；② 把
`dispatch.choose()` 收敛为 `Selector.select()` 的薄适配；③ 提供「响应头 / 实际调用后端 /
矩阵期望」三者一致对照测试。用户 2026-11-10 裁定采用**行为保持型薄适配**（风险低），
并明确 **G3 仍写「不达成／未签」**。

## 2. 本轮做了什么

- **`Decision` 增显式字段** `advisory_only: bool = False`，`to_dict()` 输出该键。
- **`decision_report()`** 每行矩阵结论 `decision` 显式带 `advisory_only=True`
  （骨架 advisory，供 `reports/decisions.json` 与 `/api/capabilities` 一致呈现）。
- **`Selector.select_backend(spec, requested=None) -> Decision`**：新增薄适配方法，
  内部委托 `dispatch._choose_impl`（既有选择算法），**不读任何环境变量**，返回统一
  `Decision`。这是后端选择的**唯一对外边界**。
- **`dispatch.choose()` 收敛为薄适配层**：原选择算法体改名为 `_choose_impl`（**不读环境
  变量**）；新 `choose()` 只做一件事——把 `PLOTKIT_BACKEND` 环境变量解析进 `requested`，
  再 `return Selector().select_backend(spec, requested).backend`。语义零变化。
- **新增 `tests/contract/test_decision_consistency.py`（10 用例）**：
  1) `choose(spec, requested) == select_backend(spec, requested).backend`（2D/3D ×
     None/mpl/auto 六组）；2) `Decision.to_header()` 的 backend == 决策 backend；
  3) `decision_report()` 每行 `advisory_only is True`；4) `select_backend` 在
     `PLOTKIT_BACKEND=pyvista` 下仍返回 mpl（证明 Selector 不读环境）；5) 未知后端
     `dispatch.choose` 与 `select_backend` 抛同一 `BackendUnavailable`。

## 3. 验证（本机，`cd PlotKit && export PYTHONPATH=src`）

- `python -m pytest -o addopts= --collect-only -q` → **556 tests collected**（原 546 + 10）。
- `python -m pytest -o addopts= -q --disable-warnings` → **556 passed, 19 warnings**。
- 门禁全绿：`check_test_baseline: profile=dev_full collected=556 pinned=556 passed=556
  failed=0 skipped=0 ok=True`；`check_layers: scanned=57 violations=0`；
  `check_capability_matrix: rows=8 violations=0`；`check_doc_sync: capability_rows=8
  violations=0`；`bench_regress: check=ok`；`record_update: entries=10 ok=True`。
- `reports/*.json` 二次生成 sha256 稳定（decisions 因新增 `advisory_only` 口径更新）；
  `reports/test_baseline.json` 两 profile 均 `collected=556`（dev skip 0 / ci_no_extras skip 29）。
- `flake8` 零命中；`black --check` 3 文件 unchanged。

## 4. 对闸门的影响

- **G3 仍「不达成／未签」**：本轮只把 `choose()` 收敛为 `Selector.select_backend()` 的
  薄适配并加显式 `advisory_only`；`RendererSelector.render` / hybrid3d / pyvista pool 等
  渲染路径**尚未证明全部经此单点**，能力矩阵尚未驱动真实后端切换。不得因 8 行矩阵与
  门禁全绿改口。
- 其余门（G0/G1/G2/G4）状态不变；G4 资产处置仍留白。

## 5. 下一阶段

- N6：跨仓契约诊断（NetlabHome `pyproject.toml:26` 与 `netlab/plotkit_bridge.py:122`
  硬编码 `plotkit>=0.2,<0.3`；单一主人未落地前不得宣称 C-4；X12 只诊断不改桥接）。
- G3 的真正收敛（矩阵驱动、全渲染路径经单点）作为后续独立议题。

## 6. 远端 CI 双绿证据（2026-11-10）

- 分支 `p1-single-decision @ 3942419`：`plotkit-python-tests` success（run 42660218487，
  run_number 18）、`plotkit-static-build` success（run 42660218477，run_number 23）。
- `main @ 3942419`：`plotkit-python-tests` success（run 42660599993，run_number 19）、
  `plotkit-static-build` success（run 42660600038，run_number 24）。
- 结论：`collected=556` 全量（含新增 10 条一致性契约）在远端无 extras 环境真跑通过；
  `npm run test:ui`/drift guard 通过；G3 仍「不达成／未签」（本轮仅薄适配，非全路径收敛）。

