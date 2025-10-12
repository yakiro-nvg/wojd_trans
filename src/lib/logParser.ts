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
  const sourceStringMarker = 'source string (';
  const sourceStringIdx = lowerSegment.indexOf(sourceStringMarker);

  if (sourceStringIdx !== -1) {
    const valueStart = sourceStringIdx + sourceStringMarker.length;
    const rawAfter = segment.slice(valueStart);
    const sliced = sliceAtTerminator(rawAfter);
    if (sliced != null) {
      return sliced;
    }
    return rawAfter.trimEnd();
  }

  const sourceFieldIdx = lowerSegment.indexOf('source:');
  if (sourceFieldIdx !== -1) {
    const valueStart = sourceFieldIdx + 'source:'.length;
    const rawAfter = segment.slice(valueStart);
    const sliced = sliceAtTerminator(rawAfter);
    if (sliced != null) {
      return sliced;
    }
    return rawAfter.trimEnd();
  }

  return null;
}

function sliceAtTerminator(rawAfter: string): string | null {
  const terminatorIndex = findTerminatorIndex(rawAfter);
  if (terminatorIndex != null) {
    return rawAfter.slice(0, terminatorIndex);
  }

  const newlineIndex = rawAfter.search(/[\r\n]/);
  if (newlineIndex !== -1) {
    return rawAfter.slice(0, newlineIndex);
  }

  return rawAfter.length > 0 ? rawAfter : null;
}

function findTerminatorIndex(rawAfter: string): number | null {
  const lowerAfter = rawAfter.toLowerCase();
  const hardTerminators = [
    ') will be used',
    ') will be used.',
    ') will be used\r',
    ') will be used\n',
    ') but it did not exist',
    ') but it does not exist',
    ') but the source string',
    ') but the source text',
    ') but it was not found',
    ') and',
  ];

  let candidate: number | null = null;

  for (const terminator of hardTerminators) {
    const idx = lowerAfter.indexOf(terminator);
    if (idx !== -1 && (candidate == null || idx < candidate)) {
      candidate = idx;
    }
  }

  const primaryTerminators = [
    /\)\s*,?\s*but\b/i,
    /\)\s*,?\s*will\b/i,
    /\)\s*,?\s*and\b/i,
  ];

  for (const terminator of primaryTerminators) {
    const match = terminator.exec(rawAfter);
    if (match) {
      const idx = match.index;
      if (candidate == null || idx < candidate) {
        candidate = idx;
      }
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
      const idx = match.index;
      if (candidate == null || idx < candidate) {
        candidate = idx;
      }
    }
  }

  return candidate;
}
