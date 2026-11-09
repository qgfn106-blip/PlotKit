# 06: capability.v1.json 形状 + 8 行机器可读矩阵 + reports/decisions.json + check_capability_matrix.py

**What to build:** 能力矩阵从「计划文档里的 8 行散文」变成唯一机器可读判据：新增一种状况只加一行数据与一条 Decision 断言，不加一个 if；`check_capability_matrix.py` 逐行比对矩阵与 `reports/decisions.json`，删掉任一行能力都会让门禁失败（X1）。

**Blocked by:** 01（四份 JSON 契约 + 加载器）、05（RenderTarget/Decision/Backend Protocol + 8 行能力矩阵 + select() 唯一决策点 + X6）
**Status:** ready-for-agent

- [ ] `capability.v1.json` 定义状况字段（维度 / 需求 / 可选后端 / 前置 extra / degraded 条件），与 05 的 `Decision` 字段一一对应且由同一契约加载器读取。
- [ ] 8 行矩阵逐行落盘，顺序与计划 §4.4 :311-320 一致：2D 出版矢量、3D 出版矢量、3D 交互/大规模、百万点时序、矢量场/流线、实时流式增量、动画/批渲染、NS 涡旋教学。
- [ ] `reports/decisions.json` 由 `Selector.select()` 实际输出生成，8 行各一条，含 `backend` / `reason` / `capabilities_used` / `degraded`；禁止手写副本。
- [ ] `PlotKit/tools/check_capability_matrix.py` 机检：矩阵 8 行齐全、每行恰有一条 Decision 回归用例、无策略被删、关键 `degraded` 条件与 05 的断言一致。
- [ ] 门禁输出是命令留痕（逐行 PASS/FAIL + 计数），不是「脚本存在」即算通过（X2）。
- [ ] `reports/schema.json` / `reports/architecture.json` 由可复现脚本生成，数字绑定当前 HEAD 与生成器版本（X10；计划 §10 自检第 6 问）。
- [ ] `PlotKit/tools/` 现状无 `reports/` 目录、无 spec JSON fixtures；本票只新增目录与文件，不改动 bench_*.py / cdp_*.mjs / coverage.py / dev_serve.py / diag.py / mpl_method_audit.py / render_shot.py / shot.ps1 / verify_ns.py / verify_volume3d.py / verify_webgl3d.py 的既有行为。
- [ ] `PlotKit/pyproject.toml` 的 extras（web / desktop / three / metrics / dev / all / server / mpl）作为「前置 extra」判据来源；`ns` extra 不存在，不得在矩阵里假定它已存在。
- [ ] 测试放 `tests/contract/`，只断言矩阵→Decision 的行为映射，不测像素 / 耗时 / 私有符号（X8、计划 §9.1）。
- [ ] 旧基线不退化：`python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（最终钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准）。

完工检测：`python tools/check_capability_matrix.py` 输出 8 行逐行判定并留命令输出；`reports/decisions.json` 可由 05 的 `select()` 重放逐字段一致；`cd PlotKit && python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`。
