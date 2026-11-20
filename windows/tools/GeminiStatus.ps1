param([string]$Directory = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'RamterStudio\Vital\Gemini'))
$ErrorActionPreference = 'Stop'
try {
    if (-not [IO.File]::Exists((Join-Path $Directory 'enabled'))) { return }
    $sample = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $mail = ([string]$sample.email).Trim().ToLowerInvariant()
    if ($sample.product -ne 'antigravity' -or $mail.Length -gt 254 -or $mail -notmatch '^[^\s@\p{C}]+@[^\s@\p{C}]+$') { return }
    $quotas = [ordered]@{}
    foreach ($prop in $sample.quota.PSObject.Properties) {
        if ($prop.Name -cnotmatch '^gemini-(?:(?:argon|carbon|hydrogen)-)?(?:5h|weekly)$') { continue }
        $w = $prop.Value
        $value = $w.remaining_fraction
        if ($w.disabled -eq $true -or $null -eq $value -or $value -is [bool] -or $value -is [string]) { continue }
        $n = [double]$value
        if (-not ($n -ge 0 -and $n -le 1)) { continue }
        $reset = [DateTimeOffset]::MinValue
        $epoch = $null
        if ($w.reset_time -and [DateTimeOffset]::TryParse([string]$w.reset_time, [ref]$reset)) {
            $epoch = $reset.ToUnixTimeSeconds()
        }
        $quotas[$prop.Name] = @{remaining=$n; reset=$epoch}
    }
    if (-not $quotas.Count) { return }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $key = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($mail))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
    $file = Join-Path $Directory ($key + '.json')
    $plan = [string]$sample.plan_tier
    if ($plan.Length -gt 64 -or $plan -match '[\p{C}]') { $plan = '' }
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $content = @{email=$mail; plan=$plan; observed=$now; quotas=$quotas} | ConvertTo-Json -Compress -Depth 4
    $tmp = Join-Path $Directory ([guid]::NewGuid().ToString() + '.tmp')
    try {
        [IO.File]::WriteAllText($tmp, $content)
        if (-not [IO.File]::Exists((Join-Path $Directory 'enabled'))) { return }
        if ([IO.File]::Exists($file)) { [IO.File]::Replace($tmp, $file, [System.Management.Automation.Language.NullString]::Value) }
        else { [IO.File]::Move($tmp, $file) }
    } finally { if ([IO.File]::Exists($tmp)) { [IO.File]::Delete($tmp) } }
} catch { return }
