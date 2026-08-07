import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import type { ReactNode } from "react";

export default function AppLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <div className="md:flex">
        <Sidebar />

        <main className="min-w-0 flex-1 p-5 md:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
