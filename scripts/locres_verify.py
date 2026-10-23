"""Read-only locresV3 tuple parser; independent of overlay producer code."""
import collections,hashlib,re,struct,zlib
from pylocres.city_hash import CityHash
MAGIC=bytes.fromhex('0e147475674a03fc4a15909dc3377f1b')
GUID=re.compile('[0-9A-F]{32}\\Z');ANY_GUID=re.compile('[0-9A-Fa-f]{32}\\Z')
class Invalid(ValueError):pass
def require(value,message):
 if not value:raise Invalid(message)
class Reader:
 def __init__(self,data):self.data=data;self.offset=0
 def take(self,size):
  require(type(size) is int and 0<=size<=len(self.data)-self.offset,'LOCRES_RANGE');start=self.offset;self.offset+=size;return self.data[start:self.offset]
 def number(self,fmt):return struct.unpack('<'+fmt,self.take(struct.calcsize('<'+fmt)))[0]
 def string(self):
  n=self.number('i');require(abs(n)<=10000000,'LOCRES_STRING_LIMIT')
  if n==0:return ''
  wide=n<0;raw=self.take(-2*n if wide else n);terminator=b'\0\0' if wide else b'\0';require(raw.endswith(terminator),'LOCRES_TERMINATOR')
  try:value=raw[:-len(terminator)].decode('utf-16le' if wide else 'ascii',errors='strict')
  except UnicodeError as e:raise Invalid('LOCRES_STRING_ENCODING') from e
  require('\0' not in value,'LOCRES_EMBEDDED_NUL');return value
def read_bytes(data):
 r=Reader(data);require(r.take(16)==MAGIC and r.number('B')==3,'LOCRES_V3_ONLY');pool_offset=r.number('Q');entry_count=r.number('I');namespace_count=r.number('I');require(entry_count<=len(data)//12 and namespace_count<=len(data)//8,'LOCRES_IMPOSSIBLE_COUNTS')
 rows=[];names=set();identities=set()
 for _ in range(namespace_count):
  stored=r.number('I');namespace=r.string();require(stored==CityHash.city_hash_64_utf16_to_uint32(namespace),'LOCRES_NAMESPACE_HASH');require(namespace not in names,'LOCRES_DUPLICATE_NAMESPACE');names.add(namespace);count=r.number('I');require(count<=entry_count,'LOCRES_NAMESPACE_COUNT')
  for _ in range(count):
   stored=r.number('I');key=r.string();require(bool(key),'LOCRES_EMPTY_KEY');require(stored==CityHash.city_hash_64_utf16_to_uint32(key),'LOCRES_KEY_HASH');identity=namespace,key;require(identity not in identities,'LOCRES_DUPLICATE_KEY');identities.add(identity);rows.append((identity,r.number('I'),r.number('I')))
 require(r.offset==pool_offset and len(rows)==entry_count,'LOCRES_POOL_OFFSET_COUNT');pool_count=r.number('I');require(pool_count<=entry_count,'LOCRES_POOL_COUNT');targets=[];references=[]
 for _ in range(pool_count):targets.append(r.string());references.append(r.number('I'))
 require(r.offset==len(data),'LOCRES_TRAILING_BYTES');used=collections.Counter(row[2] for row in rows);require(all(i<pool_count for _,_,i in rows),'LOCRES_POOL_INDEX');require(all(used[i]==n for i,n in enumerate(references)),'LOCRES_POOL_REFERENCES')
 return {identity:(crc,targets[index]) for identity,crc,index in rows}
