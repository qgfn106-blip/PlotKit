# 04: Frame v1 encode_frame/decode_frame + golden vector + 并发 1000 次

**What to build:** 实时流式增量有一份可逐字节复现的 wire 契约：调用方 `encode_frame()` 再 `decode_frame()` 得到逐字段相同的 Frame，并发 wire 编码 1000 次不出现列长不一致；**新增**一条平行 `Frame v1` wire（`FRAME_MAGIC=b"PKF1"`）与纯只读 `GET /api/frame`。`src/plotkit/server/app.py:38` `MAGIC = b"PK01"`、`:41-52` `_binary_xyz()` 等内联 struct 打包**原样保留、不收敛**（收敛会改变 `/api/column` / `/api/xyz` 的对外字节，属计划 §8 P3，本轮 deferred）。

**Blocked by:** 01（四份 JSON 契约 + 加载器，提供 frame.v1 字段名 / 类型 / 字节序）
**Status:** ready-for-agent

- [ ] `encode_frame()` / `decode_frame()` 字段与字节序只从 frame.v1 契约读取，不写第二份 struct 布局。
- [ ] 固定 golden vector：给定一组列数据，编码字节序列逐字节固定；解码后逐字段相等（X2 要输出留痕，不是脚本存在）。
- [ ] 并发 wire 编码 1000 次：每次帧的列数、列长、`generation` 一致；断言是值相等，不是耗时阈值（X8）。
- [ ] 既有 `MAGIC = b"PK01"` 与 `_binary_xyz()` 的字节输出保持不变（无重构），用 parity 测试锁住同一输入同一字节。
- [ ] 未知 / 截断 / 错版本帧给出含字段路径的失败信息，不静默返回空帧。
- [ ] 契约层测试放 `tests/contract/`，等价层放 `tests/parity/`，不交叉（计划 §9.1）。
- [ ] 纯新增，不改 `GET /api/render` 的对外响应头（`src/plotkit/server/app.py:956-1009`）；内联 struct 打包收敛到一处本轮不实施（deferred，P3）。
- [ ] 旧基线不退化：`python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`（最终钉定数以 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0 回填为准）。

完工检测：golden vector 逐字节比对与 1000 次并发实测各留一条命令输出；`cd PlotKit && python -m pytest -o addopts= -q --disable-warnings` 满足判据 `pytest exit 0 且 collected == 签字表 G0 钉定常量 且 failed == 0 且 skipped 显式列出 且 四门禁 violations == 0 且 reports/*.json 二次生成 sha256 不变`；不以「脚本存在」当等价证据（X2/X7）。
