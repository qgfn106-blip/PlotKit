---
status: implemented
date: 2026-11-09
关联: PK-R24, D39, docs/PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md §8 P0
---

# P0 契约冻结：四份 JSON 契约与纯新增纵切（2026-11-09）

- 状态：规格口径已定稿；本文件不宣称代码实施结果，见文末「实测」
- 来源：用户原话（见下，不改写）
- 关联：`PlotKit/docs/REQUIREMENTS_AND_PROGRESS.md`（PK-R24、D39 为本轮新分配编号，既有上限 PK-R23 / D38）、`docs/PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md` §8 P0

> **裁定书覆盖声明（2026-11-09 收口追加；2026-11-10 治理口径收口复修）**：`docs/PLOTKIT_P0_DECISIONS_2026-11-09.md` §二 第 11 项已**否决**本文正文（Problem Statement / Solution / User Story 20 / Testing Decisions / Further Notes）中出现的 `>= 473 passed` 放行判据（X7 镜像漏洞：测试数量上升本身不能当放行条件）。正文是 P0 第一轮 `/to-spec` 原始合成文本，**保留原样不改写以留痕**；其中一切 `>= 473 passed` / `>= 470 passed` / `451→470→473` 数字链均**不再作为放行依据**。**现行唯一放行判据**以 `docs/GOVERNANCE_SSOT_2026-11-10.md` §4 与 `PlotKit/reports/test_baseline.json` 的 `collected`（pinned 常量，数值只在该 JSON 维护、文档不写死；合法增量见 `docs/waivers.md` W-002）为准：`pytest exit 0 AND collected == pinned 常量 AND failed == 0 AND skipped 显式且与 profile 一致 AND 门禁 violations == 0 AND reports 二次生成 sha256 不变`。本文 §实测 中的 `544 passed` / `70 passed` / `collected=544` 等均为 2026-11-09 当次**历史实测点值**，不是现行 pinned 常量。正文中对签字表 / 裁定书 / 复核报告 / 计划 / 下一阶段计划等治理文档的引用，原件为工作区根 `docs/` 文档、已于 2026-11-09 23:55 清理删除、从未提交进 PlotKit 仓；现由 `PlotKit/docs/` 下**同名归档指针**（明确标注「非原件」）承接，46 处引用全部可解析并最终导向 `docs/GOVERNANCE_SSOT_2026-11-10.md`；仓内随 commit 冻结的机器证据是 `PlotKit/reports/*.json`；`/to-tickets` 12 张票已由 `.scratch/plotkit-origin-refactor/issues/` 移入 `PlotKit/docs/tickets/`。

## 用户原话（不改写）

> @docs\PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md 请就这个文档对plotkit项目进行复核，然后按照文档提出的规划进行代码优化 请遵守代码规范与文档规范 /to-spec /to-tickets 然后自行按照任务，开始完成任务，之间不要反复找我批准，只留下需要审批复核决策的操作

## Problem Statement

PlotKit 的图形内容、图页布局与 UI 状态分别长在三处互不知情的真相树上：`src/plotkit/spec/model.py:83-115` 的 `new_spec()` 返回裸 dict、`src/plotkit/server/app.py:933` 把 UI 状态默认落到 `Path.cwd() / "layout.json"`、前端另有一份 `clientRenderable()` 判断。字段形状同时被 `src/plotkit/spec/model.py:40-61` `default_style()`、`:64-80` `default_view()`、`src/plotkit/spec/validate.py:163/:183/:255/:272` 四组 `KNOWN_*_KEYS` 白名单与 presets 各写一遍；渲染选择散在 `src/plotkit/backends/dispatch.py:179-186` `_hybrid_3d(fmt)`、`src/plotkit/server/app.py:956-1009` 的 backend 传参、前端的 kind 判断三处。结果是：任何一处改动都没有可机检的契约可依，旧文件读回来是否等价、 capabilities 随 extra 变了什么、当前渲染为何选了这个后端，都无法从一份机器可读的单一来源回答。用户要的是按 `docs/PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md` 规划推进，但代码规范只允许「不改变对外行为」的等价改进，因此第一步必须是**先立规矩、不写功能**：把形状、版本、能力、兼容关系冻结成可被程序读取的单一来源，并证明旧的行为回归不退化——复核阶段 `c563707` = `470 passed, 19 warnings in 51.34s`；并行提交 `1cf2570` 新增 3 条 host_api 测试后本轮实施基线 = `473 passed, 19 warnings in 70.56s`；**放行判据为 `>= 473 passed`**，最终钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准，不硬编码 470 / 473。

