import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkflowDirectory } from "@/features/workflows/workflow-directory";
import { CreateWorkflowForm } from "@/features/workflows/create-workflow-form";
import { WorkflowDetail } from "@/features/workflows/workflow-detail";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
afterEach(() => {
  vi.unstubAllGlobals();
  push.mockReset();
});

describe("workflow automation", () => {
  it("renders loading, directory results, filters, and the bounded contract", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          workflowRules: {
            nodes: [
              {
                id: "rule-1",
                projectId: "project-1",
                name: "Export completed",
                enabled: true,
                triggerType: "TASK_COMPLETED",
                actionType: "PROJECT_TASK_EXPORT",
              },
            ],
            pageInfo: { hasNextPage: false, endCursor: null },
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetch);
    render(<WorkflowDirectory />);
    expect(screen.getByLabelText("Loading workflows")).toBeInTheDocument();
    expect(await screen.findByText("Export completed")).toBeInTheDocument();
    expect(screen.getByText(/Task completed/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Rule state"), {
      target: { value: "false" },
    });
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  });
  it("renders a retryable sanitized error", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error("http://workflow:8050 secret"))
      .mockResolvedValue({
        ok: true,
        json: async () => ({
          data: {
            workflowRules: {
              nodes: [],
              pageInfo: { hasNextPage: false, endCursor: null },
            },
          },
        }),
      });
    vi.stubGlobal("fetch", fetch);
    render(<WorkflowDirectory />);
    expect(
      await screen.findByText("Unable to load workflows"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/workflow:8050/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No workflow rules")).toBeInTheDocument();
  });
  it("validates and submits the fixed trigger and action", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          data: { createWorkflowRule: { id: "rule-1" } },
        }),
      }),
    );
    render(<CreateWorkflowForm />);
    fireEvent.click(screen.getByRole("button", { name: "Create rule" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "valid project UUID",
    );
    fireEvent.change(screen.getByLabelText("Rule name"), {
      target: { value: "Export done" },
    });
    fireEvent.change(screen.getByLabelText("Project UUID"), {
      target: { value: "22222222-2222-4222-8222-222222222222" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create rule" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/workflows/rule-1"));
  });
  it("shows execution history and resulting job linkage", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          data: {
            workflowRule: {
              id: "rule-1",
              name: "Export",
              projectId: "project-1",
              enabled: true,
              version: 1,
            },
            workflowExecutions: {
              nodes: [
                {
                  id: "execution-1",
                  status: "SUCCEEDED",
                  taskId: "task-1",
                  resultingJobId: "job-1",
                  failureClassification: null,
                  createdAt: "2026-10-28T00:00:00Z",
                },
              ],
            },
          },
        }),
      }),
    );
    render(<WorkflowDetail id="rule-1" />);
    expect(await screen.findByText("Execution history")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open resulting job" }),
    ).toHaveAttribute("href", "/jobs/job-1");
    fireEvent.click(screen.getByRole("button", { name: "Disable" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
