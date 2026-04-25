Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DefaultChannel = "stable"
$DefaultUpdateBaseUrl = "__NAGIENT_UPDATE_BASE_URL__"

$Channel = if ($env:NAGIENT_CHANNEL) { $env:NAGIENT_CHANNEL } else { $DefaultChannel }
$UpdateBaseUrl = if ($env:NAGIENT_UPDATE_BASE_URL) { $env:NAGIENT_UPDATE_BASE_URL } else { $DefaultUpdateBaseUrl }

if ($UpdateBaseUrl -eq "__NAGIENT_UPDATE_BASE_URL__" -or [string]::IsNullOrWhiteSpace($UpdateBaseUrl)) {
  throw "NAGIENT_UPDATE_BASE_URL is not configured."
}

$channelPayload = Invoke-RestMethod "$($UpdateBaseUrl.TrimEnd('/'))/channels/$Channel.json"
$version = [string]$channelPayload.latest_version
if ([string]::IsNullOrWhiteSpace($version)) {
  throw "Cannot resolve latest version for channel $Channel"
}

$installScriptUrl = "$($UpdateBaseUrl.TrimEnd('/'))/$version/install.ps1"
Invoke-Expression ((Invoke-WebRequest -UseBasicParsing -Uri $installScriptUrl).Content)
