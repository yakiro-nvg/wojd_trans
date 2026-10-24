"""Collect DLL-free UE localization misses and reuse existing translations.

Native catalogs are translation dictionaries only: they never filter misses or
provide namespace/key identities. No provider, DLL or original .data is used.
"""
import argparse,collections,hashlib,json,pathlib,tempfile
from binascii import crc32
from catalog_core import CJK,RESOURCE,ReuseIndex,digest,read_ndjson,source_id,write_json,write_ndjson
from compile_locres_bindings import compile_bindings,load_bindings
from locres_verify import read_bytes
from ue_log import iter_misses
ROOT=pathlib.Path(__file__).resolve().parents[1]

def collect(logs,index):
    stats=collections.Counter();observed={};variants=collections.defaultdict(set)
    for path in logs:
        for row in iter_misses(path,stats):
            source=row['source']
            if not source or not CJK.search(source) or RESOURCE.search(source):continue
            identity=row['namespace'],row['key']
            if not row['key']:continue
            variants[identity].add(source)
            observed.setdefault((*identity,source),dict(row,log_file=pathlib.Path(path).name))
    rows=[];conflicts=[];cache={}
    for (ns,key,source),row in sorted(observed.items()):
        if len(variants[ns,key])>1:
            conflicts.append(dict(row,reason='conflicting_sources_for_identity'));continue
        if source not in cache:cache[source]=index.choose(source)
        target,reuse=cache[source]
        rows.append(dict(namespace=ns,key=key,source=source,source_sha256=source_id(source),
            source_crc=crc32(source.encode('utf-32-le')) & 0xffffffff,
            translated=target,translation_source_sha256=source_id(source) if target else None,
            translation_sha256=source_id(target) if target else None,status='translated' if target else 'missing',
            quality='unreviewed',origin='UE_LOCALIZATION_LOG',reuse=reuse,
            log_file=row['log_file'],log_line=row['log_line'],diagnostic_kind=row['diagnostic_kind']))
    return rows,conflicts,dict(entries=len(rows),translated=sum(bool(r['translated']) for r in rows),
        pending=sum(not r['translated'] for r in rows),conflicts=len(conflicts),counts=dict(stats),
        native_source_filter=False,inferred_locres_ids=0,provider_requests=0,
        limitation='Only observed misses; valid stock passthrough and text bypassing UE localization are not covered. Reuse does not certify translation meaning or universal UI fit.')

def publish(rows,destination,refresh_namespaces=()):
    """Persist compact, reproducible overrides; callers must resolve conflicts."""
    bindings=[]
    for row in rows:
        if row['status']!='translated':continue
        if row['source_sha256']!=source_id(row['source']) or row['translation_source_sha256']!=source_id(row['source']) or row['translation_sha256']!=source_id(row['translated']):raise ValueError('Legacy source/target hash changed')
        crc=crc32(row['source'].encode('utf-32-le')) & 0xffffffff
        if row['source_crc']!=crc:raise ValueError('Legacy source CRC changed')
        bindings.append(dict(namespace=row['namespace'],key=row['key'],source_crc=crc,target=row['translated']))
    destination=pathlib.Path(destination);destination.mkdir(parents=True,exist_ok=True)
    path=destination/'overrides.ndjson';write_ndjson(path,bindings)
    # Strict duplicate/CRC/type validation before any cook.
    load_bindings(path)
    write_json(destination/'manifest.json',dict(format_version=1,input=path.name,entries=len(bindings),sha256=digest(path),crc_refresh_namespaces=sorted(set(refresh_namespaces)),
        policy='Exact namespace/key/source from DLL-free UE logs. Existing translations only; no .data-source exclusion or inferred IDs. Conflicting source variants are quarantined.'))

def merge_legacy(mapping,overrides,refresh_namespaces=()):
    """Keep matching approved bindings; refresh only reviewed source changes."""
    result=dict(mapping);counts=collections.Counter()
    for identity,value in overrides.items():
        old=mapping.get(identity)
        if old is not None and old[0]==value[0]:
            counts['retained_existing']+=1
            if old[1]!=value[1]:counts['retained_existing_target_choice']+=1
            continue
        if old is not None:
            if identity[0] not in refresh_namespaces:raise ValueError('Legacy source CRC conflicts with a protected baseline binding')
            counts['refreshed_source_crc']+=1
        else:counts['added']+=1
        result[identity]=value
    return result,dict(counts)

