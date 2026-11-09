# 10: X3: UI 状态默认路径显式注入或用户配置目录，Path.cwd()/layout.json 不再作默认；需兼容既有 layout_path 参数

**What to build:** 在 A、B 两个不同工作目录启动同一份 PlotKit，UI 状态（面板位置、主题偏好）保持一致；文档落点由显式注入或用户配置目录决定，不再随 cwd 漂移，而已经传了 `layout_path` 的既有调用方行为不变。

**审批闸门:** 复核报告 §七 第 3 项（`Path.cwd()/layout.json` 默认落点迁移到用户配置目录对既有用户的兼容性）须先裁定；本票在裁定前只做「显式注入 + 用户配置目录」的新路径，不得单方面删除或重定向 `layout_path` 的既有语义。

**Blocked by:** 01（四份 JSON 契约 + 加载器）、07（compat_matrix.json 单一来源 + probe 追加键且旧三态不变 + /api/capabilities）
**Status:** ready-for-agent

- [ ] `src/plotkit/server/app.py:933` `layout_file = Path(layout_path) if layout_path else Path.cwd() / "layout.json"` 中 `Path.cwd()` 分支不再作为**默认**落点（X3）；默认改为用户配置目录（如 `~/.config/plotkit/ui.json`）或要求显式 `ui_state_path`。
- [ ] `src/plotkit/server/app.py:182-188` `def create_app(figure, *, title=None, layout_path=None, with_ns=False)` 与 `src/plotkit/host_api.py:66-76` `create_server(...)` 的既有 `layout_path` 参数保持可传入、语义不变；本票纯新增另一入口，不改签名（CODE_STANDARDS §0 等价性要求）。
- [ ] `src/plotkit/server/app.py:935` / `:942` GET/PUT `/api/layout` 对外行为不变；`probe()` 的 `optional` 追加键（07）声明 `ui_state_path`，宿主不另写一份路径判据（X5）。
- [ ] 文档 `FigureDocument` 与偏好 `UiState` 分离：`*.pkfig` 随工程，`UiState` 不随工程（计划 §7.4 :520-525）。
- [ ] A/B cwd 行为测试：同一用户配置目录下，在 A、B 两个 cwd 起服务，`GET /api/layout` 返回同一份状态；`pk.save()` 产物在另一 cwd `pk.load()` 后布局一致（G2 前置，但本票只产行为证据，不宣称 G2 达成）。
- [ ] 用户配置目录不存在时创建路径并给出可诊断的错误信息，不静默回退到 `Path.cwd()`；不因目录权限失败而崩服务。
- [ ] 迁移兼容性（审批闸门）：既有用户在 cwd 下已有 `layout.json` 时，需有明确的一次性读取/迁移策略，**未经裁定不得自动删除或忽略**该文件。
- [ ] legacy 迁移接线（一）：cwd 下 legacy `layout.json` 存在、用户配置目录目标文件不存在时，首次 `GET /api/layout` 返回 legacy 文件的旧内容，并留命令输出。
- [ ] legacy 迁移接线（二）：用户配置目录目标文件已存在时不覆盖既有目标文件（其字节不变），legacy 与既有语义均不被改写。
- [ ] legacy 迁移接线（三）：向新路径写入 UI 状态后，cwd 下 legacy `layout.json` 文件字节不变（迁移非破坏性，X3）。
- [ ] 契约层测试放 `tests/contract/`，用临时目录 + 显式路径注入做行为断言；不读源码字符串、不做精确耗时断言（X8）。
- [ ] 旧基线不退化：`python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（最终钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准）。

完工检测：A/B 双 cwd 的 `GET /api/layout` 输出逐字段相等并留命令输出；`grep` 机检默认分支不再出现 `Path.cwd() / "layout.json"`；既有 `layout_path` 传参的 parity 测试全绿；`cd PlotKit && python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`。
