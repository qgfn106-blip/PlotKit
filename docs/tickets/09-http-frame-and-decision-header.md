# 09: GET /api/frame + X-PlotKit-Decision 响应头，纯新增

**What to build:** 流式/增量渲染的调用方拿到一份带版本列的 Frame v1 字节流，并从响应头读到「本次为什么选这个后端」的可机检解释；降级绝不静默，旧 `/api/render` / `/api/anim` / `/api/png` 一个字节不改。

**Blocked by:** 01（四份 JSON 契约 + 加载器）、04（Frame v1 encode_frame/decode_frame + golden vector + 并发 1000 次）、05（RenderTarget/Decision/Backend Protocol + 8 行能力矩阵 + select() 唯一决策点 + X6）
**Status:** ready-for-agent

- [ ] 新增只读 `GET /api/frame`，响应体由 04 的 `encode_frame()` 产出，帧头 `src/plotkit/server/app.py:38` `MAGIC = b"PK01"` 与 `:41-52` `_binary_xyz()` 的现有字节布局不变（X2 要等价留痕）。
- [ ] 新增 `X-PlotKit-Decision` 响应头，内容取自 05 的可序列化 `Decision`：至少含 `backend` / `degraded` / `capabilities_used` / `reason`；`degraded=True` 时头部必须可观测，禁止静默降级（G3 前置）。
- [ ] `Selector.select()` 是本路由唯一的状况判断点，环境变量只允许覆盖 `policy`（X6）；调试指定后端名必须带 `degraded=True`。
- [ ] `src/plotkit/server/app.py:956-1009` `GET /api/render` 的既有响应头 `X-PlotKit-Backend` / `X-PlotKit-Xlim` / `X-PlotKit-Ylim` 与按 `figure.revision` 取 ETag 的行为保持不变。
- [ ] `src/plotkit/server/app.py:1027` `/api/anim`、`:1069` `/api/png` 不改；不删隐式双路（P3 属 Out of Scope，见复核报告 §六）。
- [ ] 并发 push/render 1000 次下响应帧列数、列长、`ColumnStore.version` 一致；断言值相等而非耗时阈值（X8）。
- [ ] 决策解释只有一处：不新增第二份人可读 reason 生成逻辑；`Decision` 可写进 06 的 `reports/decisions.json`。
- [ ] 前端 `/api/` 调用走 `api()` helper（`NetlabHome/netlab/docs/AGENT_GUIDE.md` §1.1）；契约层测试放 `tests/contract/`，等价层放 `tests/parity/`。
- [ ] 旧基线不退化：`python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（最终钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准）。

完工检测：`GET /api/frame` 字节与 04 golden vector 一致；8 行矩阵各留一条 `X-PlotKit-Decision` 输出（含 `degraded=True` 样例）的命令留痕；`cd PlotKit && python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`。
