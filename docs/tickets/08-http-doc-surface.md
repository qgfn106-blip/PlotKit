# 08: GET /api/doc + ETag + X-PlotKit-Revision（纯只读；PATCH /api/doc 本轮 deferred）

**What to build:** 调用方能用只读端点拿到版本化的 FigureDocument v1 表示（`ETag` + `X-PlotKit-Revision`），并保留一条「按 ops 白名单增量改文档」的设计路径；整份覆盖的 `PUT /api/spec` 一条不动，旧调用方零迁移成本。三个纯只读路由 `GET /api/capabilities`、`GET /api/doc`、`GET /api/frame` 同源读取契约声明。

**审批闸门:** 复核报告 §七 第 2 项（删除 `PUT /api/spec` 的影响面与迁移路径）与 §七 第 9 项（/to-spec 接缝确认）须先裁定；`PATCH /api/doc` + `base_revision` 失配 409 + ops 白名单属**本轮未实施（deferred）**，不得当作已交付能力（计划 §8 P2；CODE_STANDARDS §0 只许等价改进）。本票交付的只是纯只读路由与响应头，不新增任何写接口。

**Blocked by:** 02（FigureDocument frozen dataclasses + strict from_dict/migrate/validate + Report）、03（0.1→v1 显式迁移 + 双向 golden + 3 fixtures + X9 不删旧字段）
**Status:** ready-for-agent

- [ ] 新增只读 `GET /api/doc`，返回 FigureDocument v1 的可序列化形式；`ETag` 与 `X-PlotKit-Revision` 响应头取同一 revision 值（与 `src/plotkit/server/app.py:956-1009` `GET /api/render` 的 ETag 习惯一致）；`If-None-Match` 命中返回 304。
- [ ] `PUT /api/spec`（`src/plotkit/server/app.py:232-247`，整份 `figure.spec = payload`）**不改动、不删除、不重定向**；无 revision 之外并发控制的现状保持。
- [ ] `src/plotkit/server/app.py:182-188` `def create_app(figure, *, title=None, layout_path=None, with_ns=False)` 签名不变；新增只读路由不改变既有 23 个 `@app.(get|put|post)` 的行为。
- [ ] `PATCH /api/doc` 的 `ops` 白名单、`base_revision` 乐观并发、失配返回 409 **本轮未实施（deferred）**，不接线、不造测试桩谎报「已实现」；见审批闸门。
- [ ] 未知字段按 `src/plotkit/spec/model.py` 头注释「未知字段一律保留（前向兼容）」进入 `extensions`，不丢弃；`spec_version="0.1"`（`src/plotkit/spec/model.py:15`）旧文档仍可由 03 的迁移器读出。
- [ ] `src/plotkit/spec/validate.py:163` KNOWN_VIEW_KEYS / `:183` KNOWN_STYLE_KEYS / `:255` KNOWN_FIGURE_KEYS / `:272` `KNOWN_TOP_KEYS = {"spec_version","figure","layers"}` 四组白名单保持对外校验行为不变。
- [ ] 契约层测试放 `tests/contract/`，只断言端点响应体、ETag、响应头与旧端点不变；不读源码做字符串断言（X8）。
- [ ] 前端 `/api/` 调用走 `api()` helper，失败态 / 空态 / 未挂载态分开（`NetlabHome/netlab/docs/AGENT_GUIDE.md` §1.1）。
- [ ] 旧基线不退化：`python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（最终钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准）。

完工检测：`GET /api/doc` 的 ETag 与 `X-PlotKit-Revision` 逐请求一致并留命令输出；保留期内不得删除 `PUT /api/spec`；删除须 `PATCH /api/doc` 上线 + 双入口并存观察一个发布周期后单独审批；deferred 的 PATCH 项在票面上显式标注未实施、不得谎报；`cd PlotKit && python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`。
