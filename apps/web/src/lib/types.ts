export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface ExampleJob {
  id: string;
  idempotency_key: string;
  payload_hash: string;
  status: JobStatus;
  attempt_count: number;
  result: string | null;
  error_category: string | null;
}

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  request_id: string;
}
