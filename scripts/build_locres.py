#!/usr/bin/env python3
"""Generate a UE locres file from an NDJSON translation catalog."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable
from zlib import crc32

try:
    from pylocres import LocresFile, Namespace, Entry
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "Missing dependency 'pylocres'. Install with: pip install pylocres"
    ) from exc

try:
    from opencc import OpenCC
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "Missing dependency 'opencc-python-reimplemented'. Install with:\n"
        "  pip install opencc-python-reimplemented"
    ) from exc


def normalize_crlf(text: str) -> str:
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", "\r\n")


def hash_utf32le(text: str) -> int:
    return crc32(text.encode("utf-32-le")) & 0xFFFFFFFF


def compute_source_hash(source: str, converter: OpenCC) -> int:
    normalized = normalize_crlf(source)
    simplified = converter.convert(normalized)
    return hash_utf32le(simplified)


def build_locres(entries: Iterable[dict], output_path: Path) -> int:
    converter = OpenCC("t2s")
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

        if not isinstance(translated, str) or not translated.strip():
            continue

        target = normalize_crlf(str(translated))

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
            src_hash = compute_source_hash(str(source), converter)

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
