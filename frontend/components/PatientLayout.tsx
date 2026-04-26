"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity, Home, ClipboardList, Stethoscope, FileText,
  Pill, Settings, LogOut, Menu, X, ChevronRight, PhoneCall, HeartPulse,
} from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { cn, getInitials } from "@/lib/utils";

const navItems = [
  { href: "/patient/home", icon: Home, label: "Home" },
  { href: "/patient/checkin", icon: ClipboardList, label: "Daily Check-in" },
  { href: "/patient/previsit", icon: PhoneCall, label: "Pre-Visit Call" },
  { href: "/patient/report", icon: HeartPulse, label: "Report Condition" },
  { href: "/patient/clinic", icon: Stethoscope, label: "Clinic Session" },
  { href: "/patient/records", icon: FileText, label: "Health Records" },
  { href: "/patient/medications", icon: Pill, label: "Medications" },
  { href: "/patient/settings", icon: Settings, label: "Settings" },
];

export default function PatientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, clearAuth } = useAuthStore();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const handleLogout = () => {
    clearAuth();
    router.push("/login");
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex flex-col w-64 bg-white border-r border-slate-100 shadow-sm">
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-slate-100">
          <div className="w-9 h-9 rounded-xl gradient-bg flex items-center justify-center shadow-sm">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-bold text-slate-900">CrossCures</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "sidebar-item",
                pathname === item.href || pathname?.startsWith(item.href + "/") ? "active" : ""
              )}
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              <span>{item.label}</span>
              {(pathname === item.href || pathname?.startsWith(item.href + "/")) && (
                <ChevronRight className="w-4 h-4 ml-auto text-crosscure-500" />
              )}
            </Link>
          ))}
        </nav>

        {/* User */}
        <div className="p-4 border-t border-slate-100">
          <div className="flex items-center gap-3 p-3 rounded-xl hover:bg-slate-50 cursor-pointer">
            <div className="w-9 h-9 rounded-full gradient-bg flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
              {user ? getInitials(user.full_name) : "U"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-900 truncate">{user?.full_name}</p>
              <p className="text-xs text-slate-400 truncate">{user?.email}</p>
            </div>
            <button onClick={handleLogout} className="text-slate-400 hover:text-red-500 transition-colors">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile Nav */}
      <div className="lg:hidden fixed inset-x-0 top-0 z-50 bg-white border-b border-slate-200 flex items-center justify-between px-4 h-14">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg gradient-bg flex items-center justify-center">
            <Activity className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-slate-900">CrossCures</span>
        </div>
        <button onClick={() => setMobileOpen(true)} className="p-2 rounded-lg hover:bg-slate-100">
          <Menu className="w-5 h-5 text-slate-700" />
        </button>
      </div>

      {/* Mobile Drawer — client-only to prevent SSR/hydration mismatch */}
      {mounted && mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <aside className="relative w-72 bg-white h-full flex flex-col shadow-xl">
            <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg gradient-bg flex items-center justify-center">
                  <Activity className="w-4 h-4 text-white" />
                </div>
                <span className="font-bold text-slate-900">CrossCures</span>
              </div>
              <button onClick={() => setMobileOpen(false)} className="p-1.5 rounded-lg hover:bg-slate-100">
                <X className="w-5 h-5" />
              </button>
            </div>
            <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={cn("sidebar-item", pathname === item.href ? "active" : "")}
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </Link>
              ))}
            </nav>
            <div className="p-4 border-t border-slate-100">
              <button onClick={handleLogout} className="sidebar-item w-full text-red-500 hover:bg-red-50 hover:text-red-600">
                <LogOut className="w-5 h-5" />
                <span>Sign out</span>
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto lg:overflow-hidden flex flex-col">
        <div className="lg:flex-1 lg:overflow-y-auto pt-14 lg:pt-0">
          {children}
        </div>
      </main>
    </div>
  );
}
