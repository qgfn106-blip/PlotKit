# 12: tests/contract|parity|render 三层 + 全量回归 + 文档同步 REQUIREMENTS_AND_PROGRESS.md + 签字表回填

**What to build:** 三层测试各守一个不变量且互不越界，`PlotKit/docs/REQUIREMENTS_AND_PROGRESS.md` 记下本轮 PK-R24 / D39，`docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` 的 G0 行由 lead 用捕获到的命令输出回填；本票只准备证据与占位，不代填任何数字。

**审批闸门:** 复核报告 §七 第 9 项（/to-spec 接缝确认）、第 10 项（/to-tickets 粒度确认）、第 11 项（G0 判据改为 collected 常量门禁，钉定常量见签字表 G0）与第 8 项（BENCHMARKS.md / bench_baseline.json 性能数字冲突裁定）须先裁定；未裁定前不得把 G0 结论标为 completed（计划 §10「空白格 = 未完成，不得标 completed」）。

**Blocked by:** 01（四份 JSON 契约 + 加载器）、02（FigureDocument）、03（0.1→v1 显式迁移 + 双向 golden）、04（Frame v1）、05（Selector/Decision）、06（capability.v1.json + 8 行矩阵）、07（compat_matrix.json + probe 追加键）、08（GET /api/doc）、09（GET /api/frame + X-PlotKit-Decision）、10（X3 UI 状态默认路径）、11（python-tests.yml + 三个门禁）
**Status:** ready-for-agent

- [ ] 建立 `tests/contract/`、`tests/parity/`、`tests/render/` 三层目录；`PlotKit/tools/` 现状无这三目录，本票纯新增。
- [ ] `tests/contract/` 唯一职责 = schema 校验 / 0.1→v1 版本迁移 golden / 能力矩阵 / Decision 可解释性；不测像素、不测耗时（计划 §9.1 :571-577）。
- [ ] `tests/parity/` 唯一职责 = 重构前后同一输入同一结果（SVG 结构哈希、AST 搬运等价）；不得用 `git diff --numstat` 增删差当等价判据（X7）。
- [ ] `tests/render/` 唯一职责 = 视觉回归（结构比对 + 像素容差）；不逐字节比 PNG、不做跨后端 bit-exact（X8）。
- [ ] 三层禁止交叉引用彼此的断言工具；既有 7 个 `read_text()` 文件是 legacy（P1-9 已 CONFIRMED），本票**不新增**源码字符串断言、不删既有测试（X8，复核报告 §三 P1-9）。
- [ ] `PlotKit/docs/REQUIREMENTS_AND_PROGRESS.md` 追加 PK-R24 / D39（既有最大编号 PK-R23 / D38），并按其 §1 头部约定「PlotKit 自己的需求、决策、计划、进度与经验全部在本文件」，不写进 netlab 的文档；每条数字带 `文件:行号` 或命令输出证据（CODE_STANDARDS §0）。
- [ ] 同步 `PlotKit/docs/specs/2026-11-09-p0-contract-freeze.md` 的 `## 实测` 保持为 lead 回填占位；本票不填数字、不冒充命令已跑。
- [ ] `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 行由 lead 回填 `命令全文` / `输出摘要` / `结论`；G1–G4 保持「未实施（本轮范围外，见复核报告 §六）」+「需审批」，不得改标。
- [ ] 本票不创建 `docs/waivers.md`、不写 `NetlabHome/` 任何文件（计划 §10 边界；复核报告 §六 裁定「不做不等于豁免」）。
- [ ] 全量回归 `cd PlotKit && python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（钉定常量见 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0，票面不写数字下限），`tsc --strict` 0 errors，`git diff --exit-code` 无产物漂移。

完工检测：三层目录各自 `pytest` 输出留命令留痕且无跨层引用；文档新增条目逐条可追溯到 `文件:行号` 或命令输出；签字表 G0 由 lead 回填后方可标结论；`cd PlotKit && python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`。
