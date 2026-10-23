"""Sparse, source-and-target-bound language review evidence; never runtime data."""
from __future__ import annotations
import collections,datetime,hashlib,json,pathlib

LEVELS=('unreviewed','draft','source_reviewed','client_verified')

def identity(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()

def records(path):
    path=pathlib.Path(path)
    if not path.exists():return
    with path.open(encoding='utf-8-sig') as stream:
        for line in stream:
            if line.strip():yield json.loads(line)

def save(path,rows):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as stream:
        for row in rows:stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    tmp.replace(path)

def active_translations(catalogs):
    active=set()
    for path in catalogs:
        for row in records(path):
            source=row['source'];target=row.get('translated')
            if row.get('status')=='translated' and target:
                if row.get('source_sha256',identity(source))!=identity(source):raise ValueError('Catalog source hash mismatch')
                if row.get('translation_source_sha256',identity(source))!=identity(source):raise ValueError('Catalog has stale translation binding')
                active.add((identity(source),identity(target)))
    return active

def mark(ledger,review,catalogs,level,reviewer,note,glossary_revision=None):
    from translation_quality import validate
    if level not in LEVELS:raise ValueError('Unknown quality level')
    if not reviewer.strip() or not note.strip():raise ValueError('Reviewer and evidence note are required')
    # For client_verified, note describes the particular in-game observation.
    # A general client start or ABI fixture is not language/placement evidence.
    active=active_translations(catalogs)
    existing={}
    for row in records(ledger):
        key=row['source_sha256'],row['translation_sha256']
        if key in existing:raise ValueError('Duplicate quality evidence binding')
        existing[key]=row
    pending={}
    for row in records(review):
        if row.get('status')=='ignore':continue
        source=row['source'];target=row.get('translated')
        if row.get('source_sha256')!=identity(source):raise ValueError('Review source hash mismatch')
        errors=validate(source,target)
        if errors:raise ValueError(f'Invalid review translation: {errors}')
        key=identity(source),identity(target)
        if key not in active:raise ValueError('Review is not the active source/target; refusing partial evidence import')
        old=existing.get(key)
        # Lower-level work does not erase stronger existing evidence.
        if old and LEVELS.index(old['level'])>LEVELS.index(level):continue
        pending[key]=dict(source_sha256=key[0],translation_sha256=key[1],level=level,reviewer=reviewer,
            note=note,glossary_revision=glossary_revision,recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    existing.update(pending);save(ledger,[existing[k] for k in sorted(existing)])
    return dict(recorded=len(pending),evidence_records=len(existing),level=level)

def report(catalogs,ledger,source_output=None):
    from translation_quality import validate
    evidence={}
    for row in records(ledger):
        key=row['source_sha256'],row['translation_sha256']
        if row['level'] not in LEVELS or key in evidence:raise ValueError('Invalid or duplicate quality evidence')
        evidence[key]=row
    sources=collections.defaultdict(dict);used=set();entry_states=collections.Counter()
    qa_failures=0;entry_count=0
    for path in catalogs:
        for row in records(path):
            entry_count+=1;s=row['source'];sid=identity(s);state=row.get('status','missing');t=row.get('translated')
            if row.get('source_sha256',sid)!=sid:raise ValueError('Catalog source hash mismatch')
            if state=='ignore':key=('ignore',None);level='ignore';problems=[]
            elif state!='translated' or not t:key=('untranslated',None);level='untranslated';problems=[]
            else:
                tid=identity(t);binding=sid,tid;key=('translated',tid)
                problems=validate(s,t)
                if row.get('translation_source_sha256',sid)!=sid:problems.append('stale_source_binding')
                level='needs_repair' if problems else evidence.get(binding,{}).get('level','unreviewed')
                if binding in evidence:used.add(binding)
            qa_failures+=bool(problems);entry_states[level]+=1
            item=sources[s].setdefault(key,dict(level=level,translation_sha256=key[1],structural_qa='fail' if problems else ('pass' if state=='translated' else 'not_applicable'),references=[]))
            item['references'].append(dict(catalog=pathlib.Path(path).name,namespace=row.get('namespace'),key=row.get('key')))
    unique_states=collections.Counter();output=[]
    for source,variants in sorted(sources.items()):
        values=list(variants.values());levels={v['level'] for v in values}
        if 'untranslated' in levels:state='untranslated'
        elif 'needs_repair' in levels:state='needs_repair'
        elif levels=={'ignore'}:state='ignore'
        else:state=min((x for x in levels if x!='ignore'),key=LEVELS.index)
        unique_states[state]+=1
        output.append(dict(source=source,source_sha256=identity(source),quality=state,variants=values))
    if source_output:save(source_output,output)
    return dict(unique_sources=len(sources),unique_source_quality=dict(unique_states),catalog_entries=entry_count,
        entry_quality=dict(entry_states),structural_qa_failures=qa_failures,evidence_records=len(evidence),active_evidence_records=len(used),
        unused_evidence_records=len(evidence.keys()-used),
        policy='Lowest active variant level is shown for each source. Same source with a different translation has separate evidence. Structural QA never grants semantic or client verification.',
        definitions=dict(untranslated='Missing or unresolved source in a current route.',ignore='Explicit decision to retain source; not language work.',
            unreviewed='Translation reused/imported without recorded source comparison.',draft='New translation awaiting source review.',
            source_reviewed='Recorded comparison with CN source; not necessarily checked in game.',client_verified='Specific source/target observed in game with recorded evidence.',
            needs_repair='Active translation fails structural/source-binding checks.'))
