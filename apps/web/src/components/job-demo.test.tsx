import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import Home from "@/app/page";
import { JobDemo } from "@/components/job-demo";

const apiBase = "http://localhost:8000";
const jobId = "00000000-0000-0000-0000-000000000001";
const queuedJob = {
  id: jobId,
  idempotency_key: "test-key",
  payload_hash: "hash",
  status: "queued",
  attempt_count: 0,
  result: null,
  error_category: null,
};

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("VendorLens foundation", () => {
  it("explains that the release is infrastructure scaffolding", () => {
    render(<Home />);

    expect(screen.getByText(/not a vendor-risk decision system/i)).toBeVisible();
    expect(screen.getByRole("link", { name: /vendorlens home/i })).toBeVisible();
  });

  it("submits and displays a completed example job", async () => {
    server.use(
      http.post(`${apiBase}/api/v1/example-jobs`, () =>
        HttpResponse.json(queuedJob, {
          status: 202,
          headers: { Location: `/api/v1/example-jobs/${jobId}` },
        }),
      ),
      http.get(`${apiBase}/api/v1/example-jobs/${jobId}`, () =>
        HttpResponse.json({ ...queuedJob, status: "succeeded", result: "VENDORLENS" }),
      ),
    );
    render(<JobDemo />);

    await userEvent.type(screen.getByLabelText(/example label/i), "VendorLens");
    await userEvent.click(screen.getByRole("button", { name: /run example job/i }));

    expect(await screen.findByText("VENDORLENS")).toBeVisible();
  });

  it("keeps a recoverable error visible", async () => {
    server.use(
      http.post(`${apiBase}/api/v1/example-jobs`, () =>
        HttpResponse.json(
          {
            type: "https://vendorlens.dev/problems/rate-limit-exceeded",
            title: "Request rate exceeded",
            status: 429,
            detail: "Too many submissions.",
            request_id: "request-1",
          },
          { status: 429 },
        ),
      ),
    );
    render(<JobDemo />);

    await userEvent.type(screen.getByLabelText(/example label/i), "VendorLens");
    await userEvent.click(screen.getByRole("button", { name: /run example job/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/try again later/i);
    expect(screen.getByRole("button", { name: /try again/i })).toBeVisible();
  });
});
