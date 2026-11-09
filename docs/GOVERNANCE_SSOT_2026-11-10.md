# PlotKit 治理口径单一来源（SSOT）· 2026-11-10

> 本文件是 **PlotKit 仓内现行唯一治理口径**。2026-11-09 23:55 清理的五份「工作区根 `docs/`」治理文档（计划 / 复核报告 / 签字表 / 裁定书 / 下一阶段计划）原件从未提交进本仓、不可逐字恢复；仓内 `docs/` 下同名 `PLOTKIT_*.md` 文件均为**归档指针（非原件）**，把历史引用导向本文件、`docs/waivers.md`、`reports/*.json` 与各阶段报告。凡「现行判据 / 闸门状态 / 放行依据」以本文件为准，历史文档仅作留痕。

## 1. 准确状态（用户 m04076 核定措辞，逐字）

> **N0–N6 六阶段任务交付完毕、远端 CI 稳定双绿；G3 / C-4 / G4 未达成，签字表待签**——而不是「修复完了」。

- 远端 CI：`plotkit-python-tests` 与 `plotkit-static-build` 在分支与 `main` 上均稳定 success；终局双绿 run `42662171282` / `42662171298`（`main`=`f5fd9b3`）。
- `main` = `f5fd9b39d644e9054cd5398fe37624c05a5009be`（本轮治理口径收口前钉桩）；轻量 tag `p0-freeze-2026-11-09` → `116ec67be9163aac54f7f4ed33d4d6a00ba8e2e5`（冻结标签不可变；全程未 amend / rebase / force-push / reset / 删移 tag）。

## 2. 闸门真实状态（G0–G4 / C-4）

| 闸门 | 状态 | 依据 / 未达成原因 |
| --- | --- | --- |
| G0 契约冻结 | **机器可判达成；「评审通过」签字待用户** | 四份契约 JSON / 双向 golden / 三层测试 / 六门禁 / `collected == pinned 常量` 门禁全绿；签字表待签，不自签「达成」 |
| G1 contrib 拆分 | **隔离机器可判完成；签字待用户** | 根因 `src/plotkit/__init__.py:25 from . import field3d, ns` 已处理；+2 真实用例（见 W-002） |
| G2 PATCH /api/doc | **留白（方案 B：只读、推迟）** | `docs/N2_PATCH_DEFERRED_2026-11-09.md`；`docs/decisions/2026-11-09-patch-api-design.md` 已 `status: decided`；`PUT /api/spec` 保留 |
| G3 单一决策点 | **不达成 / 未签** | N5 仅做「行为保持型薄适配」：`dispatch.choose()` 收敛为 env 解析 + `Selector().select_backend(...).backend`；真实算法仍在 `dispatch._choose_impl`，`RendererSelector.render` / hybrid3d / pyvista pool 未证明全经此单点；`Decision.advisory_only=True` 只标注骨架 advisory |
| G4 docs 资产 | **留白** | `docs/ASSET_INVENTORY_2026-11-09.md` 102 行 / 29,930,760 字节仅逐行标注；未删除 / 迁移 / LFS；`docs<1MB` 判据未碰（用户 m03409 裁定「仅逐行标注」，X10 禁止擅自删资产 / 改 `.gitattributes` / 启 LFS） |
| C-4 跨仓版本契约 | **未达成** | `docs/N6_CROSS_REPO_CONTRACT_2026-11-10.md` 只读诊断列全 8 处 `0.2/0.3`；`NetlabHome/pyproject.toml:26` 与 `netlab/plotkit_bridge.py:129/:191` 是手写拷贝、不被 `gen_contracts.py --check` / `test_compat_matrix.py` 覆盖；单一主人未落地 |

