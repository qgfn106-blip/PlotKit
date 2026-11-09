---
status: proposed
date: 2026-11-09
evidence_head: 1cf2570844c533cb2eb3ef44f352caa7d82fe764
ruling: docs/PLOTKIT_P0_DECISIONS_2026-11-09.md §二②
scope: 只设计、不实施、不接线、不造测试桩
---

# PATCH /api/doc 设计评审稿（②）

## 0. 状态与边界

- `status: proposed`：本文只是裁定书 §四第 5 步要求的「PATCH 设计评审稿」。
- 本轮**不实施**：不改 `src/plotkit/server/app.py`、不改 `src/plotkit/host_api.py`、
  不改 `pyproject.toml`、不改 `package.json`、不新增路由、不新增测试桩、不接线。
- **本轮不实施，先定写回 v0 还是 v1 需用户拍板**；在拍板前，任何写接口都不上线；
  裁定书 §二② 明确「不接受『先加写接口、存储模型以后再说』」。
- 依据：`docs/PLOTKIT_P0_DECISIONS_2026-11-09.md:71-81`（§二②）、
  `PlotKit/src/plotkit/server/app.py:246-261`、`PlotKit/src/plotkit/server/app.py:1143-1162`。

## 1. 现状事实（只读视图，不是文档存储）

- `GET /api/spec` 返回 `figure.spec`；`PUT /api/spec` 在
  `PlotKit/src/plotkit/server/app.py:246-261` 验证后直接赋值 `figure.spec = payload`，
  仍是 v0 spec 的写入口；裁定书 `:73` 称票 08 用 parity 测试锁住旧行为。
- `GET /api/doc` 在 `PlotKit/src/plotkit/server/app.py:1143-1162` 是
  `cls.migrate(figure.spec)` 的**现场迁移只读视图**：
  每次请求从 v0 `figure.spec` 现造一个 `FigureDocument` v1，
  `body` 用 `json.dumps(..., sort_keys=True, ensure_ascii=False)`，
  响应带 `ETag` 与 `X-PlotKit-Revision`。
- 因此当前**没有 v1 文档存储**；`figure.spec` 仍是唯一真相树。
  若 PATCH 直接把 ops 写回 v0 `figure.spec`，等于让 v1 视图和 v0 spec
  同时可写，重新制造 P0-1「双真相树」。这是 §二② 的**最硬前置**：
  **写回目标必须唯一**。

## 2. 协议草案（仅评审，不实施）

### 2.1 ops 白名单：精确 7 个

允许的 `ops[].op` 只有：

1. `set_page`
2. `set_axes`
3. `add_plot`
4. `remove_plot`
5. `move_layer`
6. `apply_theme`
7. `set_note`

**显式禁止** `replace_doc`：不允许客户端一次替换整份文档；
白名单外的 op 必须拒绝，不能静默忽略。这样把写面收敛到
`PageSpec` / `AxesSpec` / `PlotSpec` / `LayerSpec` / `ThemeRef` / `NoteSpec`
六种局部变更，避免暴露 `legacy`、整份 `extensions` 或任意 JSON patch。

### 2.2 请求与并发

请求体草案（只描述形状，不接线）：

```json
{
  "base_revision": 0,
  "ops": [
    {"op": "set_page", "path": "page.dpi", "value": 120}
  ]
}
```

- `base_revision` 必须等于服务端当前 `revision`。
- **不匹配 → HTTP 409**，响应体必须带 `current_revision` 与**冲突 op 索引**：

```json
{
  "ok": false,
  "error": "revision_conflict",
  "current_revision": 3,
  "conflict_op_index": 1
}
```

  索引是 `ops` 数组下标；实现时须在重放/预检阶段定位第一个使
  `base_revision` 失配的 op，而不是只回一个笼统 409。
- 成功时返回**新 revision**（不是返回整份文档）：

```json
{"ok": true, "revision": 4}
```

- 成功响应应同时刷新 `ETag` / `X-PlotKit-Revision` 语义；
  并发控制用 `FigureDocument.with_revision(n)` 或同类乐观并发助手，
  不允许就地改 frozen dataclass。
- 失败响应不得隐式落盘、不得部分写回：7 个 op 要么全成功，要么整体拒绝。

### 2.3 白名单与不可变约束

- 每个 op 先校验参数类型/范围，再构造新 `FigureDocument`；
  `layer.rect` 必须仍是 4 个 0..1 的数字，`link_to` 必须指向已有 layer index
  或为 `None`，notes/shapes id 保持唯一。
- `legacy` 与 `extensions` 不由 ops 直接改写：
  它们承载 v0 原样信封和未知字段，只能由迁移/存储层整体保留。