def overlay_legacy(stage,source):
    source=pathlib.Path(source);manifest=json.loads((source/'manifest.json').read_bytes())
    if manifest['format_version']!=1 or manifest['input']!='overrides.ndjson':raise ValueError('Invalid legacy override manifest')
    path=source/manifest['input']
    if digest(path)!=manifest['sha256']:raise ValueError('Legacy override pin changed')
    overrides=load_bindings(path)
    if len(overrides)!=manifest['entries']:raise ValueError('Legacy override count changed')
    result={}
    for route in ('ZhuxianClient/Content/Localization/Game/zh-Hans/Game.locres',
                  'ZhuxianClient/gamedata/client/ZCTranslateData/Game/zh-Hans/Game.locres'):
        target=pathlib.Path(stage)/route;original=target.read_bytes()
        counts={}
        if overrides:
            mapping,counts=merge_legacy(read_bytes(original),overrides,manifest.get('crc_refresh_namespaces',[]))
            target.write_bytes(compile_bindings(mapping))
        result[route]=dict(overrides=len(overrides),changes=counts,bytes=target.stat().st_size,sha256=digest(target))
    return result

def overlay_font(stage,base_source):
    """Use the already built main-outline conversion font in every UI face."""
    folder=pathlib.Path('ZhuxianClient/Content/UI/UI_Texture/UI_ziti')
    root=pathlib.Path(stage)/folder;source=pathlib.Path(base_source)/folder
    plain=(source/'FZShengSKSJW_Zhong.ufont').read_bytes();font=(source/'WOJD_HV_PlayerName.ufont').read_bytes()
    changed=[]
    for path in sorted(root.glob('*.ufont')):
        if path.read_bytes()==plain:path.write_bytes(font);changed.append((folder/path.name).as_posix())
    if not changed:raise ValueError('No main UI font faces found for Legacy')
    return dict(files=changed,font_sha256=hashlib.sha256(font).hexdigest(),main_outlines_only=True)

def collection_proof(log):
    """Authenticate a closed Legacy session archive; raw logs are not proof."""
    path=pathlib.Path(log).with_name('collection.json')
    if not path.exists():return None
    value=json.loads(path.read_bytes())
    if value.get('status')!='PASS' or value.get('profile')!='legacy' or value.get('dll_injection') is not False or value.get('sha256')!=digest(log) or value.get('bytes')!=pathlib.Path(log).stat().st_size:
        raise ValueError('Legacy collection proof does not match the log')
    return dict(file=path.name,sha256=digest(path),install_transaction=value['install_transaction'],source_revision=value['source_revision'])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--logs',nargs='+',type=pathlib.Path,required=True)
    p.add_argument('--catalogs',nargs='+',type=pathlib.Path,default=[ROOT/f'translations/vi.{kind}.ndjson' for kind in ('native','residual','fmtstring')])
    p.add_argument('--out',type=pathlib.Path,required=True)
    p.add_argument('--publish',type=pathlib.Path,help='Publish compact overrides after reviewing this collection; keeps diagnostics in --out')
    p.add_argument('--refresh-namespace',action='append',default=[],help='Explicitly reviewed namespace whose existing source CRC may be refreshed from the fresh capture')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    proofs=[collection_proof(log) for log in args.logs]
    if args.publish and not all(proofs):raise ValueError('Publishing Legacy bindings requires a verified DLL-free collection for every log')
    with tempfile.TemporaryDirectory(prefix='reuse-',dir=args.out) as temp:
        index=ReuseIndex(pathlib.Path(temp)/'reuse.sqlite');index.build(args.catalogs)
        try:rows,conflicts,report=collect(args.logs,index)
        finally:index.db.close()
    write_ndjson(args.out/'catalog.ndjson',rows);write_ndjson(args.out/'conflicts.ndjson',conflicts)
    report['logs']=[dict(name=path.name,bytes=path.stat().st_size,sha256=digest(path)) for path in args.logs]
    report['dll_free_collection_verified']=all(proofs);report['collection_proofs']=proofs
    report['catalogs']=[dict(name=path.name,sha256=digest(path)) for path in args.catalogs]
    write_json(args.out/'report.json',report)
    if args.publish:publish(rows,args.publish,args.refresh_namespace)
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
