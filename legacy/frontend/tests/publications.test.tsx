import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PublicationDirectory } from "@/features/jobs/publication-directory";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("publication diagnostics", () => {
  it("renders loading, typed states, filtering, and pagination without sensitive fields", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          jobPublications: {
            nodes: [
              {
                id: "event-1",
                status: "FAILED",
                attemptCount: 2,
                nextRetryAt: "2026-10-20T00:00:05Z",
                leaseExpiresAt: null,
                publishedAt: null,
                lastFailureClassification: "CONNECTION_FAILED",
                reconciliationRequired: false,
              },
            ],
            pageInfo: { hasNextPage: true, endCursor: "opaque-next" },
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetch);
    render(<PublicationDirectory />);
    expect(await screen.findByText("Retry scheduled")).toBeInTheDocument();
    expect(screen.getByText("CONNECTION_FAILED")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/lease token|amqp:\/\//i);
    fireEvent.change(screen.getByLabelText("Status"), {
      target: { value: "PUBLISHED" },
    });
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
  });

  it("renders empty and retryable sanitized errors", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error("amqp://secret@internal"))
      .mockResolvedValue({
        ok: true,
        json: async () => ({
          data: {
            jobPublications: {
              nodes: [],
              pageInfo: { hasNextPage: false, endCursor: null },
            },
          },
        }),
      });
    vi.stubGlobal("fetch", fetch);
    render(<PublicationDirectory />);
    expect(
      await screen.findByText("Unable to load publications"),
    ).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("amqp://secret@internal");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByText(/No publication events/),
    ).toBeInTheDocument();
  });
});
