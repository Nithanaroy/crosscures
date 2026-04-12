"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ChevronLeft, CheckCircle2, Loader2, FileText, User, Calendar, Activity, Pill, Heart, MessageSquare } from "lucide-react";
import { physicianApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn, formatDatetime } from "@/lib/utils";
import PhysicianLayout from "@/components/PhysicianLayout";

const SECTION_ICONS: Record<string, any> = {
  patient_summary: User,
  patient_snapshot: User,
  symptom_trends: Activity,
  wearable_highlights: Heart,
  medication_adherence: Pill,
  patient_concerns: MessageSquare,
  suggested_discussion_points: MessageSquare,
};

const SECTION_TITLES: Record<string, string> = {
  patient_summary: "Patient Summary for Physician",
  patient_snapshot: "Patient Snapshot",
  symptom_trends: "Symptom Trends (14 days)",
  wearable_highlights: "Wearable Highlights",
  medication_adherence: "Medication Adherence",
  patient_concerns: "Patient Concerns",
  suggested_discussion_points: "Suggested Discussion Points",
};

export default function BriefDetailPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const { briefId } = useParams();
  const [brief, setBrief] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [acknowledging, setAcknowledging] = useState(false);

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    physicianApi.getBrief(briefId as string).then((res) => {
      setBrief(res.data);
    }).finally(() => setLoading(false));
  }, [user, briefId, router]);

  const handleAcknowledge = async () => {
    setAcknowledging(true);
    try {
      await physicianApi.acknowledgeBrief(briefId as string);
      setBrief((b: any) => ({ ...b, acknowledged_at: new Date().toISOString() }));
    } finally {
      setAcknowledging(false);
    }
  };

  if (loading) return (
    <PhysicianLayout>
      <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-crosscure-500" /></div>
    </PhysicianLayout>
  );

  if (!brief) return (
    <PhysicianLayout>
      <div className="text-center py-20 text-slate-400">Brief not found</div>
    </PhysicianLayout>
  );

  return (
    <PhysicianLayout>
      <div className="max-w-3xl mx-auto px-6 py-8">
        <button onClick={() => router.back()} className="flex items-center gap-2 text-slate-500 hover:text-slate-800 mb-6 text-sm">
          <ChevronLeft className="w-4 h-4" /> Back
        </button>

        {/* Header */}
        <div className="bg-white rounded-3xl border border-slate-100 p-6 mb-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <FileText className="w-5 h-5 text-teal-600" />
                <span className="text-xs font-semibold text-teal-600 uppercase tracking-wide">Pre-Visit Brief</span>
              </div>
              <h1 className="text-2xl font-bold text-slate-900">{brief.patient_name}</h1>
              <p className="text-sm text-slate-400 mt-1">
                Generated {formatDatetime(brief.generated_at)}
              </p>
            </div>
            {brief.acknowledged_at ? (
              <div className="flex items-center gap-2 text-green-600 bg-green-50 border border-green-200 px-4 py-2 rounded-xl">
                <CheckCircle2 className="w-4 h-4" />
                <span className="text-sm font-medium">Acknowledged</span>
              </div>
            ) : (
              <button
                onClick={handleAcknowledge}
                className="btn-primary py-2 px-5 text-sm"
                disabled={acknowledging}
              >
                {acknowledging ? <Loader2 className="w-4 h-4 animate-spin" /> : <><CheckCircle2 className="w-4 h-4" /> Acknowledge</>}
              </button>
            )}
          </div>
        </div>

        {/* Sections */}
        <div className="space-y-4">
          {Object.entries(brief.sections || {}).map(([key, value]) => {
            if (!value) return null;
            const Icon = SECTION_ICONS[key] || FileText;
            const title = SECTION_TITLES[key] || key;
            return (
              <div key={key} className="bg-white rounded-2xl border border-slate-100 overflow-hidden">
                <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-50 bg-slate-50/50">
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
                    <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">{value as string}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* HIPAA notice */}
        <p className="text-xs text-slate-300 text-center mt-6">
          This brief was generated by CrossCures AI from patient-reported data. It does not constitute a diagnosis. Verify with the patient.
        </p>
      </div>
    </PhysicianLayout>
  );
}
