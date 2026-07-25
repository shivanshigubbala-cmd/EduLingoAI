"use client";

import { useAuth } from "@/contexts/AuthContext";
import Link from "next/link";

interface HeaderProps {
  onMenuClick?: () => void;
}

export default function Header({ onMenuClick }: HeaderProps) {
  const { user, logout, loading } = useAuth();

  if (loading) return null;
  if (!user) return null;

  return (
    <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-900 md:hidden"
          aria-label="Open menu"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M3 5h14M3 10h14M3 15h14" strokeLinecap="round" />
          </svg>
        </button>
        <Link
          href="/dashboard"
          className="text-lg font-semibold tracking-tight md:hidden"
        >
          EduLingoAI
        </Link>
      </div>
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