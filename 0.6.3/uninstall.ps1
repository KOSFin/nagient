Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$NagientHome = if ($env:NAGIENT_HOME) { $env:NAGIENT_HOME } else { Join-Path $HOME ".nagient" }
$ComposeFile = Join-Path $NagientHome "docker-compose.yml"
$EnvFile = Join-Path $NagientHome ".env"
$Purge = if ($env:NAGIENT_PURGE) { $env:NAGIENT_PURGE } else { "false" }

if (Test-Path $ComposeFile) {
  docker compose -f $ComposeFile --env-file $EnvFile down --remove-orphans
}

if ($Purge -eq "true") {
  Remove-Item -Recurse -Force $NagientHome
  Write-Host "Nagient removed with local state purge."
} else {
  Write-Host "Containers removed. Local files kept in $NagientHome."
}

