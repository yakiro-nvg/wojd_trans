"""Build the production player ZIP from public, pinned inputs."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile,zipfile
from catalog_core import digest,render_fmt,write_json
from compile_locres_bindings import build_routes
ROOT=pathlib.Path(__file__).resolve().parents[1]

def residual_bindings(entries,native_outputs):
    """Validate a future residual import; source overlap alone is not an exclusion."""
    merged={}
    for row in entries:
        if row['source'] in native_outputs:raise ValueError('Residual contains an already substituted native output')
        identity=row['namespace'],row['key']
        if identity in merged and merged[identity]!=row:raise ValueError('Conflicting residual source variants require explicit runtime binding resolution')
        merged[identity]=row
    return merged

def file_index(root):
    return {p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(root.rglob('*')) if p.is_file()}

def pack_verified(repak,source,destination):
    subprocess.run([str(repak),'pack','--version','V8B',str(source),str(destination)],check=True)
    expected=file_index(source)
    listing=subprocess.run([str(repak),'list',str(destination)],check=True,capture_output=True,text=True,encoding='utf-8').stdout.splitlines()
    if sorted(listing)!=sorted(expected):raise ValueError('PAK listing differs from intended payload')
    with tempfile.TemporaryDirectory(prefix='unpack-',dir=destination.parent) as directory:
        subprocess.run([str(repak),'unpack','--quiet','--output',directory,str(destination)],check=True)
        if file_index(pathlib.Path(directory))!=expected:raise ValueError('PAK full read-back differs')
    return expected

def zip_verified(source,destination):
    expected=file_index(source)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name in expected:
            entry=zipfile.ZipInfo(name,date_time=(2020,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o644<<16
            archive.writestr(entry,(source/name).read_bytes())
    with zipfile.ZipFile(destination) as archive:
        if len(archive.namelist())!=len(expected) or set(archive.namelist())!=set(expected):raise ValueError('ZIP membership differs')
        for name,pin in expected.items():
            data=archive.read(name)
            if len(data)!=pin['bytes'] or hashlib.sha256(data).hexdigest()!=pin['sha256']:raise ValueError('ZIP read-back differs')

def overlay(source,target):
    if not source.is_dir():raise ValueError(f'Missing source layer: {source}')
    shutil.copytree(source,target,dirs_exist_ok=True)

def main():
    from legacy_locres import overlay_legacy,overlay_font
    parser=argparse.ArgumentParser();parser.add_argument('--language',choices=['vi'],default='vi');parser.add_argument('--repak',required=True,type=pathlib.Path)
    parser.add_argument('--out',type=pathlib.Path,default=ROOT/'artifacts');parser.add_argument('--revision',default=os.environ.get('GITHUB_SHA','local-unpublished'))
    parser.add_argument('--variant',choices=['all','base','legacy'],default='all')
    parser.add_argument('--collect-legacy',action='store_true',help='Local diagnostic Legacy ZIP, omitting both translated locres routes to expose misses')
    args=parser.parse_args();args.repak=args.repak.resolve();args.out.mkdir(parents=True,exist_ok=True)
    if args.collect_legacy and args.variant!='legacy':raise ValueError('Collection is a separate Legacy-only diagnostic build')
    matrix=json.loads((ROOT/'config/packages.json').read_bytes());variants=matrix['variants']
    if matrix['format_version']!=1 or set(variants)!={'base','legacy'}:raise ValueError('Expected full and DLL-free Legacy packages')
    selected={name:rule for name,rule in variants.items() if args.variant in ('all',name)}
    production=None
    if 'base' in selected:
        production=json.loads((ROOT/'native/build/production-check.json').read_bytes())['runtime']
        if production['status']!='PASS' or production['build']!=dict(profile='runtime',capture=0,selftest=0,optimization='O2',static_crt=True):raise ValueError('Full player packages require verified production runtime build')
        if production['sha256']!=digest(ROOT/'native/build/runtime/dbghelp.dll'):raise ValueError('Production DLL changed after verification')
    subprocess.run([sys.executable,str(ROOT/'scripts/wojd.py'),'validate',*[str(ROOT/f'translations/vi.{k}.ndjson') for k in ['native','residual','fmtstring']]],check=True)
    parent=ROOT/'work/package-stage';parent.mkdir(parents=True,exist_ok=True)
    stage=pathlib.Path(tempfile.mkdtemp(prefix='release-',dir=parent));common=stage/'common';common.mkdir()
    if 'base' in selected:subprocess.run([sys.executable,str(ROOT/'scripts/wojd.py'),'compile-runtime',str(ROOT/'translations/vi.native.ndjson'),str(common/'catalog.bin')],check=True)
    base=stage/'base-source';overlay(ROOT/'assets/vi-base',base)
    locres=build_routes(ROOT/'resources/locres',base)
    render_fmt([ROOT/'resources/FormatString'],ROOT/'translations/vi.fmtstring.ndjson',base/'ZhuxianClient/gamedata/client/FormatString',ROOT/'translations/vi.fmtstring.sources.json')
    approved=json.loads((ROOT/'config/base-payload.json').read_bytes())
    if file_index(base)!=approved:raise ValueError('Base payload differs from approved localization/UI source manifest')
    legacy=stage/'legacy-source';overlay(base,legacy)
    legacy_locres=overlay_legacy(legacy,ROOT/'resources/legacy-locres');legacy_font=overlay_font(legacy,ROOT/'assets/vi-base')
    if file_index(legacy)!=json.loads((ROOT/'config/legacy-payload.json').read_bytes()):raise ValueError('Legacy payload differs from approved source manifest')
    if args.collect_legacy:
        for path in legacy_locres:(legacy/path).unlink()
        expected={path:pin for path,pin in json.loads((ROOT/'config/legacy-payload.json').read_bytes()).items() if path not in legacy_locres}
        if file_index(legacy)!=expected:raise ValueError('Diagnostic layer may omit only the two translated locres routes')
    hud=common/'zz_WOJD_HUD_S2_1_P.pak';hud_index=pack_verified(args.repak,ROOT/'assets/vi-hud',hud)
    if len(hud_index)!=4 or any(p.endswith('.locres') for p in hud_index):raise ValueError('Unexpected HUD layer')
    legacy_pak=common/'legacy.pak';legacy_index=pack_verified(args.repak,legacy,legacy_pak)
    compatibility=json.loads((ROOT/'distribution/compatibility.json').read_bytes());profiles={}
    for variant,rule in selected.items():
        expected_profile='runtime' if variant=='base' else 'legacy'
        expected_archive='VI_PATCH.zip' if variant=='base' else 'VI_LEGACY.zip'
        expected_profiles=['runtime','legacy'] if variant=='base' else ['legacy']
        if set(rule)!={'archive','description','profile','supported_profiles'} or rule['archive']!=expected_archive or rule['profile']!=expected_profile or rule['supported_profiles']!=expected_profiles:raise ValueError('Unexpected player package configuration')
        target=stage/variant;target.mkdir();payload=target/'payload';payload.mkdir()
        names=['Installer.ps1','install.bat','verify.bat','uninstall.bat','rollback.bat','README.txt','Collect-LegacyLog.ps1','collect-legacy-log.bat']
        if variant=='base':names+=['Archive-Session.ps1','ChatSettings.ps1','chat-settings.bat','CHAT_GUIDE.txt']
        for name in names:shutil.copyfile(ROOT/'distribution'/name,target/name)
        shutil.copyfile(hud,payload/hud.name)
        (payload/'legacy').mkdir();shutil.copyfile(legacy_pak,payload/'legacy/zz_WOJD_LOCALIZATION_P.pak')
        pak_index=legacy_index
        if variant=='base':
            pak_index=pack_verified(args.repak,base,payload/'zz_WOJD_LOCALIZATION_P.pak')
            shutil.copyfile(common/'catalog.bin',payload/'catalog.bin')
            shutil.copyfile(ROOT/'native/build/runtime/dbghelp.dll',payload/'dbghelp.dll')
            shutil.copyfile(ROOT/'native/vendor/minhook/LICENSE.txt',target/'MinHook-LICENSE.txt')
        shutil.copyfile(ROOT/'LICENSE',target/'LICENSE');shutil.copyfile(ROOT/'docs/font-credits.txt',target/'Font-CREDITS.txt')
        shutil.copyfile(ROOT/'docs/OFL-League-Spartan.txt',target/'OFL-League-Spartan.txt')
        for credit in ('MIT-HanViet-PhongPhan.txt','Unicode-LICENSE.txt'):shutil.copyfile(ROOT/'docs'/credit,target/credit)
        shutil.copyfile(ROOT/'docs/known-issues.txt',target/'KNOWN_ISSUES.txt')
        (target/'CONFIGURATION.txt').write_text(rule['description']+'\n',encoding='utf-8')
        files=[dict(path=name,**pin) for name,pin in file_index(target).items()]
        if variant=='legacy' and any(row['path'].lower().endswith(('.dll','.exe')) or row['path']=='payload/catalog.bin' for row in files):raise ValueError('DLL-free ZIP contains native code or catalog')
        manifest=dict(format_version=2,owner='wojd-localization',profile=rule['profile'],supported_profiles=rule['supported_profiles'],variant=variant,collection_only=args.collect_legacy,native_build=production['build'] if variant=='base' else None,release_id='WOJD-VI-'+variant+'-'+args.revision[:16],source_revision=args.revision,files=files,**compatibility)
        write_json(target/'manifest.json',manifest)
        archive=args.out/rule['archive'];zip_verified(target,archive)
        profiles[variant]=dict(file=archive.name,bytes=archive.stat().st_size,sha256=digest(archive),pak_files=pak_index,legacy_pak_files=legacy_index,hud_files=hud_index,supported_profiles=rule['supported_profiles'])
    write_json(args.out/'vi-build.json',dict(source_revision=args.revision,locres=locres,legacy_locres=legacy_locres,legacy_font=legacy_font,variants=profiles))
    (args.out/'checksums.txt').write_text(''.join(f"{row['sha256']}  {row['file']}\n" for row in profiles.values()),encoding='ascii')
    print(json.dumps({k:{n:v for n,v in row.items() if n not in ['pak_files','legacy_pak_files','hud_files']} for k,row in profiles.items()},indent=2))

if __name__=='__main__':main()
