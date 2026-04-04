"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Mic, MicOff, Send, Phone, PhoneOff, Volume2, VolumeX,
  Loader2,
} from "lucide-react";
import { patientApi } from "@/lib/api";
import { speakText } from "@/lib/cartesia";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import PatientLayout from "@/components/PatientLayout";

const WAKE_WORD = "maria";

/** Strip markdown so messages display and speak cleanly. */
function stripMarkdown(text: string): string {
  return text
    .replace(/⚠️[^\n]*\n*/g, "")
    .replace(/#{1,6}\s+/g, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/---+/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

type TranscriptEntry = {
  id: string;
  text: string;
  time: string;
          triggered: boolean; // true if this utterance activated Maria
};

type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
};

export default function ClinicPage() {
  const { user } = useAuthStore();
  const router = useRouter();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [micMuted, setMicMuted] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [wakeDetected, setWakeDetected] = useState(false);
  const [transcriptLog, setTranscriptLog] = useState<TranscriptEntry[]>([]);

  // Refs to avoid stale closures in recognition callbacks
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const transcriptLogEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);
  const sessionIdRef = useRef<string | null>(null);
  const isSpeakingRef = useRef(false);
  const micMutedRef = useRef(false);
  const loadingRef = useRef(false);
  // sendMessageRef breaks the circular dep: startRecognition no longer needs
  // sendMessage in its useCallback deps, so it stays stable forever.
  const sendMessageRef = useRef<(text?: string) => void>(() => {});
  // startRecognitionRef lets sendMessage's finally block call the latest version.
  const startRecognitionRef = useRef<() => void>(() => {});

  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
  useEffect(() => { micMutedRef.current = micMuted; }, [micMuted]);
  useEffect(() => { loadingRef.current = loading; }, [loading]);

  useEffect(() => {
    if (!user) router.push("/login");
  }, [user, router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    transcriptLogEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcriptLog]);

  // Stop recognition on unmount / session end
  useEffect(() => {
    return () => { recognitionRef.current?.stop(); };
  }, []);

  const addMessage = (role: Message["role"], content: string) => {
    setMessages((prev) => [
      ...prev,
      { id: Date.now().toString(), role, content, timestamp: new Date().toISOString() },
    ]);
  };

  const sendMessage = useCallback(async (text?: string) => {
    const content = (text ?? input).trim();
    const sid = sessionIdRef.current;
    if (!content || !sid || loadingRef.current) return;

    setInput("");
    setLiveTranscript("");
    setWakeDetected(false);
    addMessage("user", content);
    loadingRef.current = true;
    setLoading(true);

    // Pause recognition while Sarah thinks + speaks
    recognitionRef.current?.stop();

    try {
      const res = await patientApi.sendClinicTurn(sid, content);
      const agentContent = stripMarkdown(res.data.content);
      addMessage("assistant", agentContent);

      if (ttsEnabled) {
        isSpeakingRef.current = true;
        setTtsPlaying(true);
        try {
          await speakText(agentContent);
        } finally {
          // Always reset even if speakText throws — otherwise mic is blocked forever
          setTtsPlaying(false);
          isSpeakingRef.current = false;
        }
      }
    } catch {
      addMessage("assistant", "I'm having trouble right now. Please try again.");
    } finally {
      loadingRef.current = false;
      setLoading(false);
      // Use ref so we always call the latest version (avoids stale closure)
      if (sessionIdRef.current && !micMutedRef.current) {
        startRecognitionRef.current();
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input, ttsEnabled]);

  // Must be after sendMessage declaration to avoid TDZ error
  useEffect(() => { sendMessageRef.current = sendMessage; }, [sendMessage]);

  const startRecognition = useCallback(() => {
    const SR =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    if (!SR) return;

    try { recognitionRef.current?.stop(); } catch {}

    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event: any) => {
      if (isSpeakingRef.current || micMutedRef.current) return;

      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          const text = result[0].transcript.trim();
          if (!text) continue;

          const triggered = text.toLowerCase().includes(WAKE_WORD);
          const afterWake = triggered
            ? text.replace(/^.*?maria[,!?\s]*/i, "").trim()
            : "";

          // Always log to transcript history
          setTranscriptLog(prev => [...prev, {
            id: Date.now().toString(),
            text,
            time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
            triggered,
          }]);
          setLiveTranscript("");

          if (triggered) {
            setWakeDetected(true);
            if (afterWake.length > 2) {
              // Use ref so this closure always calls the latest sendMessage
              setTimeout(() => sendMessageRef.current(afterWake), 300);
            }
          }
        } else {
          interim += result[0].transcript;
          setLiveTranscript(interim);
        }
      }
    };

    recognition.onerror = (e: any) => {
      if (e.error === "no-speech" || e.error === "aborted") return;
      console.warn("Speech recognition error:", e.error);
    };

    // Continuously restart as long as session is active and mic isn't muted
    recognition.onend = () => {
      if (
        sessionIdRef.current &&
        !isSpeakingRef.current &&
        !micMutedRef.current &&
        !loadingRef.current
      ) {
        try { recognition.start(); } catch {}
      }
    };

    recognition.start();
    recognitionRef.current = recognition;
  // No deps — sendMessage is accessed via sendMessageRef.current, so this
  // function is created once and never recreated, preventing stale closures.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep forward-ref in sync so sendMessage's finally always calls the latest version
  useEffect(() => {
    startRecognitionRef.current = startRecognition;
  }, [startRecognition]);

  const startSession = async () => {
    setStarting(true);
    try {
      const res = await patientApi.startClinicSession({ audio_enabled: true });
      const sid = res.data.session_id;
      setSessionId(sid);
      sessionIdRef.current = sid;

      const greeting = "Hi, I'm Maria, your clinic companion. Just say my name to get started.";
      addMessage("assistant", greeting);

      // Speak the greeting inside the button-click context to unlock browser
      // autoplay for all subsequent speakText calls in this session.
      if (ttsEnabled) {
        isSpeakingRef.current = true;
        setTtsPlaying(true);
        try {
          await speakText(greeting);
        } finally {
          setTtsPlaying(false);
          isSpeakingRef.current = false;
        }
      }

      // Begin ambient listening after greeting finishes
      setTimeout(() => startRecognition(), 300);
    } catch (e: any) {
      addMessage("system", `Failed to start session: ${e.response?.data?.detail || e.message}`);
    } finally {
      setStarting(false);
    }
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

  const endSession = async () => {
    if (!sessionId) return;
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    try {
      await patientApi.endClinicSession(sessionId);
      addMessage("system", "Session ended. A summary has been saved. Thank you!");
    } catch {
      addMessage("system", "Session ended.");
    }
    setSessionId(null);
    sessionIdRef.current = null;
    setLiveTranscript("");
    setWakeDetected(false);
    setTranscriptLog([]);
  };

  const micStatusLabel = micMuted
    ? "Muted"
    : ttsPlaying
    ? "Maria is speaking…"
    : loading
    ? "Thinking…"
    : liveTranscript
    ? "Hearing you…"
    : "Listening for Maria…";

  const micStatusColor = micMuted
    ? "bg-slate-300"
    : ttsPlaying
    ? "bg-teal-400 animate-pulse"
    : loading
    ? "bg-amber-400 animate-pulse"
    : liveTranscript
    ? "bg-crosscure-500 animate-pulse"
    : "bg-green-400 animate-pulse";

  return (
    <PatientLayout>
      <div className="flex h-[calc(100vh-56px)] lg:h-screen max-w-5xl mx-auto">

        {/* ── Chat panel ── */}
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
                <h1 className="font-bold text-slate-900">Maria</h1>
                <p className="text-xs text-slate-400">
                  {sessionId ? "Clinic AI Companion · Active" : "Your Clinic AI Companion"}
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
                title="Toggle voice responses"
              >
                {ttsEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
              </button>
              {sessionId && (
                <button
                  onClick={endSession}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-50 border border-red-200 text-red-600 text-sm font-medium hover:bg-red-100 transition-all"
                >
                  <PhoneOff className="w-4 h-4" /> End session
                </button>
              )}
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-6 pb-8">
                <div className="w-20 h-20 rounded-full gradient-bg flex items-center justify-center shadow-lg">
                  <span className="text-white font-bold text-3xl">A</span>
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-900 mb-2">Meet Maria</h2>
                  <p className="text-slate-500 max-w-sm text-sm leading-relaxed">
                    Your AI clinic companion. Say{" "}
                    <span className="font-semibold text-crosscure-600">"Maria"</span> to activate
                    — she can recall your medications, symptoms, and help prepare questions for your doctor.
                  </p>
                </div>
                <div className="grid grid-cols-1 gap-2 w-full max-w-xs">
                  {[
                    "Maria, what medications am I taking?",
                    "Maria, what are my recent symptoms?",
                    "Maria, help me prepare for my doctor visit",
                  ].map((s) => (
                    <button
                      key={s}
                      onClick={() => { if (sessionId) sendMessage(s.replace(/^Maria, /i, "")); }}
                      className="text-sm text-left px-4 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-crosscure-50 hover:border-crosscure-200 text-slate-600 transition-all disabled:opacity-40"
                      disabled={!sessionId}
                    >
                      {s}
                    </button>
                  ))}
                </div>
                {!sessionId && (
                  <button className="btn-primary" onClick={startSession} disabled={starting}>
                    {starting
                      ? <><Loader2 className="w-4 h-4 animate-spin" /> Starting…</>
                      : <><Phone className="w-4 h-4" /> Start Session with Maria</>}
                  </button>
                )}
              </div>
            )}

            {messages.map((msg) => (
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
                    {[0, 1, 2].map((i) => (
                      <span key={i} className="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Manual text input (fallback) */}
          {sessionId && (
            <div className="bg-white border-t border-slate-100 px-4 py-3 flex-shrink-0">
              <div className="flex items-center gap-2">
                <input
                  ref={inputRef}
                  type="text"
                  className="input-field flex-1 text-sm"
                  placeholder="Or type a message and press Enter…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
                  disabled={loading}
                />
                <button
                  onClick={() => sendMessage()}
                  disabled={!input.trim() || loading}
                  className="w-9 h-9 rounded-xl gradient-bg text-white flex items-center justify-center flex-shrink-0 disabled:opacity-40 hover:opacity-90 transition-opacity"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ── Transcript sidebar ── */}
        {sessionId && (
          <div className="w-64 flex-shrink-0 border-l border-slate-100 bg-slate-50 flex flex-col">

            {/* Mic control + status */}
            <div className="p-4 border-b border-slate-100 bg-white space-y-3 flex-shrink-0">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Microphone</p>
              <button
                onClick={toggleMic}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl border-2 font-medium text-sm transition-all",
                  micMuted
                    ? "bg-slate-100 border-slate-200 text-slate-500 hover:bg-slate-200"
                    : "bg-crosscure-50 border-crosscure-300 text-crosscure-700 hover:bg-crosscure-100"
                )}
              >
                {micMuted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                {micMuted ? "Mic off — tap to enable" : "Mic on"}
              </button>
              <div className="flex items-center gap-2">
                <span className={cn("w-2 h-2 rounded-full flex-shrink-0", micStatusColor)} />
                <p className="text-xs text-slate-500">{micStatusLabel}</p>
              </div>
            </div>

            {/* Live interim transcript */}
            {(liveTranscript || wakeDetected || ttsPlaying) && (
              <div className="px-4 pt-3 flex-shrink-0 space-y-2">
                {liveTranscript && (
                  <div className="bg-white border border-crosscure-200 rounded-xl px-3 py-2">
                    <p className="text-xs text-slate-400 mb-1">Hearing…</p>
                    <p className="text-sm text-slate-700 leading-relaxed">{liveTranscript}</p>
                  </div>
                )}
                {wakeDetected && !liveTranscript && (
                  <div className="bg-crosscure-50 border border-crosscure-200 rounded-xl px-3 py-2 text-xs text-crosscure-700 font-medium">
                    Maria activated — listening for question…
                  </div>
                )}
                {ttsPlaying && (
                  <div className="bg-teal-50 border border-teal-200 rounded-xl px-3 py-2 flex items-center gap-2 text-xs text-teal-700">
                    <Volume2 className="w-3.5 h-3.5 animate-pulse flex-shrink-0" />
                    Maria is speaking…
                  </div>
                )}
              </div>
            )}

            {/* Transcript log (persistent, scrollable) */}
            <div className="flex-1 min-h-0 flex flex-col p-4 gap-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Transcript Log</p>
                {transcriptLog.length > 0 && (
                  <button
                    onClick={() => setTranscriptLog([])}
                    className="text-xs text-slate-300 hover:text-slate-500 transition-colors"
                  >
                    Clear
                  </button>
                )}
              </div>

              <div className="flex-1 min-h-0 overflow-y-auto space-y-2 pr-1">
                {transcriptLog.length === 0 ? (
                  <p className="text-xs text-slate-300 italic mt-2">
                    {micMuted ? "Microphone is off" : "Everything you say will be logged here…"}
                  </p>
                ) : (
                  transcriptLog.map(entry => (
                    <div
                      key={entry.id}
                      className={cn(
                        "rounded-lg px-2.5 py-2 text-xs leading-relaxed border",
                        entry.triggered
                          ? "bg-crosscure-50 border-crosscure-200 text-crosscure-800"
                          : "bg-white border-slate-200 text-slate-600"
                      )}
                    >
                      <div className="flex items-center justify-between gap-2 mb-0.5">
                        <span className={cn(
                          "font-semibold",
                          entry.triggered ? "text-crosscure-600" : "text-slate-400"
                        )}>
                          {entry.triggered ? "→ Maria" : "heard"}
                        </span>
                        <span className="text-slate-300 font-mono">{entry.time}</span>
                      </div>
                      <p>{entry.text}</p>
                    </div>
                  ))
                )}
                <div ref={transcriptLogEndRef} />
              </div>
            </div>

            {/* Waveform */}
            <div className="p-4 border-t border-slate-100 flex items-center justify-center gap-1.5 h-12 flex-shrink-0">
              {[0.35, 0.65, 1, 0.65, 0.35].map((scale, i) => (
                <span
                  key={i}
                  className={cn(
                    "w-1.5 rounded-full transition-all duration-150",
                    micMuted || ttsPlaying || loading
                      ? "bg-slate-200"
                      : liveTranscript
                      ? "bg-crosscure-400"
                      : "bg-slate-300"
                  )}
                  style={{
                    height:
                      !micMuted && !loading && !ttsPlaying && liveTranscript
                        ? `${scale * 28}px`
                        : "4px",
                  }}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </PatientLayout>
  );
}
