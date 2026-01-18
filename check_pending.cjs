const fs = require('fs');

// Load skip rules
const skipConfig = JSON.parse(fs.readFileSync('config/translation-skip.json', 'utf8'));

function shouldSkip(namespace, key, source) {
  for (const rule of skipConfig.rules) {
    if (rule.namespace && namespace !== rule.namespace) continue;
    if (rule.keyRegex) {
      const regex = new RegExp(rule.keyRegex);
      if (!regex.test(key)) continue;
    }
    if (rule.sourcePattern) {
      const regex = new RegExp(rule.sourcePattern);
      if (!regex.test(source || '')) continue;
    }
    return true;
  }
  return false;
}

const content = fs.readFileSync('translations/vi.ndjson', 'utf8');
let pending = [];
for (const line of content.split('\n')) {
  if (line.trim()) {
    try {
      const item = JSON.parse(line);

      // Skip if matches skip rules
      if (shouldSkip(item.namespace, item.key, item.source || item.locresImport)) {
        continue;
      }

      // Check if pending (no translated field or empty)
      if (!item.translated || item.translated.trim() === '') {
        // Has source or locresImport
        const src = item.source || item.locresImport || '';
        if (src.trim()) {
          pending.push(item);
        }
      }
    } catch(e) {}
  }
}

console.log('Pending items:', pending.length);
console.log('\nFirst 30 pending items:');
pending.slice(0, 30).forEach((p, i) => {
  console.log('---', i+1, '---');
  console.log('ns:', p.namespace);
  console.log('key:', p.key);
  const src = p.source || p.locresImport || '';
  console.log('text:', src.substring(0, 150) + (src.length > 150 ? '...' : ''));
});

// Save pending to file for translation
const pendingForTranslation = pending.map(p => ({
  zh: p.source || p.locresImport,
  vi: '',
  namespace: p.namespace,
  key: p.key
}));
fs.writeFileSync('translations/to_translate.json', JSON.stringify(pendingForTranslation, null, 2));
console.log('\nSaved', pending.length, 'pending items to to_translate.json');
