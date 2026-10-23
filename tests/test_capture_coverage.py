import collections
import contextlib
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import capture_coverage
from capture_coverage import CaptureInputError, analyze_coverage, main


def sid(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class CaptureCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work/tmp')
        self.addCleanup(self.temp.cleanup)
        self.folder = pathlib.Path(self.temp.name)
        self.log = self.folder / 'paired.log'
        self.native = self.folder / 'rawdata.ndjson'
        self.expected = self.folder / 'expected.ndjson'
        self.log.write_bytes(b'')
        self.native.write_bytes(b'')

    def ndjson(self, path, rows):
        path.write_bytes((''.join(json.dumps(r, ensure_ascii=True) + '\n' for r in rows)).encode('utf-8'))

    def ue(self, *sources):
        events = []
        for n, source in enumerate(sources):
            prefix = ('[2026.10.19-20.15.58:352][772]LogTextLocalizationManager: Verbose: '
                      'An attempt was made to get a localized string ')
            if n % 2:
                events.append(prefix + f'(Namespace:n, Key:k{n}), but the source string hash does not match - the source string (' + source + ') will be used.\r\n')
            else:
                events.append(prefix + f'(Namespace:n, Key:k{n}, Source:' + source + '), but it did not exist.\r\n')
        self.log.write_bytes(''.join(events).encode('utf-8'))

    def captured(self, *sources, route='native_record_string_reader'):
        self.ndjson(self.native, [dict(route=route, source=s) for s in sources])

    def test_both_ue_diagnostics_and_duplicate_events_are_measured(self):
        self.ue('源甲', '源乙', '源甲')
        self.captured('源甲', '源乙', '源甲')
        r = analyze_coverage(self.log, self.native)
        self.assertEqual(r['gate']['status'], 'PASS')
        self.assertEqual(r['parser']['diagnostic_events'], {'HASH_MISMATCH': 1, 'MISSING': 2})
        self.assertEqual(r['counts']['ue_observed_unique_sources'], 2)
        self.assertEqual(r['counts']['ue_observed_identity_sources'], 3)
        self.assertEqual(r['native']['rows'], 3)
        self.assertEqual(r['native']['unique_sources'], 2)

    def test_target_never_substitutes_for_original_source_evidence(self):
        self.ue('当前源')
        self.ndjson(self.native, [dict(route='native_record_string_reader', source='其他源', target='当前源')])
        r = analyze_coverage(self.log, self.native)
        self.assertEqual(r['gate']['status'], 'FAIL')
        self.assertEqual(r['gaps'], [dict(source_sha256=sid('当前源'), status='MISSING_NATIVE_CURRENT_UE_OBSERVED')])
        text = json.dumps(r, ensure_ascii=False)
        self.assertNotIn('当前源', text)
        self.assertNotIn('其他源', text)
        self.assertNotIn(str(self.folder), text)

    def test_crlf_lf_and_literal_escape_sources_remain_distinct(self):
        sources = ['首行\r\n末行', '首行\n末行', r'首行\n末行']
        self.ue(*sources)
        self.captured(sources[1])
        r = analyze_coverage(self.log, self.native)
        self.assertEqual(r['counts']['required_and_ue_observed'], 3)
        self.assertEqual(r['coverage']['numerator'], 1)
        self.assertEqual({x['source_sha256'] for x in r['gaps']}, {sid(sources[0]), sid(sources[2])})

    def test_unseen_expected_is_not_a_current_capture_failure(self):
        self.ue('已观察')
        self.captured('已观察')
        self.ndjson(self.expected, [dict(source='已观察'), dict(source='尚未观察')])
        r = analyze_coverage(self.log, self.native, self.expected)
        self.assertEqual(r['gate']['status'], 'PASS')
        self.assertEqual(r['coverage']['percent'], 100.0)
        self.assertEqual(r['coverage']['scope'], 'REQUIRED_AND_UE_OBSERVED_ONLY')
        self.assertEqual(r['not_observed'], [dict(source_sha256=sid('尚未观察'), status='NOT_OBSERVED', native_source_observed=False)])
        self.assertFalse(r['scope']['all_game_coverage_claimed'])
        self.assertFalse(r['scope']['client_verified'])
        strict = analyze_coverage(self.log, self.native, self.expected, strict_global=True)
        self.assertEqual(strict['gate']['status'], 'FAIL')
        self.assertEqual(strict['gaps'], [])
        self.assertEqual(strict['global_missing_native_sha256'], [sid('尚未观察')])

    def test_unseen_ue_source_with_native_evidence_satisfies_strict_global(self):
        self.ue('已观察')
        self.captured('已观察', '尚未观察')
        self.ndjson(self.expected, [dict(source=s) for s in ['已观察', '尚未观察']])
        r = analyze_coverage(self.log, self.native, self.expected, strict_global=True)
        self.assertEqual(r['gate']['status'], 'PASS')
        self.assertTrue(r['not_observed'][0]['native_source_observed'])

    def test_no_observations_has_no_fake_one_hundred_percent(self):
        self.ndjson(self.expected, [dict(source='尚未观察')])
        r = analyze_coverage(self.log, self.native, self.expected)
        self.assertEqual(r['state'], 'NO_REQUIRED_UE_OBSERVATIONS')
        self.assertEqual(r['gate']['status'], 'NOT_EXERCISED')
        self.assertIsNone(r['coverage']['percent'])
        self.assertEqual(r['coverage']['denominator'], 0)
        self.assertEqual(r['not_observed'][0]['status'], 'NOT_OBSERVED')

    def test_no_inventory_and_empty_pair_is_not_exercised(self):
        r = analyze_coverage(self.log, self.native)
        self.assertIsNone(r['coverage']['percent'])
        self.assertEqual(r['counts']['required_unique_sources'], 0)
        self.assertEqual(r['gate']['status'], 'NOT_EXERCISED')

    def test_inventory_subset_does_not_claim_other_ue_sources_covered(self):
        self.ue('必需', '其他')
        self.captured('必需')
        self.ndjson(self.expected, [dict(source_sha256=sid('必需'))])
        r = analyze_coverage(self.log, self.native, self.expected)
        self.assertEqual(r['gate']['status'], 'PASS')
        self.assertEqual(r['counts']['ue_observed_outside_required'], 1)
        self.assertEqual(r['counts']['all_ue_observed_captured'], 1)
        self.assertFalse(r['scope']['all_game_coverage_claimed'])

    def test_empty_ue_source_is_valid_and_still_scoped_by_required_inventory(self):
        self.ue('', '必需')
        self.captured('必需')
        self.ndjson(self.expected, [dict(source='必需')])
        r = analyze_coverage(self.log, self.native, self.expected)
        self.assertEqual(r['gate']['status'], 'PASS')
        self.assertEqual(r['counts']['ue_empty_source_events'], 1)
        self.assertEqual(r['counts']['ue_observed_outside_required'], 1)

    def test_routes_are_labels_without_a_whitelist_or_origin_inference(self):
        self.ue('资源.data')
        self.captured('资源.data', route='future.reader:probe')
        r = analyze_coverage(self.log, self.native)
        self.assertEqual(r['gate']['status'], 'PASS')
        self.assertIn('future.reader:probe', r['native']['routes'])
        self.assertFalse(r['scope']['route_labels_are_coverage_proof'])
        self.assertEqual(r['scope']['origin_inference'], 'NONE')
        self.captured('不同源', route='native_data_decoder_assignment')
        self.assertEqual(analyze_coverage(self.log, self.native)['gate']['status'], 'FAIL')

    def test_malformed_native_rows_fail_instead_of_being_silently_skipped(self):
        cases = [
            dict(route='native_record_string_reader', target='private prose'),
            dict(route='native_record_string_reader', source=''),
            dict(route='native_record_string_reader', source=42),
            dict(route='native_record_string_reader', source=None),
            dict(source='源'),
            dict(route=42, source='源'),
            dict(route='private prose with spaces', source='源'),
            dict(route='probe', source='源', source_sha256='0' * 64),
            dict(route='probe', source='源', source_sha256='bad'),
            dict(route='probe', source='\ud800'),
            [],
        ]
        for row in cases:
            with self.subTest(row=row):
                self.ndjson(self.native, [row])
                with self.assertRaises(CaptureInputError) as caught:
                    analyze_coverage(self.log, self.native)
                self.assertNotIn('private prose', str(caught.exception))
        for raw in [b'{"source": invalid}\n', b'\xff\n']:
            with self.subTest(raw=raw):
                self.native.write_bytes(raw)
                with self.assertRaises(CaptureInputError):
                    analyze_coverage(self.log, self.native)

    def test_expected_inventory_accepts_exact_text_or_hash_and_deduplicates(self):
        self.ue('源')
        self.captured('源')
        self.ndjson(self.expected, [dict(source='源', source_sha256=sid('源')), dict(source_sha256=sid('源'))])
        r = analyze_coverage(self.log, self.native, self.expected)
        self.assertEqual(r['counts']['required_inventory_rows'], 2)
        self.assertEqual(r['counts']['required_unique_sources'], 1)
        for row in [dict(source='源', source_sha256='0' * 64), {}, dict(source_sha256='bad')]:
            with self.subTest(row=row):
                self.ndjson(self.expected, [row])
                with self.assertRaises(CaptureInputError):
                    analyze_coverage(self.log, self.native, self.expected)

    def test_truncated_ue_record_invalidates_evidence_separately_from_gaps(self):
        self.log.write_bytes(b'[2026.10.19-20.15.58:352]LogTextLocalizationManager: (Namespace:n, Key:k, Source:unfinished\n')
        r = analyze_coverage(self.log, self.native)
        self.assertEqual(r['state'], 'INVALID_INPUT')
        self.assertEqual(r['gate']['status'], 'NOT_EVALUATED')
        self.assertEqual(r['parser']['errors'], 1)
        self.assertEqual(r['gaps'], [])

    def test_changed_input_is_rejected(self):
        original = capture_coverage._native_sources
        def changed(path):
            result = original(path)
            path.write_bytes(b'\n')
            return result
        with mock.patch.object(capture_coverage, '_native_sources', side_effect=changed):
            with self.assertRaises(CaptureInputError) as caught:
                analyze_coverage(self.log, self.native)
        self.assertEqual(caught.exception.code, 'INPUT_CHANGED_DURING_ANALYSIS')

    def test_cli_exit_codes_hashes_and_safe_invalid_input_report(self):
        self.ue('当前源')
        args = ['--ue-log', str(self.log), '--rawdata', str(self.native)]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            status = main(args)
        r = json.loads(output.getvalue())
        self.assertEqual(status, 1)
        self.assertEqual(r['inputs']['ue_log']['sha256'], hashlib.sha256(self.log.read_bytes()).hexdigest())
        self.captured('当前源')
        dest = self.folder / 'report.json'
        self.assertEqual(main(args + ['--out', str(dest)]), 0)
        self.assertEqual(json.loads(dest.read_text('utf-8'))['gate']['status'], 'PASS')
        self.ndjson(self.native, [dict(route='probe', target='private prose')])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            status = main(args)
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(output.getvalue())['state'], 'INVALID_INPUT')
        self.assertNotIn('private prose', output.getvalue())

    def test_cli_cannot_overwrite_a_capture(self):
        self.ue('源')
        before = self.log.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            status = main(['--ue-log', str(self.log), '--native-capture', str(self.native), '--out', str(self.log)])
        self.assertEqual(status, 2)
        self.assertEqual(self.log.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
