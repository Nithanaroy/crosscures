import { state } from './state.js';
import { API_BASE_URL } from './state.js';

const numberWords = {
    one: 1,
    two: 2,
    three: 3,
    four: 4,
    five: 5,
    six: 6,
    seven: 7,
    eight: 8,
    nine: 9,
    ten: 10,
};

const voiceState = {
    supported: !!window.MediaRecorder && !!navigator.mediaDevices?.getUserMedia,
    enabled: false,
    mediaStream: null,
    recorder: null,
    chunks: [],
    isListening: false,
    maxRecordTimer: null,
    silenceCheckTimer: null,
    lastQuestionId: null,
    voiceAgentWs: null,
    voiceAgentReady: false,
    voiceAgentInitStarted: false,
};

function setStatus(message) {
    const el = document.getElementById('voiceStatus');
    if (el) el.textContent = message;
}

function setButtonState() {
    const toggleBtn = document.getElementById('voiceToggleBtn');
    const listenBtn = document.getElementById('voiceListenBtn');
    const readBtn = document.getElementById('voiceReadBtn');

    if (!toggleBtn || !listenBtn || !readBtn) return;

    toggleBtn.textContent = voiceState.enabled ? 'Disable Voice' : 'Enable Voice';
    listenBtn.disabled = !voiceState.enabled;
    readBtn.disabled = !voiceState.enabled;
}

async function postTTS(text) {
    const resp = await fetch(`${API_BASE_URL}/voice/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, language: 'en' }),
    });
    if (!resp.ok) {
        const err = await resp.text();
        throw new Error(err || 'TTS failed');
    }
    return resp.blob();
}

async function postSTT(blob) {
    const form = new FormData();
    form.append('file', blob, 'answer.webm');

    const resp = await fetch(`${API_BASE_URL}/voice/stt`, {
        method: 'POST',
        body: form,
    });
    if (!resp.ok) {
        const err = await resp.text();
        throw new Error(err || 'STT failed');
    }

    const data = await resp.json();
    return (data.text || '').trim();
}

function wsBaseFromApiBase(apiBase) {
    if (apiBase.startsWith('https://')) return `wss://${apiBase.slice(8)}`;
    if (apiBase.startsWith('http://')) return `ws://${apiBase.slice(7)}`;
    return apiBase;
}

async function initVoiceAgentSession() {
    if (voiceState.voiceAgentInitStarted) return;
    voiceState.voiceAgentInitStarted = true;

    try {
        const callId = `web-${Date.now()}`;
        const resp = await fetch(`${API_BASE_URL}/voice-agent/chats`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                call_id: callId,
                from: 'web-user',
                to: 'crosscures',
                agent_call_id: callId,
                agent: {
                    system_prompt: 'You are a voice check-in assistant. Keep responses concise.',
                    introduction: 'Hello, we are starting your check-in.',
                },
                metadata: {
                    source: 'crosscures-web',
                },
            }),
        });

        if (!resp.ok) {
            throw new Error(await resp.text());
        }

        const data = await resp.json();
        const wsUrl = `${wsBaseFromApiBase(API_BASE_URL)}/voice-agent${data.websocket_url}`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            voiceState.voiceAgentReady = true;
            voiceState.voiceAgentWs = ws;
        };

        ws.onclose = () => {
            voiceState.voiceAgentReady = false;
            voiceState.voiceAgentWs = null;
        };

        ws.onerror = () => {
            voiceState.voiceAgentReady = false;
            voiceState.voiceAgentWs = null;
        };
    } catch (error) {
        console.error('VoiceAgent session init failed:', error);
    }
}

