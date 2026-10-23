import collections
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ue_log import iter_misses


class LocalizationFailureLogTests(unittest.TestCase):
    def parse(self, text):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work/tmp') as folder:
            path = pathlib.Path(folder) / 'fixture.log'
            path.write_bytes(text.encode('utf-8'))
            stats = collections.Counter()
            return list(iter_misses(path, stats)), stats

    def test_missing_and_changed_source_are_both_collected(self):
        text = (
            '[2026.10.19-20.15.58:352][772]LogTextLocalizationManager: Verbose: '
            'An attempt was made to get a localized string (Namespace:, Key:card-label, Source:绘灵值), but it did not exist.\r\n'
            '[2026.10.19-20.15.58:353][773]LogTextLocalizationManager: Verbose: '
            'An attempt was made to get a localized string (Namespace:ZCTooltipSkillDoc, Key:skill), '
            'but the source string hash does not match - the source string (<RTP_Default>第一行</>\r\n'
            '<RTP_SkillTitleName>第二行 ${value}</>) will be used.\r\n'
        )
        rows, stats = self.parse(text)
        self.assertEqual([r['diagnostic_kind'] for r in rows], ['MISSING', 'HASH_MISMATCH'])
        self.assertEqual(rows[0]['namespace'], '')
        self.assertEqual(rows[0]['source'], '绘灵值')
        self.assertEqual(rows[1]['source'], '<RTP_Default>第一行</>\r\n<RTP_SkillTitleName>第二行 ${value}</>')
        self.assertEqual(rows[1]['log_line'], 2)
        self.assertEqual(stats['parsed_miss_events'], 2)
        self.assertEqual(stats['parsed_hash_mismatch_events'], 1)
        self.assertEqual(stats['unparsed_missing_records'], 0)

    def test_truncated_record_does_not_swallow_following_record(self):
        rows, stats = self.parse(
            '[2026.10.19-20.15.58:352][772]LogTextLocalizationManager: Verbose: '
            'An attempt was made to get a localized string (Namespace:n, Key:broken), '
            'but the source string hash does not match - the source string (truncated\n'
            '[2026.10.19-20.15.58:353][773]LogTextLocalizationManager: Verbose: '
            'An attempt was made to get a localized string (Namespace:n, Key:valid, Source:升级), but it did not exist.\n'
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['key'], 'valid')
        self.assertEqual(stats['unparsed_missing_records'], 1)

    def test_exact_source_parentheses_and_literal_newline_survive(self):
        source = '使用(目标), Source:原文\\n${名称}'
        rows, stats = self.parse(
            '[2026.10.19-20.15.58:353][773]LogTextLocalizationManager: Verbose: '
            'An attempt was made to get a localized string (Namespace:n, Key:k), '
            'but the source string hash does not match - the source string (' + source + ') will be used.\n'
        )
        self.assertEqual(rows[0]['source'], source)
        self.assertEqual(stats['unparsed_missing_records'], 0)


if __name__ == '__main__':
    unittest.main()
