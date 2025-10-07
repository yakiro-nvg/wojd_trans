import { access, mkdir, readFile, writeFile, rename } from 'node:fs/promises';
import path from 'node:path';
import type { LocalizationEntry } from '../types.js';

export interface TranslationItem {
  namespace: string;
  key: string;
  source: string | null;
  translated: string | null;
  locresImport?: string | null;
  importedHash?: number | null;
}

export interface MergeStats {
  added: number;
  updated: number;
  removed: number;
}

export interface MergeResult {
  items: TranslationItem[];
  stats: MergeStats;
  changedIndices: number[];
}

export async function loadTranslationFile(filePath: string): Promise<TranslationItem[]> {
  try {
    const raw = await readFile(filePath, 'utf8');
    const lines = raw.split(/\r?\n/).filter((line) => line.trim().length > 0);

    const items: TranslationItem[] = [];
    for (let index = 0; index < lines.length; index += 1) {
      const line = lines[index];
      try {
        const parsed = JSON.parse(line);
        if (!parsed || typeof parsed !== 'object') {
          continue;
        }

        const namespace = typeof parsed.namespace === 'string' ? parsed.namespace : '';
        const key = typeof parsed.key === 'string' ? parsed.key : '';
        const source = typeof parsed.source === 'string' ? parsed.source : null;
        const translated = typeof parsed.translated === 'string' ? parsed.translated : null;
        const locresImport = typeof parsed.locresImport === 'string' ? parsed.locresImport : null;
        let importedHash: number | null = null;
        const rawHash = (parsed as Record<string, unknown>).importedHash;
        if (typeof rawHash === 'number' && Number.isFinite(rawHash)) {
          importedHash = rawHash;
        } else if (typeof rawHash === 'string') {
          const parsedValue = Number.parseInt(rawHash, 10);
          if (!Number.isNaN(parsedValue)) {
            importedHash = parsedValue;
          }
        }

        if (!key) {
          continue;
        }

        const normalizedNamespace = namespace ?? '';
        items.push({
          namespace: normalizedNamespace,
          key,
          source,
          translated,
          locresImport,
          importedHash,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.warn(
          `Skipping invalid translation line ${index + 1} (${filePath}): ${message}. Content: ${line.slice(0, 200)}`,
        );
      }
    }

    return sortItems(items);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return [];
    }
    throw error;
  }
}

export async function saveTranslationFile(
  filePath: string,
  items: TranslationItem[],
  _options: { prune?: boolean } = {},
): Promise<void> {
  const dir = path.dirname(path.resolve(filePath));
  await mkdir(dir, { recursive: true });

  const sorted = sortItems(items);
  const lines = sorted.map((item) => {
    const record: Record<string, unknown> = {
      namespace: item.namespace,
      key: item.key,
      source: item.source ?? null,
      translated: item.translated ?? null,
    };
    if (item.locresImport != null) {
      record.locresImport = item.locresImport;
    }
    if (item.importedHash != null) {
      record.importedHash = item.importedHash;
    }
    return JSON.stringify(record);
  });

  const tmpPath = `${filePath}.tmp`;
  await writeFile(tmpPath, lines.join('\n') + (lines.length > 0 ? '\n' : ''), 'utf8');
  await rename(tmpPath, filePath);
}

export async function saveTranslationUpdates(
  filePath: string,
  items: TranslationItem[],
  _indices: Iterable<number>,
): Promise<void> {
  await saveTranslationFile(filePath, items);
}

export function mergeCollectedWithTranslations(
  collected: LocalizationEntry[],
  existingItems: TranslationItem[],
): MergeResult {
  const existingMap = new Map<string, TranslationItem>();
  existingItems.forEach((item) => {
    existingMap.set(createKey(item.namespace, item.key), item);
  });

  const merged: Array<{ item: TranslationItem; changed: boolean }> = [];
  let added = 0;
  let updated = 0;

  for (const entry of collected) {
    const namespace = entry.namespace ?? '';
    const key = entry.key;
    const source = entry.source;
    const mapKey = createKey(namespace, key);
    const existing = existingMap.get(mapKey);

    if (!existing) {
      merged.push({
        item: {
          namespace,
          key,
          source,
          translated: null,
          locresImport: null,
          importedHash: null,
        },
        changed: true,
      });
      added += 1;
      continue;
    }

    existingMap.delete(mapKey);

    if (existing.source !== source) {
      merged.push({
        item: {
          namespace,
          key,
          source,
          translated: null,
          locresImport: existing.locresImport ?? null,
          importedHash: null,
        },
        changed: true,
      });
      updated += 1;
    } else {
      merged.push({
        item: existing,
        changed: false,
      });
    }
  }

  for (const remaining of existingMap.values()) {
    merged.push({ item: remaining, changed: false });
  }

  merged.sort((a, b) => {
    const namespaceA = a.item.namespace ?? '';
    const namespaceB = b.item.namespace ?? '';
    if (namespaceA !== namespaceB) {
      return namespaceA.localeCompare(namespaceB);
    }
    return a.item.key.localeCompare(b.item.key);
  });

  const items = merged.map((entry) => entry.item);
  const changedIndices: number[] = [];
  merged.forEach((entry, index) => {
    if (entry.changed) {
      changedIndices.push(index);
    }
  });

  return {
    items,
    stats: { added, updated, removed: 0 },
    changedIndices,
  };
}

export function resetTranslations(items: TranslationItem[]): TranslationItem[] {
  return items.map((item) => ({ ...item, translated: null }));
}

export function countPendingTranslations(items: TranslationItem[]): number {
  let count = 0;
  for (const item of items) {
    if (!item.translated || item.translated.trim().length === 0) {
      count += 1;
    }
  }
  return count;
}

export function createKey(namespace: string, key: string): string {
  return `${namespace}\u0000${key}`;
}

function sortItems(items: TranslationItem[]): TranslationItem[] {
  return [...items].sort((a, b) => {
    if (a.namespace !== b.namespace) {
      return a.namespace.localeCompare(b.namespace);
    }
    return a.key.localeCompare(b.key);
  });
}
