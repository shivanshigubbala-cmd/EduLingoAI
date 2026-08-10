"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter, useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  generateQuiz,
  submitQuizAnswer,
  QuizError,
  type QuizQuestionPublic,
  type QuizAnswerResult,
} from "@/lib/quiz";

type AnsweredEntry = {
  question: QuizQuestionPublic;
  result: QuizAnswerResult;
};

export default function QuizPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const params = useParams<{ documentId: string }>();

  const [questions, setQuestions] = useState<QuizQuestionPublic[] | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [shortAnswerText, setShortAnswerText] = useState("");
  const [answered, setAnswered] = useState<AnsweredEntry[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quizLoadError, setQuizLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (!user || !params.documentId) return;

    generateQuiz(params.documentId)
      .then((res) => setQuestions(res.questions))
      .catch((err) => {
        const message =
          err instanceof QuizError ? err.message : "Failed to generate quiz.";
        setQuizLoadError(message);
      });
  }, [user, params.documentId]);

  if (loading || (!quizLoadError && questions === null)) {
    return <p className="text-sm text-gray-500">Loading quiz…</p>;
  }
  if (!user) return null;

  if (quizLoadError) {
    return (
      <div>
        <h1 className="text-2xl font-semibold">Quiz</h1>
        <p className="mt-2 text-red-600">{quizLoadError}</p>
      </div>
    );
  }

  const allQuestions = questions as QuizQuestionPublic[];
  const isFinished = currentIndex >= allQuestions.length;

  if (isFinished) {
    return <ResultsScreen answered={answered} />;
  }

  const currentQuestion = allQuestions[currentIndex];

  async function handleSubmit() {
    const answerText =
      currentQuestion.question_type === "mcq" ? selectedOption : shortAnswerText;

    if (!answerText) {
      setError("Please provide an answer before continuing.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const result = await submitQuizAnswer(currentQuestion.id, answerText);
      setAnswered((prev) => [...prev, { question: currentQuestion, result }]);
      setSelectedOption(null);
      setShortAnswerText("");
      setCurrentIndex((i) => i + 1);
    } catch (err) {
      const message =
        err instanceof QuizError ? err.message : "Failed to submit answer.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Quiz</h1>
        <p className="text-sm text-gray-500">
          Question {currentIndex + 1} of {allQuestions.length}
        </p>
      </div>

      <p className="mt-1 text-sm text-gray-500">{currentQuestion.topic_name}</p>

      <div className="mt-6 rounded-lg border border-gray-200 p-6">
        <p className="text-lg">{currentQuestion.question_text}</p>

        {currentQuestion.question_type === "mcq" && currentQuestion.options && (
          <div className="mt-4 flex flex-col gap-2">
            {currentQuestion.options.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setSelectedOption(option)}
                className={`rounded-md border px-4 py-2 text-left ${
                  selectedOption === option
                    ? "border-blue-600 bg-blue-50"
                    : "border-gray-300"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        )}

        {currentQuestion.question_type === "short_answer" && (
          <textarea
            className="mt-4 w-full rounded-md border border-gray-300 p-3"
            rows={4}
            value={shortAnswerText}
            onChange={(e) => setShortAnswerText(e.target.value)}
            placeholder="Type your answer…"
          />
        )}

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting}
          className="mt-6 rounded-md bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting
            ? "Submitting…"
            : currentIndex === allQuestions.length - 1
              ? "Finish quiz"
              : "Next question"}
        </button>
      </div>
    </div>
  );
}

function ResultsScreen({ answered }: { answered: AnsweredEntry[] }) {
  const totalScore = answered.reduce((sum, a) => sum + a.result.score, 0);
  const maxScore = answered.length;

  return (
    <div>
      <h1 className="text-2xl font-semibold">Quiz results</h1>
      <p className="mt-2 text-gray-600">
        Score: {totalScore.toFixed(1)} / {maxScore}
      </p>

      <div className="mt-6 flex flex-col gap-4">
        {answered.map(({ question, result }) => (
          <div
            key={result.quiz_result_id}
            className={`rounded-lg border p-4 ${
              result.is_correct === false
                ? "border-red-200 bg-red-50"
                : result.is_correct === true
                  ? "border-green-200 bg-green-50"
                  : "border-gray-200"
            }`}
          >
            <p className="text-sm text-gray-500">{question.topic_name}</p>
            <p className="mt-1 font-medium">{question.question_text}</p>
            <p className="mt-2 text-sm">
              Score: {result.score}
              {result.is_correct !== null &&
                (result.is_correct ? " · Correct" : " · Incorrect")}
            </p>
            <p className="mt-1 text-sm text-gray-600">{result.rationale}</p>
          </div>
        ))}
      </div>
    </div>
  );
}