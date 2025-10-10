#!/usr/bin/env python3
"""Generate a UE locres file from an NDJSON translation catalog."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from zlib import crc32

try:
    from pylocres import LocresFile, Namespace, Entry
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "Missing dependency 'pylocres'. Install with: pip install pylocres"
    ) from exc

SkipRule = Tuple[str, Optional[re.Pattern[str]]]
_cached_rules: Optional[List[SkipRule]] = None


def load_skip_rules() -> List[SkipRule]:
    global _cached_rules  # noqa: PLW0603 -- cache is module-level by design
    if _cached_rules is not None:
        return _cached_rules

    config_path = Path(__file__).resolve().parent.parent / "config" / "translation-skip.json"
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _cached_rules = []
        return _cached_rules

    rules: List[SkipRule] = []
    for entry in raw.get("rules", []):
        namespace = entry.get("namespace")
        if not namespace:
            continue
        regex_value = entry.get("keyRegex")
        pattern = re.compile(regex_value) if isinstance(regex_value, str) else None
        rules.append((namespace, pattern))

    _cached_rules = rules
    return rules


def should_skip_translation(namespace: str, key: str) -> bool:
    if not namespace:
        return False
    for rule_namespace, pattern in load_skip_rules():
        if rule_namespace != namespace:
            continue
        if pattern is None:
            return True
        if key is not None and pattern.search(key):
            return True
    return False


def normalize_crlf(text: str) -> str:
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", "\r\n")


def hash_utf32le(text: str) -> int:
    return crc32(text.encode("utf-32-le")) & 0xFFFFFFFF


def compute_source_hash(source: str) -> int:
    normalized = normalize_crlf(source)
    return hash_utf32le(normalized)


def build_locres(entries: Iterable[dict], output_path: Path) -> int:
    loc = LocresFile()

    namespace_map: Dict[str, Namespace] = {}
    total_entries = 0

    for entry in entries:
        namespace = entry.get("namespace", "")
        key = entry.get("key")
        source = entry.get("source")
        translated = entry.get("translated")
        locres_override = entry.get("locresImport")
        hash_override = entry.get("importedHash")

        if not key:
            continue

        if should_skip_translation(str(namespace), str(key)):
            translated = None

        if translated is None:
            continue

        if not isinstance(translated, str):
            continue

        target = normalize_crlf(translated)

        if namespace not in namespace_map:
            namespace_map[namespace] = Namespace(namespace)

        if hash_override is not None:
            try:
                src_hash = int(str(hash_override), 0) & 0xFFFFFFFF
            except (TypeError, ValueError):
                continue
        else:
            if not source:
                continue
            src_hash = compute_source_hash(str(source))

        namespace_map[namespace].add(Entry(key, target, src_hash))
        total_entries += 1

    for namespace in namespace_map.values():
        loc.add(namespace)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    loc.write(str(output_path))
    return total_entries


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build UE locres from NDJSON catalog")
    parser.add_argument("--input", required=True, help="Path to translations NDJSON file")
    parser.add_argument("--output", required=True, help="Path to output Game.locres")
    return parser.parse_args(argv)


def iter_catalog_lines(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Invalid JSON on line {line_number} of {path}: {exc}"
                ) from exc


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    catalog_path = Path(args.input)
    output_path = Path(args.output)

    if not catalog_path.is_file():
        raise RuntimeError(f"Catalog not found: {catalog_path}")

    entries = list(iter_catalog_lines(catalog_path))
    total = build_locres(entries, output_path)
    print(f"Wrote {total} entries to {output_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
