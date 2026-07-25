"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/chat", label: "Doubt Chat" },
  { href: "/upload", label: "Upload" },
  { href: "/schedule", label: "Schedule" },
  { href: "/quiz", label: "Quiz" },
];

export default function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();

  const linkClass = (href: string) => {
    const active = pathname === href || pathname.startsWith(href + "/");
    return `block rounded px-3 py-2 text-sm transition ${
      active
        ? "bg-gray-900 text-white"
        : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
    }`;
  };

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/30 md:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-56 transform border-r border-gray-200 bg-white transition-transform md:static md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-6 py-4">
          <span className="text-lg font-semibold tracking-tight">
            EduLingoAI
          </span>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-900 md:hidden"
            aria-label="Close menu"
          >
            ✕
          </button>
        </div>
        <nav className="space-y-1 px-3">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={linkClass(item.href)}
              onClick={onClose}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
    </>
  );
}