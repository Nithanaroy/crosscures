import { state } from './state.js';
import { showLoadingOverlay, hideLoadingOverlay, showError, hideError } from './state.js';
import { fetchPatients, fetchDataSource, fetchGeneratorStatus, initializeSession } from './api.js';
import { renderPatientBanner } from './banner.js';
import { renderSidePanel } from './tree.js';
import { displayQuestion } from './questionnaire.js';
import { switchSection } from './app.js';

export async function loadDataSourceInfo() {
    try {
        const data = await fetchDataSource();
        const infoDiv = document.getElementById('dataSourceInfo');
        infoDiv.textContent = `Data Source: ${data.provider_type.toUpperCase()} - ${data.description}`;
    } catch (error) {
        console.error('Error loading data source:', error);
    }
}

export async function loadGeneratorStatus() {
    try {
        const status = await fetchGeneratorStatus();
        const toggle = document.getElementById('modeToggle');
        if (!toggle) return;

        // Cloud LLM button
        const llmBtn = toggle.querySelector('[data-mode="llm"]');
        if (llmBtn) {
            if (status.llm) {
                llmBtn.disabled = false;
                llmBtn.title = '';
            } else {
                llmBtn.disabled = true;
                llmBtn.title = 'Set OPENROUTER_API_KEY to enable';
            }
        }

        // Local LLM button
        const localBtn = toggle.querySelector('[data-mode="local"]');
        if (localBtn) {
            if (status.local) {
                localBtn.disabled = false;
                localBtn.title = '';
            } else {
                localBtn.disabled = true;
                localBtn.title = 'Start a local LLM server (e.g. ollama serve)';
            }
        }

        // Populate cloud model selector
        if (status.models && status.models.length > 0) {
            state.availableModels = status.models;
            const select = document.getElementById('modelSelect');
            if (select) {
                select.innerHTML = '';
                status.models.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m.id;
                    opt.textContent = m.name;
                    opt.title = m.note || '';
                    select.appendChild(opt);
                });
            }
        }

        // Populate local model selector
        if (status.local_models && status.local_models.length > 0) {
            state.availableLocalModels = status.local_models;
            const localSelect = document.getElementById('localModelSelect');
            if (localSelect) {
                localSelect.innerHTML = '';
                status.local_models.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m.id;
                    opt.textContent = m.name;
                    opt.title = m.note || '';
                    localSelect.appendChild(opt);
                });
            }
        }
    } catch (error) {
        console.error('Error loading generator status:', error);
    }
}

export async function loadPatients() {
    try {
        const patients = await fetchPatients();
        const patientList = document.getElementById('patientList');
        patientList.innerHTML = '';

        patients.forEach(patient => {
            const card = document.createElement('div');
            card.className = 'patient-card';
            card.onclick = () => selectPatient(patient);

            const conditions = patient.conditions.length > 0
                ? patient.conditions.join(', ')
                : 'No significant conditions';

            card.innerHTML = `
                <div class="patient-name">${patient.name}</div>
                <div class="patient-conditions">${conditions}</div>
                <div style="font-size: 12px; color: #999; margin-top: 4px;">ID: ${patient.patient_id}</div>
            `;
            patientList.appendChild(card);
        });
    } catch (error) {
        console.error('Error loading patients:', error);
        document.getElementById('patientList').innerHTML = `
            <div class="error">Error loading patients. Make sure the API is running.</div>
        `;
    }
}

async function selectPatient(patient) {
    if (state.submitting) return;
    state.submitting = true;
    state.currentPatient = patient;
    hideError();
    showLoadingOverlay('Initializing check-in...');
    try {
        await initializeCheckin(patient.patient_id);
    } finally {
        state.submitting = false;
        hideLoadingOverlay();
    }
}

export function selectMode(mode) {
    state.generatorMode = mode;
    document.querySelectorAll('#modeToggle button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    // Show/hide model selectors based on mode
    const modelRow = document.getElementById('modelSelectRow');
    const localModelRow = document.getElementById('localModelSelectRow');
    if (modelRow) modelRow.style.display = mode === 'llm' ? 'flex' : 'none';
    if (localModelRow) localModelRow.style.display = mode === 'local' ? 'flex' : 'none';

    // Set selectedModel based on active dropdown
    if (mode === 'llm') {
        const sel = document.getElementById('modelSelect');
        if (sel && sel.value) state.selectedModel = sel.value;
    } else if (mode === 'local') {
        const sel = document.getElementById('localModelSelect');
        if (sel && sel.value) state.selectedModel = sel.value;
    } else {
        state.selectedModel = null;
    }
}

export function selectModel(modelId) {
    state.selectedModel = modelId;
}

async function initializeCheckin(patientId) {
    try {
        const useModel = state.generatorMode !== 'static' ? state.selectedModel : null;
        const data = await initializeSession(
            patientId,
            state.generatorMode,
            useModel
        );

        state.currentSessionId = data.session_id;
        state.sessionData = {
            patientName: data.patient_name,
            patientId: data.patient_id,
            conditions: data.conditions || [],
            medications: data.medications || [],
            totalQuestions: data.total_questions,
        };
        state.currentQuestion = data.first_question;
        state.allResponses = {};
        state.answeredCount = 0;
        state.questionTree = data.question_tree || [];
        state.answeredQuestions = {};
        state.skippedQuestions = new Set();
        state.generatorMode = data.mode || 'static';
        state.reasoningHistory = [];

        // If LLM mode returned first_reasoning, push it
        if (data.first_reasoning && (data.mode === 'llm' || data.mode === 'local')) {
            state.reasoningHistory.push({
                question_id: data.first_question.question_id,
                question_text: data.first_question.question_text,
                reasoning: data.first_reasoning,
            });
        }

        // Update side panel header and toggle button text
        const panelHeader = document.querySelector('.tree-panel-header span');
        const toggleBtn = document.getElementById('treeToggleBtn');
        if (state.generatorMode === 'llm' || state.generatorMode === 'local') {
            if (panelHeader) panelHeader.textContent = 'LLM Reasoning';
            if (toggleBtn) toggleBtn.textContent = 'Show Reasoning';
        } else {
            if (panelHeader) panelHeader.textContent = 'Decision Tree';
            if (toggleBtn) toggleBtn.textContent = 'Show Tree';
        }

        renderPatientBanner();
        renderSidePanel();
        displayQuestion();
        switchSection('questionnaireSection');
    } catch (error) {
        console.error('Error initializing check-in:', error);
        showError('Failed to start check-in: ' + error.message);
    }
}
