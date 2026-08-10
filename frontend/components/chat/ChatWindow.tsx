"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  referencedTopicName?: string | null;
}

interface DoubtResponse {
  session_id: string;
  answer: string;
  referenced_topic_id: string | null;
  referenced_topic_name: string | null;
}

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "placeholder-1",
      role: "assistant",
      content:
        "Ask me anything about your syllabus once your notes are uploaded and processed.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/chat/ask`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message: trimmed,
        }),
      });

      if (!res.ok) {
        let detail = "Something went wrong. Please try again.";
        try {
          const body = await res.json();
          if (body.detail) detail = body.detail;
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }

      const data: DoubtResponse = await res.json();
      setSessionId(data.session_id);

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.answer,
          referencedTopicName: data.referenced_topic_name,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get an answer.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[70vh] flex-col rounded-lg border border-gray-200 bg-white">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? "ml-auto max-w-[80%]" : "max-w-[80%]"}>
            <div
              className={`rounded-lg px-4 py-2 text-sm ${
                m.role === "user"
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {m.content}
            </div>
            {m.referencedTopicName && (
              <p className="mt-1 text-xs text-gray-400">
                Based on: {m.referencedTopicName}
              </p>
            )}
          </div>
        ))}
        {loading && (
          <div className="max-w-[80%] rounded-lg bg-gray-100 px-4 py-2 text-sm text-gray-400">
            Thinking...
          </div>
        )}
      </div>

      {error && (
        <p className="border-t border-red-100 bg-red-50 px-4 py-2 text-sm text-red-600">
          {error}
        </p>
      )}

      <form
        onSubmit={handleSend}
        className="flex gap-2 border-t border-gray-200 p-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a doubt about your syllabus..."
          disabled={loading}
          className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-800 disabled:opacity-50"
        >
          {loading ? "..." : "Send"}
        </button>
      </form>
    </div>
  );
}