function sendTranscriptToVoiceAgent(transcript) {
    if (!voiceState.voiceAgentReady || !voiceState.voiceAgentWs) return;
    try {
        voiceState.voiceAgentWs.send(JSON.stringify({ type: 'user_state', value: 'speaking' }));
        voiceState.voiceAgentWs.send(JSON.stringify({ type: 'message', content: transcript }));
        voiceState.voiceAgentWs.send(JSON.stringify({ type: 'user_state', value: 'idle' }));
    } catch (error) {
        console.error('VoiceAgent send failed:', error);
    }
}

function extractScaleValue(transcript) {
    const digitMatch = transcript.match(/\b([1-9]|10)\b/);
    if (digitMatch) return Number(digitMatch[1]);

    for (const [word, value] of Object.entries(numberWords)) {
        if (transcript.includes(word)) return value;
    }

    return null;
}

function autoSubmitCurrentAnswer() {
    // Let the UI update selected state before submitting.
    setTimeout(() => {
        if (typeof window._submitResponse === 'function') {
            window._submitResponse();
        }
    }, 150);
}

function handleTranscript(rawTranscript) {
    if (!state.currentQuestion) return;

    sendTranscriptToVoiceAgent(rawTranscript);

    const transcript = rawTranscript.toLowerCase().trim();
    const q = state.currentQuestion;

    if (q.question_type === 'yes_no') {
        if (transcript.includes('yes')) {
            window._recordResponse(true, 'Yes');
            setStatus('Captured answer: Yes');
            autoSubmitCurrentAnswer();
            return;
        }
        if (transcript.includes('no')) {
            window._recordResponse(false, 'No');
            setStatus('Captured answer: No');
            autoSubmitCurrentAnswer();
            return;
        }
    }

    if (q.question_type === 'scale_1_10') {
        const value = extractScaleValue(transcript);
        if (value !== null) {
            window._recordResponse(value, String(value));
            setStatus(`Captured answer: ${value}`);
            autoSubmitCurrentAnswer();
            return;
        }
    }

    if (q.question_type === 'multiple_choice' && Array.isArray(q.options)) {
        const option = q.options.find(o => transcript.includes(o.toLowerCase()));
        if (option) {
            window._recordResponse(option, option);
            setStatus(`Captured answer: ${option}`);
            autoSubmitCurrentAnswer();
            return;
        }
    }

    if (q.question_type === 'text') {
        const input = document.getElementById('textInput');
        if (input) {
            input.value = rawTranscript.trim();
            setStatus('Captured answer in text field');
            autoSubmitCurrentAnswer();
            return;
        }
    }

    setStatus('Could not map that voice answer. Please try again.');
    startVoiceInput();
}

async function ensureMicStream() {
    if (voiceState.mediaStream) return voiceState.mediaStream;
    voiceState.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    return voiceState.mediaStream;
}

function stopTimers() {
    if (voiceState.maxRecordTimer) {
        clearTimeout(voiceState.maxRecordTimer);
        voiceState.maxRecordTimer = null;
    }
    if (voiceState.silenceCheckTimer) {
        clearInterval(voiceState.silenceCheckTimer);
        voiceState.silenceCheckTimer = null;
    }
}

async function beginRecording() {
    const stream = await ensureMicStream();
    voiceState.chunks = [];
    voiceState.recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

    let hasSpeech = false;
    let lastSpeechAt = Date.now();

    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);

    voiceState.recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
            voiceState.chunks.push(event.data);
        }
    };

    voiceState.recorder.onstop = async () => {
        stopTimers();
        await audioContext.close();
        voiceState.isListening = false;

        const blob = new Blob(voiceState.chunks, { type: 'audio/webm' });
        if (blob.size === 0) {
            setStatus('No audio captured. Listening again...');
            startVoiceInput();
            return;
        }

        setStatus('Transcribing...');
        try {
            const transcript = await postSTT(blob);
            if (!transcript) {
                setStatus('No transcript received. Listening again...');
                startVoiceInput();
                return;
            }
            setStatus(`Heard: ${transcript}`);
            handleTranscript(transcript);
        } catch (error) {
            console.error('STT failed:', error);
            setStatus('STT failed. Listening again...');
            startVoiceInput();
        }
    };

    voiceState.recorder.start(250);
    voiceState.isListening = true;

    voiceState.maxRecordTimer = setTimeout(() => {
        if (voiceState.recorder && voiceState.recorder.state === 'recording') {
            voiceState.recorder.stop();
        }
    }, 12000);

    voiceState.silenceCheckTimer = setInterval(() => {
        analyser.getByteFrequencyData(data);
        const avg = data.reduce((sum, v) => sum + v, 0) / data.length;

        if (avg > 14) {
            hasSpeech = true;
            lastSpeechAt = Date.now();
        }

        if (hasSpeech && Date.now() - lastSpeechAt > 1100) {
            if (voiceState.recorder && voiceState.recorder.state === 'recording') {
                voiceState.recorder.stop();
            }
        }
    }, 160);
}

