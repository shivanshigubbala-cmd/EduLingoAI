/**
 * Quiz API client — thin wrappers around backend quiz endpoints.
 *
 * Expected backend endpoints:
 *   POST /documents/{document_id}/quiz?max_questions=N
 *     → 200 { quiz_id, questions: [{ id, topic_id, topic_name, question_type, question_text, options }] }
 *   POST /quiz/{quiz_result_id}/answer   { answer_text }
 *     → 200 { quiz_result_id, is_correct, score, rationale }
 *
 * P6-SRE11. Depends on P6-SHR8 (generation) / P6-SHR9 (grading).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class QuizError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "QuizError";
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
    throw new QuizError(message, res.status);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export type QuestionType = "mcq" | "short_answer";

export interface QuizQuestionPublic {
  id: string;
  topic_id: string;
  topic_name: string;
  question_type: QuestionType;
  question_text: string;
  options: string[] | null;
}

export interface QuizResponse {
  quiz_id: string;
  questions: QuizQuestionPublic[];
}

export interface QuizAnswerResult {
  quiz_result_id: string;
  is_correct: boolean | null;
  score: number;
  rationale: string;
}

export interface TopicScoreBreakdown {
  topic_id: string;
  topic_name: string;
  questions_total: number;
  questions_answered: number;
  average_score: number | null;
  is_weak: boolean;
}

export interface QuizScoreAnalysis {
  quiz_id: string;
  total_questions: number;
  graded_questions: number;
  average_score: number | null;
  weak_threshold: number;
  topics: TopicScoreBreakdown[];
}

export async function generateQuiz(
  documentId: string,
  maxQuestions = 10,
): Promise<QuizResponse> {
  return request<QuizResponse>(
    `/documents/${documentId}/quiz?max_questions=${maxQuestions}`,
    { method: "POST" },
  );
}

export async function submitQuizAnswer(
  quizResultId: string,
  answerText: string,
): Promise<QuizAnswerResult> {
  return request<QuizAnswerResult>(`/quiz/${quizResultId}/answer`, {
    method: "POST",
    body: JSON.stringify({ answer_text: answerText }),
  });
}

export async function getQuizAnalysis(quizId: string): Promise<QuizScoreAnalysis> {
  return request<QuizScoreAnalysis>(`/quiz/${quizId}/analysis`);
}

export { QuizError };
