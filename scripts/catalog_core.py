"""Offline source-exact translation reuse. No provider credentials or network calls."""
from __future__ import annotations
import collections,hashlib,itertools,json,pathlib,re,sqlite3
from translation_quality import validate

CJK=re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')
RESOURCE=re.compile(r'^(?:/Game/|/Script/|Texture2D\x27|Material\x27)|\.(?:xlsx?|lua|data|gdv|uasset|umap|png|dds|tga)$|^(?:@[pP]\([^\r\n)]*\))+$',re.I)

def digest(path):
    value=hashlib.sha256()
    with pathlib.Path(path).open('rb') as src:
        while block:=src.read(1024*1024):value.update(block)
    return value.hexdigest()

def source_id(source):return hashlib.sha256(source.encode('utf-8')).hexdigest()

def read_ndjson(path):
    with pathlib.Path(path).open(encoding='utf-8-sig') as src:
        for number,line in enumerate(src,1):
            if not line.strip():continue
            if line.startswith('version https://git-lfs'):raise ValueError(f'{path}: fetch Git LFS objects first')
            try:row=json.loads(line)
            except ValueError as error:raise ValueError(f'{path}:{number}: {error}') from error
            if not isinstance(row,dict):raise ValueError(f'{path}:{number}: expected an object')
            yield number,row

def write_ndjson(path,rows):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w',encoding='utf-8',newline='\n') as dst:
        for row in rows:dst.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    temporary.replace(path)

def write_json(path,value):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def approved(path):
    result={}
    if not path or not pathlib.Path(path).exists():return result
    for number,row in read_ndjson(path):
        source=row.get('source');target=row.get('translated',row.get('target'))
        if row.get('status') in ['missing','dated','ignore','technical']:continue
        if isinstance(source,str) and row.get('translation_source_sha256',source_id(source))!=source_id(source):continue
        if not isinstance(source,str) or not isinstance(target,str) or not target:continue
        errors=validate(source,target)
        if errors:raise ValueError(f'{path}:{number}: {errors}')
        if source in result and result[source]!=target:raise ValueError(f'Conflicting reviewed source in {path}:{number}')
        result[source]=target
    return result

class ReuseIndex:
    def __init__(self,path):
        self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA temp_store=MEMORY');self.db.execute('PRAGMA cache_size=-65536')
    def build(self,paths):
        self.db.executescript('DROP TABLE IF EXISTS legacy; CREATE TABLE legacy(source TEXT,target TEXT,file TEXT,line INTEGER,namespace TEXT,key TEXT,kind TEXT);')
        count=0
        for path in paths:
            pending=[]
            for number,row in read_ndjson(path):
                target=row.get('translated',row.get('target',row.get('vi')))
                if not isinstance(target,str) or not target:continue
                fields=[('source',row.get('source',row.get('zh'))),('locresImport',row.get('locresImport'))]
                seen=set()
                for kind,source in fields:
                    if not isinstance(source,str) or not source or source in seen:continue
                    seen.add(source);pending.append((source,target,str(path),number,row.get('namespace',''),row.get('key',''),kind));count+=1
                if len(pending)>=10000:self.db.executemany('INSERT INTO legacy VALUES(?,?,?,?,?,?,?)',pending);pending=[]
            self.db.executemany('INSERT INTO legacy VALUES(?,?,?,?,?,?,?)',pending)
        self.db.execute('CREATE INDEX legacy_source ON legacy(source)')
        self.db.execute('CREATE INDEX legacy_identity ON legacy(source,namespace,key)');self.db.commit()
        return count
    def choose(self,source):
        candidates=[];rejected=collections.Counter()
        def checked(rows):
            result=[]
            for row in rows:
                row=dict(row);errors=validate(source,row['target'])
                if row['target']==source:errors.append('unchanged_target')
                if errors:rejected.update(errors)
                else:result.append(row)
            return result
        # Reuse eligibility is literal source equality across all indexed routes.
        # Namespace/key are provenance only, never query constraints.
        candidates=checked(self.db.execute('SELECT * FROM legacy WHERE source=?',(source,)))
        if not candidates:return None,dict(reason='quality_review' if rejected else 'no_exact_translation',rejected=dict(rejected))
        if any(r['kind']=='source' for r in candidates):candidates=[r for r in candidates if r['kind']=='source']
        canonical={}
        for row in candidates:
            identity=row['file'],row['namespace'],row['key']
            if identity not in canonical or row['line']>canonical[identity]['line']:canonical[identity]=row
        groups=collections.defaultdict(list)
        for row in canonical.values():groups[row['target']].append(row)
        def rank(item):
            target,refs=item
            return len(refs),max(pathlib.Path(r['file']).name=='vi.ndjson' for r in refs),max(r['line'] for r in refs),target
        target,refs=max(groups.items(),key=rank)
        references=[{k:r[k] for k in ['file','line','namespace','key','kind']} for r in refs[:3]]
        for reference in references:reference['file']=pathlib.Path(reference['file']).name
        return target,dict(method='exact_legacy_source',alternatives=len(groups),refs=references)

