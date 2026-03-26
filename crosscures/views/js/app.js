import { resetState } from './state.js';
import { loadDataSourceInfo, loadPatients, loadGeneratorStatus, selectMode, selectModel } from './patients.js';
import { recordResponse, submitResponse, saveNotes } from './questionnaire.js';
import { toggleTreePanel, resetTreePanel } from './tree.js';
import { hidePatientBanner } from './banner.js';
import { initVoiceControls, toggleVoiceMode, startVoiceInput, speakCurrentQuestion } from './voice.js';

export function switchSection(sectionId) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.getElementById(sectionId).classList.add('active');
}

function backToPatients() {
    resetState();
    hidePatientBanner();
    resetTreePanel();
    switchSection('patientSection');
}

// Expose handlers for inline onclick attributes
window._recordResponse = recordResponse;
window._submitResponse = submitResponse;
window._saveNotes = saveNotes;
window._completeQuestionnaire = async () => {
    const { completeQuestionnaire } = await import('./summary.js');
    await completeQuestionnaire();
};
window._backToPatients = backToPatients;
window._startOver = backToPatients;
window._toggleTreePanel = toggleTreePanel;
window._selectMode = selectMode;
window._selectModel = selectModel;
window._toggleVoiceMode = toggleVoiceMode;
window._startVoiceInput = startVoiceInput;
window._speakCurrentQuestion = speakCurrentQuestion;

// Boot
async function init() {
    await initVoiceControls();
    await loadDataSourceInfo();
    await loadGeneratorStatus();
    await loadPatients();
}

init();
