"""静态资源：vendored plotly bundle（零 CDN）+ 自包含 HTML 生成。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
VENDOR_DIR = STATIC_DIR / "vendor"
PLOTLY_BUNDLE = VENDOR_DIR / "plotly-basic.min.js"


@lru_cache(maxsize=1)
def plotly_source() -> str:
    if not PLOTLY_BUNDLE.exists():
        raise FileNotFoundError(
            f"缺少 vendored plotly bundle: {PLOTLY_BUNDLE}\n"
            "离线环境请把 plotly-basic.min.js 放进 plotkit/static/vendor/"
        )
    return PLOTLY_BUNDLE.read_text(encoding="utf-8")


def self_contained_html(
    figure: Mapping[str, Any],
    *,
    title: str = "PlotKit",
    height: int | None = None,
) -> str:
    """把 {data, layout} 与 plotly bundle 一起内联成单个 HTML（无网络也能看）。"""
    payload = json.dumps(figure, ensure_ascii=False).replace("</", "<\\/")
    height_style = f"height:{int(height)}px" if height else "height:100vh"
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{title}</title>
<style>
  html,body{{margin:0;padding:0;background:#fff;font-family:system-ui,"Microsoft YaHei",sans-serif}}
  #plot{{{height_style};width:100%}}
</style></head>
<body><div id="plot"></div>
<script>{plotly_source()}</script>
<script>
  const FIG = {payload};
  const el = document.getElementById('plot');
  Plotly.newPlot(el, FIG.data, FIG.layout, {{responsive: true, displaylogo: false}});
  window.addEventListener('resize', () => Plotly.Plots.resize(el));
</script>
</body></html>"""