def native_sync(dumps,out,index,reviewed=None):
    sources={};refs={};previous=approved(reviewed)
    decisions={r['source']:r for _,r in read_ndjson(reviewed)} if reviewed and pathlib.Path(reviewed).exists() else {}
    for path in dumps:
        for number,row in read_ndjson(path):
            if row.get('route') not in ['native_record_string_reader','native_data_decoder_assignment']:raise ValueError(f'{path}:{number}: not a native data capture')
            source=row.get('source')
            if not isinstance(source,str) or not source:raise ValueError('Missing capture source')
            sources[source]=sources.get(source,0)+1;refs.setdefault(source,dict(file=pathlib.Path(path).name,line=number))
    observed=set(sources)
    for source,row in decisions.items():
        if row.get('status') in ['translated','missing','ignore'] and row.get('source_sha256')==source_id(source):sources.setdefault(source,0)
    rows=[];provenance=[];counts=collections.Counter()
    for source in sorted(sources):
        target=None;why={}
        previous_row=decisions.get(source,{})
        if previous_row.get('status')=='ignore':state='ignore';why=dict(reason=previous_row.get('reason','reviewed_ignore'))
        elif RESOURCE.search(source):state='ignore';why=dict(reason='resource_or_filename')
        else:
            if source in previous:target=previous[source];why=dict(method='previous_reviewed_exact_source')
            else:target,why=index.choose(source)
            stale=previous_row.get('status')=='dated' or (previous_row.get('translated') and previous_row.get('translation_source_sha256',source_id(source))!=source_id(source))
            state='translated' if target else 'missing'
            if stale and not target:why=dict(reason='previous_translation_bound_to_other_source',review_required=True)
        retained_review=state=='translated' and target==previous_row.get('translated') and previous_row.get('review_required',False)
        counts[state]+=1
        rows.append(dict(source=source,source_sha256=source_id(source),translation_source_sha256=source_id(source) if target else None,
            translated=target,status=state,reason=why.get('reason'),review_required=bool(retained_review or why.get('reason')=='quality_review' or why.get('review_required',False)),
            review_reason=previous_row.get('review_reason') if retained_review else None,observed_in_inputs=source in observed))
        provenance.append(dict(source_sha256=source_id(source),capture=refs.get(source),reuse=why))
    write_ndjson(out,rows);write_ndjson(pathlib.Path(out).with_suffix('.provenance.ndjson'),provenance)
    return rows,dict(unique_sources=len(rows),counts=dict(counts),quality_review=sum(r['review_required'] for r in rows),
        observed_unique_sources=len(observed),retained_not_observed=len(sources.keys()-observed),inputs=[dict(file=pathlib.Path(p).name,sha256=digest(p)) for p in dumps])

def native_usage(catalog,dumps,out):
    decisions={r['source']:r for _,r in read_ndjson(catalog)};observed=set();sessions=[]
    for path in dumps:
        for _,row in read_ndjson(path):observed.add(row['source'])
        metadata=pathlib.Path(path).parent/'session.json';build=pathlib.Path(path).parent/'build.json'
        sessions.append(dict(dump=str(path),sha256=digest(path),session=json.loads(metadata.read_text(encoding='utf-8-sig')) if metadata.exists() else None,
            build=json.loads(build.read_text(encoding='utf-8-sig')) if build.exists() else None))
    rows=[dict(source=s,status=row.get('status','missing'),usage='observed' if s in observed else 'not_observed',
        source_sha256=source_id(s)) for s,row in sorted(decisions.items())]
    write_ndjson(pathlib.Path(out).with_suffix('.ndjson'),rows)
    result=dict(dictionary_entries=len(rows),observed_dictionary_entries=len(decisions.keys()&observed),not_observed=len(decisions.keys()-observed),
        sessions=sessions,policy='not_observed is a review candidate, never automatic proof of dead content. No catalog entries were removed.')
    write_json(out,result);return result

