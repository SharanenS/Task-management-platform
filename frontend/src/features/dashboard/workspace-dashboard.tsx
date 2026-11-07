"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  Briefcase,
  CheckCircle2,
  Clock,
  FolderKanban,
  Layers,
  ListTodo,
  RefreshCw,
  XCircle,
  Zap,
} from "lucide-react";

import type { EmployeeProfile } from "@/auth/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import {
  DashboardDocument,
  type DashboardQuery,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

type DashboardData = DashboardQuery["dashboard"];

export function WorkspaceDashboard({
  employee,
}: {
  employee: EmployeeProfile;
}) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [isRetrying, setIsRetrying] = useState(false);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const result = await requestGraphQL(DashboardDocument, {});
      setData(result.dashboard);
      if (!result.dashboard.workAvailable && !result.dashboard.jobAvailable) {
        setState("error");
      } else {
        setState("ready");
      }
    } catch {
      setState("error");
    } finally {
      setIsRetrying(false);
    }
  }, [setData, setIsRetrying, setState]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const handleRetry = () => {
    setIsRetrying(true);
    void load();
  };

  if (state === "loading") {
    return (
      <div className="space-y-8" aria-label="Loading workspace dashboard">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-96" />
          </div>
          <Skeleton className="h-10 w-36" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-5">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="mt-2 h-8 w-16" />
              <Skeleton className="mt-2 h-3 w-32" />
            </Card>
          ))}
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="p-6">
            <Skeleton className="h-6 w-36" />
            <Skeleton className="mt-4 h-24 w-full" />
          </Card>
          <Card className="p-6">
            <Skeleton className="h-6 w-36" />
            <Skeleton className="mt-4 h-24 w-full" />
          </Card>
        </div>
      </div>
    );
  }

  if (state === "error" || !data) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            Workspace Dashboard
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            A live aggregate view of your projects, tasks, and background jobs.
          </p>
        </div>
        <ErrorState
          title="Workspace dashboard unavailable"
          description="The dashboard services are temporarily unavailable. Please try again."
          onRetry={handleRetry}
          pending={isRetrying}
        />
      </div>
    );
  }

  const role = employee.role;
  const pm = data.projectMetrics;
  const tm = data.taskMetrics;
  const atm = data.assignedTaskMetrics;
  const jm = data.jobMetrics;

  return (
    <div className="space-y-8">
      {/* Header section */}
      <section className="flex flex-wrap items-end justify-between gap-4 border-b pb-6">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-xs font-semibold tracking-[.14em] text-primary uppercase">
              Workspace Overview
            </p>
            <Badge className="font-mono text-xs">{role}</Badge>
          </div>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            Welcome back, {employee.displayName}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {role === "MEMBER" &&
              "Personal workspace overview: your accessible projects, assigned tasks, and background jobs."}
            {role === "MANAGER" &&
              "Project management overview: health and tasks across managed projects, personal assigned work, and background jobs."}
            {role === "ADMIN" &&
              "Platform-wide executive overview: aggregate metrics across projects, tasks, and background jobs."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRetry}
            disabled={isRetrying}
          >
            <RefreshCw
              className={`size-4 ${isRetrying ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Button asChild>
            <Link href="/system">
              System status <ArrowUpRight className="size-4" />
            </Link>
          </Button>
        </div>
      </section>

      {/* Partial failure alert for Work Service */}
      {!data.workAvailable && (
        <ErrorState
          title="Work Service Temporarily Unavailable"
          description="Project and task metrics could not be loaded at this time. Background job data is still displayed below."
          onRetry={handleRetry}
          pending={isRetrying}
        />
      )}

      {/* Work Service metrics & previews */}
      {data.workAvailable && pm && (
        <section className="space-y-6" aria-label="Projects and Tasks Overview">
          {/* Projects Overview */}
          <div>
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold tracking-tight">Projects</h2>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/projects">
                  View all projects <ArrowUpRight className="size-4" />
                </Link>
              </Button>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card className="p-5 transition hover:shadow-sm">
                <Link
                  href="/projects"
                  className="block focus:outline-none focus:ring-2 focus:ring-primary rounded-lg"
                >
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span className="text-xs font-semibold tracking-wider uppercase">
                      Accessible
                    </span>
                    <FolderKanban className="size-4 text-indigo-600" />
                  </div>
                  <div className="mt-2 text-3xl font-bold">{pm.totalCount}</div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Total visible projects
                  </p>
                </Link>
              </Card>

              {(role === "MANAGER" || role === "ADMIN") && (
                <Card className="p-5 transition hover:shadow-sm">
                  <Link
                    href="/projects"
                    className="block focus:outline-none focus:ring-2 focus:ring-primary rounded-lg"
                  >
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span className="text-xs font-semibold tracking-wider uppercase">
                        Managed
                      </span>
                      <Briefcase className="size-4 text-sky-600" />
                    </div>
                    <div className="mt-2 text-3xl font-bold">
                      {pm.managedTotalCount ?? 0}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {role === "ADMIN"
                        ? "All managed projects"
                        : "Projects you manage"}
                    </p>
                  </Link>
                </Card>
              )}

              <Card className="p-5 transition hover:shadow-sm">
                <Link
                  href="/projects?status=ACTIVE"
                  className="block focus:outline-none focus:ring-2 focus:ring-primary rounded-lg"
                >
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span className="text-xs font-semibold tracking-wider uppercase">
                      Active
                    </span>
                    <CheckCircle2 className="size-4 text-emerald-600" />
                  </div>
                  <div className="mt-2 text-3xl font-bold">
                    {pm.activeCount}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    In active execution
                  </p>
                </Link>
              </Card>

              <Card className="p-5 transition hover:shadow-sm">
                <Link
                  href="/projects?status=DRAFT"
                  className="block focus:outline-none focus:ring-2 focus:ring-primary rounded-lg"
                >
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span className="text-xs font-semibold tracking-wider uppercase">
                      Draft
                    </span>
                    <Clock className="size-4 text-amber-600" />
                  </div>
                  <div className="mt-2 text-3xl font-bold">{pm.draftCount}</div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    In planning / draft
                  </p>
                </Link>
              </Card>

              {role === "MEMBER" && (
                <Card className="p-5 transition hover:shadow-sm">
                  <Link
                    href="/projects?status=ARCHIVED"
                    className="block focus:outline-none focus:ring-2 focus:ring-primary rounded-lg"
                  >
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span className="text-xs font-semibold tracking-wider uppercase">
                        Archived
                      </span>
                      <Layers className="size-4 text-gray-500" />
                    </div>
                    <div className="mt-2 text-3xl font-bold">
                      {pm.archivedCount}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Completed or archived
                    </p>
                  </Link>
                </Card>
              )}
            </div>
          </div>

          {/* Managed / Platform Tasks Breakdown (for MANAGER / ADMIN) */}
          {(role === "MANAGER" || role === "ADMIN") && tm && (
            <div>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold tracking-tight">
                  {role === "ADMIN"
                    ? "Platform Tasks Breakdown"
                    : "Managed Projects Tasks"}
                </h3>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7">
                <Card className="p-4">
                  <div className="text-xs text-muted-foreground">
                    Total Tasks
                  </div>
                  <div className="mt-1 text-2xl font-bold">{tm.totalCount}</div>
                </Card>
                <Card className="p-4">
                  <div className="text-xs text-muted-foreground">To Do</div>
                  <div className="mt-1 text-2xl font-bold text-slate-700">
                    {tm.todoCount}
                  </div>
                </Card>
                <Card className="p-4">
                  <div className="text-xs text-muted-foreground">
                    In Progress
                  </div>
                  <div className="mt-1 text-2xl font-bold text-blue-600">
                    {tm.inProgressCount}
                  </div>
                </Card>
                <Card className="p-4">
                  <div className="text-xs text-muted-foreground">Blocked</div>
                  <div className="mt-1 text-2xl font-bold text-amber-600">
                    {tm.blockedCount}
                  </div>
                </Card>
                <Card className="p-4">
                  <div className="text-xs text-muted-foreground">Done</div>
                  <div className="mt-1 text-2xl font-bold text-emerald-600">
                    {tm.doneCount}
                  </div>
                </Card>
                <Card className="p-4">
                  <div className="text-xs text-muted-foreground">Cancelled</div>
                  <div className="mt-1 text-2xl font-bold text-gray-500">
                    {tm.cancelledCount}
                  </div>
                </Card>
                <Card
                  className={`p-4 ${tm.overdueCount > 0 ? "border-red-200 bg-red-50/50" : ""}`}
                >
                  <div className="flex items-center gap-1 text-xs font-semibold text-red-700">
                    <AlertTriangle className="size-3.5" /> Overdue
                  </div>
                  <div className="mt-1 text-2xl font-bold text-red-700">
                    {tm.overdueCount}
                  </div>
                </Card>
              </div>
            </div>
          )}

          {/* Assigned Work & Recent Previews Grid */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Assigned Work Card */}
            <Card className="flex min-w-0 flex-col p-4 sm:p-6">
              <div className="flex items-center justify-between border-b pb-4">
                <div>
                  <h3 className="font-semibold">My Assigned Work</h3>
                  <p className="text-xs text-muted-foreground">
                    Tasks currently assigned to you across accessible projects
                  </p>
                </div>
                <ListTodo className="size-5 text-primary" />
              </div>

              {atm && (
                <div className="mt-4 grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
                  <div className="rounded-lg bg-muted/50 p-2.5">
                    <div className="text-xs text-muted-foreground">
                      Assigned
                    </div>
                    <div className="text-xl font-bold">{atm.totalCount}</div>
                  </div>
                  <div className="rounded-lg bg-blue-50 p-2.5">
                    <div className="text-xs text-blue-700">In Flight</div>
                    <div className="text-xl font-bold text-blue-800">
                      {atm.todoCount + atm.inProgressCount + atm.blockedCount}
                    </div>
                  </div>
                  <div className="rounded-lg bg-emerald-50 p-2.5">
                    <div className="text-xs text-emerald-700">Done</div>
                    <div className="text-xl font-bold text-emerald-800">
                      {atm.doneCount}
                    </div>
                  </div>
                  <div
                    className={`rounded-lg p-2.5 ${atm.overdueCount > 0 ? "bg-red-100 text-red-900" : "bg-muted/50"}`}
                  >
                    <div
                      className={`text-xs ${atm.overdueCount > 0 ? "font-semibold text-red-800" : "text-muted-foreground"}`}
                    >
                      Overdue
                    </div>
                    <div
                      className={`text-xl font-bold ${atm.overdueCount > 0 ? "text-red-700" : ""}`}
                    >
                      {atm.overdueCount}
                    </div>
                  </div>
                </div>
              )}

              <div className="mt-5 flex-1">
                <div className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                  Recent Assigned Tasks
                </div>
                {data.recentAssignedTasks &&
                data.recentAssignedTasks.length > 0 ? (
                  <ul className="mt-3 divide-y rounded-lg border">
                    {data.recentAssignedTasks.map((task) => (
                      <li
                        key={task.id}
                        className="p-3 transition hover:bg-muted/40"
                      >
                        <Link
                          href={`/projects/${task.projectId}/tasks`}
                          className="flex min-w-0 items-center justify-between gap-3 text-sm focus:outline-none focus:underline"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-bold text-primary">
                                {task.projectKey}-{task.number}
                              </span>
                              <Badge className="text-[10px]">
                                {task.status}
                              </Badge>
                              {task.dueDate &&
                                new Date(task.dueDate) <
                                  new Date(new Date().toDateString()) &&
                                !["DONE", "CANCELLED"].includes(
                                  task.status,
                                ) && (
                                  <Badge className="bg-red-100 text-red-800 text-[10px]">
                                    Overdue
                                  </Badge>
                                )}
                            </div>
                            <p className="mt-1 truncate font-medium">
                              {task.title}
                            </p>
                          </div>
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {task.dueDate
                              ? `Due ${task.dueDate}`
                              : "No due date"}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="mt-3">
                    <EmptyState
                      title="No assigned tasks"
                      description="You currently have no tasks assigned to you across accessible projects."
                    />
                  </div>
                )}
              </div>
            </Card>

            {/* Recent Projects Preview */}
            <Card className="flex min-w-0 flex-col p-4 sm:p-6">
              <div className="flex items-center justify-between border-b pb-4">
                <div>
                  <h3 className="font-semibold">Recent Projects</h3>
                  <p className="text-xs text-muted-foreground">
                    Projects you have access to or recently worked on
                  </p>
                </div>
                <FolderKanban className="size-5 text-primary" />
              </div>

              <div className="mt-5 flex-1">
                {data.recentProjects && data.recentProjects.length > 0 ? (
                  <ul className="divide-y rounded-lg border">
                    {data.recentProjects.map((project) => (
                      <li
                        key={project.id}
                        className="p-3 transition hover:bg-muted/40"
                      >
                        <Link
                          href={`/projects/${project.id}`}
                          className="flex min-w-0 items-center justify-between gap-3 text-sm focus:outline-none focus:underline"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-bold text-primary">
                                {project.key}
                              </span>
                              <Badge className="text-[10px]">
                                {project.status}
                              </Badge>
                            </div>
                            <p className="mt-1 truncate font-medium">
                              {project.name}
                            </p>
                          </div>
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {project.updatedAt
                              ? new Date(project.updatedAt).toLocaleDateString()
                              : ""}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState
                    title="No projects available"
                    description="You are not currently a member of any projects."
                  />
                )}
              </div>
            </Card>
          </div>
        </section>
      )}

      {/* Partial failure alert for Job Service */}
      {!data.jobAvailable && (
        <ErrorState
          title="Job Service Temporarily Unavailable"
          description="Background job summaries and history could not be loaded at this time. Project and task data is still available above."
          onRetry={handleRetry}
          pending={isRetrying}
        />
      )}

      {/* Job Service metrics & previews */}
      {data.jobAvailable && jm && (
        <section className="space-y-6" aria-label="Background Jobs Overview">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold tracking-tight">
                {role === "ADMIN"
                  ? "Platform Background Jobs"
                  : "My Background Jobs"}
              </h2>
              <p className="text-xs text-muted-foreground">
                {role === "ADMIN"
                  ? "Platform-wide summary of asynchronous report exports and background processing."
                  : "Status of report exports and background jobs you have submitted."}
              </p>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/jobs">
                View all jobs <ArrowUpRight className="size-4" />
              </Link>
            </Button>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <Card className="p-5 transition hover:shadow-sm">
              <Link
                href="/jobs"
                className="block focus:outline-none focus:ring-2 focus:ring-primary rounded-lg"
              >
                <div className="flex items-center justify-between text-muted-foreground">
                  <span className="text-xs font-semibold tracking-wider uppercase">
                    Total Jobs
                  </span>
                  <Zap className="size-4 text-violet-600" />
                </div>
                <div className="mt-2 text-3xl font-bold">{jm.totalCount}</div>
                <p className="mt-1 text-xs text-muted-foreground">
                  All job submissions
                </p>
              </Link>
            </Card>

            <Card className="p-5 transition hover:shadow-sm">
              <Link
                href="/jobs?status=SUCCEEDED"
                className="block focus:outline-none focus:ring-2 focus:ring-primary rounded-lg"
              >
                <div className="flex items-center justify-between text-muted-foreground">
                  <span className="text-xs font-semibold tracking-wider uppercase">
                    Succeeded
                  </span>
                  <CheckCircle2 className="size-4 text-emerald-600" />
                </div>
                <div className="mt-2 text-3xl font-bold text-emerald-700">
                  {jm.succeededCount}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Completed successfully
                </p>
              </Link>
            </Card>

            <Card
              className={`p-5 transition hover:shadow-sm ${jm.failedCount > 0 ? "border-red-200 bg-red-50/30" : ""}`}
            >
              <Link
                href="/jobs?status=FAILED"
                className="block focus:outline-none focus:ring-2 focus:ring-primary rounded-lg"
              >
                <div className="flex items-center justify-between text-muted-foreground">
                  <span
                    className={`text-xs font-semibold tracking-wider uppercase ${jm.failedCount > 0 ? "text-red-700 font-bold" : ""}`}
                  >
                    Failed
                  </span>
                  <XCircle
                    className={`size-4 ${jm.failedCount > 0 ? "text-red-600" : "text-gray-400"}`}
                  />
                </div>
                <div
                  className={`mt-2 text-3xl font-bold ${jm.failedCount > 0 ? "text-red-700" : ""}`}
                >
                  {jm.failedCount}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Require attention
                </p>
              </Link>
            </Card>

            <Card className="p-5 transition hover:shadow-sm">
              <Link
                href="/jobs?status=RUNNING"
                className="block focus:outline-none focus:ring-2 focus:ring-primary rounded-lg"
              >
                <div className="flex items-center justify-between text-muted-foreground">
                  <span className="text-xs font-semibold tracking-wider uppercase">
                    Running
                  </span>
                  <Clock className="size-4 text-blue-600" />
                </div>
                <div className="mt-2 text-3xl font-bold text-blue-600">
                  {jm.runningCount}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Currently executing
                </p>
              </Link>
            </Card>

            <Card className="p-5 transition hover:shadow-sm">
              <Link
                href="/jobs?status=SUBMITTED"
                className="block focus:outline-none focus:ring-2 focus:ring-primary rounded-lg"
              >
                <div className="flex items-center justify-between text-muted-foreground">
                  <span className="text-xs font-semibold tracking-wider uppercase">
                    Queued
                  </span>
                  <Layers className="size-4 text-amber-600" />
                </div>
                <div className="mt-2 text-3xl font-bold text-amber-700">
                  {jm.queuedCount + jm.submittedCount}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Awaiting execution
                </p>
              </Link>
            </Card>
          </div>

          {/* Recent Jobs Preview */}
          <Card className="min-w-0 p-4 sm:p-6">
            <div className="flex items-center justify-between border-b pb-4">
              <h3 className="font-semibold">Recent Job Submissions</h3>
              <Button variant="outline" size="sm" asChild>
                <Link href="/jobs/new">Submit new job</Link>
              </Button>
            </div>
            {data.recentJobs && data.recentJobs.length > 0 ? (
              <ul className="mt-4 divide-y rounded-lg border">
                {data.recentJobs.map((job) => (
                  <li key={job.id} className="p-3 transition hover:bg-muted/40">
                    <Link
                      href="/jobs"
                      className="flex min-w-0 items-center justify-between gap-3 text-sm focus:outline-none focus:underline"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-semibold">
                            {job.jobType === "PROJECT_TASK_EXPORT"
                              ? "Task Export"
                              : job.jobType}
                          </span>
                          <Badge
                            tone={
                              job.status === "SUCCEEDED" ? "success" : undefined
                            }
                            className={
                              job.status === "FAILED"
                                ? "bg-red-100 text-red-800 text-[10px]"
                                : "text-[10px]"
                            }
                          >
                            {job.status}
                          </Badge>
                        </div>
                        {job.resultSummary && (
                          <p className="mt-1 truncate text-xs text-muted-foreground">
                            {job.resultSummary}
                          </p>
                        )}
                      </div>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {new Date(job.createdAt).toLocaleDateString()}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="mt-4">
                <EmptyState
                  title="No background jobs"
                  description="No background processing or export jobs have been submitted yet."
                />
              </div>
            )}
          </Card>
        </section>
      )}
    </div>
  );
}
