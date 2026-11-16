import { redirect } from "next/navigation";
import { authConfig } from "@/shared/auth/config";
import { sessionCookie } from "@/shared/auth/session";
export const dynamic = "force-dynamic";
export default async function Home() {
  const path = (await sessionCookie()) ? "/auth/ready" : "/sign-in";
  redirect(new URL(path, authConfig().origin).href);
}
