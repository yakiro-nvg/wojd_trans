"""Cook exact, route-specific runtime bindings without editorial normalization."""
import hashlib,json,pathlib
from pylocres import LocresFile,Namespace,Entry
from catalog_core import read_ndjson
from locres_verify import read_bytes

def load_bindings(path):
    result={}
    for number,row in read_ndjson(path):
        if set(row)!={'namespace','key','source_crc','target'}:
            raise ValueError(f'{path}:{number}: unexpected binding fields')
        ns,key,crc,text=(row[k] for k in ('namespace','key','source_crc','target'))
        if not all(isinstance(s,str) and '\0' not in s for s in (ns,key,text)) or not key:
            raise ValueError('Invalid runtime binding text')
        if type(crc) is not int or not 0<=crc<=0xffffffff:raise ValueError('Invalid source CRC')
        if (ns,key) in result:raise ValueError('Duplicate runtime identity')
        result[ns,key]=(crc,text)
    return result

def compile_bindings(mapping):
    loc=LocresFile();namespaces={}
    for (ns,key),(crc,text) in sorted(mapping.items()):
        if ns not in namespaces:
            namespaces[ns]=Namespace(ns);loc.add(namespaces[ns])
        namespaces[ns].add(Entry(key,text,crc))
    data=loc.to_binary()
    if read_bytes(data)!=mapping:raise ValueError('Locres round-trip changed an identity, CRC or target')
    return data

def build_routes(source,stage):
    manifest=json.loads((source/'manifest.json').read_bytes())
    if manifest['format_version']!=1 or set(manifest['routes'])!={'content','gamedata'}:
        raise ValueError('Expected both resource routes')
    results={}
    allowed={
        'content':'ZhuxianClient/Content/Localization/Game/zh-Hans/Game.locres',
        'gamedata':'ZhuxianClient/gamedata/client/ZCTranslateData/Game/zh-Hans/Game.locres'}
    for name,rule in manifest['routes'].items():
        if rule['input']!=name+'.ndjson' or rule['output']!=allowed[name]:raise ValueError('Unexpected route path')
        path=source/rule['input']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=rule['source_sha256']:raise ValueError('Runtime bindings changed without a manifest update')
        mapping=load_bindings(path)
        if len(mapping)!=rule['entries']:raise ValueError('Runtime binding count differs')
        data=compile_bindings(mapping);sha=hashlib.sha256(data).hexdigest()
        if sha!=rule['output_sha256']:raise ValueError('Cooked locres differs from approved output')
        target=stage/rule['output'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        results[name]=dict(entries=len(mapping),sha256=sha,bytes=len(data))
    return results
