"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Activity, ChevronRight, ChevronLeft } from "lucide-react";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const CONSENT_ACTIONS = [
  { key: "HEALTH_RECORD_STORAGE", label: "Store & process my health records", required: true },
  { key: "LLM_INFERENCE", label: "Use AI to analyze my health data (zero-retention)", required: true },
  { key: "PHYSICIAN_BRIEF_SHARING", label: "Share pre-visit briefs with my physician", required: false },
  { key: "PHYSICIAN_ALERT_SHARING", label: "Send therapy alerts to my physician", required: false },
  { key: "WEARABLE_SYNC", label: "Sync Apple Health/wearable data", required: false },
  { key: "AMBIENT_LISTENING", label: "Voice transcription during clinic sessions", required: false },
];

export default function RegisterPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return <div className="min-h-screen bg-white" />;
  }

  const [form, setForm] = useState({
    email: "",
    password: "",
    full_name: "",
    role: "patient" as "patient" | "physician",
    date_of_birth: "",
    npi_number: "",
    specialty: "",
  });

  const [consents, setConsents] = useState<Record<string, boolean>>({
    HEALTH_RECORD_STORAGE: true,
    LLM_INFERENCE: true,
    PHYSICIAN_BRIEF_SHARING: true,
    PHYSICIAN_ALERT_SHARING: true,
    WEARABLE_SYNC: false,
    AMBIENT_LISTENING: false,
  });

  const handleRegister = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await authApi.register(form);
      const { access_token, user } = res.data;
      setAuth(user, access_token);
      if (user.role === "physician") {
        router.push("/physician/dashboard");
      } else {
        router.push("/patient/home");
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Registration failed");
      setStep(1);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-crosscure-50 to-teal-50 p-4">
      <div className="w-full max-w-lg bg-white rounded-3xl shadow-xl border border-slate-100 overflow-hidden">
        {/* Header */}
        <div className="gradient-bg p-8 text-white">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-9 h-9 bg-white/20 rounded-xl flex items-center justify-center">
              <Activity className="w-5 h-5" />
            </div>
            <span className="text-xl font-bold">CrossCures</span>
          </div>
          <h1 className="text-2xl font-bold">Create your account</h1>
          <p className="text-white/80 mt-1">Step {step} of 3</p>
          <div className="flex gap-2 mt-4">
            {[1, 2, 3].map((s) => (
              <div
                key={s}
                className={cn(
                  "h-1.5 rounded-full flex-1 transition-all",
                  s <= step ? "bg-white" : "bg-white/30"
                )}
              />
            ))}
          </div>
        </div>

        <div className="p-8 space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
              {error}
            </div>
          )}

          {/* Step 1 — Account type */}
          {step === 1 && (
            <div className="space-y-5 animate-fade-in">
              <h2 className="text-xl font-semibold text-slate-900">I am a...</h2>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { role: "patient", icon: "🧑‍⚕️", label: "Patient", desc: "Track symptoms, manage health" },
                  { role: "physician", icon: "👨‍⚕️", label: "Physician", desc: "View patient briefs & alerts" },
                ].map((opt) => (
                  <button
                    key={opt.role}
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, role: opt.role as any }))}
                    className={cn(
                      "p-4 rounded-2xl border-2 text-left transition-all",
                      form.role === opt.role
                        ? "border-crosscure-500 bg-crosscure-50"
                        : "border-slate-200 hover:border-slate-300 bg-white"
                    )}
                  >
                    <div className="text-3xl mb-2">{opt.icon}</div>
                    <div className="font-semibold text-slate-900">{opt.label}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{opt.desc}</div>
                  </button>
                ))}
              </div>
              <div className="space-y-4">
                <div>
                  <label className="label-text">Full name</label>
                  <input className="input-field" placeholder="Jane Smith" value={form.full_name}
                    onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} />
                </div>
                <div>
                  <label className="label-text">Email address</label>
                  <input type="email" className="input-field" placeholder="jane@example.com" value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
                </div>
                <div>
                  <label className="label-text">Password</label>
                  <input type="password" className="input-field" placeholder="Min. 8 characters" value={form.password}
                    onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
                </div>
                {form.role === "patient" && (
                  <div>
                    <label className="label-text">Date of birth</label>
                    <input type="date" className="input-field" value={form.date_of_birth}
                      onChange={(e) => setForm((f) => ({ ...f, date_of_birth: e.target.value }))} />
                  </div>
                )}
                {form.role === "physician" && (
                  <>
                    <div>
                      <label className="label-text">NPI Number</label>
                      <input className="input-field" placeholder="10-digit NPI" value={form.npi_number}
                        onChange={(e) => setForm((f) => ({ ...f, npi_number: e.target.value }))} />
                    </div>
                    <div>
                      <label className="label-text">Specialty</label>
                      <input className="input-field" placeholder="e.g. Cardiology" value={form.specialty}
                        onChange={(e) => setForm((f) => ({ ...f, specialty: e.target.value }))} />
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Step 2 — Consent (patients only) */}
          {step === 2 && (
            <div className="space-y-5 animate-fade-in">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">Privacy & Consent</h2>
                <p className="text-slate-500 text-sm mt-1">Please review and configure your consent settings. Required items cannot be unchecked.</p>
              </div>
              <div className="space-y-3">
                {CONSENT_ACTIONS.map((item) => (
                  <label key={item.key} className={cn(
                    "flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition-all",
                    consents[item.key] ? "border-crosscure-200 bg-crosscure-50" : "border-slate-200 bg-white hover:bg-slate-50"
                  )}>
                    <input
                      type="checkbox"
                      className="mt-0.5 w-4 h-4 rounded accent-crosscure-600"
                      checked={consents[item.key]}
                      disabled={item.required}
                      onChange={(e) => setConsents((c) => ({ ...c, [item.key]: e.target.checked }))}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900">{item.label}</p>
                      {item.required && <p className="text-xs text-crosscure-600 mt-0.5">Required</p>}
                    </div>
                  </label>
                ))}
              </div>
              <p className="text-xs text-slate-400">All data is encrypted at rest (AES-256) and in transit (TLS 1.3). You can change these settings anytime.</p>
            </div>
          )}

          {/* Step 3 — Review */}
          {step === 3 && (
            <div className="space-y-5 animate-fade-in">
              <h2 className="text-xl font-semibold text-slate-900">You're all set</h2>
              <div className="bg-slate-50 rounded-2xl p-5 space-y-3">
                {[
                  { label: "Name", value: form.full_name },
                  { label: "Email", value: form.email },
                  { label: "Role", value: form.role === "patient" ? "Patient" : "Physician" },
                  form.role === "physician" && form.specialty ? { label: "Specialty", value: form.specialty } : null,
                ].filter(Boolean).map((item: any) => (
                  <div key={item.label} className="flex justify-between text-sm">
                    <span className="text-slate-500">{item.label}</span>
                    <span className="text-slate-900 font-medium">{item.value}</span>
                  </div>
                ))}
              </div>
              <p className="text-sm text-slate-500">By creating an account you agree to our Terms of Service and Privacy Policy. CrossCures is HIPAA-compliant and your data is encrypted at all times.</p>
            </div>
          )}

          {/* Navigation */}
          <div className="flex gap-3 pt-2">
            {step > 1 && (
              <button className="btn-secondary flex-1" onClick={() => setStep((s) => s - 1)}>
                <ChevronLeft className="w-4 h-4" /> Back
              </button>
            )}
            {step < 3 ? (
              <button
                className="btn-primary flex-1"
                onClick={() => setStep((s) => s + 1)}
                disabled={!form.full_name || !form.email || !form.password}
              >
                Next <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                className="btn-primary flex-1"
                onClick={handleRegister}
                disabled={loading}
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Creating account...
                  </span>
                ) : (
                  "Create account"
                )}
              </button>
            )}
          </div>

          <p className="text-center text-sm text-slate-500">
            Already have an account?{" "}
            <Link href="/login" className="text-crosscure-600 font-semibold hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
