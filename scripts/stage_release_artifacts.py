"""Select and authenticate player release files from an Actions artifact tree."""
import argparse,hashlib,json,pathlib,shutil

def stage_release(source,output,revision):
    selected={}
    for name in ['VI_PATCH.zip','checksums.txt','vi-build.json']:
        found=[p for p in source.rglob(name) if p.is_file()]
        if len(found)!=1:raise ValueError(f'Expected exactly one downloaded {name}')
        selected[name]=found[0]
    build=json.loads(selected['vi-build.json'].read_bytes())
    sha=hashlib.sha256(selected['VI_PATCH.zip'].read_bytes()).hexdigest()
    checksums=selected['checksums.txt'].read_text(encoding='ascii').splitlines()
    if build['source_revision']!=revision or set(build['variants'])!={'base'}:raise ValueError('Artifact belongs to a different source revision or lineup')
    if build['variants']['base']['file']!='VI_PATCH.zip' or build['variants']['base']['sha256']!=sha:raise ValueError('Build report does not authenticate the player ZIP')
    if len(checksums)!=1 or checksums[0].split()!=[sha,'VI_PATCH.zip']:raise ValueError('Release checksum differs')
    output.mkdir(parents=True,exist_ok=True)
    for name,path in selected.items():shutil.copyfile(path,output/name)
    return sha

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);p.add_argument('--revision',required=True);args=p.parse_args()
    print(stage_release(args.input,args.output,args.revision))
