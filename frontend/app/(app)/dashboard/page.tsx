import SuggestionFeed from "@/components/dashboard/SuggestionFeed";

export default function DashboardPage() {
  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100 p-6 md:p-10 max-w-4xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
      <SuggestionFeed />
    </main>
  );
}
