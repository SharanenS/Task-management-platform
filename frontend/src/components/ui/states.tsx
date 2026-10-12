import { AlertCircle, Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-md bg-muted", className)}
    />
  );
}
export function EmptyState({
  title = "Nothing here yet",
  description = "New activity will appear here when it is available.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-4 rounded-xl border bg-background p-3">
        <Inbox className="size-5 text-muted-foreground" />
      </div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
        {description}
      </p>
    </div>
  );
}
export function ErrorState({
  title = "Unable to connect",
  description = "Please try again in a moment.",
  onRetry,
  pending = false,
}: {
  title?: string;
  description?: string;
  onRetry: () => void;
  pending?: boolean;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-5"
    >
      <AlertCircle className="size-5 text-amber-800" />
      <div>
        <h3 className="text-sm font-semibold text-amber-950">{title}</h3>
        <p className="mt-1 text-sm leading-6 text-amber-900">{description}</p>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry} disabled={pending}>
        {pending ? "Checking…" : "Try again"}
      </Button>
    </div>
  );
}