## Solution

- 在契约层落地四份 JSON：`figure.v1.json`、`frame.v1.json`、`capability.v1.json`、`compat_matrix.json`，配一个只用标准库的加载器与带字段路径的校验报告；这四份是字段、版本、能力、兼容关系的唯一来源。
- 文档层给出 frozen `FigureDocument` 与其 `from_dict()` / `migrate()` / `validate()`：未知字段进 `extensions` 保留（前向兼容），0.1 旧 spec 有显式迁移入口与双向 golden，任何一份旧图都能读回且不丢字段（X9）。
- 数据层**新增** `Frame v1` 的 `encode_frame()` / `decode_frame()` 单一 wire 编码入口（`FRAME_MAGIC=b"PKF1"`）与固定 golden vector，配纯只读 `GET /api/frame`；`src/plotkit/server/app.py:38` `MAGIC = b"PK01"`、`:41-52` `_binary_xyz()` 等内联 struct 打包**原样保留、不收敛**（收敛到一处会改变既有 `/api/column` / `/api/xyz` 的对外字节，属计划 §8 P3，本轮 Out of Scope，见下方）；并发 wire 编码 1000 次列数与长度无不一致由三层测试断言。
- 策略层给出 `RenderTarget` / `Decision` / Backend Protocol 与 8 行能力矩阵；`select()` 是唯一决策点，环境变量只允许覆盖 `policy`，调试指定后端必须 `degraded=True`（X6）；`Decision` 可序列化，降级可观测。
- `probe()` 与 `compat_matrix.json` 接通但**不改名**三态、不 bump `api_version`；新增三个**纯只读**路由 `GET /api/capabilities`、`GET /api/doc`（带 ETag 与 `X-PlotKit-Revision` 响应头）、`GET /api/frame`，渲染响应追加 `X-PlotKit-Decision`；UI 状态默认路径改为显式注入或用户配置目录的纯新增路径（`Path.cwd()/layout.json` 的默认迁移本身属审批项，见复核报告 §七 第 3 项）。
- **本轮未实施（deferred，不得当作已交付）**：带 `base_revision` 的 `PATCH /api/doc` 与冲突返回 409 的乐观并发写入口。它改变对外写行为，属 Out of Scope / 审批项（复核报告 §七 第 2 项）；本轮只读 `GET /api/doc` 只用 ETag 与 `X-PlotKit-Revision` 暴露修订号，不新增任何写接口。
- 用 Python 测试工作流、三层测试目录与三个门禁工具把上述不变量变成 CI 可判的断言；放行判据为 `>= 473 passed`，最终钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准（不是 451 静态计数、也不是复核阶段的 470）。

## User Stories

