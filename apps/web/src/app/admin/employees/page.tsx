import { PeopleWorkspace } from "@/portals/admin/organization";
export default async function Employees({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; search?: string; notice?: string }>;
}) {
  return <PeopleWorkspace employees params={await searchParams} />;
}
