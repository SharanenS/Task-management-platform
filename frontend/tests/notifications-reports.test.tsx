import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NotificationCenter } from "@/features/notifications/notification-center";
import { ReportCenter } from "@/features/reports/report-center";
import { ReportDetail } from "@/features/reports/report-detail";

afterEach(() => vi.unstubAllGlobals());

function response(data: object) {
  return Promise.resolve({ ok: true, json: async () => ({ data }) });
}

describe("notifications and reports", () => {
  it("renders private notifications and marks one read", async () => {
    const fetch = vi.fn().mockImplementation((_url, options) => {
      const body = JSON.parse(String(options.body));
      if (body.operationName === "MarkNotificationRead") {
        return response({
          markNotificationRead: {
            id: "note-1",
            readAt: "2026-10-29T01:00:00Z",
          },
        });
      }
      return response({
        notifications: {
          nodes: [
            {
              id: "note-1",
              notificationType: "TASK_ASSIGNED",
              title: "Task assigned",
              message: `Safe${"Placeholder".repeat(30)}`,
              projectId: "project-1",
              taskId: "task-1",
              reportId: null,
              readAt: null,
              createdAt: "2026-10-29T00:00:00Z",
            },
          ],
          pageInfo: { hasNextPage: false, endCursor: null },
        },
        unreadNotificationCount: 1,
      });
    });
    vi.stubGlobal("fetch", fetch);
    render(<NotificationCenter />);
    expect(await screen.findByText("Task assigned")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute(
      "href",
      "/projects/project-1/tasks/task-1",
    );
    const heading = screen.getByRole("heading", { name: "Task assigned" });
    const content = heading.parentElement?.parentElement;
    const cardLayout = content?.parentElement;
    const pageHeader = screen.getByRole("heading", {
      name: "Notification center",
    }).parentElement?.parentElement;
    expect(pageHeader).toHaveClass("flex-col", "sm:flex-row");
    expect(content).toHaveClass("min-w-0");
    expect(cardLayout).toHaveClass("flex-col", "sm:flex-row");
    expect(screen.getByText(/^SafePlaceholder/)).toHaveClass(
      "break-words",
      "[overflow-wrap:anywhere]",
    );
    expect(
      screen.getByRole("link", { name: "Open" }).parentElement,
    ).toHaveClass("flex-wrap", "sm:shrink-0");
    expect(screen.getByRole("button", { name: "Mark all read" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Mark read" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
  });

  it("renders sanitized notification errors and empty state", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error("http://notification:8060 secret"))
      .mockImplementation(() =>
        response({
          notifications: {
            nodes: [],
            pageInfo: { hasNextPage: false, endCursor: null },
          },
          unreadNotificationCount: 0,
        }),
      );
    vi.stubGlobal("fetch", fetch);
    render(<NotificationCenter />);
    expect(
      await screen.findByText("Unable to load notifications"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/notification:8060/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No notifications")).toBeInTheDocument();
  });

  it("requests a report from an authorized project selection", async () => {
    const fetch = vi.fn().mockImplementation((_url, options) => {
      const operation = JSON.parse(String(options.body)).operationName;
      if (operation === "ProjectDirectory")
        return response({
          projects: {
            nodes: [
              {
                id: "22222222-2222-4222-8222-222222222222",
                key: "SAFE",
                name: "Safe",
                description: null,
                status: "ACTIVE",
                version: 1,
                updatedAt: "2026-10-29T00:00:00Z",
                memberships: [],
              },
            ],
            pageInfo: { hasNextPage: false, endCursor: null },
          },
        });
      if (operation === "RequestProjectTaskReport")
        return response({
          requestProjectTaskReport: {
            id: "job-1",
            status: "QUEUED",
            version: 2,
          },
        });
      return response({
        reports: {
          nodes: [],
          pageInfo: { hasNextPage: false, endCursor: null },
        },
      });
    });
    vi.stubGlobal("fetch", fetch);
    render(<ReportCenter />);
    expect(await screen.findByText("No reports")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Request report" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(5));
  });

  it("downloads only a completed persisted CSV artifact", async () => {
    const createObjectURL = vi.fn(() => "blob:safe");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      value: createObjectURL,
      configurable: true,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      value: revokeObjectURL,
      configurable: true,
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => undefined,
    );
    const fetch = vi.fn().mockImplementation((_url, options) => {
      const operation = JSON.parse(String(options.body)).operationName;
      if (operation === "ReportArtifact")
        return response({
          reportArtifact: {
            reportId: "job-1",
            filename: "project-tasks-job-1.csv",
            contentType: "text/csv; charset=utf-8",
            checksum: "abc",
            rowCount: 1,
            truncated: false,
            content: "reference,title\nSAFE-1,Task",
          },
        });
      return response({
        report: {
          id: "job-1",
          status: "SUCCEEDED",
          payload: {
            projectId: "project-1",
            format: "CSV",
            includeCompleted: true,
          },
          failureClassification: null,
          completedAt: "2026-10-29T00:01:00Z",
          resultChecksum: "abc",
          resultRowCount: 1,
          resultTruncated: false,
          resultContentType: "text/csv; charset=utf-8",
          createdAt: "2026-10-29T00:00:00Z",
        },
      });
    });
    vi.stubGlobal("fetch", fetch);
    render(<ReportDetail id="job-1" />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Download CSV" }),
    );
    await waitFor(() => expect(createObjectURL).toHaveBeenCalled());
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:safe");
  });
});
