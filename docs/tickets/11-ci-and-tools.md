# 11: 独立 python-tests.yml + check_layers.py / check_capability_matrix.py / check_doc_sync.py / generate_reports.py + reports/

**What to build:** CI 第一次能拦住「契约被绕过、分层依赖反向、文档与代码脱节」这三类回归；`.github/workflows/` 现状只有 `frontend-static-build.yml`，本票**纯新增一个独立 `python-tests.yml`**（跑全量 pytest、三层测试、三个门禁、`generate_reports.py` 与 `reports/` 漂移守卫），**不改动既有前端工作流的任何步骤**、`package.json` 也不新增脚本。

**审批闸门:** 复核报告 §七 第 5 项（TS/JS 双份改 CI 生成不入库、前端工作流追加 `test:ui`）须先裁定；本轮**未实施**「前端工作流追加 `test:ui` 与 `git diff --exit-code`」「TS 产物不入库」，既有 `.js` 产物全部保留入库（CODE_STANDARDS §2 D100/D119 零构建红线要求每个 `.ts` 都有已提交的 `.js`）。`git diff --ignore-cr-at-eol --exit-code -- reports/` 漂移守卫只针对新 Python 工作流生成的三份确定性 JSON 报告，与前端 `.js` 产物无关。

**Blocked by:** 06（capability.v1.json 形状 + 8 行机器可读矩阵 + reports/decisions.json + check_capability_matrix.py）、07（compat_matrix.json 单一来源 + probe 追加键且旧三态不变 + /api/capabilities）、08（GET /api/doc + ETag）、09（GET /api/frame + X-PlotKit-Decision 响应头，纯新增）
**Status:** ready-for-agent

- [ ] 新增 `PlotKit/.github/workflows/python-tests.yml`：checkout@v4 / setup-python@v5(3.11) / `pip install -e ".[dev,web]"` / `python -m pytest -o addopts= -q --disable-warnings`（全量）/ `pytest tests/contract tests/parity -q` / `pytest tests/render -q` / `python tools/check_layers.py` / `check_capability_matrix.py` / `check_doc_sync.py` / `generate_reports.py` / `git diff --ignore-cr-at-eol --exit-code -- reports/`（计划 §9.3，独立工作流不改 frontend-static-build.yml）。
- [ ] 必须用 `-o addopts=`：`PlotKit/pyproject.toml:66-67` 有 `testpaths = ["tests"]` 与 `addopts = "-q"`，裸 `python -m pytest -q` 会变成 `-qq` 吞掉汇总行。
- [ ] `check_layers.py` 机检计划 §3 依赖方向：`schema/` 只用标准库且不 import `plotkit`；`backend/*` 不 import `server/*` / `static/*` / `desktop/*`；`server/*` 不 import `api/native.py` 的 Figure 活对象；`contrib/*` 不被 `plotkit/__init__.py` 顶层导入。
- [ ] `check_doc_sync.py` 落实 CODE_STANDARDS §0 第 3 条：断言 `docs/REQUIREMENTS_AND_PROGRESS.md` 含 `PK-R24` / `D39`、`pyproject.toml` package-data 含 `schema/*.json`、`docs/specs/2026-11-09-p0-contract-freeze.md` 存在；输出是逐项 PASS/FAIL 的命令留痕，不是「脚本存在」即算通过（X2）。
- [ ] `reports/schema.json` / `architecture.json` / `decisions.json` 由 `generate_reports.py` 确定性生成（`json.dumps(sort_keys=True, ensure_ascii=False, indent=2)`），二次运行 sha256 不变。
- [ ] 前端「追加 `test:ui`」「TS 产物改 CI 生成不入库」本轮 **deferred**，不接线、不造测试桩；`package.json` 现状 `build` 为 esbuild 六个 `.ts`→`.js`、`typecheck` 为 `tsc -p tsconfig.json --noEmit`、`test:utils` 为 `tsc -p tsconfig.utils.json && node --test "tests/**/*.test.cjs"`，**无 `test:ui`**。
- [ ] 不新增读源码字符串断言、精确耗时硬阈值、跨后端 bit-exact 比对；不以 `git diff -w --numstat` 增删差或「测试数量上升」作放行条件（X7 / X8）。
- [ ] 不放行性能数字：`PlotKit/docs/BENCHMARKS.md` 在 `1cf2570` 已有 `unverified (2026-11-09 严格审计)` banner，`check_doc_sync.py` 不得把其中数字当已验证基线（X10；复核报告 §七 第 8 项）。
- [ ] 旧基线不退化：`python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（最终钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准）。

完工检测：三个门禁各输出逐项 PASS/FAIL 并留命令输出；`generate_reports.py` 二次运行三份 JSON sha256 不变；`tsc --strict` 0 errors 且 `git diff --stat -- src/plotkit/static/*.js` 为空；`cd PlotKit && python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`。注意：`reports/` 当前 UNTRACKED，CI 的 `git diff --exit-code -- reports/` 漂移闸门须在 `git add` 三份报告 JSON 后才生效（列为审批项）。
