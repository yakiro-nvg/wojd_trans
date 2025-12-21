import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { generateObject, type LanguageModel } from 'ai';
import { createAmazonBedrock } from '@ai-sdk/amazon-bedrock';
import { createGoogleGenerativeAI } from '@ai-sdk/google';
import { select } from '@inquirer/prompts';
import { z } from 'zod';
import { promptInput } from '../lib/prompt.js';
import {
  loadTranslationFile,
  saveTranslationFile,
  saveTranslationUpdates,
  resetTranslations,
  countPendingTranslations,
  type TranslationItem,
} from '../lib/translationFile.js';
import { shouldSkipTranslation } from '../lib/skipList.js';

const LANGUAGE_LABELS: Record<string, string> = {
  vi: 'Vietnamese',
  en: 'English',
};

const DEFAULT_BATCH_SIZE = 5;
const DEFAULT_CONCURRENCY = 4;
const DEFAULT_CHECKPOINT = 20;
const GEMINI_DEFAULT_BATCH_SIZE = 20;
const GEMINI_DEFAULT_CONCURRENCY = 4;
const GEMINI_DEFAULT_MODEL_ID = 'gemini-3-pro-preview';
const GEMINI_DEFAULT_THINKING_LEVEL = 'low';
const MAX_ATTEMPTS = 5;
const SKIP_NAMESPACES = new Set(['RankDetail']);
const SKIP_ROWOBJECT_KEYS = ['110731', '110735', '110761', '110769', '110770', '110772'];

export interface TranslateOptions {
  translationPath: string;
  language: string;
  force?: boolean;
  limit?: number;
  testLimit?: number;
  batchSize?: number;
  systemPromptPath?: string;
  checkpoint?: number;
  concurrency?: number;
}

type ModelProvider = 'bedrock' | 'gemini';

interface BaseTranslationConfig {
  provider: ModelProvider;
  targetLanguage: string;
  systemPrompt: string;
}

interface BedrockTranslationConfig extends BaseTranslationConfig {
  provider: 'bedrock';
  accessKeyId: string;
  secretAccessKey: string;
  region: string;
  modelId: string;
}

interface GeminiTranslationConfig extends BaseTranslationConfig {
  provider: 'gemini';
  apiKey: string;
  modelId: string;
  thinkingLevel?: 'minimal' | 'low' | 'medium' | 'high';
  includeThoughts?: boolean;
}

type TranslationConfig = BedrockTranslationConfig | GeminiTranslationConfig;

interface TranslationResult {
  id: number;
  translated: string;
}

type TranslationSchema = z.ZodSchema<{ translations: TranslationResult[] }>;

type TranslationGroup = {
  groupId: number;
  sampleNamespace: string;
  sampleKey: string;
  source: string;
  indexes: number[];
  entryCount: number;
  attempts: number;
};

interface CatalogOptions extends TranslateOptions {
  label: string;
  existingConfig?: TranslationConfig | null;
  skipIfMissing?: boolean;
}

interface CatalogResult {
  count: number;
  config: TranslationConfig | null;
  cancelled: boolean;
}

