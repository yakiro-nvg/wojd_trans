"""Durable, offline translation/review queue. This module never changes catalogs.

Input sources and batch membership are literal and SHA-bound. Structural QA is
only a gate to independent semantic review, never evidence of language quality.
Run ``python scripts/batch_workflow.py --help`` for the handoff protocol.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import time
import uuid

from catalog_core import digest, source_id
from translation_quality import PROTECTED, validate


STATES = ('READY', 'TRANSLATING', 'AWAITING_REVIEW', 'REVIEWING',
          'APPROVED', 'PARTIALLY_APPROVED', 'REJECTED', 'NEEDS_CONTEXT', 'INVALIDATED')
DECISIONS = ('TRANSLATED', 'IGNORE', 'NEEDS_CONTEXT')
RESOURCE_TOKENS = re.compile(
    r'''(?:/(?:Game|Script)/[^\s<>\{\}"'，。；、！？]+|[A-Za-z]:[\\/][^\s<>\{\}"'，。；、！？]+|(?:Texture2D|Material)'[^'\r\n]+'|[^\s<>\{\}"'，。；、！？]+\.(?:xlsx?|lua|data|gdv|uasset|umap|png|dds|tga)(?=$|[\s<>\{\}"'，。；、！？]))''', re.I)


def resource_contract(text):
    # Complete @p payloads are already compared byte for byte by validate().
    # Mask only those recognized spans so the bare-path regex cannot consume
    # their closing ')' and adjacent translated caption. Keep malformed or
    # unclosed directives and every resource outside the span under the same
    # conservative path check. A space preserves token boundaries.
    spans = [match.span() for match in PROTECTED.finditer(text)
             if match.group().startswith(('@p(', '@P('))]
    if not spans:
        return RESOURCE_TOKENS.findall(text)
    masked = PROTECTED.sub(lambda match: ' ' if match.group().startswith(('@p(', '@P('))
                           else match.group(), text)
    tokens = RESOURCE_TOKENS.findall(masked)
    # Preserve the old conservative check for an external path whose token
    # starts outside a directive and crosses into it (e.g. x@p(...)y.png).
    # Rescan from each outside interval: a raw match inside an earlier payload
    # can otherwise hide an external filename prefix before a later directive.
    # Accept only starts before the next protected span, never payload origins.
    outside_start = 0
    for start, end in spans:
        if outside_start < start:
            for match in RESOURCE_TOKENS.finditer(text, outside_start):
                if match.start() >= start:
                    break
                if match.end() > start:
                    tokens.append(match.group())
        outside_start = end
    return tokens


def structural_errors(source, target):
    errors = validate(source, target)
    if isinstance(target, str) and resource_contract(source) != resource_contract(target):
        errors.append('resource_path_changed')
    return errors


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def stamp(value):
    return datetime.datetime.fromtimestamp(value, datetime.timezone.utc).isoformat()


def required(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} is required')
    return value


def parse_rows(raw):
    rows = []
    for number, line in enumerate(raw.split('\n'), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f'Line {number}: expected an object')
        rows.append(row)
    return rows


class Workflow:
    def __init__(self, path):
        self.path = pathlib.Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS snapshots(
                id INTEGER PRIMARY KEY,path TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources(
                sha256 TEXT PRIMARY KEY,source TEXT UNIQUE NOT NULL,input_json TEXT NOT NULL,
                current_translation TEXT,priority INTEGER NOT NULL,ordinal INTEGER NOT NULL,active INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS batches(
                id TEXT PRIMARY KEY,state TEXT NOT NULL,input_path TEXT NOT NULL,input_sha256 TEXT NOT NULL,
                source_count INTEGER NOT NULL,source_chars INTEGER NOT NULL,created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,owner TEXT,lease_token TEXT,lease_expires REAL,
                latest_attempt INTEGER,approved_review INTEGER);
            CREATE TABLE IF NOT EXISTS members(
                batch_id TEXT NOT NULL REFERENCES batches(id),source_sha256 TEXT NOT NULL REFERENCES sources(sha256),
                ordinal INTEGER NOT NULL,input_json TEXT NOT NULL,current_translation TEXT,
                PRIMARY KEY(batch_id,source_sha256));
            CREATE INDEX IF NOT EXISTS members_source ON members(source_sha256);
            CREATE TABLE IF NOT EXISTS attempts(
                id INTEGER PRIMARY KEY,batch_id TEXT NOT NULL REFERENCES batches(id),translator TEXT NOT NULL,
                created_at TEXT NOT NULL,raw_output TEXT NOT NULL,output_json TEXT,sha256 TEXT,
                errors_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reviews(
                id INTEGER PRIMARY KEY,batch_id TEXT NOT NULL REFERENCES batches(id),attempt_id INTEGER NOT NULL REFERENCES attempts(id),
                reviewer TEXT NOT NULL,created_at TEXT NOT NULL,raw_review TEXT NOT NULL,
                state TEXT NOT NULL,errors_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY,batch_id TEXT,created_at TEXT NOT NULL,kind TEXT NOT NULL,
                actor TEXT,details_json TEXT NOT NULL);
        ''')

    def close(self):
        self.db.close()

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def event(self, batch, kind, actor=None, now=None, **details):
        self.db.execute('INSERT INTO events(batch_id,created_at,kind,actor,details_json) VALUES(?,?,?,?,?)',
                        (batch, stamp(time.time() if now is None else now), kind, actor, encoded(details)))

    def coordinator(self, owner):
        required(owner, 'Coordinator identity')
        row = self.db.execute("SELECT value FROM metadata WHERE key='coordinator'").fetchone()
        if row is None or row['value'] != owner:
            raise ValueError('This operation is coordinator-only; identity must match refresh configuration')

    def refresh(self, remaining, coordinator):
        """Atomically replace active inventory, retaining old attempts and evidence."""
        required(coordinator, 'Coordinator identity')
        remaining = pathlib.Path(remaining).resolve()
        raw = remaining.read_bytes()
        rows = parse_rows(raw.decode('utf-8-sig'))
        seen = set()
        for row in rows:
            source = row.get('source')
            if not isinstance(source, str) or row.get('source_sha256') != source_id(source):
                raise ValueError('Every source needs an exact source_sha256; no normalization is allowed')
            if row['source_sha256'] in seen:
                raise ValueError('Duplicate source in remaining inventory')
            seen.add(row['source_sha256'])
            target = row.get('current_translation', row.get('translated'))
            if target is not None and not isinstance(target, str):
                raise ValueError('Current translation must be text or null')
        now = time.time()
        with self.transaction():
            configured = self.db.execute("SELECT value FROM metadata WHERE key='coordinator'").fetchone()
            if configured:
                self.coordinator(coordinator)
            else:
                self.db.execute("INSERT INTO metadata VALUES('coordinator',?)", (coordinator,))
            self.db.execute('UPDATE sources SET active=0')
            for ordinal, row in enumerate(rows):
                target = row.get('current_translation', row.get('translated'))
                self.db.execute('''INSERT INTO sources VALUES(?,?,?,?,?,?,1)
                    ON CONFLICT(sha256) DO UPDATE SET input_json=excluded.input_json,
                    current_translation=excluded.current_translation,priority=excluded.priority,
                    ordinal=excluded.ordinal,active=1''',
                    (row['source_sha256'], row['source'], encoded(row), target, int(bool(target)), ordinal))
            stale = self.db.execute('''SELECT DISTINCT b.id FROM batches b JOIN members m ON m.batch_id=b.id
                JOIN sources s ON s.sha256=m.source_sha256 WHERE b.state!='INVALIDATED'
                AND (s.active=0 OR s.current_translation IS NOT m.current_translation)''').fetchall()
            for batch in stale:
                self.db.execute("UPDATE batches SET state='INVALIDATED',owner=NULL,lease_token=NULL,lease_expires=NULL,approved_review=NULL,updated_at=? WHERE id=?",
                                (stamp(now), batch['id']))
                self.event(batch['id'], 'INVALIDATED', coordinator, now, reason='source removed or current target changed')
            sha = hashlib.sha256(raw).hexdigest()
            self.db.execute('INSERT INTO snapshots(path,sha256,created_at) VALUES(?,?,?)', (str(remaining), sha, stamp(now)))
            self.event(None, 'REFRESHED', coordinator, now, sha256=sha, sources=len(rows))
        return dict(sources=len(rows), invalidated_batches=len(stale), remaining_sha256=sha)

    def check_snapshot(self):
        row = self.db.execute('SELECT * FROM snapshots ORDER BY id DESC LIMIT 1').fetchone()
        if row is None:
            raise ValueError('Run refresh first')
        if not pathlib.Path(row['path']).exists() or digest(row['path']) != row['sha256']:
            raise ValueError('Remaining inventory changed on disk; run refresh before continuing')

    def make_batches(self, directory, max_chars=12000, max_count=60, max_batches=0):
        if max_chars <= 0 or max_count <= 0 or max_batches < 0:
            raise ValueError('Batch bounds must be positive; max_batches may be zero for unlimited')
        directory = pathlib.Path(directory).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        now = time.time()
        created, oversized = [], []
        with self.transaction():
            self.check_snapshot()
            rows = self.db.execute('''SELECT s.* FROM sources s WHERE active=1 AND NOT EXISTS(
                SELECT 1 FROM members m JOIN batches b ON b.id=m.batch_id
                WHERE m.source_sha256=s.sha256 AND b.state!='INVALIDATED') ORDER BY priority,ordinal''').fetchall()
            groups, group, chars = [], [], 0
            for row in rows:
                size = len(row['source'])
                if size > max_chars:
                    oversized.append(dict(source_sha256=row['sha256'], source_chars=size))
                    continue
                if group and (chars + size > max_chars or len(group) == max_count):
                    groups.append(group)
                    group, chars = [], 0
                group.append(row)
                chars += size
            if group:
                groups.append(group)
            for group in groups[:max_batches or None]:
                batch_id = uuid.uuid4().hex
                path = directory / f'{batch_id}.input.ndjson'
                payload = ''.join(row['input_json'] + '\n' for row in group).encode('utf-8')
                # Exclusive creation + hash checks make inputs immutable. A crash
                # before DB commit may leave an unreferenced file, never a job.
                with path.open('xb') as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                self.db.execute('''INSERT INTO batches(id,state,input_path,input_sha256,source_count,source_chars,created_at,updated_at)
                    VALUES(?,'READY',?,?,?,?,?,?)''',
                    (batch_id, str(path), hashlib.sha256(payload).hexdigest(), len(group), sum(len(r['source']) for r in group), stamp(now), stamp(now)))
                self.db.executemany('INSERT INTO members VALUES(?,?,?,?,?)',
                    [(batch_id, r['sha256'], n, r['input_json'], r['current_translation']) for n, r in enumerate(group)])
                self.event(batch_id, 'CREATED', now=now)
                created.append(batch_id)
        return dict(batches=created, oversized_sources=oversized)

    def batch(self, batch_id):
        row = self.db.execute('SELECT * FROM batches WHERE id=?', (batch_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown batch')
        return row

    def verify_batch(self, batch):
        if digest(batch['input_path']) != batch['input_sha256']:
            raise ValueError('Immutable batch input was modified')
        members = self.db.execute('SELECT * FROM members WHERE batch_id=? ORDER BY ordinal', (batch['id'],)).fetchall()
        if len(members) != batch['source_count']:
            raise ValueError('Batch membership mismatch')
        for member in members:
            source = json.loads(member['input_json'])['source']
            if source_id(source) != member['source_sha256']:
                raise ValueError('Batch source hash mismatch')
            current = self.db.execute('SELECT * FROM sources WHERE sha256=?', (member['source_sha256'],)).fetchone()
            if not current['active'] or current['source'] != source or current['current_translation'] != member['current_translation']:
                raise ValueError('Batch source/current target changed; refresh and re-batch')
        return members

    def release(self, batch, actor, reason, now):
        state = 'READY' if batch['state'] == 'TRANSLATING' else 'AWAITING_REVIEW'
        self.db.execute('UPDATE batches SET state=?,owner=NULL,lease_token=NULL,lease_expires=NULL,updated_at=? WHERE id=?',
                        (state, stamp(now), batch['id']))
        self.event(batch['id'], 'RECLAIMED', actor, now, previous_owner=batch['owner'], reason=reason)

    def reclaim(self, batch_id, coordinator, reason, live_owners=(), now=None):
        required(reason, 'Explicit reclaim reason')
        now = time.time() if now is None else now
        with self.transaction():
            self.coordinator(coordinator)
            batch = self.batch(batch_id)
            if batch['state'] not in ('TRANSLATING', 'REVIEWING'):
                raise ValueError('Batch has no active claim')
            if batch['owner'] in set(live_owners):
                raise ValueError('Verified live owner blocks reclaim')
            self.release(batch, coordinator, reason, now)
        return dict(batch_id=batch_id, reclaimed=True)

    def claim(self, stage, owner, lease_seconds=1800, batch_id=None, live_owners=(), now=None):
        required(owner, 'Owner')
        if stage not in ('TRANSLATE', 'REVIEW') or lease_seconds <= 0:
            raise ValueError('Stage must be TRANSLATE or REVIEW and lease must be positive')
        now = time.time() if now is None else now
        live = set(live_owners)
        with self.transaction():
            expired = self.db.execute("SELECT * FROM batches WHERE state IN ('TRANSLATING','REVIEWING') AND lease_expires<=?", (now,)).fetchall()
            for batch in expired:
                if batch['owner'] not in live:
                    self.release(batch, owner, 'expired lease; no verified live owner supplied', now)
            eligible = ('READY', 'REJECTED') if stage == 'TRANSLATE' else ('AWAITING_REVIEW',)
            query = 'SELECT * FROM batches WHERE state IN (' + ','.join('?' for _ in eligible) + ')'
            args = list(eligible)
            if batch_id:
                query += ' AND id=?'
                args.append(batch_id)
            query += ''' ORDER BY (SELECT min(s.priority) FROM members m JOIN sources s
                ON s.sha256=m.source_sha256 WHERE m.batch_id=batches.id),rowid'''
            for batch in self.db.execute(query, args).fetchall():
                attempt = None
                if stage == 'REVIEW':
                    attempt = self.db.execute('SELECT * FROM attempts WHERE id=?', (batch['latest_attempt'],)).fetchone()
                    if attempt['translator'] == owner:
                        continue
                members = self.verify_batch(batch)
                frozen = self.frozen_attempt_rows(attempt, members) if attempt else None
                token = uuid.uuid4().hex
                state = 'TRANSLATING' if stage == 'TRANSLATE' else 'REVIEWING'
                self.db.execute('UPDATE batches SET state=?,owner=?,lease_token=?,lease_expires=?,updated_at=? WHERE id=?',
                                (state, owner, token, now + lease_seconds, stamp(now), batch['id']))
                self.event(batch['id'], 'CLAIMED', owner, now, stage=stage, lease_expires_at=stamp(now + lease_seconds))
                result = dict(batch_id=batch['id'], state=state, owner=owner, lease_token=token,
                              lease_expires_at=stamp(now + lease_seconds), input_path=batch['input_path'], input_sha256=batch['input_sha256'])
                if attempt:
                    result.update(attempt_id=attempt['id'], attempt_sha256=attempt['sha256'], rows=frozen)
                return result
        return None

    def authorized(self, batch_id, owner, token, stage, now):
        batch = self.batch(batch_id)
        if batch['state'] != stage or batch['owner'] != owner or batch['lease_token'] != token:
            raise ValueError('Claim state, owner or lease token does not match')
        if batch['lease_expires'] <= now:
            raise ValueError('Lease expired; claim again before submitting')
        return batch

    def heartbeat(self, batch_id, owner, token, lease_seconds=1800, now=None):
        if lease_seconds <= 0:
            raise ValueError('Lease must be positive')
        now = time.time() if now is None else now
        with self.transaction():
            batch = self.batch(batch_id)
            if batch['state'] not in ('TRANSLATING', 'REVIEWING'):
                raise ValueError('Batch has no active claim')
            self.authorized(batch_id, owner, token, batch['state'], now)
            self.db.execute('UPDATE batches SET lease_expires=?,updated_at=? WHERE id=?', (now + lease_seconds, stamp(now), batch_id))
            self.event(batch_id, 'HEARTBEAT', owner, now, lease_expires_at=stamp(now + lease_seconds))
        return dict(batch_id=batch_id, lease_expires_at=stamp(now + lease_seconds))

    def decisions(self, raw, members, check_structure=True):
        rows = parse_rows(raw)
        expected = {m['source_sha256']: json.loads(m['input_json'])['source'] for m in members}
        found, result = set(), []
        for row in rows:
            sid, source = row.get('source_sha256'), row.get('source')
            if sid not in expected or source != expected[sid] or source_id(source) != sid or sid in found:
                raise ValueError('Output source/membership changed or duplicated')
            found.add(sid)
            decision = row.get('status')
            if decision not in DECISIONS:
                raise ValueError(f'Use an English decision enum from {DECISIONS}')
            target, reason = row.get('translated'), row.get('reason')
            if decision == 'TRANSLATED':
                if not isinstance(target, str) or not target:
                    raise ValueError(f'{sid}: translated target must be nonempty text')
                if check_structure:
                    errors = structural_errors(source, target)
                    if target == source:
                        errors.append('unchanged_target_requires_explicit_ignore')
                    if errors:
                        raise ValueError(f'{sid}: structural QA failed: {errors}')
            else:
                required(reason, f'{decision} reason')
                if target is not None:
                    raise ValueError('IGNORE/NEEDS_CONTEXT must not supply a target')
            result.append(dict(source=source, source_sha256=sid, translated=target, status=decision, reason=reason,
                               translation_sha256=source_id(target) if target is not None else None))
        if found != set(expected):
            raise ValueError('Output must contain exactly every immutable batch member')
        return sorted(result, key=lambda r: r['source_sha256'])

    def submit(self, batch_id, owner, token, output, now=None):
        raw = pathlib.Path(output).read_text(encoding='utf-8-sig')
        now = time.time() if now is None else now
        with self.transaction():
            batch = self.authorized(batch_id, owner, token, 'TRANSLATING', now)
            members = self.verify_batch(batch)
            errors, rows = [], None
            try:
                rows = self.decisions(raw, members)
            except (ValueError, TypeError, UnicodeError) as error:
                errors.append(str(error))
            payload = encoded(rows) if rows is not None else None
            cur = self.db.execute('''INSERT INTO attempts(batch_id,translator,created_at,raw_output,output_json,sha256,errors_json)
                VALUES(?,?,?,?,?,?,?)''', (batch_id, owner, stamp(now), raw, payload, source_id(payload) if payload else None, encoded(errors)))
            state = 'REJECTED' if errors else 'AWAITING_REVIEW'
            self.db.execute('''UPDATE batches SET state=?,latest_attempt=?,approved_review=NULL,
                owner=NULL,lease_token=NULL,lease_expires=NULL,updated_at=? WHERE id=?''', (state, cur.lastrowid, stamp(now), batch_id))
            self.event(batch_id, 'SUBMITTED', owner, now, attempt_id=cur.lastrowid, state=state, errors=errors)
        return dict(batch_id=batch_id, attempt_id=cur.lastrowid, state=state, errors=errors)

    def frozen_attempt_rows(self, attempt, members):
        """Recheck the exact stored payload, member identities and target hashes."""
        payload = attempt['output_json']
        if not isinstance(payload, str) or source_id(payload) != attempt['sha256']:
            raise ValueError('Frozen attempt payload changed')
        stored = json.loads(payload)
        if not isinstance(stored, list):
            raise ValueError('Frozen attempt must contain a member list')
        # Keep exact canonical/hash binding, but allow a reviewer to reject a
        # target newly invalidated by a stricter QA rule. APPROVE rechecks the
        # current structural contract below; submissions remain strict too.
        rows = self.decisions('\n'.join(encoded(row) for row in stored), members, check_structure=False)
        if encoded(rows) != payload:
            raise ValueError('Frozen attempt source/target hash or canonical binding changed')
        return rows

    def review_decisions(self, raw, attempt, members):
        """Bind full or compact evidence to content exclusively from the attempt."""
        submitted = {r['source_sha256']: r for r in self.frozen_attempt_rows(attempt, members)}
        seen, reviewed = set(), []
        for row in parse_rows(raw):
            sid = row.get('source_sha256')
            original = submitted.get(sid)
            if not original or sid in seen:
                raise ValueError('Review membership changed or duplicated')
            seen.add(sid)
            full = any(key in row for key in ('source', 'translated', 'status'))
            if full:
                for key in ('source', 'translated', 'status'):
                    if row.get(key) != original[key]:
                        raise ValueError('Reviewer changed source, target or translator decision; reject and retranslate instead')
            if not full or 'translation_sha256' in row:
                if 'translation_sha256' not in row or row['translation_sha256'] != original['translation_sha256']:
                    raise ValueError('Review translation_sha256 must exactly match the frozen target (null for no target)')
            required(row.get('note'), 'Per-source semantic review evidence note')
            outcome = row.get('decision')
            if outcome not in ('APPROVE', 'REJECT', 'NEEDS_CONTEXT'):
                raise ValueError('Review decision must be APPROVE, REJECT or NEEDS_CONTEXT')
            if original['status'] == 'NEEDS_CONTEXT' and outcome == 'APPROVE':
                raise ValueError('A needs-context item cannot be approved')
            if original['status'] == 'TRANSLATED' and outcome == 'APPROVE':
                errors = structural_errors(original['source'], original['translated'])
                if original['source'] == original['translated']:
                    errors.append('unchanged_target_requires_explicit_ignore')
                if errors:
                    raise ValueError(f'{sid}: approval fails current structural QA: {errors}')
            reviewed.append(dict(original, decision=outcome, note=row['note']))
        if seen != set(submitted):
            raise ValueError('Review must cover exactly every batch member')
        return reviewed

    def review(self, batch_id, owner, token, attempt_id, review, now=None):
        raw = pathlib.Path(review).read_text(encoding='utf-8-sig')
        now = time.time() if now is None else now
        with self.transaction():
            batch = self.authorized(batch_id, owner, token, 'REVIEWING', now)
            members = self.verify_batch(batch)
            attempt = self.db.execute('SELECT * FROM attempts WHERE id=?', (batch['latest_attempt'],)).fetchone()
            if attempt['id'] != attempt_id or attempt['translator'] == owner:
                raise ValueError('Review must bind to the current attempt and a different translator identity')
            errors, outcomes = [], []
            try:
                outcomes = [row['decision'] for row in self.review_decisions(raw, attempt, members)]
            except (ValueError, TypeError, UnicodeError) as error:
                errors.append(str(error))
            state = ('REJECTED' if errors else
                     'APPROVED' if outcomes and set(outcomes) == {'APPROVE'} else
                     'PARTIALLY_APPROVED' if 'APPROVE' in outcomes else
                     'NEEDS_CONTEXT' if 'NEEDS_CONTEXT' in outcomes else 'REJECTED')
            cur = self.db.execute('''INSERT INTO reviews(batch_id,attempt_id,reviewer,created_at,raw_review,state,errors_json)
                VALUES(?,?,?,?,?,?,?)''', (batch_id, attempt_id, owner, stamp(now), raw, state, encoded(errors)))
            self.db.execute('''UPDATE batches SET state=?,approved_review=?,owner=NULL,lease_token=NULL,
                lease_expires=NULL,updated_at=? WHERE id=?''', (state, cur.lastrowid if state in ('APPROVED', 'PARTIALLY_APPROVED') else None, stamp(now), batch_id))
            self.event(batch_id, 'REVIEWED', owner, now, review_id=cur.lastrowid, attempt_id=attempt_id, state=state, errors=errors)
        return dict(batch_id=batch_id, review_id=cur.lastrowid, state=state, errors=errors)

    def reopen(self, batch_id, coordinator, reason):
        required(reason, 'Reopen reason')
        with self.transaction():
            self.coordinator(coordinator)
            batch = self.batch(batch_id)
            if batch['state'] not in ('APPROVED', 'PARTIALLY_APPROVED', 'NEEDS_CONTEXT', 'REJECTED'):
                raise ValueError('Only resolved/rejected batches can be reopened')
            self.verify_batch(batch)
            self.db.execute("UPDATE batches SET state='READY',approved_review=NULL,updated_at=? WHERE id=?", (stamp(time.time()), batch_id))
            self.event(batch_id, 'REOPENED', coordinator, reason=reason)
        return dict(batch_id=batch_id, state='READY')

    def export(self, output, coordinator):
        """Produce an exclusive, validated review-import file; never import it."""
        output = pathlib.Path(output).resolve()
        manifest = output.with_suffix(output.suffix + '.manifest.json')
        with self.transaction():
            self.coordinator(coordinator)
            self.check_snapshot()
            rows, pending = [], {}
            for source in self.db.execute('SELECT * FROM sources WHERE active=1 ORDER BY ordinal'):
                pending[source['sha256']] = dict(source_sha256=source['sha256'], batch_id=None, state='UNBATCHED')
            for batch in self.db.execute("SELECT * FROM batches WHERE state!='INVALIDATED' ORDER BY rowid").fetchall():
                for member in self.db.execute('SELECT * FROM members WHERE batch_id=?', (batch['id'],)):
                    pending[member['source_sha256']] = dict(source_sha256=member['source_sha256'], batch_id=batch['id'], state=batch['state'])
                if batch['state'] not in ('APPROVED', 'PARTIALLY_APPROVED'):
                    if batch['latest_attempt']:
                        proposal = self.db.execute('SELECT * FROM attempts WHERE id=?', (batch['latest_attempt'],)).fetchone()
                        if proposal['output_json']:
                            for row in json.loads(proposal['output_json']):
                                pending[row['source_sha256']].update(proposal=row['status'], reason=row['reason'])
                            evidence = self.db.execute('SELECT * FROM reviews WHERE attempt_id=? ORDER BY id DESC LIMIT 1', (proposal['id'],)).fetchone()
                            if evidence and not json.loads(evidence['errors_json']):
                                for row in parse_rows(evidence['raw_review']):
                                    pending[row['source_sha256']].update(decision=row['decision'], note=row['note'])
                    continue
                members = self.verify_batch(batch)
                attempt = self.db.execute('SELECT * FROM attempts WHERE id=?', (batch['latest_attempt'],)).fetchone()
                review = self.db.execute('SELECT * FROM reviews WHERE id=?', (batch['approved_review'],)).fetchone()
                if not review or review['state'] != batch['state'] or review['attempt_id'] != attempt['id'] or review['reviewer'] == attempt['translator']:
                    raise ValueError('Approval does not bind to the active attempt/independent reviewer')
                for row in self.review_decisions(review['raw_review'], attempt, members):
                    evidence = row
                    if evidence['decision'] != 'APPROVE':
                        pending[row['source_sha256']].update(decision=evidence['decision'], note=evidence['note'], reason=row['reason'])
                        continue
                    state = row['status']
                    if state not in ('TRANSLATED', 'IGNORE'):
                        raise ValueError('Unresolved decision cannot be exported')
                    if state == 'TRANSLATED' and structural_errors(row['source'], row['translated']):
                        raise ValueError('Approved output no longer passes structural QA')
                    rows.append(dict(source=row['source'], source_sha256=row['source_sha256'], translated=row['translated'],
                        status=state.lower(), reason=row['reason'], translation_source_sha256=row['source_sha256'] if state == 'TRANSLATED' else None,
                        translation_sha256=row['translation_sha256'], workflow_batch_id=batch['id'], workflow_attempt_id=attempt['id'],
                        workflow_review_id=review['id'], translator=attempt['translator'], reviewer=review['reviewer'],
                        review_note=evidence['note'], reviewed_at=review['created_at'],
                        quality='source_reviewed' if state == 'TRANSLATED' else 'ignore'))
                    pending.pop(row['source_sha256'], None)
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.exists() or manifest.exists():
                raise FileExistsError('Export or companion manifest already exists; choose a new output name')
            # Never overwrite a previous coordinator handoff or any catalog.
            with output.open('x', encoding='utf-8', newline='\n') as stream:
                for row in rows:
                    stream.write(encoded(row) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            output_sha = digest(output)
            snapshot = self.db.execute('SELECT * FROM snapshots ORDER BY id DESC LIMIT 1').fetchone()
            inventory = dict(output=str(output), output_sha256=output_sha, created_at=stamp(time.time()), coordinator=coordinator,
                inventory=dict(path=snapshot['path'], sha256=snapshot['sha256'], active_sources=len(rows) + len(pending)),
                exported=[dict(source_sha256=r['source_sha256'], translation_sha256=r['translation_sha256'], batch_id=r['workflow_batch_id'],
                               attempt_id=r['workflow_attempt_id'], review_id=r['workflow_review_id'], status=r['status']) for r in rows],
                pending=list(pending.values()))
            with manifest.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(json.dumps(inventory, ensure_ascii=False, indent=2) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            self.event(None, 'EXPORTED', coordinator, path=str(output), sha256=output_sha, manifest=str(manifest), sources=len(rows), pending_sources=len(pending))
        return dict(output=str(output), manifest=str(manifest), sources=len(rows), pending_sources=len(pending), sha256=output_sha,
                    policy='Only explicit per-source approvals are exported. Coordinator must separately inspect and import; structural QA alone never grants semantic approval')

    def status(self):
        counts = {state: 0 for state in STATES}
        counts.update({r['state']: r['n'] for r in self.db.execute('SELECT state,count(*) n FROM batches GROUP BY state')})
        return dict(states=counts, active_sources=self.db.execute('SELECT count(*) FROM sources WHERE active=1').fetchone()[0],
                    attempts=self.db.execute('SELECT count(*) FROM attempts').fetchone()[0], reviews=self.db.execute('SELECT count(*) FROM reviews').fetchone()[0])

    def history(self, batch_id):
        self.batch(batch_id)
        return {name: [dict(r) for r in self.db.execute(f'SELECT * FROM {name} WHERE batch_id=? ORDER BY id', (batch_id,))]
                for name in ('attempts', 'reviews', 'events')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Protocol:
  refresh --coordinator coordinator
  batch --directory work/orchestration/batches
  claim --stage TRANSLATE --owner translator-a
  submit --batch-id ID --owner translator-a --token TOKEN --file draft.ndjson
  claim --stage REVIEW --owner reviewer-b
  review --batch-id ID --owner reviewer-b --token TOKEN --attempt-id N --file review.ndjson
  export --owner coordinator --out work/orchestration/approved-001.ndjson

Draft NDJSON: preserve source/source_sha256; set status TRANSLATED with translated,
or IGNORE/NEEDS_CONTEXT with translated:null and an explicit reason. No automated
ignore inference or translation is performed. Preserve tags, placeholders, CJK
technical tokens, paths, @p/@t, image payloads and literal/actual newline forms.
Review NDJSON: copy the exact draft source/source_sha256/status/translated; add
decision APPROVE/REJECT/NEEDS_CONTEXT and a per-source semantic evidence note.
Compact review NDJSON may instead contain only source_sha256,
translation_sha256, decision and note. Copy both hashes from the claimed attempt;
translation_sha256 must be null for IGNORE/NEEDS_CONTEXT with no target. Every
member must occur exactly once. Full and compact rows may be mixed. Content is
hydrated only from the specified frozen attempt after exact hash, membership and
structural checks; a compact row never supplies replacement source/target text.
The reviewer must differ from the translator. REJECT or changed content removes
approval; edited targets require a new translation attempt. Mixed valid reviews
produce PARTIALLY_APPROVED; export emits only explicit APPROVE rows plus a
companion manifest listing all exported/pending source hashes and unresolved
decisions. Only use an export with its matching manifest/output SHA. Coordinator
reopen clears all batch approvals for a new attempt;
refresh after imports re-batches remaining sources. Export requires configured
coordinator identity and produces review-import schema without changing catalogs.
Identity strings are accountability labels, not OS authentication. Never share
identities across translator/reviewer roles. Batch inputs are exclusive, immutable
files checked by SHA. --live-owner supplies external live-owner verification and
blocks both automatic expiry recovery and explicit reclaim; no process is probed.
Each lease requires its opaque token; heartbeat before expiry. Use history for
retained attempts, evidence and audit events. No network or provider is used.''')
    parser.add_argument('--db', default='work/orchestration/batches.sqlite3')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('refresh', help='Initialize/refresh exact source inventory; invalidate obsolete approvals')
    p.add_argument('--remaining', default='work/review/remaining.ndjson')
    p.add_argument('--coordinator', required=True)
    p = sub.add_parser('batch', help='Create bounded immutable inputs, missing translations first')
    p.add_argument('--directory', default='work/orchestration/batches')
    p.add_argument('--max-chars', type=int, default=12000)
    p.add_argument('--max-count', type=int, default=60)
    p.add_argument('--max-batches', type=int, default=0)
    p = sub.add_parser('claim', help='Atomically lease work; expired owners are not presumed dead')
    p.add_argument('--stage', choices=['TRANSLATE', 'REVIEW'], required=True)
    p.add_argument('--owner', required=True)
    p.add_argument('--batch-id')
    p.add_argument('--lease-seconds', type=int, default=1800)
    p.add_argument('--live-owner', action='append', default=[])
    for command in ('heartbeat', 'submit', 'review'):
        p = sub.add_parser(command)
        p.add_argument('--batch-id', required=True)
        p.add_argument('--owner', required=True)
        p.add_argument('--token', required=True)
        if command == 'heartbeat':
            p.add_argument('--lease-seconds', type=int, default=1800)
        else:
            p.add_argument('--file', required=True)
        if command == 'review':
            p.add_argument('--attempt-id', type=int, required=True)
    for command in ('reclaim', 'reopen'):
        p = sub.add_parser(command, help='Explicit coordinator action; requires reason')
        p.add_argument('--batch-id', required=True)
        p.add_argument('--owner', required=True)
        p.add_argument('--reason', required=True)
        if command == 'reclaim':
            p.add_argument('--live-owner', action='append', default=[])
    p = sub.add_parser('export', help='Coordinator-only approved review export, never a catalog import')
    p.add_argument('--owner', required=True)
    p.add_argument('--out', required=True)
    sub.add_parser('status')
    p = sub.add_parser('history')
    p.add_argument('--batch-id', required=True)
    args = parser.parse_args(argv)
    workflow = Workflow(args.db)
    try:
        command = args.command
        if command == 'refresh':
            result = workflow.refresh(args.remaining, args.coordinator)
        elif command == 'batch':
            result = workflow.make_batches(args.directory, args.max_chars, args.max_count, args.max_batches)
        elif command == 'claim':
            result = workflow.claim(args.stage, args.owner, args.lease_seconds, args.batch_id, args.live_owner)
        elif command == 'heartbeat':
            result = workflow.heartbeat(args.batch_id, args.owner, args.token, args.lease_seconds)
        elif command == 'submit':
            result = workflow.submit(args.batch_id, args.owner, args.token, args.file)
        elif command == 'review':
            result = workflow.review(args.batch_id, args.owner, args.token, args.attempt_id, args.file)
        elif command == 'reclaim':
            result = workflow.reclaim(args.batch_id, args.owner, args.reason, args.live_owner)
        elif command == 'reopen':
            result = workflow.reopen(args.batch_id, args.owner, args.reason)
        elif command == 'export':
            result = workflow.export(args.out, args.owner)
        elif command == 'history':
            result = workflow.history(args.batch_id)
        else:
            result = workflow.status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if isinstance(result, dict) and result.get('errors') else 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(json.dumps(dict(error=str(error)), ensure_ascii=False))
        return 2
    finally:
        workflow.close()


if __name__ == '__main__':
    raise SystemExit(main())