def native_sources(path):
    """Current reader-source inventory, independent of translation decisions.

    Accept raw captures or a native-sync catalog. Retained historical catalog
    rows explicitly absent from the selected captures are not current evidence.
    """
    sources=set()
    for number,row in read_ndjson(path):
        source=row.get('source')
        if not isinstance(source,str) or not source:raise ValueError(f'{path}:{number}: missing native source')
        if row.get('route') is None and not isinstance(row.get('observed_in_inputs'),bool):
            raise ValueError(f'{path}:{number}: native provenance missing; use a reader capture or native-sync catalog, not a legacy translation catalog')
        if row.get('route') is not None and row['route'] not in ['native_record_string_reader','native_data_decoder_assignment','native_tooltip_fstring_observation']:
            raise ValueError(f'{path}:{number}: not a native data capture')
        if row.get('source_sha256',source_id(source))!=source_id(source):raise ValueError(f'{path}:{number}: native source hash mismatch')
        if row.get('observed_in_inputs') is False:continue
        sources.add(source)
    return sources


def native_origin_texts(path):
    """Source text plus the observed/applied reader-output text, for provenance."""
    sources=native_sources(path);outputs=set()
    for _,row in read_ndjson(path):
        source=row['source']
        if row.get('observed_in_inputs') is False:continue
        if row.get('route') is not None:
            # Observation/capture-only rows cannot certify a substituted output.
            applied=row.get('status')=='translated' and row.get('capture_only') is not True
            target=row.get('target') if applied else None
        else:
            target=row.get('translated') if row.get('status')=='translated' and row.get('translation_source_sha256',source_id(source))==source_id(source) else None
        if isinstance(target,str) and target:outputs.add(target)
    return sources,outputs


def fallback_sync(logs,native,out,index):
    from ue_log import iter_misses
    data_sources,data_outputs=native_origin_texts(native);stats=collections.Counter();observations={};identity_sources=collections.defaultdict(set);excluded=[]
    previous={(r['namespace'],r['key']):r for _,r in read_ndjson(out)} if pathlib.Path(out).exists() else {}
    for path in logs:
        for row in iter_misses(path,stats):
            source=row['source'];identity=row['namespace'],row['key'],source
            if source in data_outputs:
                stats['native_reader_output_miss_events']+=1;continue
            if source in data_sources:
                # The same CN literal can also be an independent widget FText.
                # It is a reuse key, never evidence that this identity is handled.
                stats['retained_native_source_overlap_events']+=1
            if not source or not CJK.search(source) or RESOURCE.search(source):continue
            observations.setdefault(identity,{**row,'log_file':pathlib.Path(path).name})
            identity_sources[identity[:2]].add(source)
    rows=[];provenance=[];cache={}
    for identity,row in sorted(observations.items()):
        source=row['source']
        if len(identity_sources[identity[:2]])>1:
            excluded.append(dict(**row,reason='conflicting_source_for_runtime_identity'));continue
        if source not in cache:cache[source]=index.choose(source)
        target,why=cache[source];old=previous.get(identity[:2],{})
        state='translated' if target else 'missing'
        if old.get('source')==source:
            if old.get('status')=='ignore':target=None;state='ignore';why=dict(reason=old.get('reason','reviewed_ignore'))
            elif old.get('translated') and old.get('translation_source_sha256',source_id(source))==source_id(source) and not validate(source,old['translated']):
                target=old['translated'];state='translated';why=dict(method='previous_reviewed_exact_identity_source')
        rows.append(dict(namespace=row['namespace'],key=row['key'],source=source,translated=target,
            source_sha256=source_id(source),translation_source_sha256=source_id(source) if target else None,
            status=state,reason=why.get('reason'),review_required=why.get('reason')=='quality_review'))
        provenance.append(dict(**row,reuse=why))
    write_ndjson(out,rows);write_ndjson(pathlib.Path(out).with_suffix('.provenance.ndjson'),provenance)
    write_ndjson(pathlib.Path(out).with_suffix('.conflicts.ndjson'),excluded)
    return rows,dict(entries=len(rows),unique_sources=len({r['source'] for r in rows}),translated=sum(bool(r['translated']) for r in rows),
        pending=sum(not r['translated'] for r in rows),conflicts=len(excluded),counts=dict(stats),
        native_source_inventory=dict(file=pathlib.Path(native).name,sha256=digest(native),unique_sources=len(data_sources),unique_reader_outputs=len(data_outputs),scope='Current capture sources and observed/applied substitution outputs; exclude explicitly not-observed historical catalog rows.'),
        exclusion='Exclude only exact observed/applied native output text. Keep CN source overlap at its fresh FText namespace/key/source; source equality is reuse evidence, not producer or replacement evidence.',
        limitation='Missing diagnostics do not cover valid CN stock passthrough. Preserve separately validated stock widget bindings and all conflicting source variants.')

