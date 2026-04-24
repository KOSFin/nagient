Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DefaultChannel = "__NAGIENT_DEFAULT_CHANNEL__"
$DefaultUpdateBaseUrl = "__NAGIENT_UPDATE_BASE_URL__"

$NagientHome = if ($env:NAGIENT_HOME) { $env:NAGIENT_HOME } else { Join-Path $HOME ".nagient" }
$Channel = if ($env:NAGIENT_CHANNEL) { $env:NAGIENT_CHANNEL } else { $DefaultChannel }
$UpdateBaseUrl = if ($env:NAGIENT_UPDATE_BASE_URL) { $env:NAGIENT_UPDATE_BASE_URL } else { $DefaultUpdateBaseUrl }
$ComposeFile = Join-Path $NagientHome "docker-compose.yml"
$EnvFile = Join-Path $NagientHome ".env"
$CurrentManifest = Join-Path $NagientHome "releases/current.json"

New-Item -ItemType Directory -Force -Path (Join-Path $NagientHome "bin"), (Join-Path $NagientHome "releases") | Out-Null

if ($UpdateBaseUrl -eq "__NAGIENT_UPDATE_BASE_URL__") {
  throw "NAGIENT_UPDATE_BASE_URL is not configured. Use a released updater asset or set the variable explicitly."
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
