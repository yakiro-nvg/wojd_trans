"""Independent ABI, source guarding and origin-gate tests; never executes captured code."""
import argparse,collections,concurrent.futures,ctypes as c,hashlib,json,os,pathlib,re,shutil,struct,subprocess,sys
from ctypes import wintypes as w
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from catalog_core import approved,read_ndjson
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['normal','far']);p.add_argument('--profile',choices=['runtime','dump'],default='dump');p.add_argument('--language',default='vi');a=p.parse_args()
OUT=ROOT/'native/build'/(a.profile+'-test')
if a.mode is None:
    for mode in ['normal','far']:subprocess.run([sys.executable,'-X','utf8',__file__,'--mode',mode,'--profile',a.profile,'--language',a.language],check=True)
    print(a.profile+': all fixture modes passed');raise SystemExit()
shutil.copyfile(pathlib.Path(os.environ['SystemRoot'])/'System32/dbghelp.dll',OUT/'wojd_dbghelp_original.dll')
exports=[]
for line in (ROOT/'native/original.def').read_text().splitlines()[2:]:
    tokens=line.split()
    if not tokens:continue
    exports.append(dict(name=None if 'NONAME' in tokens else tokens[0],ordinal=int(next(x[1:] for x in tokens if x.startswith('@')))))
manifest=dict(exports=exports,catalog_path=str(ROOT/'work/catalog.bin'))
K=c.WinDLL('kernel32',use_last_error=True)
K.VirtualAlloc.argtypes=[c.c_void_p,c.c_size_t,w.DWORD,w.DWORD];K.VirtualAlloc.restype=c.c_void_p
K.VirtualFree.argtypes=[c.c_void_p,c.c_size_t,w.DWORD];K.VirtualFree.restype=w.BOOL
K.VirtualProtect.argtypes=[c.c_void_p,c.c_size_t,w.DWORD,c.POINTER(w.DWORD)];K.VirtualProtect.restype=w.BOOL
K.GetProcAddress.argtypes=[w.HMODULE,c.c_void_p];K.GetProcAddress.restype=c.c_void_p
original=c.WinDLL(str(OUT/'wojd_dbghelp_original.dll'));dll=c.WinDLL(str(OUT/'dbghelp.dll'))
for symbol in manifest['exports']:
    token=c.cast(c.c_char_p(symbol['name'].encode()),c.c_void_p) if symbol['name'] else c.c_void_p(symbol['ordinal'])
    assert K.GetProcAddress(original._handle,token)==K.GetProcAddress(dll._handle,token)
assert dll.WojdNativeCanaryVersion()==0x4e3a
class GameString(c.Structure):_fields_=[('data',c.c_void_p),('count',c.c_int),('capacity',c.c_int)]
class Stream(c.Structure):_fields_=[('data',c.c_void_p),('size',c.c_size_t),('position',c.c_size_t),('calls',w.DWORD),('last_key',w.DWORD)]
class Status(c.Structure):_fields_=[(n,w.LONG) for n in ['calls','failed','strings','translated','unknown','invalid','exceptions','dropped']]+[('restored',w.DWORD)]
def api(name,args,ret=w.DWORD):
    fn=getattr(dll,'WojdN10SelfTest'+name);fn.argtypes=args;fn.restype=ret;return fn
origin=api('Origin',[c.c_void_p,c.c_void_p,c.c_void_p])
header=(ROOT/'native/src/native_data_signatures.h').read_text()
def signature(name):
    value=re.search(r'\b'+name+r'\[\]\s*=\s*\{(.*?)\}',header,re.S)[1]
    return bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{2})',value))
