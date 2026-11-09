# 03: 0.1→v1 显式迁移 + 双向 golden + 3 fixtures + X9 不删旧字段

**What to build:** 让任何一份 `spec_version="0.1"` 的旧图都能被显式 `migrate_v0_to_v1()` 读入并再逐字段写回 0.1，用户不会因升级丢字段。本票单独可演示「拿 3 份旧 spec fixture 迁移 → 回写 → 逐字段一致」。

**Blocked by:** 01（四份 JSON 契约 + 加载器）、02（FigureDocument frozen dataclasses + strict from_dict/migrate/validate + Report）
**Status:** ready-for-agent

- [ ] `migrate_v0_to_v1()` 是唯一显式迁移入口，不做隐式版本猜测；`migrate_v1_to_v0()` 可回写（双向 golden）。
- [ ] 3 份 0.1 fixtures：最小 `new_spec()`、带 layers/style/view/shapes/insets/notes 的完整图、带未知扩展字段的图。
- [ ] `src/plotkit/spec/model.py:83-115` `new_spec()` 全部顶层键与 figure 子键、`:143` `SHAPE_TYPES`、`:166` `NOTE_TYPES` 一个不删（X9）。
- [ ] 未知字段进 `extensions` 并随回写原样保留；旧 dict 逐字段相等，不用「字段集合相同」糊弄。
- [ ] golden 断言是数据断言（0.1 fixture → v1 → 0.1 逐字段比对），不是源码字符串断言、不是 `git diff --numstat`（X7/X8）。
- [ ] 迁移失败给出含字段路径的 Report；缺 `spec_version` / 未知版本各有行为测试。
- [ ] `src/plotkit/spec/io.py:34-38` `loads()` 与 `src/plotkit/spec/model.py:15` `SPEC_VERSION = "0.1"` 对外行为不变。
- [ ] 契约层测试只放 `tests/contract/`，不测像素、不测耗时（计划 §9.1 分层）。
- [ ] 旧基线不退化：`python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（最终钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准）。

完工检测：3 份 fixture 的 0.1→v1→0.1 双向 golden 逐字段实测并留命令输出；`cd PlotKit && python -m pytest -o addopts= -q tests/contract --disable-warnings` 与 `python -m pytest -o addopts= -q --disable-warnings` 均全绿（判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`，钉定常量见 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0）；不以「脚本存在」当等价证据（X2）。
