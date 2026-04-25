Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DefaultChannel = "__NAGIENT_DEFAULT_CHANNEL__"
$DefaultUpdateBaseUrl = "__NAGIENT_UPDATE_BASE_URL__"

$NagientHome = if ($env:NAGIENT_HOME) { $env:NAGIENT_HOME } else { Join-Path $HOME ".nagient" }
$Channel = if ($env:NAGIENT_CHANNEL) { $env:NAGIENT_CHANNEL } else { $DefaultChannel }
$UpdateBaseUrl = if ($env:NAGIENT_UPDATE_BASE_URL) { $env:NAGIENT_UPDATE_BASE_URL } else { $DefaultUpdateBaseUrl }
$ComposeFile = Join-Path $NagientHome "docker-compose.yml"
$EnvFile = Join-Path $NagientHome ".env"
$ConfigFile = Join-Path $NagientHome "config.toml"
$SecretsFile = Join-Path $NagientHome "secrets.env"
$PluginsDir = Join-Path $NagientHome "plugins"
$ProvidersDir = Join-Path $NagientHome "providers"
$CredentialsDir = Join-Path $NagientHome "credentials"
$ReleasesDir = Join-Path $NagientHome "releases"
$BinDir = Join-Path $NagientHome "bin"

if ($UpdateBaseUrl -eq "__NAGIENT_UPDATE_BASE_URL__") {
  throw "NAGIENT_UPDATE_BASE_URL is not configured. Use a released installer asset or set the variable explicitly."
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

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker is required."
}

New-Item -ItemType Directory -Force -Path $NagientHome, $ReleasesDir, $BinDir, $PluginsDir, $ProvidersDir, $CredentialsDir, (Join-Path $NagientHome "runtime") | Out-Null

$channelPayload = Join-Path ([System.IO.Path]::GetTempPath()) "nagient-channel.json"
$manifestPayload = Join-Path ([System.IO.Path]::GetTempPath()) "nagient-manifest.json"

Invoke-WebRequest -UseBasicParsing -Uri "$($UpdateBaseUrl.TrimEnd('/'))/channels/$Channel.json" -OutFile $channelPayload
$manifestUrl = Get-JsonField -Path $channelPayload -Field "manifest_url"
Invoke-WebRequest -UseBasicParsing -Uri $manifestUrl -OutFile $manifestPayload

$composeUrl = Get-JsonField -Path $manifestPayload -Field "docker.compose_url"
$image = Get-JsonField -Path $manifestPayload -Field "docker.image"
$version = Get-JsonField -Path $manifestPayload -Field "version"
$updateUrl = Get-ArtifactUrl -Path $manifestPayload -Name "update.ps1"
$uninstallUrl = Get-ArtifactUrl -Path $manifestPayload -Name "uninstall.ps1"

Invoke-WebRequest -UseBasicParsing -Uri $composeUrl -OutFile $ComposeFile
Invoke-WebRequest -UseBasicParsing -Uri $updateUrl -OutFile (Join-Path $BinDir "nagient-update.ps1")
Invoke-WebRequest -UseBasicParsing -Uri $uninstallUrl -OutFile (Join-Path $BinDir "nagient-uninstall.ps1")
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
plugins_dir = "$PluginsDir"
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
# ANTHROPIC_API_KEY=
# GEMINI_API_KEY=
# DEEPSEEK_API_KEY=
# TELEGRAM_BOT_TOKEN=
# NAGIENT_WEBHOOK_SHARED_SECRET=
"@ | Set-Content -Path $SecretsFile -Encoding utf8
}

@"
NAGIENT_IMAGE=$image
NAGIENT_CHANNEL=$Channel
NAGIENT_UPDATE_BASE_URL=$UpdateBaseUrl
NAGIENT_CONTAINER_NAME=nagient
NAGIENT_DOCKER_PROJECT_NAME=nagient
NAGIENT_SAFE_MODE=true
"@ | Set-Content -Path $EnvFile -Encoding utf8

docker compose -f $ComposeFile --env-file $EnvFile pull
docker compose -f $ComposeFile --env-file $EnvFile up -d

Write-Host "Nagient $version installed into $NagientHome"
