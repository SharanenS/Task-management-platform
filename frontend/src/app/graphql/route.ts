import { NextRequest, NextResponse } from "next/server";

import { authConfig } from "@/auth/config";
import { getSession } from "@/auth/session";

export async function POST(request: NextRequest) {
  const session = await getSession();
  try {
    const upstream = await fetch(`${authConfig.gatewayUrl}/graphql`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(session
          ? { Authorization: `Bearer ${session.record.accessToken}` }
          : {}),
      },
      body: await request.text(),
      cache: "no-store",
      signal: AbortSignal.timeout(8_000),
    });
    return new NextResponse(await upstream.text(), {
      status: upstream.status,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      { errors: [{ message: "The gateway is temporarily unavailable." }] },
      { status: 502 },
    );
  }
}
