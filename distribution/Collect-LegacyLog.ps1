param([string]$GameRoot,[string]$LogPath)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
try{
    if([string]::IsNullOrWhiteSpace($GameRoot)){$GameRoot=(Read-Host 'Nhap thu muc Game, ZhuxianClient hoac Binaries\Win64').Trim('"')}
    $root=[IO.Path]::GetFullPath($GameRoot)
    $relative=@('ZhuxianClient-Win64-Shipping.exe','Binaries/Win64/ZhuxianClient-Win64-Shipping.exe','ZhuxianClient/Binaries/Win64/ZhuxianClient-Win64-Shipping.exe','ZXSJ/Game/ZhuxianClient/Binaries/Win64/ZhuxianClient-Win64-Shipping.exe')
    $matches=@($relative | ForEach-Object { Join-Path $root $_ } | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
    if($matches.Count -ne 1){throw 'Khong tim thay duy nhat client.'}
    $bin=Split-Path $matches[0];$data=Join-Path $bin 'wojd'
    & "$env:SystemRoot/System32/WindowsPowerShell/v1.0/powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Installer.ps1') -Action Verify -GameRoot $bin
    if($LASTEXITCODE -ne 0){throw 'Can kiem tra ban Legacy da cai va thoat game truoc khi thu log.'}
    $state=ConvertFrom-Json ([IO.File]::ReadAllText((Join-Path $data 'install-state.json')))
    if($state.profile -cne 'legacy'){throw 'Can cai Legacy va chay mot luot game khong DLL truoc.'}
    if([string]::IsNullOrWhiteSpace($LogPath)){
        $candidates=@()
        $settings=Join-Path $data 'settings.json'
        if(Test-Path -LiteralPath $settings){
            $config=ConvertFrom-Json ([IO.File]::ReadAllText($settings))
            if('ue_log_path' -in @($config.PSObject.Properties.Name)){$candidates+=@($config.ue_log_path)}
        }
        $candidates+=@(Join-Path $env:LOCALAPPDATA 'ZhuxianClient/Saved/Logs/ZhuxianClient.log')
        $candidates+=@(Join-Path ([IO.Path]::GetFullPath((Join-Path $bin '../..'))) 'Saved/Logs/ZhuxianClient.log')
        $found=@($candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Sort-Object -Unique)
        if($found.Count -eq 1){$LogPath=$found[0]}
        else{$LogPath=(Read-Host 'Nhap duong dan file log game vua chay').Trim('"')}
    }
    $file=Get-Item -LiteralPath $LogPath -Force
    if($file.PSIsContainer -or $file.Length -gt 2GB -or $file.Extension -ine '.log'){throw 'Can file log game duoi 2 GiB.'}
    if($file.LastWriteTimeUtc -lt ([DateTime]::Parse($state.installed_at)).ToUniversalTime()){throw 'Log cu hon lan cai Legacy; hay chay mot luot game moi roi thu lai.'}
    $session=Join-Path $data ('logs/legacy-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N'))
    $null=[IO.Directory]::CreateDirectory($session)
    $target=Join-Path $session 'ZhuxianClient.log'
    $source=[IO.File]::Open($file.FullName,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    try{
        $length=$source.Length
        $destination=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
        try{$source.CopyTo($destination);$destination.Flush($true)}finally{$destination.Dispose()}
        if($source.Length -ne $length){throw 'Log thay doi khi sao luu; ban sao chua duoc xac nhan.'}
        $source.Position=0;$hasher=[Security.Cryptography.SHA256]::Create()
        try{$hash=[BitConverter]::ToString($hasher.ComputeHash($source)).Replace('-','').ToLowerInvariant()}finally{$hasher.Dispose()}
    }finally{$source.Dispose()}
    $copy=[IO.File]::OpenRead($target);$hasher=[Security.Cryptography.SHA256]::Create()
    try{$copyHash=[BitConverter]::ToString($hasher.ComputeHash($copy)).Replace('-','').ToLowerInvariant()}finally{$hasher.Dispose();$copy.Dispose()}
    if($copyHash -cne $hash -or (Get-Item -LiteralPath $target).Length -ne $length){throw 'Ban sao log khong khop.'}
    $report=[ordered]@{status='PASS';profile='legacy';source_revision=$state.source_revision;install_transaction=$state.transaction_id;
        collected_at=[DateTime]::UtcNow.ToString('o');bytes=$length;sha256=$hash;source_log=$file.FullName;dll_injection=$false}
    [IO.File]::WriteAllText((Join-Path $session 'collection.json'),(($report | ConvertTo-Json -Depth 4)+"`n"),[Text.UTF8Encoding]::new($false))
    Write-Output "Da luu log Legacy: $session"
    Write-Output 'Log co the chua thong tin rieng; chi chia se sau khi kiem tra.'
}catch{Write-Error $_.Exception.Message -ErrorAction Continue;exit 1}
