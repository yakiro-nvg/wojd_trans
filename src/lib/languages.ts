import { readFile } from 'node:fs/promises';
import path from 'node:path';

let cachedLanguages: string[] | null = null;

export async function getSupportedLanguages(configPath?: string): Promise<string[]> {
  if (cachedLanguages) {
    return cachedLanguages;
  }

  const resolvedPath = path.resolve(configPath ?? 'languages.json');
  try {
    const raw = await readFile(resolvedPath, 'utf8');
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      throw new Error('languages.json must be an array of strings');
    }
    const cleaned = parsed
      .map((item) => (typeof item === 'string' ? item.trim() : ''))
      .filter((item) => item.length > 0);
    cachedLanguages = cleaned.length > 0 ? cleaned : ['vi'];
  } catch (error) {
    cachedLanguages = ['vi'];
  }

  return cachedLanguages;
}

export function clearLanguagesCache(): void {
  cachedLanguages = null;
}
