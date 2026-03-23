import { API_BASE_URL } from './state.js';

export async function fetchDataSource() {
    const resp = await fetch(`${API_BASE_URL}/data-source`);
    return resp.json();
}

export async function fetchPatients() {
    const resp = await fetch(`${API_BASE_URL}/patients`);
    return resp.json();
}

export async function initializeSession(patientId) {
    const resp = await fetch(`${API_BASE_URL}/checkin/initialize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient_id: patientId })
    });
    return resp.json();
}

export async function submitQuestionResponse(sessionId, questionId, responseValue) {
    const resp = await fetch(`${API_BASE_URL}/checkin/submit-response`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionId,
            response: {
                question_id: questionId,
                response_value: responseValue
            }
        })
    });
    return resp.json();
}

export async function completeSession(sessionId) {
    const resp = await fetch(`${API_BASE_URL}/checkin/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
    });
    return resp.json();
}
