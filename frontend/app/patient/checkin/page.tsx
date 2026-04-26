"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight, Mic, MicOff, CheckCircle2, Loader2, Volume2 } from "lucide-react";
import { patientApi } from "@/lib/api";
import { speakText } from "@/lib/cartesia";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import PatientLayout from "@/components/PatientLayout";

type Question = {
  question_id: string;
  text: string;
  response_type: string;
  domain: string;
  source: string;
};

type Response = {
  question_id: string;
  value: any;
  answered_at: string;
  skipped: boolean;
};

export default function CheckinPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [responses, setResponses] = useState<Record<string, Response>>({});
  const [currentIdx, setCurrentIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [value, setValue] = useState<any>(null);
  const [recording, setRecording] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    patientApi.getTodayCheckin().then((res) => {
      const qs = res.data.questions || [];
      setQuestions(qs);
      if (res.data.existing_responses?.length > 0) {
        const existing: Record<string, Response> = {};
        res.data.existing_responses.forEach((r: Response) => { existing[r.question_id] = r; });
        setResponses(existing);
        if (res.data.completion_status === "completed") setDone(true);
      }
    }).finally(() => setLoading(false));
  }, [user, router]);

  useEffect(() => {
    if (!loading && questions.length > 0 && currentIdx < questions.length) {
      const q = questions[currentIdx];
      if (q) setValue(responses[q.question_id]?.value ?? null);
    }
  }, [currentIdx, questions, loading]);

  const currentQ = questions[currentIdx];
  const progress = questions.length > 0 ? ((Object.keys(responses).length) / questions.length) * 100 : 0;

  const handleAnswer = (val: any) => {
    setValue(val);
    if (!currentQ) return;
    setResponses((prev) => ({
      ...prev,
      [currentQ.question_id]: {
        question_id: currentQ.question_id,
        value: val,
        answered_at: new Date().toISOString(),
        skipped: false,
      },
    }));
  };

  const handleNext = () => {
    if (value !== null && value !== "" && currentQ) {
      setResponses((prev) => ({
        ...prev,
        [currentQ.question_id]: {
          question_id: currentQ.question_id,
          value,
          answered_at: new Date().toISOString(),
          skipped: false,
        },
      }));
    }
    setValue(null);
    if (currentIdx < questions.length - 1) {
      setCurrentIdx((i) => i + 1);
    } else {
      handleSubmit();
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const allResponses = Object.values(responses);
      if (currentQ && value !== null) {
        allResponses.push({ question_id: currentQ.question_id, value, answered_at: new Date().toISOString(), skipped: false });
      }
      await patientApi.submitCheckin({ responses: allResponses });
      setDone(true);
    } finally {
      setSubmitting(false);
    }
  };

  const handleVoiceInput = () => {
    const SR =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    if (!SR) {
      console.warn("SpeechRecognition not supported in this browser.");
      return;
    }

    // Stop if already recording
    if (recording) {
      recognitionRef.current?.stop();
      setRecording(false);
      return;
    }

    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = "en-US";

    let committed = "";

    rec.onresult = (e: any) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          committed += e.results[i][0].transcript;
        } else {
          interim += e.results[i][0].transcript;
        }
      }
      // Show live interim text while speaking; commit final result
      setValue((committed || interim).trim() || null);
    };

    rec.onerror = (e: any) => {
      if (e.error !== "no-speech" && e.error !== "aborted") {
        console.warn("[Checkin STT] error:", e.error);
      }
      setRecording(false);
      recognitionRef.current = null;
    };

    rec.onend = () => {
      if (committed.trim()) handleAnswer(committed.trim());
      setRecording(false);
      recognitionRef.current = null;
    };

    rec.start();
    recognitionRef.current = rec;
    setRecording(true);
  };

  const handleSpeak = async () => {
    if (!currentQ || speaking) return;
    setSpeaking(true);
    try {
      await speakText(currentQ.text);
    } finally {
      setSpeaking(false);
    }
  };

  if (loading) return (
    <PatientLayout>
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-crosscure-500" />
      </div>
    </PatientLayout>
  );

  if (done) return (
    <PatientLayout>
      <div className="max-w-lg mx-auto px-4 py-16 text-center">
        <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-6">
          <CheckCircle2 className="w-10 h-10 text-green-600" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900 mb-3">Check-in complete!</h1>
        <p className="text-slate-500 mb-8">
          Your responses have been saved. This data helps your care team track your health trends.
        </p>
        <div className="flex gap-3 justify-center">
          <button className="btn-secondary" onClick={() => router.push("/patient/home")}>Back to Home</button>
          <button className="btn-primary" onClick={() => router.push("/patient/clinic")}>Open Clinic</button>
        </div>
      </div>
    </PatientLayout>
  );

  if (!currentQ) return null;

  return (
    <PatientLayout>
      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Progress */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <h1 className="section-title">Daily Check-in</h1>
            <span className="text-sm text-slate-400">{currentIdx + 1} / {questions.length}</span>
          </div>
          <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full gradient-bg rounded-full transition-all duration-500"
              style={{ width: `${((currentIdx + 1) / questions.length) * 100}%` }}
            />
          </div>
          <div className="flex gap-2 mt-2">
            <span className="badge bg-crosscure-50 text-crosscure-600 text-xs capitalize">
              {currentQ.domain.replace("_", " ")}
            </span>
            {currentQ.source === "llm_generated" && (
              <span className="badge bg-violet-50 text-violet-600 text-xs">AI-generated</span>
            )}
          </div>
        </div>

        {/* Question card */}
        <div className="bg-white rounded-3xl shadow-sm border border-slate-100 p-8 mb-6">
          <div className="flex items-start justify-between gap-4 mb-8">
            <h2 className="text-xl font-semibold text-slate-900 leading-relaxed flex-1">
              {currentQ.text}
            </h2>
            <button
              onClick={handleSpeak}
              className={cn(
                "flex-shrink-0 p-2.5 rounded-xl border transition-all",
                speaking ? "bg-crosscure-100 border-crosscure-200" : "bg-slate-50 border-slate-200 hover:bg-crosscure-50"
              )}
              title="Read question aloud"
            >
              <Volume2 className={cn("w-5 h-5", speaking ? "text-crosscure-600 animate-pulse" : "text-slate-400")} />
            </button>
          </div>

          {/* Response controls */}
          {currentQ.response_type === "scale_1_10" && (
            <div className="space-y-4">
              <div className="flex justify-between text-xs text-slate-400 px-1">
                <span>1 — None/Minimal</span>
                <span>10 — Severe/Maximum</span>
              </div>
              <input
                type="range"
                min="1" max="10"
                value={value ?? 5}
                onChange={(e) => handleAnswer(parseInt(e.target.value))}
                className="w-full h-3 rounded-full appearance-none cursor-pointer accent-crosscure-600"
              />
              <div className="flex justify-center">
                <div className="w-14 h-14 rounded-2xl gradient-bg flex items-center justify-center text-white text-2xl font-bold shadow-lg">
                  {value ?? 5}
                </div>
              </div>
              <div className="grid grid-cols-10 gap-1 mt-2">
                {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                  <button
                    key={n}
                    onClick={() => handleAnswer(n)}
                    className={cn(
                      "h-9 rounded-lg text-sm font-semibold transition-all",
                      value === n
                        ? "gradient-bg text-white shadow-sm"
                        : "bg-slate-100 text-slate-600 hover:bg-crosscure-100 hover:text-crosscure-700"
                    )}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>
          )}

          {currentQ.response_type === "yes_no" && (
            <div className="grid grid-cols-2 gap-4">
              {["Yes", "No"].map((opt) => (
                <button
                  key={opt}
                  onClick={() => handleAnswer(opt)}
                  className={cn(
                    "py-4 rounded-2xl text-lg font-semibold border-2 transition-all",
                    value === opt
                      ? "border-crosscure-500 bg-crosscure-50 text-crosscure-700 shadow-sm"
                      : "border-slate-200 bg-white text-slate-700 hover:border-crosscure-300"
                  )}
                >
                  {opt === "Yes" ? "✓ Yes" : "✗ No"}
                </button>
              ))}
            </div>
          )}

          {currentQ.response_type === "free_text" && (
            <div className="space-y-4">
              <textarea
                className="input-field min-h-[100px] resize-none"
                placeholder="Type your answer here... or use voice input below"
                value={value ?? ""}
                onChange={(e) => handleAnswer(e.target.value)}
              />
              <div className="flex items-center gap-3">
                <button
                  onClick={handleVoiceInput}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2.5 rounded-xl border-2 font-medium text-sm transition-all",
                    recording
                      ? "border-red-500 bg-red-50 text-red-600"
                      : "border-crosscure-200 bg-crosscure-50 text-crosscure-700 hover:bg-crosscure-100"
                  )}
                >
                  {recording ? (
                    <><MicOff className="w-4 h-4" /> Stop recording</>
                  ) : (
                    <><Mic className="w-4 h-4" /> Voice input</>
                  )}
                </button>
                {recording && (
                  <span className="flex items-center gap-2 text-sm text-red-500">
                    <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                    Recording...
                  </span>
                )}
              </div>
            </div>
          )}

          {currentQ.response_type === "multiple_choice" && (
            <div className="grid grid-cols-2 gap-3">
              {["Never", "Sometimes", "Often", "Always"].map((opt) => (
                <button
                  key={opt}
                  onClick={() => handleAnswer(opt)}
                  className={cn(
                    "py-3 px-4 rounded-xl text-sm font-medium border-2 transition-all text-left",
                    value === opt
                      ? "border-crosscure-500 bg-crosscure-50 text-crosscure-700"
                      : "border-slate-200 bg-white text-slate-700 hover:border-crosscure-200"
                  )}
                >
                  {opt}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Navigation buttons */}
        <div className="flex gap-3">
          <button
            className="btn-secondary"
            onClick={() => { setValue(null); setCurrentIdx((i) => Math.max(0, i - 1)); }}
            disabled={currentIdx === 0}
          >
            <ChevronLeft className="w-4 h-4" /> Back
          </button>
          <button
            className="btn-secondary flex-none px-4"
            onClick={() => {
              setResponses((prev) => ({
                ...prev,
                [currentQ.question_id]: {
                  question_id: currentQ.question_id,
                  value: null,
                  answered_at: new Date().toISOString(),
                  skipped: true,
                },
              }));
              handleNext();
            }}
          >
            Skip
          </button>
          <button
            className="btn-primary flex-1"
            onClick={handleNext}
            disabled={submitting}
          >
            {submitting ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Submitting...</>
            ) : currentIdx < questions.length - 1 ? (
              <>Next <ChevronRight className="w-4 h-4" /></>
            ) : (
              <>Submit Check-in <CheckCircle2 className="w-4 h-4" /></>
            )}
          </button>
        </div>
      </div>
    </PatientLayout>
  );
}