1. 作为宿主集成方，我希望 `figure.v1.json` / `frame.v1.json` / `capability.v1.json` / `compat_matrix.json` 四份 JSON 可被纯标准库加载器读取并报出带字段路径的 Report，以便不安装第三方依赖就能判断一份文档是否合法。
2. 作为维护者，我希望字段形状只来自契约层、dataclasses 与 TS 类型都由它生成或校验，以便不再出现第三份手写字段表（复核报告 §三 P0-2）。
3. 作为多窗口集成方，我希望每个文档带单调递增的 `revision` 并可由 `X-PlotKit-Revision` 读出，以便 UI 能观察文档版本；`base_revision` 乐观并发写入属**未来 story（本轮未实施，见第 13 条）**。
4. 作为旧版用户，我希望 frozen `FigureDocument` 的 `strict from_dict()` 对未知字段给出可机检的拒绝或 `extensions` 归类，以便拼写错误不会被静默吞掉。
5. 作为旧版用户，我希望 `spec_version="0.1"` 的旧图有显式 `migrate_v0_to_v1()` 且 `extensions` 保留全部未知字段，以便前向兼容且不丢字段（X9）。
6. 作为发布负责人，我希望 0.1→v1→0.1 有 3 个 fixtures 的双向 golden 逐字段还原，以便迁移可逆、可机检。
7. 作为流式数据调用方，我希望 `Frame v1` 的 `encode_frame()` / `decode_frame()` 与固定 golden vector 逐字节往返一致，以便 wire 格式可复现。
8. 作为流式数据调用方，我希望并发 push/render 1000 次后列数与长度无不一致且 `ColumnStore.version` 单调，以便实时增量不撕裂。
9. 作为策略维护者，我希望 `RenderTarget` / `Decision` / Backend Protocol 与 8 行能力矩阵逐行对应、每行一条 select 断言，以便新增一种状况等于加一行加一条测试而不是加一个 if。
10. 作为运维，我希望环境变量只覆盖 `policy`、调试指定后端时 `Decision.degraded=True`，以便降级可观测且没有第二处状况判断（X6）。
11. 作为调用方，我希望 `Decision` 可序列化并写入 `reports/decisions.json`，以便「为什么选这个后端」有输出留痕。
12. 作为宿主集成方，我希望 `GET /api/doc` 带 ETag 与 `X-PlotKit-Revision` 响应头，以便 UI 能缓存文档并读到修订号；并发写冲突检测依赖 `PATCH /api/doc` + `base_revision`，**本轮未实施（见第 13 条）**。
13. **（未来 story，本轮未实施 / deferred）** 作为多窗口用户，我希望 `PATCH /api/doc` 带 `base_revision` 且失配返回 409，以便两个写者并发时后写者被明确拒绝而不是静默覆盖；该写入口改变对外行为，须先经复核报告 §七 第 2 项审批。
14. 作为宿主探测方，我希望 `probe()` 只**追加** `schema_versions` / `frame_schema_versions` / `capabilities` / `optional` / `compat` 五键且旧三态 `available/missing/incompatible` 不变，以便现有宿主不因探测结果改名而断连。
15. 作为宿主探测方，我希望 `compat_matrix.json` 是 schema 版本与能力声明的唯一主人，以便 netlab 侧不需要补第三种 `probe()` 状态（X5）。
16. **（未来 story，本轮未实施 / deferred）** 作为前端集成方，我希望带 `base_revision` 的 `PATCH /api/doc` 在 409 时返回当前文档与修订号，以便 UI 提示「文档已被其他窗口修改」；本轮只提供只读 ETag / `X-PlotKit-Revision`，不提供该写路径。
17. 作为渲染调用方，我希望 `GET /api/frame` 与 `X-PlotKit-Decision` 响应头纯新增、既有 `GET /api/render` 的 `X-PlotKit-Backend` / ETag 行为不变，以便旧调用方零改动。
18. 作为桌面用户，我希望 UI 状态可由显式注入的路径或用户配置目录读写、且既有 `layout_path` 参数继续有效，以便 A/B 两个 cwd 起服务时状态一致（X3；默认落点迁移的兼容性裁定见复核报告 §七 第 3 项）。
19. 作为发布负责人，我希望**新建独立** `.github/workflows/python-tests.yml`（跑全量 pytest、三层测试、三个门禁与 `reports/` 漂移守卫），配 `tools/check_layers.py` / `check_capability_matrix.py` / `check_doc_sync.py` / `generate_reports.py` 输出留痕，以便契约、层次、文档同步都可机检；**本轮不改**既有 `frontend-static-build.yml`、`package.json` 也未新增 `test:ui` 脚本——「前端工作流追加 `test:ui`」及 TS 产物改为 CI 生成不入库属计划 §9.3 / P5 的需审批项（复核报告 §七），本轮未实施。
20. 作为发布负责人，我希望放行判据写为 `>= 473 passed` 且最终钉定数由签字表 G0 回填，以便 `python -m pytest -o addopts= -q --disable-warnings` 的输出与该判据比对后放行 G0（不硬编码 470 / 473）。

## Implementation Decisions

