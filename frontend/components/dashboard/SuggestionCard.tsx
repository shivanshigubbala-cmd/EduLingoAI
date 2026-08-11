"use client";

import { useState } from "react";
import { Suggestion } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

interface SuggestionCardProps {
  suggestion: Suggestion;
  onStart: (s: Suggestion) => void;
  onDismiss: (id: string) => void;
}

export function SuggestionCard({
  suggestion,
  onStart,
  onDismiss,
}: SuggestionCardProps) {
  const [leaving, setLeaving] = useState(false);

  const handleStart = () => {
    if (leaving) return;
    setLeaving(true);
    setTimeout(() => {
      onStart(suggestion);
    }, 200);
  };

  const handleDismiss = () => {
    if (leaving) return;
    setLeaving(true);
    setTimeout(() => {
      onDismiss(suggestion.id);
    }, 200);
  };

  return (
    <div
      className={`transition-all duration-200 ease-in-out overflow-hidden ${
        leaving
          ? "opacity-0 max-h-0 py-0 my-0 border-0 pointer-events-none"
          : "opacity-100 max-h-96 my-2"
      }`}
    >
      <Card className="p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2">
            <span
              className={`inline-block w-2.5 h-2.5 rounded-full shrink-0 ${
                suggestion.seen
                  ? "border border-amber-500 bg-transparent"
                  : "bg-amber-500"
              }`}
            />
            <h3 className="font-bold text-neutral-100 text-base">
              {suggestion.title}
            </h3>
          </div>
        </div>

        <p className="text-neutral-400 text-sm line-clamp-2 mb-4">
          {suggestion.message}
        </p>

        <div className="flex items-center gap-3">
          <Button variant="primary" onClick={handleStart}>
            Start now ↗
          </Button>
          <Button variant="secondary" onClick={handleDismiss}>
            Later
          </Button>
        </div>
      </Card>
    </div>
  );
}

export default SuggestionCard;
