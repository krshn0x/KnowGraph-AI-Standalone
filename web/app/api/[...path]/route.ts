import { NextRequest, NextResponse } from "next/server";
import { request as httpRequest, type IncomingMessage } from "node:http";
import { request as httpsRequest } from "node:https";
import { Readable } from "node:stream";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 930;

const allowed = new Set(["health", "entities", "incidents", "experts", "documents", "graph", "ask", "ingest", "settings"]);

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (!allowed.has(path[0]) || path.some(p => p === "." || p === "..")) {
    return NextResponse.json({ detail: "Unknown API endpoint." }, { status: 404 });
  }
  const base = process.env.API_BASE_URL || "http://127.0.0.1:8000";
  const target = new URL(path.map(encodeURIComponent).join("/"), base.replace(/\/$/, "") + "/");
  target.search = request.nextUrl.search;
  const timeout = AbortSignal.timeout(path[0] === "ask" ? 915000 : 125000);
  const signal = AbortSignal.any([request.signal, timeout]);
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
    // Native HTTP avoids fetch's separate response-header timeout during slow
    // local inference. The explicit absolute deadline also covers the body.
    const response = await new Promise<IncomingMessage>((resolve, reject) => {
      const transport = target.protocol === "https:" ? httpsRequest : httpRequest;
      const upstream = transport(target, { method: request.method, headers: Object.fromEntries(headers), signal }, resolve);
      upstream.on("error", reject);
      upstream.end(body ? Buffer.from(body) : undefined);
    });
    return new NextResponse(Readable.toWeb(response) as ReadableStream<Uint8Array>, { status: response.statusCode || 502, headers: {
      "content-type": response.headers["content-type"] || "application/json",
      "cache-control": "no-store",
    } });
  } catch {
    if (timeout.aborted) {
      return NextResponse.json({ detail: "The knowledge service exceeded the request deadline. Check the Ollama investigation deadline in AI settings and the backend logs." }, { status: 504 });
    }
    return NextResponse.json({ detail: "The knowledge service is unavailable. Check that the API and FalkorDB are running, then retry." }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;
