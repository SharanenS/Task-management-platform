"use client";
import { useQuery } from "@tanstack/react-query";
import { SystemInfoDocument } from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";
export function useSystemInfo() {
  return useQuery({
    queryKey: ["systemInfo"],
    queryFn: ({ signal }) =>
      requestGraphQL(SystemInfoDocument, undefined, signal),
    refetchInterval: 15_000,
  });
}
