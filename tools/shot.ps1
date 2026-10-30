# 无头 Edge 截图 / 取 DOM（Windows 专用）
#
# 为什么需要它：直接在本机调用 msedge.exe 时，如果用户已经开着 Edge，
# 新进程会把命令行转交给已有实例然后**立刻退出**（exit 0、无输出、无截图）。
# 必须用 Start-Process 起独立进程 + 独立 --user-data-dir + --no-sandbox。
#
# 用法：
#   powershell -File tools/shot.ps1 -Url http://127.0.0.1:8791/ -Out shot.png
#   powershell -File tools/shot.ps1 -Url http://127.0.0.1:8791/ -Out shot.png -Width 1400 -Height 900
#   powershell -File tools/shot.ps1 -Url http://127.0.0.1:8791/ -Dom dom.html

param(
    [Parameter(Mandatory = $true)][string]$Url,
    [string]$Out = "",
    [string]$Dom = "",
    [int]$Width = 1400,
    [int]$Height = 900,
    [int]$BudgetMs = 9000
)

$ErrorActionPreference = "Stop"

$exe = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path $exe)) { throw "找不到 Edge：$exe" }

# Windows 环境里 HTTPS_PROXY 与 https_proxy 同时存在时，Start-Process 会报
# “已添加项。字典中的关键字:HTTPS_PROXY”，必须先删掉重复项。
Remove-Item Env:https_proxy -ErrorAction SilentlyContinue
Remove-Item Env:http_proxy -ErrorAction SilentlyContinue

$profileDir = Join-Path $env:TEMP ("edge-pk-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$args = @(
    "--headless=new", "--no-sandbox", "--disable-gpu", "--no-first-run",
    "--user-data-dir=$profileDir",
    "--window-size=$Width,$Height",
    "--virtual-time-budget=$BudgetMs"
)

if ($Out) {
    Remove-Item $Out -ErrorAction SilentlyContinue
    $args += "--screenshot=$Out"
}
if ($Dom) {
    Remove-Item $Dom -ErrorAction SilentlyContinue
    $args += "--dump-dom"
}
$args += $Url

if ($Dom) {
    $p = Start-Process -FilePath $exe -ArgumentList $args -RedirectStandardOutput $Dom -PassThru -Wait
} else {
    $p = Start-Process -FilePath $exe -ArgumentList $args -PassThru -Wait
}

Remove-Item $profileDir -Recurse -Force -ErrorAction SilentlyContinue

if ($p.ExitCode -ne 0) { throw "Edge 退出码 $($p.ExitCode)" }
if ($Out) {
    if (-not (Test-Path $Out)) { throw "截图没生成：$Out" }
    "screenshot: $Out ($((Get-Item $Out).Length) bytes)"
}
if ($Dom) {
    if (-not (Test-Path $Dom)) { throw "DOM 没生成：$Dom" }
    "dom: $Dom ($((Get-Item $Dom).Length) bytes)"
}
