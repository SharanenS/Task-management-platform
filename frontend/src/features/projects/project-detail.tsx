"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import type { ApplicationRole } from "@/auth/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/states";
import {
  AddProjectMemberDocument,
  EligibleProjectMembersDocument,
  ProjectDetailDocument,
  RemoveProjectMemberDocument,
  SetProjectStatusDocument,
  UpdateProjectDocument,
  UpdateProjectMemberRoleDocument,
  type EligibleProjectMembersQuery,
  type ProjectDetailQuery,
  type ProjectRole,
  type ProjectStatus,
} from "@/graphql/generated/graphql";
import { GraphQLRequestError, requestGraphQL } from "@/lib/graphql";

type Detail = ProjectDetailQuery["project"];
type Eligible =
  EligibleProjectMembersQuery["eligibleProjectMembers"]["nodes"][number];
export function ProjectDetail({
  id,
  employeeId,
  applicationRole,
}: {
  id: string;
  employeeId: string;
  applicationRole: ApplicationRole;
}) {
  const [project, setProject] = useState<Detail | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [eligible, setEligible] = useState<Eligible[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState("");
  const load = useCallback(async () => {
    setState("loading");
    try {
      setProject((await requestGraphQL(ProjectDetailDocument, { id })).project);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [id]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);
  if (state === "loading")
    return (
      <Card className="space-y-4 p-6" aria-label="Loading project">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40" />
      </Card>
    );
  if (state === "error" || !project)
    return (
      <ErrorState
        title="Unable to load project"
        description="The project is unavailable or access is not permitted."
        onRetry={() => void load()}
      />
    );
  const membership = project.memberships.find(
    (item) => item.employeeId === employeeId,
  );
  const canManage =
    applicationRole === "ADMIN" || membership?.role === "PROJECT_MANAGER";
  async function mutate(action: () => Promise<unknown>) {
    setMessage(null);
    try {
      await action();
      await load();
    } catch (error) {
      setMessage(
        error instanceof GraphQLRequestError
          ? error.message
          : "The project could not be updated.",
      );
    }
  }
  const nextStatus: ProjectStatus | null =
    project.status === "DRAFT"
      ? "ACTIVE"
      : project.status === "ACTIVE"
        ? "ARCHIVED"
        : "ACTIVE";
  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/projects"
          className="text-xs font-medium text-primary hover:underline"
        >
          ← Project directory
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Badge>{project.key}</Badge>
          <h1 className="text-3xl font-semibold tracking-tight">
            {project.name}
          </h1>
          <Badge tone={project.status === "ACTIVE" ? "success" : "neutral"}>
            {project.status}
          </Badge>
        </div>
        <p className="mt-3 text-sm text-muted-foreground">
          {project.description || "No description"}
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_.7fr]">
        <Card className="p-6">
          <h2 className="font-semibold">Project members</h2>
          <div className="mt-4 divide-y">
            {project.memberships.map((member) => (
              <div
                key={member.id}
                className="flex items-center justify-between gap-4 py-3"
              >
                <span className="min-w-0 text-sm">
                  <span className="block truncate font-medium">
                    {member.displayName ?? "Unavailable employee"}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {member.email ?? member.employeeId}
                  </span>
                </span>
                {canManage && project.status !== "ARCHIVED" ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <label>
                      <span className="sr-only">Membership role</span>
                      <select
                        value={member.role}
                        onChange={(event) =>
                          void mutate(() =>
                            requestGraphQL(UpdateProjectMemberRoleDocument, {
                              projectId: id,
                              employeeId: member.employeeId,
                              role: event.target.value as ProjectRole,
                            }),
                          )
                        }
                        className="h-9 rounded-lg border bg-background px-2 text-xs focus:ring-2 focus:ring-ring"
                      >
                        <option value="PROJECT_MANAGER">Project manager</option>
                        <option value="CONTRIBUTOR">Contributor</option>
                      </select>
                    </label>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        if (window.confirm("Remove this project member?"))
                          void mutate(() =>
                            requestGraphQL(RemoveProjectMemberDocument, {
                              projectId: id,
                              employeeId: member.employeeId,
                            }),
                          );
                      }}
                    >
                      Remove
                    </Button>
                  </div>
                ) : (
                  <Badge>{member.role}</Badge>
                )}
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-6">
          <h2 className="font-semibold">Project controls</h2>
          {canManage ? (
            <div className="mt-4 space-y-3">
              <p className="text-sm text-muted-foreground">
                Version {project.version}. Archived projects remain read-only
                until reactivated.
              </p>
              <Button
                variant="outline"
                onClick={async () => {
                  if (!nextStatus) return;
                  setMessage(null);
                  try {
                    await requestGraphQL(SetProjectStatusDocument, {
                      projectId: id,
                      status: nextStatus,
                      expectedVersion: project.version,
                    });
                    await load();
                  } catch (error) {
                    setMessage(
                      error instanceof GraphQLRequestError
                        ? error.message
                        : "The status could not be changed.",
                    );
                  }
                }}
              >
                {project.status === "ARCHIVED"
                  ? "Reactivate project"
                  : project.status === "DRAFT"
                    ? "Activate project"
                    : "Archive project"}
              </Button>
              {project.status !== "ARCHIVED" && (
                <div className="space-y-4 border-t pt-4">
                  <form
                    key={project.version}
                    className="space-y-3"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const data = new FormData(event.currentTarget);
                      void mutate(() =>
                        requestGraphQL(UpdateProjectDocument, {
                          projectId: id,
                          input: {
                            name: String(data.get("name")),
                            description:
                              String(data.get("description")) || null,
                            expectedVersion: project.version,
                          },
                        }),
                      );
                    }}
                  >
                    <label className="block text-sm font-medium">
                      Project name
                      <input
                        name="name"
                        required
                        maxLength={200}
                        defaultValue={project.name}
                        className="mt-2 h-10 w-full rounded-lg border bg-background px-3 text-sm focus:ring-2 focus:ring-ring"
                      />
                    </label>
                    <label className="block text-sm font-medium">
                      Project description
                      <textarea
                        name="description"
                        rows={3}
                        maxLength={4000}
                        defaultValue={project.description ?? ""}
                        className="mt-2 w-full rounded-lg border bg-background p-3 text-sm focus:ring-2 focus:ring-ring"
                      />
                    </label>
                    <Button type="submit" variant="outline">
                      Save project details
                    </Button>
                  </form>
                  <Button
                    variant="outline"
                    onClick={async () => {
                      try {
                        const result = await requestGraphQL(
                          EligibleProjectMembersDocument,
                          { first: 25, after: null, search: null },
                        );
                        setEligible(
                          result.eligibleProjectMembers.nodes.filter(
                            (item) =>
                              !project.memberships.some(
                                (member) => member.employeeId === item.id,
                              ),
                          ),
                        );
                      } catch (error) {
                        setMessage(
                          error instanceof GraphQLRequestError
                            ? error.message
                            : "Eligible employees could not be loaded.",
                        );
                      }
                    }}
                  >
                    Find eligible employees
                  </Button>
                  {eligible.length > 0 && (
                    <div className="space-y-3">
                      <label className="block text-sm font-medium">
                        Employee
                        <select
                          value={selectedEmployee}
                          onChange={(event) =>
                            setSelectedEmployee(event.target.value)
                          }
                          className="mt-2 h-10 w-full rounded-lg border bg-background px-3 text-sm focus:ring-2 focus:ring-ring"
                        >
                          <option value="">Select employee</option>
                          {eligible.map((employee) => (
                            <option key={employee.id} value={employee.id}>
                              {employee.displayName} ({employee.email})
                            </option>
                          ))}
                        </select>
                      </label>
                      <Button
                        disabled={!selectedEmployee}
                        onClick={() =>
                          void mutate(async () => {
                            await requestGraphQL(AddProjectMemberDocument, {
                              projectId: id,
                              employeeId: selectedEmployee,
                              role: "CONTRIBUTOR",
                            });
                            setSelectedEmployee("");
                            setEligible([]);
                          })
                        }
                      >
                        Add contributor
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">
              Your membership is read-only.
            </p>
          )}
        </Card>
      </div>
      <Card className="flex flex-wrap items-center justify-between gap-4 p-6">
        <div>
          <h2 className="font-semibold">Project tasks</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Open the task list or bounded status board for this project.
          </p>
        </div>
        <Button asChild>
          <Link href={`/projects/${id}/tasks`}>View tasks</Link>
        </Button>
      </Card>
      {message && (
        <p role="alert" className="rounded-lg border p-4 text-sm">
          {message}
        </p>
      )}
    </div>
  );
}