async function translateCatalog(options: CatalogOptions): Promise<CatalogResult> {
  const { translationPath, language, label } = options;

  if (!translationPath) {
    throw new Error('Missing translation JSON path.');
  }
  if (!language) {
    throw new Error('Missing target language code.');
  }

  const contextKey = `${label}:${language}`;

  let items = await loadTranslationFile(translationPath);
  if (items.length === 0) {
    if (options.skipIfMissing) {
      console.log(`[${label}:${language}] No catalog entries found. Skipping.`);
      return { count: 0, config: options.existingConfig ?? null, cancelled: false };
    }
    throw new Error('Translation file is empty. Run sync before translating.');
  }

  if (options.force === true) {
    items = resetTranslations(items);
    await saveTranslationFile(translationPath, items);
  }

  const pendingOverallBefore = countPendingTranslations(items);
  if (pendingOverallBefore === 0) {
    console.log(`[${label}:${language}] No entries require translation.`);
    return { count: 0, config: options.existingConfig ?? null, cancelled: false };
  }

  let translationConfig = options.existingConfig ?? null;
  if (!translationConfig) {
    translationConfig = await promptForTranslationConfig(language, options.systemPromptPath);
  }

  const queueBase = buildTranslationQueue(items, options);
  if (queueBase.length === 0) {
    console.log(`[${label}:${language}] No entries matched the translation criteria (limit/test).`);
    return { count: 0, config: translationConfig, cancelled: false };
  }

  const totalGroups = queueBase.length;
  const totalEntriesScheduled = queueBase.reduce((sum, group) => sum + group.entryCount, 0);

  const defaultBatchSize = translationConfig.provider === 'gemini' ? GEMINI_DEFAULT_BATCH_SIZE : DEFAULT_BATCH_SIZE;
  const defaultConcurrency = translationConfig.provider === 'gemini' ? GEMINI_DEFAULT_CONCURRENCY : DEFAULT_CONCURRENCY;

  const effectiveBatchSize = validateBatchSize(options.batchSize ?? defaultBatchSize);
  const concurrency = validateConcurrency(options.concurrency ?? defaultConcurrency);

  console.log(
    `[${label}:${language}] Pending entries overall: ${pendingOverallBefore}. Processing up to ${totalGroups} unique sources (${totalEntriesScheduled} entries).`,
  );
  if (translationConfig.provider === 'gemini' && options.batchSize == null) {
    console.log(
      `[${label}:${language}] Gemini defaults applied (Level 1): batch size ${effectiveBatchSize}, concurrency ${concurrency}.`,
    );
  }

  const model = createModelFromConfig(translationConfig);
  const translationSchema: TranslationSchema = z.object({
    translations: z
      .array(
        z.object({
          id: z.number(),
          translated: z.string().min(1),
        }),
      )
      .nonempty(),
  });

  const checkpoint = normalizeCheckpoint(options.checkpoint);

  const workQueue: TranslationGroup[] = [...queueBase];
  const failures: TranslationGroup[] = [];
  let processedGroups = 0;
  let processedEntries = 0;
  let pendingOverall = pendingOverallBefore;
  const batchRates: number[] = [];
  let cancelled = false;
  let dirtyCount = 0;
  const dirtyIndices = new Set<number>();

  const handleInterrupt = (signal: NodeJS.Signals) => {
    if (cancelled) {
      return;
    }
    cancelled = true;
    console.warn(`\nReceived ${signal}. Finishing current requests and saving progress...`);
  };

  process.on('SIGINT', handleInterrupt);
  process.on('SIGTERM', handleInterrupt);

  try {
    while (workQueue.length > 0 && !cancelled) {
      const groupSize = Math.min(effectiveBatchSize * concurrency, workQueue.length);
      const groupBatch = workQueue.splice(0, groupSize);
      if (groupBatch.length === 0) {
        break;
      }

      const chunks: TranslationGroup[][] = [];
      for (let i = 0; i < groupBatch.length; i += effectiveBatchSize) {
        chunks.push(groupBatch.slice(i, i + effectiveBatchSize));
      }

      console.log(
        `Translating ${groupBatch.length} unique sources (${chunks.length} request${chunks.length > 1 ? 's' : ''}) with concurrency ${concurrency}.`,
      );

      const results = await Promise.all(
        chunks.map(async (chunk) => {
          const startTime = Date.now();
          try {
            const translations = await translateChunk({
              entries: chunk,
              config: translationConfig,
              model,
              schema: translationSchema,
            });
            const duration = (Date.now() - startTime) / 1000;
            return { chunk, translations, duration } as const;
          } catch (error) {
            const duration = (Date.now() - startTime) / 1000;
            return { chunk, error, duration } as const;
          }
        }),
      );

      for (const result of results) {
        if ('error' in result) {
          const attemptDisplay = (result.chunk[0]?.attempts ?? 0) + 1;
          console.error(
            `[${label}:${language}] Translation request failed (${describeError(result.error)}). Retrying entries individually (attempt ${attemptDisplay}/${MAX_ATTEMPTS}).`,
          );
          if (!cancelled) {
            const backoffMs = computeBackoffMs(attemptDisplay);
            console.warn(
              `[${label}:${language}] Waiting ${Math.round(backoffMs)}ms before retrying failed entries.`,
            );
            await delay(backoffMs);
            enqueueRetries(result.chunk, workQueue, failures, contextKey, true);
          }
          continue;
        }

        const { chunk, translations, duration } = result;
        const translationLookup = new Map<number, string>();
        for (const item of translations) {
          translationLookup.set(item.id, item.translated.trim());
        }

        const missing: TranslationGroup[] = [];
        let appliedEntriesForChunk = 0;
        let appliedGroupsForChunk = 0;

        for (const group of chunk) {
          const translated = translationLookup.get(group.groupId);
          if (!translated) {
            if (group.attempts + 1 < MAX_ATTEMPTS) {
              console.warn(
                `[${label}:${language}] Retrying namespace="${group.sampleNamespace}" key="${group.sampleKey}" (attempt ${group.attempts + 1}/${MAX_ATTEMPTS}).`,
              );
              missing.push({ ...group, attempts: group.attempts + 1 });
            } else {
              console.error(
                `[${label}:${language}] Failed to translate namespace="${group.sampleNamespace}" key="${group.sampleKey}" after ${MAX_ATTEMPTS} attempts.`,
              );
              failures.push(group);
            }
            continue;
          }

          let appliedCount = 0;
          for (const idx of group.indexes) {
            const current = items[idx];
            if (!current) {
              continue;
            }
            if (current.translated !== translated) {
              items[idx] = { ...current, translated };
              appliedCount += 1;
              dirtyIndices.add(idx);
            }
          }

          if (appliedCount > 0) {
            appliedEntriesForChunk += appliedCount;
            appliedGroupsForChunk += 1;
          }
        }

        if (missing.length > 0 && !cancelled) {
          if (missing.length === chunk.length) {
            const attemptDisplay = (missing[0]?.attempts ?? 0);
            const backoffMs = computeBackoffMs(attemptDisplay);
            console.warn(
              `[${label}:${language}] All entries missing translations; waiting ${Math.round(backoffMs)}ms before retry.`,
            );
            await delay(backoffMs);
          }
          workQueue.push(...missing);
        }

        if (appliedEntriesForChunk > 0 || appliedGroupsForChunk > 0) {
          processedEntries += appliedEntriesForChunk;
          processedGroups += appliedGroupsForChunk;
          dirtyCount += appliedEntriesForChunk;
          pendingOverall = Math.max(0, pendingOverall - appliedEntriesForChunk);

          const durationSeconds = Math.max(duration, 0.1);
          const groupRate = appliedGroupsForChunk / durationSeconds;
          if (!Number.isNaN(groupRate) && groupRate > 0) {
            batchRates.push(groupRate);
            if (batchRates.length > 5) {
              batchRates.shift();
            }
          }
        }

        const smoothedRate = computeAverage(batchRates);
        const remainingGroups = Math.max(totalGroups - processedGroups, 0);
        const remainingEntries = Math.max(totalEntriesScheduled - processedEntries, 0);
        const estimatedSeconds = smoothedRate > 0 ? Math.round(remainingGroups / smoothedRate) : null;
        const eta = estimatedSeconds != null ? formatDuration(estimatedSeconds) : 'unknown';
        const percentGroups = totalGroups > 0 ? ((processedGroups / totalGroups) * 100).toFixed(1) : '0.0';
        const recentEntryRate = duration > 0 ? appliedEntriesForChunk / Math.max(duration, 0.1) : 0;

        console.log(
          `[${label}:${language}] Progress this run: ${processedGroups}/${totalGroups} sources (${processedEntries}/${totalEntriesScheduled} entries). ` +
            `Remaining sources: ${remainingGroups}. Remaining entries: ${remainingEntries}. Pending overall: ${Math.max(pendingOverall, 0)}. ` +
            `Recent source rate: ${smoothedRate.toFixed(2)} sources/s (entries ~${recentEntryRate.toFixed(2)}/s). ETA: ${eta}.`,
        );

        if (appliedEntriesForChunk === 0 && missing.length === 0) {
          console.error(`[${label}:${language}] No translations returned for current batch; skipping to avoid infinite loop.`);
        }

        if (cancelled) {
          break;
        }
      }

      if (checkpoint !== null && dirtyCount >= checkpoint && dirtyIndices.size > 0) {
        await saveTranslationUpdates(translationPath, items, dirtyIndices);
        dirtyIndices.clear();
        dirtyCount = 0;
      }

      if (cancelled) {
        break;
      }
    }

    if ((dirtyCount > 0 || cancelled) && dirtyIndices.size > 0) {
      await saveTranslationUpdates(translationPath, items, dirtyIndices);
      dirtyIndices.clear();
      dirtyCount = 0;
    }

    if (failures.length > 0) {
      console.error(
        `[${label}:${language}] Untranslated entries after ${MAX_ATTEMPTS} attempts: ${failures.length}. See logs for details.`,
      );
    }

    if (cancelled) {
      console.warn(`[${label}:${language}] Translation interrupted before completion. Progress saved.`);
    } else {
      console.log(
        `[${label}:${language}] Translation run completed. Translated this session: ${processedGroups} sources (${processedEntries} entries). Pending overall after run: ${Math.max(pendingOverall, 0)}.`,
      );
    }

    return { count: processedEntries, config: translationConfig, cancelled };
  } finally {
    process.off('SIGINT', handleInterrupt);
    process.off('SIGTERM', handleInterrupt);
  }
}

