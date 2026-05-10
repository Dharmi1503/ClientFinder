import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Search, Zap, Loader2 } from 'lucide-react'
import { apiService } from '../services/api'

const services = [
  'AI Automation',
  'Website Development',
  'App Development',
  'Digital Marketing',
  'ML Solutions',
  'SEO Services',
  'Social Media Marketing',
  'CRM Implementation',
]

const industries = [
  'AI Automation', 
  'Website Development', 
  'App Development', 
  'Digital Marketing', 
  'ML Solutions',
  'SEO Services',        // Add yours
  'Social Media Marketing', // Add yours
  'CRM Implementation',  
  'Hospitals', 
  'Restaurants', 
  'Real Estate', 
  'Clinics', 
  'Salons', 
  'Gyms', 
  'Schools', 
  'Hotels',
  'E-commerce',          // Add yours
  'Manufacturing',       // Add yours
  'Education Tech',      // Add yours
  'Healthcare'  ,
]

const locations = [
  'Delhi NCR',
  'Mumbai',
  'Bangalore',
  'Hyderabad',
  'Chennai',
  'Kolkata',
  'Pune',
  'Ahmedabad',
  'Jaipur',
  'Lucknow',
  'Chandigarh',
  'Goa',
]

// onJobStart(jobId) — parent passes this to wire LiveStatus
export default function RunSearch({ onJobStart }) {
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [formData, setFormData] = useState({
    service: 'Website Development',
    industry: 'Hospitals',
    location: 'Delhi NCR',
    budget_range: '',
    max_leads: 20,
    fast_mode: true,
  })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setStatus('Starting pipeline...')

    try {
      const result = await apiService.runPipeline(formData)
      const jobId = result.job_id
      setStatus(`Job started: ${jobId}`)

      // Tell parent (Dashboard) about the job so LiveStatus can poll it
      if (onJobStart) onJobStart(jobId)

      // Also poll here to update local status text
      const interval = setInterval(async () => {
        try {
          const job = await apiService.getJob(jobId)
          setStatus(`${job.stage || 'Running'}: ${job.message || ''}`)

          if (job.status === 'done' || job.status === 'error') {
            clearInterval(interval)
            setLoading(false)
            if (job.status === 'done') {
              setStatus(`✅ Done! Found ${job.result?.total_leads || 0} leads.`)
            } else {
              setError(`Pipeline failed: ${job.error || 'Unknown error'}`)
              setStatus(null)
            }
          }
        } catch (err) {
          clearInterval(interval)
          setLoading(false)
          setError('Polling failed. Check backend.')
        }
      }, 2000)
    } catch (err) {
      setLoading(false)
      setError(err.error || err.message || 'Failed to start pipeline')
      setStatus(null)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 overflow-hidden"
    >
      <div className="p-6 border-b border-gray-200 dark:border-gray-800">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Search className="w-5 h-5 text-indigo-500" />
          AI Search Pipeline
        </h2>
        <p className="text-sm text-gray-500 mt-1">Configure and launch intelligent lead discovery</p>
      </div>

      <form onSubmit={handleSubmit} className="p-6 space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <label className="block text-sm font-medium mb-2">Service Type</label>
            <select
              value={formData.service}
              onChange={(e) => setFormData({ ...formData, service: e.target.value })}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 transition-all"
            >
              {services.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Industry</label>
            <select
              value={formData.industry}
              onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 transition-all"
            >
              {industries.map(i => <option key={i}>{i}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Location</label>
            <select
              value={formData.location}
              onChange={(e) => setFormData({ ...formData, location: e.target.value })}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 transition-all"
            >
              {locations.map(l => <option key={l}>{l}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Budget Range</label>
            <input
              type="text"
              value={formData.budget_range}
              onChange={(e) => setFormData({ ...formData, budget_range: e.target.value })}
              placeholder="e.g. INR 50k-2L"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 transition-all"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Max Leads</label>
            <input
              type="number"
              value={formData.max_leads}
              onChange={(e) => setFormData({ ...formData, max_leads: parseInt(e.target.value) })}
              min={1}
              max={100}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 transition-all"
            />
          </div>

          <div className="flex items-center justify-between">
            <label className="text-sm font-medium">Fast Mode</label>
            <button
              type="button"
              onClick={() => setFormData({ ...formData, fast_mode: !formData.fast_mode })}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${formData.fast_mode ? 'bg-indigo-500' : 'bg-gray-300 dark:bg-gray-700'}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${formData.fast_mode ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>
        </div>

        {status && (
          <div className="p-3 bg-gray-100 dark:bg-gray-800 rounded-xl text-sm text-gray-600 dark:text-gray-400">
            {status}
          </div>
        )}
        {error && (
          <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-xl text-sm text-red-600 dark:text-red-400">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-gradient-to-r from-indigo-500 to-cyan-500 text-white font-semibold rounded-xl hover:shadow-lg transition-all duration-300 disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {loading ? (
            <><Loader2 className="w-5 h-5 animate-spin" /> Searching for leads...</>
          ) : (
            <><Zap className="w-5 h-5" /> Run AI Search</>
          )}
        </button>
      </form>
    </motion.div>
  )
}