"""Export portable editorial evidence paths without editing translation content."""
import argparse,hashlib,json,pathlib,re,shutil
PROTECTED={'source','translated','target','previous_source','locresImport','key','namespace','candidate','current_translation'}
LOCAL=re.compile(r"(?i)(?:[a-z]:[\\/]|/home/|/mnt/[a-z]/)[^\s\"'<>`\r\n]*")

def portable(value):
    def replace(match):
        name=match[0].replace('\\','/').rstrip('/').rsplit('/',1)[-1]
        return 'local-evidence/'+name
    return LOCAL.sub(replace,value)

def clean(value,field=None):
    if field in PROTECTED:return value
    if isinstance(value,dict):return {k:clean(v,k) for k,v in value.items()}
    if isinstance(value,list):return [clean(v,field) for v in value]
    return portable(value) if isinstance(value,str) else value

def sanitize(path,backup):
    backup.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,backup/path.name)
    temporary=path.with_suffix('.portable-tmp');changed=0;before=hashlib.sha256();after=hashlib.sha256()
    with path.open('rb') as src,temporary.open('wb') as dst:
        for raw in src:
            before.update(raw)
            if raw.strip():
                row=json.loads(raw);result=clean(row)
                if result!=row:
                    for field in PROTECTED:
                        if field in row:assert result[field]==row[field]
                    raw=(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8');changed+=1
            dst.write(raw);after.update(raw)
    temporary.replace(path)
    return dict(file=path.name,changed_metadata_rows=changed,before=before.hexdigest(),after=after.hexdigest(),translation_fields_preserved=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('catalog',type=pathlib.Path,nargs='+');parser.add_argument('--backup',required=True,type=pathlib.Path);args=parser.parse_args()
    print(json.dumps([sanitize(path,args.backup) for path in args.catalog],indent=2))
