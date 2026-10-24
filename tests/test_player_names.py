"""Deterministic public name readings and scoped conversion font."""
import hashlib,importlib.util,json,pathlib,struct,tempfile,unittest
from fontTools.ttLib import TTFont
ROOT=pathlib.Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
class PlayerNamesTests(unittest.TestCase):
    def test_current_nameboard_route_changes_only_two_font_values(self):
        proof=json.loads((ROOT/'resources/player-name-ui.sources.json').read_bytes())
        raw=(ROOT/'assets/vi-base'/proof['path']).read_bytes()
        original=raw.replace(proof['name_font'].encode(),proof['source_font'].encode())
        self.assertEqual(len(original),proof['source_bytes'])
        self.assertEqual(hashlib.sha256(original).hexdigest(),proof['source_sha256'])
        def nodes(value):
            if isinstance(value,dict):
                yield value
                for child in value.values():yield from nodes(child)
            elif isinstance(value,list):
                for child in value:yield from nodes(child)
        data=json.loads(raw)
        self.assertEqual(data['SourceBlueprint'],'/Game/UI/UI_ActorAttached/WB_TargetInfo3D')
        changed=[n for n in nodes(data) if n.get('Font')==proof['name_font']]
        self.assertEqual(sorted(n['Name'] for n in changed),proof['widgets'])
        self.assertTrue(all(n['Type']=='TextBlock' for n in changed))
        self.assertEqual(raw.count(proof['name_font'].encode()),2)
    def test_generated_table_matches_public_source(self):
        raw=(ROOT/'resources/player-name-readings.ndjson').read_text(encoding='utf-8')
        self.assertEqual(module('compile_player_name_readings').compile_readings(raw),(ROOT/'native/src/player_name_readings.h').read_bytes())
    def test_readings_reject_duplicate_characters_and_non_reading_payloads(self):
        compile=module('compile_player_name_readings').compile_readings
        a=json.dumps({'codepoint':0x5f20,'reading':'Trương'},ensure_ascii=False)
        for raw in (a+'\n'+a,json.dumps({'codepoint':0x5f20,'reading':'<a action="send">'}),json.dumps({'codepoint':65,'reading':'A'})):
            with self.assertRaises(ValueError):compile(raw)
    def test_conversion_font_reproduces_and_preserves_existing_vietnamese(self):
        build=module('build_player_name_font')
        with tempfile.TemporaryDirectory() as temp:
            output=pathlib.Path(temp)/'names.ttf';build.build(build.BASE/'FZShengSKSJW_Zhong.ufont',build.READINGS,output)
            self.assertEqual(output.read_bytes(),(build.BASE/'WOJD_HV_PlayerName.ufont').read_bytes())
            with TTFont(build.BASE/'FZShengSKSJW_Zhong.ufont') as plain, TTFont(output) as converted:
                a=plain.getBestCmap();b=converted.getBestCmap()
                for cp,glyph in a.items():
                    self.assertEqual(b[cp],glyph)
                original=plain.getGlyphOrder()
                self.assertEqual(converted.getGlyphOrder()[:len(original)],original)
                for glyph in original:
                    self.assertEqual(plain['hmtx'][glyph],converted['hmtx'][glyph])
                    self.assertEqual(plain['glyf'][glyph].compile(plain['glyf']),converted['glyf'][glyph].compile(converted['glyf']))
                readings={r['codepoint']:r['reading'] for r in (json.loads(l) for l in build.READINGS.read_text(encoding='utf-8').splitlines())}
                self.assertEqual(set(b),set(a)|set(readings))
                self.assertEqual(len(converted.getGlyphOrder()),len(original)+len(readings))
                for table in converted['cmap'].tables:
                    if table.isUnicode() and table.format==4:
                        self.assertEqual(set(table.cmap),{cp for cp in b if cp<0xffff})
                for cp,word in readings.items():
                    glyph=converted['glyf'][b[cp]]
                    self.assertTrue(glyph.isComposite())
                    self.assertEqual([c.glyphName for c in glyph.components],[a[ord(c)] for c in word])
                    advance=0
                    for component in glyph.components:
                        self.assertEqual((component.x,component.y),(advance,0))
                        advance+=plain['hmtx'][component.glyphName][0]
                    self.assertEqual(converted['hmtx'][b[cp]],(advance+plain['hmtx'][a[32]][0],0))
                self.assertEqual(readings[ord('吃')],'Cật')
                self.assertEqual(readings[ord('饭')],'Phạn')
                self.assertEqual(readings[0x884c],'Hành')
                self.assertEqual(readings[0x91cd],'Trọng')
    def test_readings_are_bound_to_mvh_source_without_xf_fallback(self):
        proof=json.loads((ROOT/'resources/player-name-readings.source.json').read_bytes())
        self.assertIn('vi-lim-mvh',proof['source_path'])
        self.assertEqual(hashlib.sha256((ROOT/proof['mapping_snapshot']).read_bytes()).hexdigest(),proof['mapping_snapshot_sha256'])
        self.assertNotIn('vendored_source',proof)
        rows=[json.loads(l) for l in (ROOT/'resources/player-name-readings.ndjson').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(rows),proof['readings'])
        self.assertGreater(proof['expanded_dictionary']['readings'],proof['mvh_readings'])
        self.assertEqual(module('compile_player_name_dictionary').build()[0],(ROOT/'resources/player-name-readings.ndjson').read_bytes())
    def test_buff_source_changes_only_its_name_field_and_retains_original_text(self):
        proof=json.loads((ROOT/'resources/player-name-buff-ui.source.json').read_bytes())
        path=ROOT/'assets/vi-base'/proof['path']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),proof['header_sha256'])
        body=bytearray(path.with_suffix('.uexp').read_bytes())
        self.assertEqual(hashlib.sha256(body).hexdigest(),proof['payload_sha256'])
        self.assertEqual([row['widget'] for row in proof['changes']],['Txt_BuffSource_name'])
        for row in proof['changes']:
            struct.pack_into('<i',body,row['property_offset'],proof['source_font_ref'])
        self.assertEqual(hashlib.sha256(body).hexdigest(),proof['source_payload_sha256'])
    def test_scoped_font_keeps_original_chinese_and_emoji_fallbacks(self):
        path=module('build_player_name_font').BASE/'WOJD_HV_PlayerName_Font.uexp'
        body=path.read_bytes()
        self.assertEqual([struct.unpack_from('<i',body,at+53)[0] for at in (287,389,683,4805)],[-4,-4,-6,-5])
if __name__=='__main__':unittest.main()
