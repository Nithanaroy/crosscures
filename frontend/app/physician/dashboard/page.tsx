"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  FileText, Bell, Users, AlertTriangle, CheckCircle2,
  ChevronRight, Loader2, Clock, TrendingUp
} from "lucide-react";
import { physicianApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn, timeAgo, severityBadgeColor } from "@/lib/utils";
import PhysicianLayout from "@/components/PhysicianLayout";

export default function PhysicianDashboard() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [dashboard, setDashboard] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    if (user.role !== "physician") { router.push("/patient/home"); return; }
    physicianApi.getDashboard().then((res) => {
      setDashboard(res.data);
    }).finally(() => setLoading(false));
  }, [user, router]);

  if (!user) return null;

  return (
    <PhysicianLayout>
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Good morning, Dr. {user.full_name.split(" ").slice(-1)[0]} 👋
          </h1>
          <p className="text-slate-500 mt-1">
            {user.specialty ? `${user.specialty} · ` : ""}
            {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
          </p>
        </div>

        {/* Stats */}
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-crosscure-500" /></div>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-4">
              {[
                {
                  label: "Linked Patients", value: dashboard?.linked_patient_count ?? 0,
                  icon: Users, color: "bg-crosscure-100", iconColor: "text-crosscure-600"
                },
                {
                  label: "Unread Briefs", value: dashboard?.unread_briefs?.length ?? 0,
                  icon: FileText, color: "bg-teal-100", iconColor: "text-teal-600"
                },
                {
                  label: "Pending Alerts", value: dashboard?.unacknowledged_alerts?.length ?? 0,
                  icon: Bell, color: dashboard?.unacknowledged_alerts?.length > 0 ? "bg-red-100" : "bg-slate-100",
                  iconColor: dashboard?.unacknowledged_alerts?.length > 0 ? "text-red-600" : "text-slate-500"
                },
              ].map((stat) => (
                <div key={stat.label} className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
                  <div className={cn("w-11 h-11 rounded-xl flex items-center justify-center mb-3", stat.color)}>
                    <stat.icon className={cn("w-5 h-5", stat.iconColor)} />
                  </div>
                  <p className="text-3xl font-bold text-slate-900">{stat.value}</p>
                  <p className="text-sm text-slate-400 mt-1">{stat.label}</p>
                </div>
              ))}
            </div>

            {/* Unacknowledged Alerts */}
            {dashboard?.unacknowledged_alerts?.length > 0 && (
              <section>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-semibold text-slate-900 flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-red-500" /> Pending Alerts
                  </h2>
                  <Link href="/physician/alerts" className="text-sm text-crosscure-600 hover:underline flex items-center gap-1">
                    View all <ChevronRight className="w-4 h-4" />
                  </Link>
                </div>
                <div className="space-y-3">
                  {dashboard.unacknowledged_alerts.slice(0, 5).map((alert: any) => (
                    <Link key={alert.alert_id} href={`/physician/alerts/${alert.alert_id}`}>
                      <div className="bg-white rounded-2xl p-4 border border-red-100 hover:border-red-300 hover:shadow-sm transition-all flex items-center gap-4 group">
                        <div className={cn(
                          "w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0",
                          alert.severity === "severe" ? "bg-red-100" : alert.severity === "moderate" ? "bg-orange-100" : "bg-yellow-100"
                        )}>
                          <Bell className={cn(
                            "w-5 h-5",
                            alert.severity === "severe" ? "text-red-600" : alert.severity === "moderate" ? "text-orange-600" : "text-yellow-600"
                          )} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-semibold text-slate-900 truncate">{alert.patient_name}</p>
                            <span className={cn("badge text-xs", severityBadgeColor(alert.severity))}>
                              {alert.severity}
                            </span>
                            {alert.requires_acknowledgment && (
                              <span className="badge bg-red-100 text-red-700 text-xs">Requires ACK</span>
                            )}
                          </div>
                          <p className="text-xs text-slate-400 mt-0.5">{timeAgo(alert.generated_at)}</p>
                        </div>
                        <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-600 transition-colors flex-shrink-0" />
                      </div>
                    </Link>
                  ))}
                </div>
              </section>
            )}

            {/* Unread Briefs */}
            {dashboard?.unread_briefs?.length > 0 && (
              <section>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-semibold text-slate-900 flex items-center gap-2">
                    <FileText className="w-5 h-5 text-teal-500" /> Unread Briefs
                  </h2>
                  <Link href="/physician/briefs" className="text-sm text-crosscure-600 hover:underline flex items-center gap-1">
                    View all <ChevronRight className="w-4 h-4" />
                  </Link>
                </div>
                <div className="space-y-3">
                  {dashboard.unread_briefs.slice(0, 5).map((brief: any) => (
                    <Link key={brief.brief_id} href={`/physician/briefs/${brief.brief_id}`}>
                      <div className="bg-white rounded-2xl p-4 border border-slate-100 hover:border-crosscure-200 hover:shadow-sm transition-all flex items-center gap-4 group">
                        <div className="w-10 h-10 rounded-xl bg-teal-50 flex items-center justify-center flex-shrink-0">
                          <FileText className="w-5 h-5 text-teal-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-slate-900 truncate">{brief.patient_name}</p>
                          <p className="text-xs text-slate-400 mt-0.5">Pre-visit brief · {timeAgo(brief.generated_at)}</p>
                        </div>
                        <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-600 transition-colors flex-shrink-0" />
                      </div>
                    </Link>
                  ))}
                </div>
              </section>
            )}

            {/* Empty state */}
            {(!dashboard?.unacknowledged_alerts?.length && !dashboard?.unread_briefs?.length) && (
              <div className="text-center py-16 bg-white rounded-3xl border border-slate-100">
                <CheckCircle2 className="w-14 h-14 text-green-400 mx-auto mb-4" />
                <h2 className="text-lg font-semibold text-slate-700">All caught up!</h2>
                <p className="text-slate-400 mt-2">No unread briefs or pending alerts.</p>
                {dashboard?.linked_patient_count === 0 && (
                  <p className="text-sm text-slate-400 mt-2">Ask your patients to link you in their app to get started.</p>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </PhysicianLayout>
  );
}
