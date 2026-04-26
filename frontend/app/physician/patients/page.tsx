"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Users, Bell, FileText, ChevronRight, Loader2, AlertTriangle } from "lucide-react";
import { physicianApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn, getInitials, timeAgo } from "@/lib/utils";
import PhysicianLayout from "@/components/PhysicianLayout";

export default function PatientsPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [patients, setPatients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    physicianApi.getPatients().then((res) => {
      setPatients(res.data.patients || []);
    }).finally(() => setLoading(false));
  }, [user, router]);

  return (
    <PhysicianLayout>
      <div className="max-w-4xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">Patients</h1>
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-crosscure-500" /></div>
        ) : patients.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-3xl border border-slate-100">
            <Users className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500 font-medium">No linked patients yet</p>
            <p className="text-slate-400 text-sm mt-1">Patients can link you by adding your email in their app settings</p>
          </div>
        ) : (
          <div className="space-y-3">
            {patients.map((patient) => (
              <Link key={patient.id} href={`/physician/patients/${patient.id}`}>
                <div className="bg-white rounded-2xl p-5 border border-slate-100 hover:border-crosscure-200 hover:shadow-sm transition-all flex items-center gap-4 group">
                  <div className="w-12 h-12 rounded-full bg-crosscure-100 flex items-center justify-center text-crosscure-700 font-bold text-sm flex-shrink-0">
                    {getInitials(patient.full_name)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-slate-900">{patient.full_name}</p>
                    <p className="text-sm text-slate-400">{patient.email} · Linked {timeAgo(patient.linked_at)}</p>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    {patient.unacknowledged_alert_count > 0 && (
                      <span className="flex items-center gap-1 badge bg-red-100 text-red-700">
                        <AlertTriangle className="w-3 h-3" />
                        {patient.unacknowledged_alert_count} alert{patient.unacknowledged_alert_count > 1 ? "s" : ""}
                      </span>
                    )}
                    {patient.brief_count > 0 && (
                      <span className="flex items-center gap-1 badge bg-teal-50 text-teal-700">
                        <FileText className="w-3 h-3" />
                        {patient.brief_count} brief{patient.brief_count > 1 ? "s" : ""}
                      </span>
                    )}
                    <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-600 transition-colors" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </PhysicianLayout>
  );
}
