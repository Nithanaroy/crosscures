"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { FileText, ChevronRight, Loader2 } from "lucide-react";
import { physicianApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn, timeAgo, getInitials } from "@/lib/utils";
import PhysicianLayout from "@/components/PhysicianLayout";

export default function BriefsPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [patients, setPatients] = useState<any[]>([]);
  const [allBriefs, setAllBriefs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    physicianApi.getPatients().then(async (res) => {
      const pts = res.data.patients || [];
      setPatients(pts);
      const briefPromises = pts.map((p: any) =>
        physicianApi.getPatientBriefs(p.id).then((r) =>
          (r.data.briefs || []).map((b: any) => ({ ...b, patient_name: p.full_name, patient_id: p.id }))
        ).catch(() => [])
      );
      const results = await Promise.all(briefPromises);
      const combined = results.flat().sort((a, b) =>
        new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime()
      );
      setAllBriefs(combined);
    }).finally(() => setLoading(false));
  }, [user, router]);

  return (
    <PhysicianLayout>
      <div className="max-w-4xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">Patient Briefs</h1>
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-crosscure-500" /></div>
        ) : allBriefs.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-3xl border border-slate-100">
            <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-400">No briefs generated yet</p>
          </div>
        ) : (
          <div className="space-y-3">
            {allBriefs.map((brief) => (
              <Link key={brief.brief_id} href={`/physician/briefs/${brief.brief_id}`}>
                <div className="bg-white rounded-2xl p-4 border border-slate-100 hover:border-crosscure-200 hover:shadow-sm transition-all flex items-center gap-4 group">
                  <div className="w-10 h-10 rounded-full bg-teal-100 flex items-center justify-center text-teal-700 font-bold text-sm flex-shrink-0">
                    {getInitials(brief.patient_name || "?")}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-slate-900">{brief.patient_name}</p>
                    <p className="text-xs text-slate-400">Pre-visit brief · {timeAgo(brief.generated_at)}</p>
                  </div>
                  {brief.acknowledged_at ? (
                    <span className="badge bg-green-100 text-green-700 text-xs flex-shrink-0">Acknowledged</span>
                  ) : (
                    <span className="badge bg-amber-100 text-amber-700 text-xs flex-shrink-0">Unread</span>
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
