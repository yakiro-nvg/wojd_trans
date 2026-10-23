#!/usr/bin/env python3
"""Offline localization CLI. Run with --help; all translation is reviewed externally."""
import argparse,json,pathlib,sys
from catalog_core import ReuseIndex,approved,apply_review,fallback_sync,fmt_sync,native_sync,native_usage,read_ndjson,render_fmt,review_batches,source_id,write_json
from compile_native_text_catalog import compile_catalog
from translation_quality import validate

def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('index',help='Build an offline source-exact reuse index');p.add_argument('catalogs',nargs='+',type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path)
    p=commands.add_parser('native-sync');p.add_argument('dumps',nargs='+',type=pathlib.Path);p.add_argument('--index',required=True,type=pathlib.Path);p.add_argument('--reviewed',type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path)
    p=commands.add_parser('fallback-sync');p.add_argument('logs',nargs='+',type=pathlib.Path);p.add_argument('--native',required=True,type=pathlib.Path);p.add_argument('--index',required=True,type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path)
    p=commands.add_parser('fmt-sync');p.add_argument('sources',nargs='+',type=pathlib.Path);p.add_argument('--previous',required=True,type=pathlib.Path);p.add_argument('--index',required=True,type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path)
    p=commands.add_parser('fmt-render');p.add_argument('sources',nargs='+',type=pathlib.Path);p.add_argument('--catalog',required=True,type=pathlib.Path);p.add_argument('--source-manifest',required=True,type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path)
    p=commands.add_parser('compile-runtime');p.add_argument('input',type=pathlib.Path);p.add_argument('output',type=pathlib.Path)
    p=commands.add_parser('validate');p.add_argument('catalogs',nargs='+',type=pathlib.Path)
    p=commands.add_parser('review-export');p.add_argument('catalog',type=pathlib.Path);p.add_argument('out',type=pathlib.Path)
    p=commands.add_parser('review-import');p.add_argument('catalog',type=pathlib.Path);p.add_argument('review',type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path)
    p=commands.add_parser('native-usage');p.add_argument('dumps',nargs='+',type=pathlib.Path);p.add_argument('--catalog',required=True,type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path)
    p=commands.add_parser('quality-report');p.add_argument('catalogs',nargs='+',type=pathlib.Path);p.add_argument('--ledger',required=True,type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path);p.add_argument('--sources-out',type=pathlib.Path)
    p=commands.add_parser('quality-mark');p.add_argument('catalogs',nargs='+',type=pathlib.Path);p.add_argument('--ledger',required=True,type=pathlib.Path);p.add_argument('--review',required=True,type=pathlib.Path);p.add_argument('--level',choices=['unreviewed','draft','source_reviewed','client_verified'],required=True);p.add_argument('--reviewer',required=True);p.add_argument('--note',required=True);p.add_argument('--glossary-revision')
    args=parser.parse_args();result={}
    if args.command=='index':
        args.out.parent.mkdir(parents=True,exist_ok=True);result=dict(indexed_rows=ReuseIndex(args.out).build(args.catalogs))
    elif args.command=='native-sync':
        _,result=native_sync(args.dumps,args.out,ReuseIndex(args.index),args.reviewed)
    elif args.command=='fallback-sync':
        _,result=fallback_sync(args.logs,args.native,args.out,ReuseIndex(args.index))
    elif args.command=='fmt-sync':
        _,result=fmt_sync(args.sources,args.out,ReuseIndex(args.index),args.previous)
    elif args.command=='fmt-render':render_fmt(args.sources,args.catalog,args.out,args.source_manifest)
    elif args.command=='compile-runtime':
        translations=approved(args.input);records=[];seen=set()
        for number,row in read_ndjson(args.input):
            source=row['source'];state=row.get('status','translated' if row.get('translated') else 'missing')
            if source in seen:raise ValueError(f'{args.input}:{number}: duplicate source decision')
            seen.add(source)
            if row.get('translation_source_sha256',source_id(source))!=source_id(source) and row.get('translated'):state='missing'
            if state=='translated':
                if source not in translations:raise ValueError(f'{args.input}:{number}: invalid translation')
                records.append(dict(field='NativeString',source=source,target=translations[source]))
            elif state=='ignore':records.append(dict(field='NativeIgnore',source=source,target=''))
            elif state not in ['missing','pending']:raise ValueError(f'{args.input}:{number}: invalid decision status')
        binary=compile_catalog(dict(format_version=2,capture_fields=['NativeString','NativeIgnore'],translations=records))
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(binary);result=dict(translations=len(translations),decisions=len(records),bytes=len(binary))
    elif args.command=='validate':
        checked=0
        for path in args.catalogs:
            identities={}
            for number,row in read_ndjson(path):
                source=row.get('source');target=row.get('translated')
                if not isinstance(source,str):raise ValueError(f'{path}:{number}: missing source')
                state=row.get('status','translated' if target else 'missing')
                if state not in ['translated','missing','dated','ignore']:raise ValueError(f'{path}:{number}: invalid status')
                if row.get('source_sha256',source_id(source))!=source_id(source):raise ValueError(f'{path}:{number}: current source hash mismatch')
                if state=='translated' and row.get('translation_source_sha256',source_id(source))!=source_id(source):raise ValueError(f'{path}:{number}: dated translation binding')
                if state in ['ignore','dated']:continue
                if not target:continue
                problems=validate(source,target)
                identity=(row.get('namespace',''),row.get('key',source))
                if identity in identities and identities[identity]!=(source,target):problems.append('conflicting_identity')
                identities[identity]=source,target
                if problems:raise ValueError(f'{path}:{number}: {problems}')
                checked+=1
        result=dict(validated_translations=checked)
    elif args.command=='review-export':result=dict(batches=review_batches(args.catalog,args.out))
    elif args.command=='review-import':result=dict(imported=apply_review(args.catalog,args.review,args.out))
    elif args.command=='native-usage':result=native_usage(args.catalog,args.dumps,args.out)
    elif args.command=='quality-report':
        from quality_tracking import report
        result=report(args.catalogs,args.ledger,args.sources_out);write_json(args.out,result)
    elif args.command=='quality-mark':
        from quality_tracking import mark
        result=mark(args.ledger,args.review,args.catalogs,args.level,args.reviewer,args.note,args.glossary_revision)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError) as error:print(str(error),file=sys.stderr);raise SystemExit(1)
