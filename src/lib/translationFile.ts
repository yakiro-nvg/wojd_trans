import { access, mkdir, readFile, writeFile, rename, lstat } from 'node:fs/promises';
import path from 'node:path';
import type { LocalizationEntry } from '../types.js';
import { sanitizeTranslationItem, sanitizeTranslationItems, shouldSkipTranslation } from './skipList.js';

const CRC32_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let crc = i;
    for (let bit = 0; bit < 8; bit += 1) {
      const mask = -(crc & 1);
      crc = (crc >>> 1) ^ (0xedb88320 & mask);
    }
    table[i] = crc >>> 0;
  }
  return table;
})();

const GIT_LFS_POINTER_PREFIX = 'version https://git-lfs.github.com/spec/';

function computeCrc32(buffer: Buffer): number {
  let crc = 0 ^ -1;
  for (let i = 0; i < buffer.length; i += 1) {
    const byte = buffer[i];
    crc = (CRC32_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8)) >>> 0;
  }
  return (crc ^ -1) >>> 0;
}

function encodeUtf32Le(text: string): Buffer {
  const codePoints: number[] = [];
  for (let i = 0; i < text.length; i += 1) {
    const codePoint = text.codePointAt(i);
    if (codePoint == null) {
      continue;
    }
    codePoints.push(codePoint);
    if (codePoint > 0xffff) {
      i += 1;
    }
  }

  const buffer = Buffer.alloc(codePoints.length * 4);
  for (let i = 0; i < codePoints.length; i += 1) {
    buffer.writeUInt32LE(codePoints[i], i * 4);
  }
  return buffer;
}

function computeSourceHash(source: string): number {
  const normalized = source ?? '';
  const encoded = encodeUtf32Le(normalized);
  return computeCrc32(encoded);
}

export function detectLfsPointer(raw: string): boolean {
  const trimmed = raw.trim();
  if (!trimmed) {
    return false;
  }

  const [line1 = '', line2 = '', line3 = ''] = trimmed.split(/\r?\n/, 4);
  return (
    line1.startsWith(GIT_LFS_POINTER_PREFIX) &&
    line2.startsWith('oid sha256:') &&
    line3.startsWith('size ')
  );
}

export interface GitLfsPointerInfo {
  oid: string;
  size?: number;
}

export class GitLfsObjectMissingError extends Error {
  constructor(public readonly label: string, public readonly oid: string) {
    super(`Git LFS object ${oid} missing for ${label}`);
    this.name = 'GitLfsObjectMissingError';
  }
}

export function parseLfsPointer(raw: string): GitLfsPointerInfo | null {
  if (!detectLfsPointer(raw)) {
    return null;
  }

  const lines = raw.trim().split(/\r?\n/);
  let oid: string | undefined;
  let size: number | undefined;

  for (const line of lines) {
    if (line.startsWith('oid sha256:')) {
      oid = line.slice('oid sha256:'.length).trim();
    } else if (line.startsWith('size ')) {
      const rawSize = line.slice('size '.length).trim();
      const parsed = Number.parseInt(rawSize, 10);
      if (!Number.isNaN(parsed)) {
        size = parsed;
      }
    }
  }

  if (!oid) {
    return null;
  }

  return { oid, size };
}

let cachedGitDir: string | null = null;

async function resolveGitDir(): Promise<string> {
  if (cachedGitDir) {
    return cachedGitDir;
  }

  const gitMarkerPath = path.resolve('.git');

  try {
    const stats = await lstat(gitMarkerPath);
    if (stats.isDirectory()) {
      cachedGitDir = gitMarkerPath;
      return cachedGitDir;
    }

    const marker = await readFile(gitMarkerPath, 'utf8');
    const match = marker.trim().match(/^gitdir:\s*(.+)$/i);
    if (match) {
      cachedGitDir = path.resolve(path.dirname(gitMarkerPath), match[1]);
      return cachedGitDir;
    }
  } catch (error) {
    // ignore and fall through to error below
  }

  throw new Error('Unable to resolve .git directory required for Git LFS objects.');
}

