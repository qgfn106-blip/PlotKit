# N0 远端首绿 · 诊断报告（未达成 · 阻塞待用户决策）

> 阶段：N0（远端 CI 首次绿灯，唯一硬阻塞）
> 时间窗：2026-11-09 17:33–17:39 +0800
> 执行：lead（本地诊断 → 经用户授权后已 push 新分支并触发 CI，见 §8）
> 依据：`docs/PLOTKIT_NEXT_PHASE_AGENT_PROMPT_2026-11-09.md` §0–§2 N0
> 红线遵守：X1 —— 未 push、未改 `.git/config`/代理/网络设置、未 rebase/force-push/amend/reset；仅用单次 `-c http.proxy=…` 覆盖做诊断，不落盘任何配置。

## 0. 证据基线（动手前逐字重钉）

| 项 | 值 |
|---|---|
| date（重钉） | `Mon Nov  9 17:33:36 CST 2026` |
| HEAD | `b45db0ab55dc9b2cdedb58406b79928dd406188f`（`b45db0a` 2026-11-09 17:06:55 `docs(spec): add 裁定书 ⑪ override banner to frozen P0 spec`） |
| tag `p0-freeze-2026-11-09` → | `116ec67be9163aac54f7f4ed33d4d6a00ba8e2e5`（未移动、未 amend） |
| `git status --short` | 空（干净） |
| 本地跟踪 `origin/main`（fetch 前，**陈旧**） | `786c93afb8d8d9263751878fa85097638ebbc4a3` |
| `git rev-list --left-right --count origin/main...main`（fetch 前） | `0	4`（此即计划 §0 所载基线） |
| 真远端 `origin/main`（fetch 后） | `30779d2a8a22bfb5321c062839b9ead442401da8` |
| `git rev-list --left-right --count origin/main...HEAD`（fetch 后） | `2	4` —— **已分叉，非快进** |
| merge-base | `786c93afb8d8d9263751878fa85097638ebbc4a3` |

> 差异说明（R11）：计划 §0 写的 `origin/main...main = 0/4` 是针对**本地陈旧跟踪引用** `786c93a` 计算的；经 `fetch` 后真远端 `origin/main = 30779d2`，真实拓扑为 `2/4` 分叉。此处只记录「基线不同」，不判定计划核查错误。

## 1. 命令全文与输出逐字（网络诊断，只读）

```
# A：git ls-remote 用仓配置（.git/config: proxy = http://127.0.0.1:7897）
$ git ls-remote origin
warning: Ignoring unavailable SSL backend 'openssl'; using 'schannel' instead
fatal: unable to access 'https://github.com/qgfn106-blip/PlotKit.git/':
       Failed to connect to github.com:443 over proxy 127.0.0.1 after 0 ms: Could not connect to server
rc=128

# B：curl 直连（--noproxy '*'）
$ curl -sS -m 20 --noproxy '*' -o /dev/null -w 'http=%{http_code} time=%{time_total}\n' https://github.com/qgfn106-blip/PlotKit
http=200 time=4.618977

# C：curl 经 7897
$ curl -sS -m 20 -x http://127.0.0.1:7897 -o /dev/null -w 'http=%{http_code}\n' https://github.com
curl: (7) Failed to connect to github.com:443 over proxy 127.0.0.1 after 0 ms: Could not connect to server
http=000

# D：curl 经 2494
$ curl -sS -m 20 -x http://127.0.0.1:2494 -o /dev/null -w 'http=%{http_code}\n' https://github.com
http=200

# E：git ls-remote 直连（-c http.proxy= -c https.proxy= 单次空覆盖）
$ git -c http.proxy= -c https.proxy= ls-remote origin
30779d2a8a22bfb5321c062839b9ead442401da8	HEAD
...
30779d2a8a22bfb5321c062839b9ead442401da8	refs/heads/main
rc=0

# F：git ls-remote 经 2494（单次 -c 覆盖）
$ git -c http.proxy=http://127.0.0.1:2494 -c https.proxy=http://127.0.0.1:2494 ls-remote origin
30779d2a8a22bfb5321c062839b9ead442401da8	refs/heads/main
rc=0

# fetch 直连（单次空覆盖）—— 不稳定，超时失败
$ git -c http.proxy= -c https.proxy= fetch origin --prune
fatal: unable to access 'https://github.com/qgfn106-blip/PlotKit.git/':
       Failed to connect to github.com:443 after 21205 ms: Could not connect to server
rc=128

# fetch 经 2494（单次 -c 覆盖）—— 成功
$ git -c http.proxy=http://127.0.0.1:2494 -c https.proxy=http://127.0.0.1:2494 fetch origin --prune -v
   786c93a..30779d2  main   -> origin/main
rc=0
```

