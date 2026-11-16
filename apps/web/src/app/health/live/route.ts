import { NextResponse } from "next/server";
export const dynamic = "force-dynamic";
export function GET() {
  return NextResponse.json(
    { status: "up" },
    { headers: { "Cache-Control": "no-store" } },
  );
}
