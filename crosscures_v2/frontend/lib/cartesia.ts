/**
 * Cartesia voice integration — STT and TTS using Cartesia's API.
 * STT: ink-whisper model via /audio/transcriptions
 * TTS: sonic-3 model via /tts/bytes (streamed)
 */

const CARTESIA_API_KEY = process.env.NEXT_PUBLIC_CARTESIA_API_KEY || '';
const CARTESIA_VERSION = process.env.NEXT_PUBLIC_CARTESIA_VERSION || '2026-03-01';
const CARTESIA_VOICE_ID = process.env.NEXT_PUBLIC_CARTESIA_VOICE_ID || '694f9389-aac1-45b6-b726-9d9369183238';
const CARTESIA_TTS_MODEL = process.env.NEXT_PUBLIC_CARTESIA_TTS_MODEL || 'sonic-3';
const CARTESIA_STT_MODEL = process.env.NEXT_PUBLIC_CARTESIA_STT_MODEL || 'ink-whisper';
const CARTESIA_BASE = 'https://api.cartesia.ai';

export interface TranscriptResult {
  text: string;
  confidence?: number;
}

/**
 * Transcribe audio blob using Cartesia ink-whisper.
 */
export async function transcribeAudio(audioBlob: Blob): Promise<TranscriptResult> {
  const formData = new FormData();
  formData.append('file', audioBlob, 'recording.webm');
  formData.append('model', CARTESIA_STT_MODEL);

  const response = await fetch(`${CARTESIA_BASE}/audio/transcriptions`, {
    method: 'POST',
    headers: {
      'X-API-Key': CARTESIA_API_KEY,
      'Cartesia-Version': CARTESIA_VERSION,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Cartesia STT error: ${error}`);
  }

  const data = await response.json();
  return {
    text: data.text || data.transcript || '',
    confidence: data.confidence,
  };
}

/**
 * Fetch the full text as a single PCM WAV buffer from Cartesia.
 * PCM has no codec — decodeAudioData handles it natively in every browser.
 * One request = no parallel-race failures, no sentence-split drops.
 */
async function fetchSpeechBuffer(text: string): Promise<ArrayBuffer> {
  const response = await fetch(`${CARTESIA_BASE}/tts/bytes`, {
    method: 'POST',
    headers: {
      'X-API-Key': CARTESIA_API_KEY,
      'Cartesia-Version': CARTESIA_VERSION,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model_id: CARTESIA_TTS_MODEL,
      transcript: text,
      voice: { mode: 'id', id: CARTESIA_VOICE_ID },
      output_format: {
        container: 'wav',
        encoding: 'pcm_f32le',
        sample_rate: 44100,
      },
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Cartesia TTS error ${response.status}: ${error}`);
  }

  return response.arrayBuffer();
}

/**
 * Keep the old URL-based export for any legacy callers.
 */
export async function synthesizeSpeech(text: string): Promise<string> {
  const buf = await fetchSpeechBuffer(text);
  const blob = new Blob([buf], { type: 'audio/wav' });
  return URL.createObjectURL(blob);
}

/**
 * Strip markdown and clean text before speaking.
 */
function prepareForSpeech(text: string): string {
  return text
    .replace(/⚠️[^\n]*\n*/g, '')
    .replace(/#{1,6}\s+/g, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/^[-*+]\s+/gm, '')
    .replace(/---+/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\n+/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

/**
 * Speak text via Cartesia TTS.
 *
 * Uses HTMLAudioElement (speaker output only) — NOT AudioContext.
 * AudioContext.resume() acquires the browser's shared audio session which
 * can silently revoke microphone access for SpeechRecognition running in
 * the same tab.  HTMLAudioElement uses only the output pipeline and never
 * touches microphone capture.
 *
 * PCM WAV is kept because audio.duration is exact (no codec, computed from
 * file size / sample rate), making the loadedmetadata fallback 100% reliable
 * even if the 'ended' event fires late.
 */
export async function speakText(text: string): Promise<void> {
  const cleaned = prepareForSpeech(text);
  if (!cleaned) return;

  let rawBuffer: ArrayBuffer;
  try {
    rawBuffer = await fetchSpeechBuffer(cleaned);
  } catch (e) {
    console.error('[TTS] synthesis failed:', e);
    return;
  }

  const blob = new Blob([rawBuffer], { type: 'audio/wav' });
  const url = URL.createObjectURL(blob);

  await new Promise<void>((resolve) => {
    const audio = new Audio(url);
    let settled = false;

    const finish = () => {
      if (settled) return;
      settled = true;
      URL.revokeObjectURL(url);
      resolve();
    };

    audio.addEventListener('ended', finish);
    audio.addEventListener('error', finish);

    // PCM WAV duration is always accurate — use it as a hard deadline so
    // the promise never hangs if 'ended' fires late (+1 s buffer).
    audio.addEventListener('loadedmetadata', () => {
      if (isFinite(audio.duration) && audio.duration > 0) {
        setTimeout(finish, (audio.duration + 1) * 1000);
      }
    });

    // Absolute ceiling in case loadedmetadata never fires (e.g. empty buffer)
    setTimeout(finish, 300_000);

    audio.play().catch(finish);
  });
}

/**
 * Real-time speech-to-text using the browser's native SpeechRecognition API.
 * Calls onInterim with partial results as the user speaks,
 * and onFinal with the committed transcript when a phrase is complete.
 * Returns a stop() function.
 */
export function startLiveTranscription({
  onInterim,
  onFinal,
  onError,
}: {
  onInterim: (text: string) => void;
  onFinal: (text: string) => void;
  onError?: (err: string) => void;
}): () => void {
  const SR =
    (window as any).SpeechRecognition ||
    (window as any).webkitSpeechRecognition;

  if (!SR) {
    onError?.('SpeechRecognition is not supported in this browser. Please use Chrome or Edge.');
    return () => {};
  }

  const recognition: any = new SR();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  let finalTranscript = '';

  recognition.onresult = (event: any) => {
    let interim = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      if (result.isFinal) {
        finalTranscript += result[0].transcript;
        onFinal(finalTranscript.trim());
      } else {
        interim += result[0].transcript;
      }
    }
    onInterim((finalTranscript + interim).trim());
  };

  recognition.onerror = (event: any) => {
    if (event.error !== 'no-speech') {
      onError?.(event.error);
    }
  };

  recognition.start();
  return () => {
    recognition.stop();
  };
}

/**
 * Record audio from microphone and return as a Blob.
 */
export function createAudioRecorder() {
  let mediaRecorder: MediaRecorder | null = null;
  let chunks: Blob[] = [];

  return {
    async start() {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = [];
      
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/ogg';
      
      mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };
      mediaRecorder.start(100);
      return stream;
    },

    stop(): Promise<Blob> {
      return new Promise((resolve) => {
        if (!mediaRecorder) { resolve(new Blob()); return; }
        mediaRecorder.onstop = () => {
          const blob = new Blob(chunks, { type: mediaRecorder!.mimeType });
          resolve(blob);
        };
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach((t) => t.stop());
      });
    },

    get isRecording() {
      return mediaRecorder?.state === 'recording';
    },
  };
}
