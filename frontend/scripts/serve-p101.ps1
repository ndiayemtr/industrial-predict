# Dedicated future demo launcher; normal DEV commands/proxy stay unchanged.
$ErrorActionPreference = 'Stop'
$frontendRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $frontendRoot
try {
    if (-not (Test-Path -LiteralPath 'node_modules/@angular/cli/bin/ng.js' -PathType Leaf)) {
        throw 'Existing Angular CLI installation required; no download is authorized automatically.'
    }
    & node node_modules/@angular/cli/bin/ng.js serve --configuration development --host 127.0.0.1 --port 4201 --proxy-config proxy.p101.conf.json
    if ($LASTEXITCODE -ne 0) { throw 'P101 Angular demo server failed.' }
}
finally {
    Pop-Location
}
