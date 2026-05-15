import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'
const API_KEY_STORAGE = 'clientfinder_api_key'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use(
  (config) => {
    const headers = config.headers || {}
    const explicitKey = headers['X-API-Key'] || headers['x-api-key']
    const storedKey = localStorage.getItem(API_KEY_STORAGE)

    if (!explicitKey && storedKey) {
      headers['X-API-Key'] = storedKey
    }

    config.headers = headers
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    if (error.response?.status === 403) {
      localStorage.removeItem(API_KEY_STORAGE)
      window.dispatchEvent(new CustomEvent('clientfinder-api-key-cleared'))
    }
    throw error.response?.data || { error: error.message }
  }
)

export const getStoredApiKey = () => localStorage.getItem(API_KEY_STORAGE) || ''
export const setStoredApiKey = (key) => {
  localStorage.setItem(API_KEY_STORAGE, key)
  window.dispatchEvent(new CustomEvent('clientfinder-api-key-changed'))
}
export const clearStoredApiKey = () => {
  localStorage.removeItem(API_KEY_STORAGE)
  window.dispatchEvent(new CustomEvent('clientfinder-api-key-cleared'))
}

export const verifyApiKey = (key) => api.get('/health', { headers: { 'X-API-Key': key } })

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