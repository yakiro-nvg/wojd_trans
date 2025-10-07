#!/usr/bin/env python3
"""Import/sync locres entries into the NDJSON catalog."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, Tuple
from zlib import crc32

try:
    from pylocres import LocresFile
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_converter: OpenCC | None = None


def _get_converter() -> OpenCC:
    global _converter
    if _converter is None:
        _converter = OpenCC("t2s")
    return _converter


def _normalize_crlf(text: str) -> str:
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", "\r\n")


def _hash_utf32le(text: str) -> int:
    return crc32(text.encode("utf-32-le")) & 0xFFFFFFFF


def compute_catalog_hash(source: str) -> int:
    normalized = _normalize_crlf(source)
    simplified = _get_converter().convert(normalized)
    return _hash_utf32le(simplified)


def _entry_text(entry) -> str:
    for attr in ("text", "translation", "value", "string"):
        if hasattr(entry, attr):
            value = getattr(entry, attr)
            if isinstance(value, str):
                return value
    return ""


def _entry_hash(entry) -> int:
    for attr in ("source_hash", "hash", "SourceHash"):
        if hasattr(entry, attr):
            value = getattr(entry, attr)
            try:
                return int(value)
            except Exception:
                pass
    raise AttributeError("Locres entry missing source_hash attribute")


def read_locres(path: Path) -> Iterable[Tuple[str, str, str, int]]:
    loc = LocresFile()
    loc.read(str(path))

    for ns in loc:
        ns_name = getattr(ns, "name", "") or ""
        for entry in ns:
            key = getattr(entry, "key", "")
            if not key:
                continue
            text = _normalize_crlf(_entry_text(entry))
            source_hash = _entry_hash(entry)
            yield ns_name, str(key), text, source_hash


def read_catalog(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:  # pragma: no cover
                raise RuntimeError(f"Invalid JSON at line {line_number} of {path}: {exc}") from exc
            if not isinstance(record, dict):
                continue
            record.setdefault("source", None)
            record.setdefault("translated", None)
            if "locres" in record and record.get("locres") is not None:
                record["locresImport"] = record.pop("locres")
            record.setdefault("locresImport", None)
            if "hashOverride" in record and record.get("hashOverride") is not None:
                record["importedHash"] = record.pop("hashOverride")
            if "importedHash" in record and record["importedHash"] is not None:
                try:
                    record["importedHash"] = int(str(record["importedHash"]), 0)
                except Exception:
                    record["importedHash"] = None
            rows.append(record)
    return rows


def write_catalog(path: Path, rows: Iterable[dict]) -> None:
    sorted_rows = sorted(
        rows,
        key=lambda r: ((r.get("namespace") or ""), r.get("key") or ""),
    )
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in sorted_rows:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def index_catalog(rows: list[dict]) -> Dict[Tuple[str, str], int]:
    index: Dict[Tuple[str, str], int] = {}
    for idx, row in enumerate(rows):
        ns = (row.get("namespace") or "").strip()
        key = (row.get("key") or "").strip()
        if not key:
            continue
        pair = (ns, key)
        if pair not in index:
            index[pair] = idx
    return index


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import locres into NDJSON catalog")
    parser.add_argument("--locres", required=True, help="Path to Game.locres")
    parser.add_argument("--catalog", required=True, help="Path to catalog NDJSON (updated in place)")
    if argv is None:
        return parser.parse_args()
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    locres_path = Path(args.locres)
    catalog_path = Path(args.catalog)

    if not locres_path.is_file():
        raise RuntimeError(f"Locres file not found: {locres_path}")
    if catalog_path.exists():
        rows = read_catalog(catalog_path)
    else:
        rows = []
    index = index_catalog(rows)

    added = updated = skipped = 0

    for namespace, key, target, source_hash in read_locres(locres_path):
        pair = (namespace, key)
        if pair in index:
            row = rows[index[pair]]
            source = row.get("source")
            if isinstance(source, str) and source.strip():
                calculated = compute_catalog_hash(source)
                if calculated == source_hash:
                    row["locresImport"] = target
                    row.pop("importedHash", None)
                    updated += 1
                else:
                    skipped += 1
            else:
                # No source stored; nothing to compare
                skipped += 1
        else:
            rows.append(
                {
                    "namespace": namespace,
                    "key": key,
                    "source": None,
                    "translated": None,
                    "locresImport": target,
                    "importedHash": int(source_hash),
                }
            )
            index[pair] = len(rows) - 1
            added += 1

    write_catalog(catalog_path, rows)
    print(f"Import summary: updated {updated}, added {added}, skipped {skipped}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
