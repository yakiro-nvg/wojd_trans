import { mkdtemp, mkdir, rename, rm, writeFile, cp } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadTranslationFile, type TranslationItem } from '../lib/translationFile.js';
import { detectPython, runCommand } from '../lib/python.js';

export interface PackOptions {
  translationsPath: string;
  outputDir: string;
  pythonPath?: string;
  keepTemp?: boolean;
  pakName?: string;
  language?: string;
  excludeAssets?: string[];
}

export async function buildPak(options: PackOptions): Promise<void> {
  const { translationsPath, outputDir, pythonPath, keepTemp, pakName, language, excludeAssets } = options;

  if (!translationsPath) {
    throw new Error('Missing translations NDJSON path.');
  }
  if (!outputDir) {
    throw new Error('Missing output directory.');
  }

  const targetLanguage = 'zh-Hans';
  const pakBase = pakName ?? 'translation';

  const translations = await loadTranslationFile(translationsPath);
  const translatedEntries = translations.filter(
    (entry) => entry.translated !== null && entry.translated !== undefined,
  );

  const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'wojd-pak-'));
  try {
    const patchRoot = path.join(tempRoot, pakBase);
    const locresDir = path.join(
      patchRoot,
      'ZhuxianClient',
      'gamedata',
      'client',
      'ZCTranslateData',
      'Game',
      targetLanguage,
    );
    const locresPath = path.join(locresDir, 'Game.locres');
    await mkdir(locresDir, { recursive: true });

    const fmtCatalogPath = path.join('translations', `${language}.fmtstring.ndjson`);
    const fmtItems = await loadTranslationFile(fmtCatalogPath);
    const fmtTranslatedCount = fmtItems.filter(
      (item) => item.translated !== null && item.translated !== undefined,
    ).length;
    if (translatedEntries.length === 0 && fmtTranslatedCount === 0) {
      console.warn(`[${language ?? 'default'}] No translated entries in locres or FormatString catalogs; skipping.`);
      return;
    }

    const pythonExecutable = detectPython(pythonPath);
    const buildScriptPath = fileURLToPath(new URL('../../scripts/build_locres.py', import.meta.url));

    await runCommand(pythonExecutable, [buildScriptPath, '--input', translationsPath, '--output', locresPath]);

    if (fmtItems.length > 0) {
      await writeFormatStringFiles(patchRoot, fmtItems);
      const formatRoot = path.join(
        patchRoot,
        'ZhuxianClient',
        'gamedata',
        'client',
        'FormatString',
      );
      console.log(`[${language ?? 'default'}] FormatString entries included: ${fmtItems.length}`);
      console.log(`[${language ?? 'default'}] FormatString files written under ${formatRoot}`);
    }

    if (language) {
      await copyAssetOverrides(patchRoot, language, excludeAssets);
    }

    const pakTempPath = path.join(tempRoot, `${pakBase}.pak`);
    await runCommand('repak', ['pack', patchRoot, pakTempPath]);

    const finalDir = path.resolve(outputDir);
    await mkdir(finalDir, { recursive: true });
    const finalBaseName = pakBase.startsWith('~') ? pakBase : `~${pakBase}`;
    const finalPakPath = path.join(finalDir, `${finalBaseName}.pak`);
    await rename(pakTempPath, finalPakPath);

    console.log(`[${language ?? 'default'}] Locres written to ${locresPath}`);
    console.log(`[${language ?? 'default'}] Packed PAK generated at ${finalPakPath}`);
    console.log(`[${language ?? 'default'}] Translated entries included: ${translatedEntries.length}`);
  } finally {
    if (!keepTemp) {
      await rm(tempRoot, { recursive: true, force: true });
    } else {
      console.log(`Temporary files kept at ${tempRoot}`);
    }
  }
}

async function writeFormatStringFiles(patchRoot: string, items: TranslationItem[]): Promise<void> {
  const formatRoot = path.join(patchRoot, 'ZhuxianClient', 'gamedata', 'client', 'FormatString');
  const grouped = new Map<string, TranslationItem[]>();

  for (const item of items) {
    const normalizedPath = item.namespace.replace(/\\/g, '/');
    const collection = grouped.get(normalizedPath);
    if (collection) {
      collection.push(item);
    } else {
      grouped.set(normalizedPath, [item]);
    }
  }

  if (grouped.size === 0) {
    return;
  }

  for (const [relativePath, records] of grouped) {
    const targetPath = path.join(formatRoot, ...relativePath.split('/'));
    await mkdir(path.dirname(targetPath), { recursive: true });

    const sortedRecords = [...records].sort((a, b) => a.key.localeCompare(b.key));
    if (sortedRecords.length === 0) {
      continue;
    }
    const lines = sortedRecords.map((entry) => {
      const translated = entry.translated !== null && entry.translated !== undefined ? entry.translated : null;
      const fallback = translated ?? entry.source ?? '';
      return `${entry.key} = ${fallback}`;
    });

    const content = `${lines.join('\r\n')}\r\n`;
    await writeFile(targetPath, content, 'utf8');
  }
}

async function copyAssetOverrides(patchRoot: string, language: string, excludePatterns?: string[]): Promise<void> {
  const sourceDir = path.resolve('assets', language.toLowerCase());
  const targetDir = path.join(patchRoot);

  try {
    const filterFn = excludePatterns && excludePatterns.length > 0
      ? (src: string) => {
          const relativePath = path.relative(sourceDir, src);
          for (const pattern of excludePatterns) {
            if (relativePath.includes(pattern) || src.includes(pattern)) {
              return false;
            }
          }
          return true;
        }
      : undefined;

    await cp(sourceDir, targetDir, { recursive: true, force: false, filter: filterFn });
    console.log(`[${language}] Asset overrides copied from ${sourceDir}`);
    if (excludePatterns && excludePatterns.length > 0) {
      console.log(`[${language}] Excluded patterns: ${excludePatterns.join(', ')}`);
    }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') {
      throw error;
    }
  }
}
