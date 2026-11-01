"""给验收脚本加 JS 错误捕获与画布状态输出。"""
import pathlib

p = pathlib.Path("tools/verify_volume3d.py")
s = p.read_text(encoding="utf-8")

trap = (
    '            win.evaluate_js("window.__err=null;"\n'
    '                            "window.addEventListener(\'error\',function(e){window.__err=\'err:\'+e.message;});"\n'
    '                            "window.addEventListener(\'unhandledrejection\',function(e){'
    'window.__err=\'rej:\'+((e.reason&&e.reason.message)||e.reason);});")\n'
)

if "window.__err=null" not in s:
    s = s.replace('            info["page"] = win.evaluate_js(', trap + '            info["page"] = win.evaluate_js(', 1)

state_js = (
    '                "JSON.stringify({cls: document.body.className,"\n'
    '                " cw: (document.getElementById(\'plot3d\')||{}).width,"\n'
    '                " ch: (document.getElementById(\'plot3d\')||{}).height,"\n'
    '                " err: window.__err})")'
)
old_state = '                " hud: (document.getElementById(\'plot3d-hud\')||{}).textContent,"\n                " err: (window.__err||window.__nsErr||null)})")'
if old_state in s:
    s = s.replace(old_state, state_js, 1)

p.write_text(s, encoding="utf-8")
print("verify script updated")
