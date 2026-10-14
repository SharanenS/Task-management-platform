import type { Metadata } from "next";
import { ComponentPreview } from "@/features/design-system/component-preview";
export const metadata: Metadata = { title: "Design system" };
export default function DesignSystemPage() {
  return <ComponentPreview />;
}
