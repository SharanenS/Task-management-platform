import Link from "next/link";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCheck,
  Circle,
  Clock3,
  FolderKanban,
  Layers,
  ListTodo,
  Sparkles,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const stats = [
  {
    label: "Active projects",
    value: "12",
    detail: "Across your workspace",
    change: "+2 this month",
    icon: FolderKanban,
    color: "bg-indigo-50 text-indigo-600",
  },
  {
    label: "Tasks in progress",
    value: "48",
    detail: "Moving work forward",
    change: "8 due this week",
    icon: ListTodo,
    color: "bg-amber-50 text-amber-700",
  },
  {
    label: "Completed tasks",
    value: "128",
    detail: "A little progress, every day",
    change: "+18 this month",
    icon: CheckCheck,
    color: "bg-emerald-50 text-emerald-700",
  },
  {
    label: "Background jobs",
    value: "24",
    detail: "Illustrative processing total",
    change: "Demo data",
    icon: Zap,
    color: "bg-violet-50 text-violet-600",
  },
];
const projects = [
  {
    name: "Website redesign",
    subtitle: "Design & experience",
    initials: "WR",
    color: "bg-violet-50 text-violet-600",
    progress: 72,
    tasks: "18 / 25",
    status: "In progress",
    people: ["AL", "SK", "+2"],
  },
  {
    name: "Customer onboarding",
    subtitle: "Customer success",
    initials: "CO",
    color: "bg-amber-50 text-amber-700",
    progress: 45,
    tasks: "9 / 20",
    status: "In progress",
    people: ["JM", "RT", "+1"],
  },
  {
    name: "Internal knowledge base",
    subtitle: "Operations",
    initials: "KB",
    color: "bg-sky-50 text-sky-700",
    progress: 90,
    tasks: "27 / 30",
    status: "In review",
    people: ["SK", "AL"],
  },
];
export default function Dashboard() {
  return (
    <div className="space-y-7">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Your workspace, at a glance</p>
          <h1 className="page-title">Make room for great work.</h1>
          <p className="page-description">
            A clear view of your projects, people, and progress.
          </p>
        </div>
        <Button asChild>
          <Link href="/system">
            View system status <ArrowUpRight />
          </Link>
        </Button>
      </section>
      <div className="flex items-start gap-3 rounded-lg border border-emerald-900/10 bg-[#edf4f0] px-4 py-3">
        <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" />
        <p className="text-xs leading-5 text-primary">
          <strong className="font-semibold">
            You’re exploring the foundation.
          </strong>{" "}
          The overview below uses sample data to preview the interface. Business
          features are not connected yet.
        </p>
        <Badge className="ml-auto hidden shrink-0 border border-emerald-900/10 bg-white/60 text-primary sm:inline-flex">
          Demo content
        </Badge>
      </div>
      <section
        aria-label="Sample workspace metrics"
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        {stats.map(({ label, value, detail, change, icon: Icon, color }) => (
          <Card key={label} className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {label}
              </span>
              <span className={`rounded-lg p-2 ${color}`}>
                <Icon className="size-4" />
              </span>
            </div>
            <p className="mt-3 text-[34px] font-semibold leading-none tracking-tight">
              {value}
            </p>
            <p className="mt-2 text-[11px] text-muted-foreground">{detail}</p>
            <div className="mt-5 flex items-center gap-1.5 border-t pt-3 text-[11px] text-muted-foreground">
              {label === "Completed tasks" || label === "Active projects" ? (
                <ArrowUpRight className="size-3.5 text-primary" />
              ) : (
                <Clock3 className="size-3.5" />
              )}
              {change}
            </div>
          </Card>
        ))}
      </section>
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.8fr)_minmax(280px,1fr)]">
        <div className="min-w-0 space-y-6">
          <Card>
            <div className="flex items-center justify-between gap-2 border-b px-5 py-5">
              <div>
                <h2 className="text-sm font-semibold">Project overview</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  A shared direction for every team.
                </p>
              </div>
              <Badge>Sample projects</Badge>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[530px] text-left text-xs">
                <caption className="sr-only">
                  Illustrative projects; project management arrives in Phase 4.
                </caption>
                <thead>
                  <tr className="border-b bg-background/60 text-[10px] font-medium text-muted-foreground">
                    <th className="px-5 py-3 font-medium">Project name</th>
                    <th className="px-3 py-3 font-medium">Progress</th>
                    <th className="px-3 py-3 font-medium">Team</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map((project) => (
                    <tr key={project.name} className="border-b last:border-0">
                      <td className="px-5 py-5">
                        <div className="flex items-center gap-3">
                          <span
                            className={`flex size-9 shrink-0 items-center justify-center rounded-lg text-[10px] font-semibold ${project.color}`}
                          >
                            {project.initials}
                          </span>
                          <div>
                            <p className="whitespace-nowrap font-medium">
                              {project.name}
                            </p>
                            <p className="mt-1 text-[10px] text-muted-foreground">
                              {project.subtitle}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-5">
                        <div className="flex min-w-20 items-center justify-between gap-3 text-[10px]">
                          <span>{project.progress}%</span>
                          <span className="text-muted-foreground">
                            {project.tasks}
                          </span>
                        </div>
                        <div
                          role="progressbar"
                          aria-label={`${project.name} sample progress`}
                          aria-valuenow={project.progress}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          className="mt-2 h-1.5 rounded-full bg-muted"
                        >
                          <div
                            className="h-full rounded-full bg-primary/75"
                            style={{ width: `${project.progress}%` }}
                          />
                        </div>
                      </td>
                      <td className="px-3 py-5">
                        <div className="flex -space-x-1.5">
                          {project.people.map((person) => (
                            <span
                              key={person}
                              className="flex size-6 items-center justify-center rounded-full border-2 border-white bg-stone-100 text-[8px] font-semibold text-stone-600"
                            >
                              {person}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-5 py-5">
                        <Badge
                          tone={
                            project.status === "In review"
                              ? "warning"
                              : "success"
                          }
                        >
                          {project.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center gap-2 border-t px-5 py-3 text-[10px] text-muted-foreground">
              <Layers className="size-3.5" /> Project management becomes
              available in Phase 4.
            </div>
          </Card>
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">A week of progress</h2>
              <Badge>Illustrative</Badge>
            </div>
            <div className="mt-5 flex flex-wrap items-end gap-6">
              <div className="min-w-32">
                <p className="text-3xl font-semibold tracking-tight">
                  32{" "}
                  <span className="text-xs font-normal text-muted-foreground">
                    tasks completed
                  </span>
                </p>
                <p className="mt-2 flex items-center gap-1 text-[11px] text-primary">
                  <ArrowUpRight className="size-3" /> 12% over the previous
                  sample week
                </p>
              </div>
              <div
                className="flex h-24 min-w-48 flex-1 items-end gap-3"
                role="img"
                aria-label="Illustrative weekly activity: Monday 4, Tuesday 6, Wednesday 3, Thursday 7, Friday 5, Saturday 4, Sunday 3 tasks."
              >
                {[4, 6, 3, 7, 5, 4, 3].map((value, index) => (
                  <div
                    key={index}
                    className="flex h-full flex-1 flex-col items-center justify-end gap-2"
                  >
                    <div
                      className={`w-full max-w-9 rounded-t-sm ${index === 3 ? "bg-primary" : "bg-[#dce9e2]"}`}
                      style={{ height: `${value * 10}px` }}
                    />
                    <span className="text-[9px] text-muted-foreground">
                      {["M", "T", "W", "T", "F", "S", "S"][index]}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>
        <div className="space-y-6">
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">
                The foundation checklist
              </h2>
              <span className="text-[10px] text-muted-foreground">
                Phase 01
              </span>
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              Small steps toward a connected workspace.
            </p>
            <div className="mt-6 space-y-5">
              {[
                {
                  title: "A place for your work",
                  text: "Responsive application shell",
                  done: true,
                },
                {
                  title: "One consistent language",
                  text: "Reusable interface components",
                  done: true,
                },
                {
                  title: "A real connection",
                  text: "Explore live GraphQL diagnostics",
                  done: true,
                },
                {
                  title: "Built together",
                  text: "Your review and acceptance",
                  done: false,
                },
              ].map((item) => (
                <div key={item.title} className="flex gap-3">
                  <span
                    className={`mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full ${item.done ? "bg-[#e9f1ed] text-primary" : "text-muted-foreground"}`}
                  >
                    {item.done ? (
                      <Check className="size-3" />
                    ) : (
                      <Circle className="size-4" />
                    )}
                  </span>
                  <div>
                    <p className="text-xs font-medium">{item.title}</p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {item.text}
                    </p>
                  </div>
                </div>
              ))}
            </div>
            <Button variant="outline" asChild className="mt-6 w-full">
              <Link href="/design-system">
                Explore the design system <ArrowRight />
              </Link>
            </Button>
          </Card>
          <div className="relative overflow-hidden rounded-xl bg-[#233e34] p-6 text-white">
            <div className="absolute -right-5 -top-7 size-32 rounded-full border border-white/10" />
            <div className="absolute -right-10 -top-12 size-44 rounded-full border border-white/10" />
            <span className="relative inline-flex rounded-lg border border-white/15 p-2">
              <ArrowDownRight className="size-5 text-emerald-200" />
            </span>
            <p className="relative mt-5 text-[10px] font-medium uppercase tracking-[.16em] text-emerald-100/70">
              Next on the roadmap
            </p>
            <h2 className="relative mt-2 text-lg font-medium tracking-tight">
              A workspace that knows you.
            </h2>
            <p className="relative mt-2 text-xs leading-5 text-white/65">
              Secure login, protected pages, and your personal profile arrive in
              Phase 2.
            </p>
            <div className="mt-5 border-t border-white/10 pt-4 text-[10px] text-white/65">
              Keycloak · OpenID Connect · Role-aware navigation
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
