import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach auth token from localStorage
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('crosscures_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('crosscures_token');
      localStorage.removeItem('crosscures_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// Auth
export const authApi = {
  register: (data: RegisterRequest) => api.post('/v1/auth/register', data),
  login: (data: LoginRequest) => api.post('/v1/auth/login', data),
  me: () => api.get('/v1/auth/me'),
  linkPhysician: (physician_email: string) => api.post('/v1/auth/link-physician', { physician_email }),
};

// Patient
export const patientApi = {
  getConsents: () => api.get('/v1/patient/consent'),
  grantConsent: (action: string) => api.post('/v1/patient/consent/grant', { action }),
  revokeConsent: (action: string) => api.post('/v1/patient/consent/revoke', { action }),
  
  uploadRecords: (formData: FormData) => api.post('/v1/patient/records/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  getRecords: (params?: { resource_type?: string }) => api.get('/v1/patient/records', { params }),
  
  getTodayCheckin: () => api.get('/v1/patient/checkin/today'),
  submitCheckin: (data: CheckinSubmitRequest) => api.post('/v1/patient/checkin/response', data),
  
  getAppointments: () => api.get('/v1/patient/appointments'),
  createAppointment: (data: AppointmentCreateRequest) => api.post('/v1/patient/appointments', data),
  generateBrief: (appointmentId: string, force = false) =>
    api.post(`/v1/patient/appointments/${appointmentId}/generate-brief`, null, {
      params: { force },
    }),
  
  startClinicSession: (data: { appointment_id?: string; audio_enabled: boolean }) =>
    api.post('/v1/patient/clinic/session/start', data),
  sendClinicTurn: (sessionId: string, content: string) =>
    api.post(`/v1/patient/clinic/session/${sessionId}/turn`, { content }),
  endClinicSession: (sessionId: string) =>
    api.post(`/v1/patient/clinic/session/${sessionId}/end`),
  getClinicSessions: () => api.get('/v1/patient/clinic/sessions'),
  
  getPrescriptions: () => api.get('/v1/patient/prescriptions'),
  createPrescription: (data: PrescriptionCreateRequest) => api.post('/v1/patient/prescriptions', data),
  confirmPrescription: (id: string) => api.post(`/v1/patient/prescriptions/${id}/confirm`),
  
  getProfile: () => api.get('/v1/patient/profile'),

  // Pre-Visit Call
  schedulePrevisit: (data: { scheduled_at: string; appointment_id?: string }) =>
    api.post('/v1/patient/previsit/schedule', data),
  getPrevisitSlots: () => api.get('/v1/patient/previsit/slots'),
  startPrevisitSession: (data?: { slot_id?: string; appointment_id?: string }) =>
    api.post('/v1/patient/previsit/session/start', data ?? {}),
  sendPrevisitTurn: (sessionId: string, content: string) =>
    api.post(`/v1/patient/previsit/session/${sessionId}/turn`, { content }),
  endPrevisitSession: (sessionId: string) =>
    api.post(`/v1/patient/previsit/session/${sessionId}/end`),

  // Health Condition Report
  startHealthReportSession: () =>
    api.post('/v1/patient/health-report/session/start'),
  sendHealthReportTurn: (sessionId: string, content: string) =>
    api.post(`/v1/patient/health-report/session/${sessionId}/turn`, { content }),
  endHealthReportSession: (sessionId: string) =>
    api.post(`/v1/patient/health-report/session/${sessionId}/end`),
};

// Physician
export const physicianApi = {
  getDashboard: () => api.get('/v1/physician/dashboard'),
  getPatients: () => api.get('/v1/physician/patients'),
  getPatientBriefs: (patientId: string) => api.get(`/v1/physician/patients/${patientId}/briefs`),
  getBrief: (briefId: string) => api.get(`/v1/physician/briefs/${briefId}`),
  acknowledgeBrief: (briefId: string) => api.post(`/v1/physician/briefs/${briefId}/acknowledge`),
  getPatientAlerts: (patientId: string) => api.get(`/v1/physician/patients/${patientId}/alerts`),
  getAlert: (alertId: string) => api.get(`/v1/physician/alerts/${alertId}`),
  acknowledgeAlert: (alertId: string) => api.post(`/v1/physician/alerts/${alertId}/acknowledge`),
};

// Voice
export const voiceApi = {
  transcribe: (audioBlob: Blob) => {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');
    return api.post('/v1/voice/transcribe', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  synthesize: (text: string) => api.post('/v1/voice/synthesize', { text }, { responseType: 'arraybuffer' }),
};

// Types
export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  role: 'patient' | 'physician';
  date_of_birth?: string;
  npi_number?: string;
  specialty?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface CheckinSubmitRequest {
  responses: Array<{ question_id: string; value: any; answered_at: string; skipped: boolean }>;
  session_date?: string;
  prescription_id?: string;
  day_since_start?: number;
}

export interface AppointmentCreateRequest {
  physician_name: string;
  appointment_date: string;
  location?: string;
  reason?: string;
  physician_id?: string;
}

export interface PrescriptionCreateRequest {
  medication_name: string;
  dose: string;
  frequency: string;
  prescribing_physician?: string;
  start_date: string;
  medication_code?: string;
}
