import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  ShieldCheck, 
  Settings2, 
  Activity, 
  AlertCircle, 
  CheckCircle2, 
  XCircle,
  ExternalLink,
  ChevronRight,
  Database
} from 'lucide-react'
import { apiService } from '../services/api'

export default function Operations() {
  const [summary, setSummary] = useState({
    runningJobs: 0,
    reviewCount: 0,
    failedJobs: 0,
  })
  const [reviewLeads, setReviewLeads] = useState([])
  const [loading, setLoading] = useState(true)

  const loadOperations = async () => {
    try {
      setLoading(true)
      const [jobsResponse, reviewResponse] = await Promise.all([
        apiService.getAllJobs(),
        apiService.getReviewQueue(),
      ])

      const jobs = Array.isArray(jobsResponse) ? jobsResponse : []
      // Mock mode handles this specifically in api.js
      const reviewData = reviewResponse.results || reviewResponse.leads || []

      setSummary({
        runningJobs: jobs.filter((job) => job.status === 'running').length,
        failedJobs: jobs.filter((job) => job.status === 'error').length,
        reviewCount: reviewData.length,
      })
      setReviewLeads(reviewData)
    } catch (error) {
      console.error('Operations fetch failed:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadOperations()
  }, [])

  const handleReviewAction = async (id, action) => {
    try {
      await apiService.reviewLead(id, action)
      setReviewLeads(prev => prev.filter(l => l.id !== id))
      setSummary(prev => ({ ...prev, reviewCount: prev.reviewCount - 1 }))
    } catch (err) {
      console.error('Review action failed:', err)
    }
  }

  return (
    <div className="space-y-10 pb-20">
      {/* Page Header */}
      <section className="glass rounded-[2.5rem] p-10 border border-white/20 shadow-2xl relative overflow-hidden bg-slate-900 text-white">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-[100px] -translate-y-1/2 translate-x-1/2" />
        <div className="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-8">
          <div className="max-w-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-white/10 rounded-xl">
                <Settings2 className="w-5 h-5 text-indigo-400" />
              </div>
              <span className="text-xs font-bold uppercase tracking-[0.3em] text-indigo-400">Operations Control</span>
            </div>
            <h2 className="text-4xl font-black mb-4">Mission Control Hub</h2>
            <p className="text-slate-400 text-lg leading-relaxed">
              Coordinate live search jobs, manage high-value review gates, and monitor system health from a single operational pane.
            </p>
          </div>
          
          <div className="flex gap-4">
            <div className="px-8 py-6 rounded-[2rem] bg-white/5 border border-white/10 backdrop-blur-md text-center">
              <p className="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-1">Live Jobs</p>
              <p className="text-3xl font-black text-indigo-400">{summary.runningJobs}</p>
            </div>
            <div className="px-8 py-6 rounded-[2rem] bg-white/5 border border-white/10 backdrop-blur-md text-center">
              <p className="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-1">Backlog</p>
              <p className="text-3xl font-black text-amber-400">{summary.reviewCount}</p>
            </div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
        {/* Left Column: Review Queue */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between mb-2 px-2">
            <h3 className="text-2xl font-black flex items-center gap-3">
              <ShieldCheck className="w-7 h-7 text-indigo-500" />
              Quality Review Queue
            </h3>
            <span className="px-3 py-1 bg-indigo-500/10 text-indigo-500 rounded-lg text-xs font-bold">
              {summary.reviewCount} PENDING
            </span>
          </div>

          <div className="space-y-4">
            <AnimatePresence mode="popLayout">
              {reviewLeads.map((lead) => (
                <motion.div
                  key={lead.id}
                  layout
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="glass rounded-3xl p-6 border border-white/10 shadow-lg flex flex-col md:flex-row items-center justify-between gap-6"
                >
                  <div className="flex items-center gap-6 flex-1">
                    <div className="w-14 h-14 bg-gradient-to-br from-indigo-500/20 to-cyan-500/20 rounded-2xl flex items-center justify-center text-indigo-500 border border-indigo-500/20">
                      <Database className="w-6 h-6" />
                    </div>
                    <div>
                      <h4 className="font-bold text-lg text-gray-900 dark:text-white">{lead.company_name}</h4>
                      <div className="flex items-center gap-2 text-sm text-gray-500 mt-0.5">
                        <span>{lead.industry}</span>
                        <span>•</span>
                        <span>{lead.city}</span>
                        {lead.website && (
                          <a href={lead.website} target="_blank" rel="noreferrer" className="text-indigo-500">
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <button 
                      onClick={() => handleReviewAction(lead.id, 'rejected')}
                      className="p-3 rounded-2xl bg-red-500/10 text-red-500 hover:bg-red-500 hover:text-white transition-all group"
                      title="Reject Lead"
                    >
                      <XCircle className="w-6 h-6 group-hover:scale-110 transition-transform" />
                    </button>
                    <button 
                      onClick={() => handleReviewAction(lead.id, 'approved')}
                      className="p-3 rounded-2xl bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500 hover:text-white transition-all group"
                      title="Approve Lead"
                    >
                      <CheckCircle2 className="w-6 h-6 group-hover:scale-110 transition-transform" />
                    </button>
                    <button className="p-3 rounded-2xl bg-gray-100 dark:bg-gray-800 text-gray-400 hover:text-gray-900 dark:hover:text-white transition-all">
                      <ChevronRight className="w-6 h-6" />
                    </button>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {reviewLeads.length === 0 && !loading && (
              <div className="py-20 glass rounded-[2.5rem] border border-dashed border-gray-300 dark:border-gray-700 text-center">
                <div className="w-16 h-16 bg-gray-50 dark:bg-gray-800 rounded-full flex items-center justify-center mx-auto mb-4 text-emerald-500">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <h4 className="text-xl font-bold">Queue Clear!</h4>
                <p className="text-gray-500">No leads waiting for manual review.</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: System Signals */}
        <div className="space-y-8">
          <div className="glass rounded-[2.5rem] p-8 border border-white/10 shadow-xl">
            <h3 className="text-xl font-black mb-6 flex items-center gap-2">
              <Activity className="w-5 h-5 text-indigo-500" />
              System Signals
            </h3>
            
            <div className="space-y-6">
              {[
                { label: 'Scraper Engine', status: 'Online', color: 'text-emerald-500' },
                { label: 'AI Inference', status: 'Optimal', color: 'text-emerald-500' },
                { label: 'Lead Database', status: 'Connected', color: 'text-indigo-500' },
                { label: 'Outreach API', status: 'Active', color: 'text-emerald-500' },
              ].map((sig) => (
                <div key={sig.label} className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-500">{sig.label}</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-bold ${sig.color}`}>{sig.status}</span>
                    <div className={`w-1.5 h-1.5 rounded-full ${sig.color.replace('text', 'bg')} animate-pulse`} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="glass rounded-[2.5rem] p-8 border border-red-500/10 shadow-xl bg-red-500/5">
            <h3 className="text-xl font-black mb-4 flex items-center gap-2 text-red-500">
              <AlertCircle className="w-5 h-5" />
              Failed Jobs
            </h3>
            <p className="text-xs text-red-600/70 mb-4 leading-relaxed">
              These searches encountered errors (usually network timeouts or anti-bot blocks).
            </p>
            <div className="text-center py-6">
              <p className="text-2xl font-black text-red-500">{summary.failedJobs}</p>
              <p className="text-[10px] uppercase font-bold text-red-400 mt-1 tracking-widest">Flagged Jobs</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
