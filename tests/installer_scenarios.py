"""Independent, inert synthetic-tree lifecycle tests. Never loads PE fixtures."""
import copy
import hashlib
import json
import pathlib
import struct
import subprocess
import time
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUTHOR = ROOT / 'distribution'
OUT = ROOT / 'work/installer-scenarios'
OUT.mkdir(parents=True,exist_ok=True)
import tempfile
CASES = pathlib.Path(tempfile.mkdtemp(prefix='run-',dir=OUT)) / 'cases'
POWERSHELL = str(pathlib.Path(__import__('os').environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe')
SOURCE_SHA = hashlib.sha256((AUTHOR/'Installer.ps1').read_bytes()).hexdigest()
RESULTS = []
CALLS = []

def sha(b): return hashlib.sha256(b).hexdigest()
def pin(p):
    if not p.exists(): return dict(exists=False, bytes=0, sha256=None)
    b=p.read_bytes(); return dict(exists=True, bytes=len(b), sha256=sha(b))
def write(p,b):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(bytes(b) if isinstance(b,(bytes,bytearray)) else b.encode('utf-8'))
def dump(p,obj): write(p,json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def pe(dll, marker=b''):
    b=bytearray(256)+marker
    struct.pack_into('<H',b,0,0x5a4d);struct.pack_into('<I',b,0x3c,64)
    struct.pack_into('<IHH',b,64,0x4550,0x8664,0)
    struct.pack_into('<H',b,86,0x2000 if dll else 0)
    struct.pack_into('<H',b,88,0x20b)
    return bytes(b)

def make(name,stock=False,instrument=None):
    c=CASES/name
    assert not c.exists(), c
    c.mkdir(parents=True)
    game=c/'Ổ đĩa D người dùng thử/Game tùy chọn'
    client=game/'ZhuxianClient';binp=client/'Binaries/Win64';data=binp/'wojd';pak=client/'Content/Paks'
    vendor=game/'Engine/Binaries/ThirdParty/DbgHelp/dbghelp.dll'
    exe=binp/'ZhuxianClient-Win64-Shipping.exe'
    write(exe,pe(False,b'INERT-NOT-EXECUTABLE-FIXTURE'))
    write(vendor,pe(True,b'INERT-LOCAL-VENDOR'))
    write(pak/'pakchunk0-Windows.pak',b'official-file-preserve')
    if stock: write(binp/'dbghelp.dll',vendor.read_bytes())
    pkg=c/'Gói phát hành ở thư mục khác'
    source=(AUTHOR/'Installer.ps1').read_bytes()
    assert sha(source)==SOURCE_SHA
    if instrument:
        text=source.decode('utf-8')
        boundary='try{\n    Check-Package\n'
        assert text.count(boundary)==1
        text=text.replace(boundary,instrument+'\n'+boundary,1)
        source=text.encode('utf-8')
    write(pkg/'Installer.ps1',source)
    for n in ['install.bat','verify.bat','uninstall.bat','rollback.bat']:
        write(pkg/n,(AUTHOR/n).read_bytes())
    for n in ['README.txt','LICENSE','MinHook-LICENSE.txt','Archive-Session.ps1']:
        write(pkg/n,'INERT FIXTURE DOCUMENT '+n+'\n')
    write(pkg/'payload/dbghelp.dll',pe(True,b'INERT-NEW-PROXY'))
    write(pkg/'payload/catalog.bin',b'new-catalog-fixture')
    write(pkg/'payload/zz_WOJD_LOCALIZATION_P.pak',b'new-full-base-fixture')
    write(pkg/'payload/zz_WOJD_HUD_S2_1_P.pak',b'new-HUD-fixture')
    o=dict(case=c,game=game,client=client,bin=binp,data=data,pak=pak,vendor=vendor,exe=exe,pkg=pkg)
    manifest(o)
    return o

def manifest(o,legacy=None):
    files=[]
    for p in sorted(o['pkg'].rglob('*')):
        if p.is_file() and p.name!='manifest.json':
            pp=pin(p);files.append(dict(path=p.relative_to(o['pkg']).as_posix(),bytes=pp['bytes'],sha256=pp['sha256']))
    pp=pin(o['vendor'])
    m=dict(format_version=2,owner='wojd-localization',profile='runtime',release_id='INERT-RC-FIXTURE',source_revision='independent-offline-test',vendor_dbghelp=dict(bytes=pp['bytes'],sha256=pp['sha256']),accepted_legacy_installations=legacy or [],files=files)
    if 'profiles' in o:m.update(profile='legacy' if o['profiles']==['legacy'] else 'runtime',supported_profiles=o['profiles'])
    dump(o['pkg']/'manifest.json',m)
    return m

TARGETS=['bin/dbghelp.dll','data/catalog.bin','data/Archive-Session.ps1','pak/zz_WOJD_LOCALIZATION_P.pak','pak/zz_WOJD_HUD_S2_1_P.pak','bin/wojd_dbghelp_original.dll']
def target(o,name):
    role,rel=name.split('/',1);return o[role]/rel
def managed(o): return {n:pin(target(o,n)) for n in TARGETS+['data/install-state.json']}
def snapshot(o):
    return {p.relative_to(o['game']).as_posix():pin(p) for p in o['game'].rglob('*') if p.is_file() and p.name!='.installer.lock'}
def private(o):
    sent={
        'cache/runtime-addresses.bin':b'PRIVATE-CACHE-DO-NOT-ALTER',
        'settings/client.json':b'{"private":"settings sentinel"}',
        'logs/native.log':b'PRIVATE-LOG-SENTINEL-NOT-REAL-ACCOUNT-DATA',
    }
    for n,b in sent.items():write(o['data']/n,b)
    return {n:pin(o['data']/n) for n in sent}
def assert_private(o,s):
    assert {n:pin(o['data']/n) for n in s}==s
def state(o): return json.loads((o['data']/'install-state.json').read_bytes())
def run(o,action,code=0,tx=None,shim=None,profile=None):
    cmd=[POWERSHELL,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass']
    args=['-Action',action,'-GameRoot',str(o['game']),'-PackageRoot',str(o['pkg'])]
    if tx:args+=['-TransactionId',tx]
    if profile:args+=['-Profile',profile]
    if shim:
        sp=o['case']/('shim-'+str(len(CALLS))+'.ps1')
        shim_text=shim+"\n& '"+str(o['pkg']/'Installer.ps1').replace("'","''")+"' @args\nexit $LASTEXITCODE\n"
        # WinPS5 needs BOM for Unicode literal paths in this test-only shim.
        write(sp,shim_text.encode('utf-8-sig'))
        cmd+=['-File',str(sp)]+args
    else:cmd+=['-File',str(o['pkg']/'Installer.ps1')]+args
    started=time.monotonic()
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=35)
    event=dict(case=o['case'].name,action=action,expected_exit=code,actual_exit=p.returncode,seconds=round(time.monotonic()-started,3),instrumented=pin(o['pkg']/'Installer.ps1')['sha256']!=SOURCE_SHA,process_or_race_shim=bool(shim),stdout=p.stdout.decode('utf-8',errors='replace'),stderr=p.stderr.decode('utf-8',errors='replace'))
    CALLS.append(event)
    assert p.returncode==code,event
    return event
def rejection(o,action='Install',tx=None,shim=None):
    before=snapshot(o);run(o,action,code=1,tx=tx,shim=shim);assert snapshot(o)==before,'Rejected operation modified game-tree file bytes'
def case(name,fn):
    try: evidence=fn();RESULTS.append(dict(name=name,status='PASS',evidence=evidence))
    except Exception as e:
        RESULTS.append(dict(name=name,status='FAIL',error=str(e),traceback=traceback.format_exc()))
        persist()
        raise
    persist()
def persist():
    dump(OUT/'fixture-results.json',dict(source_sha256=SOURCE_SHA,synthetic_root=str(CASES),results=RESULTS,calls=CALLS,actual_game_tree_writes=False,synthetic_PE_fixtures_loaded_or_executed=False))

def fresh_lifecycle():
    o=make('01-fresh-full-lifecycle');run(o,'Install');first=state(o)['transaction_id'];s=private(o);installed=managed(o)
    run(o,'Verify');run(o,'Uninstall');second=json.loads(next(p for p in (o['data']/'transactions').glob('*/journal.json') if json.loads(p.read_bytes())['action']=='Uninstall').read_bytes())['id']
    assert all(not x['exists'] for x in managed(o).values());assert_private(o,s)
    run(o,'Rollback',tx=second);assert managed(o)==installed;assert_private(o,s)
    run(o,'Rollback',tx=first);assert all(not x['exists'] for x in managed(o).values());assert_private(o,s)
    assert (o['data']/'ownership.json').exists()
    return dict(install_transaction=first,uninstall_transaction=second,private_sentinels_preserved=True)

def stock_lifecycle():
    o=make('02-stock-dll-restore',stock=True);stock=pin(o['bin']/'dbghelp.dll')
    run(o,'Install');assert state(o)['original_bin_dll_existed'];s=private(o);run(o,'Uninstall')
    assert pin(o['bin']/'dbghelp.dll')==stock;assert_private(o,s)
    return dict(stock_exact_restored=True)

def legacy(o,mutate=None):
    owner=dict(format_version=1,owner='wojd-localization',game_exe=str(o['exe']))
    dump(o['data']/'ownership.json',owner)
    oldbytes={
        'bin/dbghelp.dll':pe(True,b'INERT-LEGACY-C8'),
        'data/catalog.bin':b'old-C8-catalog',
        'data/Archive-Session.ps1':b'old-archive-helper',
        'pak/zz_WOJD_LOCALIZATION_P.pak':b'old-S1-base',
        'pak/zz_WOJD_HUD_S2_1_P.pak':b'old-S2-HUD',
        'bin/wojd_dbghelp_original.dll':o['vendor'].read_bytes(),
    }
    for n,b in oldbytes.items():write(target(o,n),b)
    accepted=[dict(id='C8_S1_S2_INERT_EXACT',files=[dict(target=n,**pin(target(o,n))) for n in TARGETS])]
    manifest(o,accepted)
    st=dict(format_version=1,game_exe=str(o['exe']),original_bin_dll_existed=False,files=[dict(path=str(target(o,n)),sha256='0'*64) for n in TARGETS if n!='pak/zz_WOJD_HUD_S2_1_P.pak'])
    dump(o['data']/'install-state.json',st)
    if mutate:mutate(o,st,owner)
    return accepted

def legacy_ok():
    o=make('03-exact-legacy-stale-recorded-hashes');legacy(o);s=private(o);run(o,'Install');run(o,'Verify');assert_private(o,s)
    assert state(o)['migration_from']=='LEGACY_EXACT_C8_S1_S2_INERT_EXACT'
    return dict(full_six_file_tuple_required=True,stale_V1_recorded_hashes_allowed_only_after_exact_actual_match=True)

def legacy_reject(name,mutator):
    o=make(name);legacy(o,mutator);rejection(o);return dict(no_game_file_writes=True)

def v2_upgrade():
    o=make('09-v2-upgrade-reinstall-rollback');run(o,'Install');s=private(o)
    write(o['pkg']/'payload/catalog.bin',b'upgraded-catalog');write(o['pkg']/'payload/zz_WOJD_LOCALIZATION_P.pak',b'upgraded-main-pak');manifest(o)
    before=managed(o);run(o,'Install');upgraded=managed(o);assert before!=upgraded;assert state(o)['migration_from']=='MANAGED_V2'
    run(o,'Install');tx=state(o)['transaction_id'];run(o,'Rollback',tx=tx);assert managed(o)==upgraded;assert_private(o,s)
    return dict(upgrade_and_idempotent_reinstall_pass=True)

def fresh_conflict(name,role,rel,b):
    o=make(name);write(o[role]/rel,b);rejection(o);return dict(no_game_file_writes=True)

def managed_conflict(name,changed):
    o=make(name);run(o,'Install');write(target(o,changed),b'UNKNOWN-BYTES-PRESERVE');rejection(o);return dict(changed_target_preserved=changed)

def bad_manifest(name,mutation):
    o=make(name);p=o['pkg']/'manifest.json';m=json.loads(p.read_bytes());mutation(o,m);dump(p,m);rejection(o);return dict(no_game_file_writes=True)

def junction(name,package=False):
    o=make(name)
    if package:
        link=o['pkg']/'payload'/'linked';dest=o['case']/'outside-package';write(dest/'sentinel',b'outside')
    else:
        link=o['bin']/'wojd';dest=o['case']/'outside-game-data';write(dest/'sentinel',b'outside')
    command="New-Item -ItemType Junction -Path '"+str(link).replace("'","''")+"' -Target '"+str(dest).replace("'","''")+"' | Out-Null"
    proc=subprocess.run([POWERSHELL,'-NoProfile','-NonInteractive','-Command',command],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
    assert proc.returncode==0,proc.stderr
    outside=pin(dest/'sentinel');rejection(o);assert pin(dest/'sentinel')==outside
    return dict(junction_rejected=True,outside_preserved=True)

def unknown_other_mod():
    o=make('24-unrelated-other-mod-preserved');write(o['pak']/'Another-User-Mod_P.pak',b'OTHER-MOD');before=pin(o['pak']/'Another-User-Mod_P.pak');run(o,'Install');run(o,'Uninstall');assert pin(o['pak']/'Another-User-Mod_P.pak')==before
    return dict(unrelated_mod_preserved=True)

def exe_no_version_gate():
    o=make('25-valid-exe-content-size-time-change');write(o['exe'],pe(False,b'CHANGED-FIXTURE-EXE'+b'X'*1031));run(o,'Install');return dict(exe_length=pin(o['exe'])['bytes'],valid_shape_without_content_pin=True)

def invalid_exe():
    o=make('26-invalid-exe-architecture');b=bytearray(o['exe'].read_bytes());struct.pack_into('<H',b,68,0x14c);write(o['exe'],b);rejection(o);return dict(x86_shape_rejected=True)

def guard_start():
    o=make('27-fake-running-process-at-start');rejection(o,shim="function global:Get-Process { [pscustomobject]@{ProcessName='ZhuxianClient-Win64-Shipping'} }")
    assert 'Game dang chay' in CALLS[-1]['stderr']
    return dict(process_enumeration_dependency_explicitly_mocked=True)

def pending_blocks():
    o=make('28-pending-prepared-blocks-all');run(o,'Install');st=state(o);j=o['data']/'transactions'/st['transaction_id']/'journal.json';obj=json.loads(j.read_bytes());obj['status']='PREPARED';dump(j,obj)
    for action in ['Install','Verify','Uninstall']:rejection(o,action)
    return dict(three_operations_rejected_without_writes=True)

def bad_journal(name,mutator):
    o=make(name);run(o,'Install');st=state(o);p=o['data']/'transactions'/st['transaction_id']/'journal.json';obj=json.loads(p.read_bytes());mutator(obj);dump(p,obj);rejection(o,'Rollback',tx=st['transaction_id']);return dict(no_game_file_writes=True)

def concurrent_lock():
    o=make('31-exclusive-lock-conflict');run(o,'Install')
    lock=o['data']/'.installer.lock'
    cmd="$s=[IO.File]::Open('"+str(lock).replace("'","''")+"',[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None);[Console]::WriteLine('LOCKED');[Console]::Out.Flush();[Console]::ReadLine()|Out-Null;$s.Dispose()"
    child=subprocess.Popen([POWERSHELL,'-NoProfile','-NonInteractive','-Command',cmd],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        assert child.stdout.readline().strip()==b'LOCKED';rejection(o)
    finally:
        child.communicate(b'\n',timeout=10)
    return dict(real_FileShare_None_contention_rejected=True)

def running_before_publish():
    o=make('32-fake-new-process-before-second-publish')
    shim="""$global:enumerations=0
function global:Get-Process {
    $global:enumerations++
    if($global:enumerations -ge 5){[pscustomobject]@{ProcessName='ZhuxianClient-Win64-Shipping'}}
}"""
    event=run(o,'Install',code=1,shim=shim);assert 'Game dang chay' in event['stderr']
    journals=list((o['data']/'transactions').glob('*/journal.json'));assert len(journals)==1
    j=json.loads(journals[0].read_bytes());assert j['status'] in ['PREPARED','ROLLING_BACK']
    assert (o['bin']/'dbghelp.dll').exists()
    run(o,'Rollback',tx=j['id']);assert all(not x['exists'] for x in managed(o).values())
    return dict(new_process_blocks_publish_and_auto_rollback=True,explicit_closed_rollback_recovers=True)

def race_after_preflight():
    o=make('33-unknown-target-change-after-preflight');run(o,'Install');before=managed(o)
    catalog=str(o['data']/'catalog.bin').replace("'","''")
    shim="""$global:enumerations=0
function global:Get-Process {
    $global:enumerations++
    if($global:enumerations -eq 3){[IO.File]::WriteAllText('"""+catalog+"""','UNRECOGNIZED-RACE-CHANGE')}
}"""
    run(o,'Install',code=1,shim=shim)
    assert (o['data']/'catalog.bin').read_bytes()==b'UNRECOGNIZED-RACE-CHANGE'
    for n,p in before.items():
        if n not in ['data/catalog.bin','data/install-state.json']:assert managed(o)[n]==p
    journals=[json.loads(p.read_bytes()) for p in (o['data']/'transactions').glob('*/journal.json')]
    assert any(j['status'] in ['PREPARED','ROLLING_BACK'] for j in journals)
    return dict(unknown_changed_bytes_preserved=True,recoverable_journal_kept=True,state_may_have_been_published_before_final_all_target_readback=True)

def no_state_owned_data(name,rel):
    o=make(name)
    dump(o['data']/'ownership.json',dict(format_version=2,owner='wojd-localization',game_exe=str(o['exe'])))
    write(o['data']/rel,b'UNKNOWN-OWNED-PATH-WITHOUT-INSTALL-STATE')
    rejection(o)
    return dict(owned_marker_does_not_authorize_unknown_managed_data_without_state=True,target=rel)

def race_between_validation_and_snapshot():
    instrument="""$script:ValidationMutationInjected=$false
Set-Item -Path Function:FixtureOriginalReadInstallation -Value ${function:Read-Installation}
function Read-Installation {
    $installation=FixtureOriginalReadInstallation
    if($installation.kind -eq 'MANAGED_V2' -and -not $script:ValidationMutationInjected){
        $script:ValidationMutationInjected=$true
        [IO.File]::WriteAllText((Target 'data/catalog.bin'),'UNKNOWN-CHANGE-AFTER-VALIDATION')
    }
    return $installation
}
"""
    o=make('36-race-between-validation-and-snapshot',instrument=instrument)
    run(o,'Install');before=managed(o)
    run(o,'Install',code=1)
    assert (o['data']/'catalog.bin').read_bytes()==b'UNKNOWN-CHANGE-AFTER-VALIDATION'
    for n,p in before.items():
        if n!='data/catalog.bin':assert managed(o)[n]==p
    return dict(unknown_change_not_adopted_as_authorized_preimage=True,explicit_test_only_post_validation_mutation=True)

def fault_instrument(kind,n):
    # Exact source bodies remain unchanged. A test-only dependency wrapper is
    # inserted after definitions and before the original production entrypoint.
    if kind=='commit':
        return """$script:InjectedOnce=$false
Set-Item -Path Function:FixtureOriginalWriteJournal -Value ${function:Write-Journal}
function Write-Journal($Journal,[string]$Directory){
    if($Journal.status -eq 'COMMITTED' -and -not $script:InjectedOnce){$script:InjectedOnce=$true;throw 'INJECTED_BEFORE_COMMIT'}
    FixtureOriginalWriteJournal $Journal $Directory
}
"""
    name='Publish' if kind=='publish' else 'Remove-Owned'
    params=('$Source,$Destination,$Before,$After,$Token' if kind=='publish' else '$Path,$Before,$Directory,$Ordinal')
    forwarded=('$Source $Destination $Before $After $Token' if kind=='publish' else '$Path $Before $Directory $Ordinal')
    return ('$script:InjectedOnce=$false\n$script:MutationCounter=0\nSet-Item -Path Function:FixtureOriginalMutation -Value ${function:'+name+'}\nfunction '+name+'('+params+'){\n    FixtureOriginalMutation '+forwarded+'\n    $script:MutationCounter++\n    if($script:MutationCounter -eq '+str(n)+" -and -not $script:InjectedOnce){$script:InjectedOnce=$true;throw 'INJECTED_AFTER_MUTATION'}\n}\n")

def faults(kind,n):
    o=make('fault-'+kind+'-'+str(n),instrument=fault_instrument(kind,n))
    if kind=='remove':
        # Disable the remove-only wrapper for install by its natural call site:
        # install never calls Remove-Owned in the successful path.
        run(o,'Install');before=managed(o);s=private(o);event=run(o,'Uninstall',code=1);assert managed(o)==before;assert_private(o,s)
    else:
        event=run(o,'Install',code=1);assert all(not x['exists'] for x in managed(o).values())
    assert 'INJECTED_' in event['stderr']
    js=[json.loads(p.read_bytes()) for p in (o['data']/'transactions').glob('*/journal.json')]
    assert any(j['status']=='ROLLED_BACK' for j in js)
    return dict(explicit_test_copy_instrumentation=True,fault=kind,ordinal=n,automatic_rollback_restored_all_managed_preimages=True)

def profiles(o,only=False):
    o['profiles']=['legacy'] if only else ['runtime','legacy']
    write(o['pkg']/'payload/legacy/zz_WOJD_LOCALIZATION_P.pak',b'legacy-font-locres-layout-fixture')
    write(o['pkg']/'Collect-LegacyLog.ps1',(AUTHOR/'Collect-LegacyLog.ps1').read_bytes())
    if only:
        for name in ('payload/dbghelp.dll','payload/catalog.bin','payload/zz_WOJD_LOCALIZATION_P.pak','Archive-Session.ps1','MinHook-LICENSE.txt'):
            (o['pkg']/name).unlink()
    manifest(o)

def legacy_fresh(stock=False,vendor=True):
    o=make('legacy-fresh-'+str(stock)+'-'+str(vendor),stock=stock);profiles(o,only=True)
    if not vendor:o['vendor'].unlink()
    original=pin(o['bin']/'dbghelp.dll');run(o,'Install');first=state(o)['transaction_id'];s=private(o)
    assert state(o)['profile']=='legacy' and pin(o['bin']/'dbghelp.dll')==original
    for name in ('bin/wojd_dbghelp_original.dll','data/catalog.bin','data/Archive-Session.ps1'):assert not target(o,name).exists()
    assert not any(p.suffix.lower()=='.dll' for p in o['pkg'].rglob('*'))
    before=managed(o);run(o,'Verify');run(o,'Uninstall');assert pin(o['bin']/'dbghelp.dll')==original;assert_private(o,s)
    run(o,'Rollback',tx=first);assert pin(o['bin']/'dbghelp.dll')==original;assert_private(o,s)
    return dict(dll_bytes_unchanged=True,no_native_payload=True,vendor_required=False)

def profile_switch(stock=False):
    o=make('profile-switch-'+str(stock),stock=stock);profiles(o);run(o,'Install');s=private(o);runtime=managed(o)
    run(o,'Install',profile='legacy');legacy_tx=state(o)['transaction_id'];legacy_snapshot=managed(o)
    assert state(o)['profile']=='legacy';run(o,'Verify');assert_private(o,s)
    assert pin(o['bin']/'dbghelp.dll')['exists']==stock
    if stock:assert pin(o['bin']/'dbghelp.dll')==pin(o['vendor'])
    assert not (o['bin']/'wojd_dbghelp_original.dll').exists()
    run(o,'Install',profile='runtime');new_tx=state(o)['transaction_id'];run(o,'Verify')
    run(o,'Rollback',tx=new_tx);assert managed(o)==legacy_snapshot;run(o,'Verify')
    run(o,'Rollback',tx=legacy_tx);assert managed(o)==runtime;run(o,'Verify');assert_private(o,s)
    return dict(two_way_switch_and_rollback=True,private_sentinels_preserved=True)

def legacy_tamper(kind):
    o=make('legacy-tamper-'+kind);profiles(o,only=True)
    if kind=='native-package':
        write(o['pkg']/'unexpected.dll',pe(True,b'UNEXPECTED'));manifest(o);rejection(o)
    else:
        run(o,'Install')
        if kind=='native-game':write(o['bin']/'dbghelp.dll',pe(True,b'UNKNOWN'))
        elif kind=='missing-pak':(o['pak']/'zz_WOJD_LOCALIZATION_P.pak').unlink()
        elif kind=='forged-state':
            doc=state(o)
            for row in doc['files']:
                if row['target'].startswith('pak/'):row.update(exists=False,bytes=0,sha256=None)
            dump(o['data']/'install-state.json',doc)
        rejection(o,'Verify')
    return dict(legacy_conflict_preserved=kind)

def unsupported_profile():
    o=make('unsupported-profile');before=snapshot(o);run(o,'Install',profile='legacy',code=1);assert snapshot(o)==before
    return dict(unavailable_profile_rejected=True)

def switch_fault():
    o=make('profile-switch-remove-fault',instrument=fault_instrument('remove',2));profiles(o)
    run(o,'Install');before=managed(o);s=private(o);run(o,'Install',profile='legacy',code=1)
    assert managed(o)==before;assert state(o)['profile']=='runtime';assert_private(o,s);run(o,'Verify')
    return dict(partially_removed_runtime_restored=True)

def legacy_log():
    o=make('legacy-log-collection');profiles(o,only=True);run(o,'Install')
    log=o['case']/'fixture-game.log';write(log,'[2026.10.25-00.00.00:000]LogTextLocalizationManager: (Namespace:N, Key:k, Source:甲), but it did not exist.\n')
    cmd=[POWERSHELL,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(o['pkg']/'Collect-LegacyLog.ps1'),'-GameRoot',str(o['game']),'-LogPath',str(log)]
    result=subprocess.run(cmd,capture_output=True,timeout=20);assert result.returncode==0,(result.stdout,result.stderr)
    reports=list((o['data']/'logs').glob('legacy-*/collection.json'));assert len(reports)==1
    doc=json.loads(reports[0].read_bytes());assert doc['status']=='PASS' and doc['sha256']==pin(log)['sha256']
    assert reports[0].with_name('ZhuxianClient.log').read_bytes()==log.read_bytes()
    import os
    os.utime(log,(0,0));result=subprocess.run(cmd,capture_output=True,timeout=20);assert result.returncode==1
    assert len(list((o['data']/'logs').glob('legacy-*/collection.json')))==1
    return dict(fresh_log_archived_exactly=True,stale_log_rejected=True)

def main():
    assert sha((AUTHOR/'Installer.ps1').read_bytes())==SOURCE_SHA
    assert not CASES.exists(),'Fresh fixture run only'
    CASES.mkdir(parents=True)
    case('fresh install/verify/uninstall/rollback uninstall/rollback install + private sentinels',fresh_lifecycle)
    case('stock bin DLL exact restore',stock_lifecycle)
    case('legacy exact six-target migration with stale V1 state hashes',legacy_ok)
    case('legacy one changed byte rejects',lambda:legacy_reject('04-legacy-one-byte',lambda o,s,w:write(o['data']/'catalog.bin',b'wrong-one-byte')))
    case('legacy extra state path rejects',lambda:legacy_reject('05-legacy-extra-path',lambda o,s,w:(s['files'].append(dict(path=str(o['data']/'private.bin'),sha256='0'*64)),dump(o['data']/'install-state.json',s))))
    case('legacy duplicate state target rejects',lambda:legacy_reject('06-legacy-duplicate',lambda o,s,w:(s['files'].append(s['files'][0]),dump(o['data']/'install-state.json',s))))
    case('legacy invalid owner rejects',lambda:legacy_reject('07-legacy-bad-owner',lambda o,s,w:(w.update(owner='another-mod'),dump(o['data']/'ownership.json',w))))
    case('legacy wrong selected EXE path rejects',lambda:legacy_reject('08-legacy-wrong-exe',lambda o,s,w:(s.update(game_exe=str(o['bin']/'Other.exe')),dump(o['data']/'install-state.json',s))))
    case('V2 upgrade + reinstall + rollback + private sentinels',v2_upgrade)
    case('unknown dbghelp proxy rejects',lambda:fresh_conflict('10-unknown-proxy','bin','dbghelp.dll',b'UNKNOWN-PROXY'))
    case('unknown base PAK rejects',lambda:fresh_conflict('11-unknown-base-pak','pak','zz_WOJD_LOCALIZATION_P.pak',b'UNKNOWN-BASE'))
    case('unknown HUD PAK rejects',lambda:fresh_conflict('12-unknown-hud-pak','pak','zz_WOJD_HUD_S2_1_P.pak',b'UNKNOWN-HUD'))
    case('changed managed mirror rejects',lambda:managed_conflict('13-changed-mirror','bin/wojd_dbghelp_original.dll'))
    case('changed managed catalog rejects',lambda:managed_conflict('14-changed-catalog','data/catalog.bin'))
    case('manifest traversal rejects',lambda:bad_manifest('15-manifest-traversal',lambda o,m:m['files'].append(dict(path='../outside',bytes=0,sha256='0'*64))))
    case('manifest rooted path rejects',lambda:bad_manifest('16-manifest-rooted',lambda o,m:m['files'].append(dict(path=str(o['vendor']),bytes=0,sha256='0'*64))))
    case('manifest case-duplicate rejects',lambda:bad_manifest('17-manifest-case-duplicate',lambda o,m:m['files'].append(dict(m['files'][0],path=m['files'][0]['path'].upper()))))
    case('package unlisted file rejects',lambda:bad_manifest('18-package-unlisted',lambda o,m:write(o['pkg']/'unexpected.bin',b'unlisted')))
    case('package payload tamper rejects',lambda:bad_manifest('19-package-tamper',lambda o,m:write(o['pkg']/'payload/catalog.bin',b'tampered')))
    case('invalid hash tuple rejects',lambda:bad_manifest('20-manifest-invalid-hash',lambda o,m:m['files'][0].update(sha256='A'*64)))
    case('target junction rejects',lambda:junction('21-target-junction'))
    case('package junction rejects',lambda:junction('22-package-junction',package=True))
    case('retired named translation PAK rejects',lambda:fresh_conflict('23-retired-pak','pak','~VI_PATCH.pak',b'OLD-TRANSLATION'))
    case('unrelated mod PAK preserved',unknown_other_mod)
    case('valid changed EXE accepted without hash/size/time gate',exe_no_version_gate)
    case('invalid x86 EXE rejected',invalid_exe)
    case('fake running-client guard at start',guard_start)
    case('PREPARED journal blocks Install/Verify/Uninstall',pending_blocks)
    case('unknown journal target rejects',lambda:bad_journal('29-journal-unknown-target',lambda j:j['files'][0].update(target='bin/Other.dll')))
    case('escaped journal backup rejects',lambda:bad_journal('30-journal-escaped-backup',lambda j:j['files'][-1].update(backup='../escaped.bin')))
    case('real concurrent FileShare.None lock rejects',concurrent_lock)
    case('new fake process before publish + preserved recoverable journal',running_before_publish)
    case('unknown target change after preflight preserved',race_after_preflight)
    case('owned no-state unknown catalog rejects',lambda:no_state_owned_data('34-owned-no-state-catalog','catalog.bin'))
    case('owned no-state unknown helper rejects',lambda:no_state_owned_data('35-owned-no-state-helper','Archive-Session.ps1'))
    case('change between validation and preimage snapshot rejects',race_between_validation_and_snapshot)
    for n in range(1,8):case('fault after fresh Publish '+str(n),lambda n=n:faults('publish',n))
    for n in range(1,8):case('fault after uninstall Remove-Owned '+str(n),lambda n=n:faults('remove',n))
    case('fault immediately before commit',lambda:faults('commit',1))
    case('Legacy fresh no vendor DLL dependency',lambda:legacy_fresh(vendor=False))
    case('Legacy stock DLL untouched',lambda:legacy_fresh(stock=True))
    case('runtime Legacy two-way switch rollback private files',profile_switch)
    case('runtime Legacy stock DLL restore switch rollback',lambda:profile_switch(stock=True))
    for kind in ('native-package','native-game','missing-pak','forged-state'):case('Legacy tamper '+kind,lambda kind=kind:legacy_tamper(kind))
    case('unsupported selected profile rejects without writes',unsupported_profile)
    case('runtime Legacy partial removal failure restores runtime',switch_fault)
    case('Legacy fresh log exact archive and stale rejection',legacy_log)
    print(json.dumps(dict(tests=len(RESULTS),calls=len(CALLS),failures=sum(x['status']!='PASS' for x in RESULTS)),ensure_ascii=False))

if __name__=='__main__':main()
