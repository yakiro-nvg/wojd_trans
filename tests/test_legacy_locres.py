import collections,json,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from catalog_core import ReuseIndex,write_ndjson
from compile_locres_bindings import compile_bindings
from legacy_locres import collect,publish,overlay_legacy,overlay_font,collection_proof,merge_legacy
from locres_verify import read_bytes

class LegacyTests(unittest.TestCase):
    def test_native_source_overlap_is_reused_at_observed_id_and_both_routes(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as temp:
            root=pathlib.Path(temp);catalog=root/'vi.native.ndjson'
            write_ndjson(catalog,[dict(source='读取源',translated='Nguồn Đọc',status='translated')])
            log=root/'game.log';log.write_text('[2026.10.25-00.00.00:000]LogTextLocalizationManager: (Namespace:Skill, Key:actual-id, Source:读取源), but it did not exist.\n',encoding='utf-8')
            index=ReuseIndex(root/'reuse.sqlite');index.build([catalog])
            try:rows,conflicts,report=collect([log],index)
            finally:index.db.close()
            self.assertFalse(conflicts);self.assertEqual(rows[0]['key'],'actual-id');self.assertEqual(rows[0]['translated'],'Nguồn Đọc')
            self.assertFalse(report['native_source_filter']);self.assertEqual(report['provider_requests'],0)
            self.assertIsNone(collection_proof(log))
            from catalog_core import digest
            (root/'collection.json').write_text(json.dumps(dict(status='PASS',profile='legacy',dll_injection=False,sha256=digest(log),bytes=log.stat().st_size,install_transaction='fixture',source_revision='fixture')))
            self.assertEqual(collection_proof(log)['source_revision'],'fixture')
            publish(rows,root/'overrides')
            paths=['ZhuxianClient/Content/Localization/Game/zh-Hans/Game.locres','ZhuxianClient/gamedata/client/ZCTranslateData/Game/zh-Hans/Game.locres']
            for path in paths:
                p=root/path;p.parent.mkdir(parents=True);p.write_bytes(compile_bindings({('','old'):(123,'Bố Cục')}))
            overlay_legacy(root,root/'overrides')
            for path in paths:
                self.assertEqual(read_bytes((root/path).read_bytes()),{('','old'):(123,'Bố Cục'),('Skill','actual-id'):(rows[0]['source_crc'],'Nguồn Đọc')})
            base={('','widget'):(123,'Nhãn ngắn'),('Skill','id'):(456,'Bản cũ')}
            with self.assertRaisesRegex(ValueError,'protected baseline'):merge_legacy(base,{('Skill','id'):(789,'Bản mới')})
            merged,counts=merge_legacy(base,{('','widget'):(123,'Nhãn quá dài'),('Skill','id'):(789,'Bản mới')},['Skill'])
            self.assertEqual(merged[('','widget')],base[('','widget')]);self.assertEqual(merged[('Skill','id')],(789,'Bản mới'))
    def test_conflicting_ids_and_unknown_sources_are_not_guessed(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as temp:
            root=pathlib.Path(temp);index=ReuseIndex(root/'reuse.sqlite');index.build([])
            log=root/'game.log';log.write_text(''.join('[2026.10.25-00.00.00:000]LogTextLocalizationManager: (Namespace:N, Key:'+key+', Source:'+source+'), but it did not exist.\n' for key,source in [('same','甲'),('same','乙'),('unknown','尚未翻译')]),encoding='utf-8')
            try:rows,conflicts,report=collect([log],index)
            finally:index.db.close()
            self.assertEqual(len(conflicts),2);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'missing')
            publish(rows,root/'out');self.assertEqual((root/'out/overrides.ndjson').read_bytes(),b'')
            self.assertEqual(report['inferred_locres_ids'],0)
    def test_source_newlines_escapes_markup_and_translation_hash_are_exact(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as temp:
            root=pathlib.Path(temp);source=' 第一行\r\n第二行\\n%d <a x="5">甲</> ';target=' Dòng Một\r\nDòng Hai\\n%d <a x="5">Giáp</> '
            catalog=root/'translations.ndjson';write_ndjson(catalog,[dict(source=source,translated=target)])
            log=root/'game.log';log.write_bytes(('[2026.10.25-00.00.00:000]LogTextLocalizationManager: (Namespace:N, Key:k), but the source string hash does not match - the source string ('+source+') will be used.\r\n').encode('utf-8'))
            index=ReuseIndex(root/'reuse.sqlite');index.build([catalog])
            try:rows,conflicts,_=collect([log],index)
            finally:index.db.close()
            self.assertEqual(rows[0]['source'],source);self.assertEqual(rows[0]['translated'],target)
            publish(rows,root/'out');rows[0]['translated']='Bị sửa'
            before=(root/'out/overrides.ndjson').read_bytes()
            with self.assertRaisesRegex(ValueError,'hash changed'):publish(rows,root/'out')
            self.assertEqual((root/'out/overrides.ndjson').read_bytes(),before)
    def test_legacy_font_reuses_built_font_and_preserves_other_assets(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as temp:
            root=pathlib.Path(temp);folder=root/'ZhuxianClient/Content/UI/UI_Texture/UI_ziti';folder.mkdir(parents=True)
            (folder/'FZShengSKSJW_Zhong.ufont').write_bytes(b'main');(folder/'WOJD_HV_PlayerName.ufont').write_bytes(b'converted')
            (folder/'alternate.ufont').write_bytes(b'main');(folder/'unknown.ufont').write_bytes(b'other');(folder/'widget.uasset').write_bytes(b'layout')
            report=overlay_font(root,root)
            self.assertEqual(len(report['files']),2);self.assertEqual((folder/'alternate.ufont').read_bytes(),b'converted')
            self.assertEqual((folder/'unknown.ufont').read_bytes(),b'other');self.assertEqual((folder/'widget.uasset').read_bytes(),b'layout')
if __name__=='__main__':unittest.main()
