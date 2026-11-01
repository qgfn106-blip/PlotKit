# 安装 · 更新 · 卸载

> 一句话：**只需要 `numpy`+`matplotlib`+`pillow` 就能画二维图**；浏览器界面、三维、桌面壳各自是可选依赖，按需装。

## 1. 环境要求

| 项目 | 要求 | 说明 |
| --- | --- | --- |
| Python | **≥ 3.10** | 3.10 / 3.11 / 3.12 / 3.13 都在 CI 和本机验过 |
| numpy | ≥ 1.23 | 2.x 也可以 |
| matplotlib | ≥ 3.6 | 3.6–3.10 已验；**3.9+ 删除了 `cm.get_cmap`**，本项目已用 `plotkit._compat.get_cmap` 兜住 |
| pillow | ≥ 9.0 | 只用于 PNG 编码 |

可选依赖：

| 功能 | extra | 装进来的包 |
| --- | --- | --- |
| 浏览器界面 / HTTP 服务 | `web` | fastapi, uvicorn |
| 桌面壳（WebView2 / GTK / WKWebView） | `desktop` | pywebview |
| 三维（PyVista/VTK） | `three` | pyvista（自带 vtk 约束，**不要自己 pin vtk**） |
| 进程池 / 内存诊断 | `metrics` | psutil |
| 开发（测试 + lint） | `dev` | pytest, httpx, ruff |

> 历史文档里出现过 `plotkit[server]`、`plotkit[mpl]`，这两个名字保留为别名，等价于 `web` / `matplotlib`，不会报错。

## 2. 安装

```bash
# 最小安装（只画二维图）
pip install plotkit

# 常用组合：二维 + 浏览器界面 + 三维
pip install "plotkit[web,three]"

# 全量
pip install "plotkit[all]"
```

从源码开发（就是本仓库）：

```bash
git clone https://github.com/weijiewang/plotkit.git
cd plotkit
pip install -e ".[all,dev]"
```

> **装完第一件事**：`plotkit doctor`。它会打印 Python 与每个依赖的实际版本、满足/不满足的条目、可选功能是否可用。

```bash
$ plotkit doctor
python   3.13.9
numpy    2.3.5     需要 >= 1.23  OK
...
[web    ] 可用
[three  ] 可用
[desktop] 可用
结论：环境满足要求
```

`plotkit doctor --json` 输出机器可读结果，方便写进 CI 或工单。

## 3. 更新

```bash
pip install -U plotkit                # 升级到最新
pip install -U "plotkit[all]"         # 连同可选依赖一起升
pip install -U numpy matplotlib       # 只升底层库（一般不需要）
plotkit doctor                        # 升完再体检一次
```

`pip` 只会替换包本体，**不会删除**运行时生成的缓存目录（见下节）。

## 4. 卸载

```bash
plotkit uninstall          # 只列缓存目录，不动任何东西
plotkit uninstall --yes    # 删掉缓存目录
pip uninstall -y plotkit   # 卸载包本体
```

缓存目录（`pip uninstall` 不会碰，需要手动清）：

- `~/.plotkit-desktop/` —— 桌面壳的 WebView2 配置/缓存
- `~/.plotkit/` —— 其它运行时缓存

如果你是用 `pip install -e .` 开发安装，卸载同样是 `pip uninstall plotkit`，然后自行删除克隆目录。

## 5. 依赖版本兼容性（踩过的坑）

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `AttributeError: module 'matplotlib.cm' has no attribute 'get_cmap'` | matplotlib ≥ 3.9 删除了该函数，用户脚本或旧版本 plotkit 直接调用 | 升级 plotkit（≥0.2.0 内部走 `_compat.get_cmap`）；自己的代码改用 `matplotlib.colormaps[name]` |
| `AttributeError: module 'numpy' has no attribute 'trapz'` | numpy ≥ 2.0 删除 `np.trapz` | `plotkit._compat.trapezoid` 自动选 `np.trapezoid` / `np.trapz` |
| 装 `three` 后 import 报 VTK 版本冲突 | vtk 由 pyvista 约束（例：pyvista 0.49.2 → vtk 9.7.1） | **不要单独 `pip install vtk==x.y.z`**，让 pyvista 自己解析；必要时 `pip install "pyvista>=0.44,<0.50"` |
| `pywebview` 在 Linux 上起不来 | 需要 GTK（`python3-gi`）或 Qt 后端 | `apt install python3-gi gir1.2-webkit2-4.1`，或设 `PYWEBVIEW_GUI=qt` 并装 PyQt5 |
| WSL 里开窗口报 `no display` | WSL 默认无 X/Wayland | 用 `--shot out.png`（离屏截图）或配 WSLg / `DISPLAY=:0` |
| 桌面壳打包体积 | 不打包 Chromium，用系统 WebView2 | Windows 需系统装有 WebView2 Runtime（Win11 自带） |
| `plotkit doctor` 说 `python 3.9 不满足` | requires-python ≥3.10 | 换 3.10+ 解释器；或 `pipx install --python 3.11 plotkit` |

## 6. 离线 / 内网安装

在有网机器上：

```bash
pip download "plotkit[all]" -d wheels/          # 连同可选依赖一起下
```

在目标机器上：

```bash
pip install --no-index --find-links wheels/ "plotkit[all]"
```

三维的 vtk 轮子较大（约 100 MB），如果目标机器只需要二维，直接用 `pip download plotkit` 只下核心三个依赖即可。

## 7. 多环境常见疑问

- **“我 `pip install` 了但 `import plotkit` 还是旧版”** → `plotkit where` 看实际加载路径；通常是装到了另一个 Python（conda base vs venv）。
- **“同时装了多个版本”** → `pip list | grep plotkit`，用 `python -m pip install -U --force-reinstall plotkit` 或不加 `-U` 的干净重装。
- **conda 环境** → `conda install numpy matplotlib pillow` 再用 `pip install plotkit`（gevent/vtk 这类库用 conda 装更稳）。
