import { notFound, redirect } from "next/navigation";
import { requirePortalSession } from "@/features/portals/server-session";
import { portalHome } from "@/features/portals/portal-policy";

const sections = new Set([
  "projects",
  "employees",
  "jobs",
  "reports",
  "notifications",
  "operations",
  "system",
  "workflows",
]);

export default async function PreviousBookmark({
  params,
  searchParams,
}: {
  params: Promise<{ legacy: string[] }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { legacy } = await params;
  if (!sections.has(legacy[0]) && legacy[0] !== "design-system") notFound();
  const session = await requirePortalSession();
  const home = portalHome(session.record.employee.role);
  if (legacy[0] === "design-system") redirect(home);
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(await searchParams)) {
    if (Array.isArray(value)) value.forEach((item) => query.append(key, item));
    else if (value !== undefined) query.set(key, value);
  }
  const suffix = query.size ? `?${query}` : "";
  redirect(`${home}/${legacy.map(encodeURIComponent).join("/")}${suffix}`);
}
