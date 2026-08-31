#Requires -Version 7
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
python -m adash ingest @args
exit $LASTEXITCODE
