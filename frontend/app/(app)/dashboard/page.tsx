"use client";

import ChatWindow from "@/components/chat/ChatWindow";
import UploadPanel from "@/components/upload/UploadPanel";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="mt-2 text-gray-600">
          Welcome, Sreehitha! Your learning journey starts here.
        </p>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        <ChatWindow />
        <UploadPanel />
      </div>
    </div>
  );
}