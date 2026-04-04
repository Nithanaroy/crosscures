"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Settings, Shield, Bell, User, Link2, LogOut, CheckCircle2,
  XCircle, Loader2, Calendar, Plus
} from "lucide-react";
import { patientApi, authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn, formatDate } from "@/lib/utils";
import PatientLayout from "@/components/PatientLayout";

const CONSENT_LABELS: Record<string, { label: string; description: string }> = {
  HEALTH_RECORD_STORAGE: { label: "Health Record Storage", description: "Store and process uploaded health records" },
  WEARABLE_SYNC: { label: "Wearable Sync", description: "Read and store Apple HealthKit data" },
  AMBIENT_LISTENING: { label: "Voice Transcription", description: "Transcribe audio during clinic sessions" },
  PHYSICIAN_BRIEF_SHARING: { label: "Pre-Visit Brief Sharing", description: "Send pre-visit briefs to your physician" },
  PHYSICIAN_ALERT_SHARING: { label: "Therapy Alert Sharing", description: "Send therapy deviation alerts to your physician" },
  LLM_INFERENCE: { label: "AI Analysis", description: "Use AI to analyze your health data" },
  RESEARCH_DATA_USE: { label: "Research Data Use", description: "Use anonymized data for model improvement" },
};

export default function SettingsPage() {
  const { user, clearAuth } = useAuthStore();
  const router = useRouter();
  const [consents, setConsents] = useState<any[]>([]);
  const [appointments, setAppointments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);
  const [linkEmail, setLinkEmail] = useState("");
  const [linking, setLinking] = useState(false);
  const [linkStatus, setLinkStatus] = useState<string | null>(null);
  const [showAddAppt, setShowAddAppt] = useState(false);
  const [apptForm, setApptForm] = useState({ physician_name: "", appointment_date: "", location: "", reason: "" });
  const [savingAppt, setSavingAppt] = useState(false);

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    Promise.all([
      patientApi.getConsents().catch(() => ({ data: { consents: [] } })),
      patientApi.getAppointments().catch(() => ({ data: { appointments: [] } })),
    ]).then(([c, a]) => {
      setConsents(c.data.consents || []);
      setAppointments(a.data.appointments || []);
    }).finally(() => setLoading(false));
  }, [user, router]);

  const toggleConsent = async (action: string, granted: boolean) => {
    setToggling(action);
    try {
      if (granted) {
        await patientApi.revokeConsent(action);
      } else {
        await patientApi.grantConsent(action);
      }
      const res = await patientApi.getConsents();
      setConsents(res.data.consents || []);
    } finally {
      setToggling(null);
    }
  };

  const consentMap: Record<string, any> = {};
  consents.forEach((c) => { consentMap[c.action] = c; });

  const handleLinkPhysician = async (e: React.FormEvent) => {
    e.preventDefault();
    setLinking(true);
    setLinkStatus(null);
    try {
      const res = await authApi.linkPhysician(linkEmail);
      setLinkStatus(`Linked to Dr. ${res.data.physician_name || linkEmail}`);
      setLinkEmail("");
    } catch (e: any) {
      setLinkStatus("Error: " + (e.response?.data?.detail || "Physician not found"));
    } finally {
      setLinking(false);
    }
  };

  const handleAddAppointment = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingAppt(true);
    try {
      await patientApi.createAppointment(apptForm);
      const res = await patientApi.getAppointments();
      setAppointments(res.data.appointments || []);
      setShowAddAppt(false);
      setApptForm({ physician_name: "", appointment_date: "", location: "", reason: "" });
    } finally {
      setSavingAppt(false);
    }
  };

  if (!user) return null;

  return (
    <PatientLayout>
      <div className="max-w-3xl mx-auto px-4 py-8 lg:px-8 space-y-8">
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>

        {/* Profile */}
        <section className="bg-white rounded-2xl p-6 border border-slate-100">
          <div className="flex items-center gap-3 mb-5">
            <User className="w-5 h-5 text-slate-600" />
            <h2 className="font-semibold text-slate-900">Profile</h2>
          </div>
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full gradient-bg flex items-center justify-center text-white font-bold text-xl">
              {user.full_name.charAt(0).toUpperCase()}
            </div>
            <div>
              <p className="font-semibold text-slate-900">{user.full_name}</p>
              <p className="text-sm text-slate-400">{user.email}</p>
              <span className="badge bg-crosscure-50 text-crosscure-700 text-xs mt-1">Patient</span>
            </div>
          </div>
        </section>

        {/* Appointments */}
        <section className="bg-white rounded-2xl p-6 border border-slate-100">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <Calendar className="w-5 h-5 text-slate-600" />
              <h2 className="font-semibold text-slate-900">Appointments</h2>
            </div>
            <button className="btn-secondary text-sm py-2 px-4" onClick={() => setShowAddAppt(true)}>
              <Plus className="w-4 h-4" /> Add
            </button>
          </div>
          {showAddAppt && (
            <form onSubmit={handleAddAppointment} className="bg-slate-50 rounded-2xl p-4 mb-4 space-y-3 animate-fade-in">
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="label-text text-xs">Physician name *</label>
                  <input className="input-field text-sm" placeholder="Dr. Smith" required value={apptForm.physician_name}
                    onChange={(e) => setApptForm(f => ({ ...f, physician_name: e.target.value }))} />
                </div>
                <div>
                  <label className="label-text text-xs">Date & time *</label>
                  <input type="datetime-local" className="input-field text-sm" required value={apptForm.appointment_date}
                    onChange={(e) => setApptForm(f => ({ ...f, appointment_date: e.target.value }))} />
                </div>
                <div>
                  <label className="label-text text-xs">Location</label>
                  <input className="input-field text-sm" placeholder="Clinic name" value={apptForm.location}
                    onChange={(e) => setApptForm(f => ({ ...f, location: e.target.value }))} />
                </div>
                <div className="col-span-2">
                  <label className="label-text text-xs">Reason</label>
                  <input className="input-field text-sm" placeholder="Purpose of visit" value={apptForm.reason}
                    onChange={(e) => setApptForm(f => ({ ...f, reason: e.target.value }))} />
                </div>
              </div>
              <div className="flex gap-2">
                <button type="button" className="btn-secondary flex-1 text-sm py-2" onClick={() => setShowAddAppt(false)}>Cancel</button>
                <button type="submit" className="btn-primary flex-1 text-sm py-2" disabled={savingAppt}>
                  {savingAppt ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save"}
                </button>
              </div>
            </form>
          )}
          {appointments.length === 0 ? (
            <p className="text-slate-400 text-sm">No appointments scheduled</p>
          ) : (
            <div className="space-y-2">
              {appointments.slice(0, 3).map((a) => (
                <div key={a.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                  <div>
                    <p className="text-sm font-medium text-slate-900">{a.physician_name}</p>
                    <p className="text-xs text-slate-400">{formatDate(a.appointment_date)} · {a.location}</p>
                  </div>
                  {a.brief_generated ? (
                    <span className="badge bg-green-100 text-green-700 text-xs">Brief ready</span>
                  ) : (
                    <span className="badge bg-slate-100 text-slate-500 text-xs">No brief</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Link physician */}
        <section className="bg-white rounded-2xl p-6 border border-slate-100">
          <div className="flex items-center gap-3 mb-5">
            <Link2 className="w-5 h-5 text-slate-600" />
            <h2 className="font-semibold text-slate-900">Link Physician</h2>
          </div>
          <form onSubmit={handleLinkPhysician} className="flex gap-3">
            <input
              type="email"
              className="input-field flex-1"
              placeholder="Physician's email address"
              value={linkEmail}
              onChange={(e) => setLinkEmail(e.target.value)}
            />
            <button type="submit" className="btn-primary whitespace-nowrap" disabled={linking}>
              {linking ? <Loader2 className="w-4 h-4 animate-spin" /> : "Link"}
            </button>
          </form>
          {linkStatus && (
            <p className={cn(
              "text-sm mt-3 flex items-center gap-2",
              linkStatus.startsWith("Error") ? "text-red-600" : "text-green-600"
            )}>
              {linkStatus.startsWith("Error") ? <XCircle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
              {linkStatus}
            </p>
          )}
        </section>

        {/* Consent management */}
        <section className="bg-white rounded-2xl p-6 border border-slate-100">
          <div className="flex items-center gap-3 mb-5">
            <Shield className="w-5 h-5 text-slate-600" />
            <h2 className="font-semibold text-slate-900">Privacy & Consent</h2>
          </div>
          {loading ? (
            <Loader2 className="w-5 h-5 animate-spin text-crosscure-500" />
          ) : (
            <div className="space-y-3">
              {Object.entries(CONSENT_LABELS).map(([action, info]) => {
                const record = consentMap[action];
                const isGranted = record?.granted && !record?.revoked_at;
                const isRequired = ["HEALTH_RECORD_STORAGE", "LLM_INFERENCE"].includes(action);
                return (
                  <div key={action} className="flex items-start justify-between gap-4 p-3 rounded-xl hover:bg-slate-50">
                    <div className="flex-1">
                      <p className="text-sm font-medium text-slate-900">{info.label}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{info.description}</p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {toggling === action ? (
                        <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
                      ) : (
                        <button
                          onClick={() => !isRequired && toggleConsent(action, isGranted)}
                          disabled={isRequired}
                          className={cn(
                            "relative w-11 h-6 rounded-full transition-all",
                            isGranted ? "bg-crosscure-500" : "bg-slate-200",
                            isRequired ? "opacity-60 cursor-default" : "cursor-pointer"
                          )}
                        >
                          <span className={cn(
                            "absolute top-1 w-4 h-4 bg-white rounded-full shadow-sm transition-all",
                            isGranted ? "left-6" : "left-1"
                          )} />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Sign out */}
        <button
          onClick={() => { clearAuth(); router.push("/login"); }}
          className="w-full flex items-center justify-center gap-2 p-4 rounded-2xl border border-red-200 text-red-600 hover:bg-red-50 transition-all font-medium"
        >
          <LogOut className="w-5 h-5" /> Sign out
        </button>
      </div>
    </PatientLayout>
  );
}
