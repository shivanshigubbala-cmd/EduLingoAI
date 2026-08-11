"use client";

import { useEffect, useState } from "react";
import { Suggestion } from "@/lib/types";
import { dismissSuggestion, getSuggestions } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { SuggestionCard } from "./SuggestionCard";

export function SuggestionFeed() {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    const fetchFeed = async () => {
      const data = await getSuggestions();
      if (isMounted) {
        setSuggestions(data);
        setLoading(false);
      }
    };

    fetchFeed();

    const intervalId = setInterval(() => {
      fetchFeed();
    }, 30000);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, []);

  const handleDismiss = async (id: string) => {
    await dismissSuggestion(id);
    setSuggestions((prev) => prev.filter((item) => item.id !== id));
  };

  const handleStart = async (suggestion: Suggestion) => {
    await dismissSuggestion(suggestion.id);
    console.log("navigate", suggestion);
    setSuggestions((prev) => prev.filter((item) => item.id !== suggestion.id));
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Card className="p-4 sm:p-5">
          <div className="animate-pulse space-y-3">
            <div className="h-4 bg-neutral-800 rounded w-3/4" />
            <div className="h-3 bg-neutral-800 rounded w-full" />
            <div className="h-3 bg-neutral-800 rounded w-5/6" />
            <div className="flex gap-3 pt-2">
              <div className="h-8 bg-neutral-800 rounded w-24" />
              <div className="h-8 bg-neutral-800 rounded w-20" />
            </div>
          </div>
        </Card>
        <Card className="p-4 sm:p-5">
          <div className="animate-pulse space-y-3">
            <div className="h-4 bg-neutral-800 rounded w-2/3" />
            <div className="h-3 bg-neutral-800 rounded w-full" />
            <div className="h-3 bg-neutral-800 rounded w-4/5" />
            <div className="flex gap-3 pt-2">
              <div className="h-8 bg-neutral-800 rounded w-24" />
              <div className="h-8 bg-neutral-800 rounded w-20" />
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {suggestions.map((suggestion) => (
        <SuggestionCard
          key={suggestion.id}
          suggestion={suggestion}
          onStart={handleStart}
          onDismiss={handleDismiss}
        />
      ))}
    </div>
  );
}

export default SuggestionFeed;
