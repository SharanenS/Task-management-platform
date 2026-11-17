import { NextRequest } from "next/server";
import { beginLogin } from "@/shared/auth/start-login";
export async function POST(request: NextRequest) {
  return beginLogin(request);
}
