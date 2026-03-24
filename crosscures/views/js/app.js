import { resetState } from './state.js';
import { loadDataSourceInfo, loadPatients, loadGeneratorStatus, selectMode, selectModel } from './patients.js';
import { recordResponse, submitResponse } from './questionnaire.js';
import { toggleTreePanel, resetTreePanel } from './tree.js';
import { hidePatientBanner } from './banner.js';

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
window._completeQuestionnaire = async () => {
    const { completeQuestionnaire } = await import('./summary.js');
    await completeQuestionnaire();
};
window._backToPatients = backToPatients;
window._startOver = backToPatients;
window._toggleTreePanel = toggleTreePanel;
window._selectMode = selectMode;
window._selectModel = selectModel;

// Boot
async function init() {
    await loadDataSourceInfo();
    await loadGeneratorStatus();
    await loadPatients();
}

init();
