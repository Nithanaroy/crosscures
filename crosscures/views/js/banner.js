import { state } from './state.js';

export function renderPatientBanner() {
    const banner = document.getElementById('patientBanner');
    const sd = state.sessionData;

    document.getElementById('bannerName').textContent = sd.patientName;
    document.getElementById('bannerId').textContent = 'ID: ' + sd.patientId;

    const tagsDiv = document.getElementById('bannerConditions');
    if (sd.conditions.length > 0) {
        tagsDiv.innerHTML = sd.conditions.map(c =>
            '<span class="condition-pill">' + c + '</span>'
        ).join('');
    } else {
        tagsDiv.innerHTML = '<span class="no-conditions-pill">No active conditions</span>';
    }

    const medsDiv = document.getElementById('bannerMeds');
    if (sd.medications.length > 0) {
        medsDiv.innerHTML = '<strong>Meds:</strong> ' + sd.medications.join(', ');
    } else {
        medsDiv.innerHTML = '<strong>Meds:</strong> None';
    }

    banner.style.display = 'flex';
}

export function hidePatientBanner() {
    document.getElementById('patientBanner').style.display = 'none';
}
