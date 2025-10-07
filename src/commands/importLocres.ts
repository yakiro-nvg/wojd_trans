import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { detectPython, runCommand } from '../lib/python.js';
import { getSupportedLanguages } from '../lib/languages.js';

export interface ImportLocresOptions {
  locresPath: string;
  pythonPath?: string;
}

export async function importLocres(options: ImportLocresOptions): Promise<void> {
  const { locresPath, pythonPath } = options;

  if (!locresPath) {
    throw new Error('Missing locres file path.');
  }

  const pythonExecutable = detectPython(pythonPath);
  const scriptPath = fileURLToPath(new URL('../../scripts/import_locres.py', import.meta.url));

  const languages = await getSupportedLanguages();
  for (const language of languages) {
    const catalogPath = path.resolve('translations', `${language}.ndjson`);
    console.log(`Importing ${locresPath} into ${catalogPath} [${language}]`);
    await runCommand(pythonExecutable, [
      scriptPath,
      '--locres',
      path.resolve(locresPath),
      '--catalog',
      catalogPath,
    ]);
  }
}
