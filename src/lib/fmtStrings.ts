import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import type { LocalizationEntry } from '../types.js';

interface DirEntry {
  name: string;
  fullPath: string;
  isDirectory: boolean;
}

export async function collectFmtStringEntries(rootDir: string): Promise<LocalizationEntry[]> {
  const normalizedRoot = path.resolve(rootDir);
  const entries: LocalizationEntry[] = [];
  const queue: DirEntry[] = [
    { name: '', fullPath: normalizedRoot, isDirectory: true },
  ];

  while (queue.length > 0) {
    const current = queue.pop();
    if (!current) {
      continue;
    }

    if (!current.isDirectory) {
      if (!current.name.toLowerCase().endsWith('.txt')) {
        continue;
      }
      const relativePath = toPosix(path.relative(normalizedRoot, current.fullPath));
      const rawBuffer = await readFile(current.fullPath);
      const fileContent = decodeTextBuffer(rawBuffer);
      parseFmtFile(relativePath, fileContent, entries);
      continue;
    }

    const dirents = await readdir(current.fullPath, { withFileTypes: true });
    for (const dirent of dirents) {
      const fullPath = path.join(current.fullPath, dirent.name);
      queue.push({
        name: dirent.name,
        fullPath,
        isDirectory: dirent.isDirectory(),
      });
    }
  }

  entries.sort((a, b) => {
    if (a.namespace !== b.namespace) {
      return a.namespace.localeCompare(b.namespace);
    }
    return a.key.localeCompare(b.key);
  });

  return entries;
}

function parseFmtFile(relativePath: string, rawContent: string, acc: LocalizationEntry[]): void {
  const normalized = rawContent.replace(/\r\n?|\u2028|\u2029/g, '\n');
  const lines = normalized.split('\n');

  for (const line of lines) {
    if (!line) {
      continue;
    }
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }

    const eqIndex = line.indexOf('=');
    if (eqIndex === -1) {
      continue;
    }

    const key = line.slice(0, eqIndex).trim();
    const value = line.slice(eqIndex + 1).trimStart();
    if (!key) {
      continue;
    }

    acc.push({
      namespace: relativePath,
      key,
      source: value,
    });
  }
}

function toPosix(input: string): string {
  return input.split(path.sep).join('/');
}

function decodeTextBuffer(buffer: Buffer): string {
  if (buffer.length === 0) {
    return '';
  }

  // UTF-16 BOM detection
  if (buffer.length >= 2) {
    const bom0 = buffer[0];
    const bom1 = buffer[1];
    if (bom0 === 0xff && bom1 === 0xfe) {
      return buffer.slice(2).toString('utf16le');
    }
    if (bom0 === 0xfe && bom1 === 0xff) {
      const swapped = Buffer.from(buffer.slice(2));
      if (swapped.length > 0) {
        swapped.swap16();
      }
      return swapped.toString('utf16le');
    }
  }

  // Heuristic: many null bytes → treat as UTF-16 LE
  const sampleLength = Math.min(buffer.length, 128);
  let nullCount = 0;
  for (let i = 0; i < sampleLength; i += 1) {
    if (buffer[i] === 0) {
      nullCount += 1;
    }
  }
  if (nullCount > sampleLength / 4) {
    return buffer.toString('utf16le');
  }

  // Remove UTF-8 BOM if present before returning
  if (buffer.length >= 3 && buffer[0] === 0xef && buffer[1] === 0xbb && buffer[2] === 0xbf) {
    return buffer.slice(3).toString('utf8');
  }

  return buffer.toString('utf8');
}
