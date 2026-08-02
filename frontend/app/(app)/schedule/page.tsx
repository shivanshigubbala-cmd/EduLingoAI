"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import ScheduleView from "@/components/schedule/ScheduleView";

export default function SchedulePage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [loading, user, router]);

  if (loading) {
    return <p className="text-sm text-gray-500">Loading...</p>;
  }

  if (!user) return null;

  return (
    <div>
      <h1 className="text-2xl font-semibold">Schedule</h1>
      <ScheduleView />
    </div>
  );
}
