# Claude Code status line: retain only documented quota fields, never the input.
param([string]$OutputDirectory = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'RamterStudio\Vital'))
$ErrorActionPreference = 'Stop'
try {
    $data = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $windows = [ordered]@{}
    $parts = @()
    foreach ($field in @('five_hour', 'seven_day')) {
        $w = $data.rate_limits.$field
        if ($null -eq $w -or $null -eq $w.used_percentage -or $null -eq $w.resets_at) { continue }
        $used = [double]$w.used_percentage
        if ($used -lt 0 -or $used -gt 100) { continue }
        $windows[$field] = @{ remaining = 100 - $used; reset = [long]$w.resets_at }
        $period = if ($field -eq 'five_hour') { '5h' } else { '1w' }
        $parts += "$period $([math]::Round(100 - $used))%"
    }
    if ($windows.Count -gt 0) {
        $dir = $OutputDirectory
        [IO.Directory]::CreateDirectory($dir) | Out-Null
        $dest = Join-Path $dir 'claude-usage.json'
        $tmp = Join-Path $dir ([guid]::NewGuid().ToString() + '.tmp')
        try {
            $json = @{observed = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds(); windows = $windows} | ConvertTo-Json -Compress -Depth 4
            [IO.File]::WriteAllText($tmp, $json)
            if ([IO.File]::Exists($dest)) { [IO.File]::Replace($tmp, $dest, [System.Management.Automation.Language.NullString]::Value) }
            else { [IO.File]::Move($tmp, $dest) }
        } finally { if ([IO.File]::Exists($tmp)) { [IO.File]::Delete($tmp) } }
    }
    if ($parts.Count) { 'Claude | ' + ($parts -join ' | ') } else { 'Claude' }
} catch { 'Claude' }
