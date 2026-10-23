"""Read production PE exports without loading/executing either DLL."""
import hashlib,json,pathlib,struct
ROOT=pathlib.Path(__file__).resolve().parents[1]

def exports(path):
    raw=path.read_bytes();pe=struct.unpack_from('<I',raw,0x3c)[0]
    assert raw[:2]==b'MZ' and raw[pe:pe+4]==b'PE\0\0'
    machine,sections,_,_,_,optional_size,_=struct.unpack_from('<HHIIIHH',raw,pe+4)
    assert machine==0x8664;optional=pe+24
    assert struct.unpack_from('<H',raw,optional)[0]==0x20b
    spans=[]
    for i in range(sections):
        start=optional+optional_size+i*40
        virtual_size,rva,size,offset=struct.unpack_from('<IIII',raw,start+8);spans.append((rva,max(size,virtual_size),offset))
    def address(rva):
        for begin,length,offset in spans:
            if begin<=rva<begin+length:return offset+rva-begin
        raise ValueError('Unmapped PE RVA')
    def string(rva):
        offset=address(rva);return raw[offset:raw.index(b'\0',offset)].decode('ascii')
    rva,length=struct.unpack_from('<II',raw,optional+112)
    _,_,_,_,_,base,functions,names,table,name_table,ordinals=struct.unpack_from('<IIHHIIIIIII',raw,address(rva))
    named={}
    for i in range(names):
        name=string(struct.unpack_from('<I',raw,address(name_table)+i*4)[0])
        ordinal=base+struct.unpack_from('<H',raw,address(ordinals)+i*2)[0];named[ordinal]=name
    result={}
    for i in range(functions):
        target=struct.unpack_from('<I',raw,address(table)+i*4)[0]
        if target:result[base+i]=dict(name=named.get(base+i),forward=string(target) if rva<=target<rva+length else None)
    imports=[];import_rva,import_length=struct.unpack_from('<II',raw,optional+120)
    if import_rva:
        cursor=address(import_rva)
        while True:
            descriptor=struct.unpack_from('<IIIII',raw,cursor)
            if not any(descriptor):break
            imports.append(string(descriptor[3]));cursor+=20
    # Delay-loaded dependencies must satisfy exactly the same portability rules.
    delay_rva,delay_length=struct.unpack_from('<II',raw,optional+112+13*8)
    if delay_rva:
        cursor=address(delay_rva)
        while True:
            descriptor=struct.unpack_from('<IIIIIIII',raw,cursor)
            if not any(descriptor):break
            assert descriptor[0]&1,'Unsupported VA-based delay import descriptor'
            imports.append(string(descriptor[1]));cursor+=32
    return result,raw,imports

results={}
for profile in ['runtime','dump']:
    found,raw,imports=exports(ROOT/f'native/build/{profile}/dbghelp.dll');forwarded=0
    build=json.loads((ROOT/f'native/build/{profile}/build-profile.json').read_bytes())
    assert build==dict(profile=profile,capture=int(profile=='dump'),selftest=0,optimization='O2',static_crt=True)
    for line in (ROOT/'native/exports.def').read_text().splitlines()[2:]:
        tokens=line.split()
        if not tokens:continue
        name,target=tokens[0].split('=');ordinal=int(tokens[1][1:])
        assert found[ordinal]==dict(name=None if 'NONAME' in tokens else name,forward=target),(profile,ordinal)
        forwarded+=1
    additional=[v for v in found.values() if not v['forward']]
    assert [v['name'] for v in additional]==['WojdTranslationVersion'],additional
    for value in ['D:\\wojd-research','C:\\Users\\','/home/']:
        assert value.encode() not in raw and value.encode('utf-16-le') not in raw
    allowed={'kernel32.dll','ntdll.dll','advapi32.dll','user32.dll','shell32.dll','ole32.dll','wojd_dbghelp_original.dll'}
    unexpected=set(name.lower() for name in imports)-allowed
    assert not unexpected,('Non-system runtime dependency; distribution is not self-contained',unexpected)
    results[profile]=dict(status='PASS',original_forwarders=forwarded,production_exports_only=True,no_research_paths=True,
        imports=imports,external_msvc_runtime_required=False,static_crt=True,sha256=hashlib.sha256(raw).hexdigest(),build=build)
output=ROOT/'native/build/production-check.json';output.write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(results))
