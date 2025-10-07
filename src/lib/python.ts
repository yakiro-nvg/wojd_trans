import { spawn, spawnSync } from 'node:child_process';

export interface CommandResult {
  stdout: string;
  stderr: string;
}

export function detectPython(preferred?: string): string {
  if (preferred) {
    return preferred;
  }
  const candidates = ['python3', 'python'];
  for (const exe of candidates) {
    const result = spawnSync(exe, ['--version'], { stdio: 'ignore' });
    if (result.status === 0 && !result.error) {
      return exe;
    }
  }
  throw new Error('Unable to find a Python interpreter (tried python3 and python).');
}

export async function runCommand(command: string, args: string[]): Promise<CommandResult> {
  return new Promise((resolve, reject) => {
    const proc = spawn(command, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
      process.stdout.write(chunk);
    });
    proc.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
      process.stderr.write(chunk);
    });
    proc.on('error', (error) => reject(error));
    proc.on('close', (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        reject(new Error(`${command} exited with code ${code}`));
      }
    });
  });
}
