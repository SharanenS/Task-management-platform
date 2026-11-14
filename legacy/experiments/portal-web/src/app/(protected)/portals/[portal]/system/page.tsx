import type { Metadata } from "next";
import { SystemPanel } from "@/features/system/system-panel";
export const metadata: Metadata = { title: "System status" };
export default function SystemPage() {
  return <SystemPanel />;
}
