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

function Write-Step {
  param([Parameter(Mandatory = $true)][string]$Message)
  Write-Host "[nagient] $Message"
}

function Write-NagientCtl {
  $target = Join-Path $NagientHome "bin/nagientctl.ps1"
  $launcher = @'
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProgramName = [System.IO.Path]::GetFileNameWithoutExtension($MyInvocation.MyCommand.Name)
$NagientHome = if ($env:NAGIENT_HOME) { $env:NAGIENT_HOME } else { Join-Path $HOME ".nagient" }
$ComposeFile = Join-Path $NagientHome "docker-compose.yml"
$EnvFile = Join-Path $NagientHome ".env"
$Service = if ($env:NAGIENT_SERVICE) { $env:NAGIENT_SERVICE } else { "nagient" }
$ConfigFile = Join-Path $NagientHome "config.toml"
$SecretsFile = Join-Path $NagientHome "secrets.env"
$ToolSecretsFile = Join-Path $NagientHome "tool-secrets.env"
$WorkspaceDir = Join-Path $NagientHome "workspace"
$LogDir = Join-Path $NagientHome "logs"

function Show-Usage {
  @"
Usage: $ProgramName <command>

Commands:
  status|st          Show compact runtime status
  doctor|cfg         Show detailed runtime diagnostics
  paths|config       Show local config and workspace paths
  ps                 Show raw docker compose status
  up|start           Start runtime container
  down|stop          Stop runtime container
  restart            Restart runtime container
  preflight|check    Run config validation
  reconcile|fix      Run activation cycle
  logs|log [svc]     Stream logs (default: nagient)
  shell|sh           Open shell in runtime container
  exec|x <cmd...>    Execute command in runtime container
  update             Run installed updater
  remove|uninstall   Run installed uninstaller
  help               Show this help
  <other command>    Pass through to the in-container nagient CLI
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

function Compose-ExecNagient {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CommandArgs)
  Compose exec `
    -e "NAGIENT_HOST_HOME=$NagientHome" `
    -e "NAGIENT_HOST_CONFIG_FILE=$ConfigFile" `
    -e "NAGIENT_HOST_SECRETS_FILE=$SecretsFile" `
    -e "NAGIENT_HOST_TOOL_SECRETS_FILE=$ToolSecretsFile" `
    -e "NAGIENT_HOST_WORKSPACE_DIR=$WorkspaceDir" `
    $Service @CommandArgs
}

function Show-Paths {
  @"
Nagient home: $NagientHome
Config: $ConfigFile
Secrets: $SecretsFile
Tool secrets: $ToolSecretsFile
Workspace: $WorkspaceDir
Logs: $LogDir
"@ | Write-Host
}

$Command = if ($args.Count -gt 0) { $args[0].ToLowerInvariant() } else { "help" }
$Rest = if ($args.Count -gt 1) { $args[1..($args.Count - 1)] } else { @() }

switch ($Command) {
  { $_ -in @("status", "st") } {
    Assert-ComposeFiles
    Compose-ExecNagient nagient status --format text @Rest
    break
  }
  { $_ -in @("doctor", "cfg") } {
    Assert-ComposeFiles
    Compose-ExecNagient nagient doctor --format text @Rest
    break
  }
  { $_ -in @("paths", "config") } {
    Show-Paths
    break
  }
  "ps" {
    Assert-ComposeFiles
    Compose ps
    break
  }
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
  { $_ -in @("preflight", "check") } {
    Assert-ComposeFiles
    Compose-ExecNagient nagient preflight --format text @Rest
    break
  }
  { $_ -in @("reconcile", "fix") } {
    Assert-ComposeFiles
    Compose-ExecNagient nagient reconcile --format text @Rest
    break
  }
  { $_ -in @("logs", "log") } {
    Assert-ComposeFiles
    if ($Rest.Count -eq 0) {
      $Rest = @($Service)
    }
    Compose logs -f @Rest
    break
  }
  { $_ -in @("shell", "sh") } {
    Assert-ComposeFiles
    Compose exec $Service sh
    break
  }
  { $_ -in @("exec", "x") } {
    Assert-ComposeFiles
    if ($Rest.Count -eq 0) {
      throw "Usage: $ProgramName exec <cmd...>"
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
    Assert-ComposeFiles
    Compose-ExecNagient nagient $Command @Rest
  }
}
'@
  $launcher | Set-Content -Path $target -Encoding utf8
  $launcher | Set-Content -Path (Join-Path $NagientHome "bin/nagient.ps1") -Encoding utf8
}

function Invoke-ComposeUpdateStep {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ComposeArgs)

  $logPath = New-TemporaryFile
  & docker compose -f $ComposeFile --env-file $EnvFile @ComposeArgs 2>&1 | Tee-Object -FilePath $logPath | Out-Host
  $exitCode = $LASTEXITCODE
  $output = (Get-Content -Raw -Path $logPath).Trim()
  Remove-Item -Force -Path $logPath
  if ($exitCode -ne 0) {
    if (-not [string]::IsNullOrWhiteSpace($output)) {
      Write-Error $output
    }
    if ($output -like "*no matching manifest*" -and $output -like "*arm64*") {
      throw "The published Docker image does not include an arm64 variant yet. Temporary workaround on Apple Silicon:`nDOCKER_DEFAULT_PLATFORM=linux/amd64 ~/.nagient/bin/nagient-update"
    }
    throw "Docker Compose failed."
  }
}

if (-not (Test-Path $CurrentManifest)) {
  throw "Current release manifest is missing."
}

$channelPayload = Join-Path ([System.IO.Path]::GetTempPath()) "nagient-channel.json"
$manifestPayload = Join-Path ([System.IO.Path]::GetTempPath()) "nagient-manifest.json"

$currentVersion = Get-JsonField -Path $CurrentManifest -Field "version"
Write-Step "Resolving update channel metadata"
Invoke-WebRequest -UseBasicParsing -Uri "$($UpdateBaseUrl.TrimEnd('/'))/channels/$Channel.json" -OutFile $channelPayload
$manifestUrl = Get-JsonField -Path $channelPayload -Field "manifest_url"
Write-Step "Downloading target release manifest"
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
Write-Step "Refreshing local runtime assets"
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

Write-Step "Pulling Docker image $image"
Invoke-ComposeUpdateStep pull
Write-Step "Restarting Nagient container"
Invoke-ComposeUpdateStep up -d

Write-Host "Nagient upgraded: $currentVersion -> $targetVersion"
Write-Host "Quick start: $(Join-Path $NagientHome 'bin/nagient.ps1') status"
