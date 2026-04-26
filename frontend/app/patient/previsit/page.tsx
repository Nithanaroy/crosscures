"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  PhoneCall, PhoneOff, Mic, MicOff, Calendar, Clock, Volume2,
  VolumeX, Loader2, Check, Plus, ChevronRight,
} from "lucide-react";
import { patientApi } from "@/lib/api";
import { speakText } from "@/lib/cartesia";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import PatientLayout from "@/components/PatientLayout";

/** Strip markdown for clean TTS. */
function stripMarkdown(text: string): string {
  return text
    .replace(/#{1,6}\s+/g, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/---+/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
};

type Slot = {
  slot_id: string;
  scheduled_at: string;
  duration_minutes: number;
  status: string;
  session_id: string | null;
  appointment_id: string | null;
};

function formatSlotTime(iso: string) {
  return new Date(iso).toLocaleString("en-US", {
    weekday: "short", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

function slotStatusBadge(status: string) {
  const map: Record<string, string> = {
    scheduled: "bg-blue-100 text-blue-700",
    in_progress: "bg-amber-100 text-amber-700",
    completed: "bg-green-100 text-green-700",
    cancelled: "bg-slate-100 text-slate-500",
  };
  return map[status] ?? "bg-slate-100 text-slate-500";
}

export default function PrevisitPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const searchParams = useSearchParams();

  // ── Scheduling ──
  const [slots, setSlots] = useState<Slot[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(true);
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleTime, setScheduleTime] = useState("10:00");
  const [scheduling, setScheduling] = useState(false);
  const [view, setView] = useState<"list" | "call">("list");

  // ── Active call ──
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [micMuted, setMicMuted] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const sessionIdRef = useRef<string | null>(null);
  const isSpeakingRef = useRef(false);
  const micMutedRef = useRef(false);
  const loadingRef = useRef(false);
  const mounted = useRef(false);
  const pauseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingTextRef = useRef<string>("");
  // Forward-ref so sendMessage's finally block always calls the latest startRecognition
  const startRecognitionRef = useRef<() => void>(() => {});

  useEffect(() => { mounted.current = true; }, []);
  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
  useEffect(() => { micMutedRef.current = micMuted; }, [micMuted]);
  useEffect(() => { loadingRef.current = loading; }, [loading]);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  useEffect(() => { return () => { recognitionRef.current?.stop(); }; }, []);

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    patientApi.getPrevisitSlots()
      .then(r => setSlots(r.data.slots || []))
      .catch(() => {})
      .finally(() => setSlotsLoading(false));

    // Auto-start call if navigated with ?start=1
    if (searchParams.get("start") === "1") {
      setView("call");
    }
  }, [user, router, searchParams]);

  const addMessage = (role: Message["role"], content: string) => {
    setMessages(prev => [
      ...prev,
      { id: Date.now().toString(), role, content, timestamp: new Date().toISOString() },
    ]);
  };

  const sendMessage = useCallback(async (text: string) => {
    const sid = sessionIdRef.current;
    if (!text.trim() || !sid || loadingRef.current) return;

    setLiveTranscript("");
    addMessage("user", text);
    loadingRef.current = true;
    setLoading(true);
    recognitionRef.current?.stop();

    try {
      const res = await patientApi.sendPrevisitTurn(sid, text);
      const content = stripMarkdown(res.data.content);
      addMessage("assistant", content);

      if (ttsEnabled) {
        isSpeakingRef.current = true;
        setTtsPlaying(true);
        try {
          await speakText(content);
        } finally {
          setTtsPlaying(false);
          isSpeakingRef.current = false;
        }
      }
    } catch {
      addMessage("assistant", "I'm sorry, I'm having a little trouble. Please try again.");
    } finally {
      loadingRef.current = false;
      setLoading(false);
      if (sessionIdRef.current && !micMutedRef.current) startRecognitionRef.current();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ttsEnabled]);

  /**
   * Accumulate final speech results and send only after 2 s of silence.
   * Any new words during the window are appended, not replaced.
   */
  const scheduleSend = useCallback((text: string) => {
    pendingTextRef.current = pendingTextRef.current
      ? `${pendingTextRef.current} ${text}`
      : text;
    if (pauseTimerRef.current) clearTimeout(pauseTimerRef.current);
    pauseTimerRef.current = setTimeout(() => {
      const t = pendingTextRef.current.trim();
      pendingTextRef.current = "";
      if (t) sendMessage(t);
    }, 3500);
  }, [sendMessage]);

  const startRecognition = useCallback(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    try { recognitionRef.current?.stop(); } catch {}

    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";

    rec.onresult = (e: any) => {
      if (isSpeakingRef.current || micMutedRef.current) return;
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          const text = e.results[i][0].transcript.trim();
          if (text) scheduleSend(text);
        } else {
          interim += e.results[i][0].transcript;
        }
      }
      setLiveTranscript(interim);
    };

    rec.onerror = (e: any) => {
      if (e.error !== "no-speech" && e.error !== "aborted") {
        console.warn("[Previsit STT] recognition error:", e.error);
      }
    };

    rec.onend = () => {
      if (sessionIdRef.current && !isSpeakingRef.current && !micMutedRef.current && !loadingRef.current) {
        try { rec.start(); } catch {}
      }
    };

    rec.start();
    recognitionRef.current = rec;
  }, [scheduleSend]);

  // Keep forward-ref in sync
  useEffect(() => {
    startRecognitionRef.current = startRecognition;
  }, [startRecognition]);

  const startCall = async (slotId?: string) => {
    setStarting(true);
    setView("call");
    try {
      const res = await patientApi.startPrevisitSession(slotId ? { slot_id: slotId } : {});
      const sid = res.data.session_id;
      const firstMsg = res.data.initial_message;
      setSessionId(sid);
      sessionIdRef.current = sid;
      addMessage("assistant", firstMsg);

      if (ttsEnabled) {
        isSpeakingRef.current = true;
        setTtsPlaying(true);
        try {
          await speakText(firstMsg);
        } finally {
          setTtsPlaying(false);
          isSpeakingRef.current = false;
        }
      }
      setTimeout(() => startRecognition(), 300);

      // Refresh slots
      patientApi.getPrevisitSlots().then(r => setSlots(r.data.slots || [])).catch(() => {});
    } catch (e: any) {
      addMessage("system", `Could not start session: ${e.response?.data?.detail || e.message}`);
    } finally {
      setStarting(false);
    }
  };

  const endCall = async () => {
    if (pauseTimerRef.current) { clearTimeout(pauseTimerRef.current); pauseTimerRef.current = null; }
    pendingTextRef.current = "";
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    if (sessionId) {
      try { await patientApi.endPrevisitSession(sessionId); } catch {}
    }
    addMessage("system", "Pre-visit call completed. Your responses have been saved for your doctor.");
    setSessionId(null);
    sessionIdRef.current = null;
    setLiveTranscript("");
    patientApi.getPrevisitSlots().then(r => setSlots(r.data.slots || [])).catch(() => {});
  };

  const toggleMic = () => {
    const next = !micMuted;
    setMicMuted(next);
    micMutedRef.current = next;
    if (next) { recognitionRef.current?.stop(); setLiveTranscript(""); }
    else startRecognition();
  };

  const scheduleCall = async () => {
    if (!scheduleDate || !scheduleTime) return;
    setScheduling(true);
    try {
      const iso = new Date(`${scheduleDate}T${scheduleTime}`).toISOString();
      await patientApi.schedulePrevisit({ scheduled_at: iso });
      const r = await patientApi.getPrevisitSlots();
      setSlots(r.data.slots || []);
      setScheduleDate("");
    } catch (e: any) {
      alert(e.response?.data?.detail || "Failed to schedule");
    } finally {
      setScheduling(false);
    }
  };

  // Min date: today + 0, rounded guidance
  const today = new Date();
  const minDate = today.toISOString().split("T")[0];
  const maxDate = new Date(today.getTime() + 14 * 86400000).toISOString().split("T")[0];

  const micStatus = micMuted
    ? "Muted"
    : ttsPlaying ? "Maria is speaking…"
    : loading ? "Thinking…"
    : liveTranscript ? "Hearing you…"
    : "Listening…";

  const micColor = micMuted
    ? "bg-slate-300"
    : ttsPlaying ? "bg-teal-400 animate-pulse"
    : loading ? "bg-amber-400 animate-pulse"
    : liveTranscript ? "bg-crosscure-500 animate-pulse"
    : "bg-green-400 animate-pulse";

  if (!user) return null;

  // ── Call view ────────────────────────────────────────────────────────────────
  if (view === "call") {
    return (
      <PatientLayout>
        <div className="flex h-[calc(100vh-56px)] lg:h-screen max-w-4xl mx-auto">
          <div className="flex flex-col flex-1 min-w-0">
            {/* Header */}
            <div className="bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <div className="w-10 h-10 rounded-xl gradient-bg flex items-center justify-center shadow-sm">
                    <span className="text-white font-bold text-lg">A</span>
                  </div>
                  {sessionId && (
                    <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-500 rounded-full border-2 border-white" />
                  )}
                </div>
                <div>
                  <h1 className="font-bold text-slate-900">Maria — Pre-Visit Call</h1>
                  <p className="text-xs text-slate-400">
                    {sessionId ? "Live · Structured intake interview" : "Pre-Visit AI Assistant"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setTtsEnabled(!ttsEnabled)}
                  className={cn(
                    "p-2 rounded-xl border transition-all",
                    ttsEnabled
                      ? "bg-crosscure-50 border-crosscure-200 text-crosscure-600"
                      : "bg-slate-50 border-slate-200 text-slate-400"
                  )}
                  title="Toggle voice"
                >
                  {ttsEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
                </button>
                {sessionId && (
                  <button
                    onClick={endCall}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-50 border border-red-200 text-red-600 text-sm font-medium hover:bg-red-100 transition-all"
                  >
                    <PhoneOff className="w-4 h-4" /> End call
                  </button>
                )}
                {!sessionId && (
                  <button
                    onClick={() => setView("list")}
                    className="text-sm text-slate-500 hover:text-slate-700 transition-colors px-3 py-2"
                  >
                    ← Back
                  </button>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {messages.length === 0 && !starting && (
                <div className="flex flex-col items-center justify-center h-full text-center space-y-5 pb-8">
                  <div className="w-20 h-20 rounded-full gradient-bg flex items-center justify-center shadow-lg">
                    <span className="text-white font-bold text-3xl">A</span>
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-slate-900 mb-2">Start Pre-Visit Call with Maria</h2>
                    <p className="text-slate-500 max-w-sm text-sm leading-relaxed">
                      Maria will conduct a structured 15-minute intake interview to prepare your doctor for your visit.
                    </p>
                  </div>
                  <button className="btn-primary" onClick={() => startCall()} disabled={starting}>
                    {starting
                      ? <><Loader2 className="w-4 h-4 animate-spin" /> Starting…</>
                      : <><PhoneCall className="w-4 h-4" /> Start Call</>}
                  </button>
                </div>
              )}

              {starting && (
                <div className="flex flex-col items-center justify-center h-full gap-3">
                  <Loader2 className="w-8 h-8 animate-spin text-crosscure-500" />
                  <p className="text-slate-500 text-sm">Connecting to Maria…</p>
                </div>
              )}

              {messages.map(msg => (
                <div
                  key={msg.id}
                  className={cn(
                    "flex gap-3 animate-fade-in",
                    msg.role === "user" ? "flex-row-reverse" : "flex-row",
                    msg.role === "system" ? "justify-center" : ""
                  )}
                >
                  {msg.role === "system" ? (
                    <div className="bg-slate-100 text-slate-500 text-xs rounded-xl px-4 py-2 max-w-sm text-center">
                      {msg.content}
                    </div>
                  ) : (
                    <>
                      <div className={cn(
                        "w-8 h-8 rounded-xl flex-shrink-0 flex items-center justify-center text-sm font-bold",
                        msg.role === "user" ? "gradient-bg text-white" : "bg-teal-100 text-teal-700"
                      )}>
                        {msg.role === "user" ? "Y" : "A"}
                      </div>
                      <div className={cn(
                        "max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm",
                        msg.role === "user"
                          ? "gradient-bg text-white rounded-tr-none"
                          : "bg-white border border-slate-100 text-slate-800 rounded-tl-none"
                      )}>
                        {msg.content}
                      </div>
                    </>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex gap-3 animate-fade-in">
                  <div className="w-8 h-8 rounded-xl bg-teal-100 flex items-center justify-center text-teal-700 text-sm font-bold flex-shrink-0">A</div>
                  <div className="bg-white border border-slate-100 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm">
                    <div className="flex gap-1 items-center h-5">
                      {[0, 1, 2].map(i => (
                        <span key={i} className="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                      ))}
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Live transcript + mic status bar */}
            {sessionId && (
              <div className="bg-white border-t border-slate-100 px-4 py-3 flex items-center gap-3 flex-shrink-0">
                <button
                  onClick={toggleMic}
                  className={cn(
                    "flex-shrink-0 w-9 h-9 rounded-xl border-2 flex items-center justify-center transition-all",
                    micMuted
                      ? "bg-slate-100 border-slate-200 text-slate-500"
                      : "bg-crosscure-50 border-crosscure-300 text-crosscure-700"
                  )}
                >
                  {micMuted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
                <div className="flex-1 min-w-0">
                  {liveTranscript ? (
                    <p className="text-sm text-slate-700 truncate">{liveTranscript}</p>
                  ) : (
                    <p className="text-xs text-slate-400">{micStatus}</p>
                  )}
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <span className={cn("w-2 h-2 rounded-full", micColor)} />
                  {ttsPlaying && <Volume2 className="w-4 h-4 text-teal-500 animate-pulse" />}
                </div>
              </div>
            )}
          </div>
        </div>
      </PatientLayout>
    );
  }

  // ── List / Schedule view ─────────────────────────────────────────────────────
  return (
    <PatientLayout>
      <div className="max-w-3xl mx-auto px-4 py-8 lg:px-8 space-y-8">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Pre-Visit Call</h1>
            <p className="text-slate-500 mt-1 text-sm">
              Book a 15-minute call with Maria to prepare your doctor before your appointment
            </p>
          </div>
          <button
            onClick={() => startCall()}
            className="btn-primary flex items-center gap-2 flex-shrink-0"
            disabled={starting}
          >
            {starting
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Starting…</>
              : <><PhoneCall className="w-4 h-4" /> Start Call Now</>}
          </button>
        </div>

        {/* Schedule a new slot */}
        <div className="metric-card">
          <h2 className="section-title mb-4 flex items-center gap-2">
            <Calendar className="w-4 h-4 text-crosscure-500" />
            Schedule a Slot
          </h2>
          <p className="text-sm text-slate-500 mb-4">
            Book your call up to 7 days in advance. Each slot is 15 minutes. 
            We recommend scheduling 48–72 hours before your appointment.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="date"
              min={minDate}
              max={maxDate}
              value={scheduleDate}
              onChange={e => setScheduleDate(e.target.value)}
              className="input-field flex-1"
            />
            <input
              type="time"
              value={scheduleTime}
              onChange={e => setScheduleTime(e.target.value)}
              className="input-field w-36"
            />
            <button
              onClick={scheduleCall}
              disabled={!scheduleDate || scheduling}
              className="btn-primary flex items-center gap-2 flex-shrink-0 disabled:opacity-40"
            >
              {scheduling
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Plus className="w-4 h-4" />}
              Book slot
            </button>
          </div>
        </div>

        {/* Scheduled slots */}
        <div>
          <h2 className="section-title mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-400" />
            Your Scheduled Slots
          </h2>

          {slotsLoading ? (
            <div className="flex items-center gap-3 text-slate-400 py-4">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading…
            </div>
          ) : slots.length === 0 ? (
            <div className="metric-card text-center py-8 text-slate-400">
              <PhoneCall className="w-8 h-8 mx-auto mb-3 opacity-30" />
              <p className="text-sm">No slots scheduled yet.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {slots.map(slot => (
                <div
                  key={slot.slot_id}
                  className="metric-card flex items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-crosscure-50 flex items-center justify-center flex-shrink-0">
                      <PhoneCall className="w-5 h-5 text-crosscure-500" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-900 text-sm">{formatSlotTime(slot.scheduled_at)}</p>
                      <p className="text-xs text-slate-400">{slot.duration_minutes} min · Pre-Visit Call</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className={cn("badge text-xs", slotStatusBadge(slot.status))}>
                      {slot.status === "in_progress" ? "In progress" : slot.status.charAt(0).toUpperCase() + slot.status.slice(1)}
                    </span>
                    {(slot.status === "scheduled" || slot.status === "in_progress") && (
                      <button
                        onClick={() => startCall(slot.slot_id)}
                        className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1"
                        disabled={starting}
                      >
                        {starting ? <Loader2 className="w-3 h-3 animate-spin" /> : <PhoneCall className="w-3 h-3" />}
                        Start
                      </button>
                    )}
                    {slot.status === "completed" && (
                      <span className="flex items-center gap-1 text-xs text-green-600">
                        <Check className="w-3 h-3" /> Done
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Info card */}
        <div className="bg-teal-50 border border-teal-100 rounded-2xl p-5">
          <h3 className="font-semibold text-teal-900 text-sm mb-2">What to expect</h3>
          <ul className="text-sm text-teal-700 space-y-1.5">
            {[
              "Maria will ask about your reason for the visit and current symptoms",
              "She'll collect your medication history, allergies, and past medical history",
              "The call takes 10–15 minutes and you can speak naturally",
              "All information is shared with your doctor before your appointment",
            ].map(t => (
              <li key={t} className="flex items-start gap-2">
                <ChevronRight className="w-4 h-4 flex-shrink-0 mt-0.5 text-teal-500" />
                {t}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </PatientLayout>
  );
}
