param(
    [ValidateSet('Install','Verify','Uninstall','Rollback')][string]$Action='Install',
    [string]$GameRoot,
    [string]$PackageRoot=$PSScriptRoot,
    [string]$TransactionId,
    [switch]$ChatSetup,
    [ValidateSet('runtime','legacy')][string]$Profile='runtime',
    [switch]$ChooseProfile
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Owner='wojd-localization'
$ProcessNames=@('ZhuxianClient-Win64-Shipping','ZhuxianClient')
$PayloadSources=[ordered]@{
    'bin/dbghelp.dll'='payload/dbghelp.dll'
    'data/catalog.bin'='payload/catalog.bin'
    'data/Archive-Session.ps1'='Archive-Session.ps1'
    'pak/zz_WOJD_LOCALIZATION_P.pak'='payload/zz_WOJD_LOCALIZATION_P.pak'
    'pak/zz_WOJD_HUD_S2_1_P.pak'='payload/zz_WOJD_HUD_S2_1_P.pak'
}
$ProfilePayloadSources=@{
    runtime=$PayloadSources
    legacy=[ordered]@{
        'pak/zz_WOJD_LOCALIZATION_P.pak'='payload/legacy/zz_WOJD_LOCALIZATION_P.pak'
        'pak/zz_WOJD_HUD_S2_1_P.pak'='payload/zz_WOJD_HUD_S2_1_P.pak'
    }
}
$ManagedTargets=@($PayloadSources.Keys)+@('bin/wojd_dbghelp_original.dll')
$JournalTargets=$ManagedTargets+@('data/install-state.json','data/ownership.json')
$RetiredPakNames=@('~VI_PATCH.pak','~VI_PATCH_LIM.pak','~VI_PATCH_LIM_XF.pak','~VI_PATCH_LIM_MVH.pak','~VI_QFONT.pak','~VI_QFONT_XF.pak','~VI_QFONT_MVH.pak','~EN_PATCH.pak')
$script:Lock=$null
$script:ActiveJournal=$null
$script:ActiveTransaction=$null
$script:BootstrappedOwner=$false
$script:ExplicitProfile=$PSBoundParameters.ContainsKey('Profile')

function Require($Condition,[string]$Message) { if(-not $Condition){throw $Message} }
function Has($Value,[string]$Name) { return $null -ne $Value -and $Name -in @($Value.PSObject.Properties.Name) }
function Closed {
    $running=@(Get-Process -ErrorAction Stop | Where-Object { $_.ProcessName -in $ProcessNames })
    Require ($running.Count -eq 0) 'Game dang chay. Hay thoat game binh thuong roi chay lai.'
}
function Plain-Existing([string]$Path,[bool]$Directory) {
    $item=Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    Require ([bool]$item.PSIsContainer -eq $Directory) "Sai loai file/thu muc: $Path"
    Require (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) "Khong dung lien ket thu muc/file: $Path"
    $cursor=if($Directory){$item.FullName}else{$item.DirectoryName}
    while($cursor){
        $ancestor=Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
        Require (-not ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint)) "Thu muc cha la lien ket: $cursor"
        $parent=[IO.Directory]::GetParent($cursor)
        $cursor=if($parent){$parent.FullName}else{$null}
    }
    return $item.FullName
}
function Under([string]$Root,[string]$Relative) {
    Require (-not [string]::IsNullOrWhiteSpace($Relative)) 'Duong dan trong goi bi rong.'
    Require (-not [IO.Path]::IsPathRooted($Relative) -and $Relative -notmatch ':') 'Duong dan trong goi phai tuong doi.'
    $parts=@($Relative -split '[\\/]')
    Require ($parts.Count -gt 0 -and @($parts | Where-Object { $_ -eq '' -or $_ -eq '.' -or $_ -eq '..' -or $_ -match '[<>:"|?*]' -or $_.EndsWith('.') -or $_.EndsWith(' ') }).Count -eq 0) 'Duong dan trong goi khong hop le.'
    $base=[IO.Path]::GetFullPath($Root).TrimEnd('\')+'\'
    $path=[IO.Path]::GetFullPath((Join-Path $Root ($parts -join '\')))
    Require ($path.StartsWith($base,[StringComparison]::OrdinalIgnoreCase)) 'Duong dan vuot khoi thu muc du kien.'
    $cursor=$path
    while(-not (Test-Path -LiteralPath $cursor)){
        $parent=[IO.Directory]::GetParent($cursor)
        Require ($null -ne $parent) 'Khong tim thay thu muc cha an toan.'
        $cursor=$parent.FullName
    }
    $item=Get-Item -LiteralPath $cursor -Force
    $null=Plain-Existing $cursor ([bool]$item.PSIsContainer)
    return $path
}
function Pin([string]$Path) {
    $null=Plain-Existing $Path $false
    $stream=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    $algorithm=[Security.Cryptography.SHA256]::Create()
    try{
        $length=$stream.Length
        $hash=[BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant()
        Require ($stream.Length -eq $length) "File thay doi trong luc doc: $Path"
        return [pscustomobject]@{exists=$true;bytes=[Int64]$length;sha256=$hash}
    }finally{$stream.Dispose();$algorithm.Dispose()}
}
function Maybe-Pin([string]$Path) {
    if(Test-Path -LiteralPath $Path){return Pin $Path}
    return [pscustomobject]@{exists=$false;bytes=0;sha256=$null}
}
function Valid-Pin($Value,[bool]$AllowAbsent=$false) {
    Require ($null -ne $Value -and (Has $Value 'exists') -and $Value.exists -is [bool]) 'Thieu trang thai file.'
    if(-not $Value.exists){Require $AllowAbsent 'File bat buoc dang thieu.';return}
    Require ((Has $Value 'bytes') -and ($Value.bytes -is [Int32] -or $Value.bytes -is [Int64]) -and $Value.bytes -ge 0) 'Kich thuoc file khong hop le.'
    Require ((Has $Value 'sha256') -and $Value.sha256 -is [string] -and $Value.sha256 -cmatch '^[a-f0-9]{64}$') 'SHA256 khong hop le.'
}
function Same-Pin($Left,$Right) {
    if([bool]$Left.exists -ne [bool]$Right.exists){return $false}
    if(-not $Left.exists){return $true}
    return [Int64]$Left.bytes -eq [Int64]$Right.bytes -and $Left.sha256 -ceq $Right.sha256
}
function Expect([string]$Path,$Wanted) {
    Valid-Pin $Wanted $true
    $actual=Maybe-Pin $Path
    Require (Same-Pin $actual $Wanted) "File da thay doi; giu nguyen de kiem tra: $Path"
    return $actual
}
function Read-Json([string]$Path) {
    $null=Plain-Existing $Path $false
    return ConvertFrom-Json ([IO.File]::ReadAllText($Path,[Text.Encoding]::UTF8))
}
function Json-Bytes($Value) {
    $text=($Value | ConvertTo-Json -Depth 20)+"`n"
    return ,([Text.UTF8Encoding]::new($false).GetBytes($text))
}
function Write-New([string]$Path,[byte[]]$Bytes) {
    $null=Under ([IO.Path]::GetDirectoryName($Path)) ([IO.Path]::GetFileName($Path))
    $stream=[IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
function Write-Journal($Journal,[string]$Directory) {
    $path=Under $Directory 'journal.json'
    $temp=Under $Directory ('journal-'+[Guid]::NewGuid().ToString('N')+'.tmp')
    Write-New $temp (Json-Bytes $Journal)
    if(Test-Path -LiteralPath $path){$null=Plain-Existing $path $false;[IO.File]::Replace($temp,$path,[NullString]::Value)}else{[IO.File]::Move($temp,$path)}
}
function X64-PE([string]$Path,[bool]$Dll) {
    $null=Plain-Existing $Path $false
    $stream=[IO.File]::OpenRead($Path);$reader=[IO.BinaryReader]::new($stream)
    try{
        Require ($stream.Length -ge 128 -and $reader.ReadUInt16() -eq 0x5a4d) "Khong phai file Windows: $Path"
        $stream.Position=0x3c;$pe=$reader.ReadUInt32()
        Require ($pe -ge 64 -and [Int64]$pe+26 -le $stream.Length) "PE header khong hop le: $Path"
        $stream.Position=$pe
        Require ($reader.ReadUInt32() -eq 0x4550 -and $reader.ReadUInt16() -eq 0x8664) "Can ban Windows x64: $Path"
        $stream.Position=[Int64]$pe+22;$flags=$reader.ReadUInt16()
        Require ([bool]($flags -band 0x2000) -eq $Dll) "Sai loai EXE/DLL: $Path"
        $stream.Position=[Int64]$pe+24
        Require ($reader.ReadUInt16() -eq 0x20b) "Can PE32+ x64: $Path"
    }finally{$reader.Dispose();$stream.Dispose()}
}
function Resolve-Game([string]$InputPath) {
    if([string]::IsNullOrWhiteSpace($InputPath)){$InputPath=(Read-Host 'Nhap thu muc Game, ZhuxianClient hoac Binaries\Win64').Trim('"')}
    $root=Plain-Existing ([IO.Path]::GetFullPath($InputPath)) $true
    $relative=@('ZhuxianClient-Win64-Shipping.exe','Binaries/Win64/ZhuxianClient-Win64-Shipping.exe','ZhuxianClient/Binaries/Win64/ZhuxianClient-Win64-Shipping.exe','ZXSJ/Game/ZhuxianClient/Binaries/Win64/ZhuxianClient-Win64-Shipping.exe')
    $matches=@()
    foreach($name in $relative){$p=Under $root $name;if(Test-Path -LiteralPath $p -PathType Leaf){$matches+=$p}}
    Require ($matches.Count -eq 1) 'Khong tim thay duy nhat client. Hay chon dung thu muc Binaries\Win64.'
    $exe=$matches[0];X64-PE $exe $false
    $bin=[IO.Path]::GetDirectoryName($exe)
    $client=[IO.Path]::GetFullPath((Join-Path $bin '..\..'))
    $null=Plain-Existing $client $true
    $game=[IO.Path]::GetDirectoryName($client)
    $paks=Under $client 'Content/Paks';$null=Plain-Existing $paks $true
    return [pscustomobject]@{exe=$exe;bin=$bin;client=$client;pak=$paks;data=(Under $bin 'wojd');vendor=(Under $game 'Engine/Binaries/ThirdParty/DbgHelp/dbghelp.dll')}
}
function Target([string]$Name) {
    Require ($Name -in $JournalTargets) 'Ten file dich khong duoc phep.'
    $parts=$Name.Split('/',2)
    return Under $script:Game.($parts[0]) $parts[1]
}
function Check-Package {
    $script:PackageRoot=Plain-Existing ([IO.Path]::GetFullPath($PackageRoot)) $true
    $manifestPath=Under $script:PackageRoot 'manifest.json'
    $m=Read-Json $manifestPath
    Require ($m.format_version -eq 2 -and $m.owner -ceq $Owner -and $m.profile -in @('runtime','legacy')) 'Manifest goi Viet hoa khong hop le.'
    Require ($m.source_revision -is [string] -and -not [string]::IsNullOrWhiteSpace($m.source_revision)) 'Thieu ma nguon/revision cua goi.'
    Require ($m.release_id -is [string] -and $m.release_id -cmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$') 'Release ID khong hop le.'
    $script:PackageFiles=@{}
    foreach($row in @($m.files)){
        Require ($row.path -is [string]) 'Ten file manifest khong hop le.'
        $name=$row.path.Replace('\','/')
        Require ($name -cne 'manifest.json' -and -not $script:PackageFiles.ContainsKey($name)) 'Manifest trung ten file.'
        $p=Under $script:PackageRoot $name
        $wanted=[pscustomobject]@{exists=$true;bytes=$row.bytes;sha256=$row.sha256};Valid-Pin $wanted
        $null=Expect $p $wanted
        $script:PackageFiles[$name]=$wanted
    }
    $actual=@();$pending=@($script:PackageRoot)
    while($pending.Count){
        $directory=$pending[0]
        if($pending.Count -eq 1){$pending=@()}else{$pending=@($pending[1..($pending.Count-1)])}
        foreach($item in Get-ChildItem -LiteralPath $directory -Force){
            Require (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'Goi co lien ket file/thu muc.'
            if($item.PSIsContainer){$pending+=$item.FullName}
            else{$name=$item.FullName.Substring($script:PackageRoot.TrimEnd('\').Length+1).Replace('\','/');if($name -cne 'manifest.json'){$actual+=$name}}
        }
    }
    $actualNames=(@($actual | Sort-Object) -join "`n")
    $manifestNames=(@($script:PackageFiles.Keys | Sort-Object) -join "`n")
    Require ($actualNames -ceq $manifestNames) 'Danh sach file thuc khong khop manifest.'
    $available=@(if(Has $m 'supported_profiles'){$m.supported_profiles}else{$m.profile})
    Require ($available.Count -ge 1 -and $m.profile -in $available -and @($available | Where-Object { $_ -notin @('runtime','legacy') }).Count -eq 0 -and @($available | Sort-Object -Unique).Count -eq $available.Count) 'Danh sach phien ban khong hop le.'
    $required=@('Installer.ps1','install.bat','verify.bat','uninstall.bat','rollback.bat','README.txt','LICENSE')
    foreach($choice in $available){$required+=@($ProfilePayloadSources[$choice].Values)}
    if('runtime' -in $available){$required+='MinHook-LICENSE.txt';X64-PE (Under $script:PackageRoot 'payload/dbghelp.dll') $true}
    else{Require (@($script:PackageFiles.Keys | Where-Object { $_ -match '\.(dll|exe)$' -or $_ -ceq 'payload/catalog.bin' }).Count -eq 0) 'Goi Legacy khong duoc chua DLL, EXE hoac tu dien native.'}
    foreach($name in $required){Require ($script:PackageFiles.ContainsKey($name)) "Goi thieu file: $name"}
    $null=Expect $PSCommandPath $script:PackageFiles['Installer.ps1']
    $script:SelectedProfile=if($script:ExplicitProfile){$Profile}else{$m.profile}
    if($ChooseProfile -and $Action -eq 'Install' -and $available.Count -gt 1){
        Write-Host '1. Day du - DLL, ban dich game va tuy chon dich chat'
        Write-Host '2. Legacy - khong nap DLL, it noi dung duoc dich hon'
        $answer=Read-Host 'Chon 1 hoac 2 (Enter = 1)'
        Require ($answer -in @('','1','2')) 'Lua chon khong hop le.'
        $script:SelectedProfile=if($answer -ceq '2'){'legacy'}else{'runtime'}
    }
    Require ($script:SelectedProfile -in $available) 'Goi nay khong chua phien ban da chon.'
    $vendor=[pscustomobject]@{exists=$true;bytes=$m.vendor_dbghelp.bytes;sha256=$m.vendor_dbghelp.sha256};Valid-Pin $vendor
    $script:Manifest=$m;$script:VendorPin=$vendor
}
function Read-Owner {
    if(-not (Test-Path -LiteralPath $script:Game.data)){return}
    $null=Plain-Existing $script:Game.data $true
    $p=Target 'data/ownership.json'
    Require (Test-Path -LiteralPath $p -PathType Leaf) 'Thu muc wojd chua duoc quan ly. Giu nguyen va xu ly xung dot truoc.'
    $o=Read-Json $p
    Require ($o.owner -ceq $Owner -and [IO.Path]::GetFullPath($o.game_exe) -ieq $script:Game.exe) 'Quyen so huu thu muc wojd khong khop client nay.'
}
function Read-Installation {
    Read-Owner
    $statePath=Target 'data/install-state.json'
    if(-not (Test-Path -LiteralPath $statePath)){
        Require (-not (Test-Path -LiteralPath (Target 'bin/wojd_dbghelp_original.dll'))) 'Co DLL mirror chua duoc quan ly; giu nguyen.'
        # An ownership marker permits retaining caches/settings/logs, not overwriting
        # untracked managed payloads after install-state has gone missing.
        foreach($name in @('data/catalog.bin','data/Archive-Session.ps1')){
            Require (-not (Test-Path -LiteralPath (Target $name))) "Co file du lieu Viet hoa chua duoc quan ly: $name. Giu nguyen."
        }
        foreach($name in @('pak/zz_WOJD_LOCALIZATION_P.pak','pak/zz_WOJD_HUD_S2_1_P.pak')){Require (-not (Test-Path -LiteralPath (Target $name))) 'Co PAK Viet hoa chua duoc quan ly; giu nguyen.'}
        $proxy=Maybe-Pin (Target 'bin/dbghelp.dll')
        if($proxy.exists){Require (Same-Pin $proxy $script:VendorPin) 'Mot mod khac dang dung dbghelp.dll; giu nguyen.'}
        return [pscustomobject]@{kind='FRESH';original_bin_dll_existed=[bool]$proxy.exists;state=$null}
    }
    $s=Read-Json $statePath
    Require ([IO.Path]::GetFullPath($s.game_exe) -ieq $script:Game.exe) 'Trang thai cai dat thuoc client khac.'
    Require ($s.original_bin_dll_existed -is [bool]) 'Thieu trang thai DLL goc.'
    if($s.format_version -eq 2){
        Require ($s.owner -ceq $Owner -and $s.profile -in @('runtime','legacy')) 'Trang thai Viet hoa khong hop le.'
        $seen=@{}
        foreach($row in @($s.files)){
            Require ($row.target -in $ManagedTargets -and -not $seen.ContainsKey($row.target)) 'Trang thai co file la/trung lap.'
            $exists=if(Has $row 'exists'){$row.exists}else{$true}
            $wanted=[pscustomobject]@{exists=$exists;bytes=$row.bytes;sha256=$row.sha256};Valid-Pin $wanted $true
            if($s.profile -ceq 'runtime'){Require $wanted.exists 'Ban day du dang thieu file bat buoc.'}
            elseif($row.target -in @('data/catalog.bin','data/Archive-Session.ps1','bin/wojd_dbghelp_original.dll')){Require (-not $wanted.exists) 'Ban Legacy con file runtime dang hoat dong.'}
            elseif($row.target -ceq 'bin/dbghelp.dll'){
                Require ([bool]$wanted.exists -eq $s.original_bin_dll_existed) 'Trang thai DLL goc cua Legacy khong khop.'
                if($wanted.exists){Require (Same-Pin $wanted $script:VendorPin) 'Legacy khong duoc nap DLL Viet hoa.'}
            }else{Require $wanted.exists 'Ban Legacy dang thieu PAK.'}
            $null=Expect (Target $row.target) $wanted;$seen[$row.target]=$true
        }
        Require ($seen.Count -eq $ManagedTargets.Count) 'Trang thai khong du 6 file duoc quan ly.'
        if($s.profile -ceq 'runtime'){Require ((Pin (Target 'bin/wojd_dbghelp_original.dll')).sha256 -ceq $script:VendorPin.sha256) 'DLL mirror khong tuong thich voi goi nay.'}
        return [pscustomobject]@{kind='MANAGED_V2';original_bin_dll_existed=$s.original_bin_dll_existed;state=$s}
    }
    Require ($s.format_version -eq 1) 'Khong ho tro trang thai cai dat nay.'
    $legacyTargets=@('bin/dbghelp.dll','bin/wojd_dbghelp_original.dll','data/catalog.bin','data/Archive-Session.ps1','pak/zz_WOJD_LOCALIZATION_P.pak')
    $seen=@{}
    foreach($row in @($s.files)){
        Require ($row.path -is [string] -and $row.sha256 -cmatch '^[a-f0-9]{64}$') 'Trang thai cu khong hop le.'
        $key=@($legacyTargets | Where-Object { (Target $_) -ieq [IO.Path]::GetFullPath($row.path) })
        Require ($key.Count -eq 1 -and -not $seen.ContainsKey($key[0])) 'Trang thai cu co duong dan la/trung lap.'
        $seen[$key[0]]=$true
    }
    Require ($seen.Count -eq 5) 'Trang thai cu khong du 5 file.'
    $accepted=@()
    foreach($candidate in @($script:Manifest.accepted_legacy_installations)){
        Require ($candidate.id -is [string] -and $candidate.id -cmatch '^[A-Za-z0-9._-]+$') 'Migration ID khong hop le.'
        $keys=@{};$match=$true
        foreach($row in @($candidate.files)){
            Require ($row.target -in $ManagedTargets -and -not $keys.ContainsKey($row.target)) 'Migration co file la/trung lap.'
            $wanted=[pscustomobject]@{exists=$row.exists;bytes=$row.bytes;sha256=$row.sha256};Valid-Pin $wanted $true
            if(-not (Same-Pin (Maybe-Pin (Target $row.target)) $wanted)){$match=$false}
            $keys[$row.target]=$true
        }
        Require ($keys.Count -eq $ManagedTargets.Count) 'Migration phai rang buoc du 6 file.'
        if($match){$accepted+=$candidate.id}
    }
    Require ($accepted.Count -eq 1) 'Ban cu khong khop mot migration da kiem tra. Khong ghi de file.'
    return [pscustomobject]@{kind=('LEGACY_EXACT_'+$accepted[0]);original_bin_dll_existed=$s.original_bin_dll_existed;state=$s}
}
function Check-Pending {
    $transactions=Under $script:Game.data 'transactions'
    if(-not (Test-Path -LiteralPath $transactions)){return}
    $null=Plain-Existing $transactions $true
    foreach($item in Get-ChildItem -LiteralPath $transactions -Force){
        Require ($item.PSIsContainer -and $item.Name -cmatch '^[a-f0-9]{32}$') 'Lich su giao dich co muc khong ro nguon goc.'
        $null=Plain-Existing $item.FullName $true
        $path=Under $item.FullName 'journal.json'
        Require (Test-Path -LiteralPath $path -PathType Leaf) "Giao dich chua co journal: $($item.Name). Giu backup de kiem tra."
        $journal=Read-Json $path
        Require ($journal.owner -ceq $Owner -and $journal.game_exe -ieq $script:Game.exe -and $journal.id -ceq $item.Name) 'Journal thuoc client khac.'
        Require ($journal.status -in @('PLANNING','PREPARED','ROLLING_BACK','COMMITTED','ROLLED_BACK')) 'Trang thai journal khong hop le.'
        # PLANNING is persisted before snapshots/materials and before any game-file write.
        Require ($journal.status -in @('PLANNING','COMMITTED','ROLLED_BACK')) "Giao dich chua xong: $($item.Name). Dong game va chay rollback.bat voi ma nay truoc."
    }
}
function Acquire-Lock {
    Closed
    if(-not (Test-Path -LiteralPath $script:Game.data)){$null=[IO.Directory]::CreateDirectory($script:Game.data)}
    $null=Plain-Existing $script:Game.data $true
    $lockPath=Under $script:Game.data '.installer.lock'
    if(Test-Path -LiteralPath $lockPath){$null=Plain-Existing $lockPath $false}
    $script:Lock=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    $ownerPath=Target 'data/ownership.json'
    if(-not (Test-Path -LiteralPath $ownerPath)){
        # Only an empty freshly created directory may acquire our persistent marker.
        $other=@(Get-ChildItem -LiteralPath $script:Game.data -Force | Where-Object { $_.Name -cne '.installer.lock' })
        Require ($other.Count -eq 0) 'Thu muc wojd da thay doi trong luc chuan bi. Khong ghi de.'
        $ownershipDocument=[ordered]@{format_version=2;owner=$Owner;game_exe=$script:Game.exe}
        Write-New $ownerPath (Json-Bytes $ownershipDocument)
        $script:BootstrappedOwner=$true
    }else{Read-Owner}
}
function Publish([string]$Source,[string]$Destination,$Before,$After,[string]$Token) {
    $null=Expect $Source $After
    $null=Expect $Destination $Before
    $parent=[IO.Path]::GetDirectoryName($Destination);$null=Plain-Existing $parent $true
    $temp=Under $parent ('.wojd-rc-'+$Token+'-'+[Guid]::NewGuid().ToString('N')+'.tmp')
    [IO.File]::Copy($Source,$temp,$false);$null=Expect $temp $After
    Closed;$null=Expect $Destination $Before
    if($Before.exists){[IO.File]::Replace($temp,$Destination,[NullString]::Value)}else{[IO.File]::Move($temp,$Destination)}
    $null=Expect $Destination $After
}
function Remove-Owned([string]$Path,$Before,[string]$Directory,[int]$Ordinal) {
    $null=Expect $Path $Before
    if(-not $Before.exists){return}
    Closed
    $removed=Under $Directory ('removed-'+$Ordinal+'-'+[Guid]::NewGuid().ToString('N')+'.bin')
    [IO.File]::Move($Path,$removed);$null=Expect $removed $Before
}
function Restore-Journal($Journal,[string]$Directory) {
    Require ($Journal.format_version -eq 1 -and $Journal.owner -ceq $Owner -and $Journal.game_exe -ieq $script:Game.exe) 'Journal khong thuoc client nay.'
    Require ($Journal.id -cmatch '^[a-f0-9]{32}$' -and [IO.Path]::GetFileName($Directory) -ceq $Journal.id) 'Journal ID khong hop le.'
    Require ($Journal.action -in @('Install','Uninstall')) 'Journal action khong hop le.'
    $seen=@{};$index=0
    foreach($row in @($Journal.files)){
        Require ($row.target -in $JournalTargets -and -not $seen.ContainsKey($row.target)) 'Journal co file la/trung lap.'
        Valid-Pin $row.before $true;Valid-Pin $row.after $true
        Require ($row.retain_created_owner -is [bool] -and (-not $row.retain_created_owner -or ($row.target -ceq 'data/ownership.json' -and -not $row.before.exists -and $row.after.exists))) 'Journal retain policy khong hop le.'
        if($row.before.exists){
            Require ($row.backup -ceq ('before-'+$index+'.bin')) 'Backup journal khong hop le.'
            $null=Expect (Under $Directory $row.backup) $row.before
        }else{Require ($null -eq $row.backup) 'File absent khong duoc co backup.'}
        $current=Maybe-Pin (Target $row.target)
        Require ((Same-Pin $current $row.before) -or (Same-Pin $current $row.after)) "File da thay doi sau giao dich; khong khoi phuc de: $($row.target)"
        $seen[$row.target]=$true;$index++
    }
    Require ($seen.Count -eq $JournalTargets.Count) 'Journal thieu file.'
    Closed
    $Journal.status='ROLLING_BACK';Write-Journal $Journal $Directory
    $rows=@($Journal.files)
    for($i=$rows.Count-1;$i -ge 0;$i--){
        $row=$rows[$i];$path=Target $row.target;$current=Maybe-Pin $path
        if($row.retain_created_owner){continue}
        if(Same-Pin $current $row.before){continue}
        if($row.before.exists){Publish (Under $Directory $row.backup) $path $current $row.before ('rollback-'+$Journal.id)}
        else{Remove-Owned $path $current $Directory $i}
    }
    foreach($row in $rows){if(-not $row.retain_created_owner){$null=Expect (Target $row.target) $row.before}}
    $Journal.status='ROLLED_BACK';Write-Journal $Journal $Directory
}
function Original-DllSource {
    $mirror=Target 'bin/wojd_dbghelp_original.dll'
    $source=if(Test-Path -LiteralPath $mirror){$mirror}else{Target 'bin/dbghelp.dll'}
    $null=Expect $source $script:VendorPin
    return $source
}
function Run-Transaction($Installation,[hashtable]$BeforePins) {
    $id=[Guid]::NewGuid().ToString('N')
    $transactions=Under $script:Game.data 'transactions'
    if(-not (Test-Path -LiteralPath $transactions)){$null=[IO.Directory]::CreateDirectory($transactions)}
    $null=Plain-Existing $transactions $true
    $directory=Under $transactions $id;$null=[IO.Directory]::CreateDirectory($directory)
    $planning=[pscustomobject]@{format_version=1;owner=$Owner;id=$id;game_exe=$script:Game.exe;action=$Action;
        release_id=$script:Manifest.release_id;created_at=[DateTime]::UtcNow.ToString('o');status='PLANNING';files=@()}
    Write-Journal $planning $directory
    $ownershipDocument=[ordered]@{format_version=2;owner=$Owner;game_exe=$script:Game.exe}
    $ownerSource=Under $directory 'owner.json';Write-New $ownerSource (Json-Bytes $ownershipDocument)
    $sources=@{};$afterPins=@{}
    if($Action -eq 'Install'){
        $files=@()
        foreach($name in $ManagedTargets){$afterPins[$name]=[pscustomobject]@{exists=$false;bytes=0;sha256=$null}}
        foreach($targetName in $ProfilePayloadSources[$script:SelectedProfile].Keys){
            $relative=$ProfilePayloadSources[$script:SelectedProfile][$targetName]
            $sources[$targetName]=Under $script:PackageRoot $relative;$afterPins[$targetName]=$script:PackageFiles[$relative]
        }
        if($script:SelectedProfile -ceq 'runtime'){
            $sources['bin/wojd_dbghelp_original.dll']=$script:Game.vendor;$afterPins['bin/wojd_dbghelp_original.dll']=$script:VendorPin
        }elseif($Installation.original_bin_dll_existed){
            $sources['bin/dbghelp.dll']=Original-DllSource;$afterPins['bin/dbghelp.dll']=$script:VendorPin
        }
        foreach($targetName in $ManagedTargets){
            $pin=$afterPins[$targetName]
            $files+=[ordered]@{target=$targetName;exists=$pin.exists;bytes=$pin.bytes;sha256=$pin.sha256}
        }
        $next=[ordered]@{format_version=2;owner=$Owner;game_exe=$script:Game.exe;profile=$script:SelectedProfile;release_id=$script:Manifest.release_id;
            source_revision=$script:Manifest.source_revision;original_bin_dll_existed=$Installation.original_bin_dll_existed;
            migration_from=$Installation.kind;installed_at=[DateTime]::UtcNow.ToString('o');files=$files;transaction_id=$id}
        $stateSource=Under $directory 'new-install-state.json';Write-New $stateSource (Json-Bytes $next)
        $sources['data/install-state.json']=$stateSource;$afterPins['data/install-state.json']=Pin $stateSource
        $sources['data/ownership.json']=$ownerSource;$afterPins['data/ownership.json']=Pin $ownerSource
    }else{
        foreach($name in $ManagedTargets+@('data/install-state.json')){$afterPins[$name]=[pscustomobject]@{exists=$false;bytes=0;sha256=$null}}
        if($Installation.original_bin_dll_existed){$sources['bin/dbghelp.dll']=Original-DllSource;$afterPins['bin/dbghelp.dll']=$script:VendorPin}
        # Ownership marker and transaction history intentionally survive uninstall.
        $sources['data/ownership.json']=Target 'data/ownership.json';$afterPins['data/ownership.json']=$BeforePins['data/ownership.json']
    }
    $rows=@();$index=0
    foreach($name in $JournalTargets){
        $before=$BeforePins[$name];$null=Expect (Target $name) $before
        $backup=$null
        if($before.exists){$backup='before-'+$index+'.bin';[IO.File]::Copy((Target $name),(Under $directory $backup),$false);$null=Expect (Under $directory $backup) $before}
        $rows+=[ordered]@{target=$name;before=$before;after=$afterPins[$name];backup=$backup;
            retain_created_owner=($name -ceq 'data/ownership.json' -and -not $before.exists -and $afterPins[$name].exists)}
        $index++
    }
    $journal=[pscustomobject]@{format_version=1;owner=$Owner;id=$id;game_exe=$script:Game.exe;action=$Action;
        release_id=$script:Manifest.release_id;created_at=[DateTime]::UtcNow.ToString('o');status='PREPARED';files=$rows}
    Write-Journal $journal $directory
    $script:ActiveJournal=$journal;$script:ActiveTransaction=$directory
    Closed
    $index=0
    # Publish ownership first so a fresh failed install can retain its own history safely.
    $ordered=@($rows | Where-Object { $_.target -ceq 'data/ownership.json' })+@($rows | Where-Object { $_.target -cne 'data/ownership.json' })
    foreach($row in $ordered){
        if(Same-Pin $row.before $row.after){continue}
        if($row.after.exists){Publish $sources[$row.target] (Target $row.target) $row.before $row.after $id}
        else{Remove-Owned (Target $row.target) $row.before $directory $index}
        $index++
    }
    foreach($row in $rows){$null=Expect (Target $row.target) $row.after}
    Closed;$journal.status='COMMITTED';Write-Journal $journal $directory
    $script:ActiveJournal=$null
    Write-Output "Hoan tat $Action. Ma giao dich: $id"
    Write-Output "Backup va journal: $directory"
}

try{
    Check-Package
    $script:Game=Resolve-Game $GameRoot
    Closed
    if($Action -eq 'Rollback'){
        Read-Owner
        if([string]::IsNullOrWhiteSpace($TransactionId)){$TransactionId=Read-Host 'Nhap ma giao dich 32 ky tu hex'}
        Require ($TransactionId -cmatch '^[a-f0-9]{32}$') 'Nhap ma giao dich 32 ky tu hex de khoi phuc.'
        Acquire-Lock
        $directory=Under $script:Game.data ('transactions/'+$TransactionId)
        $null=Plain-Existing $directory $true
        $journal=Read-Json (Under $directory 'journal.json')
        Restore-Journal $journal $directory
        Write-Output "Da khoi phuc giao dich: $TransactionId"
    }else{
        Check-Pending
        $installation=Read-Installation
        if($Action -eq 'Verify'){
            Require ($installation.kind -cne 'FRESH') 'Chua co ban Viet hoa duoc quan ly.'
            Write-Output "Da kiem tra file cai dat: $($installation.kind)."
        }else{
            Require ($Action -eq 'Install' -or $installation.kind -cne 'FRESH') 'Chua co ban Viet hoa de go.'
            if($Action -eq 'Install'){
                if($script:SelectedProfile -ceq 'runtime'){X64-PE $script:Game.vendor $true;$null=Expect $script:Game.vendor $script:VendorPin}
                foreach($name in $RetiredPakNames){Require (-not (Test-Path -LiteralPath (Under $script:Game.pak $name))) "Con PAK Viet hoa cu: $name. Hay go bang bo cai cu truoc."}
            }
            $before=@{};foreach($name in $JournalTargets){$before[$name]=Maybe-Pin (Target $name)}
            Acquire-Lock
            if($script:BootstrappedOwner){
                Require ($installation.kind -ceq 'FRESH' -and -not $before['data/ownership.json'].exists) 'Khong duoc thay quyen so huu da co.'
                $before['data/ownership.json']=Pin (Target 'data/ownership.json')
            }
            # Do not adopt a mutation between the first validation and pin capture.
            # Refresh ownership/migration evidence while holding the installer lock;
            # the transaction uses this current kind and original-DLL baseline.
            Check-Pending
            $installation=Read-Installation
            Require ($Action -eq 'Install' -or $installation.kind -cne 'FRESH') 'Chua co ban Viet hoa de go.'
            foreach($name in $JournalTargets){$null=Expect (Target $name) $before[$name]}
            Run-Transaction $installation $before
            if($Action -eq 'Install'){
                if($script:SelectedProfile -ceq 'legacy'){Write-Output 'Da cai Legacy: chi PAK, khong nap DLL Viet hoa; dich chat khong hoat dong.'}
                else{Write-Output 'Da cai ban day du. Neu game bao da cap nhat dia chi, thoat game roi mo lai.'}
                Write-Output 'Mo game bang launcher nhu thuong le.'
                Write-Output 'Ban tam van con cac cau chua review nghia; xem README va known issues.'
                if($ChatSetup -and $script:SelectedProfile -ceq 'runtime'){
                    $setup=Under $script:PackageRoot 'ChatSettings.ps1'
                    Require ($script:PackageFiles.ContainsKey('ChatSettings.ps1')) 'Goi thieu thiet lap chat.'
                    $null=Expect $setup $script:PackageFiles['ChatSettings.ps1']
                    try{& $setup -GameRoot $script:Game.client}
                    catch{Write-Warning 'Ban Viet hoa da cai thanh cong. Thiet lap chat chua hoan tat; chay chat-settings.bat de chon lai.'}
                }
            }else{Write-Output 'Da go file Viet hoa. Cache, cai dat, log va lich su giao dich duoc giu lai.'}
        }
    }
}catch{
    $failure=$_.Exception.Message
    if($script:ActiveJournal){
        try{Restore-Journal $script:ActiveJournal $script:ActiveTransaction;Write-Output 'Giao dich loi da duoc khoi phuc.'}
        catch{Write-Warning ('Khoi phuc chua xong: '+$_.Exception.Message);Write-Warning ('Dong game va dung Rollback voi ma '+$script:ActiveJournal.id+'. Backup: '+$script:ActiveTransaction)}
    }
    Write-Error $failure -ErrorAction Continue
    exit 1
}finally{if($script:Lock){$script:Lock.Dispose()}}