**网络结论**：`.git/config` 里的 `proxy = http://127.0.0.1:7897` 已失效（连不上）；直连可用但不稳定（`ls-remote` 成、`fetch` 21s 超时）；**代理 2494 稳定可用**（`curl`/`ls-remote`/`fetch` 全通）。因此 push 技术上可行（用单次 `-c http.proxy=http://127.0.0.1:2494`，不改配置），但受下述分叉与 X1 授权双重限制。

## 2. 关键发现：远端已分叉（非快进，push 会被拒）

merge-base `786c93a` 之后两条历史各自展开：

- **本地 main 独有的 4 个提交**（`786c93a..HEAD`）：
  `c563707` 最小稳定宿主接口 → `1cf2570` probe 三态 → `116ec67` P0 contract freeze（68 文件）→ `b45db0a` 裁定 ⑪ 覆盖声明。
- **远端 main 独有的 2 个提交**（`786c93a..origin/main`）：
  `f3aa6d7` `feat(host-api): ???????? probe/create_server/PlotRenderPort`（提交信息乱码，疑似 Git Data API 并行写入）→ `30779d2` `feat(host_api): probe 三态 + 性能声称标 unverified`。

`git merge-base --is-ancestor origin/main HEAD` → **NO**（非快进）。据此 `git push origin main` 会被 GitHub 拒绝（non-fast-forward）；而 X1 禁止 force-push/rebase/amend/reset，故**不能自行调和**。

## 3. 内容等价证明（分叉只是 SHA 重写，内容不冲突的部分）

```
30779d2^{tree} = 9b13ee0f664d4c63914ed0c473408a978eb70ab1
1cf2570^{tree} = 9b13ee0f664d4c63914ed0c473408a978eb70ab1   ← 与远端 30779d2 完全一致
c563707^{tree} = 7c9238f16bb92b7a65afef6bf50a2abb92e9923a
f3aa6d7^{tree} = 7c9238f16bb92b7a65afef6bf50a2abb92e9923a   ← 与本地 c563707 完全一致
116ec67^{tree} = 6938049bf674bc85906e93a45980d6bebb1f1806   （P0 contract freeze）
```

即：远端这 2 个提交是本地 `c563707`、`1cf2570` 的**内容等价重写**（同 tree、异 SHA）。本地真正领先于远端的实质内容是 `116ec67`（P0 contract freeze，68 文件 +10454/−542）与 `b45db0a`（1 文件 +2）。`git diff --name-only 30779d2 HEAD` = **68 个文件**（`src/plotkit` 14、`tests/contract` 14、`docs/tickets` 13、`docs/decisions` 3、`tools/*` 6、`reports/*` 5、`tests/{parity,render}`、`pyproject.toml`、`.github/workflows/python-tests.yml` 等）——**真远端 main 完全不含 P0 契约冻结产物**。

## 4. CI 触发条件（供可选方案评估）

`.github/workflows/python-tests.yml` 与 `frontend-static-build.yml` 均为：

```
on:
  push:
  pull_request:
```

无分支过滤 → **任意分支 push / PR 都会触发**两条工作流。`plotkit-python-tests` 共 13 个 step（Checkout、Set up Python、Install、Full suite with collected-count gate、Contract and parity、Render baseline、Performance regression band、Update record consistency、Check layer imports、Check capability matrix、Check document & schema sync、Regenerate reports、Reports must be up to date）。

