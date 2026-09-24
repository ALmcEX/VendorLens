"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { ApiError, submitExampleJob, waitForExampleJob } from "@/lib/api";
import type { ExampleJob } from "@/lib/types";

type Phase = "idle" | "submitting" | "processing" | "succeeded" | "failed";

const friendlyError = (error: unknown): string => {
  if (error instanceof ApiError && (error.status === 429 || error.status === 503)) {
    return "The service is busy right now. Try again later.";
  }
  if (error instanceof ApiError && error.status === 409) {
    return "That request key was already used for different input. Try again.";
  }
  if (error instanceof Error && error.message.includes("deadline")) {
    return "The job is still taking longer than expected. Try again later.";
  }
  return "The example could not be completed. Try again later.";
};

export function JobDemo() {
  const [label, setLabel] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [job, setJob] = useState<ExampleJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const busy = phase === "submitting" || phase === "processing";

  useEffect(() => () => activeRequest.current?.abort(), []);

  async function runExample(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!label.trim() || busy) return;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setError(null);
    setJob(null);
    setPhase("submitting");
    try {
      const created = await submitExampleJob(
        label.trim(), globalThis.crypto.randomUUID(), controller.signal,
      );
      setJob(created);
      setPhase("processing");
      const completed = created.status === "succeeded" || created.status === "failed"
        ? created
        : await waitForExampleJob(created.id, { signal: controller.signal });
      setJob(completed);
      if (completed.status === "succeeded") {
        setPhase("succeeded");
      } else {
        setPhase("failed");
        setError("The worker could not complete this example. Try again later.");
      }
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setPhase("failed");
      setError(friendlyError(caught));
    }
  }

  return (
    <section className="demo-panel" aria-labelledby="demo-title">
      <div className="section-kicker">Live foundation check</div>
      <h2 id="demo-title">Send one safe job through the stack</h2>
      <p className="section-copy">
        This test stores a label, publishes a durable queue message, runs a deterministic worker,
        and returns the uppercase result. No vendor data or AI model is involved.
      </p>
      <form onSubmit={runExample} className="job-form">
        <label htmlFor="example-label">Example label</label>
        <div className="input-row">
          <input id="example-label" value={label}
            onChange={(event) => setLabel(event.target.value)} maxLength={100}
            placeholder="VendorLens" autoComplete="off" required disabled={busy} />
          <button type="submit" disabled={busy || !label.trim()}>
            {busy ? "Running…" : "Run example job"}
          </button>
        </div>
      </form>
      {busy && (
        <div className="job-state" role="status" aria-live="polite">
          <span className="pulse" aria-hidden="true" />
          {phase === "submitting" ? "Submitting the job…" : "Waiting for the worker…"}
        </div>
      )}
      {phase === "succeeded" && job?.result && (
        <div className="result-card" aria-live="polite">
          <span>Completed result</span><strong>{job.result}</strong>
          <small>Attempt {job.attempt_count}</small>
        </div>
      )}
      {error && (
        <div className="error-card" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => void runExample()}>Try again</button>
        </div>
      )}
    </section>
  );
}