expected=signature('data_reader_bytes');mask=signature('data_reader_mask');assign_bytes=signature('data_assign_bytes')
origin_tests=[]
for mutation in ['none','unrelated_body_changed','prologue_changed','call_window_changed','callee_changed','outside_image']:
    size=0x800000;base=K.VirtualAlloc(None,size,0x3000,4);assert base
    try:
        header=bytearray(4096);header[:2]=b'MZ';struct.pack_into('<I',header,0x3c,0x80);header[0x80:0x84]=b'PE\0\0'
        struct.pack_into('<HHIIIHH',header,0x84,0x8664,1,0,0,0,240,0x2022);struct.pack_into('<H',header,0x98,0x20b)
        struct.pack_into('<Q',header,0x98+24,base);struct.pack_into('<II',header,0x98+56,size,4096)
        header[0x188:0x18d]=b'.text';struct.pack_into('<IIII',header,0x188+8,0x600000,0x1000,0x600000,0);struct.pack_into('<I',header,0x188+36,0x60000020)
        c.memmove(base,bytes(header),4096);reader=base+0x3000;assigner=base+0x7000
        c.memmove(reader,expected,len(expected));c.memmove(assigner,assign_bytes,len(assign_bytes))
        c.memmove(reader+0x21f,struct.pack('<i',assigner-(reader+0x223)),4)
        if mutation=='unrelated_body_changed':c.c_ubyte.from_address(reader+0x15e).value^=1
        elif mutation=='prologue_changed':c.c_ubyte.from_address(reader+10).value^=1
        elif mutation=='call_window_changed':c.c_ubyte.from_address(reader+next(i for i in range(0x20b,0x230) if mask[i]==255)).value^=1
        elif mutation=='callee_changed':c.memmove(reader+0x21f,struct.pack('<i',assigner+16-(reader+0x223)),4)
        elif mutation=='outside_image':assigner=base+size+4096
        error=origin(base,reader,assigner);assert (error==0)==(mutation in ['none','unrelated_body_changed']),(mutation,error)
        origin_tests.append(dict(mutation=mutation,status=error))
    finally:assert K.VirtualFree(base,0,0x8000)
load=api('LoadCatalog',[w.LPCWSTR]);prepare=api('PrepareCatalog',[]);install=api('Install',[c.c_void_p,c.c_void_p]);restore=api('Restore',[]);status_fn=api('Status',[c.POINTER(Status)])
force=api('ForceFar',[w.DWORD]);assert force(a.mode=='far')==0
catalog=pathlib.Path(manifest['catalog_path']);assert load(str(catalog))==0 and prepare()==0
catalog_source=ROOT/f'translations/{a.language}.native.ndjson'
rules=approved(catalog_source)
f=c.WinDLL(str(OUT/'data_reader_fixture.dll'));read=f.WojdFixtureRead;read.argtypes=[c.POINTER(Stream),c.POINTER(GameString),w.DWORD];read.restype=c.c_ubyte
assign=f.WojdFixtureAssignTarget;assign.argtypes=[c.POINTER(GameString),w.LPCWSTR];assign.restype=c.c_void_p
free=f.WojdFixtureFree;free.argtypes=[c.POINTER(GameString)]
target=c.cast(assign,c.c_void_p).value;site=K.GetProcAddress(f._handle,c.cast(c.c_char_p(b'WojdFixtureAssignmentReturn'),c.c_void_p));assert site
before=c.string_at(target,32);observation=OUT/'wojd/selftest-data.ndjson';baseline=observation.stat().st_size if observation.exists() else 0
assert install(target,site)==0;patched=c.string_at(target,16);assert patched!=before[:16]
if a.mode=='far':assert patched[:2]==b'\xff\x25',patched.hex()
sentinel=0xa57839cf
def run(source,expected_target=None,key=0x4c53f9e0):
    raw=source.encode('utf-8');keybytes=struct.pack('<I',key);encrypted=bytes(v^keybytes[i%4] for i,v in enumerate(raw))
    blob=struct.pack('<I',len(raw))+encrypted+struct.pack('<I',sentinel);storage=c.create_string_buffer(blob)
    stream=Stream(c.addressof(storage),len(blob),0,0,0);out=GameString()
    try:
        assert read(c.byref(stream),c.byref(out),key)==1
        assert stream.calls==1 and stream.last_key==key and stream.position==4+len(raw)
        expected_target=rules.get(source,source) if expected_target is None else expected_target
        assert c.wstring_at(out.data)==expected_target,(source,c.wstring_at(out.data),expected_target)
        assert out.count==len(expected_target.encode('utf-16-le'))//2+1 and out.capacity>=out.count
        assert storage.raw[:len(blob)]==blob and struct.unpack_from('<I',storage.raw,stream.position)[0]==sentinel
    finally:free(c.byref(out))
