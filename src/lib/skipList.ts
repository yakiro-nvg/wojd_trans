import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { TranslationItem } from './translationFile.js';

type RawRule = {
  namespace: string;
  keyRegex?: string;
};

type SkipRule = {
  namespace: string;
  regex?: RegExp;
};

let cachedRules: SkipRule[] | null = null;

function loadRules(): SkipRule[] {
  if (cachedRules) {
    return cachedRules;
  }
  const configPath = path.resolve('config', 'translation-skip.json');
  const raw = readFileSync(configPath, 'utf8');
  const parsed = JSON.parse(raw) as { rules?: RawRule[] };
  const rules = (parsed.rules ?? []).map<SkipRule>((rule) => ({
    namespace: rule.namespace,
    regex: rule.keyRegex ? new RegExp(rule.keyRegex) : undefined,
  }));
  cachedRules = rules;
  return rules;
}

export function shouldSkipTranslation(namespace: string, key: string): boolean {
  return loadRules().some((rule) => {
    if (rule.namespace !== namespace) {
      return false;
    }
    if (rule.regex) {
      return rule.regex.test(key);
    }
    return true;
  });
}

export function sanitizeTranslationItem(item: TranslationItem): TranslationItem {
  if (shouldSkipTranslation(item.namespace, item.key)) {
    if (item.translated != null) {
      return { ...item, translated: null };
    }
  }
  return item;
}

export function sanitizeTranslationItems(items: TranslationItem[]): TranslationItem[] {
  return items.map(sanitizeTranslationItem);
}
