import path from 'node:path';
import { loadLocalizationEntries } from '../lib/entries.js';
import type { LocalizationEntry } from '../types.js';
import {
  loadTranslationFile,
  mergeCollectedWithTranslations,
  resetTranslations,
  saveTranslationFile,
  saveTranslationUpdates,
  countPendingTranslations,
  createKey,
} from '../lib/translationFile.js';
import { getSupportedLanguages } from '../lib/languages.js';

// Vietnamese diacritics pattern - used to detect already-translated text
const VIETNAMESE_PATTERN = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i;

function hasVietnameseText(text: string | null | undefined): boolean {
  return typeof text === 'string' && VIETNAMESE_PATTERN.test(text);
}

function filterVietnameseSources(entries: LocalizationEntry[]): { filtered: LocalizationEntry[]; skipped: number } {
  const filtered: LocalizationEntry[] = [];
  let skipped = 0;
  for (const entry of entries) {
    if (hasVietnameseText(entry.source)) {
      skipped++;
    } else {
      filtered.push(entry);
    }
  }
  return { filtered, skipped };
}

export interface SyncOptions {
  collectedPath: string;
  force?: boolean;
}

export async function syncTranslations(options: SyncOptions): Promise<void> {
  const { collectedPath, force } = options;

  if (!collectedPath) {
    throw new Error('Missing collected localization JSON path.');
  }

  const rawCollected = await loadLocalizationEntries(collectedPath);
  if (rawCollected.length === 0) {
    throw new Error('Collected JSON contains no localization entries.');
  }

  // Filter out entries with Vietnamese source (already translated via FormatString)
  const { filtered: collected, skipped: vietnameseSkipped } = filterVietnameseSources(rawCollected);
  if (vietnameseSkipped > 0) {
    console.log(`Skipped ${vietnameseSkipped} entries with Vietnamese source text.`);
  }

  const languages = await getSupportedLanguages();
  for (const language of languages) {
    const catalogPath = pathForLanguage(language);
    const existing = await loadTranslationFile(catalogPath);

    const existingIndex = new Set(existing.map((item) => createKey(item.namespace, item.key)));
    const missingSamples: Array<{ namespace: string; key: string }> = [];

    for (const entry of collected) {
      const namespace = entry.namespace ?? '';
      const key = entry.key;
      if (!key) {
        continue;
      }
      if (!existingIndex.has(createKey(namespace, key))) {
        missingSamples.push({ namespace, key });
        if (missingSamples.length >= 5) {
          break;
        }
      }
    }

    const mergeResult = mergeCollectedWithTranslations(collected, existing);
    let { items } = mergeResult;
    const { stats, changedIndices } = mergeResult;

    if (force === true) {
      items = resetTranslations(items);
      console.log(`[${language}] All translations have been reset to pending.`);
      await saveTranslationFile(catalogPath, items, { prune: true });
    } else if (changedIndices.length > 0) {
      await saveTranslationUpdates(catalogPath, items, changedIndices);
    }

    const pending = countPendingTranslations(items);
    reportSummary(language, stats, items.length, pending, changedIndices.length);
  }
}

function pathForLanguage(language: string): string {
  return path.join('translations', `${language}.ndjson`);
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

  console.log(parts.length > 0 ? `[${language}] Catalog changes: ${parts.join(', ')}.` : `[${language}] Catalog is already in sync.`);
  console.log(`[${language}] Lines written this run: ${changed}.`);
  console.log(`[${language}] Total entries: ${total}. Pending translations: ${pending}.`);
}
