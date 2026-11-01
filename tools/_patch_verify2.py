"""修正验收脚本里的 JS 注入（转义把语法写坏了）。"""
import pathlib

p = pathlib.Path("tools/verify_volume3d.py")
s = p.read_text(encoding="utf-8")

start = s.index('            win.evaluate_js("window.__err=null;"')
end = s.index('            info["page"] = win.evaluate_js(')
clean = (
    '            win.evaluate_js("window.__err = null;")\n'
    '            win.evaluate_js("window.onerror = function (m) { window.__err = String(m); };")\n'
    '            win.evaluate_js(\n'
    '                "window.addEventListener(\\"unhandledrejection\\", function (e) {"\n'
    '                " window.__err = String((e.reason && e.reason.message) || e.reason); });")\n'
)
s = s[:start] + clean + s[end:]
p.write_text(s, encoding="utf-8")
print("cleaned")
