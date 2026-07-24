"use client";

import { useAuth } from "@/contexts/AuthContext";
import Link from "next/link";

export default function Header() {
  const { user, logout, loading } = useAuth();

  if (loading) return null;
  if (!user) return null;

  return (
    <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
      <Link href="/dashboard" className="text-lg font-semibold tracking-tight">
        EduLingoAI
      </Link>
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-600">{user.name}</span>
        <button
          onClick={logout}
          className="rounded px-3 py-1.5 text-sm text-gray-600 transition hover:bg-gray-100 hover:text-gray-900"
        >
          Log out
        </button>
      </div>
    </header>
  );
}
