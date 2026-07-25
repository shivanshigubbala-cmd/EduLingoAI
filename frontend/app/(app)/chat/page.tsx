import ChatWindow from "@/components/chat/ChatWindow";

export default function ChatPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Doubt Chat</h1>
      <p className="mt-1 text-sm text-gray-600">
        Ask questions grounded in your uploaded syllabus.
      </p>
      <div className="mt-6">
        <ChatWindow />
      </div>
    </div>
  );
}