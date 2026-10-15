"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import {
  ProjectTaskBoardDocument,
  ProjectTasksDocument,
  type ProjectTaskBoardQuery,
  type ProjectTasksQuery,
  type TaskPriority,
  type TaskStatus,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

export function TaskDirectory({ projectId }: { projectId: string }) {
  const [mode, setMode] = useState<"list" | "board">("list");
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [list, setList] = useState<ProjectTasksQuery["projectTasks"] | null>(
    null,
  );
  const [board, setBoard] = useState<
    ProjectTaskBoardQuery["projectTaskBoard"] | null
  >(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<TaskStatus | "">("");
  const [priority, setPriority] = useState<TaskPriority | "">("");
  const [unassigned, setUnassigned] = useState(false);
  const [after, setAfter] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      if (mode === "board") {
        const result = await requestGraphQL(ProjectTaskBoardDocument, {
          projectId,
          laneSize: 12,
        });
        setBoard(result.projectTaskBoard);
      } else {
        const result = await requestGraphQL(ProjectTasksDocument, {
          projectId,
          first: 20,
          after,
          search: search || null,
          status: status || null,
          priority: priority || null,
          assigneeEmployeeId: null,
          unassigned,
        });
        setList(result.projectTasks);
      }
      setState("ready");
    } catch {
      setState("error");
    }
  }, [after, mode, priority, projectId, search, status, unassigned]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            href={`/projects/${projectId}`}
            className="text-xs font-medium text-primary hover:underline"
          >
            ← Project
          </Link>
          <h1 className="mt-2 text-3xl font-semibold">Tasks</h1>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setMode(mode === "list" ? "board" : "list")}
          >
            {mode === "list" ? "Board view" : "List view"}
          </Button>
          <Button asChild>
            <Link href={`/projects/${projectId}/tasks/new`}>Create task</Link>
          </Button>
        </div>
      </div>
      {mode === "list" && (
        <Card className="flex flex-wrap gap-3 p-4">
          <label className="grow text-sm">
            Search
            <input
              aria-label="Search tasks"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="mt-1 h-10 w-full rounded-lg border px-3"
            />
          </label>
          <label className="text-sm">
            Status
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as TaskStatus | "")}
              className="mt-1 block h-10 rounded-lg border px-3"
            >
              <option value="">All</option>
              {["TODO", "IN_PROGRESS", "BLOCKED", "DONE", "CANCELLED"].map(
                (v) => (
                  <option key={v}>{v}</option>
                ),
              )}
            </select>
          </label>
          <label className="text-sm">
            Priority
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as TaskPriority | "")}
              className="mt-1 block h-10 rounded-lg border px-3"
            >
              <option value="">All</option>
              {["LOW", "MEDIUM", "HIGH", "URGENT"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label className="flex items-end gap-2 pb-2 text-sm">
            <input
              type="checkbox"
              checked={unassigned}
              onChange={(e) => setUnassigned(e.target.checked)}
            />{" "}
            Unassigned
          </label>
          <Button
            className="self-end"
            onClick={() => {
              setAfter(null);
              void load();
            }}
          >
            Apply
          </Button>
        </Card>
      )}
      {state === "loading" && (
        <Card className="space-y-3 p-6" aria-label="Loading tasks">
          <Skeleton className="h-8" />
          <Skeleton className="h-20" />
        </Card>
      )}
      {state === "error" && (
        <ErrorState
          title="Unable to load tasks"
          description="Task management is temporarily unavailable."
          onRetry={() => void load()}
        />
      )}
      {state === "ready" &&
        mode === "list" &&
        list &&
        (list.nodes.length ? (
          <div className="space-y-3">
            {list.nodes.map((task) => (
              <Link
                key={task.id}
                href={`/projects/${projectId}/tasks/${task.id}`}
                className="block"
              >
                <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:border-primary/40">
                  <div>
                    <span className="text-xs text-muted-foreground">
                      {task.reference}
                    </span>
                    <h2 className="font-medium">{task.title}</h2>
                    <p className="text-xs text-muted-foreground">
                      {task.assigneeDisplayName ?? "Unassigned"}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Badge>{task.priority}</Badge>
                    <Badge>{task.status}</Badge>
                  </div>
                </Card>
              </Link>
            ))}
            <Button
              variant="outline"
              disabled={!list.pageInfo.hasNextPage}
              onClick={() => setAfter(list.pageInfo.endCursor ?? null)}
            >
              Next page
            </Button>
          </div>
        ) : (
          <EmptyState
            title="No tasks found"
            description="Create a task or adjust the filters."
          />
        ))}
      {state === "ready" && mode === "board" && board && (
        <div className="grid gap-4 overflow-x-auto lg:grid-cols-5">
          {board.lanes.map((lane) => (
            <Card key={lane.status} className="min-w-56 p-4">
              <h2 className="font-semibold">{lane.status}</h2>
              <div className="mt-3 space-y-2">
                {lane.tasks.map((task) => (
                  <Link
                    key={task.id}
                    href={`/projects/${projectId}/tasks/${task.id}`}
                    className="block rounded-lg border p-3 text-sm"
                  >
                    <span className="text-xs text-muted-foreground">
                      {task.reference}
                    </span>
                    <span className="block font-medium">{task.title}</span>
                  </Link>
                ))}
                {!lane.tasks.length && (
                  <p className="text-xs text-muted-foreground">No tasks</p>
                )}
                {lane.hasMore && (
                  <p className="text-xs font-medium text-primary">
                    Additional tasks are available in the list.
                  </p>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
