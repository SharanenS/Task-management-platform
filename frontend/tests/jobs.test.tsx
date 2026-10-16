import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { JobDetail } from "@/features/jobs/job-detail";
import { JobDirectory } from "@/features/jobs/job-directory";
import { SubmitJobForm } from "@/features/jobs/submit-job-form";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  push.mockReset();
});

describe("job management", () => {
  it("renders loading, success, filters, and pagination", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          jobs: {
            nodes: [
              {
                id: "job-1",
                jobType: "PROJECT_TASK_EXPORT",
                status: "SUBMITTED",
                submitterEmployeeId: "employee-1",
                payload: {
                  projectId: "project-1",
                  format: "CSV",
                  includeCompleted: true,
                },
                version: 1,
                createdAt: "2026-10-16T00:00:00Z",
                updatedAt: "2026-10-16T00:00:00Z",
              },
            ],
            pageInfo: { hasNextPage: true, endCursor: "next" },
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetch);
    render(<JobDirectory />);
    expect(screen.getByLabelText("Loading jobs")).toBeInTheDocument();
    expect(await screen.findByText("Project task export")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Job status"), {
      target: { value: "SUBMITTED" },
    });
    fireEvent.change(screen.getByLabelText("Job type"), {
      target: { value: "PROJECT_TASK_EXPORT" },
    });
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
  });

  it("renders empty and retryable error states", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error("internal.example"))
      .mockResolvedValue({
        ok: true,
        json: async () => ({
          data: {
            jobs: {
              nodes: [],
              pageInfo: { hasNextPage: false, endCursor: null },
            },
          },
        }),
      });
    vi.stubGlobal("fetch", fetch);
    render(<JobDirectory />);
    expect(await screen.findByText("Unable to load jobs")).toBeInTheDocument();
    expect(screen.queryByText("internal.example")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No jobs found")).toBeInTheDocument();
  });

  it("validates, prevents duplicate submission, and reuses the key after failure", async () => {
    vi.spyOn(crypto, "randomUUID").mockReturnValue(
      "11111111-1111-4111-8111-111111111111",
    );
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          errors: [{ message: "Temporarily unavailable" }],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: {
            submitProjectTaskExport: { id: "job-1", status: "SUBMITTED" },
          },
        }),
      });
    vi.stubGlobal("fetch", fetch);
    render(<SubmitJobForm />);
    fireEvent.change(screen.getByLabelText("Project UUID"), {
      target: { value: "invalid" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit job" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "valid project UUID",
    );
    fireEvent.change(screen.getByLabelText("Project UUID"), {
      target: { value: "22222222-2222-4222-8222-222222222222" },
    });
    const button = screen.getByRole("button", { name: "Submit job" });
    fireEvent.click(button);
    fireEvent.click(button);
    await screen.findByText("Temporarily unavailable");
    expect(fetch).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Submit job" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/jobs/job-1"));
    const first = JSON.parse(String(fetch.mock.calls[0]?.[1]?.body));
    const second = JSON.parse(String(fetch.mock.calls[1]?.[1]?.body));
    expect(first.variables.input.idempotencyKey).toBe(
      second.variables.input.idempotencyKey,
    );
  });

  it("renders typed payload and truthful empty attempt history", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          data: {
            job: {
              id: "job-1",
              jobType: "PROJECT_TASK_EXPORT",
              status: "SUBMITTED",
              submitterEmployeeId: "employee-1",
              payload: {
                projectId: "project-1",
                format: "CSV",
                includeCompleted: false,
              },
              version: 1,
              createdAt: "2026-10-16T00:00:00Z",
              updatedAt: "2026-10-16T00:00:00Z",
              attempts: [],
            },
          },
        }),
      }),
    );
    render(<JobDetail id="job-1" />);
    expect(await screen.findByText("Project task export")).toBeInTheDocument();
    expect(
      screen.getByText(
        "No execution attempts yet. Worker execution is introduced in Phase 7.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Dispatch, retry, cancellation/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/queued|running|succeeded/i),
    ).not.toBeInTheDocument();
  });
});