C-4 前置条件（用户 m04076 称「已解除」）复核：`cd NetlabHome` → HEAD `2ce0b8e4c1f7a297148827fcc4fe3a3f1ab4e10a`，`## main...origin/main`（本地=远端，这一点与用户说法一致），但 `git status --porcelain` 仍有 ` M netlab/docs/specs/2026-11-09-g0-g4-signoff.md`（并行会话未提交改动）→ **工作树并非 clean**，X12「NetlabHome status 非空或与并行会话冲突时禁改 `plotkit_bridge.py`」仍生效。故 C-4 本轮仍只做只读诊断、列为排期 / 审批项。

## 3. 豁免记录（W-001 / W-002）

- **W-001**（`docs/waivers.md`，已批准）：N0 远端首绿，解除「禁止改测试/基线」三项——3D 用例逐用例守卫、基线 schema v2 两 profile、修 `collected == passed + failed + skipped` 守恒式；生产修复 `/api/volume` 400 / `ns/iso.py` 空结果早返回。四张反向验证 V1–V4 先红后复原。
- **W-002**（`docs/waivers.md`，**状态：待用户追认，非事前豁免**）：事后如实记录 pinned 常量 `544→546→556` 三次合法增量（`f30b593` N1 +2 → `3942419` N5 +10），声明判据恒为 `collected == reports/test_baseline.json 的 pinned 常量`、从未放宽为 `>=`，并制定前瞻规则（今后改 pinned 须事前开 W-00N）。X11 禁止事后补豁免，故本条不伪称已批准。

## 4. 现行唯一放行判据（数值不硬编码）

`pytest exit 0 AND collected == reports/test_baseline.json 的 pinned 常量 AND failed == 0 AND skipped 显式且与 profile 一致 AND 门禁 violations == 0 AND reports 二次生成 sha256 不变`

- 唯一数值来源：`PlotKit/reports/test_baseline.json` 的 `collected`（本表 2026-11-10 钉桩时为 556，属历史点值；数值只在该 JSON 维护，判据 / 文档不写死；schema `plotkit.test_baseline/v2`，两 profile `dev_full` / `ci_no_extras`）。**任何文档 / 注释只准「引用 pinned 常量」，禁止写死数字**（用户 m04076 ①）。
- `>= 473 passed` 已被裁定书 §二 第 11 项否决（X7 镜像漏洞：测试数量上升本身不能当放行条件）；`451 / 470 / 473 / 544 / 546` 均为历史点值，不是现行判据。
- 六门禁：`check_test_baseline.py` / `check_layers.py` / `check_capability_matrix.py` / `check_doc_sync.py` / `bench_regress.py --check` / `record_update.py --check`；`generate_reports.py` 二次生成 sha256 不变。

## 5. 五份治理文档 → 仓内权威替代映射（46 处引用的解析规则）

| 被引用名（仓内 `docs/` 同名归档指针） | 原件 | 现行权威替代 |
| --- | --- | --- |
| `PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md` | 工作区根 `docs/`，2026-11-09 23:55 清理，从未入仓 | 本文件 + `docs/specs/2026-11-09-p0-contract-freeze.md` + `docs/tickets/` |
| `PLOTKIT_ORIGIN_REFACTOR_REVIEW_2026-11-09.md` | 同上 | 本文件 §1/§2 + 各阶段报告 `docs/N0..N6_*.md` |
| `PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` | 同上 | 本文件 §2 闸门表 + `docs/waivers.md` + `reports/*.json` + 远端 CI run |
| `PLOTKIT_P0_DECISIONS_2026-11-09.md` | 同上；逐字副本仍在 dsh 附件（见下） | 本文件 + `docs/waivers.md` + `docs/REQUIREMENTS_AND_PROGRESS.md` D39–D40 |
| `PLOTKIT_NEXT_PHASE_AGENT_PROMPT_2026-11-09.md` | 同上；逐字副本仍在 dsh 附件（见下） | 本文件 §2 + 各阶段报告 `docs/N0..N6_*.md` |

