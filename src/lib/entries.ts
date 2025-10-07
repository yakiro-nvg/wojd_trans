import { readFile } from 'node:fs/promises';
import type { LocalizationEntry } from '../types.js';

export async function loadLocalizationEntries(jsonPath: string): Promise<LocalizationEntry[]> {
  const raw = await readFile(jsonPath, 'utf8');
  let parsed: unknown;

  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    throw new Error(`Failed to parse JSON from ${jsonPath}: ${(error as Error).message}`);
  }

  if (!Array.isArray(parsed)) {
    throw new Error(`Expected an array of entries in ${jsonPath}`);
  }

  const entries: LocalizationEntry[] = [];

  for (const item of parsed) {
    if (!item) {
      continue;
    }
    const namespace = typeof item.namespace === 'string' ? item.namespace : '';
    const key = typeof item.key === 'string' ? item.key : '';
    const source = typeof item.source === 'string' ? item.source : '';

    if (!key || source.length === 0) {
      continue;
    }

    entries.push({ namespace, key, source });
  }

  return entries;
}
