# 07: compat_matrix.json 单一来源 + probe 追加键且旧三态不变 + /api/capabilities

**What to build:** 宿主在启动时能从一处读到 PlotKit 的契约版本、能力清单与可选 extra；`probe()` 只追加键，不改三态字面值与 `api_version`，既有宿主与 `tests/test_host_api.py` 不断裂；新增只读 `/api/capabilities` 让 Web/CLI 侧拿到同一份清单。

**Blocked by:** 01（四份 JSON 契约 + 加载器）
**Status:** ready-for-agent

- [ ] `compat_matrix.json` 是 schema 版本 / 最小最大兼容版本 / extra 能力清单的**唯一**来源；`src/plotkit/host_api.py:19-20` `_MIN_VERSION=(0,2)` / `_MAX_VERSION=(0,3)` 与 `:17` `API_VERSION = "1"` 不再另写一份硬编码判据。
- [ ] `probe()` 保持 `src/plotkit/host_api.py:33-63` 现有返回键 `state` / `version` / `api_version` / `detail` 与三态 `available` / `missing` / `incompatible` 字面值不变（`tests/test_host_api.py:1`、`:13`、`:28`、`:37` 已断言）。
- [ ] 只**追加**键 `schema_versions`、`frame_schema_versions`、`capabilities`、`optional`、`compat`，取值来自 `compat_matrix.json`；旧调用方按字典读取不受影响。
- [ ] 计划 §4.7 的 `state: available|incompatible|unavailable` + `api_version: 2` 是破坏性契约变更，**本票不实施**（见复核报告 §七 第 1 项）。
- [ ] 不在 NetlabHome 侧补 `probe()` 第三态；兼容矩阵与 schema 版本的唯一主人在 PlotKit（X5）。本票不写 `NetlabHome/` 任何文件。
- [ ] 新增只读 `GET /api/capabilities`，返回与 `probe().capabilities` 同源数据；不改 `src/plotkit/server/app.py:232-247` 的 GET/PUT `/api/spec` 与 `:935`/`:942` 的 GET/PUT `/api/layout`。
- [ ] `/api/` 前端调用一律走 `api()` helper 并区分失败态 / 空态 / 未挂载态（`NetlabHome/netlab/docs/AGENT_GUIDE.md` §1.1）。
- [ ] `PlotKit/pyproject.toml` 的 extras 清单（web / desktop / three / metrics / dev / all / server / mpl）驱动 `optional` 键；`ns` extra 不存在，不得伪造其可用性。
- [ ] 测试用行为断言验证三态字面值、追加键取值与端点输出一致；不新增源码字符串断言（X8）。
- [ ] 旧基线不退化：`python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（最终钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准）。

完工检测：`tests/test_host_api.py` 三条三态断言全绿；`grep` 机检 `probe()` 三态字面值未变；`GET /api/capabilities` 与 `probe().capabilities` 逐键相等留命令输出；`cd PlotKit && python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`。
