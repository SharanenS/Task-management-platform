import { NextRequest, NextResponse } from "next/server";
import { getValidAccessToken } from "@/lib/oidc";

async function proxyRequest(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const token = await getValidAccessToken();
  if (!token) {
    return NextResponse.json(
      { detail: "Authentication required" },
      { status: 401 }
    );
  }

  const { path } = await context.params;
  const pathStr = path.join("/");

  const backendBaseUrl =
    process.env.BACKEND_URL || "http://localhost:8000";
  const search = request.nextUrl.search;
  const targetUrl = `${backendBaseUrl.replace(/\/$/, "")}/${pathStr}${search}`;

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${token}`);

  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  const accept = request.headers.get("accept");
  if (accept) {
    headers.set("accept", accept);
  }

  const method = request.method;
  let body: BodyInit | undefined = undefined;

  if (method !== "GET" && method !== "HEAD") {
    const text = await request.text();
    if (text) {
      body = text;
    }
  }

  try {
    const backendResponse = await fetch(targetUrl, {
      method,
      headers,
      body,
    });

    const responseHeaders = new Headers();
    const respContentType = backendResponse.headers.get("content-type");
    if (respContentType) {
      responseHeaders.set("content-type", respContentType);
    }

    const responseBody = await backendResponse.arrayBuffer();

    return new NextResponse(responseBody, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error(`Backend proxy error calling ${targetUrl}:`, error);
    return NextResponse.json(
      { detail: "Backend service unreachable" },
      { status: 502 }
    );
  }
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}
