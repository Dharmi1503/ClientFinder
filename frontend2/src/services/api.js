import axios from 'axios'

import { MOCK_LEADS, MOCK_STATS, MOCK_JOB } from './mockData'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'
const USE_MOCK = true // Set to false to use real backend

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

// In-memory mock store with localStorage persistence
const getInitialMockLeads = () => {
  const saved = localStorage.getItem('mockLeads')
  if (saved) return JSON.parse(saved)
  return [...MOCK_LEADS]
}

let localMockLeads = getInitialMockLeads()

const saveMockLeads = (leads) => {
  localMockLeads = leads
  localStorage.setItem('mockLeads', JSON.stringify(leads))
}

export const apiService = {
  // Health
  health: () => USE_MOCK ? Promise.resolve({ status: 'ok', mode: 'mock' }) : api.get('/health'),

  // Pipeline
  runPipeline: (data) => {
    if (USE_MOCK) {
      // Create a dynamic lead based on search
      const newLead = {
        id: Date.now(),
        company_name: `${data.industry} Solutions Ltd`,
        city: data.location,
        industry: data.industry,
        source: "google_maps",
        label: "HOT",
        composite_score: 85 + Math.floor(Math.random() * 10),
        fit_score: 90,
        intent_score: 80,
        contact_score: 85,
        pain_point: `Looking for ${data.service} in ${data.location}.`,
        status: "New",
        rating: 4.5,
        review_count: 120,
        website: "https://example.com/new-lead",
        phone: "+91 99999 88888",
        email: "contact@newlead.com",
        whatsapp_msg: `Hi, I saw you're looking for ${data.service}...`,
        buying_signals: ["Search intent detected", "Real-time discovery"],
        hot_reason: "Direct match with search criteria."
      }
      
      // Add to start of list and persist
      saveMockLeads([newLead, ...localMockLeads])
      
      return new Promise(resolve => {
        setTimeout(() => resolve({ job_id: "job_mock_" + Date.now() }), 1000)
      })
    }
    return api.post('/find-clients', {
      service: data.service,
      industry: data.industry,
      location: data.location,
      budget_range: data.budget_range || data.budget || '',
      max_leads: data.max_leads || data.maxLeads || 20,
      fast_mode: data.fast_mode ?? data.fastMode ?? true,
    })
  },

  // Jobs
  getJob: (jobId) => {
    if (USE_MOCK) {
      return new Promise(resolve => {
        setTimeout(() => resolve({
            ...MOCK_JOB,
            id: jobId,
            result: {
                total_leads: 1,
                hot_leads: [localMockLeads[0]]
            }
        }), 1500)
      })
    }
    return api.get(`/jobs/${jobId}`)
  },
  
  getAllJobs: () => USE_MOCK ? Promise.resolve([MOCK_JOB]) : api.get('/jobs'),

  // Leads
  getLeads: (params = {}) => {
    if (USE_MOCK) {
      let filtered = [...localMockLeads]
      if (params.label) {
        filtered = filtered.filter(l => l.label === params.label)
      }
      
      return new Promise(resolve => {
        setTimeout(() => resolve({
          results: filtered,
          total: filtered.length,
          page: 1,
          page_size: 10
        }), 800)
      })
    }
    return api.get('/leads', { params })
  },

  updateLeadStatus: (id, status) => {
    if (USE_MOCK) return Promise.resolve({ success: true })
    return api.put(`/leads/${id}/status`, { status })
  },

  reviewLead: (id, action) => api.patch(`/leads/${id}/review`, { action }),
  getReviewQueue: () => {
    if (USE_MOCK) {
        return Promise.resolve({ 
            total: 12,
            results: localMockLeads.slice(0, 3) 
        })
    }
    return api.get('/leads/review-queue')
  },
  getFollowupToday: () => api.get('/leads/followup-today'),

  // Diagnostics
  getScraperHealth: () => USE_MOCK ? Promise.resolve({ active: 7, failing: 0 }) : api.get('/scrapers/health'),
  getSourceQuality: () => USE_MOCK ? Promise.resolve({ google_maps: 0.95, justdial: 0.82 }) : api.get('/sources/quality'),
}

export default api