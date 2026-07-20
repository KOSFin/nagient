param(
  [string]$Home = $(if ($env:NAGIENT_HOME) { $env:NAGIENT_HOME } else { Join-Path $HOME ".nagient" }),
  [string]$Source = (Split-Path -Parent $PSScriptRoot | Split-Path -Parent),
  [string]$Python = $(if ($env:NAGIENT_PYTHON) { $env:NAGIENT_PYTHON } else { "python" }),
  [switch]$NoStart
)

$ErrorActionPreference = "Stop"
& $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 or newer is required. Docker is not used by this installer." }

$venv = Join-Path $Home "venv"
New-Item -ItemType Directory -Force -Path $Home | Out-Null
if (-not (Test-Path (Join-Path $venv "Scripts/python.exe"))) { & $Python -m venv $venv }
& (Join-Path $venv "Scripts/python.exe") -m pip install --no-deps --quiet --upgrade $Source
$env:NAGIENT_HOME = $Home
& (Join-Path $venv "Scripts/nagient.exe") init --force --format json | Out-Null

$bin = Join-Path $Home "bin"
New-Item -ItemType Directory -Force -Path $bin, (Join-Path $Home "logs") | Out-Null
$launcher = Join-Path $bin "nagient.ps1"
@"
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$CommandArgs)
$ErrorActionPreference = "Stop"
$python = "$(Join-Path $venv "Scripts/python.exe")"
if ($CommandArgs.Count -gt 0 -and ($CommandArgs[0] -eq "up" -or $CommandArgs[0] -eq "start")) {
  Start-Process -FilePath $python -ArgumentList "-m nagient serve" -WorkingDirectory "$Home" -RedirectStandardOutput "$(Join-Path $Home "logs/runtime.log")"
} else {
  & $python -m nagient @$CommandArgs
}
"@ | Set-Content -Encoding UTF8 $launcher

if (-not $NoStart) { & powershell -ExecutionPolicy Bypass -File $launcher up }
Write-Host "Nagient installed without Docker in $Home"
Write-Host "Add $bin to PATH, then run: nagient setup"
