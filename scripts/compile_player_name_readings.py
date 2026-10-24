"""Reproduce the local name-reading table; no game, font compiler or network."""
import argparse,json,pathlib,unicodedata
ROOT=pathlib.Path(__file__).resolve().parents[1]
def compile_readings(raw):
    blob=bytearray();items=[];previous=0
    for line in raw.splitlines():
        if not line.strip():continue
        row=json.loads(line)
        if set(row)!={'codepoint','reading'}:raise ValueError('Unexpected reading fields')
        cp=row['codepoint'];word=row['reading']
        if type(cp) is not int or cp<=previous or not (0x3400<=cp<=0x9fff or 0xf900<=cp<=0xfaff or 0x20000<=cp<=0x323af):raise ValueError('Invalid or unsorted Han codepoint')
        if not isinstance(word,str) or not 1<=len(word)<=12 or unicodedata.normalize('NFC',word)!=word or any(not unicodedata.name(c,'').startswith('LATIN ') for c in word):raise ValueError('Invalid Latin reading')
        previous=cp;items.append((cp,len(blob)));blob.extend(word.encode('utf-8')+b'\0')
    if not items:raise ValueError('Empty name-reading table')
    header='/* Generated from resources/player-name-readings.ndjson. Readings recovered\n   from MVH and credited Han-Viet dictionary supplements; no player/account data. */\n#ifndef WOJD_PLAYER_NAME_READINGS_H\n#define WOJD_PLAYER_NAME_READINGS_H\ntypedef struct PnReading {unsigned codepoint,offset;} PnReading;\nstatic const PnReading pn_readings[]={\n'
    header+=''.join('{%u,%u},\n'%x for x in items)+'};\nstatic const unsigned char pn_text[]={\n'
    header+=''.join(','.join(str(x) for x in blob[i:i+32])+',\n' for i in range(0,len(blob),32))+'};\n#endif\n'
    return header.encode('ascii')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    result=compile_readings((ROOT/'resources/player-name-readings.ndjson').read_text(encoding='utf-8'))
    target=ROOT/'native/src/player_name_readings.h'
    if args.check:
        if target.read_bytes()!=result:raise ValueError('Generated player-name table is stale')
    else:target.write_bytes(result)
    print('PASS local name-reading table matches source')
if __name__=='__main__':main()
