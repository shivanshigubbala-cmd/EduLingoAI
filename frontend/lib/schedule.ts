/**
 * Schedule API client — thin wrappers around backend scheduling endpoints
 * (P4-SHI7 / P4-SHI8, built by Shivanshi).
 *
 * Endpoints:
 *   POST /schedules             → create a new schedule version
 *   GET  /schedules/current     → fetch the current (latest) schedule
 *   GET  /schedules/history     → list all past versions
 *   GET  /schedules/{versionId} → fetch a specific past version
 *
 * Follows the same request() pattern as lib/auth.ts and lib/diagnostic.ts.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface TopicPlanItem {
  id: string;
  title: string;
  mastery: number; // 0-1
  estimated_hours: number;
}

export interface ScheduleDay {
  label: string;
  topics: TopicPlanItem[];
}

export interface SchedulePlan {
  days: ScheduleDay[];
}

export interface ScheduleVersion {
  version_id: string;
  created_at: string;
  plan: SchedulePlan;
}

export interface ScheduleRequest {
  topics: TopicPlanItem[];
  hours_per_day?: number;
  exam_date?: string | null;
}

class ScheduleError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ScheduleError";
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
    throw new ScheduleError(message, res.status);
  }

  return res.json();
}

/** Fetch the student's current (latest) schedule version. */
export async function getCurrentSchedule() {
  return request<ScheduleVersion>("/schedules/current");
}

/** Generate and persist a new schedule version (e.g. after a re-plan). */
export async function createSchedule(payload: ScheduleRequest) {
  return request<ScheduleVersion>("/schedules", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export { ScheduleError };