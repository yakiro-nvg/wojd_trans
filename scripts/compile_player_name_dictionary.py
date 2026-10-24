"""Build broad local Han-Viet defaults from the pinned, credited sources."""
import argparse,ast,collections,csv,hashlib,json,pathlib,re,unicodedata
ROOT=pathlib.Path(__file__).resolve().parents[1]
def han(cp):return 0x3400<=cp<=0x9fff or 0xf900<=cp<=0xfaff or 0x20000<=cp<=0x323af
def clean(word):
    word=unicodedata.normalize('NFC',word.strip().lower())
    return word if 1<=len(word)<=12 and all(unicodedata.name(c,'').startswith('LATIN ') for c in word) else None
def pinyin(value):
    tone='5';result=''
    for c in unicodedata.normalize('NFD',value.lower()):
        if c in '12345':tone=c
        elif c in '\u0304\u0301\u030c\u0300':tone={'\u0304':'1','\u0301':'2','\u030c':'3','\u0300':'4'}[c]
        elif c=='\u0308':result=result[:-1]+'v'
        elif c.isalpha():result+=c
    return result+tone
def build():
    meta=json.loads((ROOT/'resources/player-name-readings.source.json').read_bytes())
    if hashlib.sha256((ROOT/meta['mapping_snapshot']).read_bytes()).hexdigest()!=meta['mapping_snapshot_sha256']:
        raise ValueError('MVH reading snapshot pin changed')
    for source in meta['supplement_sources']:
        if hashlib.sha256((ROOT/source['file']).read_bytes()).hexdigest()!=source['sha256']:raise ValueError('Dictionary source pin changed')
    source=ROOT/'resources/hanviet-sources'
    mvh={r['codepoint']:r['reading'] for r in (json.loads(l) for l in (ROOT/'resources/player-name-mvh-readings.ndjson').read_text(encoding='utf-8').splitlines())}
    weights=collections.Counter(w.lower() for w in mvh.values());lst=collections.defaultdict(list);phong=collections.defaultdict(list)
    for line in (source/'Data-HanViet-LST.txt').read_text(encoding='utf-8').splitlines():
        match=re.match(r'^U\+([0-9A-Fa-f]+)\s+([^#]+)',line)
        if match:
            cp=int(match[1],16);word=clean(match[2])
            if han(cp) and word and word not in lst[cp]:lst[cp].append(word)
    for row in csv.DictReader((source/'hanviet-pinyin.csv').read_text(encoding='utf-8-sig').splitlines()):
        if len(row['char'])!=1:continue
        cp=ord(row['char'])
        for value in ast.literal_eval(row['hanviet']):
            word=clean(value)
            if han(cp) and word:phong[cp].append((word,row['pinyin']))
    unihan=json.loads((source/'unihan-17.0.0.json').read_bytes())
    viet={int(cp):[w for x in values if (w:=clean(x))] for cp,values in unihan['readings'].items() if han(int(cp))}
    result=dict(mvh);origins={cp:'MVH' for cp in mvh}
    def common(values):return max(dict.fromkeys(values),key=lambda w:weights[w])
    for cp in sorted(set(lst)|set(phong)|set(viet)):
        if cp in result:continue
        main=unihan['mandarin'].get(str(cp),'');choices=[];origin=''
        if cp in phong:
            matching=[word for word,py in phong[cp] if py=='*' or (main and pinyin(py)==pinyin(main))]
            choices=matching or [word for word,_ in phong[cp]];origin='Phong Phan'
        if not choices:
            shared=[w for w in lst[cp] if w in viet.get(cp,[])]
            choices=shared or lst[cp] or viet.get(cp,[]);origin='WinVNKey/Unihan'
        if choices:result[cp]=common(choices).capitalize();origins[cp]=origin
    preferred=json.loads((ROOT/'resources/player-name-preferred-readings.json').read_bytes())
    for c,word in preferred.items():
        if len(c)!=1 or not han(ord(c)) or not clean(word):raise ValueError('Invalid preferred reading')
        result[ord(c)]=word;origins[ord(c)]='Preferred common default'
    for _ in range(8):
        changed=0
        for code,variants in sorted(unihan['variants'].items(),key=lambda p:int(p[0])):
            cp=int(code)
            if cp in result or not han(cp):continue
            options=[v for v in variants if v in result]
            if options:
                target=max(options,key=lambda v:weights[result[v].lower()]);result[cp]=result[target];origins[cp]='Unicode variant';changed+=1
        if not changed:break
    rows=[{'codepoint':cp,'reading':word} for cp,word in sorted(result.items())]
    raw=''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows).encode('utf-8')
    return raw,dict(readings=len(rows),mvh_base=len(mvh),origins=dict(collections.Counter(origins.values())),common_bmp_readings=sum(0x4e00<=cp<=0x9fff for cp in result),xf_input=False)
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    raw,report=build();target=ROOT/'resources/player-name-readings.ndjson'
    if args.check:
        if target.read_bytes()!=raw:raise ValueError('Expanded player-name dictionary is stale')
    else:
        target.write_bytes(raw)
        p=ROOT/'resources/player-name-readings.source.json';meta=json.loads(p.read_bytes());meta.update(readings=report['readings'],expanded_dictionary=report);p.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
if __name__=='__main__':main()