## 5. 判据核对（G0）

计划 N0 判据：`plotkit-python-tests` 与 `plotkit-static-build` **双绿**，且 `python-tests` 各 step 全绿，并取证 `run URL / run id / head_sha`；`head_sha` 不等于授权 HEAD 即判「推错基线」停止。

当前：**0 次远端运行、无 run URL、无 head_sha** → **G0 未达成**，按 X2 不得回填「达成」、不得自签「评审通过」。

## 6. 结论

**N0 未达成。** 存在两个必须先由用户决策的独立阻塞：

1. **分叉调和策略**：远端 main 被并行会话重写（内容等价、SHA 不同），本地领先 P0 契约冻结。不能自行 push（非快进）、不能 rebase/force-push/amend/reset（X1）。
2. **push 授权**：X1 要求「对指定 HEAD 的书面授权，且授权不跨 HEAD 复用」。

在用户就「如何 push 到哪个 ref」明确授权前，本阶段停在此诊断报告；N1–N6 一律不开工（严格串行，前阶段未绿不得开下一阶段）。

## 7. 待用户决策（审批 / 复核项）

| # | 决策项 | 说明 |
|---|---|---|
| D1 | 采用哪种 push 方案 | **方案 A（推荐·最安全）**：把本地 HEAD 推到**新分支** `origin/p0-freeze-2026-11-09`（不动 main、不 rebase、不 force），CI 在新分支跑双绿 → 得远端首绿证据；main 是否合并留后续 PR 决定。**方案 B**：先把 `origin/main`（30779d2）`git merge` 进本地（merge 不在 X1 禁止项），再 FF push main；但两侧对同一批文件（host_api.py 等）均有改动，可能需解冲突。**方案 C**：改成在远端基于 `30779d2` 重放 P0 两个提交（cherry-pick/新建 commit），再 push。 |
| D2 | 授权范围 | 授权对**哪个具体 HEAD / ref** push（需逐字给出 SHA/ref，X1 授权不跨 HEAD 复用） |
| D3 | tag 是否推到远端 | `p0-freeze-2026-11-09`（→116ec67）是否随 push 上传 |
| D4 | 网络修法（可选） | `.git/config` 的 7897 已死；是否要我把 repo 代理改为 2494（**需你单独授权，因为 X1 禁止我自行改配置**），或继续每次用单次 `-c` 覆盖不落盘 |

> 本报告只做诊断，未 push、未改配置、未执行 merge/rebase/cherry-pick。等你对 D1–D3 的裁定后再继续。

---

> 说明：以下 §8 起为本报告在用户裁定后的后续发展，**覆盖 §5/§6 中「0 次远端运行」的陈述**（该陈述仅是 17:39 当时的快照）。

## 8. push 执行与 CI 首跑结果（2026-11-09 18:0x–18:16）

- **用户裁定**：D1=**方案 A**（推新分支 `origin/p0-freeze-2026-11-09`，main 不动）；D3=**一并推 tag** `p0-freeze-2026-11-09`；D2 授权 HEAD=`af16001e9d00d5e8508d970a13895402e6e46c55`（X1 授权不跨 HEAD）。用户另报「重新打开了 Clash Verge 代理，clash 在 7897」，重试后 7897 恢复。
- **鉴权修法（记录）**：portable git 的 exec-path 只有 `git-credential-wincred.exe`，而 `~/.gitconfig` 的 `credential.helper=manager` 指向不存在的 `git-credential-manager`。改用 `git -c credential.helper= -c credential.helper=wincred -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 push …`（空值先清空 helper 列表再加 wincred，读 Windows 凭据管理器）成功。
- **push 结果**：`p0-freeze-2026-11-09` branch → `af16001e9d00d5e8508d970a13895402e6e46c55`（`* [new branch]`）；tag `p0-freeze-2026-11-09` → `116ec67be9163aac54f7f4ed33d4d6a00ba8e2e5`（`* [new tag]`）；`refs/heads/main` 仍 `30779d2a8a22bfb5321c062839b9ead442401da8`（**未动**）。
- **CI 触发（api.github.com 直连查询，total_count=4）**：
  - on `af16001`：`plotkit-static-build` = **success**（run 42598683901）；`plotkit-python-tests` = **failure**（run 42598684141，job 129097515999）。
  - on `116ec67`（tag push）：static-build success（42598732517）；python-tests failure（42598732523）。
