---
status: decided
date: 2026-11-09
evidence_head: 1cf2570844c533cb2eb3ef44f352caa7d82fe764
ruling: docs/PLOTKIT_P0_DECISIONS_2026-11-09.md §二⑤
scope: 只定义、不实施、不接线、不造测试桩
---

# `test:ui` 测什么定义稿（⑤）

## 0. 状态与裁定边界

- `status: proposed`：本文只定义 `test:ui` 的被测对象、输入、不变量和断言方式。
- 本轮**不实施**：不改 `package.json`、不改 `.github/workflows/frontend-static-build.yml`、
  不改 `tests/**`、不改 `src/**`、不新增测试文件、不接线、不造测试桩。
- 裁定书 §二⑤ 前半**否决**「TS/JS 产物不入库」：维持 committed JS + drift guard；
  后半**批准**新增 `test:ui` 并接入前端工作流，但必须先定义它测什么。
- 依据：`docs/PLOTKIT_P0_DECISIONS_2026-11-09.md:125-133`（§二⑤）、
  `docs/PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md:527-543`（§7.5）、
  `PlotKit/.github/workflows/frontend-static-build.yml:29-40`、
  `PlotKit/package.json:9-14`。

## 1. 通用断言纪律

- **行为断言**：调用被测模块导出的纯函数 / 组件 API，比较返回对象、状态快照、
  集合内容、抛出的异常类型；允许比较 `Report.as_dict()` 的 `ok` / `errors` 结构，
  但不锁定自然语言错误文案的字面量。
- **禁源码字符串断言**：不 `read_text` / `read_bytes` 读 `.ts`、`.js`、`.py` 源码，
  不写 `assert "function buildFields" in source`，不 grep 源码；
  被测对象是运行中的 committed `.js` 产物或其导出的纯函数。
- **禁耗时硬阈值**：不用 `performance.now()`、`Date.now()` 差值、wall-clock、
  `setTimeout` 计时，不在 CI 设毫秒上限。`test:ui` 是行为回归，不是性能门禁。
- 不新增第三方依赖：Node >=20 内置 `node:test` + `node:assert/strict`；
  `npm run build` 已在前一步生成 committed ESM JS，`test:ui` 不负责构建。

## 2. 三个被测对象

裁定书 §二⑤ 原文给出三个被测对象：`UiState 序列化/还原`、
`Inspector 的 schema 驱动字段生成`、`布局 rect 归一化与链接轴`。
下文逐个写清输入、不变量与断言方式。

### 2.1 `UiState 序列化/还原`

- **输入**
  - 最小态：`{panelWidth: 380, sections: {}, expanded: [], groups: []}`
    （当前 `PlotKit/src/plotkit/static/app.ts:295` 的默认值）。
  - 丰富态：`panelWidth: 460`，`sections: {a: true, b: false}`，
    `expanded: ["L0", "L2"]`，
    `groups: [{id: "g1", name: "G", open: true, layerIds: ["L0", "L1"]}]`，
    以及未知键 `x_future: {"enabled": true}`（前向兼容）。
  - 畸形/缺省态：`null`、`{}`、`groups: null`、`expanded: "L0"`、
    `panelWidth: "wide"`；以及旧 `Path.cwd()/layout.json` 形状的 JSON 字符串。
  - 由测试注入临时 `ui_state_path`，不写用户目录、不依赖 `Path.cwd()`。
- **不变量**
  - `restore(serialize(state))` 与归一化后的 state 深度相等；连续两次
    round-trip 结果不变（幂等）。
  - 缺省字段补默认值；`groups` / `expanded` 必须是数组；
    `expanded` 的 `Set` ↔ 数组转换不丢元素、不重复；`panelWidth` 是有限数。
  - 未知前向兼容键必须保留；显式 `ui_state_path` 优先；
    legacy `layout.json` 只由显式一次性迁移触发，不在序列化/还原里隐式写 cwd。
  - 序列化输出确定性（键顺序稳定、UTF-8 无 BOM），输入对象不被原地修改。
