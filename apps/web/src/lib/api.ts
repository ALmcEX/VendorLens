import type { ExampleJob, ProblemDetails } from "@/lib/types";

const configuredBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const API_BASE_URL = configuredBase.replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly problem: ProblemDetails | null,
  ) {
    super(problem?.title ?? `API request failed with status ${status}`);
  }
}

async function parseResponse(response: Response): Promise<ExampleJob> {
  if (!response.ok) {
    let problem: ProblemDetails | null = null;
    try {
      problem = (await response.json()) as ProblemDetails;
    } catch {
      problem = null;
    }
    throw new ApiError(response.status, problem);
  }
  return (await response.json()) as ExampleJob;
}

export async function submitExampleJob(
  label: string,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<ExampleJob> {
  const response = await fetch(`${API_BASE_URL}/api/v1/example-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ label }),
    signal,
  });
  return parseResponse(response);
}

const terminal = (job: ExampleJob) => job.status === "succeeded" || job.status === "failed";

export async function waitForExampleJob(
  jobId: string,
  options: { signal?: AbortSignal; deadlineMs?: number; intervalMs?: number } = {},
): Promise<ExampleJob> {
  const deadline = Date.now() + (options.deadlineMs ?? 30_000);
  const interval = options.intervalMs ?? 1_000;
  while (Date.now() < deadline) {
    const response = await fetch(`${API_BASE_URL}/api/v1/example-jobs/${jobId}`, {
      signal: options.signal,
    });
    const job = await parseResponse(response);
    if (terminal(job)) return job;
    await new Promise<void>((resolve, reject) => {
      const timeout = window.setTimeout(resolve, interval);
      options.signal?.addEventListener("abort", () => {
        window.clearTimeout(timeout);
        reject(new DOMException("Polling aborted", "AbortError"));
      }, { once: true });
    });
  }
  throw new Error("Job polling deadline exceeded");
}
