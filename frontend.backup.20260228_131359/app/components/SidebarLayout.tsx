"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  Mic,
  Calendar,
  Settings,
  Home,
  ChevronRight,
} from "lucide-react";

const navItems = [
  { name: "Dashboard", href: "/", icon: Home },
  { name: "Meetings", href: "/meetings", icon: Calendar },
  { name: "Settings", href: "/settings", icon: Settings },
];

export default function SidebarLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-slate-100">
          <Link href="/" className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-rose-500 to-red-600 rounded-xl flex items-center justify-center shadow-lg shadow-rose-500/20">
              <Mic className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-xl text-gray-900">MeetScribe</h1>
              <p className="text-xs text-gray-500">AI Meeting Assistant</p>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => {
            const isActive =
              pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-blue-50 text-blue-700 shadow-sm"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
              >
                <Icon
                  className={`w-5 h-5 ${
                    isActive ? "text-blue-600" : "text-gray-400"
                  }`}
                />
                {item.name}
                {isActive && (
                  <ChevronRight className="w-4 h-4 ml-auto text-blue-500" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100">
          <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-xl p-4">
            <p className="text-xs text-slate-400 mb-2">Quick Tip</p>
            <p className="text-sm text-slate-200">
              Press Ctrl+Enter to save notes instantly during a recording.
            </p>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
