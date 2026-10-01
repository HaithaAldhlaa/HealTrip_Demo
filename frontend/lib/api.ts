/** API types (mirror backend/schemas.py) and the fetch helper. */

export type Language = "en" | "ar";

export type Provider = {
  type: "doctor" | "hospital";
  id: string;
  name: string;
  name_ar?: string | null;
  city: string;
  specialties: string[];
  hospital?: string | null;
  hospital_address?: string | null;
  emergency_available?: boolean | null;
  languages: string[];
};

export type ToolTrace = {
  name: string;
  arguments: Record<string, unknown>;
  result_count: number;
};

export type ChatTurn = {
  role: "user" | "assistant";
  content: string;
};

export type ChatResponse = {
  reply: string;
  language: Language;
  urgent: boolean;
  grounded: boolean;
  providers: Provider[];
  tools_used: ToolTrace[];
  safety_notice?: string | null;
};

export type ChatApiError = {
  code: string;
  message: string;
};

/**
 * Calls the Next.js route handler, which forwards to the FastAPI backend.
 * The backend URL is server-side only (BACKEND_URL is never sent here).
 */
export async function sendChat(
  message: string,
  language: Language,
  history: ChatTurn[],
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, language, history }),
    signal,
  });

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const error = (payload as { error?: ChatApiError } | null)?.error;
    throw new Error(error?.message ?? "Something went wrong. Please try again.");
  }

  return payload as ChatResponse;
}