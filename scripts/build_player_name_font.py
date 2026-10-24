"""Compose Han-Viet name glyphs entirely from the main UI font's outlines.

The reading table supplies pronunciation only. No legacy font file is opened
or embedded. Requires fonttools for development, not for player ZIPs.
"""
import argparse,json,pathlib
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from fontTools.pens.ttGlyphPen import TTGlyphPen
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'assets/vi-base/ZhuxianClient/Content/UI/UI_Texture/UI_ziti'
READINGS=ROOT/'resources/player-name-readings.ndjson'
def build(base,readings,output):
    font=TTFont(base,recalcTimestamp=False);cmap=font.getBestCmap();wide=dict(cmap)
    rows=[json.loads(line) for line in pathlib.Path(readings).read_text(encoding='utf-8').splitlines()]
    base_order=list(font.getGlyphOrder());glyphset=font.getGlyphSet()
    for row in rows:
        cp,word=row['codepoint'],row['reading']
        if cp in cmap:raise ValueError('Reading would replace an existing UI glyph')
        missing=[c for c in word if ord(c) not in cmap]
        if missing:raise ValueError('Reading contains letters absent from main UI font: '+repr(missing))
        name='wojdHV%X'%cp;offset=0;pen=TTGlyphPen(glyphset)
        for character in word:
            glyph=cmap[ord(character)]
            pen.addComponent(glyph,(1,0,0,1,offset,0));offset+=font['hmtx'][glyph][0]
        font['glyf'][name]=pen.glyph()
        font['hmtx'][name]=(offset+font['hmtx'][cmap[32]][0],0);wide[cp]=name
    # Preserve original glyph IDs; ordered additions keep full BMP format-4
    # charmaps compact while format-12 also covers supplementary characters.
    font.setGlyphOrder(base_order+[wide[row['codepoint']] for row in sorted(rows,key=lambda row:row['codepoint'])])
    for table in font['cmap'].tables:
        if table.isUnicode() and table.format==4:table.cmap={cp:g for cp,g in wide.items() if cp<0xffff}
    for platform,encoding in ((3,10),(0,4)):
        table=CmapSubtable.newSubtable(12);table.platformID=platform;table.platEncID=encoding;table.language=0;table.cmap=wide
        font['cmap'].tables=[x for x in font['cmap'].tables if (x.platformID,x.platEncID)!=(platform,encoding)]+[table]
    for record in font['name'].names:
        if record.nameID in (1,3,4,6,16,17):
            value='WOJD HV Player Name' if record.nameID!=6 else 'WOJDHVPlayerName'
            if record.nameID==17:value='Regular'
            record.string=value.encode(record.getEncoding(),errors='strict')
    font.save(output);font.close()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=pathlib.Path,required=True);args=p.parse_args()
    build(BASE/'FZShengSKSJW_Zhong.ufont',READINGS,args.output)
    print('Built isolated name font using only main UI glyphs and the local reading table')
if __name__=='__main__':main()
