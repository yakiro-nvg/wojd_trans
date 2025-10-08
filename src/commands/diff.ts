import path from 'node:path';
import process from 'node:process';
import { execFile } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { promisify } from 'node:util';
import type { TranslationItem } from '../lib/translationFile.js';
import { createKey, loadTranslationFile, materializeLfsContent, parseTranslationContent } from '../lib/translationFile.js';

const execFileAsync = promisify(execFile);

export interface DiffOptions {
  filePath: string;
  ref?: string;
  maxDisplay?: number;
}

interface ItemChange {
  field: keyof TranslationItem;
  before: string | number | null;
  after: string | number | null;
}

interface DiffSummary {
  added: TranslationItem[];
  removed: TranslationItem[];
  changed: Array<{ item: TranslationItem; baseline: TranslationItem; changes: ItemChange[] }>;
}

const DEFAULT_MAX_DISPLAY = 10;

export async function diffTranslations(options: DiffOptions): Promise<DiffSummary> {
  const { filePath, ref = 'HEAD' } = options;

  const absolutePath = path.resolve(filePath);
  const relPath = path.relative(process.cwd(), absolutePath) || path.basename(absolutePath);

  const currentItems = await loadTranslationFile(relPath);
  const baselineItems = await loadFromGit(ref, relPath);

  const currentMap = new Map<string, TranslationItem>();
  currentItems.forEach((item) => currentMap.set(createKey(item.namespace, item.key), item));

  const baselineMap = new Map<string, TranslationItem>();
  baselineItems.forEach((item) => baselineMap.set(createKey(item.namespace, item.key), item));

  const added: TranslationItem[] = [];
  const removed: TranslationItem[] = [];
  const changed: Array<{ item: TranslationItem; baseline: TranslationItem; changes: ItemChange[] }> = [];

  for (const [key, item] of currentMap.entries()) {
    const baseline = baselineMap.get(key);
    if (!baseline) {
      added.push(item);
      continue;
    }

    baselineMap.delete(key);
    const changes = diffFields(baseline, item);
    if (changes.length > 0) {
      changed.push({ item, baseline, changes });
    }
  }

  for (const remaining of baselineMap.values()) {
    removed.push(remaining);
  }

  return { added, removed, changed };
}

function diffFields(before: TranslationItem, after: TranslationItem): ItemChange[] {
  const fields: Array<keyof TranslationItem> = ['source', 'translated', 'locresImport', 'importedHash'];
  const changes: ItemChange[] = [];

  for (const field of fields) {
    const beforeValue = normalizeValue(before[field]);
    const afterValue = normalizeValue(after[field]);

    if (beforeValue !== afterValue) {
      changes.push({ field, before: beforeValue, after: afterValue });
    }
  }

  return changes;
}

function normalizeValue(value: TranslationItem[keyof TranslationItem]): string | number | null {
  if (value === undefined) {
    return null;
  }
  if (typeof value === 'number' || value === null) {
    return value;
  }
  if (typeof value === 'string') {
    return value;
  }
  return null;
}

async function loadFromGit(ref: string, relPath: string): Promise<TranslationItem[]> {
  try {
    const { stdout } = await execFileAsync('git', ['show', `${ref}:${relPath}`], {
      cwd: process.cwd(),
      maxBuffer: 1024 * 1024 * 512,
    });
    const resolved = await materializeLfsContent(stdout, `${relPath}@${ref}`);
    return parseTranslationContent(resolved, `${relPath}@${ref}`);
  } catch (error) {
    const err = error as NodeJS.ErrnoException & { stderr?: string };
    const codeString = err.code !== undefined ? String(err.code) : undefined;
    if (codeString === '128' || (typeof err.stderr === 'string' && err.stderr.includes('fatal:'))) {
      console.warn(`No baseline found for ${relPath} at ${ref}; treating as empty.`);
      return [];
    }
    throw error;
  }
}

export function printDiff(summary: DiffSummary, options: DiffOptions): number {
  const { filePath, ref = 'HEAD', maxDisplay } = options;
  const { added, removed, changed } = summary;
  const totalCount = added.length + removed.length + changed.length;

  if (totalCount === 0) {
    console.log(`No differences between working tree and ${ref} for ${filePath}.`);
    return 0;
  }

  const limit = resolveDisplayLimit(maxDisplay);

  console.log(`Comparing ${filePath} against ${ref}:`);
  console.log(`  added: ${added.length}`);
  console.log(`  removed: ${removed.length}`);
  console.log(`  changed: ${changed.length}`);

  const printSection = <T>(
    label: string,
    items: T[],
    render: (item: T) => void,
  ): void => {
    if (items.length === 0) {
      return;
    }

    const toShow = limit === undefined ? items : items.slice(0, limit);
    const truncated = limit !== undefined && items.length > limit;
    const suffix = truncated ? ` (showing first ${toShow.length})` : '';
    console.log(`${label} entries (${items.length})${suffix}:`);
    toShow.forEach(render);
    if (truncated) {
      console.log(`  ... ${items.length - toShow.length} more ${label.toLowerCase()} entries not shown.`);
    }
  };

  printSection('Added', added, (item) => {
    console.log(formatHeader(item));
    console.log(`  source: ${formatValue(item.source)}`);
    console.log(`  translated: ${formatValue(item.translated)}`);
  });

  printSection('Removed', removed, (item) => {
    console.log(formatHeader(item));
    console.log(`  source: ${formatValue(item.source)}`);
    console.log(`  translated: ${formatValue(item.translated)}`);
  });

  printSection('Changed', changed, ({ item, changes }) => {
    console.log(formatHeader(item));
    for (const change of changes) {
      console.log(`  ${change.field}:`);
      console.log(`    ${ref}: ${formatValue(change.before)}`);
      console.log(`    working: ${formatValue(change.after)}`);
    }
  });

  return totalCount;
}

export async function writeDiffReport(
  summary: DiffSummary,
  options: { outputPath: string; filePath: string; ref?: string },
): Promise<string> {
  const { outputPath, filePath, ref = 'HEAD' } = options;
  const resolvedPath = path.resolve(outputPath);
  await mkdir(path.dirname(resolvedPath), { recursive: true });

  const payload = {
    metadata: {
      filePath,
      ref,
      generatedAt: new Date().toISOString(),
      counts: {
        added: summary.added.length,
        removed: summary.removed.length,
        changed: summary.changed.length,
      },
    },
    added: summary.added,
    removed: summary.removed,
    changed: summary.changed,
  };

  await writeFile(resolvedPath, JSON.stringify(payload, null, 2), 'utf8');
  return resolvedPath;
}

function resolveDisplayLimit(value: number | undefined): number | undefined {
  if (value === undefined) {
    return DEFAULT_MAX_DISPLAY;
  }
  if (!Number.isFinite(value) || value <= 0) {
    return undefined;
  }
  return Math.floor(value);
}

function formatHeader(item: TranslationItem): string {
  const ns = item.namespace ?? '';
  const key = item.key;
  return `- (${ns || '<root>'}, ${key})`;
}

function formatValue(value: string | number | null): string {
  if (value === null) {
    return 'null';
  }
  if (typeof value === 'number') {
    return String(value);
  }
  if (value.length === 0) {
    return '""';
  }
  return JSON.stringify(value.length > 200 ? `${value.slice(0, 200)}...` : value);
}
