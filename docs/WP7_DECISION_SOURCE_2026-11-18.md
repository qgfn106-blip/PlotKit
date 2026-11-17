---
status: active
stage: WP-7（G3 单一决策源 + PKF1 边界）
date: 2026-11-18
---

# WP-7 — 后端选择单一决策源

## 1. 变更

- `plotkit/backends/selector.py` 的 `Selector.select_backend(spec, requested)` 现在是后端选择
  算法的唯一权威实现：auto 的三维/可用性/图层支持回退、未知后端与不可用后端的异常语义都
  在此处；本方法仍不读任何环境变量。
- `plotkit/backends/dispatch.py` 不再保留第二份选择分支：`choose()` 只解析
  `PLOTKIT_BACKEND` 环境变量并调用 `Selector.select_backend(...).backend`；
  `_choose_impl()` 仅作为兼容入口委托同一方法。原有 `available()` / 后端常量 / 异常类型
  仍由 dispatch 提供给渲染执行层。
- 行为保持：`tests/contract/test_decision_consistency.py` 的 `choose == select_backend.backend`
  对照矩阵继续覆盖 2D/3D、None/mpl/auto、未知后端等路径。

## 2. 边界

G3 的「全渲染路径经单点」仍未证明：`RendererSelector.render` / hybrid3d / pyvista pool
等执行路径不在本次变更内，`Decision.advisory_only` 的矩阵语义保持不变。本次只消除
`dispatch` 与 `selector` 之间的双决策分支，为后续全路径收敛提供唯一实现源。

## 3. PKF1 边界与一致快照

- `plotkit/store/frame.py:decode_frame` 现在校验 schema、列名唯一且非空、offset/count 为整数、
  列区间连续、payload 尾部无多余字节、JSON 列元素数与 count 一致；不合法输入抛
  `ValueError`，不再产生截断或错位列。
- `DataStore.snapshot_columns(names)` 在 `DATA_LOCK` 内一次性复制多列值和 meta；
  `encode_frame_from_store` 优先使用该快照，避免逐列读取期间被并发 push 撕裂。无该方法
  的鸭子类型 store 回退旧路径。
- 回归：`tests/contract/test_frame_wire.py` 覆盖 5 类坏帧；`tests/contract/test_data_integrity.py`
  覆盖 20 万点大帧边界、trim 后 pyramid 缓存失效、并发 push 下的 t/v 一致快照。
