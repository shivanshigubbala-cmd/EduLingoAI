export default function ChatWindow() {
  return (
    <div className="flex-1 rounded-lg border bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-xl font-semibold">Chat Window</h2>

      <div className="flex h-80 items-center justify-center rounded border border-dashed border-gray-300">
        <p className="text-gray-500">
          Chat messages will appear here.
        </p>
      </div>
    </div>
  );
}