export async function translate(options: TranslateOptions): Promise<number> {
  const { translationPath, language } = options;

  const fmtPath = path.join('translations', `${language}.fmtstring.ndjson`);
  const fmtResult = await translateCatalog({
    ...options,
    translationPath: fmtPath,
    language,
    label: 'fmtstring',
    existingConfig: null,
    skipIfMissing: true,
  });

  let totalTranslated = fmtResult.count;
  let sharedConfig = fmtResult.config;

  if (fmtResult.cancelled) {
    return totalTranslated;
  }

  const locresResult = await translateCatalog({
    ...options,
    translationPath,
    language,
    label: 'locres',
    existingConfig: sharedConfig,
    skipIfMissing: false,
  });

  totalTranslated += locresResult.count;

  return totalTranslated;
}

async function promptForTranslationConfig(language: string, explicitPromptPath?: string): Promise<TranslationConfig> {
  console.log('--- Translation Setup ---');
  const providerRaw = await select<ModelProvider>({
    message: 'Select model provider',
    choices: [
      { name: 'Amazon Bedrock (Claude)', value: 'bedrock' },
      { name: 'Google Gemini', value: 'gemini' },
    ],
    default: 'bedrock',
  });

  const normalizedLanguage = language.trim().toLowerCase();
  console.log(`Target language: ${describeLanguage(normalizedLanguage)}`);
  const systemPrompt = await loadSystemPrompt(normalizedLanguage, explicitPromptPath);

  if (providerRaw === 'bedrock') {
    console.log('Model provider: Amazon Bedrock (Claude family)');
    const accessKeyId = await promptInput('Enter AWS Access Key ID');
    const secretAccessKey = await promptInput('Enter AWS Secret Access Key');
    const region = await promptInput('Enter AWS Region');
    const modelId = await promptInput('Enter Claude model ID');

    return {
      provider: 'bedrock',
      accessKeyId,
      secretAccessKey,
      region,
      modelId,
      targetLanguage: normalizedLanguage,
      systemPrompt,
    };
  }

  console.log('Model provider: Google Gemini');
  const apiKey = await promptInput('Enter Google Generative AI API Key');
  const modelId = (await promptInput('Enter Gemini model ID', { defaultValue: GEMINI_DEFAULT_MODEL_ID })).trim();
  const thinkingLevel = supportsGeminiThinkingConfig(modelId) ? GEMINI_DEFAULT_THINKING_LEVEL : undefined;

  return {
    provider: 'gemini',
    apiKey,
    modelId,
    thinkingLevel,
    includeThoughts: false,
    targetLanguage: normalizedLanguage,
    systemPrompt,
  };
}

