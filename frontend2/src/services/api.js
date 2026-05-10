import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    throw error.response?.data || { error: error.message }
  }
)

export const apiService = {
  // Health
  health: () => api.get('/health'),

  // Pipeline
  runPipeline: (data) => api.post('/find-clients', {
    service: data.service,
    industry: data.industry,
    location: data.location,
    budget_range: data.budget_range || data.budget || '',
    max_leads: data.max_leads || data.maxLeads || 20,
    fast_mode: data.fast_mode ?? data.fastMode ?? true,
  }),

  // Jobs
  getJob: (jobId) => api.get(`/jobs/${jobId}`),
  getAllJobs: () => api.get('/jobs'),

  // Leads
  getLeads: (params = {}) => api.get('/leads', { params }),
  updateLeadStatus: (id, status) => api.put(`/leads/${id}/status`, { status }),
  updateFollowup: (id, data) => api.put(`/leads/${id}/followup`, data),
  reviewLead: (id, action) => api.patch(`/leads/${id}/review`, { action }),
  getReviewQueue: () => api.get('/leads/review-queue'),
  getFollowupToday: () => api.get('/leads/followup-today'),
  getRejectedLeads: () => api.get('/leads/rejected'),

  // Diagnostics
  getScraperHealth: () => api.get('/scrapers/health'),
  getScraperHealthBySource: (source) => api.get(`/scrapers/health/${source}`),
  getSourceQuality: () => api.get('/sources/quality'),
  getLLMHealth: () => api.get('/llm/health'),
  getCalibration: () => api.get('/calibration'),
}

export default api