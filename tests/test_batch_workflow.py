import concurrent.futures
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from batch_workflow import Workflow, encoded, main, structural_errors
from catalog_core import apply_review, read_ndjson, source_id, write_ndjson


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.root = pathlib.Path(self.temp.name)
        self.remaining = self.root / 'remaining.ndjson'
        self.db = self.root / 'queue.sqlite3'
        self.workflow = Workflow(self.db)

    def tearDown(self):
        self.workflow.close()
        self.temp.cleanup()

    def inventory(self, sources=('甲%d',), targets=None):
        targets = targets or {}
        rows = [dict(source=s, source_sha256=source_id(s), translated=targets.get(s), routes=['native']) for s in sources]
        write_ndjson(self.remaining, rows)
        self.workflow.refresh(self.remaining, 'coordinator')
        return rows

    def batches(self, **kwargs):
        return self.workflow.make_batches(self.root / 'batches', **kwargs)['batches']

    def claim(self, stage='TRANSLATE', owner='translator', now=100, **kwargs):
        return self.workflow.claim(stage, owner, now=now, **kwargs)

    def draft(self, claim, targets=None, status='TRANSLATED', reason=None):
        rows = [r for _, r in read_ndjson(claim['input_path'])]
        targets = targets or {r['source']: 'Giáp%d' for r in rows}
        result = [dict(source=r['source'], source_sha256=r['source_sha256'], status=status,
                       translated=targets.get(r['source']) if status == 'TRANSLATED' else None, reason=reason) for r in rows]
        path = self.root / 'draft.ndjson'
        write_ndjson(path, result)
        return path, result

    def submit(self, claim, path):
        return self.workflow.submit(claim['batch_id'], claim['owner'], claim['lease_token'], path, now=101)

    def review(self, claim, decision='APPROVE', change=None):
        rows = [dict(r, decision=decision, note='Compared the literal CN source and VI target in context') for r in claim['rows']]
        if change:
            rows[0].update(change)
        path = self.root / 'review.ndjson'
        write_ndjson(path, rows)
        return self.workflow.review(claim['batch_id'], claim['owner'], claim['lease_token'],
                                    claim['attempt_id'], path, now=103)

    def approved(self):
        self.inventory()
        batch = self.batches()[0]
        translator = self.claim(batch_id=batch)
        path, _ = self.draft(translator)
        self.assertEqual(self.submit(translator, path)['state'], 'AWAITING_REVIEW')
        reviewer = self.claim('REVIEW', 'reviewer', now=102, batch_id=batch)
        self.assertEqual(self.review(reviewer)['state'], 'APPROVED')
        return batch

    def reviewable(self, sources=('甲%d',), targets=None):
        self.inventory(sources)
        self.batches()
        translator = self.claim()
        path, _ = self.draft(translator, targets)
        self.submit(translator, path)
        return self.claim('REVIEW', 'reviewer', now=102)

    def compact_rows(self, claim, decision='APPROVE'):
        return [dict(source_sha256=row['source_sha256'], translation_sha256=row['translation_sha256'],
                     decision=decision, note='Compared this frozen CN source and VI target in context')
                for row in claim['rows']]

    def review_rows(self, claim, rows):
        path = self.root / 'compact-review.ndjson'
        write_ndjson(path, rows)
        return self.workflow.review(claim['batch_id'], claim['owner'], claim['lease_token'], claim['attempt_id'], path, now=103)

    def test_restart_and_simultaneous_double_claim(self):
        self.inventory()
        batch = self.batches()[0]
        self.workflow.close()
        self.workflow = Workflow(self.db)

        def claim(owner):
            worker = Workflow(self.db)
            try:
                return worker.claim('TRANSLATE', owner, batch_id=batch, now=100)
            finally:
                worker.close()

        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(claim, ['a', 'b']))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(self.workflow.status()['states']['TRANSLATING'], 1)

    def test_batches_are_exact_immutable_and_bounded_with_missing_priority(self):
        exact = '  甲\\n乙\n丙\u2028丁  '
        rows = self.inventory(('已有', exact, '乙', '很长很长很长'), {'已有': 'Có sẵn'})
        result = self.workflow.make_batches(self.root / 'batches', max_chars=len(exact), max_count=1)
        self.assertEqual(len(result['batches']), 4)
        # Claim ordering, including across restart, puts missing ahead of old targets.
        first = self.claim()
        contents = [r for _, r in read_ndjson(first['input_path'])]
        self.assertEqual(contents, [rows[1]])
        self.assertEqual(contents[0]['source'], exact)
        for batch in result['batches']:
            item = self.workflow.batch(batch)
            self.assertLessEqual(item['source_count'], 1)
            self.assertLessEqual(item['source_chars'], len(exact))
        before = pathlib.Path(first['input_path']).read_bytes()
        self.inventory(('已有', exact, '乙', '很长很长很长'), {'已有': 'Có sẵn'})
        self.assertEqual(self.batches(), [])
        self.assertEqual(pathlib.Path(first['input_path']).read_bytes(), before)

    def test_oversized_source_is_reported_and_not_silently_oversized(self):
        self.inventory(('甲', '乙乙乙'))
        result = self.workflow.make_batches(self.root / 'batches', max_chars=2, max_count=10)
        self.assertEqual(result['oversized_sources'], [dict(source_sha256=source_id('乙乙乙'), source_chars=3)])
        self.assertEqual(len(result['batches']), 1)

    def test_hash_mismatch_refresh_is_atomic(self):
        self.inventory()
        write_ndjson(self.remaining, [dict(source='乙', source_sha256=source_id('甲'))])
        with self.assertRaises(ValueError):
            self.workflow.refresh(self.remaining, 'coordinator')
        self.assertEqual(self.workflow.db.execute('SELECT source FROM sources WHERE active=1').fetchone()[0], '甲%d')

    def test_modified_input_and_changed_output_membership_cannot_be_claimed_or_reviewed(self):
        self.inventory()
        batch = self.batches()[0]
        translator = self.claim()
        path, rows = self.draft(translator)
        rows[0].update(source='乙%d', source_sha256=source_id('乙%d'))
        write_ndjson(path, rows)
        result = self.submit(translator, path)
        self.assertEqual(result['state'], 'REJECTED')
        self.assertIn('membership', result['errors'][0])
        self.assertIsNone(self.claim('REVIEW', 'reviewer', now=102))
        pathlib.Path(translator['input_path']).write_text('{}\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Immutable'):
            self.claim(batch_id=batch, now=102)

    def test_translator_cannot_self_approve_and_structural_pass_is_only_draft(self):
        self.inventory()
        batch = self.batches()[0]
        translator = self.claim()
        path, _ = self.draft(translator)
        self.submit(translator, path)
        self.assertEqual(self.workflow.status()['states']['AWAITING_REVIEW'], 1)
        self.assertIsNone(self.claim('REVIEW', 'translator', now=102))
        reviewer = self.claim('REVIEW', 'reviewer', now=102)
        with self.assertRaisesRegex(ValueError, 'owner'):
            self.workflow.review(batch, 'translator', reviewer['lease_token'], reviewer['attempt_id'], path, now=103)
        self.assertEqual(self.review(reviewer)['state'], 'APPROVED')
        self.assertEqual(self.workflow.status()['reviews'], 1)

    def test_invalid_placeholders_and_malformed_outputs_retain_attempts(self):
        self.inventory()
        self.batches()
        translator = self.claim()
        path, _ = self.draft(translator, {'甲%d': 'Giáp%s'})
        rejected = self.submit(translator, path)
        self.assertEqual(rejected['state'], 'REJECTED')
        self.assertIn('printf_argument_sequence_changed', rejected['errors'][0])
        second = self.claim(now=102)
        path.write_text('{broken', encoding='utf-8')
        result = self.workflow.submit(second['batch_id'], second['owner'], second['lease_token'], path, now=103)
        self.assertEqual(result['state'], 'REJECTED')
        history = self.workflow.history(second['batch_id'])
        self.assertEqual(len(history['attempts']), 2)
        self.assertIn('Giáp%s', history['attempts'][0]['raw_output'])
        self.assertEqual(history['attempts'][1]['raw_output'], '{broken')

    def test_technical_paths_cjk_tags_image_payloads_and_newline_forms_are_preserved(self):
        source = '<中文>甲%d</> @p(图片/中文.png) @t(头@@ (@@Image)路径/图.png(/Image) /Game/中文/图.uasset \\n'
        target = '<中文>Giáp%d</> @p(图片/中文.png) @t(头@@ (@@Image)路径/图.png(/Image) /Game/中文/图.uasset \\n'
        self.assertEqual(structural_errors(source, target), [])
        for before, after in [('<中文>', '<文字>'), ('@p(图片/中文.png)', '@p(图片/越文.png)'),
                              ('@t(头@@', '@t(首@@'), ('路径/图.png', 'đường/ảnh.png'),
                              ('/Game/中文/图.uasset', '/Game/Vi/ảnh.uasset'), ('\\n', '\n')]:
            with self.subTest(token=before):
                self.assertTrue(structural_errors(source, target.replace(before, after)))

    def test_expiry_live_owner_verification_and_stale_tokens_are_safe(self):
        self.inventory()
        batch = self.batches()[0]
        old = self.claim(lease_seconds=10)
        self.assertIsNone(self.claim(owner='other', now=111, live_owners=['translator']))
        with self.assertRaisesRegex(ValueError, 'live owner'):
            self.workflow.reclaim(batch, 'coordinator', 'explicit recovery', live_owners=['translator'], now=111)
        new = self.claim(owner='other', now=111)
        self.assertEqual(new['batch_id'], batch)
        self.assertNotEqual(old['lease_token'], new['lease_token'])
        path, _ = self.draft(old)
        with self.assertRaises(ValueError):
            self.workflow.submit(batch, old['owner'], old['lease_token'], path, now=112)
        with self.assertRaises(ValueError):
            self.workflow.heartbeat(batch, old['owner'], old['lease_token'], now=112)
        self.workflow.heartbeat(batch, 'other', new['lease_token'], lease_seconds=20, now=112)
        self.assertIsNone(self.claim(owner='third', now=120))
        self.workflow.reclaim(batch, 'coordinator', 'Explicit operator recovery; worker stopped', now=120)
        self.assertIsNotNone(self.claim(owner='third', now=121))
        self.assertEqual(len([e for e in self.workflow.history(batch)['events'] if e['kind'] == 'RECLAIMED']), 2)

    def test_expired_owner_cannot_extend_or_submit_without_new_claim(self):
        self.inventory()
        self.batches()
        old = self.claim(lease_seconds=1)
        path, _ = self.draft(old)
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.workflow.heartbeat(old['batch_id'], old['owner'], old['lease_token'], now=101)
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.workflow.submit(old['batch_id'], old['owner'], old['lease_token'], path, now=101)

    def test_reviewer_expiry_is_reclaimable_but_translator_still_cannot_review(self):
        self.inventory()
        self.batches()
        translator = self.claim()
        path, _ = self.draft(translator)
        self.submit(translator, path)
        reviewer = self.claim('REVIEW', 'reviewer', now=102, lease_seconds=1)
        self.assertIsNone(self.claim('REVIEW', 'translator', now=104))
        replacement = self.claim('REVIEW', 'reviewer-2', now=104)
        self.assertEqual(reviewer['attempt_id'], replacement['attempt_id'])
        self.assertNotEqual(reviewer['lease_token'], replacement['lease_token'])

    def test_changed_target_rejected_and_reopen_never_inherits_approval(self):
        self.inventory()
        batch = self.batches()[0]
        translator = self.claim()
        path, _ = self.draft(translator)
        self.submit(translator, path)
        reviewer = self.claim('REVIEW', 'reviewer', now=102)
        self.assertEqual(self.review(reviewer, change={'translated': 'Ất%d'})['state'], 'REJECTED')
        translator = self.claim(now=100)
        path, _ = self.draft(translator, {'甲%d': 'Ất%d'})
        self.submit(translator, path)
        reviewer = self.claim('REVIEW', 'reviewer', now=102)
        self.assertEqual(self.review(reviewer)['state'], 'APPROVED')
        self.workflow.reopen(batch, 'coordinator', 'Terminology correction required')
        self.assertEqual(self.workflow.export(self.root / 'after-reopen.ndjson', 'coordinator')['sources'], 0)
        self.assertEqual(len(self.workflow.history(batch)['attempts']), 2)
        self.assertEqual(len(self.workflow.history(batch)['reviews']), 2)

    def test_source_or_current_target_change_invalidates_approval_without_mutating_inputs(self):
        batch = self.approved()
        input_path = pathlib.Path(self.workflow.batch(batch)['input_path'])
        original = input_path.read_bytes()
        write_ndjson(self.remaining, [dict(source='乙%d', source_sha256=source_id('乙%d'), translated=None)])
        with self.assertRaisesRegex(ValueError, 'refresh'):
            self.workflow.export(self.root / 'unsafe.ndjson', 'coordinator')
        self.workflow.refresh(self.remaining, 'coordinator')
        self.assertEqual(self.workflow.batch(batch)['state'], 'INVALIDATED')
        self.assertEqual(input_path.read_bytes(), original)
        self.assertEqual(self.workflow.export(self.root / 'safe.ndjson', 'coordinator')['sources'], 0)
        self.assertEqual(len(self.batches()), 1)
        # Even if the same literal source returns, its changed active target
        # cannot revive a previous source/target review.
        self.inventory(('乙%d',), {'乙%d': 'Ất%d'})
        self.assertEqual(self.workflow.status()['states']['INVALIDATED'], 2)

    def test_ignore_needs_context_and_per_source_semantic_evidence_are_explicit(self):
        self.inventory(('内部',))
        self.batches()
        translator = self.claim()
        path, _ = self.draft(translator, status='IGNORE')
        self.assertEqual(self.submit(translator, path)['state'], 'REJECTED')
        translator = self.claim()
        path, _ = self.draft(translator, status='NEEDS_CONTEXT', reason='Need screen and speaker to identify entity')
        self.submit(translator, path)
        reviewer = self.claim('REVIEW', 'reviewer', now=102)
        self.assertEqual(self.review(reviewer)['state'], 'REJECTED')
        translator = self.claim()
        path, _ = self.draft(translator, status='NEEDS_CONTEXT', reason='Unresolved entity context')
        self.submit(translator, path)
        reviewer = self.claim('REVIEW', 'reviewer', now=102)
        self.assertEqual(self.review(reviewer, decision='NEEDS_CONTEXT')['state'], 'NEEDS_CONTEXT')
        self.assertIsNone(self.claim())
        self.workflow.reopen(translator['batch_id'], 'coordinator', 'Context established: engine internal identifier')
        translator = self.claim()
        path, _ = self.draft(translator, status='IGNORE', reason='Engine identifier; retain exact CN')
        self.submit(translator, path)
        reviewer = self.claim('REVIEW', 'reviewer', now=102)
        self.assertEqual(self.review(reviewer, change={'note': ''})['state'], 'REJECTED')

    def test_approved_export_is_coordinator_only_and_existing_import_compatible(self):
        batch = self.approved()
        output = self.root / 'approved.ndjson'
        with self.assertRaisesRegex(ValueError, 'coordinator-only'):
            self.workflow.export(output, 'translator')
        self.assertFalse(output.exists())
        result = self.workflow.export(output, 'coordinator')
        self.assertEqual(result['sources'], 1)
        row = next(read_ndjson(output))[1]
        self.assertEqual(row['status'], 'translated')
        self.assertEqual(row['reviewer'], 'reviewer')
        catalog = self.root / 'catalog.ndjson'
        write_ndjson(catalog, [dict(source='甲%d', status='missing', translated=None)])
        before = catalog.read_bytes()
        imported = self.root / 'imported.ndjson'
        self.assertEqual(apply_review(catalog, output, imported), 1)
        self.assertEqual(catalog.read_bytes(), before)
        self.assertEqual(next(read_ndjson(imported))[1]['translated'], 'Giáp%d')
        with self.assertRaises(FileExistsError):
            self.workflow.export(output, 'coordinator')
        self.assertEqual(self.workflow.batch(batch)['state'], 'APPROVED')

    def test_partial_review_exports_only_approved_rows_and_manifests_every_pending_source(self):
        self.inventory(('甲%d', '乙%d', '丙%d', '丁%d'))
        self.batches(max_count=3, max_batches=1)
        translator = self.claim()
        path, _ = self.draft(translator, {'甲%d': 'Giáp%d', '乙%d': 'Ất%d', '丙%d': 'Bính%d'})
        self.submit(translator, path)
        reviewer = self.claim('REVIEW', 'reviewer', now=102)
        decisions = {'甲%d': 'APPROVE', '乙%d': 'NEEDS_CONTEXT', '丙%d': 'REJECT'}
        rows = [dict(r, decision=decisions[r['source']], note='Source comparison: ' + decisions[r['source']]) for r in reviewer['rows']]
        review_path = self.root / 'partial.ndjson'
        write_ndjson(review_path, rows)
        result = self.workflow.review(reviewer['batch_id'], reviewer['owner'], reviewer['lease_token'], reviewer['attempt_id'], review_path, now=103)
        self.assertEqual(result['state'], 'PARTIALLY_APPROVED')
        output = self.root / 'approved-subset.ndjson'
        exported = self.workflow.export(output, 'coordinator')
        self.assertEqual(exported['sources'], 1)
        self.assertEqual(exported['pending_sources'], 3)
        self.assertEqual([r['source'] for _, r in read_ndjson(output)], ['甲%d'])
        manifest = json.loads(pathlib.Path(exported['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(manifest['inventory']['active_sources'], 4)
        self.assertEqual(manifest['inventory']['path'], str(self.remaining.resolve()))
        pending = {r['source_sha256']: r for r in manifest['pending']}
        self.assertEqual(pending[source_id('乙%d')]['decision'], 'NEEDS_CONTEXT')
        self.assertEqual(pending[source_id('丙%d')]['decision'], 'REJECT')
        self.assertEqual(pending[source_id('丁%d')]['state'], 'UNBATCHED')
        self.assertEqual(set(pending) | {r['source_sha256'] for r in manifest['exported']},
                         {source_id(s) for s in ('甲%d', '乙%d', '丙%d', '丁%d')})
        # No semantic approval survives a new target attempt, including a
        # previously exported subset from this partial batch.
        self.workflow.reopen(translator['batch_id'], 'coordinator', 'Context acquired; revise targets')
        replacement = self.claim()
        path, _ = self.draft(replacement, {'甲%d': 'Giáp khác%d', '乙%d': 'Ất%d', '丙%d': 'Bính%d'})
        self.submit(replacement, path)
        self.assertEqual(self.workflow.export(self.root / 'not-yet-approved.ndjson', 'coordinator')['sources'], 0)

    def test_active_current_target_change_invalidates_existing_approval(self):
        batch = self.approved()
        self.inventory(('甲%d',), {'甲%d': 'Bản mới%d'})
        self.assertEqual(self.workflow.batch(batch)['state'], 'INVALIDATED')
        self.assertIsNone(self.workflow.batch(batch)['approved_review'])
        self.assertEqual(self.workflow.export(self.root / 'no-old-target.ndjson', 'coordinator')['sources'], 0)
        self.assertEqual(len(self.workflow.history(batch)['reviews']), 1)

    def test_compact_approval_hydrates_exact_frozen_content_for_export(self):
        source = ' 甲%d\\n<中文>乙</> @p(中文.png)'
        target = ' Giáp%d\\n<中文>Ất</> @p(中文.png)'
        reviewer = self.reviewable((source,), {source: target})
        compact = self.compact_rows(reviewer)
        self.assertEqual(set(compact[0]), {'source_sha256', 'translation_sha256', 'decision', 'note'})
        self.assertIsNone(self.claim('REVIEW', 'translator', now=102))
        result = self.review_rows(reviewer, compact)
        self.assertEqual(result['state'], 'APPROVED')
        evidence = self.workflow.history(reviewer['batch_id'])['reviews'][0]
        self.assertEqual(json.loads(evidence['raw_review']), compact[0])
        exported = self.root / 'compact-approved.ndjson'
        self.assertEqual(self.workflow.export(exported, 'coordinator')['sources'], 1)
        row = next(read_ndjson(exported))[1]
        self.assertEqual(row['source'], source)
        self.assertEqual(row['translated'], target)
        self.assertEqual(row['translation_sha256'], source_id(target))
        self.assertEqual(row['review_note'], compact[0]['note'])

    def test_compact_partial_accepts_null_hashes_without_approving_context(self):
        self.inventory(('甲%d', '内部', '实体'))
        self.batches()
        translator = self.claim()
        path, rows = self.draft(translator, {'甲%d': 'Giáp%d'})
        for row in rows:
            if row['source'] == '内部':
                row.update(status='IGNORE', translated=None, reason='Internal engine identifier; retain literal source')
            elif row['source'] == '实体':
                row.update(status='NEEDS_CONTEXT', translated=None, reason='Need entity and screen context')
        write_ndjson(path, rows)
        self.submit(translator, path)
        reviewer = self.claim('REVIEW', 'reviewer', now=102)
        compact = self.compact_rows(reviewer)
        for row in compact:
            if row['source_sha256'] == source_id('实体'):
                row['decision'] = 'NEEDS_CONTEXT'
        result = self.review_rows(reviewer, compact)
        self.assertEqual(result['state'], 'PARTIALLY_APPROVED')
        exported = self.root / 'compact-partial.ndjson'
        result = self.workflow.export(exported, 'coordinator')
        output = {row['source']: row for _, row in read_ndjson(exported)}
        self.assertEqual(set(output), {'甲%d', '内部'})
        self.assertEqual(output['内部']['status'], 'ignore')
        self.assertIsNone(output['内部']['translation_sha256'])
        manifest = json.loads(pathlib.Path(result['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(manifest['pending'][0]['source_sha256'], source_id('实体'))
        self.assertEqual(manifest['pending'][0]['decision'], 'NEEDS_CONTEXT')

    def test_mixed_full_and_compact_rows_retain_legacy_full_format(self):
        reviewer = self.reviewable(('甲%d', '乙%d'), {'甲%d': 'Giáp%d', '乙%d': 'Ất%d'})
        rows = self.compact_rows(reviewer)
        rows[0] = dict(reviewer['rows'][0], decision='APPROVE', note='Full-format source comparison')
        rows[0].pop('translation_sha256')  # Original full schema did not require it.
        self.assertEqual(self.review_rows(reviewer, rows)['state'], 'APPROVED')

    def test_compact_wrong_hash_missing_hash_unknown_member_and_note_reject(self):
        changes = [
            ('wrong target', lambda row: row.update(translation_sha256=source_id('Other target%d'))),
            ('missing target', lambda row: row.pop('translation_sha256')),
            ('unknown source', lambda row: row.update(source_sha256=source_id('Unknown source%d'))),
            ('blank evidence', lambda row: row.update(note='  ')),
            ('aggregate QA', lambda row: row.update(decision='QA_PASS')),
            ('replacement text', lambda row: row.update(translated='Other target%d')),
        ]
        for label, change in changes:
            with self.subTest(case=label):
                reviewer = self.reviewable()
                rows = self.compact_rows(reviewer)
                change(rows[0])
                result = self.review_rows(reviewer, rows)
                self.assertEqual(result['state'], 'REJECTED')
                self.assertTrue(result['errors'])
                self.assertIsNone(self.workflow.batch(reviewer['batch_id'])['approved_review'])

    def test_compact_missing_and_duplicated_rows_reject_entire_review(self):
        for kind in ('missing', 'duplicated'):
            with self.subTest(case=kind):
                reviewer = self.reviewable(('甲%d', '乙%d'), {'甲%d': 'Giáp%d', '乙%d': 'Ất%d'})
                rows = self.compact_rows(reviewer)
                rows = rows[:1] if kind == 'missing' else rows + [rows[0]]
                self.assertEqual(self.review_rows(reviewer, rows)['state'], 'REJECTED')
                self.assertIsNone(self.workflow.batch(reviewer['batch_id'])['approved_review'])

    def test_compact_modified_attempt_payload_hash_binding_and_structure_reject(self):
        for mutation in ('payload', 'target_hash', 'target', 'source', 'placeholder'):
            with self.subTest(case=mutation):
                reviewer = self.reviewable()
                compact = self.compact_rows(reviewer)
                attempt = self.workflow.db.execute('SELECT * FROM attempts WHERE id=?', (reviewer['attempt_id'],)).fetchone()
                changed = json.loads(attempt['output_json'])
                changed[0]['translated'] = 'Other target%d'
                if mutation in ('target', 'source', 'placeholder'):
                    if mutation == 'source':
                        changed[0].update(source='乙%d', source_sha256=source_id('乙%d'))
                    elif mutation == 'placeholder':
                        changed[0]['translated'] = 'Other target%s'
                    changed[0]['translation_sha256'] = source_id(changed[0]['translated'])
                payload = encoded(changed)
                payload_sha = attempt['sha256'] if mutation == 'payload' else source_id(payload)
                self.workflow.db.execute('UPDATE attempts SET output_json=?,sha256=? WHERE id=?', (payload, payload_sha, reviewer['attempt_id']))
                result = self.review_rows(reviewer, compact)
                self.assertEqual(result['state'], 'REJECTED')
                self.assertTrue(result['errors'])
                self.assertIsNone(self.workflow.batch(reviewer['batch_id'])['approved_review'])

    def test_stricter_qa_allows_rejection_and_exports_only_valid_sibling(self):
        reviewer = self.reviewable(('甲%d', '乙%d'), {'甲%d': 'Giáp%d', '乙%d': 'Ất%d'})
        rows = self.compact_rows(reviewer)
        for row in rows:
            row['decision'] = 'REJECT' if row['source_sha256'] == source_id('甲%d') else 'APPROVE'
        def newer_rule(source, target):
            return ['new_contract_failure'] if target == 'Giáp%d' else structural_errors(source, target)
        with patch('batch_workflow.structural_errors', side_effect=newer_rule):
            self.assertEqual(self.review_rows(reviewer, rows)['state'], 'PARTIALLY_APPROVED')
            path = self.root / 'valid-sibling.ndjson'
            self.assertEqual(self.workflow.export(path, 'coordinator')['sources'], 1)
            self.assertEqual(next(read_ndjson(path))[1]['source'], '乙%d')

    def test_stricter_qa_still_blocks_approval_of_old_target(self):
        reviewer = self.reviewable()
        with patch('batch_workflow.structural_errors', return_value=['new_contract_failure']):
            result = self.review_rows(reviewer, self.compact_rows(reviewer))
        self.assertEqual(result['state'], 'REJECTED')
        self.assertTrue(result['errors'])
        self.assertIsNone(self.workflow.batch(reviewer['batch_id'])['approved_review'])

    def test_compact_prior_target_hash_cannot_approve_new_attempt(self):
        reviewer = self.reviewable()
        previous = self.compact_rows(reviewer)
        self.assertEqual(self.review_rows(reviewer, self.compact_rows(reviewer, 'REJECT'))['state'], 'REJECTED')
        replacement = self.claim()
        path, _ = self.draft(replacement, {'甲%d': 'Giáp sửa%d'})
        self.submit(replacement, path)
        current = self.claim('REVIEW', 'reviewer', now=102)
        self.assertNotEqual(current['attempt_id'], reviewer['attempt_id'])
        self.assertEqual(self.review_rows(current, previous)['state'], 'REJECTED')

    def test_compact_approved_target_modified_after_review_cannot_export(self):
        reviewer = self.reviewable()
        self.assertEqual(self.review_rows(reviewer, self.compact_rows(reviewer))['state'], 'APPROVED')
        attempt = self.workflow.db.execute('SELECT * FROM attempts WHERE id=?', (reviewer['attempt_id'],)).fetchone()
        changed = json.loads(attempt['output_json'])
        changed[0]['translated'] = 'Giáp sửa%d'
        changed[0]['translation_sha256'] = source_id(changed[0]['translated'])
        payload = encoded(changed)
        self.workflow.db.execute('UPDATE attempts SET output_json=?,sha256=? WHERE id=?', (payload, source_id(payload), reviewer['attempt_id']))
        output = self.root / 'must-not-export.ndjson'
        with self.assertRaisesRegex(ValueError, 'translation_sha256'):
            self.workflow.export(output, 'coordinator')
        self.assertFalse(output.exists())

    def test_cli_help_documents_protocol(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as result:
                main(['--help'])
        self.assertEqual(result.exception.code, 0)
        self.assertIn('PARTIALLY_APPROVED', output.getvalue())
        self.assertIn('live-owner', output.getvalue())
        self.assertIn('Compact review NDJSON', output.getvalue())
        self.assertIn('translation_sha256', output.getvalue())


if __name__ == '__main__':
    unittest.main()
