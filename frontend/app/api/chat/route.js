import { NextResponse } from "next/server";
import { API_BASE } from "@/lib/api";
import { CHAT_ENDPOINT } from "@/lib/chatApi";

/* Same-origin proxy for the chat endpoint, so uploads and JSON both reach
   FastAPI without any CORS configuration. */
export async function POST(request) {
  const contentType = request.headers.get("content-type") || "";
  const isMultipart = contentType.includes("multipart/form-data");

  try {
    const upstream = await fetch(`${API_BASE}${CHAT_ENDPOINT}`, {
      method: "POST",
      headers: isMultipart
        ? { "content-type": contentType }
        : { "content-type": "application/json" },
      body: isMultipart ? await request.arrayBuffer() : await request.text(),
      duplex: "half",
    });

    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") || "application/json",
      },
    });
  } catch (error) {
    return NextResponse.json(
      { detail: `Backend unreachable at ${API_BASE}${CHAT_ENDPOINT}: ${error.message}` },
      { status: 502 }
    );
  }
}
