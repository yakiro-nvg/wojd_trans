import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from translation_quality import validate

class EscapeFormTests(unittest.TestCase):
    def test_author_template_rejects_added_escape_layer(self):
        source=r'{0}\n作者：{1}'
        self.assertFalse(validate(source,r'{0}\nTác giả：{1}'))
        self.assertIn('newline_or_escape_form_changed',validate(source,r'{0}\\nTác giả：{1}'))

    def test_escape_depth_is_preserved_for_newlines_and_tabs(self):
        for source,target in [(r'甲\\n乙',r'Giáp\nẤt'),
                              (r'甲\t乙',r'Giáp\\tẤt'),
                              (r'甲\r\n乙',r'Giáp\\r\\nẤt'),
                              (r'甲\\\n乙',r'Giáp\\nẤt')]:
            with self.subTest(source=source,target=target):
                self.assertIn('newline_or_escape_form_changed',validate(source,target))

    def test_matching_escape_forms_and_actual_newlines_remain_valid(self):
        for source,target in [(r'甲\\n乙',r'Giáp\\nẤt'),
                              (r'甲\r\n乙',r'Giáp\r\nẤt'),
                              ('甲\r\n乙','Giáp\r\nẤt'),
                              ('甲\t乙','Giáp\tẤt')]:
            with self.subTest(source=source,target=target):
                self.assertFalse(validate(source,target))
        self.assertIn('newline_or_escape_form_changed',validate(r'甲\n乙','Giáp\nẤt'))


# Full frozen source/target regression pairs, never semantic approvals.
import hashlib
import translation_quality as quality
REASON = 'literal_backslash_run_sequence_changed'
FROZEN_REJECTED_FAULTS = [{'ordinal': 76, 'source': '击败逆命寂灭墟·动态后卿魔像\\1', 'translated': 'Đánh bại Hậu Khanh Ma Tướng tại Nghịch Mệnh Tịch Diệt Khư·Động\\\\1', 'source_sha256': 'd5aa5a473cdef99f98b5c0c6eebe43e90176cfb729212e298385bc3b0888a23c', 'translation_sha256': 'c7b3dc0bb6694d1ed4504584d3f88c1a79f2ffd49e23bb5ef139f3c0a990cd60', 'source_utf8_hex': 'e587bbe8b4a5e98086e591bde5af82e781ade5a29fc2b7e58aa8e68081e5908ee58dbfe9ad94e5838f5c31', 'translated_utf8_hex': 'c490c3a16e682062e1baa1692048e1baad75204b68616e68204d612054c6b0e1bb9b6e672074e1baa169204e6768e1bb8b6368204de1bb876e682054e1bb8b6368204469e1bb8774204b68c6b0c2b7c490e1bb996e675c5c31', 'source_utf8_byte_length': 43, 'translated_utf8_byte_length': 89}, {'ordinal': 77, 'source': '击败逆命寂灭墟·噩梦后卿魔像\\1', 'translated': 'Đánh bại Hậu Khanh Ma Tướng tại Nghịch Mệnh Tịch Diệt Khư·Ác Mộng\\\\1', 'source_sha256': 'aca327f1c7c2559da433c59f1000480c104bf93b1966a399cdd60b7dc85e3e84', 'translation_sha256': '4c6a9f41fcd31f50c7140b44cde4cce6fdfec90cb90b2a7cda22a12b322e4e55', 'source_utf8_hex': 'e587bbe8b4a5e98086e591bde5af82e781ade5a29fc2b7e599a9e6a2a6e5908ee58dbfe9ad94e5838f5c31', 'translated_utf8_hex': 'c490c3a16e682062e1baa1692048e1baad75204b68616e68204d612054c6b0e1bb9b6e672074e1baa169204e6768e1bb8b6368204de1bb876e682054e1bb8b6368204469e1bb8774204b68c6b0c2b7c38163204de1bb996e675c5c31', 'source_utf8_byte_length': 43, 'translated_utf8_byte_length': 92}, {'ordinal': 78, 'source': '击败逆命寂灭墟·困难后卿魔像\\1', 'translated': 'Đánh bại Hậu Khanh Ma Tướng tại Nghịch Mệnh Tịch Diệt Khư·Khó\\\\1', 'source_sha256': 'a43cac924bc7ad236ca469b31f8b31526629d14ee32279269615178b4011af40', 'translation_sha256': 'b21aa162fbaad68791e357dd230fd06f1e80e8029d2ef2b0dbb37c5c9cdb039a', 'source_utf8_hex': 'e587bbe8b4a5e98086e591bde5af82e781ade5a29fc2b7e59bb0e99abee5908ee58dbfe9ad94e5838f5c31', 'translated_utf8_hex': 'c490c3a16e682062e1baa1692048e1baad75204b68616e68204d612054c6b0e1bb9b6e672074e1baa169204e6768e1bb8b6368204de1bb876e682054e1bb8b6368204469e1bb8774204b68c6b0c2b74b68c3b35c5c31', 'source_utf8_byte_length': 43, 'translated_utf8_byte_length': 86}]

