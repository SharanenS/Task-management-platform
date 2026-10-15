import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CreateTaskForm } from "@/features/tasks/create-task-form";
import { TaskDetail } from "@/features/tasks/task-detail";
import { TaskDirectory } from "@/features/tasks/task-directory";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
afterEach(() => vi.unstubAllGlobals());

describe("task management", () => {
  it("renders task list, filters, and bounded board lanes", async () => {
    const fetch = vi.fn().mockImplementation(async (_url, init) => {
      const body = JSON.parse(String(init.body));
      return {
        ok: true,
        json: async () =>
          body.query.includes("ProjectTaskBoard")
            ? {
                data: {
                  projectTaskBoard: {
                    lanes: [
                      {
                        status: "TODO",
                        hasMore: true,
                        tasks: [
                          {
                            id: "task-1",
                            reference: "OPS-1",
                            title: "Review",
                            status: "TODO",
                            priority: "HIGH",
                            assigneeDisplayName: null,
                            version: 1,
                          },
                        ],
                      },
                    ],
                  },
                },
              }
            : {
                data: {
                  projectTasks: {
                    nodes: [
                      {
                        id: "task-1",
                        projectId: "project-1",
                        reference: "OPS-1",
                        number: 1,
                        title: "Review",
                        description: null,
                        status: "TODO",
                        priority: "HIGH",
                        assigneeEmployeeId: null,
                        assigneeDisplayName: null,
                        dueDate: null,
                        version: 1,
                        updatedAt: "2026-10-15T00:00:00Z",
                      },
                    ],
                    pageInfo: { hasNextPage: false, endCursor: null },
                  },
                },
              },
      };
    });
    vi.stubGlobal("fetch", fetch);
    render(<TaskDirectory projectId="project-1" />);
    expect(await screen.findByText("Review")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Status"), {
      target: { value: "TODO" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "Board view" }));
    expect(await screen.findByText(/Additional tasks/)).toBeInTheDocument();
  });

  it("prevents duplicate create submission and navigates", async () => {
    let resolve!: (value: object) => void;
    const fetch = vi.fn((url?: unknown, init?: RequestInit) => {
      void url;
      void init;
      return new Promise((done) => (resolve = done));
    });
    vi.stubGlobal("fetch", fetch);
    render(<CreateTaskForm projectId="project-1" />);
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Review" },
    });
    fireEvent.change(screen.getByLabelText("Due date"), {
      target: { value: "2026-12-01" },
    });
    const button = screen.getByRole("button", { name: "Create task" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(fetch).toHaveBeenCalledOnce();
    const request = JSON.parse(String(fetch.mock.calls[0]?.[1]?.body));
    expect(request.variables.input.dueDate).toBe("2026-12-01");
    resolve({
      ok: true,
      json: async () => ({
        data: {
          createTask: {
            id: "task-1",
            reference: "OPS-1",
            title: "Review",
            status: "TODO",
            priority: "MEDIUM",
            version: 1,
          },
        },
      }),
    });
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/projects/project-1/tasks/task-1"),
    );
  });

  it("shows contributor controls only for an assigned writable task", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          data: {
            task: {
              id: "task-1",
              projectId: "project-1",
              reference: "OPS-1",
              number: 1,
              title: "Review",
              description: null,
              status: "TODO",
              priority: "MEDIUM",
              assigneeEmployeeId: "employee-1",
              assigneeDisplayName: "Contributor",
              creatorEmployeeId: "manager",
              dueDate: null,
              version: 1,
              createdAt: "2026-10-15T00:00:00Z",
              updatedAt: "2026-10-15T00:00:00Z",
            },
            project: {
              id: "project-1",
              key: "OPS",
              name: "Operations",
              status: "ACTIVE",
              memberships: [
                {
                  employeeId: "employee-1",
                  role: "CONTRIBUTOR",
                  displayName: "Contributor",
                  email: "contributor@example.test",
                },
              ],
            },
            taskComments: {
              nodes: [],
              pageInfo: { hasNextPage: false, endCursor: null },
            },
            taskActivity: {
              nodes: [],
              pageInfo: { hasNextPage: false, endCursor: null },
            },
          },
        }),
      }),
    );
    render(
      <TaskDetail
        projectId="project-1"
        taskId="task-1"
        employeeId="employee-1"
        applicationRole="MEMBER"
      />,
    );
    expect(
      await screen.findByRole("heading", { name: "Review" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "IN_PROGRESS" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save task" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Task assignee")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Add comment")).toBeInTheDocument();
  });

  it("renders HTML-like comment content as inert plain text", async () => {
    const body =
      "<script>window.__unsafe = true</script><strong>example</strong>";
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          task: {
            id: "task-1",
            projectId: "project-1",
            reference: "OPS-1",
            number: 1,
            title: "Review",
            description: null,
            status: "TODO",
            priority: "MEDIUM",
            assigneeEmployeeId: null,
            assigneeDisplayName: null,
            creatorEmployeeId: "manager",
            dueDate: "2026-12-01",
            version: 1,
            createdAt: "2026-10-15T00:00:00Z",
            updatedAt: "2026-10-15T00:00:00Z",
          },
          project: {
            id: "project-1",
            key: "OPS",
            name: "Operations",
            status: "ACTIVE",
            memberships: [],
          },
          taskComments: {
            nodes: [
              {
                id: "comment-1",
                body,
                authorEmployeeId: "manager",
                authorDisplayName: "Manager",
                createdAt: "2026-10-15T00:00:00Z",
              },
            ],
            pageInfo: { hasNextPage: false, endCursor: null },
          },
          taskActivity: {
            nodes: [],
            pageInfo: { hasNextPage: false, endCursor: null },
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetch);
    const { container } = render(
      <TaskDetail
        projectId="project-1"
        taskId="task-1"
        employeeId="manager"
        applicationRole="MANAGER"
      />,
    );
    expect(await screen.findByText(body)).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("strong")).toBeNull();
    expect(
      (window as Window & { __unsafe?: boolean }).__unsafe,
    ).toBeUndefined();
    expect(container.innerHTML).not.toContain("dangerouslySetInnerHTML");
  });
});