async function loadSystemPrompt(language: string, explicitPromptPath?: string): Promise<string> {
  const promptPath = explicitPromptPath
    ? path.resolve(process.cwd(), explicitPromptPath)
    : getDefaultSystemPromptPath(language);

  try {
    const content = await readFile(promptPath, 'utf8');
    const trimmed = content.trim();
    if (!trimmed) {
      throw new Error('System prompt file is empty.');
    }
    return trimmed;
  } catch (error) {
    throw new Error(`Failed to load system prompt from ${promptPath}: ${(error as Error).message}`);
  }
}

function getDefaultSystemPromptPath(language: string): string {
  const currentFile = fileURLToPath(import.meta.url);
  const projectRoot = path.resolve(path.dirname(currentFile), '..', '..');
  return path.resolve(projectRoot, 'prompts', language, 'system-prompt.txt');
}

function describeLanguage(language: string): string {
  const normalized = language.trim().toLowerCase();
  return LANGUAGE_LABELS[normalized] ?? normalized;
}

function supportsGeminiThinkingConfig(modelId: string): boolean {
  const normalized = modelId.trim().toLowerCase();
  return normalized.startsWith('gemini-2.') || normalized.startsWith('gemini-3.') || normalized.includes('thinking');
}

function isBedrockConfig(config: TranslationConfig): config is BedrockTranslationConfig {
  return config.provider === 'bedrock';
}

