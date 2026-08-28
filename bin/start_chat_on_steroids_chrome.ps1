[CmdletBinding()]
param(
  [int]$Port = $(if ($env:ORACLE_PERSISTENT_CDP_ENDPOINT -match '^127\.0\.0\.1:(\d+)$') { [int]$Matches[1] } else { 19356 }),
  [string]$Profile = $(if ($env:ORACLE_PERSISTENT_BROWSER_PROFILE) { $env:ORACLE_PERSISTENT_BROWSER_PROFILE } else { Join-Path $env:LOCALAPPDATA 'ChatOnSteroids\ChromeProfile' }),
  [string]$Extension = $(if ($env:CHAT_ON_STEROIDS_EXTENSION_ROOT) { $env:CHAT_ON_STEROIDS_EXTENSION_ROOT } else { Join-Path $env:APPDATA 'chat-on-steroids\extension' }),
  [string]$BrowserRoot = $(if ($env:CHAT_ON_STEROIDS_BROWSER_ROOT) { $env:CHAT_ON_STEROIDS_BROWSER_ROOT } else { Join-Path $env:USERPROFILE '.codex\state\chat-on-steroids\browsers' })
)

$ErrorActionPreference = 'Stop'
$hostName = '127.0.0.1'
$endpoint = "$hostName`:$Port"
$preflight = Join-Path $PSScriptRoot 'chatgpt_steroids_preflight.py'

function Get-SteroidsListener {
  Get-NetTCPConnection -State Listen -LocalAddress $hostName -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -First 1
}

if (-not (Test-Path -LiteralPath $preflight -PathType Leaf)) {
  throw "Steroids controller preflight helper is missing: $preflight"
}

$listener = Get-SteroidsListener
$state = 'reused-verified-controller'
if (-not $listener) {
  $candidate = Get-ChildItem -LiteralPath $BrowserRoot -Directory -Filter 'chrome-for-testing-*' |
    Sort-Object { [version]($_.Name -replace '^chrome-for-testing-', '') } -Descending |
    ForEach-Object { Join-Path $_.FullName 'chrome-win64\chrome.exe' } |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -First 1
  if (-not $candidate) {
    throw 'No verified Steroids Chrome for Testing binary is installed.'
  }
  Start-Process -FilePath $candidate -ArgumentList @(
    "--user-data-dir=$Profile",
    "--remote-debugging-port=$Port",
    "--load-extension=$Extension",
    '--no-first-run',
    '--no-default-browser-check',
    'https://chatgpt.com/'
  ) -WindowStyle Normal | Out-Null
  $deadline = (Get-Date).AddSeconds(30)
  do {
    Start-Sleep -Milliseconds 250
    $listener = Get-SteroidsListener
  } while (-not $listener -and (Get-Date) -lt $deadline)
  if (-not $listener) {
    throw "Steroids Chrome did not open CDP port $Port."
  }
  $state = 'launched-extension-controller'
}

$python = (Get-Command python.exe -ErrorAction Stop).Source
$preflightJson = & $python $preflight --endpoint $endpoint --profile $Profile --extension $Extension
if ($LASTEXITCODE -ne 0) {
  throw "STEROIDS_PERSISTENT_BROWSER_INCOMPATIBLE: $preflightJson"
}
$verified = $preflightJson | ConvertFrom-Json

[pscustomobject]@{
  ok = $verified.ok -eq $true
  state = $state
  port = $Port
  pid = $verified.pid
  browser = $verified.browser
  profile = $verified.profile
  extension = $verified.extension_root
  extensionLoadProven = $verified.extension_load_proven
  submittedQuestion = $false
} | ConvertTo-Json -Compress