- **断言方式**
  - 调用 §7.5 拆分后 `ui/state.js` 拟导出的 `serializeUiState` /
    `restoreUiState`（或等价纯函数），用 `assert.deepStrictEqual` 比较返回值；
    用冻结/深拷贝快照断言「输入未被修改」。
  - 对畸形输入断言「不抛异常 + 返回安全默认值」；对 `Set` 断言
    `Array.from(...)` 与输入数组相等。
  - 按通用纪律：仅行为断言，禁源码字符串断言、禁耗时硬阈值。

### 2.2 Inspector 的 schema 驱动字段生成

- **输入**
  - `figure.v1.json` 的 `$defs/page`、`$defs/axes`、`$defs/plot`、
    `$defs/theme_ref` 与 `properties` / `required` 片段，作为**数据**读入
    （不是读源码文本）。
  - 一个最小 `FigureDocument.to_dict()`；一个带 `extensions` 未知字段的 v1 文档。
  - 两个 schema 变体：给 `page` 增加一个可选字符串属性 `x_provenance`；
    从 `axes` 删除 `grid`。用于证明「字段来自 schema，不是硬编码」。
- **不变量**
  - 生成的字段描述符集合与所选 schema 片段的 `properties` / `required` /
    `type` / `$ref` / `enum` / `const` 一一对应；`$ref` 必须解析到 `$defs`。
  - schema 增加属性 → 描述符增加；schema 删除属性 → 描述符减少；
    `required` 标志、`const`、`enum` 选项随 schema 变化，而不是写死在 Inspector。
  - 文档里的未知字段进入 `extensions` 前向兼容袋，不被字段生成器丢弃；
    顶层未知字段按 `additionalProperties: false` 报告，不静默吞掉。
  - 生成/编辑动作只映射到 §二② 的 7 个白名单 op；**不生成 `replace_doc`**。
  - 描述符 id、顺序、默认值确定性；不依赖渲染耗时。
- **断言方式**
  - 调用 `ui/inspector.js` 拟导出的 `buildInspectorFields(schema, doc)`，
    用 `assert.deepStrictEqual` 比较描述符对象数组；用 schema 变体做前后差分断言。
  - 断言 `required` / `type` / `enum` 标志、生成 op 名称全部属于白名单、
    且 `replace_doc` 不在输出中；断言 `extensions` 原值保留。
  - 按通用纪律：仅行为断言，禁源码字符串断言、禁耗时硬阈值。

### 2.3 布局 `rect` 归一化与链接轴

- **输入**
  - 合法网格：`ncols=2, subplots=2`，
    `layout: [{slot:0, rect:[0,0,0.5,1]}, {slot:1, rect:[0.5,0,0.5,1]}]`。
  - 非法 rect：5 个数字 `[0,0,0.5,1,0.2]`、越界 `[-0.1,0,1.2,1]`、
    非数字 `["x",0,1,1]`、`NaN` / `Infinity`。
  - 链接轴：v0 `figure.link_x` 为 `true` / `false`；
    v1 `layers[].link_to` 为合法索引 `0`、越界 `9`、`None`；
    `AxesSpec.xscale` / `xlim` 组合。
  - 0.1 spec 的 `subplot` / `ncols` / `subplots` 与 v1 `LayerSpec.rect` / `link_to`。
- **不变量**
  - 每个归一化 `rect` 恰好 4 个有限数字且全部落在 0..1；等宽网格的
    `y` 从顶部起算（与 `migrate.py` 的 `_grid_rect` 一致），结果确定性。
  - `link_to` 必须指向已有 layer index 或为 `None`；`link_x=true` 时
    被链接层的 x 轴（`xscale` / `xlim`）一致，`false` 时不强制联动。
  - 非法 rect / 越界 `link_to` → `validate().ok === false`，
    `Report.errors` 含 `rect` / `0..1` / `link_to` 等结构化错误；
    `validate()` 永不抛异常。
  - 归一化与 `to_dict()` round-trip 不丢未知字段、不修改输入、不改 revision。
