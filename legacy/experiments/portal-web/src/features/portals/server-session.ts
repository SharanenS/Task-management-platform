import { cache } from "react";
import { redirect } from "next/navigation";
import { getSession } from "@/auth/session";
import { fetchEmployeeProfile, ProfileAccessDeniedError } from "@/auth/gateway";

export const requirePortalSession = cache(async () => {
  const session = await getSession();
  if (!session) redirect("/session-expired");
  try {
    const employee = await fetchEmployeeProfile(session.record.accessToken);
    return { ...session, record: { ...session.record, employee } };
  } catch (error) {
    if (error instanceof ProfileAccessDeniedError) redirect("/access-denied");
    throw new Error(
      "Your workspace is temporarily unavailable. Please try again.",
    );
  }
});
