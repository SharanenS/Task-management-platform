import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EmployeeProfile } from "@/auth/types";
import { PortalOverview } from "@/features/portals/portal-overview";
import type { DashboardQuery } from "@/graphql/generated/graphql";

const memberEmployee: EmployeeProfile = {
  id: "member-1",
  displayName: "Jordan Lee",
  email: "jordan@example.test",
  role: "MEMBER",
};

const managerEmployee: EmployeeProfile = {
  id: "manager-1",
  displayName: "Morgan Taylor",
  email: "morgan@example.test",
  role: "MANAGER",
};

const adminEmployee: EmployeeProfile = {
  id: "admin-1",
  displayName: "Alex Rivera",
  email: "alex@example.test",
  role: "ADMIN",
};

function createMockDashboardData(
  overrides?: Partial<DashboardQuery["dashboard"]>,
): DashboardQuery["dashboard"] {
  return {
    workAvailable: true,
    jobAvailable: true,
    projectMetrics: {
      totalCount: 5,
      activeCount: 3,
      draftCount: 1,
      archivedCount: 1,
      managedTotalCount: null,
      managedActiveCount: null,
      managedDraftCount: null,
      managedArchivedCount: null,
    },
    taskMetrics: null,
    assignedTaskMetrics: {
      totalCount: 4,
      todoCount: 1,
      inProgressCount: 2,
      blockedCount: 0,
      doneCount: 1,
      cancelledCount: 0,
      overdueCount: 1,
    },
    recentProjects: [
      {
        id: "proj-1",
        key: "OPS",
        name: "Platform Operations",
        description: "Core infrastructure",
        status: "ACTIVE",
        updatedAt: "2026-11-01T12:00:00Z",
      },
    ],
    recentAssignedTasks: [
      {
        id: "task-1",
        projectId: "proj-1",
        projectKey: "OPS",
        number: 101,
        title: "Review access boundaries",
        status: "IN_PROGRESS",
        priority: "HIGH",
        dueDate: "2026-11-15",
        createdAt: "2026-10-25T10:00:00Z",
        updatedAt: "2026-10-26T14:00:00Z",
      },
    ],
    jobMetrics: {
      totalCount: 3,
      submittedCount: 0,
      queuedCount: 0,
      runningCount: 1,
      succeededCount: 2,
      failedCount: 0,
      cancelledCount: 0,
    },
    recentJobs: [
      {
        id: "job-1",
        jobType: "PROJECT_TASK_EXPORT",
        status: "SUCCEEDED",
        resultSummary: "Exported 42 tasks to CSV",
        completedAt: "2026-10-28T09:00:00Z",
        createdAt: "2026-10-28T08:59:00Z",
      },
    ],
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Role portal overview", () => {
  it.each([
    [memberEmployee, "Make room for your best work."],
    [managerEmployee, "Keep delivery moving."],
    [adminEmployee, "Your organisation, in focus."],
  ])("shows a live role overview for %s", async (employee, title) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { dashboard: createMockDashboardData() },
        }),
        { status: 200 },
      ),
    );
    render(<PortalOverview employee={employee} />);
    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    expect(await screen.findByText("Platform Operations")).toBeInTheDocument();
    expect(screen.queryByText(/Sample data/i)).not.toBeInTheDocument();
    if (employee.role === "MEMBER")
      expect(screen.getByText("Review access boundaries")).toBeInTheDocument();
    else
      expect(
        screen.queryByText("Review access boundaries"),
      ).not.toBeInTheDocument();
  });

  it("fails safely and supports retry", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockRejectedValueOnce(new Error("Unavailable"))
      .mockResolvedValue(
        new Response(
          JSON.stringify({ data: { dashboard: createMockDashboardData() } }),
        ),
      );
    render(<PortalOverview employee={memberEmployee} />);
    expect(await screen.findByText("Overview unavailable")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Platform Operations")).toBeInTheDocument();
  });

  it("does not turn unavailable metrics into zero", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            dashboard: createMockDashboardData({
              workAvailable: false,
              jobAvailable: false,
              projectMetrics: null,
              taskMetrics: null,
              assignedTaskMetrics: null,
              jobMetrics: null,
            }),
          },
        }),
      ),
    );
    render(<PortalOverview employee={memberEmployee} />);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Some services are temporarily unavailable",
    );
    expect(screen.getAllByText("—")).toHaveLength(4);
    expect(screen.queryByText("Platform Operations")).not.toBeInTheDocument();
  });
});
