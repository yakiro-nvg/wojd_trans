import path from 'node:path';
import { collectFmtStringEntries } from '../lib/fmtStrings.js';
import {
  loadTranslationFile,
  resetTranslations,
  saveTranslationFile,
  countPendingTranslations,
  type TranslationItem,
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

    // Build translation lookup table keyed by source string
    const translationBySource = new Map<string, string>();
    for (const item of existing) {
      if (item.source && item.translated) {
        // Only store first translation for each source (don't overwrite)
        if (!translationBySource.has(item.source)) {
          translationBySource.set(item.source, item.translated);
        }
      }
    }

    // Create fresh structure from collected entries
    const freshItems: TranslationItem[] = collected.map((entry) => {
      const source = entry.source;
      // Auto-fill translation if we have one for this source
      const translated = source ? (translationBySource.get(source) ?? null) : null;

      return {
        namespace: entry.namespace ?? '',
        key: entry.key,
        source,
        translated: force ? null : translated,
        locresImport: null,
        importedHash: null,
      };
    });

    // Sort by namespace then key
    freshItems.sort((a, b) => {
      if (a.namespace !== b.namespace) {
        return a.namespace.localeCompare(b.namespace);
      }
      return a.key.localeCompare(b.key);
    });

    // Calculate stats
    const existingKeys = new Set(existing.map((e) => `${e.namespace}\0${e.key}`));
    const freshKeys = new Set(freshItems.map((e) => `${e.namespace}\0${e.key}`));

    let added = 0;
    let removed = 0;
    let autoTranslated = 0;

    for (const key of freshKeys) {
      if (!existingKeys.has(key)) {
        added += 1;
      }
    }
    for (const key of existingKeys) {
      if (!freshKeys.has(key)) {
        removed += 1;
      }
    }
    for (const item of freshItems) {
      if (item.translated && item.source) {
        autoTranslated += 1;
      }
    }

    // Always save fresh structure
    await saveTranslationFile(catalogPath, freshItems, { prune: true });

    if (force) {
      console.log(`[fmt:${language}] All fmtstring translations have been reset.`);
    }

    const pending = countPendingTranslations(freshItems);
    reportSummary(language, { added, removed, autoTranslated }, freshItems.length, pending);
  }
}

function reportSummary(
  language: string,
  stats: { added: number; removed: number; autoTranslated: number },
  total: number,
  pending: number,
): void {
  const parts: string[] = [];
  if (stats.added > 0) {
    parts.push(`added ${stats.added}`);
  }
  if (stats.removed > 0) {
    parts.push(`removed ${stats.removed}`);
  }

  console.log(parts.length > 0 ? `[fmt:${language}] Catalog changes: ${parts.join(', ')}.` : `[fmt:${language}] Catalog is already in sync.`);
  console.log(`[fmt:${language}] Total entries: ${total}. Auto-translated: ${stats.autoTranslated}. Pending: ${pending}.`);
}
