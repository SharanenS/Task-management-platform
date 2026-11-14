import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EmployeeDirectory } from "@/features/employees/employee-directory";
import { EmployeeDetail } from "@/features/employees/employee-detail";
import { ProvisionEmployeeForm } from "@/features/employees/provision-employee-form";

afterEach(() => vi.unstubAllGlobals());

describe("employee administration", () => {
  it("renders directory data and filters with bounded pagination", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          employees: {
            nodes: [
              {
                id: "employee-1",
                username: "avery.morgan",
                displayName: "Avery Morgan",
                email: "avery@example.test",
                role: "MANAGER",
                active: true,
                provisioningStatus: "COMPLETE",
                updatedAt: "2026-10-14T00:00:00Z",
              },
            ],
            pageInfo: { hasNextPage: false, endCursor: null },
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetch);
    render(<EmployeeDirectory />);
    expect(await screen.findByText("Avery Morgan")).toBeInTheDocument();
    expect(screen.getByText("avery@example.test")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText("Name, username, or email"), {
      target: { value: "avery" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    const request = JSON.parse(fetch.mock.calls[1][1].body);
    expect(request.variables.search).toBe("avery");
    expect(request.variables.first).toBe(12);
  });

  it("shows the directory retry state", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValue({
        ok: true,
        json: async () => ({
          data: {
            employees: {
              nodes: [],
              pageInfo: { hasNextPage: false, endCursor: null },
            },
          },
        }),
      });
    vi.stubGlobal("fetch", fetch);
    render(<EmployeeDirectory />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to load employees",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No employees found")).toBeInTheDocument();
  });

  it("applies role and status filters and follows the cursor", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          employees: {
            nodes: [
              {
                id: "employee-1",
                username: "user",
                displayName: "User",
                email: "user@example.test",
                role: "MEMBER",
                active: false,
                provisioningStatus: "COMPLETE",
                updatedAt: "2026-10-14T00:00:00Z",
              },
            ],
            pageInfo: { hasNextPage: true, endCursor: "next-cursor" },
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetch);
    render(<EmployeeDirectory />);
    await screen.findByText("User");
    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "MEMBER" },
    });
    fireEvent.change(screen.getByLabelText("Access status"), {
      target: { value: "false" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    let body = JSON.parse(fetch.mock.calls[1][1].body);
    expect(body.variables).toMatchObject({
      role: "MEMBER",
      active: false,
      first: 12,
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
    body = JSON.parse(fetch.mock.calls[2][1].body);
    expect(body.variables.after).toBe("next-cursor");
  });

  it("validates and submits provisioning without returning a credential", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          provisionEmployee: {
            id: "employee-2",
            username: "new.user",
            displayName: "New User",
            email: "new.user@example.test",
            role: "MEMBER",
            active: true,
            provisioningStatus: "COMPLETE",
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetch);
    render(<ProvisionEmployeeForm />);
    const form = screen
      .getByRole("button", { name: "Provision employee" })
      .closest("form")!;
    expect(form.checkValidity()).toBe(false);
    fireEvent.change(screen.getByLabelText(/^Username/), {
      target: { value: "new.user" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new.user@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "New User" },
    });
    fireEvent.change(screen.getByLabelText(/^Temporary password/), {
      target: { value: "temporary-password" },
    });
    expect(screen.getByLabelText(/^Temporary password/)).toHaveAttribute(
      "type",
      "password",
    );
    fireEvent.submit(form);
    expect(await screen.findByText("Employee provisioned")).toBeInTheDocument();
    const request = JSON.parse(fetch.mock.calls[0][1].body);
    expect(request.variables.input.temporaryPassword).toBe(
      "temporary-password",
    );
    expect(JSON.stringify(request)).not.toContain("client_secret");
  });

  it("prevents duplicate provisioning submissions while pending", async () => {
    let resolve!: (value: object) => void;
    const fetch = vi.fn(() => new Promise((done) => (resolve = done)));
    vi.stubGlobal("fetch", fetch);
    render(<ProvisionEmployeeForm />);
    fireEvent.change(screen.getByLabelText(/^Username/), {
      target: { value: "new.user" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "New User" },
    });
    fireEvent.change(screen.getByLabelText(/^Temporary password/), {
      target: { value: "temporary-password" },
    });
    const button = screen.getByRole("button", { name: "Provision employee" });
    fireEvent.click(button);
    expect(
      await screen.findByRole("button", { name: /Provisioning/ }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /Provisioning/ }));
    expect(fetch).toHaveBeenCalledTimes(1);
    resolve({
      ok: true,
      json: async () => ({ data: { provisionEmployee: { id: "employee-2" } } }),
    });
  });

  it("loads detail, cancels safely, and confirms a status change", async () => {
    const employee = {
      id: "employee-1",
      username: "user",
      displayName: "User",
      email: "user@example.test",
      role: "MEMBER",
      active: true,
      provisioningStatus: "COMPLETE",
      createdAt: "2026-10-14T00:00:00Z",
      updatedAt: "2026-10-14T00:00:00Z",
      version: 1,
    };
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: { employee } }),
    });
    vi.stubGlobal("fetch", fetch);
    render(<EmployeeDetail id="employee-1" />);
    await screen.findByText("user@example.test");
    fireEvent.click(
      screen.getByRole("button", { name: "Deactivate employee" }),
    );
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
    fireEvent.click(
      screen.getByRole("button", { name: "Deactivate employee" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
  });
});
