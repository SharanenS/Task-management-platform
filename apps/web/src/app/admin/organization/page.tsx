import { PeopleWorkspace } from "@/portals/admin/organization";
export default async function Organization({
  searchParams,
}: {
  searchParams: Promise<{ notice?: string }>;
}) {
  return <PeopleWorkspace employees={false} params={await searchParams} />;
}