function createModelFromConfig(config: TranslationConfig): LanguageModel {
  if (isBedrockConfig(config)) {
    const bedrock = createAmazonBedrock({
      accessKeyId: config.accessKeyId,
      secretAccessKey: config.secretAccessKey,
      region: config.region,
    });
    return bedrock(config.modelId);
  }

  const google = createGoogleGenerativeAI({ apiKey: config.apiKey });
  return google(config.modelId);
}

async function translateChunk(params: {
  entries: TranslationGroup[];
  config: TranslationConfig;
  model: LanguageModel;
  schema: TranslationSchema;
}): Promise<TranslationResult[]> {
  const { entries, config, model, schema } = params;

  const prompt = buildPrompt(entries, config.targetLanguage);
  const providerOptions =
    config.provider === 'gemini' && config.thinkingLevel != null
      ? {
          google: {
            thinkingConfig: {
              thinkingLevel: config.thinkingLevel,
              ...(config.includeThoughts === true ? { includeThoughts: true } : {}),
            },
          },
        }
      : undefined;
  const result = await generateObject({
    model,
    system: config.systemPrompt,
    prompt,
    schema,
    ...(providerOptions ? { providerOptions } : {}),
  });

  if (!result || !result.object) {
    throw new Error('No object generated from structured output response.');
  }

  return result.object.translations;
}

function buildPrompt(entries: TranslationGroup[], language: string): string {
  const lines: string[] = [];
  const languageName = describeLanguage(language);

  lines.push(`Target language: ${languageName}`);
  lines.push('Entries:');

  entries.forEach((group) => {
    lines.push(`- id: ${group.groupId}`);
    lines.push(`  namespace: ${group.sampleNamespace}`);
    lines.push(`  key: ${group.sampleKey}`);
    if (group.entryCount > 1) {
      lines.push(`  occurrences: ${group.entryCount}`);
    }
    lines.push('  source: |');
    const sourceLines = group.source.split('\n');
    for (const line of sourceLines) {
      lines.push(`    ${line}`);
    }
  });

  return lines.join('\n');
}

