param(
    [string]$Project = ""
)

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location -LiteralPath $ProjectRoot

if ($Project -eq "") {
    .\.venv\Scripts\python.exe scripts\gee\export_zhaling_eling_yearly_stats.py
} else {
    .\.venv\Scripts\python.exe scripts\gee\export_zhaling_eling_yearly_stats.py --project $Project
}

Write-Host ""
Write-Host "任务启动后，可查看状态："
Write-Host ".\.venv\Scripts\python.exe -m ee.cli.eecli task list"
Read-Host "按 Enter 退出"
