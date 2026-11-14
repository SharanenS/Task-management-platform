import { Skeleton } from "@/components/ui/states";
export default function Loading() {
  return (
    <div role="status" className="space-y-6">
      <span className="sr-only">Loading page</span>
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-5 w-96 max-w-full" />
      <div className="grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    </div>
  );
}
