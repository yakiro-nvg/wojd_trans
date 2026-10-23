"""Static contract regressions; frozen candidates still require semantic review."""
import hashlib
import json
import pathlib
import string
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from batch_workflow import RESOURCE_TOKENS, resource_contract, structural_errors
from translation_quality import technical_contract, validate

PAIRS = json.loads((ROOT / 'tests/fixtures/remaining_quality_falsepositives.json').read_text(encoding='utf-8'))


class RemainingQualityContractTests(unittest.TestCase):
    def test_three_full_pairs_remain_byte_bound_and_pass_structural_gate(self):
        self.assertEqual(len(PAIRS), 3)
        self.assertEqual(len({row['source_sha256'] for row in PAIRS}), 3)
        for row in PAIRS:
            with self.subTest(source_sha256=row['source_sha256']):
                self.assertEqual(hashlib.sha256(row['source'].encode('utf-8')).hexdigest(), row['source_sha256'])
                self.assertEqual(hashlib.sha256(row['candidate'].encode('utf-8')).hexdigest(), row['candidate_sha256'])
                self.assertEqual(structural_errors(row['source'], row['candidate']), [])

    def test_a2f_is_preserved_on_both_sides_of_cjk_prose(self):
        for source in ('甲A2F', 'A2F乙', '甲A2F乙', '甲A2F-乙', '【甲A2F】'):
            with self.subTest(source=source):
                self.assertEqual(technical_contract(source), ['A2F'])
                self.assertEqual(structural_errors(source, 'Giáp A2F'), [])
                # Same digit leaves the technical token as the relevant guard.
                self.assertIn('resource_or_technical_token_changed', structural_errors(source, 'Giáp A2G'))

    def test_every_ascii_identifier_boundary_stays_intact(self):
        for char in string.ascii_letters + string.digits + '_':
            for text in (char + 'A2F', 'A2F' + char, '甲' + char + 'A2F乙', '甲A2F' + char + '乙'):
                with self.subTest(text=text):
                    self.assertEqual(technical_contract(text), [])
        for char in ' -+/[]()，。':
            self.assertEqual(technical_contract(char + 'A2F' + char), ['A2F'])
        self.assertIn('resource_or_technical_token_changed', structural_errors('甲A2F乙', 'xA2F'))

    def test_unrelated_a2f_edits_additions_removals_and_duplicates_fail(self):
        directive = '@p(/Game/中文.中文)'
        source, target = directive + '甲A2F乙', directive + 'Giáp A2F Ất'
        self.assertEqual(structural_errors(source, target), [])
        for changed in (target.replace('A2F', 'A2G'), target.replace('A2F', ''),
                        target.replace('A2F', 'A2F A2F'), target.replace('A2F', 'a2f')):
            with self.subTest(changed=changed):
                self.assertIn('resource_or_technical_token_changed', structural_errors(source, changed))
        self.assertIn('resource_or_technical_token_changed', structural_errors(directive + '甲2乙', target))

    def test_adjacent_distinct_payloads_and_chained_escape_forms_mask_before_scan(self):
        a, b = '@p(/Game/中文/甲.甲,200,100)', '@P(/Game/中文/乙.乙,400,400,center)'
        for separator in ('', r'\n', r'\\n', r'\f', r'\\f', r'\n\f'):
            source = a + '@t(cBlue@@甲)' + b + separator + a + '“乙，丙。'
            target = a + '@t(cBlue@@Giáp)' + b + separator + a + '“Ất, Bính.'
            with self.subTest(separator=separator):
                self.assertNotEqual(RESOURCE_TOKENS.findall(source), RESOURCE_TOKENS.findall(target))
                self.assertEqual(resource_contract(source), [])
                self.assertEqual(resource_contract(target), [])
                self.assertEqual(structural_errors(source, target), [])

    def test_chained_payload_bytes_markers_deletion_and_order_remain_exact(self):
        a, b = '@p(/Game/中文/甲.甲,200,100)', '@P(/Game/中文/乙.乙,400,400,center)'
        source, target = a + b + r'\f甲', a + b + r'\fGiáp'
        for changed in (target.replace('乙.乙', '乙.丙'), target.replace('/Game/', '/Script/', 1),
                        target.replace('@P(', '@p('), target.replace('@P(', '@q('),
                        target.replace(',400,400,center', ',400,400,left'),
                        target.replace(a, '', 1), target.replace(b, b + b), b + a + r'\fGiáp'):
            with self.subTest(changed=changed):
                self.assertIn('resource_or_technical_token_changed', structural_errors(source, changed))

    def test_cjk_bare_paths_outside_multiple_payloads_stay_strict(self):
        prefix = '@p(/Game/中文/甲.甲)@p(/Game/中文/乙.乙)'
        for path, changed in (('/Game/目录/资源.uasset', '/Game/目录/变更.uasset'),
                              ('/Script/目录/资源', '/Script/目录/变更'),
                              ('目录/资源.png', '目录/变更.png'),
                              (r'D:\目录\资源.xlsx', r'D:\目录\变更.xlsx')):
            for separator in ('', ' '):
                source, target = prefix + separator + path + ' 甲', prefix + separator + path + ' Giáp'
                with self.subTest(path=path, separator=separator):
                    self.assertEqual(resource_contract(source), [path])
                    self.assertEqual(structural_errors(source, target), [])
                    self.assertIn('resource_path_changed', structural_errors(source, target.replace(path, changed)))
                    self.assertIn('resource_path_changed', structural_errors(source, target.replace(path, '')))

    def test_external_filename_crossing_multiple_payloads_stays_conservative(self):
        text = 'prefix@p(/Game/中文/甲.甲)@p(/Game/中文/乙.乙)tail.png '
        source, target = text + '甲', text + 'Giáp'
        self.assertEqual(structural_errors(source, target), [])
        for before, after in (('prefix', 'changed'), ('tail.png', 'other.png')):
            self.assertIn('resource_path_changed', structural_errors(source, target.replace(before, after)))

    def test_external_prefix_after_earlier_payload_cannot_be_lost(self):
        a, b = '@p(/Game/甲.甲)', '@P(/Game/乙.乙)'
        for preceding in (a, a + b, a + b + a):
            for prefix in ('prefix', '../assets/prefix', '中文前缀', '../目录/前缀'):
                source = preceding + prefix + b + 'tail.png 甲'
                target = preceding + prefix + b + 'tail.png Giáp'
                with self.subTest(preceding=preceding, prefix=prefix):
                    self.assertEqual(structural_errors(source, target), [])
                    for changed in ('changed', '', prefix + prefix):
                        altered = preceding + changed + b + 'tail.png Giáp'
                        self.assertIn('resource_path_changed', structural_errors(source, altered))
                    for suffix in ('other.png', '', 'tail.pngtail.png'):
                        altered = preceding + prefix + b + suffix + ' Giáp'
                        self.assertIn('resource_path_changed', structural_errors(source, altered))

    def test_every_external_interval_between_payloads_stays_strict(self):
        a, b = '@p(/Game/甲.甲)', '@P(/Game/乙.乙)'
        source = a + '前缀' + b + 'middle' + a + 'tail.png 甲'
        target = a + '前缀' + b + 'middle' + a + 'tail.png Giáp'
        self.assertEqual(structural_errors(source, target), [])
        for before, after in (('前缀', 'Tiền tố'), ('middle', 'other'), ('tail.png', '尾部.png')):
            with self.subTest(before=before):
                self.assertIn('resource_path_changed', structural_errors(source, target.replace(before, after)))

    def test_preceding_escape_and_cjk_caption_do_not_hide_external_prefix(self):
        a, b = '@p(/Game/甲.甲)', '@P(/Game/乙.乙)'
        for escape in (r'\n', r'\\n', r'\f', r'\\f'):
            source = a + escape + '../目录/前缀' + b + 'tail.png 甲'
            target = a + escape + '../目录/前缀' + b + 'tail.png Giáp'
            with self.subTest(escape=escape):
                self.assertEqual(structural_errors(source, target), [])
                self.assertIn('resource_path_changed', structural_errors(source, target.replace('../目录/', '../其他/')))
                caption_source, caption_target = a + escape + b + '甲乙', a + escape + b + 'Giáp Ất'
                self.assertEqual(resource_contract(caption_source), [])
                self.assertEqual(resource_contract(caption_target), [])
                self.assertEqual(structural_errors(caption_source, caption_target), [])

    def test_malformed_directives_keep_existing_conservative_paths(self):
        for malformed in ('@p(/Game/中文.中文', '@p (/Game/中文.中文)',
                          '@q(/Game/中文.中文)', '@p(/Game/中文\n中文)'):
            source, target = malformed + ' 甲', malformed + ' Giáp'
            with self.subTest(malformed=malformed):
                self.assertEqual(resource_contract(source), RESOURCE_TOKENS.findall(source))
                self.assertTrue(resource_contract(source))
                self.assertEqual(structural_errors(source, target), [])
                self.assertIn('resource_path_changed', structural_errors(source, target.replace('/Game/', '/Script/')))
        for source, target in (('@p (/Game/中文)甲', '@p (/Game/中文)Giáp'),
                               ('/Game/中文)甲', '/Game/中文)Giáp')):
            self.assertIn('resource_path_changed', structural_errors(source, target))

    def test_full_chained_fixture_keeps_escape_depth_and_every_payload_byte(self):
        row = next(row for row in PAIRS if row['source_sha256'].startswith('cd7702'))
        source, target = row['source'], row['candidate']
        self.assertIn('resource_or_technical_token_changed', structural_errors(source, target.replace(',400,400,center', ',400,400,left')))
        self.assertIn('newline_or_escape_form_changed', structural_errors(source, target.replace('\\\\n', '\\n', 1)))

    def test_unrelated_logic_attributes_and_protected_tokens_remain_exact(self):
        prefix = '@p(/Game/中文/甲.甲)@p(/Game/中文/乙.乙)'
        source = prefix + '<a taskID="114" text="甲" mapID="25"></> %d {中文} (@@Image)中文|24|24(/Image) A2F'
        target = prefix + '<a taskID="114" text="Giáp" mapID="25"></> %d {中文} (@@Image)中文|24|24(/Image) A2F'
        self.assertEqual(structural_errors(source, target), [])
        for before, after, reason in (('taskID="114"', 'taskID="115"', 'markup_or_logic_attribute_changed'),
                                      ('{中文}', '{越文}', 'brace_placeholder_sequence_changed'),
                                      ('%d', '%s', 'printf_argument_sequence_changed'),
                                      ('中文|24|24', '越文|24|24', 'resource_or_technical_token_changed'),
                                      ('A2F', 'A2G', 'resource_or_technical_token_changed')):
            with self.subTest(before=before):
                self.assertIn(reason, structural_errors(source, target.replace(before, after)))


if __name__ == '__main__':
    unittest.main()
