/** Client for the P5-SHR7 grounded doubt-answering endpoint. */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface DoubtResponse {
  session_id: string;
  answer: string;
  referenced_topic_id: string | null;
  referenced_topic_name: string | null;
}

export class ChatError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function askDoubt(message: string, sessionId: string | null): Promise<DoubtResponse> {
  const response = await fetch(`${API_BASE}/chat/ask`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) {
    let detail = "Couldn't get an answer. Please try again.";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Keep the user-facing fallback for a malformed error response.
    }
    throw new ChatError(detail, response.status);
  }

  return response.json();
}
