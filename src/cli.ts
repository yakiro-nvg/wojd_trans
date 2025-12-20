#!/usr/bin/env node
import path from 'node:path';
import process from 'node:process';
import { select } from '@inquirer/prompts';
import { collect } from './commands/collect.js';
import { translate } from './commands/translate.js';
import { syncTranslations } from './commands/sync.js';
import { buildPak } from './commands/pack.js';
import { importLocres } from './commands/importLocres.js';
import { getSupportedLanguages } from './lib/languages.js';
import { syncFmtStrings } from './commands/fmtstring.js';
import { diffTranslations, printDiff, writeDiffReport } from './commands/diff.js';
import { GitLfsObjectMissingError } from './lib/translationFile.js';

const DEFAULT_TEST_LIMIT = 5;

interface ParsedArgs {
  positional: string[];
  flags: Record<string, unknown>;
}

async function main(): Promise<void> {
  const [, , command, ...rest] = process.argv;

  if (!command || command === 'help' || command === '--help' || command === '-h') {
    printHelp();
    return;
  }

  try {
    if (command === 'collect') {
      const { positional, flags } = parseArgs(rest);
      let logPath: string | undefined;
      let outputPath: string | undefined;

      if (positional.length >= 2) {
        [logPath, outputPath] = positional;
      } else if (positional.length === 1) {
        [outputPath] = positional;
      }

      const force = Boolean(flags.force);

      if (!outputPath) {
        throw new Error('collect command requires <output> path (optionally preceded by <logPath>).');
      }

      const { entryCount, logFiles } = await collect({ logPath, outputPath, force });
      const logSummary = logFiles.length === 1
        ? logFiles[0]
        : `${logFiles.length} logs`;
      console.log(`Collected ${entryCount} entries from ${logSummary}.`);
      if (logFiles.length > 1) {
        console.log('Processed logs:');
        for (const file of logFiles) {
          console.log(`  - ${file}`);
        }
      }
      console.log(`Output written to ${outputPath}`);
      return;
    }

    if (command === 'translate') {
      const { positional, flags } = parseArgs(rest);
      const force = Boolean(flags.force);
      const limit = getNumericOption(flags.limit);
      const testLimit = getTestLimit(flags.test);
      const batchSize = getNumericOption(flags.batchSize);
      const systemPromptPath = typeof flags.systemPrompt === 'string' ? flags.systemPrompt : undefined;
      const checkpoint = getNumericOption(flags.checkpoint);
      const concurrency = getNumericOption(flags.concurrency);

      const languages = await getSupportedLanguages();

      let language = typeof flags.language === 'string' ? String(flags.language).toLowerCase() : undefined;
      if (!language && positional.length > 0) {
        const candidate = positional[0].toLowerCase();
        if (languages.includes(candidate)) {
          language = candidate;
        }
      }

      if (!language) {
        if (languages.length === 1) {
          language = languages[0];
        } else {
          language = await select({
            message: 'Select language to translate',
            choices: languages.map((lang) => ({ name: lang, value: lang })),
          });
        }
      }

      if (!languages.includes(language)) {
        throw new Error(`Unsupported language: ${language}`);
      }

      const translationPath = path.join('translations', `${language}.ndjson`);

      const count = await translate({
        translationPath,
        language,
        force,
        limit,
        testLimit,
        batchSize,
        systemPromptPath,
        checkpoint,
        concurrency,
      });

      console.log(`[${language}] Translated ${count} entries.`);
      console.log(`[${language}] Translations written to ${translationPath}`);
      return;
    }

    if (command === 'fmtstring') {
      const { positional, flags } = parseArgs(rest);
      const rootDir = positional[0] ?? 'FormatString';
      const force = Boolean(flags.force);
      await syncFmtStrings({ rootDir, force });
      return;
    }

    if (command === 'diff') {
      const { positional, flags } = parseArgs(rest);
      const ref = typeof flags.ref === 'string' ? String(flags.ref) : undefined;
      const languages = await getSupportedLanguages();

      let targetPath = positional[0];
      let language = typeof flags.language === 'string' ? String(flags.language).toLowerCase() : undefined;

      if (language && !languages.includes(language)) {
        throw new Error(`Unsupported language: ${language}`);
      }

      if (!targetPath) {
        if (language) {
          targetPath = path.join('translations', `${language}.ndjson`);
        } else if (languages.length === 1) {
          targetPath = path.join('translations', `${languages[0]}.ndjson`);
          language = languages[0];
        } else {
          throw new Error('diff command requires a file path or --language <code>.');
        }
      }

      if (!targetPath.endsWith('.ndjson')) {
        targetPath = `${targetPath}.ndjson`;
      }

      if (!path.isAbsolute(targetPath)) {
        targetPath = path.join(process.cwd(), targetPath);
      }

      const outputPath = typeof flags.output === 'string' ? String(flags.output) : undefined;
      const rawLimit = getNumericOption(flags.limit);
      const maxDisplay =
        rawLimit === undefined ? undefined : rawLimit <= 0 ? Number.POSITIVE_INFINITY : rawLimit;

      let summary: Awaited<ReturnType<typeof diffTranslations>>;
      try {
        summary = await diffTranslations({ filePath: targetPath, ref });
      } catch (error) {
        if (error instanceof GitLfsObjectMissingError) {
          console.error(`Missing Git LFS object ${error.oid} for ${error.label}.`);
          console.error('Run `git lfs pull` followed by `git lfs checkout` to materialise the file.');
          process.exitCode = 1;
          return;
        }
        throw error;
      }

      if (outputPath) {
        const resolved = await writeDiffReport(summary, { outputPath, filePath: targetPath, ref });
        console.log(`Full diff written to ${resolved}`);
      }

      const diffCount = printDiff(summary, { filePath: targetPath, ref, maxDisplay });
      if (diffCount > 0) {
        process.exitCode = 1;
      }
      return;
    }

    if (command === 'import' || command === 'import-locres') {
      const { positional, flags } = parseArgs(rest);
      const [locresPath] = positional;
      const pythonPath = typeof flags.python === 'string' ? flags.python : undefined;

      if (!locresPath) {
        throw new Error('import command requires <locres> path.');
      }

      await importLocres({ locresPath, pythonPath });
      return;
    }

    if (command === 'pack' || command === 'build-pak') {
      const { positional, flags } = parseArgs(rest);
      const [outputDirPos] = positional;
      const pythonPath = typeof flags.python === 'string' ? flags.python : undefined;
      const keepTemp = Boolean(flags.keepTemp);
      const outputDir = outputDirPos ?? (typeof flags.output === 'string' ? String(flags.output) : 'artifacts');
      const variant = typeof flags.variant === 'string' ? String(flags.variant) : undefined;

      interface VariantConfig {
        suffix: string;
        layers: (lang: string) => string[];
      }

      const variantConfigs: Record<string, VariantConfig> = {
        base: {
          suffix: '',
          layers: (lang) => [`${lang}-base`],
        },
        'lim-xf': {
          suffix: '_LIM_XF',
          layers: (lang) => [`${lang}-base`, `${lang}-lim`, `${lang}-lim-xf`, `${lang}-dyn-xf`],
        },
        'lim-mvh': {
          suffix: '_LIM_MVH',
          layers: (lang) => [`${lang}-base`, `${lang}-lim`, `${lang}-lim-mvh`, `${lang}-dyn-mvh`],
        },
        'full-xf': {
          suffix: '_FULL_XF',
          layers: (lang) => [`${lang}-base`, `${lang}-full-xf`],
        },
        'full-mvh': {
          suffix: '_FULL_MVH',
          layers: (lang) => [`${lang}-base`, `${lang}-full-mvh`],
        },
      };

      const languages = await getSupportedLanguages();
      const variantsToBuild = variant === 'all'
        ? Object.keys(variantConfigs)
        : [variant ?? 'base'];

      for (const variantKey of variantsToBuild) {
        const config = variantConfigs[variantKey];
        if (!config) {
          throw new Error(`Unknown variant: ${variantKey}. Valid variants: ${Object.keys(variantConfigs).join(', ')}, all`);
        }

        for (const language of languages) {
          const translationsPath = path.join('translations', `${language}.ndjson`);
          const pakName = `${language.toUpperCase()}_PATCH${config.suffix}`;
          const assetLayers = config.layers(language);
          await buildPak({
            translationsPath,
            outputDir,
            pythonPath,
            keepTemp,
            pakName,
            language,
            assetLayers,
          });
        }
      }
      return;
    }

    if (command === 'sync') {
      const { positional, flags } = parseArgs(rest);
      const [collectedPath] = positional;
      const force = Boolean(flags.force);

      if (!collectedPath) {
        throw new Error('sync command requires <collected.json> path.');
      }

      await syncTranslations({ collectedPath, force });
      return;
    }

    console.error(`Unknown command: ${command}`);
    printHelp();
    process.exitCode = 1;
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}

function parseArgs(args: string[]): ParsedArgs {
  const positional: string[] = [];
  const flags: Record<string, unknown> = {};

  let index = 0;
  while (index < args.length) {
    const arg = args[index];

    if (!arg.startsWith('-')) {
      positional.push(arg);
      index += 1;
      continue;
    }

    if (arg === '--force' || arg === '-f') {
      flags.force = true;
      index += 1;
      continue;
    }

    if (arg.startsWith('--limit')) {
      const value = extractOptionValue(arg, args[index + 1]);
      flags.limit = value.value;
      index += value.skip ? 1 : 2;
      continue;
    }

    if (arg === '--test' || arg.startsWith('--test=')) {
      const value = extractOptionValue(arg, args[index + 1]);
      flags.test = value.value ?? true;
      index += value.skip ? 1 : 2;
      continue;
    }

    if (arg.startsWith('--batch-size')) {
      const value = extractOptionValue(arg, args[index + 1]);
      flags.batchSize = value.value;
      index += value.skip ? 1 : 2;
      continue;
    }

    if (arg.startsWith('--system-prompt')) {
      const value = extractOptionValue(arg, args[index + 1]);
      flags.systemPrompt = value.value;
      index += value.skip ? 1 : 2;
      continue;
    }

    if (arg.startsWith('--checkpoint')) {
      const value = extractOptionValue(arg, args[index + 1]);
      flags.checkpoint = value.value;
      index += value.skip ? 1 : 2;
      continue;
    }

    if (arg.startsWith('--concurrency')) {
      const value = extractOptionValue(arg, args[index + 1]);
      flags.concurrency = value.value;
      index += value.skip ? 1 : 2;
      continue;
    }

    if (arg.startsWith('--language')) {
      const value = extractOptionValue(arg, args[index + 1]);
      flags.language = value.value;
      index += value.skip ? 1 : 2;
      continue;
    }

    if (arg.startsWith('--ref')) {
      const value = extractOptionValue(arg, args[index + 1]);
      flags.ref = value.value;
      index += value.skip ? 1 : 2;
      continue;
    }

    if (arg.startsWith('--python')) {
      const value = extractOptionValue(arg, args[index + 1]);
      flags.python = value.value;
      index += value.skip ? 1 : 2;
      continue;
    }

    if (arg === '--keep-temp') {
      flags.keepTemp = true;
      index += 1;
      continue;
    }

    if (arg.startsWith('--output')) {
      const value = extractOptionValue(arg, args[index + 1]);
      flags.output = value.value;
      index += value.skip ? 1 : 2;
      continue;
    }

    if (arg.startsWith('--variant')) {
      const value = extractOptionValue(arg, args[index + 1]);
      flags.variant = value.value;
      index += value.skip ? 1 : 2;
      continue;
    }


    console.warn(`Ignoring unknown option: ${arg}`);
    index += 1;
  }

  return { positional, flags };
}

interface ExtractedValue {
  value?: string;
  skip: boolean;
}

function extractOptionValue(current: string, next?: string): ExtractedValue {
  const [option, inlineValue] = current.split('=', 2);

  if (inlineValue !== undefined) {
    return { value: inlineValue, skip: true };
  }

  if (next === undefined || next.startsWith('-')) {
    return { value: undefined, skip: true };
  }

  return { value: next, skip: false };
}

function getNumericOption(value: unknown): number | undefined {
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number.parseInt(value, 10);
    if (Number.isNaN(parsed)) {
      throw new Error(`Invalid numeric value: ${value}`);
    }
    return parsed;
  }
  return undefined;
}

