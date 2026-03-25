// export const API_BASE_URL = 'http://localhost:8000';
export const API_BASE_URL = window.location.origin;

export const state = {
    currentPatient: null,
    currentSessionId: null,
    currentQuestion: null,
    sessionData: null,
    allResponses: {},
    answeredCount: 0,
    submitting: false,
    questionTree: [],
    answeredQuestions: {},
    skippedQuestions: new Set(),
    treePanelOpen: false,
    generatorMode: 'static',
    selectedModel: null,
    availableModels: [],
    reasoningHistory: [],
};

export function showLoadingOverlay(message) {
    const overlay = document.getElementById('loadingOverlay');
    const text = document.getElementById('loadingOverlayText');
    if (text) text.textContent = message || 'Processing...';
    if (overlay) overlay.classList.add('active');
}

export function hideLoadingOverlay() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.remove('active');
}

export function showError(message) {
    const banner = document.getElementById('errorBanner');
    const text = document.getElementById('errorBannerText');
    if (text) text.textContent = message;
    if (banner) banner.style.display = 'block';
}

export function hideError() {
    const banner = document.getElementById('errorBanner');
    if (banner) banner.style.display = 'none';
}

export function resetState() {
    state.currentSessionId = null;
    state.currentQuestion = null;
    state.allResponses = {};
    state.answeredCount = 0;
    state.questionTree = [];
    state.answeredQuestions = {};
    state.skippedQuestions = new Set();
    state.treePanelOpen = false;
    state.reasoningHistory = [];
}
