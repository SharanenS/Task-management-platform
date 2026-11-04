"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import {
  MarkAllNotificationsReadDocument,
  MarkNotificationReadDocument,
  NotificationsDocument,
  type NotificationsQuery,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

export function NotificationCenter() {
  const [data, setData] = useState<NotificationsQuery | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [cursor, setCursor] = useState<string | null>(null);
  const [history, setHistory] = useState<Array<string | null>>([]);
  const load = useCallback(async () => {
    setState("loading");
    try {
      setData(
        await requestGraphQL(NotificationsDocument, {
          first: 20,
          after: cursor,
          unreadOnly,
        }),
      );
      setState("ready");
    } catch {
      setState("error");
    }
  }, [cursor, unreadOnly]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);
  const markOne = async (id: string) => {
    await requestGraphQL(MarkNotificationReadDocument, { id });
    await load();
  };
  const markAll = async () => {
    await requestGraphQL(MarkAllNotificationsReadDocument);
    await load();
  };
  const relatedLink = (
    item: NotificationsQuery["notifications"]["nodes"][number],
  ) =>
    item.reportId
      ? `/reports/${item.reportId}`
      : item.projectId && item.taskId
        ? `/projects/${item.projectId}/tasks/${item.taskId}`
        : item.projectId
          ? `/projects/${item.projectId}`
          : null;
  return (
    <div className="space-y-6">
      <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold tracking-widest text-primary uppercase">
            Notifications
          </p>
          <h1 className="text-3xl font-semibold">Notification center</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Private updates for your account.
          </p>
        </div>
        <Button
          onClick={() => void markAll()}
          disabled={!data?.unreadNotificationCount}
        >
          Mark all read
        </Button>
      </div>
      <Card className="flex flex-wrap items-center justify-between gap-4 p-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(event) => {
              setUnreadOnly(event.target.checked);
              setCursor(null);
              setHistory([]);
            }}
          />
          Unread only
        </label>
        <Badge>{data?.unreadNotificationCount ?? 0} unread</Badge>
      </Card>
      {state === "loading" && (
        <Card aria-label="Loading notifications" className="space-y-3 p-6">
          <Skeleton className="h-8" />
          <Skeleton className="h-20" />
        </Card>
      )}
      {state === "error" && (
        <ErrorState
          title="Unable to load notifications"
          description="Notifications are temporarily unavailable."
          onRetry={() => void load()}
        />
      )}
      {state === "ready" &&
        data &&
        (data.notifications.nodes.length ? (
          <div className="space-y-3">
            {data.notifications.nodes.map((item) => {
              const href = relatedLink(item);
              return (
                <Card
                  key={item.id}
                  className={`p-4 ${item.readAt ? "opacity-75" : "border-primary/40"}`}
                >
                  <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="min-w-0 break-words font-medium">
                          {item.title}
                        </h2>
                        {!item.readAt && <Badge>Unread</Badge>}
                      </div>
                      <p className="mt-1 break-words text-sm text-muted-foreground [overflow-wrap:anywhere]">
                        {item.message}
                      </p>
                      <p className="mt-2 text-xs text-muted-foreground">
                        {new Date(item.createdAt).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2 sm:shrink-0">
                      {href && (
                        <Button asChild variant="outline">
                          <Link href={href}>Open</Link>
                        </Button>
                      )}
                      {!item.readAt && (
                        <Button
                          variant="outline"
                          onClick={() => void markOne(item.id)}
                        >
                          Mark read
                        </Button>
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                disabled={!history.length}
                onClick={() => {
                  const previous = history.at(-1) ?? null;
                  setHistory((values) => values.slice(0, -1));
                  setCursor(previous);
                }}
              >
                Previous page
              </Button>
              <Button
                variant="outline"
                disabled={!data.notifications.pageInfo.hasNextPage}
                onClick={() => {
                  setHistory((values) => [...values, cursor]);
                  setCursor(data.notifications.pageInfo.endCursor ?? null);
                }}
              >
                Next page
              </Button>
            </div>
          </div>
        ) : (
          <EmptyState
            title="No notifications"
            description="New task assignments and report results will appear here."
          />
        ))}
    </div>
  );
}