def decode_text(raw):
    if raw.startswith(b'\xff\xfe'):return raw[2:].decode('utf-16-le'),'utf-16-le',b'\xff\xfe'
    if raw.startswith(b'\xfe\xff'):return raw[2:].decode('utf-16-be'),'utf-16-be',b'\xfe\xff'
    if raw.startswith(b'\xef\xbb\xbf'):return raw[3:].decode('utf-8'),'utf-8',b'\xef\xbb\xbf'
    return raw.decode('utf-8'),'utf-8',b''

FMT_LINE=re.compile(r'^(?P<prefix>[ \t]*[^#;= \t\r\n][^=\r\n]*?[ \t]*=[ \t]*)(?P<source>[^\r\n]*)(?P<newline>\r\n|\r|\n)?$')
def fmt_files(roots):
    selected={}
    for root in roots:
        root=pathlib.Path(root)
        for path in sorted(root.rglob('*.txt')):selected[path.relative_to(root).as_posix()]=path
    return selected

def fmt_records(roots):
    rows=[];files=[]
    for namespace,path in sorted(fmt_files(roots).items()):
        raw=path.read_bytes();text,encoding,bom=decode_text(raw);keys=set()
        for line in text.splitlines(keepends=True):
            if line.lstrip().startswith(('#',';','//')):continue
            match=FMT_LINE.fullmatch(line)
            if not match:continue
            key=match['prefix'].split('=',1)[0].strip()
            if key in keys:raise ValueError(f'{namespace}: duplicate FormatString key {key}')
            keys.add(key);rows.append(dict(namespace=namespace,key=key,source=match['source']))
        files.append(dict(path=namespace,sha256=hashlib.sha256(raw).hexdigest(),encoding=encoding,bom=bom.hex(),entries=len(keys)))
    return rows,files

def fmt_sync(roots,out,index,old_catalog):
    current,files=fmt_records(roots);old={(r.get('namespace',''),r['key']):r for _,r in read_ndjson(old_catalog)}
    rows=[];counts=collections.Counter();current_keys=set()
    ignore_path=pathlib.Path(__file__).resolve().parents[1]/'config/ignore-strings.json'
    ignores={(r['namespace'],r['key'],r['source']):r['reason'] for r in json.loads(ignore_path.read_text(encoding='utf-8'))} if ignore_path.exists() else {}
    for row in current:
        identity=row['namespace'],row['key'];current_keys.add(identity);previous=old.get(identity)
        counts['added' if previous is None else ('source_changed' if previous.get('source')!=row['source'] else 'source_unchanged')]+=1
        target,why=index.choose(row['source'])
        state='translated' if target else ('dated' if previous is not None and previous.get('source')!=row['source'] else 'missing')
        if previous is not None and previous.get('source')==row['source']:
            if previous.get('status')=='ignore':target=None;state='ignore';why=dict(reason=previous.get('reason','reviewed_ignore'))
            elif previous.get('translated') and previous['translated']!=row['source'] and previous.get('translation_source_sha256',source_id(row['source']))==source_id(row['source']) and not validate(row['source'],previous['translated']):
                target=previous['translated'];state='translated';why=dict(method='previous_reviewed_exact_identity_source')
            elif not target and previous.get('status')=='dated' and previous.get('previous_source') is not None:
                state='dated'
        if not row['source']:target=None;state='ignore';why=dict(reason='empty_source')
        if (row['namespace'],row['key'],row['source']) in ignores:
            target=None;state='ignore';why=dict(reason=ignores[row['namespace'],row['key'],row['source']])
        rows.append(dict(**row,translated=target,status=state,source_sha256=source_id(row['source']),
            translation_source_sha256=source_id(row['source']) if target else None,
            previous_source=(previous.get('previous_source') if previous.get('source')==row['source'] else previous.get('source')) if state=='dated' else None,reason=why.get('reason'),review_required=why.get('reason')=='quality_review'))
        counts[state]+=1
    counts['removed']=len(old.keys()-current_keys)
    write_ndjson(out,rows)
    write_json(pathlib.Path(out).with_suffix('.sources.json'),dict(files=files,layer_order=[pathlib.Path(p).name for p in roots]))
    return rows,dict(entries=len(rows),unique_sources=len({r['source'] for r in rows}),files=len(files),counts=dict(counts),
        policy='Reconcile current file/key/source. Reuse only exact source; preserve independent FormatString coverage even if a source also appears in .data.')

