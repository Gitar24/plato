# Como usar: .\run.ps1 service  ou  .\run.ps1 pet
# Roda sem Docker, com as variáveis do .env desta pasta.
param([ValidateSet("service","pet")][string]$What = "service")
$root = $PSScriptRoot
$py = "$env:USERPROFILE\.local\venvs\plato\Scripts\python.exe"
Get-Content "$root\.env" | Where-Object { $_ -match '^\s*[^#\s][^=]*=' } | ForEach-Object {
    $k, $v = $_ -split '=', 2
    Set-Item "env:$($k.Trim())" $v.Trim()
}
if ($What -eq "service") {
    $env:CONFIG_PATH = "$root\config\config.json"
    $env:DATA_DIR = "$root\data"
    $env:VAULT_PATH = $env:OBSIDIAN_VAULT_PATH
    Set-Location "$root\service"
    & $py -u app.py
} else {
    Set-Location "$root\pet"
    & $py main.py
}