- **失败定位**：`python-tests` 的 **step 5 `Full suite with collected-count gate`（`python tools/check_test_baseline.py`）失败**，step 6–14 全 skipped，step 1–4 success（含 `pip install -e ".[dev,web]"`）。
- **取证限制**：job 原始日志下载被拒 `403 Must have admin rights to Repository.`（无 token）；check-run annotations 仅 `Process completed with exit code 1.`（path `..github`, start_line 18）。故 CI 原始 stdout 不可得，下面 §9.3 用**本机等价环境复现**给出等价 stderr。

## 9. 失败五要素（N0 计划 step 5 要求）

**1. 命令全文（CI step 5）**：`python tools/check_test_baseline.py`；其内部两条 = `python -m pytest -o addopts= --collect-only -q` 与 `python -m pytest -o addopts= -q --disable-warnings -ra`。

**2. 退出码**：`1`（step 5 failure）。

**3. stderr / 输出尾部（本机等价 CI 环境复现，见 §9.4）**：

```
check_test_baseline: collected=509 pinned=544 passed=501 failed=4 skipped=7 exit=1 ok=False
```

violations 共 5 条：全量 pytest 退出码 `1 != 0`；`failed == 0 不满足：failed=4`；`collected 下降 544 -> 509`（提示需 docs/waivers.md 事前豁免）；`collected == passed + skipped 不满足：509 != 501 + 7`；`skipped 集合与基线不一致：实际 7，基线 []`。

**4. 环境指纹**：CI = `ubuntu-latest` + `actions/setup-python@v5 python "3.11"` + `pip install -e ".[dev,web]"`（**不含** pyvista / vtk / psutil / pywebview / h5py）；本地复现 = Windows + 全局已装 pyvista，用 `.scratch/noextra_shim/{pyvista,vtk,psutil,pywebview,h5py}.py`（import 即 `raise ImportError`）模拟「只装 .[dev,web]」。

**5. 最小复现步骤**：

```
# 造 shim（import 即失败，模拟 CI 未装 extras）
mkdir -p .scratch/noextra_shim
for m in pyvista vtk psutil pywebview h5py; do
  echo 'raise ImportError("simulated: not installed")' > .scratch/noextra_shim/$m.py
done
cd PlotKit
PYTHONPATH="<abs>/.scratch/noextra_shim;<abs>/PlotKit/src" python tools/check_test_baseline.py   # → exit 1
# 或直接看失败用例：
PYTHONPATH="<abs>/.scratch/noextra_shim;<abs>/PlotKit/src" python -m pytest -o addopts= -q --disable-warnings -rf
# → 4 failed, 501 passed, 7 skipped
```

**4 个失败用例（缺 pyvista 时 ImportError，未加 importorskip 守卫）**：
- `tests/test_ns_physical.py::test_iso_returns_triangles`
- `tests/test_ns_physical.py::test_streamlines_returns_polylines`
- `tests/test_web3d_layers.py::test_volume_surface_returns_mesh`
- `tests/test_web3d_layers.py::test_volume_surface_rejects_empty_level`

**collected 差 35 的来源**：3 个**模块级** `pytest.importorskip("pyvista")` 模块整模块不收集 —— `tests/test_anim3d.py`、`tests/test_multibackend.py`、`tests/test_pyvista_pool.py`。

