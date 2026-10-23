param([Parameter(Mandatory=$true)][string]$Session)
$ErrorActionPreference='Stop'
function Hash([string]$Path) {
    $stream=[IO.File]::OpenRead($Path);$algorithm=[Security.Cryptography.SHA256]::Create()
    try { [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose();$algorithm.Dispose() }
}
$metadata=Get-Content -LiteralPath (Join-Path $Session 'session.json') -Encoding UTF8 -Raw | ConvertFrom-Json
$claim=[IO.File]::Open((Join-Path $Session 'archive.claim'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read);$claim.Dispose()
$report=[ordered]@{complete=$false;status='FAILED';pid=$metadata.pid;bytes=0}
$source=$null;$destination=$null;$targetProcess=$null
try {
    $targetProcess=[Diagnostics.Process]::GetProcessById([int]$metadata.pid)
    if ($targetProcess.StartTime.ToUniversalTime().ToFileTimeUtc() -ne [long]$metadata.process_creation_filetime) { throw 'PID was reused; process generation mismatch.' }
    $root=Split-Path (Split-Path $Session)
    $settings=Get-Content -LiteralPath (Join-Path $root 'settings.json') -Encoding UTF8 -Raw | ConvertFrom-Json
    $installed=Get-Content -LiteralPath (Join-Path $root 'install-state.json') -Encoding UTF8 -Raw | ConvertFrom-Json
    [ordered]@{exe_sha256=(Hash $installed.game_exe);catalog_sha256=(Hash (Join-Path $root 'catalog.bin'));source_revision=$installed.source_revision;profile=$installed.profile} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Session 'build.json') -Encoding UTF8
    $deadline=[DateTime]::UtcNow.AddSeconds(60)
    while (-not $source) {
        try {
            if ((Get-Item -LiteralPath $settings.ue_log_path).LastWriteTimeUtc.ToFileTimeUtc() -ge [long]$metadata.process_creation_filetime) {
                $source=[IO.File]::Open($settings.ue_log_path,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
            }
        } catch [IO.IOException] { }
          catch [Management.Automation.ItemNotFoundException] { }
        if (-not $source) {
            if ($targetProcess.WaitForExit(100) -or [DateTime]::UtcNow -gt $deadline) { throw 'Current game log was not available. Check wojd/settings.json.' }
        }
    }
    $report.source=$settings.ue_log_path
    $archive=Join-Path $Session 'ZhuxianClient.log'
    $destination=[IO.File]::Open($archive,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    $buffer=New-Object byte[] (1024*1024);$observerDeadline=[DateTime]::UtcNow.AddHours(12)
    do {
        if ($source.Length -lt $source.Position -or $source.Length -gt 2GB) { throw 'Source log was truncated or exceeded 2 GiB; saved prefix retained.' }
        while($source.Position -lt $source.Length) {
            $read=$source.Read($buffer,0,[int][Math]::Min($buffer.Length,$source.Length-$source.Position))
            if ($read -le 0) { throw 'Log became shorter while reading.' }
            $destination.Write($buffer,0,$read);$report.bytes+=$read
        }
        $destination.Flush()
        $exited=$targetProcess.WaitForExit(100)
        if ([DateTime]::UtcNow -gt $observerDeadline) { throw 'Archive observer timed out; saved prefix retained.' }
    } while(-not $exited -or $source.Position -lt $source.Length)
    $destination.Flush($true);$destination.Dispose();$destination=$null
    $source.Position=0;$hasher=[Security.Cryptography.SHA256]::Create()
    $sourceHash=[BitConverter]::ToString($hasher.ComputeHash($source)).Replace('-','').ToLowerInvariant();$hasher.Dispose()
    $archiveHash=Hash $archive
    if ($sourceHash -ne $archiveHash -or $report.bytes -ne $source.Length) { throw 'Archive does not match the retained source log handle.' }
    $report.complete=$true;$report.status='PASS';$report.sha256=$archiveHash
} catch { $report.error=$_.Exception.Message }
finally {
    if($destination) { $destination.Dispose() };if($source) { $source.Dispose() };if($targetProcess) { $targetProcess.Dispose() }
    $report.finished_at=[DateTime]::UtcNow.ToString('o')
    $path=Join-Path $Session 'archive-result.json'
    $output=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    $writer=New-Object IO.StreamWriter($output,(New-Object Text.UTF8Encoding($false)));$writer.Write(($report | ConvertTo-Json -Depth 6));$writer.Dispose()
}
if(-not $report.complete) { exit 1 }