async function speak(text, onEnd = null) {
    if (!voiceState.supported || !voiceState.enabled || !text) return;
    try {
        setStatus('Generating speech...');
        const blob = await postTTS(text);
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);

        audio.onended = () => {
            URL.revokeObjectURL(url);
            if (typeof onEnd === 'function') onEnd();
        };
        audio.onerror = () => {
            URL.revokeObjectURL(url);
            setStatus('Audio playback failed.');
            if (typeof onEnd === 'function') onEnd();
        };

        await audio.play();
    } catch (error) {
        console.error('TTS failed:', error);
        setStatus('TTS failed.');
        if (typeof onEnd === 'function') onEnd();
    }
}

async function checkVoiceAgentStatus() {
    try {
        const resp = await fetch(`${API_BASE_URL}/voice-agent/status`);
        return resp.ok;
    } catch {
        return false;
    }
}

export async function initVoiceControls() {
    const panel = document.getElementById('voiceControls');
    if (!panel) return;

    panel.style.display = 'block';

    if (!voiceState.supported) {
        setStatus('Microphone recording is not supported in this browser.');
        return;
    }

    voiceState.enabled = false;
    setButtonState();
    setStatus('Voice mode is off. Click "Enable Voice" to activate.');
}

export async function toggleVoiceMode() {
    if (!voiceState.supported) return;
    voiceState.enabled = !voiceState.enabled;
    setButtonState();

    if (voiceState.enabled) {
        setStatus('Enabling voice...');
        const agentUp = await checkVoiceAgentStatus();
        if (agentUp && !voiceState.voiceAgentReady) {
            await initVoiceAgentSession();
            setStatus('Voice mode enabled with VoiceAgent + Cartesia.');
        } else if (agentUp) {
            setStatus('Voice mode enabled with VoiceAgent + Cartesia.');
        } else {
            setStatus('Voice mode enabled with Cartesia. VoiceAgent status unavailable.');
        }
    } else {
        if (voiceState.recorder && voiceState.recorder.state === 'recording') {
            voiceState.recorder.stop();
        }
        stopTimers();
        setStatus('Voice mode is off.');
    }
}

export async function startVoiceInput() {
    if (!voiceState.supported || !voiceState.enabled) return;
    if (voiceState.isListening) return;

    setStatus('Listening...');
    try {
        await beginRecording();
    } catch (error) {
        voiceState.isListening = false;
        console.error('Recording failed:', error);
        setStatus('Microphone error. Please allow microphone access.');
    }
}

export function speakCurrentQuestion() {
    if (!state.currentQuestion) return;
    speak(state.currentQuestion.question_text);
}

export function onQuestionDisplayed() {
    if (!voiceState.enabled || !state.currentQuestion) return;

    const questionId = state.currentQuestion.question_id;
    if (voiceState.lastQuestionId === questionId) {
        return;
    }

    voiceState.lastQuestionId = questionId;
    speak(state.currentQuestion.question_text, () => {
        startVoiceInput();
    });
}
