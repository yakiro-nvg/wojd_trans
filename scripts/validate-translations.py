#!/usr/bin/env python3
"""
Validate translations for placeholder and tag consistency.
Detects when translated text contains placeholders/tags not present in source.
"""

import json
import re
import sys
from pathlib import Path

def extract_placeholders(text):
    """Extract all placeholder patterns from text."""
    if not text:
        return set()

    patterns = set()

    # ${...} placeholders
    patterns.update(re.findall(r'\$\{[^}]+\}', text))

    # {...} placeholders (but not color markers)
    for m in re.findall(r'\{[^}]+\}', text):
        if not m.startswith('{##'):  # Skip color markers
            patterns.add(m)

    return patterns

def extract_tags(text):
    """Extract all XML-like tags from text."""
    if not text:
        return set()

    # <...> tags, but filter out comparison operators like <25, >100
    tags = set()
    for match in re.findall(r'<[^>]+>', text):
        # Skip if it looks like a comparison operator (starts with number or comparison)
        inner = match[1:-1].strip()
        if inner and (inner[0].isdigit() or inner.startswith('=') or inner.startswith('!')):
            continue
        tags.add(match)
    return tags

def validate_file(filepath):
    """Validate translations in a single NDJSON file."""
    issues = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            translated = entry.get('translated', '')
            source = entry.get('source', '')
            locres = entry.get('locresImport', '')

            # Use locresImport as fallback source
            src_text = source if source else locres

            if not translated or not src_text:
                continue

            ns = entry.get('namespace', '')
            key = entry.get('key', '')

            # Check placeholders
            src_placeholders = extract_placeholders(src_text)
            trans_placeholders = extract_placeholders(translated)

            # Find placeholders in translation that aren't in source
            extra_placeholders = trans_placeholders - src_placeholders

            # Filter out false positives (spaces inside placeholders that match source without space)
            for ep in list(extra_placeholders):
                # Check if it's a spaced version of a source placeholder
                normalized = re.sub(r'\s+', '', ep)
                if normalized in [re.sub(r'\s+', '', sp) for sp in src_placeholders]:
                    issues.append({
                        'file': filepath.name,
                        'line': line_num,
                        'ns': ns,
                        'key': key,
                        'type': 'spaced_placeholder',
                        'value': ep,
                        'source': src_text[:60]
                    })
                elif ep not in src_placeholders:
                    issues.append({
                        'file': filepath.name,
                        'line': line_num,
                        'ns': ns,
                        'key': key,
                        'type': 'extra_placeholder',
                        'value': ep,
                        'source': src_text[:60]
                    })

            # Check for missing placeholders
            missing_placeholders = src_placeholders - trans_placeholders
            # Also check spaced versions
            for mp in list(missing_placeholders):
                spaced = re.sub(r'(\d)', r' \1', mp)
                if spaced in trans_placeholders:
                    missing_placeholders.discard(mp)

            for mp in missing_placeholders:
                issues.append({
                    'file': filepath.name,
                    'line': line_num,
                    'ns': ns,
                    'key': key,
                    'type': 'missing_placeholder',
                    'value': mp,
                    'source': src_text[:60]
                })

            # Check tags
            src_tags = extract_tags(src_text)
            trans_tags = extract_tags(translated)

            extra_tags = trans_tags - src_tags
            for et in extra_tags:
                issues.append({
                    'file': filepath.name,
                    'line': line_num,
                    'ns': ns,
                    'key': key,
                    'type': 'extra_tag',
                    'value': et,
                    'source': src_text[:60]
                })

            missing_tags = src_tags - trans_tags
            for mt in missing_tags:
                issues.append({
                    'file': filepath.name,
                    'line': line_num,
                    'ns': ns,
                    'key': key,
                    'type': 'missing_tag',
                    'value': mt,
                    'source': src_text[:60]
                })

    return issues

def main():
    translations_dir = Path(__file__).parent.parent / 'translations'

    all_issues = []

    for ndjson_file in translations_dir.glob('*.ndjson'):
        print(f"Validating {ndjson_file.name}...")
        issues = validate_file(ndjson_file)
        all_issues.extend(issues)

    if not all_issues:
        print("\nNo issues found!")
        return 0

    # Group by type
    by_type = {}
    for issue in all_issues:
        t = issue['type']
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(issue)

    print(f"\n=== Found {len(all_issues)} issues ===\n")

    for issue_type, issues in by_type.items():
        print(f"\n{issue_type.upper()} ({len(issues)} issues):")
        for i in issues[:10]:
            print(f"  {i['file']}:{i['line']} - {i['ns']}:{i['key']}")
            print(f"    Value: {i['value']}")
            print(f"    Source: {i['source']}...")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more")

    return 1 if all_issues else 0

if __name__ == '__main__':
    sys.exit(main())
