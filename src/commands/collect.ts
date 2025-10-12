import path from 'node:path';
import { readdir, readFile, stat, writeFile } from 'node:fs/promises';
import { parseLocalizationLog } from '../lib/logParser.js';
import { ensureWritable } from '../lib/file.js';
import type { LocalizationEntry } from '../types.js';

export interface CollectOptions {
  logPath?: string;
  outputPath: string;
  force?: boolean;
}

export interface CollectResult {
  entryCount: number;
  logFiles: string[];
}

const LOG_FILE_REGEX = /^ZhuxianClient(?:-backup-[0-9.\-]+)?\.log$/;

export async function collect({ logPath, outputPath, force = false }: CollectOptions): Promise<CollectResult> {
  if (!outputPath) {
    throw new Error('Missing outputPath argument.');
  }

  const logFiles = await resolveLogFiles(logPath);
  if (logFiles.length === 0) {
    const target = logPath ? path.resolve(logPath) : process.cwd();
    throw new Error(`No ZhuxianClient log files found at ${target}.`);
  }

  const aggregatedEntries: LocalizationEntry[] = [];

  for (const filePath of logFiles) {
    const rawLog = await readFile(filePath, 'utf8');
    const entries = parseLocalizationLog(rawLog);
    aggregatedEntries.push(...entries);
  }

  const uniqueEntries = dedupeEntries(aggregatedEntries);

  await ensureWritable(outputPath, force === true);
  await writeFile(outputPath, JSON.stringify(uniqueEntries, null, 2), 'utf8');

  return {
    entryCount: uniqueEntries.length,
    logFiles,
  };
}

function dedupeEntries(entries: LocalizationEntry[]): LocalizationEntry[] {
  const byKey = new Map<string, LocalizationEntry>();

  for (const entry of entries) {
    const key = entry.key;
    const source = entry.source;
    if (!key || source == null) {
      continue;
    }

    const trimmed = source.trim();
    if (!trimmed) {
      continue;
    }

    if (!containsHanCharacters(trimmed)) {
      continue;
    }

    const namespace = entry.namespace ?? '';
    const mapKey = `${namespace}\u0000${key}`;
    byKey.set(mapKey, { ...entry, namespace, key, source });
  }

  const unique = Array.from(byKey.values());

  unique.sort((a, b) => {
    if (a.namespace !== b.namespace) {
      return a.namespace.localeCompare(b.namespace);
    }
    return a.key.localeCompare(b.key);
  });

  return unique;
}

const HAN_PLUS = /(?:\p{Script=Han}|[\u3000-\u303F\uFE30-\uFE4F\uFF00-\uFFEF\u2E80-\u2EFF\u2F00-\u2FDF\u2FF0-\u2FFF\u31C0-\u31EF\uF900-\uFAFF\u2F800-\u2FA1F])/u;

function containsHanCharacters(value: string): boolean {
  return HAN_PLUS.test(value);
}

async function resolveLogFiles(logPath?: string): Promise<string[]> {
  const candidates: { path: string; mtimeMs: number }[] = [];

  if (logPath) {
    const resolved = path.resolve(logPath);
    const stats = await stat(resolved).catch(() => {
      throw new Error(`Log path not found: ${resolved}`);
    });

    if (stats.isDirectory()) {
      const fromDir = await collectLogsFromDirectory(resolved);
      candidates.push(...fromDir);
    } else if (stats.isFile()) {
      candidates.push({ path: resolved, mtimeMs: stats.mtimeMs });
    } else {
      throw new Error(`Unsupported log path type: ${resolved}`);
    }
  } else {
    const fromCwd = await collectLogsFromDirectory(process.cwd());
    candidates.push(...fromCwd);
  }

  candidates.sort((a, b) => a.mtimeMs - b.mtimeMs);
  return candidates.map((item) => item.path);
}

async function collectLogsFromDirectory(directory: string): Promise<{ path: string; mtimeMs: number }[]> {
  const dirents = await readdir(directory, { withFileTypes: true });
  const matches: { path: string; mtimeMs: number }[] = [];

  for (const dirent of dirents) {
    if (!dirent.isFile()) {
      continue;
    }
    if (!LOG_FILE_REGEX.test(dirent.name)) {
      continue;
    }

    const fullPath = path.join(directory, dirent.name);
    const stats = await stat(fullPath);
    if (!stats.isFile()) {
      continue;
    }

    matches.push({ path: fullPath, mtimeMs: stats.mtimeMs });
  }

  return matches;
}
