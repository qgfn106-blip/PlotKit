# 02: FigureDocument frozen dataclasses + strict from_dict/migrate/validate + Report

**What to build:** 把 `src/plotkit/spec/model.py:83-115` `new_spec()` 的裸 dict 升级成不可变、可校验的 v1 文档对象：调用方 `from_dict()` 装入旧 dict 时，未知顶层字段被明确拒绝（或进 extensions），并能拿到带字段路径的结构化 Report；旧 dict 仍可原样读回。

**Blocked by:** 01（四份 JSON 契约 + 加载器）
**Status:** ready-for-agent

- [ ] `FigureDocument` 及 Page/Layer/Plot/Axes/Theme/Template 为 `@dataclass(frozen=True)`，赋值即失败有行为断言。
- [ ] `from_dict()` 严格：未知顶层字段报错并列明字段名；`validate()` 返回 Report（错误集合 + 字段路径），不抛裸异常。
- [ ] 字段形状只从 01 的 figure.v1 契约加载，不得再写一份白名单；与 `src/plotkit/spec/validate.py:163` `KNOWN_VIEW_KEYS`、`:183` `KNOWN_STYLE_KEYS`、`:255` `KNOWN_FIGURE_KEYS`、`:272` `KNOWN_TOP_KEYS = {"spec_version","figure","layers"}` 并列存在但一个不改。
- [ ] legacy 无损信封：0.1 原始 dict 原样保留在 envelope，未知字段进 `extensions`，`to_legacy_dict()` 可逐字段还原（X9）。
- [ ] `migrate` 入口在本票只留签名/分派，具体实现在 03；本票不允许删除任何旧字段。
- [ ] 新增行为各配一条行为测试，禁止断言私有符号身份、禁止读源码字符串（X8）。
- [ ] 文档同步：`PlotKit/docs/REQUIREMENTS_AND_PROGRESS.md` 记 PK-R24 / D39 一条；不写进 netlab 文档。
- [ ] 旧基线不退化：`python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（钉定常量见 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0，票面不写数字下限）。

完工检测：`cd PlotKit && python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（最终钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准）；`from_dict()` 合法/未知字段/legacy 回读三条路径逐条实测并留命令输出（不是看代码推断）。
