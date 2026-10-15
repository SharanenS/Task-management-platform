"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Plus, Search } from "lucide-react";

import type { ApplicationRole } from "@/auth/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import {
  ProjectDirectoryDocument,
  type ProjectDirectoryQuery,
  type ProjectStatus,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

const PAGE_SIZE = 12;
type Item = ProjectDirectoryQuery["projects"]["nodes"][number];

export function ProjectDirectory({ role }: { role: ApplicationRole }) {
  const [items, setItems] = useState<Item[]>([]);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [status, setStatus] = useState<ProjectStatus | "">("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [history, setHistory] = useState<Array<string | null>>([]);
  const [pageInfo, setPageInfo] = useState({
    hasNextPage: false,
    endCursor: null as string | null,
  });
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  const load = useCallback(async () => {
    setState("loading");
    try {
      const data = await requestGraphQL(ProjectDirectoryDocument, {
        first: PAGE_SIZE,
        after: cursor,
        search: appliedSearch || null,
        status: status || null,
      });
      setItems(data.projects.nodes);
      setPageInfo(data.projects.pageInfo);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [appliedSearch, cursor, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-[.14em] text-primary uppercase">
            Workspace
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            Projects
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Projects visible through your current application and membership
            access.
          </p>
        </div>
        {role !== "MEMBER" && (
          <Button asChild>
            <Link href="/projects/new">
              <Plus /> Create project
            </Link>
          </Button>
        )}
      </div>
      <Card className="p-4 sm:p-5">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setHistory([]);
            setCursor(null);
            setAppliedSearch(search.trim());
          }}
          className="grid gap-3 md:grid-cols-[minmax(220px,1fr)_180px_auto]"
        >
          <label className="relative">
            <span className="sr-only">Search projects</span>
            <Search className="pointer-events-none absolute top-3 left-3 size-4 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Project key or name"
              className="h-10 w-full rounded-lg border bg-background pr-3 pl-10 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
          <label>
            <span className="sr-only">Project status</span>
            <select
              value={status}
              onChange={(event) =>
                setStatus(event.target.value as ProjectStatus | "")
              }
              className="h-10 w-full rounded-lg border bg-background px-3 text-sm focus:ring-2 focus:ring-ring"
            >
              <option value="">All statuses</option>
              <option value="DRAFT">Draft</option>
              <option value="ACTIVE">Active</option>
              <option value="ARCHIVED">Archived</option>
            </select>
          </label>
          <Button type="submit">Apply</Button>
        </form>
      </Card>
      {state === "loading" && (
        <Card className="space-y-3 p-5" aria-label="Loading projects">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-16" />
          ))}
        </Card>
      )}
      {state === "error" && (
        <ErrorState
          title="Unable to load projects"
          description="Project management could not be reached."
          onRetry={() => void load()}
        />
      )}
      {state === "ready" && items.length === 0 && (
        <Card>
          <EmptyState
            title="No projects found"
            description="Adjust the filters or create the first accessible project."
          />
        </Card>
      )}
      {state === "ready" && items.length > 0 && (
        <Card className="overflow-hidden">
          <div className="divide-y">
            {items.map((project) => (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className="grid gap-2 p-4 hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-primary sm:grid-cols-[auto_1fr_auto] sm:items-center"
              >
                <Badge>{project.key}</Badge>
                <div>
                  <p className="font-medium">{project.name}</p>
                  <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
                    {project.description || "No description"}
                  </p>
                </div>
                <Badge
                  tone={project.status === "ACTIVE" ? "success" : "neutral"}
                >
                  {project.status}
                </Badge>
              </Link>
            ))}
          </div>
          <div className="flex items-center justify-between border-t p-4">
            <Button
              variant="outline"
              disabled={!history.length}
              onClick={() => {
                const previous = history.at(-1) ?? null;
                setHistory((current) => current.slice(0, -1));
                setCursor(previous);
              }}
            >
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              Up to {PAGE_SIZE} projects
            </span>
            <Button
              variant="outline"
              disabled={!pageInfo.hasNextPage || !pageInfo.endCursor}
              onClick={() => {
                setHistory((current) => [...current, cursor]);
                setCursor(pageInfo.endCursor);
              }}
            >
              Next
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
