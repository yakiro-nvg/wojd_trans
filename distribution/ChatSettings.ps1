[CmdletBinding()]
param(
    [string]$GameRoot,
    [ValidateSet('Menu','Off','Google','DeepL','DeepSeek','Gemini','Custom','Keep')][string]$Mode='Menu',
    [Alias('ApiKey')][Security.SecureString]$DeepLKey,
    [string]$Model,
    [switch]$UseEnvironmentKey,
    [hashtable]$Channels=@{},
    [ValidateRange(16,8192)][int]$CacheEntries=1024,
    [ValidateRange(1,60)][int]$CacheIdleMinutes=10
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Chat-Require($Value,[string]$Message){if(-not $Value){throw $Message}}
function Chat-Closed {
    $running=@(Get-Process -ErrorAction Stop | Where-Object {$_.ProcessName -in @('ZhuxianClient-Win64-Shipping','ZhuxianClient')})
    Chat-Require ($running.Count -eq 0) 'Hãy thoát game bình thường trước khi đổi dịch chat.'
}
function Chat-Plain([string]$Path,[bool]$Directory) {
    $item=Get-Item -LiteralPath $Path -Force
    Chat-Require ([bool]$item.PSIsContainer -eq $Directory) 'Đường dẫn không đúng loại file/thư mục.'
    $cursor=$item
    while($cursor){
        Chat-Require (-not ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'Không dùng file hoặc thư mục liên kết.'
        $parent=if($cursor.PSIsContainer){$cursor.Parent}else{$cursor.Directory}
        $cursor=if($parent){Get-Item -LiteralPath $parent.FullName -Force}else{$null}
    }
    return $item.FullName
}
function Chat-Read([string]$Path) {
    if(-not (Test-Path -LiteralPath $Path)){return $null}
    $null=Chat-Plain $Path $false
    Chat-Require ((Get-Item -LiteralPath $Path).Length -le 8192) 'File thiết lập chat vượt giới hạn; giữ nguyên để kiểm tra.'
    return ,([IO.File]::ReadAllBytes($Path))
}
function Chat-Same($A,$B) {
    if($null -eq $A -or $null -eq $B){return $null -eq $A -and $null -eq $B}
    return [Convert]::ToBase64String($A) -ceq [Convert]::ToBase64String($B)
}
function Chat-Publish([string]$Path,$Bytes,$Expected) {
    Chat-Closed
    Chat-Require (Chat-Same (Chat-Read $Path) $Expected) 'Thiết lập chat vừa bị thay đổi; không ghi đè.'
    if(Chat-Same $Bytes $Expected){return}
    if($null -eq $Bytes){[IO.File]::Delete($Path);return}
    $parent=Chat-Plain ([IO.Path]::GetDirectoryName($Path)) $true
    $temporary=Join-Path $parent ('.wojd-chat-'+[Guid]::NewGuid().ToString('N')+'.tmp')
    try{
        $stream=[IO.File]::Open($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try{$stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
        Chat-Closed
        Chat-Require (Chat-Same (Chat-Read $Path) $Expected) 'Thiết lập chat vừa bị thay đổi; không ghi đè.'
        if($null -ne $Expected){[IO.File]::Replace($temporary,$Path,[NullString]::Value)}else{[IO.File]::Move($temporary,$Path)}
    }finally{if(Test-Path -LiteralPath $temporary){$null=Chat-Plain $temporary $false;[IO.File]::Delete($temporary)}}
}
function Chat-EnvironmentKey([string]$Name) {
    # Query persistent scopes directly: the parent app may predate the variable.
    $keyText=$null
    try{
        foreach($scope in @('User','Machine','Process')){
            $keyText=[Environment]::GetEnvironmentVariable($Name,$scope)
            if(-not [string]::IsNullOrEmpty($keyText)){break}
        }
        if([string]::IsNullOrEmpty($keyText)){return $null}
        $secure=New-Object Security.SecureString
        foreach($character in $keyText.ToCharArray()){$secure.AppendChar($character)}
        $secure.MakeReadOnly()
        return $secure
    }finally{$keyText=$null}
}
function Chat-Protect([Security.SecureString]$Key,[string]$Provider) {
    Chat-Require ($null -ne $Key -and $Key.Length -ge 16 -and $Key.Length -le 256) 'API key không hợp lệ. Hãy sao chép lại từ tài khoản dịch vụ đã chọn.'
    $pointer=[IntPtr]::Zero;$plain=New-Object byte[] $Key.Length
    try{
        $pointer=[Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($Key)
        for($i=0;$i -lt $plain.Length;$i++){
            $value=[int][Runtime.InteropServices.Marshal]::ReadInt16($pointer,$i*2)
            Chat-Require ($value -gt 32 -and $value -lt 127) 'API key có ký tự không hợp lệ; không thêm khoảng trắng hoặc xuống dòng.'
            $plain[$i]=[byte]$value
        }
        Add-Type -AssemblyName System.Security
        $entropyText=if($Provider -eq 'deepl'){'WOJD-CHAT-KEY-V1'}else{'WOJD-CHAT-KEY-V2:'+$Provider}
        $entropy=[Text.Encoding]::ASCII.GetBytes($entropyText)
        $protected=[Security.Cryptography.ProtectedData]::Protect($plain,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
        $headerText=if($Provider -eq 'deepl'){'WJDK1'}elseif($Provider -eq 'deepseek'){'WJDK24'}else{'WJDK25'}
        $header=[Text.Encoding]::ASCII.GetBytes($headerText)
        return ,([byte[]]($header+$protected))
    }finally{
        [Array]::Clear($plain,0,$plain.Length)
        if($pointer -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($pointer)}
    }
}

function Chat-Header([string]$Provider) {
    if($Provider -eq 'deepl'){return 'WJDK1'}
    if($Provider -eq 'deepseek'){return 'WJDK24'}
    return 'WJDK25'
}
function Chat-Reusable($Bytes,[string]$Provider) {
    if($null -eq $Bytes){return $false}
    $header=Chat-Header $Provider
    if($Bytes.Length -le $header.Length -or [Text.Encoding]::ASCII.GetString($Bytes,0,$header.Length) -cne $header){return $false}
    $plain=$null
    try{
        Add-Type -AssemblyName System.Security
        $entropy=if($Provider -eq 'deepl'){'WOJD-CHAT-KEY-V1'}else{'WOJD-CHAT-KEY-V2:'+$Provider}
        $plain=[Security.Cryptography.ProtectedData]::Unprotect($Bytes[$header.Length..($Bytes.Length-1)],[Text.Encoding]::ASCII.GetBytes($entropy),[Security.Cryptography.DataProtectionScope]::CurrentUser)
        if($plain.Length -lt 16 -or $plain.Length -gt 256){return $false}
        foreach($value in $plain){if($value -le 32 -or $value -ge 127){return $false}}
        return $true
    }catch{return $false}
    finally{if($null -ne $plain){[Array]::Clear($plain,0,$plain.Length)}}
}
function Chat-Model([string]$Provider,[string]$Requested,[bool]$Interactive) {
    if($Provider -notin @('gemini','deepseek')){
        Chat-Require ([string]::IsNullOrWhiteSpace($Requested)) 'Chỉ chọn model khi dùng Gemini hoặc DeepSeek.'
        return ''
    }
    $value=$Requested
    if([string]::IsNullOrWhiteSpace($value)){
        $value=if($Provider -eq 'gemini'){'gemini-3.6-flash'}else{'deepseek-flash'}
        if($Interactive -and $Provider -eq 'gemini'){
            Write-Host 'Giá USD / triệu token vào và ra, kiểm tra 24/10/2026:'
            Write-Host '  1. Gemini 3.6 Flash: 0,75 / 3,75 — khoảng 1,5 giây trong bộ thử nhỏ'
            Write-Host '  2. Gemini 3.1 Flash-Lite: 0,25 / 1,50 — tiết kiệm, dễ sót ngữ cảnh hơn'
            Write-Host '  3. Gemini 3 Flash Preview: 0,50 / 3,00 — tiếng lóng khá trong bộ thử'
            Write-Host '  4. Nhập mã model Flash tương thích (nâng cao)'
            Write-Host 'Giá 3.6 là ưu đãi hiện hành. Giá, chất lượng và độ trễ: xem CHAT_GUIDE.txt.'
            $choice=(Read-Host 'Chọn model 1–4; Enter = 1').Trim()
            if($choice -in @('','1')){}
            elseif($choice -eq '2'){$value='gemini-3.1-flash-lite'}
            elseif($choice -eq '3'){$value='gemini-3-flash-preview'}
            elseif($choice -eq '4'){$value=(Read-Host 'Mã model Gemini Flash').Trim()}
            else{throw 'Model không hợp lệ; chưa đổi dịch chat.'}
        }elseif($Interactive){
            Write-Host 'DeepSeek Flash: 0,15–0,30 USD / triệu token vào; 0,60–1,20 USD / triệu token ra.'
            Write-Host 'Khoảng 0,8 giây trong bộ thử nhỏ; tiếng lóng vẫn có thể sai.'
            $custom=(Read-Host 'Enter dùng deepseek-flash; hoặc nhập mã model tương thích').Trim()
            if($custom -ne ''){$value=$custom}
        }
    }
    Chat-Require ($value -cmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$') 'Tên model không hợp lệ; dùng đúng mã model của dịch vụ.'
    return $value
}
function Chat-Profile([string]$Provider,[string]$Requested,[bool]$Interactive) {
    Chat-Require ($Provider -in @('none','google-web','deepl','deepseek','gemini','inherit')) 'Dịch vụ không hợp lệ.'
    return @{Provider=$Provider;Model=(Chat-Model $Provider $Requested $Interactive)}
}
function Chat-Label($Profile) {
    $name=switch($Profile.Provider){'none'{'Tắt'} 'inherit'{'Theo mặc định'} 'google-web'{'Google Translate web'} 'deepl'{'DeepL'} 'deepseek'{'DeepSeek'} 'gemini'{'Gemini'}}
    if($Profile.Model){return $name+' / '+$Profile.Model}
    return $name
}

$channelNames=[ordered]@{
    local='Gần đây';world='Thế Giới';squad='Đội';team='Đoàn';gang='Bang';sect='Môn phái';
    battlefield='Chiến Trường';friend='Bạn bè / riêng';broadcast='Truyền âm';
    broadcast_anonymous='Truyền âm ẩn danh';region='Khu vực';all_broadcast='Truyền âm liên server';
    all_broadcast_anonymous='Truyền âm liên server ẩn danh';force='Phe';arena='Phòng đấu';observe='Theo dõi'
}
$lock=$null;$createdKeys=New-Object 'Collections.Generic.List[Security.SecureString]'
try{
    Chat-Closed
    Chat-Require (-not ($UseEnvironmentKey -and $null -ne $DeepLKey)) 'Chọn dùng biến môi trường hoặc nhập key, không dùng cả hai.'
    if([string]::IsNullOrWhiteSpace($GameRoot)){$GameRoot=(Read-Host 'Dán đường dẫn thư mục game (Game, ZhuxianClient hoặc Binaries\Win64)').Trim('"')}
    $root=Chat-Plain ([IO.Path]::GetFullPath($GameRoot)) $true
    $relative=@('ZhuxianClient-Win64-Shipping.exe','Binaries/Win64/ZhuxianClient-Win64-Shipping.exe','ZhuxianClient/Binaries/Win64/ZhuxianClient-Win64-Shipping.exe','ZXSJ/Game/ZhuxianClient/Binaries/Win64/ZhuxianClient-Win64-Shipping.exe')
    $matches=@();foreach($name in $relative){$candidate=Join-Path $root $name;if(Test-Path -LiteralPath $candidate -PathType Leaf){$matches+=Chat-Plain $candidate $false}}
    Chat-Require ($matches.Count -eq 1) 'Chưa tìm thấy đúng client. Chọn lại thư mục Binaries\Win64 của game.'
    $exe=$matches[0];$data=Chat-Plain (Join-Path ([IO.Path]::GetDirectoryName($exe)) 'wojd') $true
    $ownerPath=Join-Path $data 'ownership.json';$null=Chat-Plain $ownerPath $false
    $owner=ConvertFrom-Json ([IO.File]::ReadAllText($ownerPath,[Text.Encoding]::UTF8))
    Chat-Require ($owner.owner -ceq 'wojd-localization' -and [IO.Path]::GetFullPath($owner.game_exe) -ieq $exe) 'Hãy cài bản Việt hóa cho client này trước khi bật dịch chat.'
    $configPath=Join-Path $data 'chat.ini';$beforeConfig=Chat-Read $configPath
    $keyNames=@('chat-key.bin','chat-key-deepl.bin','chat-key-deepseek.bin','chat-key-gemini.bin')
    $beforeKeys=@{};$wantedKeys=@{};$currentKeys=@{}
    foreach($name in $keyNames){$beforeKeys[$name]=Chat-Read (Join-Path $data $name);$wantedKeys[$name]=$null}
    $interactiveMenu=$Mode -eq 'Menu'
    if($interactiveMenu){
        Write-Host ''
        Write-Host 'DỊCH CHAT NGƯỜI CHƠI — TÙY CHỌN'
        Write-Host 'Bước 1: chọn dịch vụ mặc định. Bước 2: đổi riêng từng kênh nếu muốn.'
        Write-Host 'Khi bật, chữ trong tin cần dịch được gửi tới dịch vụ đã chọn.'
        Write-Host 'Tin gốc và bản Việt cùng một mục. Bỏ qua hệ thống và Chiêu Mộ.'
        Write-Host '  0. Tắt dịch chat (mặc định khi cài lần đầu)'
        Write-Host '  1. Google Translate web — miễn phí, không key; có thể sai tiếng lóng'
        Write-Host '  2. DeepL API — cần key; hợp câu thường, tiếng lóng có thể dịch sát chữ'
        Write-Host '  3. DeepSeek API — cần key; nhanh, rẻ, vẫn có thể sai viết tắt'
        Write-Host '  4. Gemini API — cần key; chọn model theo giá và chất lượng mong muốn'
        if($null -ne $beforeConfig){Write-Host '  5. Giữ thiết lập hiện tại (mặc định khi cập nhật)'}
        Write-Host '  6. Chỉ bật các kênh tự chọn; mặc định các kênh còn lại tắt'
        Write-Host 'Xem CHAT_GUIDE.txt về giá và hạn mức. Kết quả dịch không được bảo đảm đúng.'
        $choice=(Read-Host 'Chọn dịch vụ 0–6; Enter dùng mặc định').Trim()
        if($choice -eq ''){$Mode=if($null -ne $beforeConfig){'Keep'}else{'Off'}}
        elseif($choice -eq '0'){$Mode='Off'}elseif($choice -eq '1'){$Mode='Google'}elseif($choice -eq '2'){$Mode='DeepL'}
        elseif($choice -eq '3'){$Mode='DeepSeek'}elseif($choice -eq '4'){$Mode='Gemini'}
        elseif($choice -eq '5' -and $null -ne $beforeConfig){$Mode='Keep'}elseif($choice -eq '6'){$Mode='Custom'}
        else{throw 'Lựa chọn không hợp lệ; chưa đổi dịch chat.'}
    }
    if($Mode -eq 'Keep'){Write-Host 'Đã giữ nguyên thiết lập dịch chat.';return}
    $provider=if($Mode -eq 'Google'){'google-web'}elseif($Mode -in @('Off','Custom')){'none'}else{$Mode.ToLowerInvariant()}
    $default=Chat-Profile $provider $Model $interactiveMenu
    $routes=@{}
    foreach($key in $Channels.Keys){
        Chat-Require ($channelNames.Contains($key)) 'Tên kênh không được hỗ trợ; hệ thống và Chiêu Mộ luôn được bỏ qua.'
        $entry=$Channels[$key]
        Chat-Require ($entry -is [hashtable] -and $entry.ContainsKey('Provider')) 'Mỗi kênh cần một lựa chọn dịch vụ.'
        foreach($field in $entry.Keys){Chat-Require ($field -in @('Provider','Model')) 'Thiết lập kênh có trường không được hỗ trợ.'}
        $selectedModel=if($entry.ContainsKey('Model')){[string]$entry.Model}else{''}
        $routes[$key]=Chat-Profile ([string]$entry.Provider) $selectedModel $false
    }
    Chat-Require ($Mode -ne 'Off' -or $routes.Count -eq 0) 'Chọn Custom để chỉ bật một số kênh; Off tắt toàn bộ.'
    if($interactiveMenu -and $Mode -ne 'Off'){
        Write-Host ''
        Write-Host 'BƯỚC 2 — LỰA CHỌN THEO KÊNH'
        Write-Host 'Kênh đông tin có thể chọn Google miễn phí, model rẻ hơn hoặc tắt để tiết kiệm.'
        Write-Host 'Đội/đoàn có thể dùng LLM khi cần hiểu giao tiếp. Bạn tự chọn; không tự chuyển dịch vụ khi lỗi.'
        Write-Host 'Thiết lập mới thay các lựa chọn kênh cũ; kênh không đổi sẽ theo mặc định vừa chọn.'
        $customize=$Mode -eq 'Custom'
        if(-not $customize){
            $answer=(Read-Host 'Đổi riêng theo kênh? Enter = dùng chung; 1 = tùy chỉnh').Trim()
            Chat-Require ($answer -in @('','1')) 'Lựa chọn không hợp lệ; chưa đổi dịch chat.'
            $customize=$answer -eq '1'
        }
        $keys=@($channelNames.Keys)
        while($customize){
            Write-Host ('Mặc định: '+(Chat-Label $default))
            for($i=0;$i -lt $keys.Count;$i++){
                $key=$keys[$i];$label=if($routes.ContainsKey($key)){Chat-Label $routes[$key]}else{'Theo mặc định'}
                Write-Host ('  '+($i+1)+'. '+$channelNames[$key]+' — '+$label)
            }
            $answer=(Read-Host 'Số kênh muốn đổi; Enter = xong').Trim()
            if($answer -eq ''){break}
            $number=0
            Chat-Require ([int]::TryParse($answer,[ref]$number) -and $number -ge 1 -and $number -le $keys.Count) 'Số kênh không hợp lệ.'
            $key=$keys[$number-1]
            Write-Host '  0. Theo mặc định; 1. Tắt; 2. Google; 3. DeepL; 4. DeepSeek; 5. Gemini'
            $choice=(Read-Host ('Dịch vụ cho '+$channelNames[$key]+'; Enter = 0')).Trim()
            $selected=switch($choice){''{'inherit'} '0'{'inherit'} '1'{'none'} '2'{'google-web'} '3'{'deepl'} '4'{'deepseek'} '5'{'gemini'} default{throw 'Dịch vụ không hợp lệ.'}}
            $routes[$key]=Chat-Profile $selected '' $true
        }
        Write-Host 'Cache giữ lại kết quả tin trùng để giảm số lần gọi dịch vụ; chỉ lưu trong RAM.'
        $answer=(Read-Host ('Số mục cache tối đa 16–8192; Enter = '+$CacheEntries)).Trim()
        if($answer -ne ''){
            $number=0
            Chat-Require ([int]::TryParse($answer,[ref]$number) -and $number -ge 16 -and $number -le 8192) 'Số mục cache không hợp lệ.'
            $CacheEntries=$number
        }
    }
    $used=@{}
    foreach($key in $channelNames.Keys){
        $effective=if($routes.ContainsKey($key) -and $routes[$key].Provider -ne 'inherit'){$routes[$key]}else{$default}
        if($effective.Provider -ne 'none'){$used[$effective.Provider]=$true}
    }
    if($used.Keys | Where-Object {$_ -in @('deepl','deepseek','gemini')}){
        Write-Host ''
        Write-Host 'GIỮ KÍN API KEY: người có key có thể dùng hạn mức hoặc phát sinh phí trên tài khoản của bạn.'
        Write-Host 'Không gửi key vào chat/log, ảnh chụp, livestream hoặc file chia sẻ. Chú ý màn hình tài khoản dịch vụ và biến môi trường.'
        Write-Host 'Bộ cài che chỗ nhập, mã hóa key bằng Windows và không ghi key vào log riêng.'
        Write-Host 'Nếu lỡ để lộ: thu hồi key cũ tại dịch vụ, tạo key mới rồi chạy lại chat-settings.bat.'
    }
    foreach($service in @('deepl','deepseek','gemini')){
        if(-not $used.ContainsKey($service)){continue}
        $name='chat-key-'+$service+'.bin';$saved=$beforeKeys[$name]
        if(-not (Chat-Reusable $saved $service)){$saved=$beforeKeys['chat-key.bin']}
        $reusable=Chat-Reusable $saved $service
        $selectedKey=if($service -eq $provider){$DeepLKey}else{$null}
        if($null -eq $selectedKey){
            $envName=switch($service){'deepl'{'DEEPL_KEY'} 'deepseek'{'DEEPSEEK_API_KEY'} 'gemini'{'GEMINI_API_KEY'}}
            $envKey=Chat-EnvironmentKey $envName
            if($null -ne $envKey){$createdKeys.Add($envKey)}
            if($UseEnvironmentKey){
                Chat-Require ($null -ne $envKey) ('Chưa tìm thấy '+$envName+' trong biến môi trường Windows.')
                $selectedKey=$envKey
            }elseif($null -ne $envKey){
                Write-Host ('Đã tìm thấy '+$envName+' trong biến môi trường; nội dung key không hiển thị.')
                $answer=(Read-Host ('Dùng key '+$service+' này? Enter = Có; N = nhập khác/giữ key đã lưu')).Trim()
                if($answer -eq '' -or $answer -match '^(?i:y|yes|c|có)$'){$selectedKey=$envKey}
                else{Chat-Require ($answer -match '^(?i:n|no|k|không)$') 'Lựa chọn không hợp lệ.'}
            }
        }
        if($null -eq $selectedKey){
            if($reusable){Write-Host ('Để trống để giữ key '+$service+' đã lưu trên máy.')}
            $selectedKey=Read-Host ('Dán API key '+$service+' (nội dung được che)') -AsSecureString
            $createdKeys.Add($selectedKey)
        }
        if($selectedKey.Length -eq 0 -and $reusable){$wantedKeys[$name]=$saved}
        else{$wantedKeys[$name]=Chat-Protect $selectedKey $service}
    }
    $enabled=if($used.Count -gt 0){1}else{0}
    $lines=New-Object 'Collections.Generic.List[string]'
    $lines.Add('[chat]');$lines.Add('enabled='+$enabled);$lines.Add('provider='+$default.Provider)
    if($default.Model){$lines.Add('model='+$default.Model)}
    if($Mode -ne 'Off'){
        $lines.Add('cache_entries='+$CacheEntries);$lines.Add('cache_idle_minutes='+$CacheIdleMinutes)
        foreach($key in $channelNames.Keys){
            if(-not $routes.ContainsKey($key) -or $routes[$key].Provider -eq 'inherit'){continue}
            $lines.Add('');$lines.Add('[channel.'+$key+']');$lines.Add('provider='+$routes[$key].Provider)
            if($routes[$key].Model){$lines.Add('model='+$routes[$key].Model)}
        }
    }
    $wantedConfig=[Text.Encoding]::ASCII.GetBytes(($lines -join "`r`n")+"`r`n")
    Chat-Require ($wantedConfig.Length -le 8192) 'Thiết lập vượt giới hạn.'
    $lockPath=Join-Path $data '.chat-settings.lock';if(Test-Path -LiteralPath $lockPath){$null=Chat-Plain $lockPath $false}
    $lock=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    Chat-Require (Chat-Same (Chat-Read $configPath) $beforeConfig) 'Thiết lập chat vừa bị đổi; hãy chạy lại.'
    foreach($name in $keyNames){Chat-Require (Chat-Same (Chat-Read (Join-Path $data $name)) $beforeKeys[$name]) 'Key đã lưu vừa bị đổi; hãy chạy lại.';$currentKeys[$name]=$beforeKeys[$name]}
    $disabled=[Text.Encoding]::ASCII.GetBytes("[chat]`r`nenabled=0`r`nprovider=none`r`n")
    # Disable admission before committing multiple provider keys. On power loss
    # midway, startup stays off. Rollback never overwrites concurrent changes.
    $currentConfig=$beforeConfig
    try{
        Chat-Publish $configPath $disabled $currentConfig;$currentConfig=$disabled
        foreach($name in $keyNames){Chat-Publish (Join-Path $data $name) $wantedKeys[$name] $currentKeys[$name];$currentKeys[$name]=$wantedKeys[$name]}
        Chat-Publish $configPath $wantedConfig $currentConfig;$currentConfig=$wantedConfig
    }catch{
        $failure=$_.Exception.Message
        try{
            foreach($name in $keyNames){Chat-Publish (Join-Path $data $name) $beforeKeys[$name] $currentKeys[$name]}
            Chat-Publish $configPath $beforeConfig $currentConfig
        }catch{throw 'Chưa khôi phục được thiết lập chat sau lỗi. Giữ game đóng và chạy chat-settings.bat để chọn lại.'}
        throw $failure
    }
    Chat-Require (Chat-Same (Chat-Read $configPath) $wantedConfig) 'Chưa xác minh được thiết lập chat đã lưu.'
    foreach($name in $keyNames){Chat-Require (Chat-Same (Chat-Read (Join-Path $data $name)) $wantedKeys[$name]) 'Chưa xác minh được key đã lưu.'}
    if(-not $enabled){Write-Host 'Đã tắt dịch chat và xóa API key đang lưu. Phần Việt hóa game vẫn hoạt động.'}
    else{
        Write-Host ('Đã lưu. Mặc định: '+(Chat-Label $default))
        foreach($key in $channelNames.Keys){if($routes.ContainsKey($key)){Write-Host ('  '+$channelNames[$key]+': '+(Chat-Label $routes[$key]))}}
        Write-Host ('Cache: tối đa '+$CacheEntries+' mục, '+$CacheIdleMinutes+' phút không dùng; trần nội dung 64 MiB.')
        Write-Host 'Mở game qua launcher để dùng. Không tự chuyển dịch vụ khi lỗi.'
    }
}catch{Write-Error $_.Exception.Message -ErrorAction Continue;throw 'Chưa đổi được dịch chat. Nếu thư mục game bị hạn chế quyền ghi, chạy lại bằng Run as administrator.'}
finally{if($lock){$lock.Dispose()};foreach($secure in $createdKeys){$secure.Dispose()}}
