import { API_BASE_URL } from './state.js';

async function handleResponse(resp) {
    if (!resp.ok) {
        let message;
        try {
            const body = await resp.json();
            message = body.detail || JSON.stringify(body);
        } catch {
            message = await resp.text() || resp.statusText;
        }
        throw new Error(`${resp.status}: ${message}`);
    }
    return resp.json();
}

export async function fetchDataSource() {
    const resp = await fetch(`${API_BASE_URL}/data-source`);
    return handleResponse(resp);
}

export async function fetchPatients() {
    const resp = await fetch(`${API_BASE_URL}/patients`);
    return handleResponse(resp);
}

export async function initializeSession(patientId, mode, model) {
    const body = { patient_id: patientId, mode: mode || 'static' };
    if (model) body.model = model;
    const resp = await fetch(`${API_BASE_URL}/checkin/initialize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    return handleResponse(resp);
}

export async function submitQuestionResponse(sessionId, questionId, responseValue, notes) {
    const response = { question_id: questionId, response_value: responseValue };
    if (notes) response.notes = notes;
    const resp = await fetch(`${API_BASE_URL}/checkin/submit-response`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionId,
            response
        })
    });
    return handleResponse(resp);
}

export async function completeSession(sessionId) {
    const resp = await fetch(`${API_BASE_URL}/checkin/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
    });
    return handleResponse(resp);
}

export async function fetchGeneratorStatus() {
    const resp = await fetch(`${API_BASE_URL}/generator/status`);
    return handleResponse(resp);
}
