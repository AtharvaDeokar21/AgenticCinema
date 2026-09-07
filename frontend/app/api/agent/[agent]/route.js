import { NextResponse } from "next/server";
import { API_BASE, ENDPOINTS } from "@/lib/api";

/* Same-origin proxy to the FastAPI backend, so the browser never makes a
   cross-origin request and you do not have to configure CORS. Streams both
   JSON and multipart bodies straight through. */
export async function POST(request, { params }) {
  const { agent } = await params;
  const path = ENDPOINTS[agent];

  if (!path) {
    return NextResponse.json(
      { detail: `Unknown agent '${agent}'.` },
      { status: 404 }
    );
  }

  const contentType = request.headers.get("content-type") || "";
  const isMultipart = contentType.includes("multipart/form-data");

  try {
    const upstream = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      /* For multipart, hand the raw body over untouched and let fetch keep
         the original boundary header. */
      headers: isMultipart ? { "content-type": contentType } : { "content-type": "application/json" },
      body: isMultipart ? await request.arrayBuffer() : await request.text(),
      duplex: "half",
    });

    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") || "application/json" },
    });
  } catch (error) {
    return NextResponse.json(
      { detail: `Backend unreachable at ${API_BASE}${path}: ${error.message}` },
      { status: 502 }
    );
  }
}
