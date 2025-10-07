export interface LocalizationEntry {
  namespace: string;
  key: string;
  source: string;
  translated?: string | null;
}

export interface TranslatedEntry extends LocalizationEntry {
  translated: string;
}
