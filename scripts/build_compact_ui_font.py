"""Build a globally smaller UI face and its two conversion derivatives.

Only the font's em scale and family metadata change. Outlines, advances,
kerning, hinting, Vietnamese coverage and Han-Viet readings are preserved.
No font from third-party player PAKs is used.
"""
import hashlib,pathlib
from fontTools.ttLib import TTFont
from build_player_name_font import build,READINGS,LEGACY_OVERRIDES
import json

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/'resources/fonts/LeagueSpartan-UI-source.ttf'
SOURCE_SHA256='9f9e6308a70b609b3744fd72ce5ca310fc0ff1fd0e6d6606b31be3e6b56d777e'
BASE=ROOT/'assets/vi-base/ZhuxianClient/Content/UI/UI_Texture/UI_ziti'
NEW_EM=2286

def compact(source,output):
    if hashlib.sha256(pathlib.Path(source).read_bytes()).hexdigest()!=SOURCE_SHA256:
        raise ValueError('UI source font differs from the reviewed baseline')
    font=TTFont(source,recalcTimestamp=False)
    if font['head'].unitsPerEm!=2000:raise ValueError('Unexpected baseline em scale')
    font['head'].unitsPerEm=NEW_EM
    for record in font['name'].names:
        if record.nameID in (1,3,4,6,16):
            family='WOJD UI Compact'
            record.string=(family.replace(' ','') if record.nameID==6 else family).encode(record.getEncoding())
    font.save(output);font.close()

def main():
    primary=BASE/'FZShengSKSJW_Zhong.ufont'
    compact(SOURCE,primary);data=primary.read_bytes()
    # These 24 existing UI aliases intentionally share one Latin face.
    aliases=[p for p in BASE.glob('*.ufont') if p.name!='WOJD_HV_PlayerName.ufont']
    if len(aliases)!=24:raise ValueError('Unexpected UI font alias set')
    for path in aliases:path.write_bytes(data)
    build(primary,READINGS,BASE/'WOJD_HV_PlayerName.ufont')
    build(primary,READINGS,ROOT/'assets/vi-legacy/WOJD_Legacy_Convert.ufont',
          json.loads(LEGACY_OVERRIDES.read_bytes()),'WOJD Legacy Convert')
    print('Built 24 compact UI aliases and both conversion faces; scale=2000/2286')

if __name__=='__main__':main()
