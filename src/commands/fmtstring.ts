import path from 'node:path';
import { collectFmtStringEntries } from '../lib/fmtStrings.js';
import {
  loadTranslationFile,
  mergeCollectedWithTranslations,
  resetTranslations,
  saveTranslationFile,
  saveTranslationUpdates,
  countPendingTranslations,
} from '../lib/translationFile.js';
import { getSupportedLanguages } from '../lib/languages.js';

export interface FmtStringSyncOptions {
  rootDir: string;
  force?: boolean;
}

export async function syncFmtStrings(options: FmtStringSyncOptions): Promise<void> {
  const { rootDir, force } = options;
  if (!rootDir) {
    throw new Error('fmtstring sync requires a FormatString directory.');
  }

  const collected = await collectFmtStringEntries(rootDir);
  if (collected.length === 0) {
    console.warn('No .txt entries found under the specified FormatString directory.');
  }

  const languages = await getSupportedLanguages();
  for (const language of languages) {
    const catalogPath = path.join('translations', `${language}.fmtstring.ndjson`);
    const existing = await loadTranslationFile(catalogPath);

    const mergeResult = mergeCollectedWithTranslations(collected, existing);
    let items = mergeResult.items;

    const { stats, changedIndices } = mergeResult;

    if (force === true) {
      items = resetTranslations(items);
      console.log(`[fmt:${language}] All fmtstring translations have been reset.`);
      await saveTranslationFile(catalogPath, items, { prune: true });
    } else if (changedIndices.length > 0) {
      await saveTranslationUpdates(catalogPath, items, changedIndices);
    }

    const pending = countPendingTranslations(items);
    reportSummary(language, stats, items.length, pending, changedIndices.length);
  }
}

function reportSummary(
  language: string,
  stats: { added: number; updated: number; removed: number },
  total: number,
  pending: number,
  changed: number,
): void {
  const parts: string[] = [];
  if (stats.added > 0) {
    parts.push(`added ${stats.added}`);
  }
  if (stats.updated > 0) {
    parts.push(`updated ${stats.updated}`);
  }
  if (stats.removed > 0) {
    parts.push(`removed ${stats.removed}`);
  }

  console.log(parts.length > 0 ? `[fmt:${language}] Catalog changes: ${parts.join(', ')}.` : `[fmt:${language}] Catalog is already in sync.`);
  console.log(`[fmt:${language}] Lines written this run: ${changed}.`);
  console.log(`[fmt:${language}] Total entries: ${total}. Pending translations: ${pending}.`);
}
