# 浏览器 3D 图层：`volume` 与 `particles`

三维数据不必都走服务端渲染。PlotKit 现在有两个"浏览器直绘"图层：
spec 里写一份图层，前端用 WebGL2 画，服务端只负责把数据打成二进制帧。

```python
import numpy as np, plotkit as pk

n = 40
x = np.linspace(-1, 1, n); y = np.linspace(-1, 1, n); z = np.linspace(-1, 1, n)
X, Y, Z = np.meshgrid(x, y, z, indexing="ij")
blob = np.exp(-(X**2 + Y**2 + Z**2) / 0.25)
field = np.transpose(blob, (2, 1, 0))          # (nz, ny, nx)，x 变化最快

fig = pk.figure()
fig.add_data("x", x); fig.add_data("y", y); fig.add_data("z", z)
fig.add_data("f", field, role="field")
fig.add("volume", {"x": "x", "y": "y", "z": "z", "values": "f"})   # 标量场
fig.add("particles", {"x": "x", "y": "y", "z": "z", "c": "c"})     # 时空点云（c 可选，逐点着色）
```

网页里点「3D」即进入三维视图；体积/粒子与既有的点云、曲面、时间轴、框选共存。

## 两条数据通路

| 图层 | 端点 | 载荷 |
| --- | --- | --- |
| `volume`（默认） | `GET /api/volume?x=&y=&z=&values=` | `PK01 + meta_len + n + meta + float32`（(nz,ny,nx)） |
| `volume`（等值面） | `GET /api/volume?...&mode=surface&level=` | 与 `/api/mesh` 同构：`PK01 + meta_len + nvert + ntri + meta + 顶点 + 法线 + 索引` |
| `particles` | `GET /api/particles?x=&y=&y=&c=` | `PK01 + meta_len + n + meta + xyz(f32) + 标量(f32)` |

`mode=surface` 用服务端 marching cubes（VTK `contour`）抽等值面，**复用浏览器已验证的 mesh 渲染路径**——比在着色器里做 raymarch 稳得多，而且带光照。

## 踩过的坑（都真实发生过）

1. **颜色必须给 4 个分量**。`setLayers` 里 `uniform4fv(uColor, layer.color)`，只传 `[r,g,b]` 时 alpha 取到未定义值 → 整层透明，画面里"什么都没画"，而 `getError()` 还是 0。
2. **R32F 纹理不能线性过滤**。WebGL2 里 32 位浮点纹理要 `OES_texture_float_linear` 才能 LINEAR，否则采样恒为 0 → 密度算成 0 → 全片 `discard`。要么用 `RG16F`，要么 `NEAREST`。
3. **`uvicorn` 的 `port=0` 不等于"拿到随机端口"**。`config.port` 仍是 0，得从 `server.servers[0].sockets[0].getsockname()[1]` 取。
4. **隐藏窗口不出图**。pywebview `hidden=True` 时 `requestAnimationFrame` 被挂起，`fps=null`、画面全黑——自动化验收必须开可见窗口。
5. **`toDataURL` 只截 WebGL canvas**，不含 HTML 叠层；叠层状态得另外读 DOM。

## 验收脚本

```
PYTHONPATH=src python tools/verify_volume3d.py      # 40³ 高斯场 + 2 万点螺旋，出 docs/web3d_volume.png
```

脚本自己起 uvicorn + pywebview，点 `#btn-3d`、等 8 s、抓 canvas、回读 `window.__err`，并在控制台打印一份 JSON 体检结果。
