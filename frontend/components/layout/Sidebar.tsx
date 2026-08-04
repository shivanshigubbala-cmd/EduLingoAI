"use client";

import Link from "next/link";
import { Home, MessageSquare, Upload, Settings } from "lucide-react";

export default function Sidebar() {
  return (
    <aside className="w-64 min-h-screen bg-gray-900 text-white p-4">
      <h2 className="text-2xl font-bold mb-8">EduLingoAI</h2>

      <nav className="space-y-3">
        <Link
          href="/dashboard"
          className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-800 transition"
        >
          <Home size={20} />
          <span>Dashboard</span>
        </Link>

        <Link
          href="/dashboard"
          className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-800 transition"
        >
          <MessageSquare size={20} />
          <span>Chat</span>
        </Link>

        <Link
          href="/dashboard"
          className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-800 transition"
        >
          <Upload size={20} />
          <span>Upload</span>
        </Link>

        <Link
          href="/dashboard"
          className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-800 transition"
        >
          <Settings size={20} />
          <span>Settings</span>
        </Link>
      </nav>
    </aside>
  );
}