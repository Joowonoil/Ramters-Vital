param(
    [switch]$Clean,
    [string]$Version = "1.1.0",
    [string]$PrivateKeyPath = ""
)

$ErrorActionPreference = "Stop"

$windowsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $windowsRoot
$releaseRoot = Join-Path $repoRoot "ReleaseArtifacts"
$installerName = "CodexVitals-Windows-$Version-Setup.exe"
$installerPath = Join-Path $releaseRoot $installerName
$hashPath = "$installerPath.sha256"
$appcastPath = Join-Path $releaseRoot "windows-appcast.xml"
$releaseNotesPath = Join-Path $releaseRoot "windows-release-notes.md"

if ([string]::IsNullOrWhiteSpace($PrivateKeyPath)) {
    $PrivateKeyPath = Join-Path $env:APPDATA "RamterStudio\ReleaseKeys\CodexVitals\windows-update-private.key"
}
if (-not (Test-Path -LiteralPath $PrivateKeyPath)) {
    throw "Windows update signing key was not found: $PrivateKeyPath"
}

if ($Clean) {
    Remove-Item -LiteralPath $releaseRoot -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null

& (Join-Path $windowsRoot "build.ps1") -Clean:$Clean -Channel Direct -Version $Version

$isccCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
)
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $iscc) {
    throw "Inno Setup 6 was not found. Install JRSoftware.InnoSetup with winget."
}

Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue
& $iscc "/DMyAppVersion=$Version" (Join-Path $windowsRoot "CodexVitals.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed."
}
if (-not (Test-Path -LiteralPath $installerPath)) {
    throw "Installer was not produced: $installerPath"
}

$winSparkleVersion = "0.9.3"
$winSparkleTool = Join-Path $env:LOCALAPPDATA "RamterStudio\BuildTools\WinSparkle-$winSparkleVersion\WinSparkle-$winSparkleVersion\bin\winsparkle-tool.exe"
if (-not (Test-Path -LiteralPath $winSparkleTool)) {
    throw "WinSparkle signing tool was not found: $winSparkleTool"
}

$signatureOutput = (& $winSparkleTool sign --verbose --private-key-file $PrivateKeyPath $installerPath 2>&1) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "WinSparkle could not sign the installer: $signatureOutput"
}
$signatureMatch = [regex]::Match($signatureOutput, 'sparkle:edSignature="([^"]+)"\s+length="(\d+)"')
if (-not $signatureMatch.Success) {
    throw "Could not parse WinSparkle signature output: $signatureOutput"
}
$signature = $signatureMatch.Groups[1].Value
$length = $signatureMatch.Groups[2].Value
$releaseTag = "windows-v$Version"
$downloadUrl = "https://github.com/Joowonoil/Ramters-Vital/releases/download/$releaseTag/$installerName"
$releaseNotesUrl = "https://github.com/Joowonoil/Ramters-Vital/releases/tag/$releaseTag"
$publicationDate = [DateTime]::UtcNow.ToString("r", [Globalization.CultureInfo]::InvariantCulture)

@"
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
  <channel>
    <title>Ramter's Vital Windows Updates</title>
    <link>https://ramterstudio.com/codex-vitals/windows-appcast.xml</link>
    <description>Updates for the direct Windows release.</description>
    <language>en</language>
    <item>
      <title>Ramter's Vital $Version</title>
      <pubDate>$publicationDate</pubDate>
      <sparkle:releaseNotesLink>$releaseNotesUrl</sparkle:releaseNotesLink>
      <enclosure
        url="$downloadUrl"
        sparkle:version="$Version"
        sparkle:shortVersionString="$Version"
        sparkle:edSignature="$signature"
        length="$length"
        type="application/octet-stream" />
    </item>
  </channel>
</rss>
"@ | Set-Content -LiteralPath $appcastPath -Encoding UTF8

$hash = (Get-FileHash -Algorithm SHA256 $installerPath).Hash.ToLowerInvariant()
Set-Content -LiteralPath $hashPath -Value "$hash  $installerName" -Encoding ASCII

@"
# Ramter's Vital for Windows $Version

Windows update for existing Codex Vitals installations.

- Monitor usage across multiple Codex accounts.
- Enable Gemini in Settings to read quota for the signed-in Antigravity CLI account. Only model allowances returned by the CLI are shown.
- Enable the optional Claude Code status line to see the last reported 5-hour and weekly quotas. Requires a Claude Code version and subscription that emit rate limits. Existing custom status lines are not overwritten.
- Add Claude Code profiles with separate official sign-ins. Switch the default for newly opened terminals, or use Open to start that profile immediately. Existing shells and sessions keep their current profile.
- Gemini follows the Google account signed in to agy. Optional saved reports are last-observed values, not live readings for inactive accounts. The report collector passed fixture tests; end-to-end collection from an interactive terminal has not been confirmed. Manage in agy opens the official CLI; this is not saved-account switching. Claude Fable quota and reset notifications are not included in this Windows release.
- Switch the active account used by Codex CLI and Codex Desktop.
- Keep local sessions and saved accounts on the device.
- Check for signed updates automatically or from Settings.

Windows may show a Microsoft Defender SmartScreen warning because the installer is not Authenticode-signed.
"@ | Set-Content -LiteralPath $releaseNotesPath -Encoding UTF8

Write-Output $installerPath
Write-Output $hashPath
Write-Output $appcastPath
Write-Output $releaseNotesPath
