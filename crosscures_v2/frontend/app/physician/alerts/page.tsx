"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Bell, ChevronRight, Loader2, AlertTriangle } from "lucide-react";
import { physicianApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn, timeAgo, getInitials, severityBadgeColor } from "@/lib/utils";
import PhysicianLayout from "@/components/PhysicianLayout";

export default function AlertsPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [allAlerts, setAllAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    physicianApi.getPatients().then(async (res) => {
      const pts = res.data.patients || [];
      const alertPromises = pts.map((p: any) =>
        physicianApi.getPatientAlerts(p.id).then((r) =>
          (r.data.alerts || []).map((a: any) => ({ ...a, patient_name: p.full_name }))
        ).catch(() => [])
      );
      const results = await Promise.all(alertPromises);
      const combined = results.flat().sort((a, b) => {
        if (!a.acknowledged_at && b.acknowledged_at) return -1;
        if (a.acknowledged_at && !b.acknowledged_at) return 1;
        return new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime();
      });
      setAllAlerts(combined);
    }).finally(() => setLoading(false));
  }, [user, router]);

  return (
    <PhysicianLayout>
      <div className="max-w-4xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">Therapy Alerts</h1>
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-crosscure-500" /></div>
        ) : allAlerts.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-3xl border border-slate-100">
            <Bell className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-400">No alerts yet</p>
          </div>
        ) : (
          <div className="space-y-3">
            {allAlerts.map((alert) => (
              <Link key={alert.alert_id} href={`/physician/alerts/${alert.alert_id}`}>
                <div className={cn(
                  "bg-white rounded-2xl p-4 border hover:shadow-sm transition-all flex items-center gap-4 group",
                  !alert.acknowledged_at ? "border-red-100 hover:border-red-300" : "border-slate-100 hover:border-slate-200"
                )}>
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
                      <p className="font-semibold text-slate-900">{alert.patient_name}</p>
                      <span className={cn("badge text-xs", severityBadgeColor(alert.severity))}>{alert.severity}</span>
                      {alert.requires_acknowledgment && !alert.acknowledged_at && (
                        <span className="badge bg-red-100 text-red-700 text-xs">Action required</span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">{timeAgo(alert.generated_at)}</p>
                  </div>
                  {alert.acknowledged_at ? (
                    <span className="badge bg-green-100 text-green-700 text-xs flex-shrink-0">Acknowledged</span>
                  ) : (
                    <span className="badge bg-red-100 text-red-700 text-xs flex-shrink-0">Pending</span>
                  )}
                  <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-600 flex-shrink-0" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </PhysicianLayout>
  );
}
