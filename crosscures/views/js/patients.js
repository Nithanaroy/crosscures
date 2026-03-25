import { state } from './state.js';
import { showLoadingOverlay, hideLoadingOverlay } from './state.js';
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
        // Populate model selector
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
                state.selectedModel = status.models[0].id;
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
    // Show/hide model selector based on mode
    const modelRow = document.getElementById('modelSelectRow');
    if (modelRow) {
        modelRow.style.display = mode === 'llm' ? 'flex' : 'none';
    }
}

export function selectModel(modelId) {
    state.selectedModel = modelId;
}

async function initializeCheckin(patientId) {
    try {
        const data = await initializeSession(
            patientId,
            state.generatorMode,
            state.generatorMode === 'llm' ? state.selectedModel : null
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
        if (data.first_reasoning && data.mode === 'llm') {
            state.reasoningHistory.push({
                question_id: data.first_question.question_id,
                question_text: data.first_question.question_text,
                reasoning: data.first_reasoning,
            });
        }

        // Update side panel header and toggle button text
        const panelHeader = document.querySelector('.tree-panel-header span');
        const toggleBtn = document.getElementById('treeToggleBtn');
        if (state.generatorMode === 'llm') {
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
        alert('Error starting check-in');
    }
}
