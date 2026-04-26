Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DefaultChannel = "__NAGIENT_DEFAULT_CHANNEL__"
$DefaultUpdateBaseUrl = "__NAGIENT_UPDATE_BASE_URL__"
$UnrenderedUpdateBaseUrlToken = "__NAGIENT_" + "UPDATE_BASE_URL__"

$NagientHome = if ($env:NAGIENT_HOME) { $env:NAGIENT_HOME } else { Join-Path $HOME ".nagient" }
$Channel = if ($env:NAGIENT_CHANNEL) { $env:NAGIENT_CHANNEL } else { $DefaultChannel }
$UpdateBaseUrl = if ($env:NAGIENT_UPDATE_BASE_URL) {
  $env:NAGIENT_UPDATE_BASE_URL
} elseif ($env:UPDATE_BASE_URL) {
  $env:UPDATE_BASE_URL
} else {
  $DefaultUpdateBaseUrl
}
$ComposeFile = Join-Path $NagientHome "docker-compose.yml"
$EnvFile = Join-Path $NagientHome ".env"
$CurrentManifest = Join-Path $NagientHome "releases/current.json"

New-Item -ItemType Directory -Force -Path (Join-Path $NagientHome "bin"), (Join-Path $NagientHome "releases") | Out-Null

function Test-UnrenderedUpdateBaseUrl {
  param([string]$Value)
  return $Value -like "*$UnrenderedUpdateBaseUrlToken*"
}

if (
  [string]::IsNullOrWhiteSpace($UpdateBaseUrl) -or (
    (Test-UnrenderedUpdateBaseUrl $DefaultUpdateBaseUrl) -and
    (Test-UnrenderedUpdateBaseUrl $UpdateBaseUrl)
  )
) {
  throw "NAGIENT_UPDATE_BASE_URL is not configured. Use a rendered updater asset or set NAGIENT_UPDATE_BASE_URL/UPDATE_BASE_URL explicitly."
}

if ($Channel -eq "__NAGIENT_DEFAULT_CHANNEL__") {
  $Channel = "stable"
}

function Get-JsonField {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Field
  )

  $json = Get-Content -Raw -Path $Path | ConvertFrom-Json
  $current = $json
  foreach ($chunk in $Field.Split(".")) {
    $current = $current.$chunk
  }
  return $current
}

function Get-ArtifactUrl {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Name
  )

  $json = Get-Content -Raw -Path $Path | ConvertFrom-Json
  $artifact = $json.artifacts | Where-Object { $_.name -eq $Name } | Select-Object -First 1
  if (-not $artifact) {
    throw "Artifact not found: $Name"
  }
  return $artifact.url
}

function Write-NagientCtl {
  $target = Join-Path $NagientHome "bin/nagientctl.ps1"
  @'
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$NagientHome = if ($env:NAGIENT_HOME) { $env:NAGIENT_HOME } else { Join-Path $HOME ".nagient" }
$ComposeFile = Join-Path $NagientHome "docker-compose.yml"
$EnvFile = Join-Path $NagientHome ".env"
$Service = if ($env:NAGIENT_SERVICE) { $env:NAGIENT_SERVICE } else { "nagient" }

function Show-Usage {
  @"
Usage: nagientctl <command>

Commands:
  up|start           Start runtime container
  down|stop          Stop runtime container
  restart            Restart runtime container
  status             Show container state and nagient status
  doctor             Show effective settings
  preflight          Run config validation
  reconcile          Run activation cycle
  logs [service]     Stream logs (default: nagient)
  shell              Open shell in runtime container
  exec <cmd...>      Execute command in runtime container
  update             Run installed updater
  remove|uninstall   Run installed uninstaller
  help               Show this help
"@ | Write-Host
}

function Assert-ComposeFiles {
  if (-not (Test-Path $ComposeFile) -or -not (Test-Path $EnvFile)) {
    throw "Nagient runtime is not initialized in $NagientHome. Run install first: irm https://ngnt-in.ruka.me/install.ps1 | iex"
  }
}

function Compose {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ComposeArgs)
  docker compose -f $ComposeFile --env-file $EnvFile @ComposeArgs
}

$Command = if ($args.Count -gt 0) { $args[0].ToLowerInvariant() } else { "help" }
$Rest = if ($args.Count -gt 1) { $args[1..($args.Count - 1)] } else { @() }