- 本轮是**纯新增**：不改任何既有对外行为、不删任何入口、不改 `src/plotkit/backends/mpl_backend.py` 绘制语义；这是 `NetlabHome/netlab/docs/CODE_STANDARDS.md` §0「只允许等价改进」的直接结论，也是计划 §8 P0「先立规矩，不写功能」的落地。
- 契约层只允许标准库，且禁止 `import plotkit` 任何子模块；依赖方向单向向下，可由门禁脚本机检。
- 文档层只依赖契约层；四份 JSON 是字段、版本、能力、兼容关系的唯一来源，禁止再手写第三份字段表。
- legacy 用无损信封承载：`extensions` 保留未知字段，0.1 旧 spec 的 `spec_version` 与全部 figure 字段可往返还原，符合前向兼容与 X9。
- 修订号只读暴露：`GET /api/doc` 的 ETag 与 `X-PlotKit-Revision` 响应头对齐文档修订号。**乐观并发（`base_revision` / 409）本轮未实施**，属后续阶段且须审批（复核报告 §七 第 2 项）；本轮不新增任何写接口，因此不产生「静默后写胜出」的新路径，也不声明其为已交付能力。
- 环境变量只允许覆盖 `policy`；调试时指定后端名必须同时 `degraded=True`，且所有状况判断只发生在 `Selector.select()` 一处（X6）。
- `probe()` 采用**追加而非改名**：保留 `available / missing / incompatible` 三态与 `API_VERSION = "1"`，新增键全部来自 `compat_matrix.json`；三态改名与 bump 到 2 是破坏性契约变更，列为审批项（复核报告 §七 第 1 项）。
- 8 行能力矩阵是 Selector 的唯一判据来源，每行对应一种「状况」，不因重构删掉任何一行（X1）。
- `Decision` 可序列化且带 `backend` / `reason` / `fallback` / `capabilities_used` / `degraded`，写进 `reports/decisions.json` 作为输出留痕（X2）。
- 不删任何现有能力、不改 `mpl_backend` 绘制语义、不删 `PUT /api/spec`、不删隐式双路；删除类动作全部留给后续阶段与审批项。
- 不碰 `NetlabHome`（计划 §10 硬边界：本轮只可改 PlotKit 仓库，宿主只在 P4 允许改一个文件）；X4 / X5 相关的宿主改造本轮不做。
- 不创建 `docs/waivers.md`：本轮不实施任何需要豁免的红线动作，「不做」不等于豁免。
- `status: implemented` 指**规格口径已定稿、可据此验收**，不指代码已全部落地；实际实施结果与最终测试数由 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` 回填。

## Testing Decisions

- 测试只断言外部行为（加载结果、往返等价、响应头、异常类型与消息），不断言私有符号、源码文本、模块内部身份。
- **三层各只有一个职责，禁止交叉**：`tests/contract/` 只测 schema 校验 / 版本迁移 / 能力矩阵 / Decision 可解释性（不测像素、不测耗时）；`tests/parity/` 只测重构前后同一输入同一结果的等价性（AST / 结构哈希，不用 `git diff --numstat` 增删差当等价判据，X7）；`tests/render/` 只测视觉回归（结构比对 + 像素容差，不逐字节比 PNG、不做跨后端 bit-exact）。
- 明确禁止：新增读源码的字符串断言、精确耗时硬阈值、私有符号断言、跨后端逐字节 bit-exact 比对（X8）。计划 §2 P1-9「7 个测试文件使用 `read_text()/read_bytes()`」**已确认（CONFIRMED）**：`grep -rlnE 'read_text\(|read_bytes\(' PlotKit/tests/ --include='*.py'` → 7 个文件（逐文件行号见 `docs/PLOTKIT_ORIGIN_REFACTOR_REVIEW_2026-11-09.md` §三 P1-9）。X8 只禁止**新增**这类断言；既有 7 个文件属 legacy，其清理在本轮 Out of Scope，不得据此改写或删除既有测试。此前「未复现、须再核」的说法源于一次 basic-regex 误用（把 `|` 当字面量、只扫 `tests/*.py`），已作废。
- 放行判据为 `>= 473 passed`：复核阶段 `c563707` = `470 passed, 19 warnings in 51.34s`；并行提交 `1cf2570` 新增 3 条 host_api 测试后本轮基线 = `473 passed, 19 warnings in 70.56s`（lead 04:22 重跑并通报）；本轮新增 contract/parity/render 测试后最终数必然 >473，钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准。451 只是静态 `def test_` 计数，不作为放行判据。
- 全量回归固定命令 `python -m pytest -o addopts= -q --disable-warnings`；必须带 `-o addopts=`，因为 `PlotKit/pyproject.toml:66-67` 的 `addopts = "-q"` 会让裸跑 `-q` 叠成 `-qq` 并隐藏汇总行。
- 前端门禁 `tsc --strict` 0 errors；esbuild 产物漂移用 `git diff --exit-code` 判定（CODE_STANDARDS §2 D100/D119 zero-build 红线）。
- 所有 `/api/` 前端调用必须走 `api()` helper（`NetlabHome/netlab/docs/AGENT_GUIDE.md` §1.1），失败态 / 空态 / 未挂载态分开。
- 等价性证据必须是**命令输出留痕**，不是「脚本存在」（X2）。

## Out of Scope

- P1：contrib 拆分与 `ns` extra（须先实测 import 代价与 X2 等价留痕）。
- P2：删除 `PUT /api/spec`、带 `base_revision` 的 `PATCH /api/doc`（409 乐观并发，**本轮未实施 / deferred**）、`Path.cwd()/layout.json` 默认落点的迁移裁定、Inspector / Theme / Template 的全量 UI 落地、六模块前端拆分。
- P3：删除隐式双路渲染路径、把 `server/app.py` 8 处内联 struct 打包收敛到 `encode_frame()`（本轮只新增 Selector 骨架、8 行矩阵定义与一条平行 `Frame v1` wire；既有内联打包与 `dispatch.choose()` 原样保留，收敛会改变 `/api/column` / `/api/xyz` 的对外字节，故 deferred）。
- P4：NetlabHome 宿主接入、FrameSource 改造、移除 X4 四符号。
- P5：docs 瘦身到 <1 MB / 资产移 LFS、TS 产物改 CI 生成不入库、性能基准与 `BENCHMARKS.md` 数字冲突裁定。
- `probe()` 三态改名与 `api_version = 2`（破坏性契约变更，须用户审批）。
- 创建 `docs/waivers.md`（本轮无红线豁免动作）。

## Further Notes

- **接缝确认项**：`/to-spec` 第 2 步正常要向用户确认测试接缝是否选在「契约加载器 + `Selector.select()`」两处、是否该再收敛为一处；`/to-tickets` 第 4 步正常要向用户确认 12 张票的粒度、阻塞边与拆分。用户原话明确「之间不要反复找我批准，只留下需要审批复核决策的操作」，故这两步**跳过并顺延为最终复核项**（复核报告 §七 第 9、10 项），不在本轮中途请示。
- **需审批 / 复核 / 决策项**：全部交叉引用 `docs/PLOTKIT_ORIGIN_REFACTOR_REVIEW_2026-11-09.md` §七 的 11 项（三态改名与 bump、删除整份覆盖接口与 PATCH 写入口、默认落点迁移兼容性、contrib 与 `ns` extra、TS/JS 产物入库策略、docs 资产处置、宿主基线重钉、性能数字裁定、接缝确认、工单粒度确认、G0 判据 451→470→`>= 473 passed`）。
- **红线与闸门**：X1–X10 全部适用于本轮；本轮唯一目标闸门是 **G0 契约冻结**，且 G0 结论须由 lead 在捕获命令输出后回填。**G1 / G2 / G3 / G4 本轮均未达到**，不得标 completed（复核报告 §五、§六）。
- **基线 addendum（2026-11-09 04:22–04:28，lead 通报）**：并行会话在 03:23:50 提交 `1cf2570844c533cb2eb3ef44f352caa7d82fe764`（新增 `tests/test_host_api.py` 3 条测试、给 `PlotKit/docs/BENCHMARKS.md` 加 `unverified (2026-11-09 严格审计)` banner），本轮实施基线由 `c563707` / 470 后移为 `1cf2570` / `473 passed, 19 warnings in 70.56s`；banner 只是 X10 的**部分**缓解，不等于冲突裁定完成。本文件不宣称在 `1cf2570` 下重新核对过任何 `src/plotkit/...` 行号，实施前须按当前 HEAD 复核。
- **编号说明**：PK-R24 / D39 是本轮按 `PlotKit/docs/REQUIREMENTS_AND_PROGRESS.md` 既有上限（PK-R23 / D38）顺延分配的新编号，文档同步由 12 号票完成。
- **签字表**：`docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` 现为 `PlotKit/docs/` 下的**同名归档指针（非原件）**，现行闸门状态与口径见 `docs/GOVERNANCE_SSOT_2026-11-10.md` §2；**工单**：`docs/tickets/01..12-*.md`（裁定 ⑩ 已入仓）；**机检证据**：`reports/*.json`（在仓内，随冻结标签提交）；**pinned 常量唯一来源**：`reports/test_baseline.json` 的 `collected`。

## 实测

本节由 lead 在捕获命令输出后回填（2026-11-09 15:36–15:49 +0800，`cd PlotKit && export PYTHONPATH=src`）；裁定书 `docs/PLOTKIT_P0_DECISIONS_2026-11-09.md` §二 11 项收口后复跑。**下列均为该次实测的历史点值（当时 pinned=544，见 `docs/waivers.md` W-002）**；现行 pinned 常量、合法增量与放行判据见 `reports/test_baseline.json`、`docs/waivers.md` W-002 与 `docs/GOVERNANCE_SSOT_2026-11-10.md` §4。命令全文、输出逐字、判据逐条与遗留见签字表归档指针所指向的现行口径文档；仓内机检证据为 `reports/*.json`。此处只给摘要，不重复造数字：

- 全量回归 `python -m pytest -o addopts= -q --disable-warnings` → `544 passed, 19 warnings in 56.13s`（exit 0）；`--collect-only -q` → `544 tests collected in 1.86s`。放行判据按裁定 ⑪ 改为 `pytest exit 0 且 collected == reports/test_baseline.json 的 pinned 常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（`tools/check_test_baseline.py` 机检，`reports/test_baseline.json` 钉定 pinned 常量（该次实测 544）），不再是 `>= 473 passed`。
- 三层 `python -m pytest -o addopts= -q tests/contract tests/parity tests/render --disable-warnings` → `70 passed, 1 warning in 3.45s`。
- 门禁全部 `ok=True`、零 violations：`check_layers: scanned=56 violations=0`、`check_capability_matrix: rows=8 violations=0`、`check_doc_sync: capability_rows=8 violations=0`、`check_test_baseline: collected=544 pinned=544 ok=True`、`bench_regress: check=ok`、`record_update: entries=10 ok=True`、`generate_reports: layers=ok; capability_matrix=ok; doc_sync=ok`；`reports/{architecture,decisions,schema}.json` 二次生成 sha256 不变。
- `python -m black -q`（本轮 30 个新增/改动 Python 文件）exit 0 且 `ast.dump` 逐文件等价（`ast_diff_count=0`）；`python -m flake8` exit 0 零命中；`npm run typecheck` exit 0、`npm run test:utils` 19 pass / 0 fail、`npm run build` 后 `git diff --stat -- src/plotkit/static/*.js` 为空（零产物漂移）。
- 裁定 ⑨ 后 `/api/capabilities` 顶层 `features` / 静态 `capabilities` / 动态 `optional` 三字段分离（8 行 `capabilities_used` 并集 19 个后端能力名，不随 pyvista 环境漂移）；裁定 ③ 后 `get_layout()` 仅在 `using_default` 下 lazy 触发一次 `migrate_legacy_layout()`，四条机检通过。
- 规格中标注「本轮未实施 / deferred / 需审批」的条目（PATCH /api/doc、PUT /api/spec 删除、inline struct 收敛、前端 `test:ui`、contrib 拆分、宿主接入、docs 瘦身）不在上述实测覆盖范围内；G1–G4 均未达到，签字表相应行不得标 completed。**G0 机器可判部分达成，但 CI 首次绿灯与「评审通过」签字待用户**（本机代理未开，无法 push 触发远端 CI）。
