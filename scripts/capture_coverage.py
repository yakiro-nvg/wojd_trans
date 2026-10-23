"""Measure exact-source native capture coverage for a paired UE log.

Only the original native ``source`` field is evidence. Targets, route names and
literal equality do not prove a .data origin or coverage outside these captures.
Reports contain source SHA-256 values, never source/target prose or input paths.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile

from ue_log import iter_misses

SHA256 = re.compile(r'[0-9a-f]{64}\Z')
# Labels are recorded, not whitelisted as evidence of an origin or coverage.
ROUTE_LABEL = re.compile(r'[A-Za-z_][A-Za-z0-9_.:-]{0,127}\Z')


class CaptureInputError(ValueError):
    """A machine-readable input failure that never echoes capture contents."""

    def __init__(self, kind, code, line=None):
        self.kind, self.code, self.line = kind, code, line
        self.inputs = {}
        super().__init__(f'{kind}: {code}' + (f' at line {line}' if line else ''))

    def evidence(self):
        result = dict(input=self.kind, code=self.code)
        if self.line is not None:
            result['line'] = self.line
        return result


def _fingerprint(path, kind):
    value = hashlib.sha256()
    size = 0
    try:
        with path.open('rb') as stream:
            while block := stream.read(1024 * 1024):
                value.update(block)
                size += len(block)
    except OSError:
        raise CaptureInputError(kind, 'UNREADABLE_INPUT') from None
    return dict(sha256=value.hexdigest(), bytes=size)


def _source_hash(source, kind, line, allow_empty=False):
    if not isinstance(source, str) or (not source and not allow_empty):
        raise CaptureInputError(kind, 'SOURCE_MISSING_OR_EMPTY', line)
    try:
        return hashlib.sha256(source.encode('utf-8')).hexdigest()
    except UnicodeError:
        raise CaptureInputError(kind, 'INVALID_SOURCE_UNICODE', line) from None


def _ndjson(path, kind):
    try:
        # No universal-newline conversion: exact source strings are significant.
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for line, text in enumerate(stream, 1):
                if not text.strip():
                    continue
                try:
                    row = json.loads(text)
                except ValueError:
                    raise CaptureInputError(kind, 'INVALID_JSON', line) from None
                if not isinstance(row, dict):
                    raise CaptureInputError(kind, 'EXPECTED_OBJECT', line)
                yield line, row
    except UnicodeError:
        raise CaptureInputError(kind, 'INVALID_UTF8') from None
    except OSError:
        raise CaptureInputError(kind, 'UNREADABLE_INPUT') from None


def _checked_hash(row, source_hash, kind, line):
    if 'source_sha256' in row:
        supplied = row['source_sha256']
        if not isinstance(supplied, str) or not SHA256.fullmatch(supplied):
            raise CaptureInputError(kind, 'INVALID_SOURCE_SHA256', line)
        if source_hash is not None and supplied != source_hash:
            raise CaptureInputError(kind, 'SOURCE_HASH_MISMATCH', line)
        return supplied
    return source_hash


def _native_sources(path):
    sources = set()
    route_rows = collections.Counter()
    route_sources = collections.defaultdict(set)
    count = 0
    for line, row in _ndjson(path, 'native_capture'):
        sid = _source_hash(row.get('source'), 'native_capture', line)
        _checked_hash(row, sid, 'native_capture', line)
        route = row.get('route')
        if not isinstance(route, str) or not ROUTE_LABEL.fullmatch(route):
            raise CaptureInputError('native_capture', 'ROUTE_MISSING_OR_INVALID', line)
        count += 1
        sources.add(sid)
        route_rows[route] += 1
        route_sources[route].add(sid)
    routes = {route: dict(rows=route_rows[route], unique_sources=len(route_sources[route]))
              for route in sorted(route_rows)}
    return sources, count, routes


def _expected_sources(path):
    sources = set()
    count = 0
    for line, row in _ndjson(path, 'expected_inventory'):
        sid = (_source_hash(row['source'], 'expected_inventory', line)
               if 'source' in row else None)
        sid = _checked_hash(row, sid, 'expected_inventory', line)
        if sid is None:
            raise CaptureInputError('expected_inventory', 'SOURCE_OR_SHA256_REQUIRED', line)
        sources.add(sid)
        count += 1
    return sources, count


def analyze_coverage(ue_log, native_capture, expected=None, strict_global=False):
    """Return bounded evidence; invalid native/inventory inputs raise safely.

    Without an inventory every exact source yielded by iter_misses is required.
    With one, the ordinary gate considers only required sources also observed
    in this UE log. Strict global additionally requires native evidence for all
    inventory sources, even those absent from the paired UE log.
    """
    paths = dict(ue_log=pathlib.Path(ue_log), native_capture=pathlib.Path(native_capture))
    if expected is not None:
        paths['expected_inventory'] = pathlib.Path(expected)
    inputs = {}
    try:
        for kind, path in paths.items():
            inputs[kind] = _fingerprint(path, kind)
        native, native_rows, routes = _native_sources(paths['native_capture'])
        stats = collections.Counter()
        kinds = collections.Counter()
        observed = set()
        identity_sources = set()
        empty_source_events = 0
        try:
            for row in iter_misses(paths['ue_log'], stats):
                # An empty source is a valid UE diagnostic. Keep its exact SHA;
                # an explicit required inventory decides whether it is relevant.
                sid = _source_hash(row['source'], 'ue_log', row['log_line'], allow_empty=True)
                empty_source_events += row['source'] == ''
                observed.add(sid)
                identity_sources.add((row['namespace'], row['key'], sid))
                kinds[row['diagnostic_kind']] += 1
        except UnicodeError:
            raise CaptureInputError('ue_log', 'INVALID_UTF8') from None
        except OSError:
            raise CaptureInputError('ue_log', 'UNREADABLE_INPUT') from None
        if expected is not None:
            required, expected_rows = _expected_sources(paths['expected_inventory'])
        else:
            required, expected_rows = set(observed), None
        for kind, path in paths.items():
            if _fingerprint(path, kind) != inputs[kind]:
                raise CaptureInputError(kind, 'INPUT_CHANGED_DURING_ANALYSIS')
    except CaptureInputError as error:
        error.inputs = inputs
        raise

    required_observed = required & observed
    covered = required_observed & native
    missing = required_observed - native
    not_observed = required - observed
    global_missing = required - native
    parser_errors = stats.get('unparsed_missing_records', 0)
    if parser_errors:
        state, gate = 'INVALID_INPUT', 'NOT_EVALUATED'
    elif missing or (strict_global and global_missing):
        state, gate = 'COVERAGE_GAP', 'FAIL'
    elif not required_observed:
        state, gate = 'NO_REQUIRED_UE_OBSERVATIONS', 'NOT_EXERCISED'
    else:
        state, gate = 'REQUIRED_OBSERVED_COVERED', 'PASS'
    denominator = len(required_observed)
    return dict(
        state=state,
        inputs=inputs,
        scope=dict(
            required_set='EXPLICIT_INVENTORY' if expected is not None else 'CURRENT_UE_OBSERVED',
            comparison='EXACT_ORIGINAL_SOURCE_UTF8_SHA256',
            native_evidence_field='source',
            target_used_as_evidence=False,
            origin_inference='NONE',
            route_labels_are_coverage_proof=False,
            all_game_coverage_claimed=False,
            client_verified=False,
        ),
        parser=dict(
            implementation='ue_log.iter_misses',
            implementation_sha256=_fingerprint(pathlib.Path(__file__).with_name('ue_log.py'), 'ue_parser')['sha256'],
            stats=dict(sorted(stats.items())),
            diagnostic_events=dict(sorted(kinds.items())),
            errors=parser_errors,
        ),
        native=dict(rows=native_rows, unique_sources=len(native), routes=routes),
        counts=dict(
            ue_observed_unique_sources=len(observed),
            ue_observed_identity_sources=len(identity_sources),
            ue_empty_source_events=empty_source_events,
            required_inventory_rows=expected_rows,
            required_unique_sources=len(required),
            required_and_ue_observed=len(required_observed),
            required_observed_captured=len(covered),
            required_observed_missing_native=len(missing),
            required_not_ue_observed=len(not_observed),
            required_not_ue_observed_missing_native=len(not_observed - native),
            required_global_missing_native=len(global_missing),
            ue_observed_outside_required=len(observed - required),
            all_ue_observed_captured=len(observed & native),
        ),
        coverage=dict(
            scope='REQUIRED_AND_UE_OBSERVED_ONLY',
            numerator=len(covered),
            denominator=denominator,
            percent=(100.0 * len(covered) / denominator) if denominator else None,
        ),
        gate=dict(
            status=gate,
            strict_global=bool(strict_global),
            required_observed_missing_native=len(missing),
            strict_global_missing_native=len(global_missing) if strict_global else None,
            errors=([dict(input='ue_log', code='UNPARSED_LOCALIZATION_RECORDS', count=parser_errors)]
                    if parser_errors else []),
        ),
        gaps=[dict(source_sha256=sid, status='MISSING_NATIVE_CURRENT_UE_OBSERVED')
              for sid in sorted(missing)],
        not_observed=[dict(source_sha256=sid, status='NOT_OBSERVED', native_source_observed=sid in native)
                      for sid in sorted(not_observed)],
        global_missing_native_sha256=sorted(global_missing) if strict_global else None,
    )


def _write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=path.parent, prefix=path.name + '.', suffix='.tmp',
                                         delete=False) as stream:
            temporary = pathlib.Path(stream.name)
            json.dump(report, stream, ensure_ascii=True, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ue-log', required=True, type=pathlib.Path)
    parser.add_argument('--native-capture', '--rawdata', required=True, type=pathlib.Path)
    parser.add_argument('--expected', type=pathlib.Path,
                        help='NDJSON source and/or source_sha256 inventory; no source normalization')
    parser.add_argument('--strict-global', action='store_true',
                        help='Also fail expected sources missing native evidence when not observed in UE')
    parser.add_argument('--out', type=pathlib.Path, help='JSON report; defaults to stdout')
    args = parser.parse_args(argv)
    inputs = [args.ue_log, args.native_capture] + ([args.expected] if args.expected else [])
    if args.out and args.out.resolve() in {p.resolve() for p in inputs}:
        report = dict(state='INVALID_INPUT', gate=dict(status='NOT_EVALUATED'),
                      errors=[dict(input='output', code='OUTPUT_OVERLAPS_INPUT')])
        print(json.dumps(report, indent=2))
        return 2
    try:
        report = analyze_coverage(args.ue_log, args.native_capture, args.expected, args.strict_global)
    except CaptureInputError as error:
        report = dict(state='INVALID_INPUT', inputs=error.inputs,
                      gate=dict(status='NOT_EVALUATED'), errors=[error.evidence()])
    if args.out:
        _write_report(args.out, report)
    else:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    if report['state'] == 'INVALID_INPUT':
        return 2
    return 1 if report['gate']['status'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
