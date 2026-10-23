import json,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from catalog_core import ReuseIndex,apply_review,fallback_sync,fmt_sync,native_sources,native_sync,native_usage,read_ndjson,render_fmt,review_batches,source_id,write_ndjson
from translation_quality import validate,visible_text

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'work');self.root=pathlib.Path(self.temp.name)
        self.legacy=self.root/'legacy.ndjson';write_ndjson(self.legacy,[dict(namespace='A.txt',key='1',source='甲%d',translated='Giáp%d'),dict(source='旧文',translated='Văn cũ')])
        self.index=ReuseIndex(self.root/'reuse.sqlite');self.index.build([self.legacy])
    def tearDown(self):self.index.db.close();self.temp.cleanup()
    def test_native_exact_reuse_and_preserved_ignore(self):
        dump=self.root/'dump.ndjson';write_ndjson(dump,[dict(route='native_data_decoder_assignment',source=s) for s in ['甲%d','甲%s','配置.xlsx','旧文']])
        reviewed=self.root/'reviewed.ndjson';write_ndjson(reviewed,[dict(source='旧文',translated=None,status='ignore',reason='internal label')])
        rows,report=native_sync([dump],self.root/'native.ndjson',self.index,reviewed);rows={r['source']:r for r in rows}
        self.assertEqual(rows['甲%d']['translated'],'Giáp%d');self.assertEqual(rows['甲%s']['status'],'missing')
        self.assertEqual(rows['配置.xlsx']['status'],'ignore');self.assertEqual(rows['旧文']['status'],'ignore')
    def test_fmt_updated_keys_source_guard_and_byte_preservation(self):
        source=self.root/'source';source.mkdir();raw=b'\xef\xbb\xbf'+('// comment = untouched\r\n1 = 甲%d\r\n2= 新文\r\n3 = 未译\r\n').encode()
        (source/'A.txt').write_bytes(raw);old=self.root/'old.ndjson'
        write_ndjson(old,[dict(namespace='A.txt',key='1',source='甲%d',translated='Giáp%d'),dict(namespace='A.txt',key='2',source='旧文',translated='Văn cũ')])
        catalog=self.root/'fmt.ndjson';rows,report=fmt_sync([source],catalog,self.index,old)
        self.assertEqual(rows[1]['status'],'dated');self.assertIsNone(rows[1]['translated'])
        rows,_=fmt_sync([source],catalog,self.index,catalog)
        self.assertEqual(rows[1]['status'],'dated');self.assertEqual(rows[1]['previous_source'],'旧文')
        out=self.root/'rendered';render_fmt([source],catalog,out,catalog.with_suffix('.sources.json'))
        self.assertEqual((out/'A.txt').read_bytes(),raw.replace('甲%d'.encode(),'Giáp%d'.encode()))
        (source/'A.txt').write_bytes(raw+b'4 = update\r\n')
        with self.assertRaisesRegex(ValueError,'source bytes changed'):render_fmt([source],catalog,out,catalog.with_suffix('.sources.json'))
    def test_review_source_and_structure_are_required(self):
        catalog=self.root/'catalog.ndjson';write_ndjson(catalog,[dict(source='甲%d',translated=None,status='missing')])
        review=self.root/'review.ndjson';out=self.root/'out.ndjson'
        write_ndjson(review,[dict(source='甲%d',source_sha256=source_id('甲%d'),translated='Giáp%s')])
        with self.assertRaises(ValueError):apply_review(catalog,review,out)
        self.assertFalse(out.exists())
        write_ndjson(review,[dict(source='甲%d',source_sha256=source_id('甲%d'),status='ignore',reason='developer string')])
        apply_review(catalog,review,out);self.assertEqual(next(read_ndjson(out))[1]['status'],'ignore')
    def test_logic_numbers_and_escape_forms(self):
        self.assertTrue(validate('<a taskID="5" text="甲"></>','<a taskID="6" text="Giáp"></>'))
        self.assertTrue(validate('甲\\n乙','Giáp\nẤt'));self.assertTrue(validate('5%伤害','6% sát thương'))

    def test_embedded_resource_paths_image_payloads_and_text_wrappers(self):
        source="@p(Texture2D'/Game/画册.画册',f)故事"
        target="@p(Texture2D'/Game/画册.画册',f)Câu chuyện"
        self.assertFalse(validate(source,target));self.assertNotIn('画册',visible_text(target))
        self.assertTrue(validate(source,target.replace('Texture2D','Texture 2 D')))
        self.assertTrue(validate('点击(@@Image)yindiao1|24|24(/Image)','Nhấn (@@Image)yindiao 1|24|24(/Image)'))
        self.assertFalse(validate('@t(cBlue@@甲||乙)','@t(cBlue@@Giáp||Ất)'))
        self.assertTrue(validate('@t(cBlue@@甲||乙)','@t(cBlue@@Giáp - Ất)'))
        self.assertTrue(validate('██之道','Đạo █'))
        self.assertTrue(validate('【徒名】的师父','Sư phụ của 【Tên đồ đệ】'))
        self.assertTrue(validate('biaoqing_sj_taimei01_morph表情','Biểu cảm biaoqing_sj_taimei 01_morph'))

    def test_resource_only_directives_are_ignored_but_embedded_prose_is_not(self):
        source="@p(Texture2D'/Game/画册.画册',f)"
        dump=self.root/'dump.ndjson'
        write_ndjson(dump,[dict(route='native_data_decoder_assignment',source=source),dict(route='native_data_decoder_assignment',source=source+'故事')])
        rows,_=native_sync([dump],self.root/'native.ndjson',self.index)
        self.assertEqual([r['status'] for r in rows],['ignore','missing'])

    def test_literal_reuse_does_not_require_matching_namespace_key_or_route(self):
        source=self.root/'source';source.mkdir();(source/'OtherRoute.txt').write_text('9000=甲%d\n',encoding='utf-8')
        previous=self.root/'previous.ndjson';write_ndjson(previous,[])
        rows,_=fmt_sync([source],self.root/'fmt.ndjson',self.index,previous)
        self.assertEqual(rows[0]['translated'],'Giáp%d')
        self.assertEqual((rows[0]['namespace'],rows[0]['key']),('OtherRoute.txt','9000'))

    def test_unobserved_is_retained_and_reported_without_deletion(self):
        dump=self.root/'dump.ndjson';write_ndjson(dump,[dict(route='native_data_decoder_assignment',source='甲%d')])
        previous=self.root/'previous.ndjson'
        write_ndjson(previous,[dict(source='旧文',source_sha256=source_id('旧文'),translated='Văn cũ',status='translated')])
        catalog=self.root/'native.ndjson';rows,report=native_sync([dump],catalog,self.index,previous)
        retained=next(r for r in rows if r['source']=='旧文')
        self.assertEqual(retained['translated'],'Văn cũ');self.assertFalse(retained['observed_in_inputs'])
        before=catalog.read_bytes();usage=native_usage(catalog,[dump],self.root/'usage.json')
        self.assertEqual(usage['not_observed'],1);self.assertEqual(catalog.read_bytes(),before)

    def test_fallback_uses_fresh_observed_ids_and_old_translations_only(self):
        native=self.root/'native.ndjson';write_ndjson(native,[dict(source='甲%d',translated='Giáp%d',status='translated',observed_in_inputs=True)])
        output=self.root/'residual.ndjson';write_ndjson(output,[dict(namespace='old',key='stale-id',source='旧文',translated='Văn cũ',status='translated')])
        log=self.root/'Game.log'
        events=[('new-id','旧文'),('covered','甲%d'),('conflict','旧文'),('conflict','新文')]
        log.write_text(''.join(f'[2026.10.18-01.02.03:004] LogTextLocalizationManager: Warning: (Namespace:Now, Key:{key}, Source:{source}), but it did not exist.\n' for key,source in events),encoding='utf-8')
        rows,report=fallback_sync([log],native,output,self.index)
        self.assertEqual([(r['namespace'],r['key']) for r in rows],[('Now','covered'),('Now','new-id')])
        self.assertEqual(rows[0]['translated'],'Giáp%d')
        self.assertEqual(rows[1]['translated'],'Văn cũ');self.assertEqual(report['conflicts'],2)

    def test_fallback_preserves_cn_source_overlap_at_independent_ftext_identities(self):
        native=self.root/'native.ndjson'
        states=[dict(source='甲%d',translated='Giáp%d',status='translated'),
            dict(source='旧文',translated=None,status='missing'),
            dict(source='内部标签',translated=None,status='ignore',reason='internal'),
            dict(source='校验%d',translated='Sai%s',status='translated',review_required=True)]
        write_ndjson(native,[dict(**row,observed_in_inputs=True) for row in states])
        log=self.root/'Game.log';observed=[row['source'] for row in states]+['其他来源']
        log.write_text(''.join(f'[2026.10.18-01.02.03:004] LogTextLocalizationManager: Warning: (Namespace:Now, Key:{key}, Source:{source}), but it did not exist.\n' for key,source in enumerate(observed)),encoding='utf-8')
        rows,report=fallback_sync([log],native,self.root/'residual.ndjson',self.index)
        self.assertEqual({r['source'] for r in rows},set(observed))
        self.assertEqual(report['counts']['retained_native_source_overlap_events'],4)
        self.assertEqual(report['native_source_inventory']['unique_sources'],4)

    def test_native_origin_inventory_distinguishes_escaped_newline_and_old_unobserved(self):
        path=self.root/'native.ndjson'
        write_ndjson(path,[dict(source='甲\\n乙',status='missing',observed_in_inputs=True),dict(source='旧文',status='translated',observed_in_inputs=False)])
        self.assertEqual(native_sources(path),{'甲\\n乙'})
        self.assertNotIn('甲\n乙',native_sources(path))
        with self.assertRaisesRegex(ValueError,'native provenance missing'):native_sources(self.legacy)

    def test_fallback_excludes_recorded_reader_outputs_with_remaining_cjk(self):
        native=self.root/'dump.ndjson';write_ndjson(native,[dict(route='native_data_decoder_assignment',source='甲%d',target='Giáp%d {甲}',status='translated')])
        log=self.root/'Game.log';log.write_text('[2026.10.18-01.02.03:004] LogTextLocalizationManager: Warning: (Namespace:Now, Key:fresh, Source:Giáp%d {甲}), but it did not exist.\n',encoding='utf-8')
        rows,report=fallback_sync([log],native,self.root/'residual.ndjson',self.index)
        self.assertEqual(rows,[]);self.assertEqual(report['counts']['native_reader_output_miss_events'],1)

    def test_capture_only_tooltip_target_is_not_a_substituted_output(self):
        native=self.root/'dump.ndjson'
        write_ndjson(native,[dict(route='native_tooltip_fstring_observation',source='甲',target='Văn 甲',status='translated',capture_only=True)])
        log=self.root/'Game.log'
        log.write_text('[2026.10.18-01.02.03:004] LogTextLocalizationManager: Warning: (Namespace:UI, Key:widget, Source:Văn 甲), but it did not exist.\n',encoding='utf-8')
        rows,report=fallback_sync([log],native,self.root/'residual.ndjson',self.index)
        self.assertEqual([r['source'] for r in rows],['Văn 甲'])
        self.assertNotIn('native_reader_output_miss_events',report['counts'])

    def test_native_translation_review_survives_sync_and_exports_original_context(self):
        dump=self.root/'dump.ndjson';write_ndjson(dump,[dict(route='native_data_decoder_assignment',source='旧文')])
        catalog=self.root/'native.ndjson';write_ndjson(catalog,[dict(source='旧文',translated='Văn 旧',status='translated',review_required=True,review_reason='visible_cjk')])
        rows,_=native_sync([dump],catalog,self.index,catalog)
        self.assertTrue(rows[0]['review_required']);self.assertEqual(rows[0]['review_reason'],'visible_cjk')
        batches=self.root/'review';review_batches(catalog,batches);review=batches/'0000.ndjson'
        row=next(read_ndjson(review))[1];self.assertEqual(row['current_translation'],'Văn 旧')
        row['translated']='Văn cũ';write_ndjson(review,[row]);apply_review(catalog,review,catalog)
        self.assertFalse(next(read_ndjson(catalog))[1]['review_required'])

if __name__=='__main__':unittest.main()
