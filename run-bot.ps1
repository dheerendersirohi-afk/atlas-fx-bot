param(
    [switch]$Open,
    [switch]$StartBot
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$entryFile = Join-Path $root "web\index.html"

if (-not (Test-Path $entryFile)) {
    throw "App entry file not found at $entryFile"
}

$resolved = (Resolve-Path $entryFile).Path
Write-Host "Atlas FX Bot entry file:"
Write-Host $resolved
Write-Host ""
Write-Host "Open this file in any browser to run the local paper-trading dashboard."

if ($Open) {
    $target = $resolved
    if ($StartBot) {
        $target = ([System.Uri]$resolved).AbsoluteUri + "#start"
    }
    Start-Process $target
}
