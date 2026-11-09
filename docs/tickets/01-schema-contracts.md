# 01: 四份 JSON 契约 + 加载器 + L0 纯标准库

**What to build:** 让「形状」第一次有唯一机器可读来源：调用方能加载四份版本化 JSON 契约并拿到逐字段校验结果，而现有 `new_spec()` 与四组白名单的对外行为完全不变。本票可单独演示「加载合法契约成功、改坏一个字段即定位报错」。

**Blocked by:** None（可立即开工）
**Status:** ready-for-agent

- [ ] 四份契约均带显式版本字段（`figure.v1.json`、`frame.v1.json`、`capability.v1.json`、`compat_matrix.json`），可由 `json.load` 读出。
- [ ] figure.v1 覆盖 `src/plotkit/spec/model.py:83-115` `new_spec()` 返回的全部顶层键与 figure 子键；`:40-61` `default_style()`、`:64-80` `default_view()`、`:143` `SHAPE_TYPES`、`:166` `NOTE_TYPES` 的字段一个不删（X9）。
- [ ] frame.v1 声明帧 wire 字段名、类型、字节序，供 04 的 golden vector 直接引用。
- [ ] capability.v1 声明 8 行矩阵的每行形状（判据 / 后端 / 能力标签 / degraded 条件），供 05、06 引用。
- [ ] compat_matrix 是 schema 版本列表、帧版本、optional 列表、能力声明的唯一主人；仓库内无第二处硬编码版本号。
- [ ] 加载器只 import 标准库；门禁命中契约层出现 `import plotkit`（含子模块）即失败。
- [ ] 加载器行为测试：合法文件加载成功、未知/缺字段给出含契约名的失败信息、重复加载结果一致。
- [ ] 契约文件与加载器全部纯新增；`src/plotkit/spec/model.py:15` `SPEC_VERSION = "0.1"` 与 `src/plotkit/spec/validate.py:163`、`:183`、`:255`、`:272` 四组白名单不改动。
- [ ] `probe()` 三态与 `src/plotkit/host_api.py:17` `API_VERSION = "1"` 不变（三态改名属复核报告 §七 第 1 项审批）。
- [ ] 旧基线不退化：`python -m pytest -o addopts= -q --disable-warnings` 须满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（钉定常量见 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0，票面不写数字下限）。
- [ ] 本票新增行为各有对应测试（CODE_STANDARDS §4），无源码字符串断言、无精确耗时阈值（X8）。

完工检测：`cd PlotKit && python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`；`python -m pytest -o addopts= --collect-only -q` 收集数与签字表 G0 钉定常量一致（见 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` §1，票面不写数字下限）。加载器合法/非法两条路径逐条实测并留命令输出，不以「脚本存在」当证据（X2/X7）。
