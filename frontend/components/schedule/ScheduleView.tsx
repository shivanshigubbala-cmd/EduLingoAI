"use client";

import { useState } from "react";

type ScheduleTopic = {
  id: string;
  title: string;
  mastery: number;
};

type ScheduleDay = {
  label: string;
  topics: ScheduleTopic[];
};

const mockDays: ScheduleDay[] = [
  { label: "Mon", topics: [{ id: "t1", title: "Thermodynamics: Laws", mastery: 35 }, { id: "t2", title: "Cell Division", mastery: 78 }] },
  { label: "Tue", topics: [{ id: "t3", title: "Integration by Parts", mastery: 42 }] },
  { label: "Wed", topics: [{ id: "t4", title: "Newton''s Laws", mastery: 60 }, { id: "t5", title: "Genetics: Mendel", mastery: 20 }] },
];

export default function ScheduleView() {
  const [days, setDays] = useState<ScheduleDay[]>(mockDays);

  function moveTopic(dayIdx: number, topicIdx: number, direction: -1 | 1) {
    setDays((prev) => {
      const next = prev.map((d) => ({ ...d, topics: [...d.topics] }));
      const topics = next[dayIdx].topics;
      const newIdx = topicIdx + direction;
      if (newIdx < 0 || newIdx >= topics.length) return prev;
      [topics[topicIdx], topics[newIdx]] = [topics[newIdx], topics[topicIdx]];
      return next;
    });
  }

  function rescheduleTopic(dayIdx: number, topicIdx: number, targetDayIdx: number) {
    setDays((prev) => {
      if (targetDayIdx < 0 || targetDayIdx >= prev.length) return prev;
      const next = prev.map((d) => ({ ...d, topics: [...d.topics] }));
      const [topic] = next[dayIdx].topics.splice(topicIdx, 1);
      next[targetDayIdx].topics.push(topic);
      return next;
    });
  }

  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
      {days.map((day, dayIdx) => (
        <div key={day.label} className="rounded-lg border border-gray-200 p-4">
          <h2 className="mb-3 font-semibold">{day.label}</h2>
          <ul className="space-y-2">
            {day.topics.map((topic, topicIdx) => (
              <li key={topic.id} className={`rounded-md border p-2 text-sm ${topic.mastery < 50 ? "border-red-300 bg-red-50" : "border-green-300 bg-green-50"}`}>
                <div className="flex items-center justify-between">
                  <span>{topic.title}</span>
                  <span className="text-xs text-gray-500">{topic.mastery}%</span>
                </div>
                <div className="mt-2 flex gap-2 text-xs">
                  <button onClick={() => moveTopic(dayIdx, topicIdx, -1)} className="rounded border px-2 py-1">Move up</button>
                  <button onClick={() => moveTopic(dayIdx, topicIdx, 1)} className="rounded border px-2 py-1">Move down</button>
                  {dayIdx > 0 && <button onClick={() => rescheduleTopic(dayIdx, topicIdx, dayIdx - 1)} className="rounded border px-2 py-1">Prev: {days[dayIdx - 1].label}</button>}
                  {dayIdx < days.length - 1 && <button onClick={() => rescheduleTopic(dayIdx, topicIdx, dayIdx + 1)} className="rounded border px-2 py-1">Next: {days[dayIdx + 1].label}</button>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
