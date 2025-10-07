import { createInterface } from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';

export interface PromptOptions {
  defaultValue?: string;
  allowEmpty?: boolean;
}

export async function promptInput(question: string, options: PromptOptions = {}): Promise<string> {
  const rl = createInterface({ input, output });

  try {
    const suffix = options.defaultValue ? ` (${options.defaultValue})` : '';
    const answer = await rl.question(`${question}${suffix ? suffix : ''}: `);
    const trimmed = answer.trim();

    if (!trimmed && options.defaultValue) {
      return options.defaultValue;
    }

    if (!trimmed && options.allowEmpty !== true) {
      return promptInput(question, options);
    }

    return trimmed;
  } finally {
    rl.close();
  }
}
