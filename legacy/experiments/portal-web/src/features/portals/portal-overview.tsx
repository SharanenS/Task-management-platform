"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "@/components/portal-ui/portal-link";
import {
  ArrowUpRight,
  FolderKanban,
  ListTodo,
  RefreshCw,
  FileChartColumn,
  ShieldCheck,
} from "lucide-react";
import type { EmployeeProfile } from "@/auth/types";
import {
  PortalCard,
  PortalCardContent,
  PortalCardHeader,
  PortalCardTitle,
} from "@/components/portal-ui/portal-card";
import { PortalButton } from "@/components/portal-ui/portal-button";
import { TaskStatusChart } from "@/components/portal-ui/charts/task-status-chart";
import { ErrorState, EmptyState, Skeleton } from "@/components/ui/states";
import {
  DashboardDocument,
  type DashboardQuery,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

export function PortalOverview({ employee }: { employee: EmployeeProfile }) {
  const [data, setData] = useState<DashboardQuery["dashboard"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    try {
      setData((await requestGraphQL(DashboardDocument, {})).dashboard);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    const timer = setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);
  const admin = employee.role === "ADMIN";
  const manager = employee.role === "MANAGER";
  const title = admin
    ? "Your organisation, in focus."
    : manager
      ? "Keep delivery moving."
      : "Make room for your best work.";
  const tasks =
    admin || manager ? data?.taskMetrics : data?.assignedTaskMetrics;
  const projects = data?.projectMetrics;
  const cards = [
    {
      label: admin
        ? "Projects"
        : manager
          ? "Managed projects"
          : "Accessible projects",
      value: manager ? projects?.managedTotalCount : projects?.totalCount,
      icon: FolderKanban,
      available: data?.workAvailable,
    },
    {
      label: admin || manager ? "Open tasks" : "My open tasks",
      value: tasks
        ? tasks.todoCount + tasks.inProgressCount + tasks.blockedCount
        : undefined,
      icon: ListTodo,
      available: data?.workAvailable,
    },
    {
      label: "Completed tasks",
      value: tasks?.doneCount,
      icon: ShieldCheck,
      available: data?.workAvailable,
    },
    {
      label: "Successful exports",
      value: data?.jobMetrics?.succeededCount,
      icon: FileChartColumn,
      available: data?.jobAvailable,
    },
  ];
  return (
    <div className="space-y-7">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs text-muted-foreground">
            Welcome back, {employee.displayName}
          </p>
          <h1 className="mt-2 text-3xl font-medium tracking-tight sm:text-4xl">
            {title}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
            {admin
              ? "People, projects and platform health, connected in one place."
              : manager
                ? "Coordinate projects and stay close to your team's delivery."
                : "Your assigned work and the projects you contribute to."}
          </p>
        </div>
        <PortalButton
          variant="secondary"
          onClick={() => void load()}
          disabled={loading}
        >
          <RefreshCw className="size-4" />
          Refresh overview
        </PortalButton>
      </section>
      {failed && (
        <ErrorState
          title="Overview unavailable"
          description="Your workspace could not be loaded. Please try again."
          onRetry={() => void load()}
        />
      )}
      {!failed && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {cards.map(({ label, value, icon: Icon, available }) => (
            <PortalCard key={label}>
              <PortalCardContent className="pt-5">
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                  <span>{label}</span>
                  <Icon className="size-4 text-cyan-700" />
                </div>
                {loading ? (
                  <Skeleton className="mt-4 h-9 w-20" />
                ) : (
                  <p className="mt-4 text-3xl font-medium">
                    {available && value != null ? value : "—"}
                  </p>
                )}
              </PortalCardContent>
            </PortalCard>
          ))}
        </div>
      )}
      {!loading && data && !failed && (
        <>
          {(!data.workAvailable || !data.jobAvailable) && (
            <p
              role="status"
              className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
            >
              Some services are temporarily unavailable. Unavailable metrics are
              shown as a dash.
            </p>
          )}
          <div className="grid min-w-0 gap-6 xl:grid-cols-[1.15fr_1fr]">
            <PortalCard variant="dark">
              <PortalCardHeader>
                <p className="text-[10px] uppercase tracking-[.18em] text-cyan-300">
                  Delivery snapshot
                </p>
                <PortalCardTitle as="h2">
                  {admin || manager
                    ? "Task distribution"
                    : "My task distribution"}
                </PortalCardTitle>
                <p className="text-xs leading-6 text-[#8fa8c6]">
                  Current authorised task counts from your workspace.
                </p>
              </PortalCardHeader>
              <PortalCardContent className="pt-4">
                {data.workAvailable && tasks ? (
                  <TaskStatusChart
                    data={[
                      {
                        status: "completed",
                        label: "Completed",
                        count: tasks.doneCount,
                        color: "#00c4cc",
                      },
                      {
                        status: "in_progress",
                        label: "In progress",
                        count: tasks.inProgressCount,
                        color: "#38bdf8",
                      },
                      {
                        status: "pending",
                        label: "Pending",
                        count: tasks.todoCount,
                        color: "#a5b4fc",
                      },
                      {
                        status: "blocked",
                        label: "Blocked",
                        count: tasks.blockedCount,
                        color: "#fda4af",
                      },
                      {
                        status: "cancelled",
                        label: "Cancelled",
                        count: tasks.cancelledCount,
                        color: "#94a3b8",
                      },
                    ]}
                  />
                ) : (
                  <p className="py-8 text-sm text-[#8fa8c6]">
                    Task metrics are unavailable.
                  </p>
                )}
              </PortalCardContent>
            </PortalCard>
            <PortalCard>
              <PortalCardHeader>
                <div className="flex items-center justify-between gap-3">
                  <PortalCardTitle as="h2">Project portfolio</PortalCardTitle>
                  <Link
                    href="/projects"
                    className="inline-flex items-center gap-1 text-xs text-cyan-800"
                  >
                    View projects <ArrowUpRight className="size-3" />
                  </Link>
                </div>
              </PortalCardHeader>
              <PortalCardContent>
                {!data.workAvailable ? (
                  <p className="py-6 text-sm text-muted-foreground">
                    Projects are temporarily unavailable.
                  </p>
                ) : data.recentProjects?.length ? (
                  <ul className="divide-y">
                    {data.recentProjects?.map((project) => (
                      <li key={project.id}>
                        <Link
                          href={`/projects/${project.id}`}
                          className="flex items-center gap-3 py-4"
                        >
                          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-cyan-50 text-cyan-800">
                            <FolderKanban className="size-4" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium">
                              {project.name}
                            </span>
                            <span className="mt-1 block text-xs text-muted-foreground">
                              {project.key} · {project.status.toLowerCase()}
                            </span>
                          </span>
                          <ArrowUpRight className="size-4 shrink-0 text-muted-foreground" />
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState
                    title="Your next project starts here"
                    description="Projects will appear here when they are available to your account."
                  />
                )}
              </PortalCardContent>
            </PortalCard>
          </div>
          <PortalCard>
            <PortalCardHeader>
              <PortalCardTitle as="h2">
                {admin
                  ? "Administration"
                  : manager
                    ? "Delivery workspace"
                    : "My assigned work"}
              </PortalCardTitle>
            </PortalCardHeader>
            <PortalCardContent>
              {admin ? (
                <div className="grid gap-3 sm:grid-cols-3">
                  {[
                    [
                      "People & accounts",
                      "/employees",
                      "Manage access and employee accounts.",
                    ],
                    [
                      "Operations",
                      "/operations",
                      "Review platform health and service signals.",
                    ],
                    [
                      "Reports",
                      "/reports",
                      "Open your report requests and downloads.",
                    ],
                  ].map(([label, href, detail]) => (
                    <Link
                      key={href}
                      href={href}
                      className="rounded-xl border p-4 hover:bg-muted"
                    >
                      <span className="text-sm font-medium">{label}</span>
                      <span className="mt-2 block text-xs leading-5 text-muted-foreground">
                        {detail}
                      </span>
                    </Link>
                  ))}
                </div>
              ) : manager ? (
                <p className="text-sm leading-6 text-muted-foreground">
                  Open a project to review delivery, coordinate its team and
                  access reports.
                </p>
              ) : data.recentAssignedTasks?.length ? (
                <ul className="divide-y">
                  {data.recentAssignedTasks?.map((task) => (
                    <li key={task.id}>
                      <Link
                        href={`/projects/${task.projectId}/tasks/${task.id}`}
                        className="flex flex-wrap items-center justify-between gap-2 py-4"
                      >
                        <span className="text-sm font-medium">
                          {task.title}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {task.projectKey}-{task.number} ·{" "}
                          {task.status.toLowerCase().replaceAll("_", " ")}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState
                  title="You're all caught up"
                  description="Your assigned tasks will appear here."
                />
              )}
            </PortalCardContent>
          </PortalCard>
        </>
      )}
    </div>
  );
}
