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
              resultSummary: null,
              resultContent: null,
              resultContentType: null,
              resultChecksum: null,
              resultRowCount: null,
              resultTruncated: null,
              failureClassification: null,
              completedAt: null,
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
    expect(screen.getByText("No execution attempts yet.")).toBeInTheDocument();
    expect(screen.getByText(/direct broker publication/)).toBeInTheDocument();
  });

  it("confirms dispatch, prevents duplicate submission, and refreshes status", async () => {
    const submitted = {
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
      resultSummary: null,
      resultContent: null,
      resultContentType: null,
      resultChecksum: null,
      resultRowCount: null,
      resultTruncated: null,
      failureClassification: null,
      completedAt: null,
      createdAt: "2026-10-16T00:00:00Z",
      updatedAt: "2026-10-16T00:00:00Z",
      attempts: [],
    };
    let resolveDispatch: ((value: object) => void) | undefined;
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { job: submitted } }),
      })
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveDispatch = resolve;
        }),
      )
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: { job: { ...submitted, status: "QUEUED", version: 2 } },
        }),
      });
    vi.stubGlobal("fetch", fetch);
    render(<JobDetail id="job-1" />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Dispatch job" }),
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dispatch job" }));
    const confirm = screen.getByRole("button", { name: "Confirm dispatch" });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    expect(fetch).toHaveBeenCalledTimes(2);
    resolveDispatch?.({
      ok: true,
      json: async () => ({
        data: { dispatchJob: { id: "job-1", status: "QUEUED", version: 2 } },
      }),
    });
    expect(await screen.findByText("QUEUED")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("renders a terminal CSV result and sanitized failure summary", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          job: {
            id: "job-1",
            jobType: "PROJECT_TASK_EXPORT",
            status: "SUCCEEDED",
            submitterEmployeeId: "employee-1",
            payload: {
              projectId: "project-1",
              format: "CSV",
              includeCompleted: true,
            },
            version: 4,
            resultSummary: "Exported 1 task rows.",
            resultContent: "reference,title\nPRJ-1,Safe\n",
            resultContentType: "text/csv; charset=utf-8",
            resultChecksum: "fixed-checksum",
            resultRowCount: 1,
            resultTruncated: false,
            failureClassification: null,
            completedAt: "2026-10-17T00:00:00Z",
            createdAt: "2026-10-16T00:00:00Z",
            updatedAt: "2026-10-17T00:00:00Z",
            attempts: [
              {
                id: "attempt-1",
                attemptNumber: 1,
                status: "SUCCEEDED",
                startedAt: "2026-10-17T00:00:00Z",
                finishedAt: "2026-10-17T00:00:01Z",
                failureCode: null,
                retryable: false,
                safeSummary: null,
              },
            ],
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetch);
    render(<JobDetail id="job-1" />);
    expect(await screen.findByText("Export result")).toBeInTheDocument();
    expect(screen.getByText(/1 rows/)).toBeInTheDocument();
    expect(screen.getByText(/PRJ-1,Safe/)).toBeInTheDocument();
  });
});
