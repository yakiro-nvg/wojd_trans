"""Defensive resource/escape regressions; linguistic fixtures are not approval."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from batch_workflow import RESOURCE_TOKENS, resource_contract, structural_errors
from translation_quality import technical_contract, validate


class ResourceDirectiveContractTests(unittest.TestCase):
    def test_exact_source70_unchanged_directive_and_caption(self):
        # Literal existing author candidate from reviewer_275/technical-findings.
        source = r'   一二三\n三二一\n   下一页，有秘籍\f没有换页功能看不到\f@p(/Game/UI/吴思宇1022_NPC攻略优化继续.吴思宇1022_NPC攻略优化继续)\f图片结束'
        target = r'   Một hai ba\nBa hai một\n   Trang tiếp theo có bí kíp\fKhông có chức năng lật trang thì không xem được\f@p(/Game/UI/吴思宇1022_NPC攻略优化继续.吴思宇1022_NPC攻略优化继续)\fKết thúc hình ảnh'
        self.assertNotEqual(RESOURCE_TOKENS.findall(source), RESOURCE_TOKENS.findall(target))
        self.assertEqual(technical_contract(source), technical_contract(target))
        self.assertEqual(resource_contract(source), [])
        self.assertEqual(structural_errors(source, target), [])

    def test_complete_directive_next_to_caption_or_external_path(self):
        for directive in ('@p(/Game/中文.中文)', '@P(/Game/中文.中文)',
                          "@p(Texture2D'/Game/中文.中文',f)"):
            for tail in ('', r'\f', ' ', ' /Game/其他.uasset '):
                with self.subTest(directive=directive, tail=tail):
                    self.assertEqual(structural_errors(directive + tail + '甲', directive + tail + 'Giáp'), [])

    def test_every_directive_byte_and_wrapper_remains_immutable(self):
        source = r'@p(/Game/中文.中文)\f甲'
        target = r'@p(/Game/中文.中文)\fGiáp'
        for before, after in (('中文.中文', '中文.变更'), ('/Game/', '/Script/'),
                              ('@p(', '@P('), ('@p(', '@q('), (')', '')):
            with self.subTest(before=before, after=after):
                self.assertIn('resource_or_technical_token_changed',
                    structural_errors(source, target.replace(before, after)))

    def test_directive_addition_removal_order_and_duplication_fail(self):
        a, b = '@p(/Game/甲.甲)', '@p(/Game/乙.乙)'
        for source, target in ((a + '甲', 'Giáp'), ('甲', a + 'Giáp'),
                               (a + b + '甲', b + a + 'Giáp'),
                               (a + '甲', a + a + 'Giáp')):
            with self.subTest(source=source, target=target):
                self.assertIn('resource_or_technical_token_changed', structural_errors(source, target))

    def test_bare_windows_engine_and_external_paths_remain_strict(self):
        directive = '@p(/Game/中文.中文)'
        paths = (('/Game/目录/资源.uasset', '/Game/目录/变更.uasset'),
                 ('/Script/模块/资源', '/Script/模块/变更'),
                 (r'C:\assets\中文.png', r'C:\assets\变更.png'),
                 ('D:/assets/中文.png', 'D:/assets/变更.png'),
                 ("Texture2D'/Game/中文.中文'", "Texture2D'/Game/变更.变更'"),
                 ("Material'/Game/中文.中文'", "Material'/Game/变更.变更'"),
                 ('../assets/中文.xlsx', '../assets/变更.xlsx'),
                 ('https://example.invalid/中文.png', 'https://example.invalid/变更.png'))
        for path, changed in paths:
            source, target = directive + ' ' + path + ' 甲', directive + ' ' + path + ' Giáp'
            with self.subTest(path=path):
                self.assertEqual(structural_errors(source, target), [])
                self.assertIn('resource_path_changed', structural_errors(source, target.replace(path, changed)))

    def test_unclosed_and_malformed_directives_stay_conservative(self):
        for path in ('@p(/Game/中文.中文', '@p (/Game/中文.中文)',
                     '@q(/Game/中文.中文)', '@p(/Game/中文\n中文)'):
            source, target = path + ' 甲', path + ' Giáp'
            with self.subTest(path=path):
                self.assertTrue(resource_contract(source))
                self.assertEqual(structural_errors(source, target), [])
                self.assertIn('resource_path_changed', structural_errors(source, target.replace('/Game/', '/Script/')))
        # No generic ')' delimiter waiver for malformed or unwrapped paths.
        self.assertIn('resource_path_changed', structural_errors('@p (/Game/中文)甲', '@p (/Game/中文)Giáp'))
        self.assertIn('resource_path_changed', structural_errors('/Game/中文)甲', '/Game/中文)Giáp'))

    def test_external_filename_crossing_directive_stays_conservative(self):
        source = 'prefix@p(/Game/中文.中文)tail.png 甲'
        target = 'prefix@p(/Game/中文.中文)tail.png Giáp'
        self.assertEqual(structural_errors(source, target), [])
        self.assertIn('resource_path_changed', structural_errors(source, target.replace('prefix', 'changed')))
        self.assertIn('resource_path_changed', structural_errors(source, target.replace('tail.png', 'other.png')))

    def test_technical_tokens_outside_directive_remain_exact(self):
        prefix = '@p(/Game/中文.中文) '
        for source, target in (('@t(头@@甲||乙)', '@t(首@@Giáp||Ất)'),
                               ('(@@Image)中文|24|24(/Image)', '(@@Image)变更|24|24(/Image)'),
                               ('biaoqing_abc', 'biaoqing_abd'), ('A2F', 'A3F'),
                               ('【徒名】', '【师名】')):
            with self.subTest(source=source):
                self.assertIn('resource_or_technical_token_changed', structural_errors(prefix + source, prefix + target))

    def test_literal_f_depth_count_order_and_actual_form_remain_exact(self):
        for depth in range(1, 5):
            escape = '\\' * depth + 'f'
            source, target = '甲' + escape + '乙', 'Giáp' + escape + 'Ất'
            with self.subTest(depth=depth):
                self.assertEqual(validate(source, target), [])
                for replacement in ('', '\f', '\\' * (depth + 1) + 'f'):
                    self.assertIn('newline_or_escape_form_changed', validate(source, target.replace(escape, replacement)))
        self.assertIn('newline_or_escape_form_changed', validate(r'甲\n乙\f丙', r'Giáp\fẤt\nBính'))
        self.assertIn('newline_or_escape_form_changed', validate(r'甲\f乙\f丙', r'Giáp\fẤtBính'))
        self.assertIn('newline_or_escape_form_changed', validate(r'甲\f乙', r'Giáp\fẤt\f'))

    def test_directive_adjacent_pagebreak_changes_fail(self):
        source, target = r'@p(/Game/中文.中文)\f甲', r'@p(/Game/中文.中文)\fGiáp'
        for replacement in ('', '\f', r'\\f', r'\n'):
            with self.subTest(replacement=replacement):
                self.assertIn('newline_or_escape_form_changed', structural_errors(source, target.replace(r'\f', replacement)))

    def test_numeric_sign_contract_is_unchanged(self):
        self.assertIn('literal_numeric_value_changed', validate('全场满1000-50', 'Toàn cửa hàng: mua đủ 1000, giảm 50'))
        # Technical token fixture only; a new target still needs language review.
        self.assertEqual(validate('全场满1000-50', '1000 -50'), [])
        for target in ('1000 +50', '1000 50', '1000 -51', '100 -50', '1000 -50 -50'):
            self.assertIn('literal_numeric_value_changed', validate('全场满1000-50', target))


if __name__ == '__main__':
    unittest.main()
