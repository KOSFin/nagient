Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DefaultChannel = "stable"
$DefaultUpdateBaseUrl = "__NAGIENT_UPDATE_BASE_URL__"
$UnrenderedUpdateBaseUrlToken = "__NAGIENT_" + "UPDATE_BASE_URL__"

$Channel = if ($env:NAGIENT_CHANNEL) { $env:NAGIENT_CHANNEL } else { $DefaultChannel }
$UpdateBaseUrl = if ($env:NAGIENT_UPDATE_BASE_URL) {
  $env:NAGIENT_UPDATE_BASE_URL
} elseif ($env:UPDATE_BASE_URL) {
  $env:UPDATE_BASE_URL
} else {
  $DefaultUpdateBaseUrl
}

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
  throw "NAGIENT_UPDATE_BASE_URL is not configured. This usually means the update center root is serving an unrendered bootstrap installer. Re-publish the update center or set NAGIENT_UPDATE_BASE_URL/UPDATE_BASE_URL explicitly."
}

$channelPayload = Invoke-RestMethod "$($UpdateBaseUrl.TrimEnd('/'))/channels/$Channel.json"
$version = [string]$channelPayload.latest_version
if ([string]::IsNullOrWhiteSpace($version)) {
  throw "Cannot resolve latest version for channel $Channel"
}

$installScriptUrl = "$($UpdateBaseUrl.TrimEnd('/'))/$version/install.ps1"
Invoke-Expression ((Invoke-WebRequest -UseBasicParsing -Uri $installScriptUrl).Content)