- 解析规则：仓内 21 文件 46 行对这些名字的引用，现均指向 `docs/` 下**同名归档指针文件**；指针明确标注「非原件」，并逐项导向本文件对应章节。**历史正文（含 `>= 473 passed` 数字链、两处用户原话逐字引用）保留不改写以留痕**，其作为放行依据的效力已被本文件 §4 覆盖。
- 两份有逐字副本的原件（仓外、可按需恢复，本轮不擅自入仓以免重新引入过期数字）：
  - `C:/Users/weijiewang/.dsh/attachments/v1/files/9c/9c55daeaae6d14cb7f546a7faf1202827bf4b728b8425e6d2e0bb2108e14d18a/PLOTKIT_P0_DECISIONS_2026-11-09.md`（25107B）
  - `C:/Users/weijiewang/.dsh/attachments/v1/files/17/179648c28beede306fa8e4fe47b27d84fe4e00dd5b2091713b14a13564effcc8/PLOTKIT_NEXT_PHASE_AGENT_PROMPT_2026-11-09.md`（14130B）
- 是否把这两份逐字副本恢复进仓、或把 46 处引用逐行重写为仓内 SSOT 链接，属**需用户裁定的决策项**（本轮采用「归档指针 + SSOT」方案：零改写引用、零伪造原件）。

## 6. 需审批 / 复核 / 决策项（本轮不做）

1. **G0「评审通过」签字**：闸门 7 列禁代签，待用户。
2. **③ docs 资产分离 / G4**：X10 禁止擅自删资产、改 `.gitattributes`、启 LFS；用户 m03409 又裁定「仅逐行标注」。二者冲突 → 待用户明确授权后再排期（「逐行标注」已完成，删除 / 迁移 / LFS 未做）。
3. **④ G3 全路径收敛**：需证明 `RendererSelector.render` / hybrid3d / pyvista pool 全经单一决策点，属行为改动，待单独审批。
4. **C-4 跨仓单一主人**：X12 前置条件未解除（Netlab 工作树非空且并行会话在写），待工作树干净 + 用户授权后改 `netlab/plotkit_bridge.py` / `NetlabHome/pyproject.toml`。
5. **W-002 追认**：三次 pinned 增量是否需单独审批，待用户逐条裁定。
6. **② 治理文档原件处置**：是否恢复两份逐字副本进仓 / 是否把 46 处引用重写为 SSOT 链接，待用户裁定。
7. **`tools/record_update.py` 已知 latent 缺陷**：`--add` 用 `newline="\n"` 写 `README.md`，而 `README.md` 为 CRLF，会把行尾改写成 LF（`6436cf5` 曾发生，靠 `f5fd9b3` 补修）。修复需改工具 + 加 CRLF 回归测试 → 会改 collected、需 W-003 事前记录，本轮不动，列为后续项。本轮所有 README 编辑均为字节级、保留 CRLF。
8. **push**：X1 禁止自 push；push 须用户对指定 HEAD 书面授权且不跨 HEAD 复用。本轮只提交到本地 git，不 push。

## 7. 本轮改动清单（2026-11-10）

- ① `tools/check_test_baseline.py` docstring、`docs/waivers.md` §二/§五/§八 与新增 W-002、`docs/specs/2026-11-09-p0-contract-freeze.md` 覆盖声明与 §实测 引言、`docs/REQUIREMENTS_AND_PROGRESS.md` D40/§4/头注、`docs/tickets/README.md` 判据：判据性 544 全部改为「引用 pinned 常量」；历史实测点值保留并声明为历史。
- ② 新建本文件 + 5 份归档指针；`docs/tickets/README.md:10-12/:37` 与 spec 覆盖声明 / §实测 的「工作区根 / 非 git 仓 / 签字表 G0 钉定常量」失实表述改为仓内 SSOT 引用。
- ⑥ `README.md` / `docs/UPDATE_LOG.md` 第 1 行：补 `546` 档（`544→546→556`）、`版本/ref` 改稳定批次标签避免落后、写入准确状态与 G3 / C-4 / G4 未达成。
- 不碰 `NetlabHome`（X12）、不删 docs 资产（X10）、不改 probe 三态 / `API_VERSION`、不删 `PUT /api/spec`、不 rebase / force-push / amend / reset、不 push。