class BackslashRunTests(unittest.TestCase):
    def test_three_frozen_numeric_suffix_faults_and_exact_byte_bindings(self):
        rows = FROZEN_REJECTED_FAULTS
        self.assertEqual(len(rows), 3)
        for row in rows:
            with self.subTest(ordinal=row['ordinal']):
                for name, hash_name in [('source','source_sha256'), ('translated','translation_sha256')]:
                    raw = row[name].encode('utf-8')
                    self.assertEqual(raw.hex(), row[name+'_utf8_hex'])
                    self.assertEqual(len(raw), row[name+'_utf8_byte_length'])
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), row[hash_name])
                self.assertEqual(quality.BACKSLASH_RUNS.findall(row['source']), ['\\'])
                self.assertEqual(quality.BACKSLASH_RUNS.findall(row['translated']), ['\\\\'])
                self.assertEqual(validate(row['source'], row['translated']), [REASON])

    def test_arbitrary_run_depths_suffix_digits_unknown_letters_and_trailing_runs(self):
        # No finite depth cap is encoded by the contract. Sample beyond usual escapes.
        for depth in (1,2,3,4,5,8,16,64):
            for suffix in ('0','1','9','123','q','E','Z','"',"'",'采集物',''):
                run = '\\' * depth
                source, target = '甲' + run + suffix, 'Giáp' + run + suffix
                with self.subTest(depth=depth, suffix=suffix):
                    self.assertEqual(validate(source, target), [])
                    self.assertIn(REASON, validate(source, 'Giáp' + run + '\\' + suffix))
                    self.assertIn(REASON, validate(source, 'Giáp' + run[:-1] + suffix))

    def test_add_drop_repeat_and_unequal_depth_order_fail(self):
        cases = [('甲', 'Giáp\\'), ('甲\\', 'Giáp'),
                 ('甲\\乙', 'Giáp\\Ất\\'),
                 ('甲\\乙\\\\丙', 'Giáp\\\\Ất\\Bính'),
                 ('甲\\\\乙\\丙', 'Giáp\\Ất\\\\Bính')]
        for source, target in cases:
            with self.subTest(source=source, target=target):
                self.assertIn(REASON, validate(source, target))

    def test_matching_nrtf_and_actual_controls_remain_valid(self):
        for suffix in ('n','r','t','f'):
            for depth in (1,2,3,8):
                escape = '\\' * depth + suffix
                self.assertEqual(validate('甲'+escape+'乙', 'Giáp'+escape+'Ất'), [])
        for control in ('\n','\r','\t','\f','\r\n','\x01','\x1f'):
            self.assertEqual(validate('甲'+control+'乙', 'Giáp'+control+'Ất'), [])
        self.assertEqual(validate(r'甲\r\n乙', r'Giáp\r\nẤt'), [])

    def test_existing_newline_guard_still_detects_changes_run_list_cannot(self):
        for source, target in [(r'甲\n乙', r'Giáp\tẤt'), ('甲\n乙','Giáp\tẤt'),
                               (r'甲\f乙', 'Giáp\fẤt')]:
            self.assertIn('newline_or_escape_form_changed', validate(source,target))

    def test_run_only_contract_does_not_claim_suffix_or_position_identity(self):
        # These are intentionally outside a run-list contract and need other QA/review.
        self.assertEqual(validate(r'甲\q乙', r'Giáp\ZẤt'), [])
        self.assertEqual(validate(r'甲\q乙', r'GiápẤt\q'), [])
        self.assertEqual(validate(r'甲\q乙\Z', r'Giáp\ZẤt\q'), [])

    def test_numeric_marker_resource_and_placeholder_contracts_stay_strict(self):
        for source,target,reason in [('3秒','4 giây','literal_numeric_value_changed'),
                                    ('<RTP_A>甲</>','<RTP_B>Giáp</>','markup_or_logic_attribute_changed'),
                                    ('@p(/Game/甲.甲)','@p(/Game/乙.乙)','resource_or_technical_token_changed'),
                                    ('{0}甲','{1}Giáp','brace_placeholder_sequence_changed')]:
            self.assertIn(reason,validate(source,target))

