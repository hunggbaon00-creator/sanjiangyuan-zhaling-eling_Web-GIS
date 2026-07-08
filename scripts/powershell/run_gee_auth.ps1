$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location -LiteralPath $ProjectRoot
.\.venv\Scripts\python.exe -m ee.cli.eecli authenticate --auth_mode=localhost:0
Write-Host ""
Write-Host "授权流程结束后，请运行："
Write-Host ".\.venv\Scripts\python.exe scripts\gee\gee_auth_check.py"
Read-Host "按 Enter 退出"
