"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { askDoubt, ChatError } from "@/lib/chat";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  topicName?: string | null;
};

const RESPONSE_CHUNK_SIZE = 12;

export default function StudyChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [isResponding, setIsResponding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isResponding]);

  async function revealAnswer(messageId: string, answer: string) {
    // P5-SHR7 currently returns JSON rather than an HTTP stream. Reveal its
    // complete response progressively so the UI remains conversational until a
    // server-side streaming contract is introduced.
    for (let end = RESPONSE_CHUNK_SIZE; end < answer.length + RESPONSE_CHUNK_SIZE; end += RESPONSE_CHUNK_SIZE) {
      if (!mountedRef.current) return;
      const content = answer.slice(0, end);
      setMessages((current) =>
        current.map((item) => (item.id === messageId ? { ...item, content } : item)),
      );
      await new Promise((resolve) => window.setTimeout(resolve, 14));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isResponding) return;

    const userMessage: ChatMessage = {
      id: `user-${crypto.randomUUID()}`,
      role: "user",
      content: message,
    };
    setMessages((current) => [...current, userMessage]);
    setDraft("");
    setError(null);
    setIsResponding(true);

    try {
      const result = await askDoubt(message, sessionId);
      if (!mountedRef.current) return;

      setSessionId(result.session_id);
      const assistantId = `assistant-${crypto.randomUUID()}`;
      setMessages((current) => [
        ...current,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          topicName: result.referenced_topic_name,
        },
      ]);
      await revealAnswer(assistantId, result.answer);
    } catch (caught) {
      if (mountedRef.current) {
        setError(
          caught instanceof ChatError ? caught.message : "Couldn't get an answer. Please try again.",
        );
      }
    } finally {
      if (mountedRef.current) setIsResponding(false);
    }
  }

  function startNewChat() {
    if (isResponding) return;
    setMessages([]);
    setSessionId(null);
    setError(null);
    setDraft("");
  }

  const history = messages.filter((message) => message.content);

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_13rem]">
      <section className="flex min-h-[34rem] flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <header className="flex items-start justify-between gap-4 border-b border-gray-100 px-5 py-4">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Study chat</h1>
            <p className="mt-1 text-sm text-gray-600">Ask about the material in your syllabus.</p>
          </div>
          <button
            type="button"
            onClick={startNewChat}
            disabled={isResponding || messages.length === 0}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            New chat
          </button>
        </header>

        <div ref={scrollRef} aria-live="polite" className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
          {messages.length === 0 ? (
            <div className="flex h-full min-h-64 items-center justify-center text-center text-sm text-gray-500">
              Ask a question to get a syllabus-grounded explanation.
            </div>
          ) : (
            messages.map((message) => (
              <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                    message.role === "user"
                      ? "bg-indigo-600 text-white"
                      : "bg-gray-100 text-gray-900"
                  }`}
                >
                  {message.content || <span className="text-gray-500">Thinking…</span>}
                  {message.role === "assistant" && message.topicName && message.content && (
                    <p className="mt-2 border-t border-gray-200 pt-2 text-xs font-medium text-indigo-700">
                      Based on: {message.topicName}
                    </p>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {error && <p className="border-t border-red-100 bg-red-50 px-5 py-3 text-sm text-red-700">{error}</p>}

        <form onSubmit={handleSubmit} className="flex gap-2 border-t border-gray-100 p-4">
          <label htmlFor="chat-message" className="sr-only">Your question</label>
          <input
            id="chat-message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={isResponding}
            placeholder="Ask about a topic…"
            className="min-w-0 flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-gray-50"
          />
          <button
            type="submit"
            disabled={isResponding || !draft.trim()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </section>

      <aside className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-900">This chat</h2>
        <p className="mt-1 text-xs text-gray-500">Current session history</p>
        <ol className="mt-4 space-y-3">
          {history.length === 0 ? (
            <li className="text-sm text-gray-500">No messages yet.</li>
          ) : (
            history.map((message) => (
              <li key={message.id} className="text-sm text-gray-700">
                <span className="block text-xs font-medium text-gray-500">
                  {message.role === "user" ? "You" : "Assistant"}
                </span>
                <span className="line-clamp-2">{message.content}</span>
              </li>
            ))
          )}
        </ol>
      </aside>
    </div>
  );
}
