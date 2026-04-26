"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, Activity, Stethoscope, User } from "lucide-react";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";

export default function LoginPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  // Render a minimal shell during SSR / first paint so the
  // server and client output are identical before hydration.
  if (!mounted) {
    return <div className="min-h-screen bg-white" />;
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await authApi.login({ email, password });
      const { access_token, user } = res.data;
      setAuth(user, access_token);
      if (user.role === "physician") {
        router.push("/physician/dashboard");
      } else {
        router.push("/patient/home");
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Invalid email or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left — Branding */}
      <div className="hidden lg:flex lg:w-1/2 gradient-bg flex-col items-center justify-center p-12 text-white">
        <div className="max-w-md space-y-8">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-white/20 rounded-2xl flex items-center justify-center backdrop-blur-sm">
              <Activity className="w-7 h-7 text-white" />
            </div>
            <span className="text-2xl font-bold">CrossCures</span>
          </div>
          <div>
            <h1 className="text-4xl font-bold leading-tight mb-4">
              Your intelligent health companion
            </h1>
            <p className="text-white/80 text-lg leading-relaxed">
              AI-powered symptom tracking, clinic support, and therapy monitoring — all in one secure platform.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4">
            {[
              { icon: "🩺", title: "Pre-visit Intelligence", desc: "Adaptive symptom check-ins and AI-generated physician briefs" },
              { icon: "💬", title: "Clinic Companion", desc: "Voice-enabled support during your medical appointments" },
              { icon: "💊", title: "Therapy Guardian", desc: "Prescription monitoring with outcome tracking" },
            ].map((f) => (
              <div key={f.title} className="flex items-start gap-4 bg-white/10 rounded-2xl p-4 backdrop-blur-sm">
                <span className="text-2xl">{f.icon}</span>
                <div>
                  <p className="font-semibold">{f.title}</p>
                  <p className="text-sm text-white/70">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right — Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-md space-y-8">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-9 h-9 rounded-xl gradient-bg flex items-center justify-center">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-slate-900">CrossCures</span>
          </div>

          <div>
            <h2 className="text-3xl font-bold text-slate-900">Welcome back</h2>
            <p className="text-slate-500 mt-2">Sign in to your CrossCures account</p>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="label-text">Email address</label>
              <input
                type="email"
                className="input-field"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div>
              <label className="label-text">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  className="input-field pr-12"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="btn-primary w-full text-base"
              disabled={loading}
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Signing in...
                </span>
              ) : (
                "Sign in"
              )}
            </button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-xs text-slate-400 uppercase tracking-wide bg-white px-3">
              or
            </div>
          </div>

          {/* Quick demo login */}
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              className="btn-secondary text-sm flex items-center gap-2 justify-center"
              onClick={() => { setEmail("patient@demo.com"); setPassword("demo1234"); }}
            >
              <User className="w-4 h-4" /> Patient Demo
            </button>
            <button
              type="button"
              className="btn-secondary text-sm flex items-center gap-2 justify-center"
              onClick={() => { setEmail("physician@demo.com"); setPassword("demo1234"); }}
            >
              <Stethoscope className="w-4 h-4" /> Physician Demo
            </button>
          </div>

          <p className="text-center text-sm text-slate-500">
            Don't have an account?{" "}
            <Link href="/register" className="text-crosscure-600 font-semibold hover:underline">
              Create account
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
