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

export function resetState() {
    state.currentSessionId = null;
    state.currentQuestion = null;
    state.allResponses = {};
    state.answeredCount = 0;
    state.questionTree = [];
    state.answeredQuestions = {};
    state.skippedQuestions = new Set();
    state.treePanelOpen = false;
    state.generatorMode = 'static';
    state.selectedModel = null;
    state.reasoningHistory = [];
}
