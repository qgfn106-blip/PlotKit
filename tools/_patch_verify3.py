"""把 state 的 JS 表达式压成单行（多行字符串在 JS 里是非法换行）。"""
import pathlib
import re

p = pathlib.Path("tools/verify_volume3d.py")
s = p.read_text(encoding="utf-8")

start = s.index('            info["state"] = win.evaluate_js(')
end = s.index('            info["state2"] = win.evaluate_js(')
one = (
    '            info["state"] = win.evaluate_js("JSON.stringify({cls: document.body.className, '
    'cw: (document.getElementById(\'plot3d\') || {}).width, '
    'ch: (document.getElementById(\'plot3d\') || {}).height, err: window.__err})")\n'
)
s = s[:start] + one + s[end:]
p.write_text(s, encoding="utf-8")
print("state js one-lined")