for i,source in enumerate(rules):run(source,key=(0x10001*i+0x12345678)&0xffffffff)
ignored=[r['source'] for _,r in read_ndjson(catalog_source) if r.get('status')=='ignore']
for source in ignored:run(source,source)
for source in ['猩红巨蚁（新版本）','猩红巨蚁%d','尚未翻译：甲\\n乙\n丙\r\n丁。','未经收录的长段落。'*200,'/Game/内部资源/猩红巨蚁','ASCII_INTERNAL_IDENTIFIER']:run(source,source)
run('猩红巨蚁\0后缀',rules.get('猩红巨蚁','猩红巨蚁'))
# The same strings assigned from every other origin must stay unchanged.
for source in list(rules)[:100]+['猩红巨蚁','提高物理技能伤害']:
    out=GameString();assert assign(c.byref(out),source)==c.addressof(out);assert c.wstring_at(out.data)==source;free(c.byref(out))
storage=c.create_string_buffer(struct.pack('<I',100)+b'bad');stream=Stream(c.addressof(storage),7,0,0,0);out=GameString();assign(c.byref(out),'Original')
assert read(c.byref(stream),c.byref(out),0x99)==0 and c.wstring_at(out.data)=='Original' and stream.position==4;free(c.byref(out))
def threaded(i):
    for j in range(100):run('猩红巨蚁',key=(i<<16)+j)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(threaded,range(4)))
assert restore()==0 and c.string_at(target,32)==before;run('猩红巨蚁','猩红巨蚁')
status=Status();assert status_fn(c.byref(status))==0
assert status.restored==1 and not any(getattr(status,n) for n in ['exceptions','invalid','dropped'])
if a.profile=='dump':assert status.translated>=len(rules)+(400 if '猩红巨蚁' in rules else 0)
else:assert status.calls==0 and status.strings==0 and status.translated==0 and not observation.exists()
if a.profile=='dump':
    rows=[json.loads(line) for line in observation.read_bytes()[baseline:].splitlines()]
    assert rows and all(r['pid']==os.getpid() and r['route']=='native_data_decoder_assignment' and r['field_key_available'] is False for r in rows)
    if '猩红巨蚁' in rules:assert any(r['source']=='猩红巨蚁' and r['target']==rules['猩红巨蚁'] for r in rows)
    if ignored:assert any(r['source']==ignored[0] and r['status']=='ignore' and not r['translated'] and r['target']=='' for r in rows)
    assert any(r['status']=='missing' and not r['translated'] for r in rows)
report=dict(status='PASS',mode=a.mode,approved_rules=len(rules),non_decoder_calls_unchanged=True,exact_source_and_marker_changes_preserve_CN=True,
    source_bytes_cursor_key_and_numeric_sentinel_unchanged=True,concurrent_threads=4,entry_restored=True,
    profile=a.profile,runtime_has_no_capture_counters_or_dump=a.profile=='runtime',origin_tests=origin_tests,entry_jump='absolute14' if patched[:2]==b'\xff\x25' else 'relative5',counters={n:getattr(status,n) for n,_ in Status._fields_})
(OUT/f'runtime-selftest-{a.mode}.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(a.profile+' '+a.mode+': PASS ('+str(len(rules))+' rules)')