switch ($Command) {
  { $_ -in @("up", "start") } {
    Assert-ComposeFiles
    Compose up -d
    break
  }
  { $_ -in @("down", "stop") } {
    Assert-ComposeFiles
    Compose down --remove-orphans
    break
  }
  "restart" {
    Assert-ComposeFiles
    Compose down --remove-orphans
    Compose up -d
    break
  }
  "status" {
    Assert-ComposeFiles
    Compose ps
    Compose exec $Service nagient status --format text
    break
  }
  "doctor" {
    Assert-ComposeFiles
    Compose exec $Service nagient doctor --format text
    break
  }
  "preflight" {
    Assert-ComposeFiles
    Compose exec $Service nagient preflight --format text
    break
  }
  "reconcile" {
    Assert-ComposeFiles
    Compose exec $Service nagient reconcile --format text
    break
  }
  "logs" {
    Assert-ComposeFiles
    if ($Rest.Count -eq 0) {
      $Rest = @($Service)
    }
    Compose logs -f @Rest
    break
  }
  "shell" {
    Assert-ComposeFiles
    Compose exec $Service sh
    break
  }
  "exec" {
    Assert-ComposeFiles
    if ($Rest.Count -eq 0) {
      throw "Usage: nagientctl exec <cmd...>"
    }
    Compose exec $Service @Rest
    break
  }
  "update" {
    & (Join-Path $NagientHome "bin/nagient-update.ps1")
    break
  }
  { $_ -in @("remove", "uninstall") } {
    & (Join-Path $NagientHome "bin/nagient-uninstall.ps1")
    break
  }
  { $_ -in @("help", "-h", "--help") } {
    Show-Usage
    break
  }
  default {
    throw "Unknown command: $Command"
  }
}
'@ | Set-Content -Path $target -Encoding utf8
}

if (-not (Test-Path $CurrentManifest)) {
  throw "Current release manifest is missing."
}

$channelPayload = Join-Path ([System.IO.Path]::GetTempPath()) "nagient-channel.json"
$manifestPayload = Join-Path ([System.IO.Path]::GetTempPath()) "nagient-manifest.json"

$currentVersion = Get-JsonField -Path $CurrentManifest -Field "version"
Invoke-WebRequest -UseBasicParsing -Uri "$($UpdateBaseUrl.TrimEnd('/'))/channels/$Channel.json" -OutFile $channelPayload
$manifestUrl = Get-JsonField -Path $channelPayload -Field "manifest_url"
Invoke-WebRequest -UseBasicParsing -Uri $manifestUrl -OutFile $manifestPayload

$targetVersion = Get-JsonField -Path $manifestPayload -Field "version"
if ($currentVersion -eq $targetVersion) {
  Write-Host "Nagient is already on $currentVersion"
  exit 0
}

$composeUrl = Get-JsonField -Path $manifestPayload -Field "docker.compose_url"
$image = Get-JsonField -Path $manifestPayload -Field "docker.image"
$updateUrl = Get-ArtifactUrl -Path $manifestPayload -Name "update.ps1"
$uninstallUrl = Get-ArtifactUrl -Path $manifestPayload -Name "uninstall.ps1"
Invoke-WebRequest -UseBasicParsing -Uri $composeUrl -OutFile $ComposeFile
Invoke-WebRequest -UseBasicParsing -Uri $updateUrl -OutFile (Join-Path $NagientHome "bin/nagient-update.ps1")
Invoke-WebRequest -UseBasicParsing -Uri $uninstallUrl -OutFile (Join-Path $NagientHome "bin/nagient-uninstall.ps1")
Write-NagientCtl
Copy-Item -Force -Path $manifestPayload -Destination $CurrentManifest

@"
NAGIENT_IMAGE=$image
NAGIENT_CHANNEL=$Channel
NAGIENT_UPDATE_BASE_URL=$UpdateBaseUrl
NAGIENT_CONTAINER_NAME=nagient
NAGIENT_DOCKER_PROJECT_NAME=nagient
"@ | Set-Content -Path $EnvFile -Encoding utf8

docker compose -f $ComposeFile --env-file $EnvFile pull
docker compose -f $ComposeFile --env-file $EnvFile up -d

Write-Host "Nagient upgraded: $currentVersion -> $targetVersion"
