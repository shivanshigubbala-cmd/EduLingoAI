"use client";

export default function ChatWindow() {
  return (
    <section className="flex flex-col flex-1 bg-white rounded-xl shadow-md p-4">
      {/* Header */}
      <div className="border-b pb-3">
        <h2 className="text-xl font-semibold">AI Chat</h2>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-4 space-y-4">
        <div className="bg-gray-100 rounded-lg p-3 max-w-md">
          👋 Welcome to EduLingoAI!
        </div>

        <div className="bg-blue-100 rounded-lg p-3 max-w-md ml-auto">
          Hello AI!
        </div>
      </div>

      {/* Input */}
      <div className="border-t pt-4 flex gap-2">
        <input
          type="text"
          placeholder="Type your message..."
          className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />

        <button className="bg-blue-600 text-white px-5 rounded-lg hover:bg-blue-700">
          Send
        </button>
      </div>
    </section>
  );
}