function getTestLimit(value: unknown): number | undefined {
  if (value === true) {
    return DEFAULT_TEST_LIMIT;
  }
  return getNumericOption(value);
}

function printHelp(): void {
  console.log('Usage: wojd-trans <command> [options]');
  console.log('Commands:');
  console.log('  collect <logPath> <outputPath> [--force|-f]');
  console.log('      Parse UE logs and materialise collected entries as JSON.');
  console.log('  sync <collected.json> [--force|-f]');
  console.log('      Merge collected entries into every language catalog (reset with --force).');
  console.log('  fmtstring [FormatStringDir] [--force|-f]');
  console.log('      Sync FormatString .txt files into per-language fmtstring catalogs.');
  console.log('  diff [file|--language <code>] [--ref <gitRef>]');
  console.log('      Compare working NDJSON against a Git ref (default HEAD).');
  console.log('      --limit <n>             Show up to <n> entries per section (default 10, use 0 for all).');
  console.log('      --output <path>        Write the full diff report as JSON to <path>.');
  console.log('  translate [--language <code>] [options]');
  console.log('      Translate pending entries for the chosen language using Bedrock Claude.');
  console.log('  import <Game.locres> [--python <path>]');
  console.log('      Import an existing locres into all language catalogs.');
  console.log('  pack [outputDir] [--python <path>] [--keep-temp]');
  console.log('      Build Game.locres and per-language PAK files into outputDir (default: artifacts).');
  console.log('Options for translate:');
  console.log('  --language <code>        Language to translate; prompts when omitted.');
  console.log('  --force, -f              Reset existing translations before translating.');
  console.log('  --limit <n>              Limit unique sources processed this run.');
  console.log('  --test[=<n>]             Enable smoke mode (defaults to 5 unique sources).');
  console.log('  --batch-size <n>         Translation batch size per request (default 5).');
  console.log('  --system-prompt <path>   Override the system prompt file.');
  console.log('  --checkpoint <n>         Persist progress after every n translations (default 20).');
  console.log('  --concurrency <n>        Parallel translation requests (default 4).');
  console.log('Options for pack:');
  console.log('  --python <path>          Use a specific Python interpreter.');
  console.log('  --keep-temp              Preserve the temporary working folder.');
  console.log('  --variant <name>         Build variant: base, lim-xf, lim-mvh, full-xf, full-mvh, or all.');
  console.log('Options for import:');
  console.log('  --python <path>          Use a specific Python interpreter.');
  console.log('Options for diff:');
  console.log('  --language <code>        Shorthand for translations/<code>.ndjson.');
  console.log('  --ref <gitRef>           Baseline Git reference (default HEAD).');
}

main();
