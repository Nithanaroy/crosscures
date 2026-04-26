"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Activity, Calendar, ClipboardList, Stethoscope, Pill,
  TrendingUp, ChevronRight, Clock, Plus, AlertCircle, CheckCircle2,
  PhoneCall, HeartPulse,
} from "lucide-react";
import { patientApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn, formatDate, daysUntil, timeAgo } from "@/lib/utils";
import PatientLayout from "@/components/PatientLayout";

export default function PatientHome() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [checkinStatus, setCheckinStatus] = useState<any>(null);
  const [appointments, setAppointments] = useState<any[]>([]);
  const [prescriptions, setPrescriptions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [briefActionLoading, setBriefActionLoading] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    Promise.all([
      patientApi.getTodayCheckin().catch(() => null),
      patientApi.getAppointments().catch(() => ({ data: { appointments: [] } })),
      patientApi.getPrescriptions().catch(() => ({ data: { prescriptions: [] } })),
    ]).then(([checkin, appts, rx]) => {
      setCheckinStatus(checkin?.data || null);
      setAppointments(appts?.data?.appointments || []);
      setPrescriptions(rx?.data?.prescriptions || []);
    }).finally(() => setLoading(false));
  }, [user, router]);

  const nextAppointment = appointments.find((a) => daysUntil(a.appointment_date) >= 0);
  const daysToAppt = nextAppointment ? daysUntil(nextAppointment.appointment_date) : null;
  const checkinDone = checkinStatus?.completion_status === "completed";
  const activePrescriptions = prescriptions.filter((p) => p.status === "monitoring");

  const greeting = () => {
    if (!mounted) return "Hello";
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  };

  if (!user) return null;

  return (
    <PatientLayout>
      <div className="max-w-4xl mx-auto px-4 py-8 lg:px-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              {greeting()}, {user.full_name.split(" ")[0]} 👋
            </h1>
            <p className="text-slate-500 mt-1">Here's your health summary for today</p>
          </div>
          <div className="text-right text-sm text-slate-400" suppressHydrationWarning>
            {mounted ? new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" }) : ""}
          </div>
        </div>

        {/* Status cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          {/* Check-in status */}
          <div className={cn(
            "metric-card flex items-center gap-4",
            checkinDone ? "border-green-100 bg-green-50" : "border-amber-100 bg-amber-50"
          )}>
            <div className={cn(
              "w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0",
              checkinDone ? "bg-green-100" : "bg-amber-100"
            )}>
              {checkinDone ? (
                <CheckCircle2 className="w-6 h-6 text-green-600" />
              ) : (
                <ClipboardList className="w-6 h-6 text-amber-600" />
              )}
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Daily Check-in</p>
              <p className="text-sm font-semibold text-slate-900 mt-0.5">
                {checkinDone ? "Completed ✓" : "Not done yet"}
              </p>
            </div>
          </div>

          {/* Next appointment */}
          <div className="metric-card flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-crosscure-100 flex items-center justify-center flex-shrink-0">
              <Calendar className="w-6 h-6 text-crosscure-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Next Appointment</p>
              <p className="text-sm font-semibold text-slate-900 mt-0.5">
                {nextAppointment
                  ? daysToAppt === 0 ? "Today!" : `In ${daysToAppt} day${daysToAppt === 1 ? "" : "s"}`
                  : "None scheduled"}
              </p>
            </div>
          </div>

          {/* Active prescriptions */}
          <div className="metric-card flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-violet-100 flex items-center justify-center flex-shrink-0">
              <Pill className="w-6 h-6 text-violet-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Active Meds</p>
              <p className="text-sm font-semibold text-slate-900 mt-0.5">
                {activePrescriptions.length} medication{activePrescriptions.length !== 1 ? "s" : ""}
              </p>
            </div>
          </div>
        </div>

        {/* Quick actions */}
        {!checkinDone && (
          <div className="bg-gradient-to-r from-crosscure-600 to-teal-500 rounded-2xl p-6 mb-6 text-white">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold">Daily Check-in Ready</h2>
                <p className="text-white/80 text-sm mt-1">
                  Complete your symptom check-in — it takes about 3 minutes
                </p>
              </div>
              <Link
                href="/patient/checkin"
                className="flex items-center gap-2 bg-white text-crosscure-700 font-semibold px-5 py-2.5 rounded-xl hover:bg-white/90 transition-all text-sm flex-shrink-0"
              >
                Start now <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        )}

        {/* Upcoming Appointment Card */}
        {nextAppointment && (
          <div className="metric-card mb-6">
            <div className="flex items-start justify-between mb-4">
              <h2 className="section-title">Upcoming Appointment</h2>
              <span className={cn(
                "badge text-xs",
                daysToAppt! <= 3 ? "bg-orange-100 text-orange-700" : "bg-crosscure-100 text-crosscure-700"
              )}>
                {daysToAppt === 0 ? "Today" : `${daysToAppt}d away`}
              </span>
            </div>
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-crosscure-50 flex flex-col items-center justify-center border border-crosscure-100">
                <span className="text-xs font-semibold text-crosscure-600">
                  {new Date(nextAppointment.appointment_date).toLocaleDateString("en-US", { month: "short" }).toUpperCase()}
                </span>
                <span className="text-xl font-bold text-crosscure-700">
                  {new Date(nextAppointment.appointment_date).getDate()}
                </span>
              </div>
              <div className="flex-1">
                <p className="font-semibold text-slate-900">{nextAppointment.physician_name}</p>
                {nextAppointment.location && (
                  <p className="text-sm text-slate-500">{nextAppointment.location}</p>
                )}
                {nextAppointment.reason && (
                  <p className="text-sm text-slate-400 mt-0.5">{nextAppointment.reason}</p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                {!nextAppointment.brief_generated ? (
                  <button
                    disabled={briefActionLoading}
                    onClick={async () => {
                      try {
                        setBriefActionLoading(true);
                        await patientApi.generateBrief(nextAppointment.id);
                        const r = await patientApi.getAppointments();
                        setAppointments(r.data.appointments || []);
                      } catch (e: any) {
                        alert(e.response?.data?.detail || "Failed to generate brief");
                      } finally {
                        setBriefActionLoading(false);
                      }
                    }}
                    className="text-xs btn-secondary py-2 px-3"
                  >
                    {briefActionLoading ? "Generating..." : "Generate Brief"}
                  </button>
                ) : (
                  <>
                    <span className="text-xs badge bg-green-100 text-green-700">Brief Ready</span>
                    <button
                      disabled={briefActionLoading}
                      onClick={async () => {
                        try {
                          setBriefActionLoading(true);
                          await patientApi.generateBrief(nextAppointment.id, true);
                          const r = await patientApi.getAppointments();
                          setAppointments(r.data.appointments || []);
                        } catch (e: any) {
                          alert(e.response?.data?.detail || "Failed to regenerate brief");
                        } finally {
                          setBriefActionLoading(false);
                        }
                      }}
                      className="text-xs btn-secondary py-2 px-3"
                    >
                      {briefActionLoading ? "Regenerating..." : "Regenerate Brief"}
                    </button>
                  </>
                )}
                <Link href="/patient/clinic" className="text-xs btn-primary py-2 px-3">
                  Open Clinic
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* Maria actions — previsit + health report */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <Link
            href="/patient/previsit"
            className="metric-card hover:border-teal-300 hover:shadow-md transition-all group cursor-pointer border-teal-100 bg-teal-50/40"
          >
            <div className="w-11 h-11 rounded-xl bg-teal-100 flex items-center justify-center mb-3">
              <Calendar className="w-5 h-5 text-teal-600" />
            </div>
            <p className="font-semibold text-slate-900 text-sm group-hover:text-teal-700 transition-colors">
              Schedule Pre-Visit Call
            </p>
            <p className="text-xs text-slate-400 mt-0.5">Book a 15-min slot with Maria</p>
          </Link>

          <Link
            href="/patient/previsit?start=1"
            className="metric-card hover:border-crosscure-300 hover:shadow-md transition-all group cursor-pointer border-crosscure-100 bg-crosscure-50/40"
          >
            <div className="w-11 h-11 rounded-xl bg-crosscure-100 flex items-center justify-center mb-3">
              <PhoneCall className="w-5 h-5 text-crosscure-600" />
            </div>
            <p className="font-semibold text-slate-900 text-sm group-hover:text-crosscure-700 transition-colors">
              Start Pre-Visit Call
            </p>
            <p className="text-xs text-slate-400 mt-0.5">Speak with Maria now</p>
          </Link>

          <Link
            href="/patient/report"
            className="metric-card hover:border-rose-300 hover:shadow-md transition-all group cursor-pointer border-rose-100 bg-rose-50/40"
          >
            <div className="w-11 h-11 rounded-xl bg-rose-100 flex items-center justify-center mb-3">
              <HeartPulse className="w-5 h-5 text-rose-600" />
            </div>
            <p className="font-semibold text-slate-900 text-sm group-hover:text-rose-700 transition-colors">
              Report Health Condition
            </p>
            <p className="text-xs text-slate-400 mt-0.5">Describe a symptom or concern</p>
          </Link>
        </div>

        {/* Navigation grid */}
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { href: "/patient/checkin", icon: ClipboardList, label: "Symptom Check-in", color: "bg-teal-100", iconColor: "text-teal-600", desc: "Adaptive daily questionnaire" },
            { href: "/patient/clinic", icon: Stethoscope, label: "Clinic Session", color: "bg-crosscure-100", iconColor: "text-crosscure-600", desc: "AI companion with Maria" },
            { href: "/patient/records", icon: Activity, label: "Health Records", color: "bg-violet-100", iconColor: "text-violet-600", desc: "FHIR records & documents" },
            { href: "/patient/medications", icon: Pill, label: "Medications", color: "bg-pink-100", iconColor: "text-pink-600", desc: `${activePrescriptions.length} active` },
            { href: "/patient/settings", icon: Calendar, label: "Appointments", color: "bg-orange-100", iconColor: "text-orange-600", desc: nextAppointment ? formatDate(nextAppointment.appointment_date) : "Add appointment" },
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="metric-card hover:border-crosscure-200 hover:shadow-md transition-all group cursor-pointer"
            >
              <div className={cn("w-11 h-11 rounded-xl flex items-center justify-center mb-3", item.color)}>
                <item.icon className={cn("w-5 h-5", item.iconColor)} />
              </div>
              <p className="font-semibold text-slate-900 text-sm group-hover:text-crosscure-700 transition-colors">
                {item.label}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">{item.desc}</p>
            </Link>
          ))}
        </div>
      </div>
    </PatientLayout>
  );
}