- **断言方式**
  - 调用 `normalizeRect` / `normalizeLayout` / `FigureDocument.validate` /
    `validate_document` 的行为结果，用 `assert.deepStrictEqual` 比较归一化数组；
    用 `report.as_dict()` 断言 `ok` 与 `errors` 结构（不锁定文案字面量）。
  - 断言链接层的 `xscale` / `xlim` 相等、非链接层不相等；
    断言 `link_to` 合法性；用深拷贝快照断言输入未被原地修改。
  - 按通用纪律：仅行为断言，禁源码字符串断言、禁耗时硬阈值。

## 3. 不接受先加空脚本

裁定书 §二⑤ 明写「**不接受先加空脚本**（`tests/test_perf.py` 零测试函数
就是前车之鉴）」；§二⑧ 也记录 `tests/test_perf.py` 零测试函数。空脚本
`exit 0` 但 `collected == 0` 等同没测，不能作为 `test:ui` 上线。

实施时最低验收：`test:ui` 必须实际收集并执行**至少 3 个真实测试函数**
（三个被测对象各 1 个）；显式列出三个测试文件，缺任一文件即 `exit 1`；
CI 把 `0 tests` / `0 passing` 视为失败。不得用 `echo ok`、`node -e ""`、
只放一个空 `describe()`、或复用 `test:utils` 的零收集壳来冒充。

本轮不实施、不造测试桩；只有定义稿，没有 `tests/ui/**` 文件。

## 4. 接入位置与最小脚本草案（只写文本，不改文件）

### 4.1 `frontend-static-build.yml` 位置

当前工作流：`PlotKit/.github/workflows/frontend-static-build.yml:23-24`
`npm run typecheck` → `:26-27` `npm run build` → `:29-30`
`Unit tests (pure utils)` / `npm run test:utils` → `:32-40`
`Artifact drift guard (committed JS must match a fresh build)`。

`test:ui` 应接在 **`npm run test:utils` 之后、drift guard 之前**：
它依赖 `npm run build` 已生成 committed JS 产物；drift guard 仍留在最后，
继续守 TS/JS 产物入库一致性。草案（只写文本，不改 `.github/**`）：

```yaml
      - name: UI behavior tests (state, inspector, layout)
        run: npm run test:ui
```

完整顺序草案：

```text
npm ci
→ npm run typecheck
→ npm run build
→ npm run test:utils
→ npm run test:ui
→ Artifact drift guard (committed JS must match a fresh build)
```

### 4.2 `package.json` 最小脚本草案

当前 `PlotKit/package.json:9-14` 只有 `build` / `typecheck` / `test:utils`，
没有 `test:ui`。草案（只写草案文本，**不改 `package.json`**）：

```json
{
  "scripts": {
    "test:ui": "node --test tests/ui/state.uitest.cjs tests/ui/inspector.uitest.cjs tests/ui/layout.uitest.cjs"
  }
}
```

说明：

- 用 Node >=20 内置 `node --test`，不新增依赖；`.uitest.cjs` 后缀避免被现有
  `test:utils` 的 `"tests/**/*.test.cjs"` glob 抢跑或重复收集。
- 显式列三个文件，避免 glob 零匹配时静默 `0 tests`；配合 §3 的
  `collected >= 3` 验收。
- 测试文件导入 committed `.js` 产物（§7.5 拆分后是 `ui/*.js`），
  不导入 `.ts` 源码，符合 zero-build / drift guard 口径。
- `test:ui` 不做构建、不设时间阈值、不改 `tsconfig.utils.json`。

## 5. 「双份 13990 行」的真正解法

