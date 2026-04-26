"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ChevronLeft, CheckCircle2, Loader2, AlertTriangle, Bell, User, Pill, TrendingDown, Activity } from "lucide-react";
import { physicianApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn, formatDatetime, severityColor } from "@/lib/utils";
import PhysicianLayout from "@/components/PhysicianLayout";

const SECTION_ICONS: Record<string, any> = {
  patient_snapshot: User,
  prescription_summary: Pill,
  expected_outcome: TrendingDown,
  observed_outcome: Activity,
  wearable_evidence: Activity,
  deviation_summary: AlertTriangle,
  suggested_actions: CheckCircle2,
};

const SECTION_TITLES: Record<string, string> = {
  patient_snapshot: "Patient Snapshot",
  prescription_summary: "Prescription Summary",
  expected_outcome: "Expected Outcome",
  observed_outcome: "Observed Outcome",
  wearable_evidence: "Wearable Evidence",
  deviation_summary: "Deviation Summary",
  suggested_actions: "Suggested Actions",
};

export default function AlertDetailPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const { alertId } = useParams();
  const [alert, setAlert] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [acknowledging, setAcknowledging] = useState(false);

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    physicianApi.getAlert(alertId as string).then((res) => {
      setAlert(res.data);
    }).finally(() => setLoading(false));
  }, [user, alertId, router]);

  const handleAcknowledge = async () => {
    setAcknowledging(true);
    try {
      await physicianApi.acknowledgeAlert(alertId as string);
      setAlert((a: any) => ({ ...a, acknowledged_at: new Date().toISOString() }));
    } finally {
      setAcknowledging(false);
    }
  };

  if (loading) return (
    <PhysicianLayout>
      <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-crosscure-500" /></div>
    </PhysicianLayout>
  );

  if (!alert) return (
    <PhysicianLayout>
      <div className="text-center py-20 text-slate-400">Alert not found</div>
    </PhysicianLayout>
  );

  const severityStyles: Record<string, string> = {
    severe: "border-red-300 bg-red-50",
    moderate: "border-orange-300 bg-orange-50",
    mild: "border-yellow-300 bg-yellow-50",
  };
  const severityStyle = severityStyles[alert.severity] || "border-slate-200 bg-slate-50";

  const severityTextColors: Record<string, string> = {
    severe: "text-red-700",
    moderate: "text-orange-700",
    mild: "text-yellow-700",
  };
  const severityTextColor = severityTextColors[alert.severity] || "text-slate-700";

  return (
    <PhysicianLayout>
      <div className="max-w-3xl mx-auto px-6 py-8">
        <button onClick={() => router.back()} className="flex items-center gap-2 text-slate-500 hover:text-slate-800 mb-6 text-sm">
          <ChevronLeft className="w-4 h-4" /> Back
        </button>

        {/* Header */}
        <div className={cn("rounded-3xl border p-6 mb-6", severityStyle)}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Bell className={cn("w-5 h-5", severityTextColor)} />
                <span className={cn("text-xs font-bold uppercase tracking-wide", severityTextColor)}>
                  {alert.severity} Therapy Alert
                </span>
                {alert.requires_acknowledgment && !alert.acknowledged_at && (
                  <span className="badge bg-red-200 text-red-800 text-xs">Action required</span>
                )}
              </div>
              <h1 className="text-2xl font-bold text-slate-900">{alert.patient_name}</h1>
              <p className="text-sm text-slate-500 mt-1">
                Generated {formatDatetime(alert.generated_at)}
              </p>
            </div>
            {alert.acknowledged_at ? (
              <div className="flex items-center gap-2 text-green-600 bg-white/80 border border-green-200 px-4 py-2 rounded-xl flex-shrink-0">
                <CheckCircle2 className="w-4 h-4" />
                <span className="text-sm font-medium">Acknowledged</span>
              </div>
            ) : (
              <button
                onClick={handleAcknowledge}
                className={cn(
                  "flex items-center gap-2 px-5 py-2 rounded-xl font-semibold text-sm transition-all flex-shrink-0",
                  alert.severity === "severe"
                    ? "bg-red-600 hover:bg-red-700 text-white shadow-sm"
                    : "btn-primary"
                )}
                disabled={acknowledging}
              >
                {acknowledging ? <Loader2 className="w-4 h-4 animate-spin" /> : <><CheckCircle2 className="w-4 h-4" /> Acknowledge</>}
              </button>
            )}
          </div>
        </div>

        {/* Sections */}
        <div className="space-y-4">
          {Object.entries(alert.sections || {}).map(([key, value]) => {
            if (!value) return null;
            const Icon = SECTION_ICONS[key] || Bell;
            const title = SECTION_TITLES[key] || key;
            return (
              <div key={key} className="bg-white rounded-2xl border border-slate-100 overflow-hidden">
                <div className="flex items-center gap-3 px-5 py-4 bg-slate-50/50 border-b border-slate-50">
                  <div className="w-8 h-8 rounded-lg bg-crosscure-100 flex items-center justify-center">
                    <Icon className="w-4 h-4 text-crosscure-600" />
                  </div>
                  <h2 className="font-semibold text-slate-900 text-sm">{title}</h2>
                </div>
                <div className="px-5 py-4">
                  {Array.isArray(value) ? (
                    <ul className="space-y-2">
                      {(value as string[]).map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                          <span className="w-5 h-5 rounded-full bg-crosscure-100 text-crosscure-700 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
                            {i + 1}
                          </span>
                          {item}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-slate-700 leading-relaxed">{value as string}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </PhysicianLayout>
  );
}
