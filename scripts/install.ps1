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
$ConfigFile = Join-Path $NagientHome "config.toml"
$SecretsFile = Join-Path $NagientHome "secrets.env"
$ToolSecretsFile = Join-Path $NagientHome "tool-secrets.env"
$PluginsDir = Join-Path $NagientHome "plugins"
$ToolsDir = Join-Path $NagientHome "tools"
$ProvidersDir = Join-Path $NagientHome "providers"
$CredentialsDir = Join-Path $NagientHome "credentials"
$StateDir = Join-Path $NagientHome "state"
$LogDir = Join-Path $NagientHome "logs"
$ReleasesDir = Join-Path $NagientHome "releases"
$BinDir = Join-Path $NagientHome "bin"
$WorkspaceDir = Join-Path $NagientHome "workspace"

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
  throw "NAGIENT_UPDATE_BASE_URL is not configured. Use a rendered installer asset or set NAGIENT_UPDATE_BASE_URL/UPDATE_BASE_URL explicitly."
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
  $target = Join-Path $BinDir "nagient.ps1"
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

Full CLI: $(Join-Path $NagientHome 'bin/nagient.ps1') help

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
  help               Show this runtime control help
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

function Invoke-ControlCommand {
  param(
    [Parameter(Mandatory = $true)][string]$Command,
    [string[]]$Rest = @()
  )

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
}

function Invoke-CliCommand {
  param(
    [Parameter(Mandatory = $true)][string]$Command,
    [string[]]$Rest = @()
  )

  switch ($Command) {
    { $_ -in @("help", "-h", "--help") } {
      Assert-ComposeFiles
      $helpArgs = @("nagient")
      if ($Rest.Count -eq 0) {
        $helpArgs += "--help"
      } else {
        $helpArgs += $Rest
        $helpArgs += "--help"
      }
      Compose-ExecNagient @helpArgs
      break
    }
    { $_ -in @("ps", "up", "start", "down", "stop", "restart", "logs", "log", "shell", "sh", "exec", "x", "remove", "uninstall", "config", "st", "cfg", "check", "fix") } {
      Invoke-ControlCommand -Command $Command -Rest $Rest
      break
    }
    "update" {
      if ($Rest.Count -eq 0) {
        Invoke-ControlCommand -Command "update" -Rest @()
        break
      }
      Assert-ComposeFiles
      Compose-ExecNagient nagient update @Rest
      break
    }
    default {
      Assert-ComposeFiles
      Compose-ExecNagient nagient $Command @Rest
    }
  }
}

$Command = if ($args.Count -gt 0) { $args[0].ToLowerInvariant() } else { "help" }
$Rest = if ($args.Count -gt 1) { $args[1..($args.Count - 1)] } else { @() }

Invoke-CliCommand -Command $Command -Rest $Rest
'@
  $launcher | Set-Content -Path $target -Encoding utf8
  if (Test-Path (Join-Path $BinDir "nagientctl.ps1")) {
    Remove-Item -Force -Path (Join-Path $BinDir "nagientctl.ps1")
  }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker is required."
}

$composeOutput = (& docker compose version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
  throw "Docker Compose v2 is required. Install Docker Desktop or Docker Engine with the Compose plugin, then retry.`n$composeOutput"
}

$dockerInfoOutput = (& docker info 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
  throw "Docker is installed but the daemon is not available. Start Docker Desktop (macOS/Windows) or the Docker service (Linux), then retry. If you use a custom Docker context or socket, make sure 'docker info' succeeds first.`n$dockerInfoOutput"
}

function Invoke-ComposeInstallStep {
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
      throw "The published Docker image does not include an arm64 variant yet. Temporary workaround on Apple Silicon:`nDOCKER_DEFAULT_PLATFORM=linux/amd64 curl -fsSL https://ngnt-in.ruka.me/install.sh | bash"
    }
    throw "Docker Compose failed."
  }
}

New-Item -ItemType Directory -Force -Path $NagientHome, $ReleasesDir, $BinDir, $PluginsDir, $ToolsDir, $ProvidersDir, $CredentialsDir, $StateDir, $LogDir, $WorkspaceDir | Out-Null

$channelPayload = Join-Path ([System.IO.Path]::GetTempPath()) "nagient-channel.json"
$manifestPayload = Join-Path ([System.IO.Path]::GetTempPath()) "nagient-manifest.json"

Write-Step "Resolving release channel metadata"
Invoke-WebRequest -UseBasicParsing -Uri "$($UpdateBaseUrl.TrimEnd('/'))/channels/$Channel.json" -OutFile $channelPayload
$manifestUrl = Get-JsonField -Path $channelPayload -Field "manifest_url"
Write-Step "Downloading release manifest"
Invoke-WebRequest -UseBasicParsing -Uri $manifestUrl -OutFile $manifestPayload

