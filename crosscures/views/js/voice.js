import { state } from './state.js';

const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;

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
    supported: !!SpeechRecognitionCtor && !!window.speechSynthesis,
    enabled: false,
    recognition: null,
    isListening: false,
    lastQuestionId: null,
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

function speak(text, onEnd = null) {
    if (!voiceState.supported || !voiceState.enabled || !text) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.onend = () => {
        if (typeof onEnd === 'function') {
            onEnd();
        }
    };
    window.speechSynthesis.speak(utterance);
}

function ensureRecognition() {
    if (!voiceState.supported || voiceState.recognition) return;

    voiceState.recognition = new SpeechRecognitionCtor();
    voiceState.recognition.lang = 'en-US';
    voiceState.recognition.interimResults = false;
    voiceState.recognition.maxAlternatives = 1;

    voiceState.recognition.onresult = (event) => {
        voiceState.isListening = false;
        const transcript = event.results?.[0]?.[0]?.transcript || '';
        if (!transcript) {
            setStatus('No speech detected. Please try again.');
            startVoiceInput();
            return;
        }
        handleTranscript(transcript);
    };

    voiceState.recognition.onerror = () => {
        voiceState.isListening = false;
        setStatus('Voice recognition error. Please try again.');
    };

    voiceState.recognition.onend = () => {
        voiceState.isListening = false;
        if (voiceState.enabled) {
            const msg = document.getElementById('voiceStatus')?.textContent || '';
            if (msg.startsWith('Listening')) {
                setStatus('Listening stopped. Trying again...');
                startVoiceInput();
            }
        }
    };
}

export function initVoiceControls() {
    const panel = document.getElementById('voiceControls');
    if (!panel) return;

    panel.style.display = 'block';

    if (!voiceState.supported) {
        setStatus('Voice is not supported in this browser.');
        return;
    }

    ensureRecognition();
    voiceState.enabled = true;
    setButtonState();
    setStatus('Voice mode enabled. Questions will be read automatically.');
}

export function toggleVoiceMode() {
    if (!voiceState.supported) return;
    voiceState.enabled = !voiceState.enabled;
    setButtonState();

    if (voiceState.enabled) {
        setStatus('Voice mode enabled. Click Read Question or Speak Answer.');
    } else {
        window.speechSynthesis.cancel();
        setStatus('Voice mode is off.');
    }
}

export function startVoiceInput() {
    if (!voiceState.supported || !voiceState.enabled || !voiceState.recognition) return;
    if (voiceState.isListening) return;

    setStatus('Listening...');
    voiceState.isListening = true;
    try {
        voiceState.recognition.start();
    } catch {
        voiceState.isListening = false;
        setStatus('Microphone is already active.');
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
