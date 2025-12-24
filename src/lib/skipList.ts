import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { TranslationItem } from './translationFile.js';

type RawRule = {
  namespace?: string; // Optional: undefined means "all namespaces"
  keyRegex?: string;
  sourcePattern?: string;
};

type SkipRule = {
  namespace?: string; // Optional: undefined means "all namespaces"
  keyRegex?: RegExp;
  sourcePattern?: RegExp;
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
    keyRegex: rule.keyRegex ? new RegExp(rule.keyRegex) : undefined,
    sourcePattern: rule.sourcePattern ? new RegExp(rule.sourcePattern) : undefined,
  }));
  cachedRules = rules;
  return rules;
}

export function shouldSkipTranslation(namespace: string, key: string, source?: string | null): boolean {
  return loadRules().some((rule) => {
    // undefined namespace means "all namespaces"
    if (rule.namespace !== undefined && rule.namespace !== namespace) {
      return false;
    }
    // Check key pattern
    if (rule.keyRegex) {
      if (!rule.keyRegex.test(key)) {
        return false;
      }
    }
    // Check source pattern (if specified, source must match to skip)
    if (rule.sourcePattern) {
      if (source == null || !rule.sourcePattern.test(source)) {
        return false;
      }
    }
    return true;
  });
}

export function sanitizeTranslationItem(item: TranslationItem): TranslationItem {
  if (shouldSkipTranslation(item.namespace, item.key, item.source)) {
    if (item.translated != null) {
      return { ...item, translated: null };
    }
  }
  return item;
}

export function sanitizeTranslationItems(items: TranslationItem[]): TranslationItem[] {
  return items.map(sanitizeTranslationItem);
}
