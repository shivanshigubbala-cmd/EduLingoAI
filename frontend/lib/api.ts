import { Suggestion } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getSuggestions(): Promise<Suggestion[]> {
  try {
    const res = await fetch(`${API_BASE}/feedback/suggestions`, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });

    if (!res.ok) {
      return [];
    }

    const data = await res.json();
    if (!Array.isArray(data)) {
      return [];
    }

    return data.map((item: Suggestion) => ({
      ...item,
      title:
        item.title ??
        (item.trigger === "quiz" ? "Quiz Review" : "Study Check-in"),
      seen: item.seen ?? false,
    }));
  } catch {
    return [];
  }
}

export async function dismissSuggestion(id: string): Promise<void> {
  try {
    await fetch(`${API_BASE}/feedback/suggestions/${id}/dismiss`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    // Ignore error per contract spec
  }
}
