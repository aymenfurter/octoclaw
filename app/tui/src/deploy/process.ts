/**
 * Child-process helpers shared by Docker and ACA deploy targets.
 *
 * Wraps `Bun.spawn` to capture output as a string or stream it
 * line-by-line to a callback.
 */

export interface ExecResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

/** Run a command and collect stdout/stderr as strings. */
export async function exec(cmd: string[], cwd?: string): Promise<ExecResult> {
  const proc = Bun.spawn(cmd, { cwd, stdout: "pipe", stderr: "pipe" });
  const [stdout, stderr] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
  ]);
  const exitCode = await proc.exited;
  return { stdout: stdout.trim(), stderr: stderr.trim(), exitCode };
}

/**
 * Run a command and stream stdout/stderr line-by-line via `onLine`.
 *
 * If `onLine` is omitted, output is inherited directly to the
 * terminal (useful for headless / bot mode).
 *
 * @returns `true` when the process exits with code 0.
 */
export async function execStream(
  cmd: string[],
  onLine?: (line: string) => void,
  cwd?: string,
): Promise<boolean> {
  if (!onLine) {
    const proc = Bun.spawn(cmd, { cwd, stdout: "inherit", stderr: "inherit" });
    return (await proc.exited) === 0;
  }

  const proc = Bun.spawn(cmd, { cwd, stdout: "pipe", stderr: "pipe" });
  await Promise.all([
    drainStream(proc.stdout as ReadableStream<Uint8Array>, onLine),
    drainStream(proc.stderr as ReadableStream<Uint8Array>, onLine),
  ]);
  return (await proc.exited) === 0;
}

/** Strip Azure CLI WARNING lines that leak into `--output json`. */
export function stripAzWarnings(raw: string): string {
  return raw
    .split("\n")
    .filter(
      (l) =>
        !l.startsWith("WARNING:") &&
        !l.startsWith("The behavior of this command has been altered"),
    )
    .join("\n")
    .trim();
}

// ---------------------------------------------------------------------------
// Internal
// ---------------------------------------------------------------------------

async function drainStream(
  stream: ReadableStream<Uint8Array> | null,
  onLine: (line: string) => void,
): Promise<void> {
  if (!stream) return;
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) onLine(line);
    }
  }
  if (buffer.trim()) onLine(buffer);
}
