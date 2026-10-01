import { NextResponse } from "next/server";

export const runtime = "nodejs";

/**
 * Thin proxy to the FastAPI backend.
 *
 * It exists so the browser only ever talks to its own origin (no CORS setup,
 * no backend URL leaked to the client) and so the same code works on Vercel
 * where the backend is deployed separately.
 */
export async function POST(request: Request) {
  const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: { code: "invalid_request", message: "Please check your message and try again." } },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(`${backendUrl.replace(/\/$/, "")}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await response.text();
    return new Response(data, {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "backend_unreachable",
          message: "The assistant service is unavailable right now. Please try again shortly.",
        },
      },
      { status: 502 },
    );
  }
}