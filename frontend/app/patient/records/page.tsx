"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { FileText, Upload, Loader2, AlertCircle, CheckCircle2, ChevronRight, Filter } from "lucide-react";
import { patientApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn, formatDate } from "@/lib/utils";
import PatientLayout from "@/components/PatientLayout";

const RESOURCE_TYPES = ["All", "Condition", "MedicationRequest", "Observation", "DiagnosticReport", "AllergyIntolerance", "Procedure", "Encounter", "DocumentReference"];

const RESOURCE_ICONS: Record<string, string> = {
  Condition: "🏥", MedicationRequest: "💊", MedicationStatement: "💊",
  Observation: "🔬", DiagnosticReport: "📋", AllergyIntolerance: "⚠️",
  Procedure: "🩺", Encounter: "🏨", DocumentReference: "📄", default: "📁",
};

export default function RecordsPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [filter, setFilter] = useState("All");
  const [uploadResult, setUploadResult] = useState<any>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    fetchRecords();
  }, [user, router]);

  const fetchRecords = async () => {
    setLoading(true);
    try {
      const res = await patientApi.getRecords();
      setRecords(res.data.records || []);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("source_name", file.name.replace(/\.[^/.]+$/, ""));
      const res = await patientApi.uploadRecords(formData);
      setUploadResult(res.data);
      await fetchRecords();
    } catch (e: any) {
      setUploadResult({ error: e.response?.data?.detail || "Upload failed" });
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const filtered = filter === "All" ? records : records.filter((r) => r.resource_type === filter);

  return (
    <PatientLayout>
      <div className="max-w-4xl mx-auto px-4 py-8 lg:px-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="section-title text-2xl">Health Records</h1>
            <p className="text-slate-400 text-sm mt-1">{records.length} records on file</p>
          </div>
          <div>
            <input
              ref={fileRef}
              type="file"
              accept=".json,.pdf,.txt"
              className="hidden"
              onChange={handleUpload}
            />
            <button
              className="btn-primary"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Uploading...</>
              ) : (
                <><Upload className="w-4 h-4" /> Upload Records</>
              )}
            </button>
          </div>
        </div>

        {/* Upload result */}
        {uploadResult && (
          <div className={cn(
            "rounded-2xl p-4 mb-6 border flex items-start gap-3",
            uploadResult.error
              ? "bg-red-50 border-red-200 text-red-700"
              : "bg-green-50 border-green-200 text-green-700"
          )}>
            {uploadResult.error ? <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" /> : <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" />}
            <div className="text-sm">
              {uploadResult.error ? (
                uploadResult.error
              ) : (
                <>
                  <p className="font-semibold">Upload successful!</p>
                  <p>{uploadResult.records_extracted} records extracted{uploadResult.warnings?.length > 0 ? `, ${uploadResult.warnings.length} warnings` : ""}</p>
                </>
              )}
            </div>
          </div>
        )}

        {/* Upload area */}
        <div
          className="border-2 border-dashed border-slate-200 rounded-2xl p-8 mb-6 text-center cursor-pointer hover:border-crosscure-300 hover:bg-crosscure-50/50 transition-all"
          onClick={() => fileRef.current?.click()}
        >
          <div className="w-12 h-12 rounded-2xl bg-crosscure-100 flex items-center justify-center mx-auto mb-3">
            <Upload className="w-6 h-6 text-crosscure-600" />
          </div>
          <p className="text-slate-700 font-medium">Upload health records</p>
          <p className="text-slate-400 text-sm mt-1">FHIR R4 JSON bundles, PDFs, or clinical notes</p>
          <p className="text-xs text-slate-300 mt-2">All files are encrypted and processed securely</p>
        </div>

        {/* Filters */}
        <div className="flex gap-2 flex-wrap mb-5">
          {RESOURCE_TYPES.map((type) => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={cn(
                "px-3.5 py-1.5 rounded-full text-xs font-medium border transition-all",
                filter === type
                  ? "bg-crosscure-600 text-white border-crosscure-600 shadow-sm"
                  : "bg-white text-slate-600 border-slate-200 hover:border-crosscure-300"
              )}
            >
              {type}
            </button>
          ))}
        </div>

        {/* Records list */}
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-crosscure-500" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-400">No records found</p>
            <p className="text-slate-300 text-sm mt-1">Upload your first health record above</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((record) => (
              <div
                key={record.id}
                className="bg-white rounded-2xl p-4 border border-slate-100 hover:border-crosscure-200 hover:shadow-sm transition-all flex items-center gap-4"
              >
                <div className="w-11 h-11 rounded-xl bg-slate-50 flex items-center justify-center text-xl flex-shrink-0">
                  {RESOURCE_ICONS[record.resource_type] || RESOURCE_ICONS.default}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-900 truncate">{record.display_text}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="badge bg-slate-100 text-slate-600 text-xs">{record.resource_type}</span>
                    {record.occurred_at && (
                      <span className="text-xs text-slate-400">{formatDate(record.occurred_at)}</span>
                    )}
                    {record.source_name && (
                      <span className="text-xs text-slate-400 truncate hidden sm:block">{record.source_name}</span>
                    )}
                    {record.confidence < 1 && (
                      <span className="badge bg-amber-50 text-amber-600 text-xs">
                        {Math.round(record.confidence * 100)}% confidence
                      </span>
                    )}
                  </div>
                </div>
                {record.flags?.length > 0 && (
                  <div className="flex gap-1 flex-shrink-0">
                    {record.flags.slice(0, 2).map((f: string) => (
                      <span key={f} className="badge bg-amber-50 text-amber-600 text-xs">{f.replace("_", " ")}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </PatientLayout>
  );
}
