"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { FileText, Bell, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { physicianApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn, timeAgo, severityBadgeColor, formatDate } from "@/lib/utils";
import PhysicianLayout from "@/components/PhysicianLayout";

export default function PatientDetailPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const { patientId } = useParams();
  const [briefs, setBriefs] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"briefs" | "alerts">("briefs");

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    Promise.all([
      physicianApi.getPatientBriefs(patientId as string),
      physicianApi.getPatientAlerts(patientId as string),
    ]).then(([b, a]) => {
      setBriefs(b.data.briefs || []);
      setAlerts(a.data.alerts || []);
    }).finally(() => setLoading(false));
  }, [user, patientId, router]);

  return (
    <PhysicianLayout>
      <div className="max-w-4xl mx-auto px-6 py-8">
        <button onClick={() => router.back()} className="flex items-center gap-2 text-slate-500 hover:text-slate-800 mb-6 text-sm">
          <ChevronLeft className="w-4 h-4" /> Back to patients
        </button>

        <div className="flex gap-4 mb-6 border-b border-slate-200">
          {[
            { id: "briefs", label: `Briefs (${briefs.length})`, icon: FileText },
            { id: "alerts", label: `Alerts (${alerts.length})`, icon: Bell },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id as any)}
              className={cn(
                "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all",
                tab === t.id ? "border-crosscure-500 text-crosscure-700" : "border-transparent text-slate-500 hover:text-slate-700"
              )}
            >
              <t.icon className="w-4 h-4" />
              {t.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-crosscure-500" /></div>
        ) : tab === "briefs" ? (
          <div className="space-y-3">
            {briefs.length === 0 ? (
              <div className="text-center py-12 text-slate-400">No briefs generated yet</div>
            ) : briefs.map((brief) => (
              <Link key={brief.brief_id} href={`/physician/briefs/${brief.brief_id}`}>
                <div className="bg-white rounded-2xl p-4 border border-slate-100 hover:border-crosscure-200 hover:shadow-sm transition-all flex items-center gap-4 group">
                  <div className="w-10 h-10 rounded-xl bg-teal-50 flex items-center justify-center flex-shrink-0">
                    <FileText className="w-5 h-5 text-teal-600" />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-slate-900">Pre-visit Brief</p>
                    <p className="text-xs text-slate-400">{timeAgo(brief.generated_at)}</p>
                  </div>
                  {brief.acknowledged_at ? (
                    <span className="badge bg-green-100 text-green-700 text-xs">Acknowledged</span>
                  ) : (
                    <span className="badge bg-amber-100 text-amber-700 text-xs">Unread</span>
                  )}
                  <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-600 transition-colors" />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.length === 0 ? (
              <div className="text-center py-12 text-slate-400">No alerts generated yet</div>
            ) : alerts.map((alert) => (
              <Link key={alert.alert_id} href={`/physician/alerts/${alert.alert_id}`}>
                <div className="bg-white rounded-2xl p-4 border border-slate-100 hover:border-crosscure-200 hover:shadow-sm transition-all flex items-center gap-4 group">
                  <div className={cn(
                    "w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0",
                    alert.severity === "severe" ? "bg-red-100" : alert.severity === "moderate" ? "bg-orange-100" : "bg-yellow-100"
                  )}>
                    <Bell className={cn(
                      "w-5 h-5",
                      alert.severity === "severe" ? "text-red-600" : alert.severity === "moderate" ? "text-orange-600" : "text-yellow-600"
                    )} />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-slate-900">Therapy Alert</p>
                      <span className={cn("badge text-xs", severityBadgeColor(alert.severity))}>{alert.severity}</span>
                    </div>
                    <p className="text-xs text-slate-400">{timeAgo(alert.generated_at)}</p>
                  </div>
                  {alert.acknowledged_at ? (
                    <span className="badge bg-green-100 text-green-700 text-xs">Acknowledged</span>
                  ) : (
                    <span className="badge bg-red-100 text-red-700 text-xs">Pending</span>
                  )}
                  <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-600 transition-colors" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </PhysicianLayout>
  );
}
