// frontend/app/api/backend/[...path]/route.js
//
// One same-origin proxy for the entire FastAPI surface. Everything the browser
// needs — chat, project state, jobs, compliance, uploads, binary assets — goes
// through here. Consequences of doing it this way:
//   - CORS never applies, in dev or on Render, because the browser only ever
//     talks to its own origin.
//   - BACKEND_URL stays server-side. It is not NEXT_PUBLIC_, so it is never
//     inlined into the client bundle.
//   - Swapping local for Render is one env var, no code change.
//
// Request and response bodies are streamed, not buffered, so a 200 MB mp4
// upload or a .wav download does not sit in Node's memory.

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.BACKEND_URL ?? "https://creatorcrew.onrender.com";

// Hop-by-hop and Next-injected headers that must not be forwarded upstream.
const STRIP_REQUEST = new Set([
  "host",
  "connection",
  "content-length",
  "transfer-encoding",
  "accept-encoding",
  "x-forwarded-host",
  "x-forwarded-proto",
]);

// Headers worth passing back so <img>, <audio> and download links behave.
const KEEP_RESPONSE = [
  "content-type",
  "content-length",
  "content-disposition",
  "accept-ranges",
  "content-range",
  "cache-control",
  "etag",
];

async function proxy(request, context) {
  const { path = [] } = await context.params;
  const target = `${BACKEND_URL}/${path.join("/")}${request.nextUrl.search}`;

  const headers = new Headers();
  for (const [key, value] of request.headers) {
    if (!STRIP_REQUEST.has(key.toLowerCase())) headers.set(key, value);
  }

  const hasBody = !["GET", "HEAD"].includes(request.method);

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      duplex: hasBody ? "half" : undefined,
      cache: "no-store",
      redirect: "follow", // signed-URL redirects keep working when you move to object storage
    });

    const out = new Headers();
    for (const name of KEEP_RESPONSE) {
      const value = upstream.headers.get(name);
      if (value) out.set(name, value);
    }

    return new Response(upstream.body, { status: upstream.status, headers: out });
  } catch (error) {
    // A dead backend must look like a gateway failure, not a broken frontend.
    return Response.json(
      { detail: `Backend unreachable at ${target}: ${error.message}` },
      { status: 502 }
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;