function buildTranslationQueue(items: TranslationItem[], options: TranslateOptions): TranslationGroup[] {
  const groupsBySource = new Map<string, TranslationGroup>();
  const orderedGroups: TranslationGroup[] = [];

  items.forEach((item, index) => {
    if (shouldSkipTranslation(item.namespace, item.key, item.source)) {
      return;
    }
    const hasManual = item.translated !== null && item.translated !== undefined;
    if (hasManual) {
      return;
    }

    const locres = item.locresImport && item.locresImport.trim().length > 0 ? item.locresImport.trim() : null;
    const baseSource = item.source && item.source.trim().length > 0 ? item.source.trim() : null;
    const groupingSource = locres ?? baseSource;
    if (!groupingSource) {
      return;
    }

    let group = groupsBySource.get(groupingSource);
    if (!group) {
      const groupId = orderedGroups.length;
      group = {
        groupId,
        sampleNamespace: item.namespace,
        sampleKey: item.key,
        source: groupingSource,
        indexes: [],
        entryCount: 0,
        attempts: 0,
      };
      groupsBySource.set(groupingSource, group);
      orderedGroups.push(group);
    }
    group.indexes.push(index);
    group.entryCount += 1;
  });

  let groups = orderedGroups;
  const effectiveLimit = determineLimit(options);
  if (effectiveLimit != null) {
    groups = groups.slice(0, effectiveLimit);
  }

  if (typeof options.testLimit === 'number') {
    const limit = Math.max(0, options.testLimit);
    groups = groups.slice(0, limit);
  }

  return groups;
}

function determineLimit(options: TranslateOptions): number | null {
  if (typeof options.limit === 'number') {
    return Math.max(0, options.limit);
  }
  return null;
}

function normalizeCheckpoint(value: number | undefined): number | null {
  if (value === undefined) {
    return DEFAULT_CHECKPOINT;
  }
  if (value <= 0) {
    return null;
  }
  return Math.floor(value);
}

function validateBatchSize(value: number): number {
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error('Batch size must be a positive integer.');
  }
  return value;
}

function validateConcurrency(value: number): number {
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error('Concurrency must be a positive integer.');
  }
  return value;
}

function enqueueRetries(
  entries: TranslationGroup[],
  workQueue: TranslationGroup[],
  failures: TranslationGroup[],
  context: string,
  fromRequestError = false,
): void {
  for (const entry of entries) {
    if (entry.attempts + 1 < MAX_ATTEMPTS) {
      workQueue.push({ ...entry, attempts: entry.attempts + 1 });
    } else {
      const reason = fromRequestError ? 'request error' : 'missing translation';
      console.error(
        `[${context}] Failed to translate namespace="${entry.sampleNamespace}" key="${entry.sampleKey}" after ${MAX_ATTEMPTS} attempts (${reason}).`,
      );
      failures.push(entry);
    }
  }
}

function computeAverage(values: number[]): number {
  if (values.length === 0) {
    return 0;
  }
  const sum = values.reduce((acc, value) => acc + value, 0);
  return sum / values.length;
}

function describeError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function formatDuration(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  const parts: string[] = [];
  if (hours > 0) {
    parts.push(`${hours}h`);
  }
  if (minutes > 0 || hours > 0) {
    parts.push(`${minutes}m`);
  }
  parts.push(`${seconds}s`);

  return parts.join(' ');
}

function computeBackoffMs(attempt: number): number {
  const base = 1000;
  const capped = Math.min(base * 2 ** Math.max(0, attempt - 1), 30000);
  const jitter = Math.random() * 0.1 * capped;
  return capped + jitter;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
