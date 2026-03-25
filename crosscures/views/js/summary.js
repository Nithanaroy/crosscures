import { state } from './state.js';
import { showLoadingOverlay, hideLoadingOverlay } from './state.js';
import { completeSession } from './api.js';
import { switchSection } from './app.js';

export function formatAnswer(value) {
    if (value === true) return 'Yes';
    if (value === false) return 'No';
    return value;
}

export async function completeQuestionnaire() {
    showLoadingOverlay('Completing check-in...');
    try {
        const data = await completeSession(state.currentSessionId);
        displaySummary(data.summary);
    } catch (error) {
        console.error('Error completing check-in:', error);
        alert('Error completing check-in');
    } finally {
        hideLoadingOverlay();
    }
}

function displaySummary(summary) {
    const duration = summary.duration_minutes.toFixed(1);
    document.getElementById('summaryMessage').textContent =
        `Check-in completed in ${duration} minutes with ${Object.keys(summary.responses).length} responses.`;

    let html = '';
    for (const qId in summary.responses) {
        const answer = formatAnswer(summary.responses[qId]);
        html += `
            <div class="response-item">
                <div class="response-question">Q: ${qId}</div>
                <div class="response-answer">A: ${answer}</div>
            </div>
        `;
    }
    document.getElementById('summaryContent').innerHTML = html;

    switchSection('summarySection');
}
