import type { LocalizationEntry } from '../types.js';

const SEGMENT_SPLIT_REGEX = /(?=\[\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3}\])/;

export function parseLocalizationLog(logContent: string): LocalizationEntry[] {
  if (!logContent) {
    return [];
  }

  const entries: LocalizationEntry[] = [];
  const segments = splitSegments(logContent);

  for (const segment of segments) {
    const parsed = parseSegment(segment);
    if (parsed) {
      entries.push(parsed);
    }
  }

  return entries;
}

function splitSegments(content: string): string[] {
  return content
    .split(SEGMENT_SPLIT_REGEX)
    .map((chunk) => chunk.trim())
    .filter((chunk) => chunk.length > 0);
}

function parseSegment(segment: string): LocalizationEntry | null {
  const namespaceMatch = segment.match(/Namespace:\s*([^,\)\r\n]*)/);
  const keyMatch = segment.match(/Key:\s*([^,\)\r\n]+)/);

  if (!keyMatch) {
    return null;
  }

  const namespace = namespaceMatch && namespaceMatch[1] != null ? namespaceMatch[1].trim() : '';
  const key = keyMatch[1]?.trim() ?? '';

  if (!key) {
    return null;
  }

  const source = extractSource(segment);
  if (source == null) {
    return null;
  }

  return {
    namespace,
    key,
    source,
  };
}

function extractSource(segment: string): string | null {
  const lowerSegment = segment.toLowerCase();
  const sourceStringIdx = lowerSegment.indexOf('source string (');

  if (sourceStringIdx !== -1) {
    const openParenIndex = segment.indexOf('(', sourceStringIdx);
    if (openParenIndex !== -1) {
      const rawSource = extractBalancedParenthetical(segment, openParenIndex);
      if (rawSource != null) {
        return cleanupSource(rawSource);
      }
    }
  }

  const sourceFieldIdx = lowerSegment.indexOf('source:');
  if (sourceFieldIdx !== -1) {
    const valueStart = sourceFieldIdx + 'source:'.length;
    const rawAfter = segment.slice(valueStart);

    const hardTerminators = [
      ') will be used',
      ') will be used.',
      ') will be used\n',
      ') but it did not exist',
      ') but it does not exist',
      ') but the source string',
      ') but the source text',
      ') but it was not found',
      ') and',
    ];

    let earliestTerminatorIndex = -1;
    for (const terminator of hardTerminators) {
      const idx = rawAfter.indexOf(terminator);
      if (idx !== -1 && (earliestTerminatorIndex === -1 || idx < earliestTerminatorIndex)) {
        earliestTerminatorIndex = idx;
      }
    }

    if (earliestTerminatorIndex !== -1) {
      const raw = rawAfter.slice(0, earliestTerminatorIndex + 1);
      return cleanupSource(raw);
    }

    const primaryTerminators = [
      /\)\s*,?\s*but\b/i,
      /\)\s*,?\s*will\b/i,
      /\)\s*,?\s*and\b/i,
    ];

    for (const terminator of primaryTerminators) {
      const match = terminator.exec(rawAfter);
      if (match) {
        const raw = rawAfter.slice(0, match.index + 1);
        return cleanupSource(raw);
      }
    }

    const secondaryTerminators = [
      /,\s*but\b/i,
      /,\s*will\b/i,
      /,\s*and\b/i,
    ];

    for (const terminator of secondaryTerminators) {
      const match = terminator.exec(rawAfter);
      if (match) {
        const raw = rawAfter.slice(0, match.index);
        return cleanupSource(raw);
      }
    }

    const newlineIndex = rawAfter.search(/[\r\n]/);
    const fallback = newlineIndex !== -1 ? rawAfter.slice(0, newlineIndex) : rawAfter;
    return cleanupSource(fallback);
  }

  return null;
}

function extractBalancedParenthetical(text: string, openParenIndex: number): string | null {
  if (text[openParenIndex] !== '(') {
    return null;
  }

  let depth = 0;
  for (let i = openParenIndex; i < text.length; i += 1) {
    const char = text[i];
    if (char === '(') {
      depth += 1;
    } else if (char === ')') {
      depth -= 1;
      if (depth === 0) {
        return text.slice(openParenIndex + 1, i);
      }
      if (depth < 0) {
        break;
      }
    }
  }

  return null;
}

function cleanupSource(source: string | null | undefined): string | null {
  if (source == null) {
    return null;
  }

  const normalized = source.replace(/\r/g, '');
  return stripDanglingParentheses(normalized);
}

function stripDanglingParentheses(value: string): string {
  if (!value.includes(')')) {
    return value;
  }

  let balance = 0;
  for (const char of value) {
    if (char === '(') {
      balance += 1;
    } else if (char === ')') {
      balance -= 1;
    }
  }

  let result = value;
  while (balance < 0 && result.endsWith(')')) {
    result = result.slice(0, -1).trimEnd();
    balance += 1;
  }

  return result;
}
