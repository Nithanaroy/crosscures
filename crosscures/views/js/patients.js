import { state } from './state.js';
import { fetchPatients, fetchDataSource, initializeSession } from './api.js';
import { renderPatientBanner } from './banner.js';
import { renderTree } from './tree.js';
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
    try {
        await initializeCheckin(patient.patient_id);
    } finally {
        state.submitting = false;
    }
}

async function initializeCheckin(patientId) {
    try {
        const data = await initializeSession(patientId);

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

        renderPatientBanner();
        renderTree();
        displayQuestion();
        switchSection('questionnaireSection');
    } catch (error) {
        console.error('Error initializing check-in:', error);
        alert('Error starting check-in');
    }
}