$composeUrl = Get-JsonField -Path $manifestPayload -Field "docker.compose_url"
$image = Get-JsonField -Path $manifestPayload -Field "docker.image"
$version = Get-JsonField -Path $manifestPayload -Field "version"
$updateUrl = Get-ArtifactUrl -Path $manifestPayload -Name "update.ps1"
$uninstallUrl = Get-ArtifactUrl -Path $manifestPayload -Name "uninstall.ps1"

Write-Step "Writing runtime assets into $NagientHome"
Invoke-WebRequest -UseBasicParsing -Uri $composeUrl -OutFile $ComposeFile
Invoke-WebRequest -UseBasicParsing -Uri $updateUrl -OutFile (Join-Path $BinDir "nagient-update.ps1")
Invoke-WebRequest -UseBasicParsing -Uri $uninstallUrl -OutFile (Join-Path $BinDir "nagient-uninstall.ps1")
Write-NagientCtl
Copy-Item -Force -Path $manifestPayload -Destination (Join-Path $ReleasesDir "current.json")
Copy-Item -Force -Path $manifestPayload -Destination (Join-Path $ReleasesDir "$version.json")

if (-not (Test-Path $ConfigFile)) {
  @"
[updates]
channel = "$Channel"
base_url = "$UpdateBaseUrl"

[runtime]
heartbeat_interval_seconds = 30
safe_mode = true

[docker]
project_name = "nagient"

[paths]
secrets_file = "$SecretsFile"
tool_secrets_file = "$ToolSecretsFile"
plugins_dir = "$PluginsDir"
tools_dir = "$ToolsDir"
providers_dir = "$ProvidersDir"
credentials_dir = "$CredentialsDir"

[agent]
default_provider = ""
require_provider = false

[transports.console]
plugin = "builtin.console"
enabled = true

[transports.webhook]
plugin = "builtin.webhook"
enabled = false
listen_host = "0.0.0.0"
listen_port = 8080
path = "/events"
shared_secret_name = "NAGIENT_WEBHOOK_SHARED_SECRET"

[transports.telegram]
plugin = "builtin.telegram"
enabled = false
bot_token_secret = "TELEGRAM_BOT_TOKEN"
default_chat_id = ""

[providers.openai]
plugin = "builtin.openai"
enabled = false
auth = "api_key"
api_key_secret = "OPENAI_API_KEY"
model = "gpt-4.1-mini"

[providers.openai-codex]
plugin = "builtin.openai_codex"
enabled = false
auth = "oauth_browser"
redirect_uri = "http://127.0.0.1:1455/auth/callback"
api_key_secret = "CODEX_API_KEY"
model = "gpt-5-codex"

[providers.anthropic]
plugin = "builtin.anthropic"
enabled = false
auth = "api_key"
api_key_secret = "ANTHROPIC_API_KEY"
model = "claude-sonnet-4-5"

[providers.gemini]
plugin = "builtin.gemini"
enabled = false
auth = "api_key"
api_key_secret = "GEMINI_API_KEY"
model = "gemini-2.5-pro"

[providers.deepseek]
plugin = "builtin.deepseek"
enabled = false
auth = "api_key"
api_key_secret = "DEEPSEEK_API_KEY"
model = "deepseek-chat"

[providers.ollama]
plugin = "builtin.ollama"
enabled = false
auth = "none"
base_url = "http://127.0.0.1:11434"
model = "llama3.1:8b"
"@ | Set-Content -Path $ConfigFile -Encoding utf8
}

if (-not (Test-Path $SecretsFile)) {
  @"
# Fill only the secrets you actually use.
# OPENAI_API_KEY=
# CODEX_API_KEY=
# ANTHROPIC_API_KEY=
# GEMINI_API_KEY=
# DEEPSEEK_API_KEY=
# TELEGRAM_BOT_TOKEN=
# NAGIENT_WEBHOOK_SHARED_SECRET=
"@ | Set-Content -Path $SecretsFile -Encoding utf8
}

if (-not (Test-Path $ToolSecretsFile)) {
  @"
# Add tool-scoped secrets here when needed.
"@ | Set-Content -Path $ToolSecretsFile -Encoding utf8
}

@"
NAGIENT_IMAGE=$image
NAGIENT_CHANNEL=$Channel
NAGIENT_UPDATE_BASE_URL=$UpdateBaseUrl
NAGIENT_CONTAINER_NAME=nagient
NAGIENT_DOCKER_PROJECT_NAME=nagient
NAGIENT_SAFE_MODE=true
"@ | Set-Content -Path $EnvFile -Encoding utf8

Write-Step "Pulling Docker image $image"
Invoke-ComposeInstallStep pull
Write-Step "Starting Nagient container"
Invoke-ComposeInstallStep up -d

Write-Host "Nagient $version installed into $NagientHome"
Write-Host "Runtime started, but provider setup is still incomplete until you enable one."
Write-Host "Next: $(Join-Path $BinDir 'nagient.ps1') status"
Write-Host "Config paths: $(Join-Path $BinDir 'nagient.ps1') paths"
Write-Host "Updater: $(Join-Path $BinDir 'nagient.ps1') update"