async function readLfsObject(pointer: GitLfsPointerInfo, label: string): Promise<string> {
  const gitDir = await resolveGitDir();
  const objectPath = path.join(
    gitDir,
    'lfs',
    'objects',
    pointer.oid.slice(0, 2),
    pointer.oid.slice(2, 4),
    pointer.oid,
  );

  try {
    return await readFile(objectPath, 'utf8');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      throw new GitLfsObjectMissingError(label, pointer.oid);
    }
    throw error;
  }
}

export async function materializeLfsContent(raw: string, label: string): Promise<string> {
  const pointer = parseLfsPointer(raw);
  if (!pointer) {
    return raw;
  }
  return readLfsObject(pointer, label);
}

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

export function parseTranslationContent(raw: string, label = '<string>'): TranslationItem[] {
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
        `Skipping invalid translation line ${index + 1} (${label}): ${message}. Content: ${line.slice(0, 200)}`,
      );
    }
  }

  return sortItems(sanitizeTranslationItems(items));
}

export async function loadTranslationFile(filePath: string): Promise<TranslationItem[]> {
  try {
    const raw = await readFile(filePath, 'utf8');
    const resolvedContent = await materializeLfsContent(raw, filePath);
    return parseTranslationContent(resolvedContent, filePath);
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
      let locresImport: string | null = null;
      let importedHash: number | null = null;

      if (existing.locresImport != null) {
        if (existing.importedHash != null && source != null && source.length > 0) {
          const expectedHash = computeSourceHash(source);
          if (expectedHash === existing.importedHash) {
            locresImport = existing.locresImport;
            importedHash = existing.importedHash;
          }
        }
      }

      merged.push({
        item: {
          namespace,
          key,
          source,
          translated: null,
          locresImport,
          importedHash,
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

  const sanitizedItems = items.map(sanitizeTranslationItem);
  const reconciliation = reconcileLocresConsistency(sanitizedItems);
  const finalItems = reconciliation.items;
  const combinedIndices = new Set<number>([...changedIndices, ...reconciliation.changedIndices]);

  return {
    items: finalItems,
    stats: { added, updated, removed: 0 },
    changedIndices: Array.from(combinedIndices).sort((a, b) => a - b),
  };
}

function reconcileLocresConsistency(items: TranslationItem[]): { items: TranslationItem[]; changedIndices: number[] } {
  const reconciled: TranslationItem[] = [...items];
  const changedIndices: number[] = [];

  for (let index = 0; index < items.length; index += 1) {
    const current = items[index];
    if (!current) {
      continue;
    }

    const source = current.source ?? null;
    const hasLocres = current.locresImport != null;
    const hash = current.importedHash ?? null;

    if (!source) {
      continue;
    }

    if (hasLocres && hash != null) {
      const expected = computeSourceHash(source);
      if (expected !== hash) {
        reconciled[index] = {
          ...current,
          locresImport: null,
          importedHash: null,
          translated: null,
        };
        changedIndices.push(index);
      }
    }
  }

  return { items: reconciled, changedIndices };
}

export function resetTranslations(items: TranslationItem[]): TranslationItem[] {
  return items.map((item) => ({ ...item, translated: null }));
}

export function countPendingTranslations(items: TranslationItem[]): number {
  let count = 0;
  for (const item of items) {
    if (shouldSkipTranslation(item.namespace, item.key)) {
      continue;
    }
    if (item.translated && item.translated.trim().length > 0) {
      continue;
    }
    const locres = item.locresImport && item.locresImport.trim().length > 0 ? item.locresImport.trim() : null;
    const source = item.source && item.source.trim().length > 0 ? item.source.trim() : null;
    if (!locres && !source) {
      continue;
    }
    count += 1;
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
