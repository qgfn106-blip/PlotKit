"""临时基准：批量端点串行 vs 4 worker。"""

import io
import time
import zipfile

import numpy as np

import plotkit as pk
from fastapi.testclient import TestClient
from plotkit.server.app import create_app


def main() -> None:
    fig3 = pk.ns.scene.figure(t=0.05, n=32, particles=4000, streamlines=6)
    x = np.linspace(-2, 2, 40)
    y = np.linspace(-2, 2, 40)
    X, Y = np.meshgrid(x, y)
    Z = np.sin(np.hypot(X, Y) * 2) / (1 + np.hypot(X, Y))
    fig = fig3
    if False:
        fig.add_data("sx", x)
        fig.add_data("sy", y)
        fig.add_data("sz", Z)
        fig.add("surface", {"x": "sx", "y": "sy", "z": "sz"})
    api = TestClient(create_app(fig))
    body = {"width": 1200, "height": 900, "frames": [{"spec": fig.spec}] * 24}

    for w in (1, 4):
        t0 = time.perf_counter()
        res = api.post("/api/render3d/batch", json={**body, "workers": w})
        dt = time.perf_counter() - t0
        if res.status_code == 200:
            names = zipfile.ZipFile(io.BytesIO(res.content)).namelist()
            print(f"workers={w}: {dt:.2f}s frames={len(names)}")
        else:
            print(f"workers={w}: {dt:.2f}s status={res.status_code} {res.text[:160]}")


if __name__ == "__main__":
    main()