**分类**：**本机可复现（当且仅当缺少 optional extras 时）**，不是「仅 CI 幽灵」。根因 = 测试套件按「已装 pyvista」的环境编写/钉基线（`reports/test_baseline.json` 钉 `collected=544` / `skipped=[]`），而 CI 只装 `.[dev,web]`。属**环境—基线口径不一致**，非代码业务逻辑错误。

## 10. 结论更新（N0 仍未达成）与待用户决策

- 依 N0 step 5：任一红即**停止 N1–N6**；且明令**「禁止改测试或基线把红抹平，禁止 pytest -k 跳过」**。故本 agent **不自行修改 test / baseline / CI 配置**，停在此交你裁定修复方式。
- 可选修复方向（**均触及计划 step5 红线或 CI 环境，需你批准**）：
  - **R-a** 让 CI 装齐 extras（如 `.[dev,web,three,metrics]` 或 `.[all]`）并解决 pyvista 无头渲染（xvfb/OSMesa）：使环境贴合 544 基线；代价大，且 3D golden 跨 OS 字节易不稳。
  - **R-b** 把测试改成「无 extras 时也收集、缺依赖优雅 skip」（模块级 `importorskip` → 逐用例 `skipif`/运行时守卫；4 个裸 pyvista 用例加 `importorskip`），并把 `reports/test_baseline.json` 钉成**无-extras 环境**的真实值（collected≈509 + 显式 skipped 列表）：这是让「基线 = CI 环境」自洽的根治，但**改测试 + 改基线**（step5 禁止项，需显式豁免）。
  - **R-c** 维持 544 基线，把 CI 换成「装全 extras 且可无头渲染」的镜像；或把 3D/NS 用例在 CI 明确标 skip（需改测试）。
- **需你拍板**：选 R-a / R-b / R-c 或其他；若选 R-b/R-c（涉及改测试或基线），请显式解除 step5 禁令并给出允许改动边界（可改哪些文件、`collected` 常量新值如何认定）。
- 本报告更新**仅文档**：未改任何 test / baseline / CI / 配置；未 push（新 commit 只落本地，X1 授权不跨 HEAD）。

## 11. R-b′ 执行与验证（2026-11-09，用户批准 W-001 后）

