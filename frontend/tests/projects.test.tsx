import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CreateProjectForm } from "@/features/projects/create-project-form";
import { ProjectDetail } from "@/features/projects/project-detail";
import { ProjectDirectory } from "@/features/projects/project-directory";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
afterEach(() => vi.unstubAllGlobals());

describe("project management", () => {
  it("renders accessible projects and role-aware creation controls", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          projects: {
            nodes: [
              {
                id: "project-1",
                key: "OPS",
                name: "Operations",
                description: null,
                status: "DRAFT",
                version: 1,
                updatedAt: "2026-10-14T00:00:00Z",
                memberships: [],
              },
            ],
            pageInfo: { hasNextPage: false, endCursor: null },
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetch);
    const { unmount } = render(<ProjectDirectory role="MANAGER" />);
    expect(await screen.findByText("Operations")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Create project/ }),
    ).toBeInTheDocument();
    unmount();
    render(<ProjectDirectory role="MEMBER" />);
    await screen.findByText("Operations");
    expect(
      screen.queryByRole("link", { name: /Create project/ }),
    ).not.toBeInTheDocument();
  });

  it("applies project search and status filters", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          projects: {
            nodes: [],
            pageInfo: { hasNextPage: false, endCursor: null },
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetch);
    render(<ProjectDirectory role="ADMIN" />);
    await screen.findByText("No projects found");
    fireEvent.change(screen.getByPlaceholderText("Project key or name"), {
      target: { value: "ops" },
    });
    fireEvent.change(screen.getByLabelText("Project status"), {
      target: { value: "ACTIVE" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(JSON.parse(fetch.mock.calls[1][1].body).variables).toMatchObject({
      search: "ops",
      status: "ACTIVE",
      first: 12,
    });
  });

  it("validates, submits once, and navigates after project creation", async () => {
    let resolve!: (value: object) => void;
    const fetch = vi.fn(() => new Promise((done) => (resolve = done)));
    vi.stubGlobal("fetch", fetch);
    render(<CreateProjectForm />);
    fireEvent.change(screen.getByLabelText("Project key"), {
      target: { value: "ops" },
    });
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Operations" },
    });
    const button = screen.getByRole("button", { name: "Create project" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(fetch).toHaveBeenCalledOnce();
    resolve({
      ok: true,
      json: async () => ({
        data: {
          createProject: {
            id: "project-1",
            key: "OPS",
            name: "Operations",
            status: "DRAFT",
            version: 1,
          },
        },
      }),
    });
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/projects/project-1"),
    );
  });

  it("loads project detail and submits an optimistic metadata update", async () => {
    const project = {
      id: "project-1",
      key: "OPS",
      name: "Operations",
      description: "Initial",
      status: "DRAFT",
      creatorEmployeeId: "employee-1",
      version: 1,
      createdAt: "2026-10-14T00:00:00Z",
      updatedAt: "2026-10-14T00:00:00Z",
      memberships: [
        {
          id: "membership-1",
          employeeId: "employee-1",
          role: "PROJECT_MANAGER",
          createdAt: "2026-10-14T00:00:00Z",
        },
      ],
    };
    const fetch = vi.fn().mockImplementation(async (_url, init) => {
      const body = JSON.parse(String(init.body));
      return {
        ok: true,
        json: async () =>
          body.query.includes("mutation UpdateProject")
            ? {
                data: {
                  updateProject: { ...project, name: "Operations updated" },
                },
              }
            : { data: { project } },
      };
    });
    vi.stubGlobal("fetch", fetch);
    render(
      <ProjectDetail
        id="project-1"
        employeeId="employee-1"
        applicationRole="MANAGER"
      />,
    );
    await screen.findByRole("heading", { name: "Operations" });
    fireEvent.change(screen.getByLabelText("Project name"), {
      target: { value: "Operations updated" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save project details" }),
    );
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
    expect(JSON.parse(fetch.mock.calls[1][1].body).variables.input).toEqual({
      name: "Operations updated",
      description: "Initial",
      expectedVersion: 1,
    });
  });

  it("keeps an assigned member visible when removal is rejected", async () => {
    const project = {
      id: "project-1",
      key: "OPS",
      name: "Operations",
      description: null,
      status: "ACTIVE",
      creatorEmployeeId: "manager-1",
      version: 1,
      createdAt: "2026-10-14T00:00:00Z",
      updatedAt: "2026-10-14T00:00:00Z",
      memberships: [
        {
          id: "membership-1",
          employeeId: "manager-1",
          role: "PROJECT_MANAGER",
          displayName: "Project Manager",
          email: "manager@example.test",
          createdAt: "2026-10-14T00:00:00Z",
        },
        {
          id: "membership-2",
          employeeId: "contributor-1",
          role: "CONTRIBUTOR",
          displayName: "Assigned Contributor",
          email: "contributor@example.test",
          createdAt: "2026-10-14T00:00:00Z",
        },
      ],
    };
    const fetch = vi.fn().mockImplementation(async (_url, init) => {
      const request = JSON.parse(String(init.body));
      return {
        ok: true,
        json: async () =>
          request.operationName === "RemoveProjectMember"
            ? {
                errors: [
                  {
                    message:
                      "Reassign the employee's tasks before removing project membership.",
                    extensions: { code: "MEMBER_HAS_ASSIGNED_TASKS" },
                  },
                ],
              }
            : { data: { project } },
      };
    });
    vi.stubGlobal("fetch", fetch);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(
      <ProjectDetail
        id="project-1"
        employeeId="manager-1"
        applicationRole="MANAGER"
      />,
    );
    await screen.findByText("Assigned Contributor");
    const removeButtons = screen.getAllByRole("button", { name: "Remove" });
    fireEvent.click(removeButtons[1]);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Reassign the employee's tasks before removing project membership.",
    );
    expect(screen.getByText("Assigned Contributor")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(2);
    confirm.mockRestore();
  });
});