def render_fmt(roots,catalog,out,source_manifest):
    items={(r['namespace'],r['key']):r for _,r in read_ndjson(catalog)}
    expected={r['path']:r['sha256'] for r in json.loads(pathlib.Path(source_manifest).read_text(encoding='utf-8'))['files']}
    files=fmt_files(roots)
    if files.keys()!=expected.keys():raise ValueError('FormatString source file set changed; sync current sources again')
    for namespace,path in sorted(files.items()):
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected[namespace]:raise ValueError(f'{namespace}: source bytes changed; sync again')
        text,encoding,bom=decode_text(raw);lines=[]
        for line in text.splitlines(keepends=True):
            match=None if line.lstrip().startswith(('#',';','//')) else FMT_LINE.fullmatch(line)
            if match:
                key=match['prefix'].split('=',1)[0].strip();row=items.get((namespace,key));target=row.get('translated') if row and row.get('status','translated')=='translated' else None
                if row is None or row['source']!=match['source']:raise ValueError(f'{namespace}:{key}: catalog/source mismatch')
                if target:
                    if row.get('translation_source_sha256',source_id(row['source']))!=source_id(row['source']):raise ValueError(f'{namespace}:{key}: dated source binding')
                    errors=validate(row['source'],target)
                    if errors:raise ValueError(f'{namespace}:{key}: {errors}')
                    line=match['prefix']+target+(match['newline'] or '')
            lines.append(line)
        target_path=pathlib.Path(out)/namespace;target_path.parent.mkdir(parents=True,exist_ok=True)
        target_path.write_bytes(bom+''.join(lines).encode(encoding))

def review_batches(catalog,out,max_chars=18000):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=False);batch=[];chars=0;count=0
    for _,row in read_ndjson(catalog):
        if row.get('status') in ['ignore','technical'] or (row.get('translated') and row.get('status')!='dated' and not row.get('review_required')):continue
        if batch and chars+len(row['source'])>max_chars:
            write_ndjson(out/f'{count:04d}.ndjson',batch);count+=1;batch=[];chars=0
        batch.append(dict(source=row['source'],source_sha256=source_id(row['source']),translated=None,current_translation=row.get('translated'),status=row.get('status','missing'),reason=row.get('review_reason') or row.get('reason')));chars+=len(row['source'])
    if batch:write_ndjson(out/f'{count:04d}.ndjson',batch);count+=1
    return count

def apply_review(catalog,review,out):
    targets={}
    for number,row in read_ndjson(review):
        if row.get('source_sha256')!=source_id(row['source']):raise ValueError(f'{review}:{number}: source identity changed')
        state=row.get('status','translated')
        if state in ['missing','dated'] and row.get('translated'):state='translated'
        if state not in ['translated','ignore']:raise ValueError('Review must supply a translation or an explicit ignore decision')
        errors=[] if state=='ignore' and row.get('reason') else validate(row['source'],row.get('translated'))
        if errors:raise ValueError(f'{review}:{number}: {errors}')
        decision=dict(translated=row.get('translated') if state=='translated' else None,status=state,reason=row.get('reason'),
            translation_source_sha256=source_id(row['source']) if state=='translated' else None,review_required=False,review_reason=None)
        if row['source'] in targets and targets[row['source']]!=decision:raise ValueError('Conflicting review answers')
        targets[row['source']]=decision
    rows=[];found=set()
    for _,row in read_ndjson(catalog):
        if row['source'] in targets:
            row.update(targets[row['source']]);found.add(row['source'])
        rows.append(row)
    if found!=targets.keys():raise ValueError('Review contains unknown source; refusing partial import')
    write_ndjson(out,rows);return len(found)