- **裁定**：用户否决 R-a、批准修正版 R-b′（m02485）；W-001 事前豁免见 `docs/waivers.md`（§七 已签署批准、§八 记录实现与验证）。
- **生产修复（2 处）**：`src/plotkit/server/app.py` 的 `/api/volume`（`mode=="surface"`）先算 `lv` 并在 `level` 越界时 `raise HTTPException(400, ...)`，之后才 `import pyvista as pv`；`src/plotkit/ns/iso.py` 的 `isosurface()` 先 `_grid_info`（纯 numpy）+ 空结果早返回，之后才 `_image_data`（内部 import pyvista）。无纯 numpy 几何回退。
- **测试守卫（逐用例化）**：`test_anim3d.py`（`import plotkit as pk` + `pytestmark=requires_pyvista`，8 例）、`test_pyvista_pool.py`（3 例）、`test_multibackend.py`（删模块级 importorskip + 8 例 `@requires_pyvista`）、`test_ns_physical.py`（2 例）、`test_web3d_layers.py`（1 例）——共 22 例 pyvista 用例改为「仍被收集、无依赖时运行时 skip」。
- **基线 v2**：`reports/test_baseline.json` → `schema: plotkit.test_baseline/v2`，`collected=544`；profile `dev_full`（Windows/3.13，全 extras，skipped=0）与 `ci_no_extras`（Linux/3.11，五 extras 全 false，`skipped_total=27 / skipped_locations=27`），均 `--write` 机器生成、断言 `failed==0`。**544 常量不变、不放宽为 `>=`。**
- **门禁 v2（`tools/check_test_baseline.py`）**：判据 = `collected==pinned`、`failed==0`、`collected==passed+failed+skipped`（计入 failed，修掉旧公式伪 violation）、`skipped_ids` 集合与 `skipped_total` 均与 profile 一致、禁 xfail/xpass/deselected、pytest exit 0；环境指纹（python/os/五 extras find_spec）不匹配 → 红。另修 `_SKIPPED_RE` 同时取「位置 + 用例数」，解决 path:line 去重集合与用例数量口径打架。
- **自查抓到的门禁缺陷（已修）**：`evaluate()` 的早期错误分支（读基线失败 / schema 不符 / collected 非法 / 指纹不匹配）原先误 `return 0`（假绿），经反向验证 V3 抓出，已全部改为 `return 1`。
- **验证结果**：dev（全 extras）`544 collected / 544 passed / 0 failed`，`profile=dev_full ... ok=True`；无 extras 仿真（faithful shim：`importlib.util.find_spec` 与真实 import 双屏蔽）`544 collected / 517 passed / 27 skipped / 0 failed`，ci profile `evaluate` → OK。四张反向验证 V1（collected 钉 545 vs 544→红）/V2（skipped 集合不符→红）/V3（伪造指纹→红）/V4（无 extras 下 `level=5.0`→400，1 passed）全部符合预期；篡改后 baseline 复原 `cmp` 一致。
- **跨 OS 修正（第一次推送后补）**：`skipped` 位置路径归一化（`\`→`/`），使 Windows 上生成的 `ci_no_extras` profile 能在 Linux CI 精确匹配（首次推送因 `tests\...` vs `tests/...` 集合比对失败，已定位并修）；门禁失败时额外输出 `::error::<违规>`，便于无 token 从 check-runs annotations 读具体原因。
- **ffmpeg 与 +2 跳过（第二次推送后补）**：Linux CI 无 ffmpeg，`tests/test_anim.py:125`/`:139` 两个 mp4 用例按 `shutil.which("ffmpeg")` skip；`ci_no_extras` 重新生成时用 faithful shim 同时屏蔽 `importlib.util.find_spec` 与真实 import（并在生成期令 `shutil.which("ffmpeg")` 返回 None），`skipped_total` 由 27 → **29**；环境指纹新增 `ffmpeg` 布尔。门禁失败注解同时输出 `FAILED <nodeid>` 列表以便定位具体失败用例。

## 12. 交付与后续

- 上述改动（生产 2 文件、测试 5 文件、`tools/check_test_baseline.py`、`reports/test_baseline.json`、`docs/waivers.md`、本报告）将作**本地 commit**（X1 允许本地提交，禁止 push/force-push/rebase/amend/reset）。
- **push 需对新的 HEAD/ref 单独书面授权**：前次授权仅覆盖 `af16001`（指向旧分支头），授权不跨 HEAD 复用（X1）。
- 真 CI 双绿仍需 push 后由 GitHub Actions 确认；**G0 在远端双绿前不自签「达成」**；N1–N6 仍锁。
## 13. 分支首绿（2026-11-09 22:32 +0800）

- 修复 `tests/test_anim.py::test_frames_share_one_viewport`：改为断言「每帧实际显示的坐标范围 == 共用视窗」（读 `render(...,with_limits=True)` 的 `get_xlim/get_ylim`），不再比较两张 PNG 的原始字节（跨平台不稳，Linux CI 曾误报）。仅改测试，未改阈值、未掩盖失败。
- 同步 `reports/test_baseline.json` 的 `ci_no_extras` 跳过行号：`tests/test_anim.py` 跳过行 125/139 → 139/153（测试改写致行号平移；skip 总数仍 29、failed 仍 0，无阈值变化）。
- 提交：`d38b609`（测试）、`96e5a80`（基线行号）。
- 远端 `p0-freeze-2026-11-09 @ 96e5a80`：`plotkit-static-build` success（run 42635485654）、`plotkit-python-tests` **success**（run 42635485655，https://github.com/qgfn106-blip/PlotKit/actions/runs/42635485655）。首次远端全绿，step 1–14（三层 contract/parity/render、能力矩阵、doc sync、reports 漂移门）全部执行并通过。
- 仍待：合并 main 并取 main 首绿（main 现 30779d2，与本地 1cf2570 树等价；需 X1 授权后 merge + FF push）。
