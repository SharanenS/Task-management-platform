"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/states";
import {
  AddTaskCommentDocument,
  AssignTaskDocument,
  ChangeTaskStatusDocument,
  TaskDetailDocument,
  UpdateTaskDocument,
  type TaskDetailQuery,
  type TaskPriority,
  type TaskStatus,
} from "@/graphql/generated/graphql";
import { GraphQLRequestError, requestGraphQL } from "@/lib/graphql";

const transitions: Record<TaskStatus, TaskStatus[]> = {
  TODO: ["IN_PROGRESS", "BLOCKED", "CANCELLED"],
  IN_PROGRESS: ["TODO", "BLOCKED", "DONE", "CANCELLED"],
  BLOCKED: ["TODO", "IN_PROGRESS", "CANCELLED"],
  DONE: ["IN_PROGRESS"],
  CANCELLED: ["TODO"],
};

export function TaskDetail({
  projectId,
  taskId,
  employeeId,
  applicationRole,
}: {
  projectId: string;
  taskId: string;
  employeeId: string;
  applicationRole: string;
}) {
  const [data, setData] = useState<TaskDetailQuery | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState<string | null>(null);
  const load = useCallback(async () => {
    setState("loading");
    try {
      setData(await requestGraphQL(TaskDetailDocument, { projectId, taskId }));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [projectId, taskId]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);
  if (state === "loading")
    return (
      <Card aria-label="Loading task" className="space-y-3 p-6">
        <Skeleton className="h-8" />
        <Skeleton className="h-40" />
      </Card>
    );
  if (state === "error" || !data)
    return (
      <ErrorState
        title="Unable to load task"
        description="The task is unavailable or access is not permitted."
        onRetry={() => void load()}
      />
    );
  const { task, project } = data;
  const membership = project.memberships.find(
    (item) => item.employeeId === employeeId,
  );
  const canManage =
    applicationRole === "ADMIN" || membership?.role === "PROJECT_MANAGER";
  const canChangeStatus = canManage || task.assigneeEmployeeId === employeeId;
  const writable = project.status !== "ARCHIVED";
  async function mutate(action: () => Promise<unknown>) {
    setMessage(null);
    try {
      await action();
      await load();
    } catch (error) {
      setMessage(
        error instanceof GraphQLRequestError
          ? error.message
          : "The task could not be updated.",
      );
    }
  }
  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/projects/${projectId}/tasks`}
          className="text-xs font-medium text-primary hover:underline"
        >
          ← Tasks
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Badge>{task.reference}</Badge>
          <h1 className="text-3xl font-semibold">{task.title}</h1>
          <Badge>{task.status}</Badge>
          <Badge>{task.priority}</Badge>
        </div>
        <p className="mt-3 text-sm text-muted-foreground">
          {task.description || "No description"}
        </p>
      </div>
      {!writable && (
        <p role="status" className="rounded-lg border p-4 text-sm">
          Archived projects are read-only.
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="font-semibold">Task controls</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Assigned to {task.assigneeDisplayName ?? "nobody"}. Version{" "}
            {task.version}.
          </p>
          {canChangeStatus && writable && (
            <div className="mt-4 flex flex-wrap gap-2">
              {transitions[task.status].map((status) => (
                <Button
                  key={status}
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    void mutate(() =>
                      requestGraphQL(ChangeTaskStatusDocument, {
                        projectId,
                        taskId,
                        status,
                        expectedVersion: task.version,
                      }),
                    )
                  }
                >
                  {status}
                </Button>
              ))}
            </div>
          )}
          {canManage && writable && (
            <>
              <form
                className="mt-5 space-y-3 border-t pt-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  void mutate(() =>
                    requestGraphQL(UpdateTaskDocument, {
                      projectId,
                      taskId,
                      input: {
                        title: String(form.get("title")),
                        description: String(form.get("description")) || null,
                        priority: String(form.get("priority")) as TaskPriority,
                        dueDate: String(form.get("dueDate")) || null,
                        expectedVersion: task.version,
                      },
                    }),
                  );
                }}
              >
                <label className="block text-sm">
                  Title
                  <input
                    name="title"
                    required
                    defaultValue={task.title}
                    className="mt-1 h-10 w-full rounded-lg border px-3"
                  />
                </label>
                <label className="block text-sm">
                  Description
                  <textarea
                    name="description"
                    defaultValue={task.description ?? ""}
                    className="mt-1 w-full rounded-lg border p-3"
                  />
                </label>
                <label className="block text-sm">
                  Priority
                  <select
                    name="priority"
                    defaultValue={task.priority}
                    className="mt-1 h-10 w-full rounded-lg border px-3"
                  >
                    <option>LOW</option>
                    <option>MEDIUM</option>
                    <option>HIGH</option>
                    <option>URGENT</option>
                  </select>
                </label>
                <label className="block text-sm">
                  Due date
                  <input
                    name="dueDate"
                    type="date"
                    defaultValue={task.dueDate ?? ""}
                    className="mt-1 h-10 w-full rounded-lg border px-3"
                  />
                </label>
                <Button type="submit">Save task</Button>
              </form>
              <label className="mt-5 block border-t pt-4 text-sm">
                Assignee
                <select
                  aria-label="Task assignee"
                  value={task.assigneeEmployeeId ?? ""}
                  onChange={(event) =>
                    void mutate(() =>
                      requestGraphQL(AssignTaskDocument, {
                        projectId,
                        taskId,
                        assigneeEmployeeId: event.target.value || null,
                        expectedVersion: task.version,
                      }),
                    )
                  }
                  className="mt-1 h-10 w-full rounded-lg border px-3"
                >
                  <option value="">Unassigned</option>
                  {project.memberships.map((item) => (
                    <option key={item.employeeId} value={item.employeeId}>
                      {item.displayName ?? item.employeeId}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
        </Card>
        <Card className="p-6">
          <h2 className="font-semibold">Comments</h2>
          <div className="mt-4 space-y-3">
            {data.taskComments.nodes.map((comment) => (
              <div key={comment.id} className="rounded-lg border p-3">
                <p className="text-xs font-medium">
                  {comment.authorDisplayName ?? "Unavailable employee"}
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm">
                  {comment.body}
                </p>
              </div>
            ))}
            {!data.taskComments.nodes.length && (
              <p className="text-sm text-muted-foreground">No comments yet.</p>
            )}
          </div>
          {writable && (
            <form
              className="mt-4"
              onSubmit={(event) => {
                event.preventDefault();
                const form = event.currentTarget;
                const body = String(new FormData(form).get("body"));
                void mutate(async () => {
                  await requestGraphQL(AddTaskCommentDocument, {
                    projectId,
                    taskId,
                    body,
                  });
                  form.reset();
                });
              }}
            >
              <label className="block text-sm">
                Add comment
                <textarea
                  name="body"
                  required
                  maxLength={4000}
                  className="mt-1 w-full rounded-lg border p-3"
                />
              </label>
              <Button className="mt-2">Add comment</Button>
            </form>
          )}
        </Card>
      </div>
      <Card className="p-6">
        <h2 className="font-semibold">Activity</h2>
        <ol className="mt-4 space-y-3">
          {data.taskActivity.nodes.map((item) => (
            <li key={item.id} className="border-l pl-3 text-sm">
              <span className="font-medium">
                {item.actorDisplayName ?? "Unavailable employee"}
              </span>{" "}
              · {item.activityType}
              <span className="block text-xs text-muted-foreground">
                {new Date(item.createdAt).toLocaleString()}
              </span>
            </li>
          ))}
        </ol>
      </Card>
      {message && (
        <p role="alert" className="rounded-lg border p-4 text-sm">
          {message}
        </p>
      )}
    </div>
  );
}
