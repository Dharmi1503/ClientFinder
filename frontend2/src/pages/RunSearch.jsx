import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Zap, Loader2, CheckCircle2, ArrowRight, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiService } from '../services/api'
import LiveStatus from '../components/Dashboard/LiveStatus'

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
  const [currentJobId, setCurrentJobId] = useState(null)
  const [error, setError] = useState(null)
  const [formData, setFormData] = useState({
    service: 'Website Development',
    industry: 'Hospitals',
    location: 'Mumbai',
    budget_range: '',
    max_leads: 20,
    fast_mode: true,
  })

  const [showSuccessModal, setShowSuccessModal] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setCurrentJobId(null)
    setShowSuccessModal(false)

    try {
      const result = await apiService.runPipeline(formData)
      const jobId = result.job_id
      setCurrentJobId(jobId)
      
      if (onJobStart) onJobStart(jobId)
    } catch (err) {
      setLoading(false)
      setError(err.error || err.message || 'Failed to start pipeline')
    }
  }

  const handleJobDone = () => {
    setLoading(false)
    setShowSuccessModal(true)
  }

  return (
    <>
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-2xl overflow-hidden"
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
            <><Loader2 className="w-5 h-5 animate-spin" /> Pipeline Running...</>
          ) : (
            <><Zap className="w-5 h-5" /> Run AI Search</>
          )}
        </button>
      </form>

      {/* Live Pipeline Visualization */}
      <AnimatePresence>
        {currentJobId && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="p-6 pt-0 border-t border-gray-200 dark:border-gray-800"
          >
            <div className="mt-6">
                <LiveStatus jobId={currentJobId} onDone={handleJobDone} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
    
    <AnimatePresence>
      {showSuccessModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6">
          <motion.div 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }} 
            exit={{ opacity: 0 }}
            onClick={() => setShowSuccessModal(false)}
            className="absolute inset-0 bg-slate-900/80 backdrop-blur-md"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="relative w-full max-w-lg bg-white dark:bg-slate-900 rounded-[3rem] p-10 text-center shadow-2xl border border-white/10 overflow-hidden"
          >
            {/* Animated background stars/particles */}
            <div className="absolute inset-0 pointer-events-none">
              {[...Array(8)].map((_, i) => (
                <motion.div
                  key={i}
                  animate={{ 
                    y: [0, -200], 
                    opacity: [0, 1, 0],
                    scale: [0, 1.2, 0.5]
                  }}
                  transition={{ 
                    duration: 3, 
                    repeat: Infinity, 
                    delay: i * 0.5,
                    ease: "easeOut" 
                  }}
                  className="absolute text-indigo-400/20"
                  style={{ 
                    left: `${Math.random() * 100}%`, 
                    top: '90%' 
                  }}
                >
                  <Star className="w-4 h-4 fill-current" />
                </motion.div>
              ))}
            </div>

            <div className="relative z-10">
              <div className="w-24 h-24 bg-gradient-to-br from-emerald-400 to-cyan-500 rounded-3xl flex items-center justify-center mx-auto mb-8 shadow-2xl shadow-emerald-500/40 rotate-12">
                <CheckCircle2 className="w-12 h-12 text-white" />
              </div>
              
              <h2 className="text-4xl font-black text-slate-900 dark:text-white mb-4">Search Complete!</h2>
              <p className="text-lg text-slate-500 dark:text-slate-400 mb-10 leading-relaxed">
                We've identified high-quality leads matching your criteria. Your dashboard is now updated.
              </p>

              <div className="flex flex-col gap-4">
                <Link 
                  to="/" 
                  className="w-full py-5 bg-gradient-to-r from-indigo-600 to-indigo-500 text-white font-black rounded-2xl shadow-xl shadow-indigo-500/20 hover:scale-105 transition-all flex items-center justify-center gap-2 group"
                >
                  Go to Dashboard
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </Link>
                <button 
                  onClick={() => setShowSuccessModal(false)}
                  className="w-full py-4 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-white font-bold transition-colors"
                >
                  Run Another Search
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
    </>
  )
}