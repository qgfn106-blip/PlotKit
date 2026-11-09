# N0 远端首绿 · 诊断报告（未达成 · 阻塞待用户决策）

> 阶段：N0（远端 CI 首次绿灯，唯一硬阻塞）
> 时间窗：2026-11-09 17:33–17:39 +0800
> 执行：lead（本地诊断，未 push）
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
