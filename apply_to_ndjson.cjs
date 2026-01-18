const fs = require('fs');

// Load translations from to_translate.json (already translated)
const toTranslate = JSON.parse(fs.readFileSync('translations/to_translate.json', 'utf8'));

// Build lookup map: source text -> vietnamese translation
const translationMap = new Map();
for (const item of toTranslate) {
  if (item.vi && item.vi.trim()) {
    translationMap.set(item.zh, item.vi);
  }
}
console.log('Loaded translations:', translationMap.size);

// Process vi.ndjson
const content = fs.readFileSync('translations/vi.ndjson', 'utf8');
const lines = content.split('\n');
let updated = 0;
const output = [];

for (const line of lines) {
  if (!line.trim()) {
    output.push(line);
    continue;
  }

  try {
    const item = JSON.parse(line);

    // Check if needs translation
    if (!item.translated || item.translated.trim() === '') {
      const source = item.source || item.locresImport || '';
      if (translationMap.has(source)) {
        item.translated = translationMap.get(source);
        updated++;
      }
    }

    output.push(JSON.stringify(item));
  } catch(e) {
    output.push(line);
  }
}

console.log('Updated entries:', updated);

// Save
fs.writeFileSync('translations/vi.ndjson', output.join('\n'), 'utf8');
console.log('Saved vi.ndjson');
