"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity, LayoutDashboard, Users, FileText, Bell,
  LogOut, Menu, X, ChevronRight, Stethoscope
} from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { cn, getInitials } from "@/lib/utils";

const navItems = [
  { href: "/physician/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/physician/patients", icon: Users, label: "Patients" },
  { href: "/physician/briefs", icon: FileText, label: "Patient Briefs" },
  { href: "/physician/alerts", icon: Bell, label: "Alerts" },
];

export default function PhysicianLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, clearAuth } = useAuthStore();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const handleLogout = () => { clearAuth(); router.push("/login"); };

  const Sidebar = () => (
    <aside className="flex flex-col w-64 bg-slate-900 h-full">
      <div className="flex items-center gap-3 px-6 py-5 border-b border-slate-700">
        <div className="w-9 h-9 rounded-xl bg-crosscure-500 flex items-center justify-center shadow-sm">
          <Stethoscope className="w-5 h-5 text-white" />
        </div>
        <div>
          <span className="text-base font-bold text-white">CrossCures</span>
          <p className="text-xs text-slate-400">Physician Portal</p>
        </div>
      </div>
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setMobileOpen(false)}
            className={cn(
              "flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all",
              pathname === item.href || pathname.startsWith(item.href + "/")
                ? "bg-crosscure-600 text-white"
                : "text-slate-400 hover:bg-slate-800 hover:text-white"
            )}
          >
            <item.icon className="w-5 h-5" />
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>
      <div className="p-4 border-t border-slate-700">
        <div className="flex items-center gap-3 p-3 rounded-xl hover:bg-slate-800 cursor-pointer">
          <div className="w-9 h-9 rounded-full bg-crosscure-700 flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
            {user ? getInitials(user.full_name) : "U"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white truncate">{user?.full_name}</p>
            <p className="text-xs text-slate-400 truncate">{user?.specialty || "Physician"}</p>
          </div>
          <button onClick={handleLogout} className="text-slate-400 hover:text-red-400 transition-colors">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );

  return (
    <div className="flex h-screen bg-slate-100 overflow-hidden">
      <div className="hidden lg:flex flex-shrink-0">
        <Sidebar />
      </div>
      {/* Mobile header */}
      <div className="lg:hidden fixed inset-x-0 top-0 z-50 bg-slate-900 flex items-center justify-between px-4 h-14">
        <div className="flex items-center gap-2">
          <Stethoscope className="w-6 h-6 text-crosscure-400" />
          <span className="font-bold text-white">CrossCures</span>
        </div>
        <button onClick={() => setMobileOpen(true)} className="p-2 rounded-lg hover:bg-slate-800 text-slate-300">
          <Menu className="w-5 h-5" />
        </button>
      </div>
      {mounted && mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <div className="relative w-64">
            <Sidebar />
          </div>
        </div>
      )}
      <main className="flex-1 overflow-y-auto pt-14 lg:pt-0">
        {children}
      </main>
    </div>
  );
}
