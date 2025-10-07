import { readFile, writeFile } from 'node:fs/promises';
import { parseLocalizationLog } from '../lib/logParser.js';
import { normalizeLineEndings } from '../lib/text.js';
import { ensureWritable } from '../lib/file.js';
import type { LocalizationEntry } from '../types.js';

export interface CollectOptions {
  logPath: string;
  outputPath: string;
  force?: boolean;
}

export async function collect({ logPath, outputPath, force = false }: CollectOptions): Promise<number> {
  if (!logPath) {
    throw new Error('Missing logPath argument.');
  }
  if (!outputPath) {
    throw new Error('Missing outputPath argument.');
  }

  const rawLog = await readFile(logPath, 'utf8');
  const logContent = normalizeLineEndings(rawLog);
  const entries = parseLocalizationLog(logContent);
  const uniqueEntries = dedupeEntries(entries);

  await ensureWritable(outputPath, force === true);
  await writeFile(outputPath, JSON.stringify(uniqueEntries, null, 2), 'utf8');

  return uniqueEntries.length;
}

function dedupeEntries(entries: LocalizationEntry[]): LocalizationEntry[] {
  const byKey = new Map<string, LocalizationEntry>();

  for (const entry of entries) {
    const key = entry.key;
    const source = entry.source;
    if (!key || source == null) {
      continue;
    }

    const trimmed = source.trim();
    if (!trimmed) {
      continue;
    }

    if (!containsHanCharacters(trimmed)) {
      continue;
    }

    const namespace = entry.namespace ?? '';
    const mapKey = `${namespace}\u0000${key}`;
    byKey.set(mapKey, { ...entry, namespace, key, source });
  }

  const unique = Array.from(byKey.values());

  unique.sort((a, b) => {
    if (a.namespace !== b.namespace) {
      return a.namespace.localeCompare(b.namespace);
    }
    return a.key.localeCompare(b.key);
  });

  return unique;
}

const HAN_PLUS = /(?:\p{Script=Han}|[\u3000-\u303F\uFE30-\uFE4F\uFF00-\uFFEF\u2E80-\u2EFF\u2F00-\u2FDF\u2FF0-\u2FFF\u31C0-\u31EF\uF900-\uFAFF\u2F800-\u2FA1F])/u;

function containsHanCharacters(value: string): boolean {
  return HAN_PLUS.test(value);
}
