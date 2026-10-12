import Link from "next/link";
import { EmptyState } from "@/components/ui/states";
import { Button } from "@/components/ui/button";
export default function NotFound() {
  return (
    <div className="py-16 text-center">
      <EmptyState
        title="This page is not here"
        description="Return to the overview to explore the Phase 1 foundation."
      />
      <Button asChild>
        <Link href="/">Back to overview</Link>
      </Button>
    </div>
  );
}
