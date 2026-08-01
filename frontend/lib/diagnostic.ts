/**
 * Diagnostic API client — thin wrappers around backend diagnostic endpoints.
 *
 * Expected backend endpoints:
 *   POST /documents/{document_id}/diagnostic          → 200 DiagnosticSessionResponse
 *   POST /diagnostic/sessions/{session_id}/answers     → 200 AnswerResult
 *
 * Follows the same request() pattern as lib/auth.ts — httpOnly cookie auth,
 * credentials included automatically.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type QuestionType = "mcq" | "short_answer";

export interface DiagnosticQuestion {
  id: string;
  topic_id: string | null;
  topic_name: string;
  question_type: QuestionType;
  question_text: string;
  options: string[] | null;
}

export interface DiagnosticSession {
  session_id: string;
  questions: DiagnosticQuestion[];
}

export interface AnswerResult {
  is_correct: boolean;
  next_question: DiagnosticQuestion | null;
  session_complete: boolean;
  answered_topic_id: string | null;
}

class DiagnosticError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "DiagnosticError";
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const body = await res.json();
      if (body.detail) message = body.detail;
    } catch {
      /* ignore parse errors */
    }
    throw new DiagnosticError(message, res.status);
  }

  return res.json();
}

/** Start a diagnostic session for a document; returns the full capped question set. */
export async function startDiagnostic(documentId: string) {
  return request<DiagnosticSession>(`/documents/${documentId}/diagnostic`, {
    method: "POST",
  });
}

/** Submit an answer; returns whether it was correct and the adaptively-chosen next question. */
export async function submitAnswer(
  sessionId: string,
  questionId: string,
  answerText: string,
) {
  return request<AnswerResult>(`/diagnostic/sessions/${sessionId}/answers`, {
    method: "POST",
    body: JSON.stringify({ question_id: questionId, answer_text: answerText }),
  });
}

export { DiagnosticError };