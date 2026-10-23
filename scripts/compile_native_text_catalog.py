"""Compile editable UTF-8 JSON text rules into a checked, sorted runtime catalog."""
import argparse,json,pathlib,re,struct
MAGIC=b'WJTXT1\r\n'
def compile_catalog(config):
    version=config.get('format_version',1)
    if version not in (1,2):raise ValueError('Unsupported catalog version')
    fields=sorted(set(config['capture_fields']))
    if not 0<len(fields)<=4096:raise ValueError('Invalid field count')
    for field in fields:
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,62}',field):raise ValueError('Invalid field name')
    rules={}
    for rule in config['translations']:
        field=rule['field'];source=rule['source'].encode('utf-8');target=rule['target'].encode('utf-8')
        if field not in fields:raise ValueError('Rule field is not in capture_fields')
        if not source or (not target and version==1) or b'\0' in source+target or max(len(source),len(target))>65535:raise ValueError('Invalid text')
        key=(fields.index(field),source)
        if key in rules and rules[key]!=target:raise ValueError('Conflicting translations')
        rules[key]=target
    if len(rules)>300000:raise ValueError('Too many translations')
    def string(value):return struct.pack('<I',len(value))+value+b'\0'
    out=bytearray((MAGIC if version==1 else b'WJTXT2\r\n')+struct.pack('<II',len(fields),len(rules)))
    for field in fields:out+=string(field.encode('ascii'))
    for (field,source),target in sorted(rules.items()):out+=struct.pack('<I',field)+string(source)+string(target)
    return bytes(out)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=pathlib.Path);p.add_argument('output',type=pathlib.Path);a=p.parse_args()
    data=compile_catalog(json.loads(a.input.read_text(encoding='utf-8')));a.output.write_bytes(data)
    print(f'Compiled {len(data)} bytes: {a.output}')
