import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EmployeeProfile } from "@/auth/types";
import { WorkspaceDashboard } from "@/features/dashboard/workspace-dashboard";
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

describe("WorkspaceDashboard", () => {
  it("renders a loading skeleton state while fetching", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {})),
    );
    render(<WorkspaceDashboard employee={memberEmployee} />);
    expect(
      screen.getByLabelText("Loading workspace dashboard"),
    ).toBeInTheDocument();
  });

  it("renders MEMBER dashboard with personal assigned work, accessible projects, and submitted jobs", async () => {
    const data = createMockDashboardData();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ data: { dashboard: data } }),
      }),
    );

    const { container } = render(
      <WorkspaceDashboard employee={memberEmployee} />,
    );

    expect(
      await screen.findByText("Welcome back, Jordan Lee"),
    ).toBeInTheDocument();
    expect(screen.getByText("MEMBER")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Personal workspace overview: your accessible projects, assigned tasks, and background jobs.",
      ),
    ).toBeInTheDocument();

    // Projects summary
    const accessibleLink = screen.getByRole("link", { name: /Accessible/i });
    expect(within(accessibleLink).getByText("5")).toBeInTheDocument();
    expect(screen.queryByText("Managed")).not.toBeInTheDocument(); // MEMBER does not see managed card
    const activeLink = container.querySelector(
      'a[href="/projects?status=ACTIVE"]',
    )!;
    expect(
      within(activeLink as HTMLElement).getByText("3"),
    ).toBeInTheDocument();

    // Assigned tasks
    expect(screen.getByText("My Assigned Work")).toBeInTheDocument();
    expect(screen.getByText("OPS-101")).toBeInTheDocument();
    expect(screen.getByText("Review access boundaries")).toBeInTheDocument();

    // Jobs section
    expect(screen.getByText("My Background Jobs")).toBeInTheDocument();
    expect(screen.getByText("Total Jobs")).toBeInTheDocument();
    expect(screen.getByText("Exported 42 tasks to CSV")).toBeInTheDocument();

    // Filter link targets
    expect(
      container.querySelector('a[href="/projects?status=ACTIVE"]'),
    ).toBeInTheDocument();
    expect(
      container.querySelector('a[href="/projects?status=DRAFT"]'),
    ).toBeInTheDocument();
    expect(
      container.querySelector('a[href="/jobs?status=SUCCEEDED"]'),
    ).toBeInTheDocument();
  });

  it("renders MANAGER dashboard with managed project health, task breakdown, and personal assigned work", async () => {
    const data = createMockDashboardData({
      projectMetrics: {
        totalCount: 8,
        activeCount: 5,
        draftCount: 2,
        archivedCount: 1,
        managedTotalCount: 3,
        managedActiveCount: 2,
        managedDraftCount: 1,
        managedArchivedCount: 0,
      },
      taskMetrics: {
        totalCount: 24,
        todoCount: 8,
        inProgressCount: 10,
        blockedCount: 2,
        doneCount: 3,
        cancelledCount: 1,
        overdueCount: 4,
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ data: { dashboard: data } }),
      }),
    );

    render(<WorkspaceDashboard employee={managerEmployee} />);

    expect(
      await screen.findByText("Welcome back, Morgan Taylor"),
    ).toBeInTheDocument();
    expect(screen.getByText("MANAGER")).toBeInTheDocument();

    // Managed projects card
    const managedLink = screen.getByRole("link", { name: /Managed/i });
    expect(within(managedLink).getByText("3")).toBeInTheDocument();

    // Managed tasks breakdown
    expect(screen.getByText("Managed Projects Tasks")).toBeInTheDocument();
    expect(screen.getByText("Total Tasks")).toBeInTheDocument();
    expect(screen.getByText("24")).toBeInTheDocument();
    const overdueCard = screen
      .getAllByText("Overdue")[0]
      .closest("div")?.parentElement;
    expect(overdueCard).not.toBeNull();
    expect(
      within(overdueCard as HTMLElement).getByText("4"),
    ).toBeInTheDocument();

    // Personal assigned work
    expect(screen.getByText("My Assigned Work")).toBeInTheDocument();
  });

  it("renders ADMIN dashboard with platform executive summary across projects, tasks, and jobs", async () => {
    const data = createMockDashboardData({
      projectMetrics: {
        totalCount: 30,
        activeCount: 20,
        draftCount: 8,
        archivedCount: 2,
        managedTotalCount: 30,
        managedActiveCount: 20,
        managedDraftCount: 8,
        managedArchivedCount: 2,
      },
      taskMetrics: {
        totalCount: 150,
        todoCount: 50,
        inProgressCount: 60,
        blockedCount: 10,
        doneCount: 25,
        cancelledCount: 5,
        overdueCount: 12,
      },
      jobMetrics: {
        totalCount: 15,
        submittedCount: 2,
        queuedCount: 1,
        runningCount: 3,
        succeededCount: 8,
        failedCount: 1,
        cancelledCount: 0,
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ data: { dashboard: data } }),
      }),
    );

    render(<WorkspaceDashboard employee={adminEmployee} />);

    expect(
      await screen.findByText("Welcome back, Alex Rivera"),
    ).toBeInTheDocument();
    expect(screen.getByText("ADMIN")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Platform-wide executive overview: aggregate metrics across projects, tasks, and background jobs.",
      ),
    ).toBeInTheDocument();

    // Platform task breakdown
    expect(screen.getByText("Platform Tasks Breakdown")).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();

    // Platform background jobs
    expect(screen.getByText("Platform Background Jobs")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();

    // Failed jobs alert link
    const failedLink = screen.getByRole("link", { name: /Failed/i });
    expect(failedLink).toHaveAttribute("href", "/jobs?status=FAILED");
  });

  it("renders genuine empty states with truthful 0 counts when data is genuinely empty", async () => {
    const emptyData = createMockDashboardData({
      projectMetrics: {
        totalCount: 0,
        activeCount: 0,
        draftCount: 0,
        archivedCount: 0,
        managedTotalCount: null,
        managedActiveCount: null,
        managedDraftCount: null,
        managedArchivedCount: null,
      },
      taskMetrics: null,
      assignedTaskMetrics: {
        totalCount: 0,
        todoCount: 0,
        inProgressCount: 0,
        blockedCount: 0,
        doneCount: 0,
        cancelledCount: 0,
        overdueCount: 0,
      },
      recentProjects: [],
      recentAssignedTasks: [],
      jobMetrics: {
        totalCount: 0,
        submittedCount: 0,
        queuedCount: 0,
        runningCount: 0,
        succeededCount: 0,
        failedCount: 0,
        cancelledCount: 0,
      },
      recentJobs: [],
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ data: { dashboard: emptyData } }),
      }),
    );

    render(<WorkspaceDashboard employee={memberEmployee} />);

    expect(
      await screen.findByText("Welcome back, Jordan Lee"),
    ).toBeInTheDocument();

    // Zeros are rendered
    const zeros = screen.getAllByText("0");
    expect(zeros.length).toBeGreaterThan(0);

    // Empty state titles
    expect(screen.getByText("No projects available")).toBeInTheDocument();
    expect(screen.getByText("No assigned tasks")).toBeInTheDocument();
    expect(screen.getByText("No background jobs")).toBeInTheDocument();
  });

  it("handles partial failure gracefully when Work Service is unavailable", async () => {
    const partialData = createMockDashboardData({
      workAvailable: false,
      projectMetrics: null,
      taskMetrics: null,
      assignedTaskMetrics: null,
      recentProjects: null,
      recentAssignedTasks: null,
      jobAvailable: true,
      jobMetrics: {
        totalCount: 4,
        submittedCount: 0,
        queuedCount: 0,
        runningCount: 0,
        succeededCount: 4,
        failedCount: 0,
        cancelledCount: 0,
      },
      recentJobs: [
        {
          id: "job-1",
          jobType: "PROJECT_TASK_EXPORT",
          status: "SUCCEEDED",
          resultSummary: "Exported",
          completedAt: "2026-11-01T00:00:00Z",
          createdAt: "2026-11-01T00:00:00Z",
        },
      ],
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ data: { dashboard: partialData } }),
      }),
    );

    render(<WorkspaceDashboard employee={memberEmployee} />);

    expect(
      await screen.findByText("Work Service Temporarily Unavailable"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Project and task metrics could not be loaded/i),
    ).toBeInTheDocument();

    // Job section is still visible
    expect(screen.getByText("My Background Jobs")).toBeInTheDocument();
    const totalJobsLink = screen.getByRole("link", { name: /Total Jobs/i });
    expect(within(totalJobsLink).getByText("4")).toBeInTheDocument();
  });

  it("handles partial failure gracefully when Job Service is unavailable", async () => {
    const partialData = createMockDashboardData({
      workAvailable: true,
      jobAvailable: false,
      jobMetrics: null,
      recentJobs: null,
      projectMetrics: {
        totalCount: 3,
        activeCount: 2,
        draftCount: 1,
        archivedCount: 0,
        managedTotalCount: null,
        managedActiveCount: null,
        managedDraftCount: null,
        managedArchivedCount: null,
      },
      taskMetrics: null,
      assignedTaskMetrics: {
        totalCount: 2,
        todoCount: 1,
        inProgressCount: 1,
        blockedCount: 0,
        doneCount: 0,
        cancelledCount: 0,
        overdueCount: 0,
      },
      recentProjects: [],
      recentAssignedTasks: [],
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ data: { dashboard: partialData } }),
      }),
    );

    render(<WorkspaceDashboard employee={memberEmployee} />);

    expect(
      await screen.findByText("Job Service Temporarily Unavailable"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Background job summaries and history could not be loaded/i,
      ),
    ).toBeInTheDocument();

    // Projects and tasks are still visible
    expect(screen.getByText("Projects")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("My Assigned Work")).toBeInTheDocument();
  });

  it("handles full failure when both services fail or network error occurs, and allows retry", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("Connection refused"))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { dashboard: createMockDashboardData() } }),
      });

    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspaceDashboard employee={memberEmployee} />);

    expect(
      await screen.findByText("Workspace dashboard unavailable"),
    ).toBeInTheDocument();
    const retryBtn = screen.getByRole("button", { name: "Try again" });
    fireEvent.click(retryBtn);

    expect(
      await screen.findByText("Welcome back, Jordan Lee"),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("provides accessible control names, keyboard reachability, and meaningful focus visibility", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: { dashboard: createMockDashboardData() } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspaceDashboard employee={memberEmployee} />);

    expect(
      await screen.findByText("Welcome back, Jordan Lee"),
    ).toBeInTheDocument();

    // 1. Accessible Control Names & Roles
    const refreshBtn = screen.getByRole("button", { name: "Refresh" });
    expect(refreshBtn).toBeInTheDocument();

    const systemStatusLink = screen.getByRole("link", {
      name: /System status/i,
    });
    expect(systemStatusLink).toHaveAttribute("href", "/system");

    const viewProjectsLink = screen.getByRole("link", {
      name: /View all projects/i,
    });
    expect(viewProjectsLink).toHaveAttribute("href", "/projects");

    const accessibleProjectsCard = screen.getByRole("link", {
      name: /Accessible.*5.*Total visible projects/i,
    });
    expect(accessibleProjectsCard).toHaveAttribute("href", "/projects");

    const taskLink = screen.getByRole("link", {
      name: /OPS-101.*Review access boundaries/i,
    });
    expect(taskLink).toHaveAttribute("href", "/projects/proj-1/tasks");

    // 2. Keyboard Focus & Interaction
    // Focus refresh button
    refreshBtn.focus();
    expect(refreshBtn).toHaveFocus();

    // Trigger refresh action via keyboard
    fireEvent.click(refreshBtn);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(
      await screen.findByText("Welcome back, Jordan Lee"),
    ).toBeInTheDocument();

    // Re-query interactive elements in ready state
    const readyViewProjectsLink = screen.getByRole("link", {
      name: /View all projects/i,
    });
    const readyAccessibleProjectsCard = screen.getByRole("link", {
      name: /Accessible.*5.*Total visible projects/i,
    });
    const readyTaskLink = screen.getByRole("link", {
      name: /OPS-101.*Review access boundaries/i,
    });

    // Focus View All Projects link
    readyViewProjectsLink.focus();
    expect(readyViewProjectsLink).toHaveFocus();

    // Focus Accessible Projects card link
    readyAccessibleProjectsCard.focus();
    expect(readyAccessibleProjectsCard).toHaveFocus();
    expect(readyAccessibleProjectsCard.className).toContain("focus:ring-2");

    // Focus Task link
    readyTaskLink.focus();
    expect(readyTaskLink).toHaveFocus();
    expect(readyTaskLink.className).toContain("focus:underline");
  });
});
