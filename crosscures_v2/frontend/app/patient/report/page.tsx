"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  HeartPulse, PhoneOff, Mic, MicOff, Volume2, VolumeX,
  Loader2, CheckCircle2, ChevronRight,
} from "lucide-react";
import { patientApi } from "@/lib/api";
import { speakText } from "@/lib/cartesia";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import PatientLayout from "@/components/PatientLayout";

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

export default function ReportPage() {
  const { user } = useAuthStore();
  const router = useRouter();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [micMuted, setMicMuted] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [questionsRemaining, setQuestionsRemaining] = useState(3);
  const [sessionComplete, setSessionComplete] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);

  // All state that needs to be read inside recognition callbacks uses refs
  // so closures never go stale.
  const sessionIdRef = useRef<string | null>(null);
  const isSpeakingRef = useRef(false);
  const micMutedRef = useRef(false);
  const loadingRef = useRef(false);
  const sessionCompleteRef = useRef(false);   // ← ref, not closure-captured state
  const pauseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingTextRef = useRef<string>("");

  // Keep refs in sync with state
  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
  useEffect(() => { micMutedRef.current = micMuted; }, [micMuted]);
  useEffect(() => { loadingRef.current = loading; }, [loading]);
  useEffect(() => {
    sessionCompleteRef.current = sessionComplete;
  }, [sessionComplete]);

  useEffect(() => { if (!user) router.push("/login"); }, [user, router]);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);
  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      if (pauseTimerRef.current) clearTimeout(pauseTimerRef.current);
    };
  }, []);

  const addMessage = (role: Message["role"], content: string) => {
    setMessages(prev => [
      ...prev,
      { id: Date.now().toString(), role, content, timestamp: new Date().toISOString() },
    ]);
  };

  // Forward-declare so sendMessage and startRecognition can reference each other
  const startRecognitionRef = useRef<() => void>(() => {});

  const sendMessage = useCallback(async (text: string) => {
    const sid = sessionIdRef.current;
    if (!text.trim() || !sid || loadingRef.current || sessionCompleteRef.current) return;

    setLiveTranscript("");
    addMessage("user", text);
    loadingRef.current = true;
    setLoading(true);
    recognitionRef.current?.stop();

    try {
      const res = await patientApi.sendHealthReportTurn(sid, text);
      const content = stripMarkdown(res.data.content);
      addMessage("assistant", content);

      if (res.data.questions_remaining !== undefined) {
        setQuestionsRemaining(res.data.questions_remaining);
      }
      if (res.data.session_complete) {
        setSessionComplete(true);
        sessionCompleteRef.current = true;
      }

      if (ttsEnabled) {
        isSpeakingRef.current = true;
        setTtsPlaying(true);
        try {
          await speakText(content);
        } finally {
          // Always reset speaking state even if speakText throws
          setTtsPlaying(false);
          isSpeakingRef.current = false;
        }
      }
    } catch {
      addMessage("assistant", "I'm sorry, I couldn't process that. Please try again.");
    } finally {
      loadingRef.current = false;
      setLoading(false);
      // Restart listening unless the session is done or mic is muted
      if (sessionIdRef.current && !micMutedRef.current && !sessionCompleteRef.current) {
        startRecognitionRef.current();
      }
    }
  }, [ttsEnabled]);

  /**
   * Accumulate final speech results and send only after 5 s of silence.
   * New words during the window are appended, not replaced.
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
      // Log real errors; ignore benign ones
      if (e.error !== "no-speech" && e.error !== "aborted") {
        console.warn("[Report STT] recognition error:", e.error);
      }
    };

    rec.onend = () => {
      // Use refs so this closure never goes stale
      if (
        sessionIdRef.current &&
        !isSpeakingRef.current &&
        !micMutedRef.current &&
        !loadingRef.current &&
        !sessionCompleteRef.current
      ) {
        try { rec.start(); } catch {}
      }
    };

    rec.start();
    recognitionRef.current = rec;
  }, [scheduleSend]);

  // Keep the forward-ref in sync so sendMessage's finally block always
  // calls the latest version of startRecognition.
  useEffect(() => {
    startRecognitionRef.current = startRecognition;
  }, [startRecognition]);

  const startSession = async () => {
    setStarting(true);
    try {
      const res = await patientApi.startHealthReportSession();
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
    } catch (e: any) {
      addMessage("system", `Could not start session: ${e.response?.data?.detail || e.message}`);
    } finally {
      setStarting(false);
    }
  };

  const endSession = async () => {
    if (pauseTimerRef.current) { clearTimeout(pauseTimerRef.current); pauseTimerRef.current = null; }
    pendingTextRef.current = "";
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    if (sessionId) {
      try { await patientApi.endHealthReportSession(sessionId); } catch {}
    }
    addMessage("system", "Report saved. Your doctor will review this before your appointment.");
    setSessionId(null);
    sessionIdRef.current = null;
    setLiveTranscript("");
  };

  const toggleMic = () => {
    const next = !micMuted;
    setMicMuted(next);
    micMutedRef.current = next;
    if (next) {
      recognitionRef.current?.stop();
      setLiveTranscript("");
    } else {
      startRecognition();
    }
  };

  const newReport = () => {
    if (pauseTimerRef.current) clearTimeout(pauseTimerRef.current);
    pendingTextRef.current = "";
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setMessages([]);
    setSessionId(null);
    sessionIdRef.current = null;
    setSessionComplete(false);
    sessionCompleteRef.current = false;
    setQuestionsRemaining(3);
    setLiveTranscript("");
  };

  const micStatus = micMuted ? "Muted"
    : ttsPlaying ? "Maria is speaking…"
    : loading ? "Thinking…"
    : liveTranscript ? "Hearing you…"
    : "Listening…";

  const micColor = micMuted ? "bg-slate-300"
    : ttsPlaying ? "bg-teal-400 animate-pulse"
    : loading ? "bg-amber-400 animate-pulse"
    : liveTranscript ? "bg-rose-500 animate-pulse"
    : "bg-green-400 animate-pulse";

  if (!user) return null;

  return (
    <PatientLayout>
      <div className="flex h-[calc(100vh-56px)] lg:h-screen max-w-4xl mx-auto">
        <div className="flex flex-col flex-1 min-w-0">

          {/* Header */}
          <div className="bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="w-10 h-10 rounded-xl bg-rose-100 flex items-center justify-center shadow-sm">
                  <HeartPulse className="w-5 h-5 text-rose-600" />
                </div>
                {sessionId && !sessionComplete && (
                  <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-500 rounded-full border-2 border-white" />
                )}
              </div>
              <div>
                <h1 className="font-bold text-slate-900">Report Health Condition</h1>
                <p className="text-xs text-slate-400">
                  {sessionComplete
                    ? "Report complete"
                    : sessionId
                    ? "Maria is listening · speak freely"
                    : "Describe a symptom or concern to Maria"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setTtsEnabled(!ttsEnabled)}
                className={cn(
                  "p-2 rounded-xl border transition-all",
                  ttsEnabled
                    ? "bg-rose-50 border-rose-200 text-rose-600"
                    : "bg-slate-50 border-slate-200 text-slate-400"
                )}
                title="Toggle voice"
              >
                {ttsEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
              </button>
              {sessionId && !sessionComplete && (
                <button
                  onClick={endSession}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-50 border border-red-200 text-red-600 text-sm font-medium hover:bg-red-100 transition-all"
                >
                  <PhoneOff className="w-4 h-4" /> End report
                </button>
              )}
              {sessionComplete && (
                <button
                  onClick={newReport}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm font-medium hover:bg-rose-100 transition-all"
                >
                  <HeartPulse className="w-4 h-4" /> New report
                </button>
              )}
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {messages.length === 0 && !starting && (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-6 pb-8">
                <div className="w-20 h-20 rounded-full bg-rose-100 flex items-center justify-center shadow-lg">
                  <HeartPulse className="w-10 h-10 text-rose-500" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-900 mb-2">Report a Health Concern</h2>
                  <p className="text-slate-500 max-w-sm text-sm leading-relaxed">
                    Speak naturally about any symptom or health concern. Maria will listen carefully
                    and ask up to 3 follow-up questions to document your condition for your doctor.
                  </p>
                </div>
                <div className="bg-rose-50 border border-rose-100 rounded-2xl p-4 max-w-sm text-left space-y-1.5">
                  {[
                    "Describe any symptom in your own words",
                    "Maria asks at most 3 clarifying questions",
                    "Your report is saved and shared with your doctor",
                  ].map(t => (
                    <div key={t} className="flex items-start gap-2 text-sm text-rose-700">
                      <ChevronRight className="w-4 h-4 flex-shrink-0 mt-0.5" />
                      {t}
                    </div>
                  ))}
                </div>
                <button
                  className="btn-primary"
                  style={{ backgroundColor: "#e11d48" }}
                  onClick={startSession}
                  disabled={starting}
                >
                  {starting
                    ? <><Loader2 className="w-4 h-4 animate-spin" /> Starting…</>
                    : <><HeartPulse className="w-4 h-4" /> Start Report</>}
                </button>
              </div>
            )}

            {starting && (
              <div className="flex flex-col items-center justify-center h-full gap-3">
                <Loader2 className="w-8 h-8 animate-spin text-rose-500" />
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
                  <div className="bg-green-50 border border-green-100 text-green-700 text-xs rounded-xl px-4 py-2 max-w-sm text-center flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
                    {msg.content}
                  </div>
                ) : (
                  <>
                    <div className={cn(
                      "w-8 h-8 rounded-xl flex-shrink-0 flex items-center justify-center text-sm font-bold",
                      msg.role === "user"
                        ? "bg-rose-500 text-white"
                        : "bg-rose-100 text-rose-700"
                    )}>
                      {msg.role === "user" ? "Y" : "A"}
                    </div>
                    <div className={cn(
                      "max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm",
                      msg.role === "user"
                        ? "bg-rose-500 text-white rounded-tr-none"
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
                <div className="w-8 h-8 rounded-xl bg-rose-100 flex items-center justify-center text-rose-700 text-sm font-bold flex-shrink-0">A</div>
                <div className="bg-white border border-slate-100 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm">
                  <div className="flex gap-1 items-center h-5">
                    {[0, 1, 2].map(i => (
                      <span key={i} className="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {sessionComplete && (
              <div className="flex justify-center py-4">
                <div className="bg-green-50 border border-green-200 rounded-2xl px-6 py-4 text-center max-w-sm">
                  <CheckCircle2 className="w-8 h-8 text-green-500 mx-auto mb-2" />
                  <p className="font-semibold text-green-800 text-sm">Report complete</p>
                  <p className="text-xs text-green-600 mt-1">Your doctor will review this before your visit.</p>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Mic bar */}
          {sessionId && !sessionComplete && (
            <div className="bg-white border-t border-slate-100 px-4 py-3 flex items-center gap-3 flex-shrink-0">
              <button
                onClick={toggleMic}
                className={cn(
                  "flex-shrink-0 w-9 h-9 rounded-xl border-2 flex items-center justify-center transition-all",
                  micMuted
                    ? "bg-slate-100 border-slate-200 text-slate-500"
                    : "bg-rose-50 border-rose-300 text-rose-700"
                )}
              >
                {micMuted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>
              <div className="flex-1 min-w-0">
                {liveTranscript ? (
                  <p className="text-sm text-slate-700 truncate italic">{liveTranscript}</p>
                ) : (
                  <p className="text-xs text-slate-400">{micStatus}</p>
                )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className={cn("w-2 h-2 rounded-full flex-shrink-0", micColor)} />
                {questionsRemaining < 3 && (
                  <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">
                    {questionsRemaining} question{questionsRemaining !== 1 ? "s" : ""} left
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </PatientLayout>
  );
}
