---
status: done
stage: N6（跨仓契约诊断）
decision: 只诊断、不改桥接（X12）
date: 2026-11-10
evidence_head: 9dc0ef9
---

# N6 — 跨仓契约诊断（PlotKit × NetlabHome，只诊断）

## 0. 前置：X12 状态（为何只读）

`NetlabHome` 工作树**非干净**：`git status --porcelain` 显示
`A  reports/shadow/5ac049fc…json`（并行会话产物）。按红线 **X12**「NetlabHome 状态非空或
与并行会话冲突时禁改 `netlab/plotkit_bridge.py`」，本轮**只做只读诊断，不修改 NetlabHome
任何文件**。

## 1. 版本区间「0.2 / 0.3」出现的全部位置（实测）

| # | 位置 | 形式 | 是否生成物 |
|---|---|---|---|
| 1 | `PlotKit/pyproject.toml:7` | `version = "0.2.1"` | 手写（PlotKit 自身版本） |
| 2 | `PlotKit/src/plotkit/schema/compat_matrix.json:5-6` | `package_version_min:"0.2"` / `package_version_max_exclusive:"0.3"` | PlotKit 侧机器真源（P0 ⑨） |
| 3 | `NetlabHome/docs/canonical/contracts/compatibility.yaml` | `plotkit.min:"0.2.0"` / `max_exclusive:"0.3.0"`（注释自称「唯一真源」） | netlab 侧机器真源 |
| 4 | `NetlabHome/netlab/contracts/generated.py:5-6` | `PLOTKIT_MIN=(0,2,0)` / `PLOTKIT_MAX_EXCLUSIVE=(0,3,0)` | **由 #3 生成**（`tools/gen_contracts.py`） |
| 5 | `NetlabHome/pyproject.toml:25-26` | `plotkit = ["plotkit>=0.2,<0.3"]` | **手写**，非生成 |
| 6 | `NetlabHome/netlab/plotkit_bridge.py:124` | `PLOTKIT_MIN <= _version_tuple(version) < PLOTKIT_MAX_EXCLUSIVE`（用 #4 常量） | 用生成常量 |
| 7 | `NetlabHome/netlab/plotkit_bridge.py:129` | 错误串 `不在 >=0.2,<0.3 兼容范围内` | **手写字符串**，非生成 |
| 8 | `NetlabHome/netlab/plotkit_bridge.py:191` | 提示串 `pip install 'plotkit>=0.2,<0.3'` | **手写字符串**，非生成 |

当前三方数值一致（均 0.2.0 / 0.3.0），且 PlotKit 版本 `0.2.1` 落在区间内。

## 2. netlab 仓内已有的一致性机制（好的一面）

- `NetlabHome/docs/canonical/contracts/compatibility.yaml` 是 netlab 侧「唯一真源」；
  `tools/gen_contracts.py` 由它生成 `netlab/contracts/generated.py` 与
  `frontend/app/contracts.ts`，并提供 `--check`（漂移 exit 1）。
- `NetlabHome/netlab/tests/test_compat_matrix.py` 断言 canonical YAML == 生成常量 ==
  `plotkit_bridge.PLOTKIT_MIN/MAX_EXCLUSIVE`，并覆盖 probe 三态（低于 min / 区间内 /
  等于 max 均 incompatible）。

→ netlab **仓内**常量链已机器自洽。

## 3. 真实缺口（N6 结论）

1. **跨仓「双真源」**：`PlotKit/src/plotkit/schema/compat_matrix.json` 与
   `NetlabHome/docs/canonical/contracts/compatibility.yaml` 各自独立声明区间，
   **没有任何机器检查把两者绑定**。今天数值一致纯属手工同步，任一侧单独 bump
   （例如 PlotKit 升 0.3 或 Netlab 改 min）不会被对方 CI 拦下。
2. **仓内两处未纳入生成/检查的手写重复**：`NetlabHome/pyproject.toml:26` 的
   `"plotkit>=0.2,<0.3"` 与 `plotkit_bridge.py:129/:191` 的错误/提示字符串，
   都**不是**由 `compatibility.yaml` 生成，`gen_contracts.py --check` 与
   `test_compat_matrix.py` 都不覆盖它们 → 与常量漂移时不会报红。
3. 因此 **C-4「单一主人」尚未落地**：区间契约事实上由两个仓各持一份真源 +
   netlab 仓内两处手写拷贝组成，缺少跨仓机器校验。

## 4. 对闸门的影响

- N6 为纯诊断，不改任何代码/依赖/桥接，不改变可运行面，不涉及 G0–G4 回填。
- **不得宣称 C-4**（单一主人未落地）。G3 仍「不达成」，G4 仍留白。

## 5. 建议（须另行单独审批后实施，本轮不做）

- 选定**唯一机器真源**（建议 PlotKit 的 `compat_matrix.json` 为权威），
  让 netlab `compatibility.yaml` 由它生成或在 CI 中做跨仓比对（跨仓 job 或 vendored 快照 + hash）。
- 把 `NetlabHome/pyproject.toml` 的 `plotkit>=…` 与 `plotkit_bridge.py` 的提示串改为
  从生成常量拼装，或加入 `test_compat_matrix.py` 的断言，避免手写拷贝漂移。
- 上述改动触及 NetlabHome，须待其工作树干净且与并行会话协调后、按 X12 单独审批执行。
