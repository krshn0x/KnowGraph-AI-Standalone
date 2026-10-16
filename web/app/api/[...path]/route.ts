import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 90;

const allowed = new Set(["health", "entities", "incidents", "experts", "documents", "graph", "ask", "ingest", "settings"]);

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (!allowed.has(path[0]) || path.some(p => p === "." || p === "..")) {
    return NextResponse.json({ detail: "Unknown API endpoint." }, { status: 404 });
  }
  const base = process.env.API_BASE_URL || "http://127.0.0.1:8000";
  const target = new URL(path.map(encodeURIComponent).join("/"), base.replace(/\/$/, "") + "/");
  target.search = request.nextUrl.search;
  try {
    const headers = new Headers();
    const contentType = request.headers.get("content-type");
    if (contentType) headers.set("content-type", contentType);
    let body: ArrayBuffer | undefined;
    if (request.method === "POST") {
      if (Number(request.headers.get("content-length") || 0) > 9 * 1024 * 1024) {
        return NextResponse.json({ detail: "Upload exceeds the 8 MiB file limit." }, { status: 413 });
      }
      body = await request.arrayBuffer();
      if (body.byteLength > 9 * 1024 * 1024) {
        return NextResponse.json({ detail: "Upload exceeds the 8 MiB file limit." }, { status: 413 });
      }
    }
    const response = await fetch(target, {
      method: request.method, headers, body, cache: "no-store", signal: AbortSignal.timeout(75000),
    });
    return new NextResponse(response.body, { status: response.status, headers: {
      "content-type": response.headers.get("content-type") || "application/json",
      "cache-control": "no-store",
    } });
  } catch {
    return NextResponse.json({ detail: "The knowledge service is unavailable. Check that the API and FalkorDB are running, then retry." }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;
