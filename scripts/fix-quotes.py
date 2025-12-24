#!/usr/bin/env python3
"""
Detect and fix quote style mismatches between source and translated text.
Ensures translations use the same quote style as the source.
"""

import json
import re
import sys
from pathlib import Path

# Quote mappings
CURLY_TO_STRAIGHT = {
    '\u201c': '"',  # Left double curly quote
    '\u201d': '"',  # Right double curly quote
    '\u2018': "'",  # Left single curly quote
    '\u2019': "'",  # Right single curly quote
}

def get_quote_style(text):
    """Detect quote style used in text."""
    if not text:
        return None

    has_straight_double = '"' in text
    has_straight_single = "'" in text
    has_escaped_double = '\\"' in text
    has_curly = any(q in text for q in CURLY_TO_STRAIGHT.keys())

    return {
        'straight_double': has_straight_double,
        'straight_single': has_straight_single,
        'escaped_double': has_escaped_double,
        'curly': has_curly
    }

def fix_quotes_to_match_source(source, translated):
    """Fix translated text to match source quote style."""
    if not source or not translated:
        return translated

    result = translated

    # Always replace curly quotes with straight quotes first
    for curly, straight in CURLY_TO_STRAIGHT.items():
        result = result.replace(curly, straight)

    return result

def process_file(filepath, fix=False):
    """Process a single NDJSON file."""
    issues = []
    fixed_count = 0
    fixed_lines = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                fixed_lines.append('')
                continue

            try:
                entry = json.loads(line)
                translated = entry.get('translated', '')
                source = entry.get('source', '')
                locres = entry.get('locresImport', '')

                src_text = source if source else locres

                if translated and src_text:
                    # Check for curly quotes in translated
                    has_curly = any(q in translated for q in CURLY_TO_STRAIGHT.keys())

                    if has_curly:
                        issues.append({
                            'file': filepath.name,
                            'line': line_num,
                            'ns': entry.get('namespace', ''),
                            'key': entry.get('key', ''),
                            'translated_snippet': translated[:60]
                        })

                        if fix:
                            fixed_translated = fix_quotes_to_match_source(src_text, translated)
                            if fixed_translated != translated:
                                fixed_count += 1
                                entry['translated'] = fixed_translated

                fixed_lines.append(json.dumps(entry, ensure_ascii=False))
            except:
                fixed_lines.append(line)

    if fix and fixed_count > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(fixed_lines))
            if fixed_lines and fixed_lines[-1]:
                f.write('\n')

    return issues, fixed_count

def main():
    fix_mode = '--fix' in sys.argv

    translations_dir = Path(__file__).parent.parent / 'translations'

    all_issues = []
    total_fixed = 0

    for ndjson_file in sorted(translations_dir.glob('*.ndjson')):
        print(f"{'Fixing' if fix_mode else 'Checking'} {ndjson_file.name}...")
        issues, fixed = process_file(ndjson_file, fix=fix_mode)
        all_issues.extend(issues)
        total_fixed += fixed
        if fix_mode:
            print(f"  Fixed {fixed} quote issues")

    if not fix_mode:
        print(f"\nFound {len(all_issues)} quote style issues")
        for issue in all_issues[:20]:
            print(f"  {issue['file']}:{issue['line']} - {issue['ns']}:{issue['key']}")
            print(f"    {issue['translated_snippet']}...")
        if len(all_issues) > 20:
            print(f"  ... and {len(all_issues) - 20} more")
        print("\nRun with --fix to auto-fix these issues")
    else:
        print(f"\nTotal fixed: {total_fixed}")

    return 1 if all_issues and not fix_mode else 0

if __name__ == '__main__':
    sys.exit(main())
