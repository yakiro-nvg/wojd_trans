import hashlib,re
STAMP=re.compile(r'^\[\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3}\]')
MISS=re.compile(r'\(Namespace:(?P<namespace>.*?), Key:(?P<key>.*?), Source:(?P<source>.*)\), but it did not exist\.$',re.S)
HASH_MISMATCH=re.compile(r'\(Namespace:(?P<namespace>.*?), Key:(?P<key>.*?)\), but the source string hash does not match - the source string \((?P<source>.*)\) will be used\.$',re.S)
CJK=re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while block:=f.read(1024*1024):h.update(block)
    return h.hexdigest()

def iter_misses(path,stats):
    buffer=None;first=0
    def parse(value,number):
        match=MISS.search(value.rstrip('\r\n'))
        kind='MISSING'
        if not match:
            match=HASH_MISMATCH.search(value.rstrip('\r\n'))
            kind='HASH_MISMATCH'
        if not match:
            stats['unparsed_missing_records']+=1;return None
        stats['parsed_miss_events']+=1
        if kind=='HASH_MISMATCH':stats['parsed_hash_mismatch_events']+=1
        return dict(namespace=match['namespace'].strip(),key=match['key'].strip(),source=match['source'],log_line=number,diagnostic_kind=kind)
    with path.open(encoding='utf-8-sig',newline='') as f:
        for number,line in enumerate(f,1):
            if buffer is not None and STAMP.match(line):
                row=parse(buffer,first)
                if row:yield row
                buffer=None
            if buffer is None and 'LogTextLocalizationManager:' in line and '(Namespace:' in line and ('Source:' in line or 'but the source string hash does not match - the source string (' in line):
                buffer=line;first=number
            elif buffer is not None:buffer+=line
            if buffer is not None and (buffer.rstrip('\r\n').endswith('), but it did not exist.') or buffer.rstrip('\r\n').endswith(') will be used.')):
                row=parse(buffer,first)
                if row:yield row
                buffer=None
        if buffer is not None:
            row=parse(buffer,first)
            if row:yield row
