"use client";

/**
 * Study schedule UI — P4-SHR6.
 *
 * Shows the student's daily study plan and lets them manually reorder or
 * reschedule a topic. Now wired to the real backend (P4-SHI7 scheduling
 * algorithm, P4-SHI8 versioned persistence) — previously used local mock
 * data since neither existed yet.
 *
 * The real API persists schedules as immutable versions (POST /schedules
 * creates a new version rather than editing in place). So a manual reorder
 * updates local state immediately for a responsive feel, and "Save changes"
 * persists that new order as a fresh version via the real endpoint.
 *
 * Acceptance criteria (WBS P4-SHR6):
 *   "Student can view the plan by day/week and manually reorder or
 *   reschedule a topic."
 */
import { useEffect, useState } from "react";
import {
  getCurrentSchedule,
  createSchedule,
  ScheduleError,
  type ScheduleDay,
  type TopicPlanItem,
} from "@/lib/schedule";

function masteryColor(mastery: number): string {
  if (mastery < 0.35) return "border-red-300 bg-red-50";
  if (mastery < 0.6) return "border-yellow-300 bg-yellow-50";
  return "border-green-300 bg-green-50";
}

export default function ScheduleView() {
  const [days, setDays] = useState<ScheduleDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const schedule = await getCurrentSchedule();
        if (!cancelled) setDays(schedule.plan.days);
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ScheduleError && err.status === 404) {
            setError(
              "You don't have a study schedule yet — complete a diagnostic first to generate one.",
            );
          } else {
            setError(
              err instanceof ScheduleError
                ? err.message
                : "Couldn't load your schedule. Please try again.",
            );
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  function handleReorderWithinDay(dayIndex: number, topicId: string, direction: "up" | "down") {
    setDays((prev) => {
      const next = prev.map((d) => ({ ...d, topics: [...d.topics] }));
      const topics = next[dayIndex].topics;
      const i = topics.findIndex((t) => t.id === topicId);
      const swapWith = direction === "up" ? i - 1 : i + 1;
      if (i === -1 || swapWith < 0 || swapWith >= topics.length) return prev;

      [topics[i], topics[swapWith]] = [topics[swapWith], topics[i]];
      return next;
    });
    setHasUnsavedChanges(true);
  }

  function handleMove(fromDayIndex: number, topicId: string, toDayIndex: number) {
    setDays((prev) => {
      const next = prev.map((d) => ({ ...d, topics: [...d.topics] }));
      const topicIndex = next[fromDayIndex].topics.findIndex((t) => t.id === topicId);
      if (topicIndex === -1) return prev;

      const [topic] = next[fromDayIndex].topics.splice(topicIndex, 1);
      next[toDayIndex].topics.push(topic);
      return next;
    });
    setHasUnsavedChanges(true);
  }

  /**
   * Persist the reordered plan as a new schedule version via the real
   * backend (POST /schedules). Flattens the current day-by-day order back
   * into a single topic list.
   *
   * NOTE: hours_per_day defaults to 2 since the current schedule response
   * doesn't echo back the original request — TODO(P4-SHI8): expose that so
   * a student's chosen study pace round-trips correctly.
   */
  async function handleSave() {
    setIsSaving(true);
    setError(null);
    try {
      const topics: TopicPlanItem[] = days.flatMap((d) => d.topics);
      const updated = await createSchedule({ topics, hours_per_day: 2 });
      setDays(updated.plan.days);
      setHasUnsavedChanges(false);
    } catch (err) {
      setError(
        err instanceof ScheduleError
          ? err.message
          : "Couldn't save your changes. Please try again.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-gray-500">
        Loading your study plan…
      </div>
    );
  }

  if (error && days.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-gray-600">{error}</div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Your study plan</h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">Weakest topics come first</span>
          {hasUnsavedChanges && (
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="rounded-full bg-indigo-500 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-600 disabled:opacity-50"
            >
              {isSaving ? "Saving…" : "Save changes"}
            </button>
          )}
        </div>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {days.map((day, dayIndex) => (
          <div key={day.label} className="rounded-xl border border-gray-200 p-3">
            <h3 className="mb-3 text-sm font-medium text-gray-700">{day.label}</h3>

            <div className="space-y-2">
              {day.topics.map((topic, topicIndex) => (
                <div
                  key={topic.id}
                  className={`rounded-lg border px-3 py-2 text-sm ${masteryColor(topic.mastery)}`}
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span className="font-medium text-gray-900">{topic.title}</span>
                    <span className="text-xs text-gray-500">
                      {Math.round(topic.mastery * 100)}% mastery
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-1 text-xs">
                    <button
                      onClick={() => handleReorderWithinDay(dayIndex, topic.id, "up")}
                      disabled={topicIndex === 0}
                      className="rounded border border-gray-300 px-2 py-0.5 hover:bg-white disabled:opacity-30"
                    >
                      ↑ Move up
                    </button>
                    <button
                      onClick={() => handleReorderWithinDay(dayIndex, topic.id, "down")}
                      disabled={topicIndex === day.topics.length - 1}
                      className="rounded border border-gray-300 px-2 py-0.5 hover:bg-white disabled:opacity-30"
                    >
                      ↓ Move down
                    </button>
                    {dayIndex > 0 && (
                      <button
                        onClick={() => handleMove(dayIndex, topic.id, dayIndex - 1)}
                        className="rounded border border-gray-300 px-2 py-0.5 hover:bg-white"
                      >
                        ← {days[dayIndex - 1].label.split(",")[0]}
                      </button>
                    )}
                    {dayIndex < days.length - 1 && (
                      <button
                        onClick={() => handleMove(dayIndex, topic.id, dayIndex + 1)}
                        className="rounded border border-gray-300 px-2 py-0.5 hover:bg-white"
                      >
                        {days[dayIndex + 1].label.split(",")[0]} →
                      </button>
                    )}
                  </div>
                </div>
              ))}

              {day.topics.length === 0 && (
                <p className="text-xs text-gray-400">No topics scheduled.</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}