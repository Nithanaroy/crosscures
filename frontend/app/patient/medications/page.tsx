"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Pill, Plus, Loader2, CheckCircle2, Clock } from "lucide-react";
import { patientApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn, formatDate } from "@/lib/utils";
import PatientLayout from "@/components/PatientLayout";

export default function MedicationsPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [prescriptions, setPrescriptions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    medication_name: "", dose: "", frequency: "",
    prescribing_physician: "", start_date: new Date().toISOString().split("T")[0],
  });

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    patientApi.getPrescriptions().then((res) => {
      setPrescriptions(res.data.prescriptions || []);
    }).finally(() => setLoading(false));
  }, [user, router]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await patientApi.createPrescription(form);
      const res = await patientApi.getPrescriptions();
      setPrescriptions(res.data.prescriptions || []);
      setShowAdd(false);
      setForm({ medication_name: "", dose: "", frequency: "", prescribing_physician: "", start_date: new Date().toISOString().split("T")[0] });
    } finally {
      setSaving(false);
    }
  };

  const statusColor: Record<string, string> = {
    monitoring: "bg-green-100 text-green-700",
    completed: "bg-slate-100 text-slate-600",
    deviated: "bg-red-100 text-red-700",
    abandoned: "bg-slate-100 text-slate-500",
  };

  return (
    <PatientLayout>
      <div className="max-w-3xl mx-auto px-4 py-8 lg:px-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="section-title text-2xl">Medications</h1>
            <p className="text-slate-400 text-sm mt-1">{prescriptions.filter(p => p.status === "monitoring").length} active</p>
          </div>
          <button className="btn-primary" onClick={() => setShowAdd(true)}>
            <Plus className="w-4 h-4" /> Add Medication
          </button>
        </div>

        {/* Add form */}
        {showAdd && (
          <div className="bg-white rounded-3xl border border-crosscure-200 shadow-lg p-6 mb-6 animate-fade-in">
            <h2 className="font-semibold text-slate-900 mb-5">Add New Medication</h2>
            <form onSubmit={handleAdd} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="label-text">Medication name *</label>
                  <input className="input-field" placeholder="e.g. Metformin" required
                    value={form.medication_name} onChange={(e) => setForm(f => ({ ...f, medication_name: e.target.value }))} />
                </div>
                <div>
                  <label className="label-text">Dose *</label>
                  <input className="input-field" placeholder="e.g. 500mg" required
                    value={form.dose} onChange={(e) => setForm(f => ({ ...f, dose: e.target.value }))} />
                </div>
                <div>
                  <label className="label-text">Frequency *</label>
                  <input className="input-field" placeholder="e.g. twice daily" required
                    value={form.frequency} onChange={(e) => setForm(f => ({ ...f, frequency: e.target.value }))} />
                </div>
                <div>
                  <label className="label-text">Prescribing physician</label>
                  <input className="input-field" placeholder="Dr. Smith"
                    value={form.prescribing_physician} onChange={(e) => setForm(f => ({ ...f, prescribing_physician: e.target.value }))} />
                </div>
                <div>
                  <label className="label-text">Start date *</label>
                  <input type="date" className="input-field" required
                    value={form.start_date} onChange={(e) => setForm(f => ({ ...f, start_date: e.target.value }))} />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" className="btn-secondary flex-1" onClick={() => setShowAdd(false)}>Cancel</button>
                <button type="submit" className="btn-primary flex-1" disabled={saving}>
                  {saving ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</> : "Add Medication"}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Prescriptions list */}
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-crosscure-500" /></div>
        ) : prescriptions.length === 0 ? (
          <div className="text-center py-16">
            <Pill className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-400">No medications on file</p>
            <button className="btn-primary mt-4" onClick={() => setShowAdd(true)}>
              <Plus className="w-4 h-4" /> Add first medication
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {prescriptions.map((rx) => (
              <div key={rx.id} className="bg-white rounded-2xl p-5 border border-slate-100 hover:border-crosscure-200 transition-all">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-violet-100 flex items-center justify-center flex-shrink-0">
                      <Pill className="w-6 h-6 text-violet-600" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-900 text-lg">{rx.medication_name}</p>
                      <p className="text-slate-600 text-sm">{rx.dose} — {rx.frequency}</p>
                      {rx.prescribing_physician && (
                        <p className="text-slate-400 text-xs mt-1">Prescribed by {rx.prescribing_physician}</p>
                      )}
                      <p className="text-slate-400 text-xs mt-0.5">
                        Started {formatDate(rx.start_date)} · Monitoring {rx.monitoring_duration_days} days
                      </p>
                    </div>
                  </div>
                  <span className={cn("badge text-xs flex-shrink-0", statusColor[rx.status] || "bg-slate-100 text-slate-600")}>
                    {rx.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </PatientLayout>
  );
}
