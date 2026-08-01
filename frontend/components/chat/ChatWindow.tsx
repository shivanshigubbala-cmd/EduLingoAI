"use client";

/**
 * Diagnostic chat UI — P3-SHR5.
 *
 * Renders the adaptive diagnostic as a chat conversation: each question
 * appears as an assistant message, the student answers inline (MCQ buttons
 * or free-text for short answer), and the next adaptively-selected question
 * streams in as a new message. A progress indicator tracks how far through
 * the capped question set the student is.
 *
 * Acceptance criteria (WBS P3-SHR5):
 *   "Questions render as chat messages; answers submit inline with a
 *   progress indicator."
 */
import { useEffect, useRef, useState } from "react";
import {
  startDiagnostic,
  submitAnswer,
  DiagnosticError,
  type DiagnosticQuestion,
  type AnswerResult,
} from "@/lib/diagnostic";

interface ChatMessage {
  id: string;
  role: "assistant" | "student";
  content: string;
  question?: DiagnosticQuestion;
  isCorrect?: boolean;
}

interface ChatWindowProps {
  documentId: string;
}

export default function ChatWindow({ documentId }: ChatWindowProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState<DiagnosticQuestion | null>(null);
  const [textAnswer, setTextAnswer] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const session = await startDiagnostic(documentId);
        if (cancelled) return;

        setSessionId(session.session_id);
        setTotalQuestions(session.questions.length);

        const firstQuestion = session.questions[0] ?? null;
        setCurrentQuestion(firstQuestion);

        if (firstQuestion) {
          setMessages([
            {
              id: firstQuestion.id,
              role: "assistant",
              content: firstQuestion.question_text,
              question: firstQuestion,
            },
          ]);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof DiagnosticError
              ? err.message
              : "Couldn't start the diagnostic. Please try again.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    init();
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function handleAnswer(answerText: string) {
    if (!sessionId || !currentQuestion || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    setMessages((prev) => [
      ...prev,
      { id: `answer-${currentQuestion.id}`, role: "student", content: answerText },
    ]);

    try {
      const result: AnswerResult = await submitAnswer(sessionId, currentQuestion.id, answerText);

      setAnsweredCount((n) => n + 1);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === `answer-${currentQuestion.id}` ? { ...m, isCorrect: result.is_correct } : m,
        ),
      );

      if (result.session_complete || !result.next_question) {
        setIsComplete(true);
        setCurrentQuestion(null);
      } else {
        setCurrentQuestion(result.next_question);
        setMessages((prev) => [
          ...prev,
          {
            id: result.next_question!.id,
            role: "assistant",
            content: result.next_question!.question_text,
            question: result.next_question!,
          },
        ]);
      }
    } catch (err) {
      setError(
        err instanceof DiagnosticError
          ? err.message
          : "Couldn't submit that answer. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
      setTextAnswer("");
    }
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-500">
        Preparing your diagnostic…
      </div>
    );
  }

  if (error && messages.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-red-600">{error}</div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-gray-200 px-4 py-3">
        <div className="mb-1 flex justify-between text-xs text-gray-500">
          <span>
            {isComplete
              ? "Diagnostic complete"
              : `Question ${Math.min(answeredCount + 1, totalQuestions)} of ${totalQuestions}`}
          </span>
          <span>{totalQuestions > 0 ? Math.round((answeredCount / totalQuestions) * 100) : 0}%</span>
        </div>
        <div className="h-2 w-full rounded-full bg-gray-100">
          <div
            className="h-2 rounded-full bg-indigo-500 transition-all"
            style={{
              width: `${totalQuestions > 0 ? (answeredCount / totalQuestions) * 100 : 0}%`,
            }}
          />
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "student" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm ${
                msg.role === "student"
                  ? msg.isCorrect === false
                    ? "bg-red-50 text-red-800"
                    : msg.isCorrect === true
                      ? "bg-green-50 text-green-800"
                      : "bg-indigo-500 text-white"
                  : "bg-gray-100 text-gray-900"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {isComplete && (
          <div className="flex justify-start">
            <div className="max-w-[75%] rounded-2xl bg-gray-100 px-4 py-2 text-sm text-gray-900">
              That&apos;s the diagnostic done — thanks! Your results are being scored.
            </div>
          </div>
        )}
      </div>

      {error && messages.length > 0 && (
        <div className="border-t border-red-100 bg-red-50 px-4 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      {!isComplete && currentQuestion && (
        <div className="border-t border-gray-200 px-4 py-3">
          {currentQuestion.question_type === "mcq" && currentQuestion.options ? (
            <div className="flex flex-wrap gap-2">
              {currentQuestion.options.map((option) => (
                <button
                  key={option}
                  disabled={isSubmitting}
                  onClick={() => handleAnswer(option)}
                  className="rounded-full border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
                >
                  {option}
                </button>
              ))}
            </div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (textAnswer.trim()) handleAnswer(textAnswer.trim());
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={textAnswer}
                onChange={(e) => setTextAnswer(e.target.value)}
                disabled={isSubmitting}
                placeholder="Type your answer…"
                className="flex-1 rounded-full border border-gray-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
              <button
                type="submit"
                disabled={isSubmitting || !textAnswer.trim()}
                className="rounded-full bg-indigo-500 px-5 py-2 text-sm text-white hover:bg-indigo-600 disabled:opacity-50"
              >
                Send
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  );
}