- `validate().ok` 必须为 True 才允许提交；错误以 `Report.errors` 形式返回，
  不抛异常到 HTTP 层。

## 3. 最硬前置：写回目标必须唯一

裁定书 §二② 给出两个可选方案（A：PATCH 直接写 v1 文档、`figure.spec`
降为派生视图；B：明确本节只做只读 PATCH、推迟到文档存储切换之后），并要求
列出各自代价与推荐。本文把 B 解释为「本节只保留只读 GET /api/doc，不开放写
PATCH」，因为「只读 PATCH」本身是矛盾措辞。两段下文按 A / B 展开。

### 方案 A：PATCH 直接写 v1 文档，`figure.spec` 降为派生视图

做法：引入唯一的 v1 文档存储（例如 `*.pkfig` 语义），
`GET /api/doc` 从该存储读；7 个 op 只改这份 v1 文档并递增 revision；
`figure.spec` 变成**只读派生视图**，由 `to_v0(doc)` 或等价反向投影生成，
`PUT /api/spec` 在保留期内要么只读代理到 v1 投影、要么明确标为兼容写入口，
但绝不重新成为第二个真相源。

代价：

- 必须一次性定义 v1 存储位置、加载/保存、迁移、revision 持久化、ETag 来源。
- 必须定义 `to_v0()` 派生规则：0.1 未知字段、`legacy`、`extensions` 如何保真；
  否则票 08 parity 会失去旧行为基线。
- 必须处理 `PUT /api/spec` 与 `PATCH /api/doc` 双入口并存期的写序：
  旧入口写 v0 时如何同步到 v1，否则仍是双写。
- 7 个 op 都要在 frozen dataclass 上实现，且要有等价 parity 测试；
  工作量与回归面都大。
- 这是**存储模型切换**，超出「纯新增 PATCH」的范围。

### 方案 B：明确本节只做只读、PATCH 推迟到文档存储切换之后

做法：本轮维持 `GET /api/doc` 为 `cls.migrate(figure.spec)` 的只读现场视图，
**不开放写 PATCH**；`PUT /api/spec` 保留；先把 v1 文档存储、
`figure.spec` 派生规则、legacy/extensions 保真、revision/ETag 语义
作为独立议题定稿并实现，之后再批准 PATCH 上线。

代价：

- 本阶段拿不到 op-based 编辑能力，前端 Inspector 仍不能通过 PATCH 写回。
- 票 08 的 parity 基线继续依赖 `PUT /api/spec`，旧行为回归面不变。
- 需要一次单独的「文档存储切换」审批，不能靠本文偷渡。

**推荐：方案 B。** 理由：裁定书 `:80` 明确「不接受『先加写接口、存储模型以后再说』」，
而当前 `GET /api/doc` 只是现场迁移视图；在 v1 存储与 `figure.spec` 派生规则
未定稿前，方案 A 会把存储切换和接口新增混在同一轮，违反「写回目标必须唯一」。
方案 B 把「先定写回 v0 还是 v1」留给用户拍板，风险最小，且不改变现有 outward behavior。
若用户拍板选 A，必须把上述存储/派生/双入口写序/parity 全部纳入同一次审批，
不能只落一个 PATCH 路由。

## 4. `PUT /api/spec` 保留期内不删

- `PUT /api/spec` 是旧行为回归基线；裁定书 §四⑩要求票 08 措辞改成
  「保留期内不得删除」，票 08 parity 依赖它。
- **本轮不删、下轮也不得顺手删**。顺序必须是：

  1. PATCH 上线（且写回目标已唯一、方案 A 前置全部完成）；
  2. `PUT /api/spec` 与 `PATCH /api/doc` **双入口并存观察一个发布周期**；
  3. 单独审批删除 `PUT /api/spec`，同时把 parity 测试改成对新接口的等价测试。

- 并存观察期内若仍允许 `PUT /api/spec` 直接写 `figure.spec`，
  必须显式定义它与 v1 存储的同步/拒绝策略；否则视为未满足「写回目标必须唯一」。

## 5. 本轮交付边界

- 本文标 `status: proposed`，**不接线、不造测试桩、不改任何现有文件**。
- 不运行全量 pytest，不新增 `tests/**`，不改 `server/app.py` / `host_api.py`
  / `package.json` / `.github/**` / `tools/**` / `docs/specs/**`。
- 待用户拍板「写回 v0 还是 v1」并复核本评审稿后，才进入实施票；
  实施票须自带 7 个白名单 op 的行为测试、409 冲突索引测试、
  `replace_doc` 拒绝测试、成功 revision/ETag 测试、双入口 parity 测试。
