import { stat } from 'node:fs/promises';

export async function ensureWritable(outputPath: string, force: boolean): Promise<void> {
  try {
    await stat(outputPath);
    if (!force) {
      throw new Error(`Output file ${outputPath} already exists. Use --force to overwrite.`);
    }
  } catch (error) {
    if (isErrnoException(error) && error.code === 'ENOENT') {
      return;
    }
    throw error;
  }
}

interface ErrnoException extends Error {
  code?: string;
}

function isErrnoException(error: unknown): error is ErrnoException {
  return Boolean(error) && typeof error === 'object' && 'code' in (error as Record<string, unknown>);
}