裁定书 §二⑤ 以「双份 13990 行」描述现状，并明确：维持 committed JS +
drift guard，否决「TS/JS 产物不入库」；**双份 13990 行真正解法是计划
§7.5 拆 `app.ts` 为 6 个 ≤500 行模块**，让每对 TS/JS 都变小，而不是取消入库。

计划 §7.5 的 6 个模块：`ui/state.ts`（UiState、撤销栈、revision ≤400）、
`ui/document.ts`（FigureDocument 客户端模型 + PATCH ops ≤450）、
`ui/inspector.ts`（schema 驱动表单 ≤500）、
`ui/canvas.ts`（布局覆盖层 / 拖拽 / 吸附 / 批注 ≤500）、
`ui/datasets.ts`（数据集列表 / 批量加图层 ≤300）、
`ui/bootstrap.ts`（装配与事件总线 ≤250）；机检任一模块 >500 行 CI 失败，
模块间只能经 `state.ts` 通信。`makeLayerCard()` 里 150 行手写字段控件
全部由 `inspector.ts` 生成。

本轮 `p1_baseline.json` 实测：`static` 6 对 TS/JS 共 12624 行
（`app.ts=3042`、`app.js=2713`），全仓 18 个 TS/JS 共 13217 行；
与裁定书「13990」的数字差异不在此稿裁定。无论按哪组数字，
`test:ui` 的定义都只针对上述三个行为对象；把巨石拆小是 §7.5 的职责，
不是靠加空脚本或删 `.js` 产物解决。

## 6. 本轮边界

- 本文标 `status: proposed`，只定义 `test:ui` 测什么。
- 不实施、不接线、不造测试桩、不改 `package.json` / `.github/**` /
  `tests/**` / `src/**` / `docs/specs/**`；不运行全量 pytest。
- 后续实施票须先完成 §7.5 的模块拆分（或至少把三个纯函数导出到 committed JS），
  再带齐三个真实测试函数接入工作流；接入仍须单独审批。

## 6. 实施记录（2026-11-09，按方案 1 落地）

- **范围**：按 §6「或至少把三个纯函数导出到 committed JS」的退路实施（不做 3042 行 `app.ts`
  的六模块 ≤500 行大拆分，那留作独立后续）。
- **新增纯函数模块（committed JS + TS 源）**：
  - `src/plotkit/static/ui/state.ts` → `ui/state.js`：`normalizeLayout` / `clampPanelWidth` /
    `serializeLayout` / `restoreLayout`（UiState 序列化/还原）。
  - `src/plotkit/static/ui/inspector.ts` → `ui/inspector.js`：`kindChoices`（Inspector schema 驱动字段生成）。
  - `src/plotkit/static/ui/layout.ts` → `ui/layout.js`：`clampRect`（rect 像素归一化）/
    `normalizeGridRect`（0..1 网格 rect 校验）。
- **接线（行为保持）**：`app.ts` 的 `applyLayout` 用 `normalizeLayout`；`applyPanelWidth` 用
  `clampPanelWidth`；`makeLayerCard` 的图型选项用 `kindChoices`；`clampLayerWinRect` 用 `clampRect`。
  `app.ts` 净 diff 仅约 7+/15−，无行尾/空白假 diff。
- **测试**：新增 `tests/ui/{state,inspector,layout}.uitest.cjs`（node:test，导入 committed `.js`），
  共 7 个真实用例，覆盖三个被测对象；`npm run test:ui` = `node --test` 显式列三文件。
- **接线位置**：`package.json` 增 `test:ui`；`frontend-static-build.yml` 在 `test:utils` 之后、
  drift guard 之前加 `npm run test:ui`，并把 `ui/*.js` 纳入 drift guard 文件清单。
- **验证**：`npm run build` OK；`npm run typecheck` OK；`npm run test:ui` 7 pass / 0 fail；
  `npm run test:utils` 19 pass / 0 fail。
