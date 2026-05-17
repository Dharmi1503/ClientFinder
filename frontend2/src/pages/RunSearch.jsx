import React, { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, Zap, Loader2, Globe, Phone, Mail,
  TrendingUp, MapPin, Sparkles, ArrowUpDown, RefreshCw
} from 'lucide-react'
import { apiService } from '../services/api'
import LeadDetailsModal from '../components/Dashboard/LeadDetailsModal'
import LiveStatus from '../components/Dashboard/LiveStatus'

// ── Original dropdowns — unchanged ────────────────────────────────────────────
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
  'SEO Services',
  'Social Media Marketing',
  'CRM Implementation',
  'Hospitals',
  'Restaurants',
  'Real Estate',
  'Clinics',
  'Salons',
  'Gyms',
  'Schools',
  'Hotels',
  'E-commerce',
  'Manufacturing',
  'Education Tech',
  'Healthcare',
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

// AI thinking stages — used during both mock-DB and live-scraping waits
const AI_STAGES = [
  'Scanning business directories…',
  'Analyzing digital presence…',
  'AI scoring potential clients…',
  'Finding high-conversion leads…',
  'Compiling results…',
]

// ── Lead card helpers ─────────────────────────────────────────────────────────
function ScoreBadge({ score }) {
  const color =
    score >= 85
      ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
      : score >= 70
      ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
      : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
  return (
    <span className={`px-2.5 py-1 rounded-lg text-sm font-bold tabular-nums ${color}`}>
      {Math.round(score)}
    </span>
  )
}

function LabelPill({ label }) {
  const styles = {
    HOT:  'bg-red-500 text-white',
    WARM: 'bg-amber-500 text-white',
    COLD: 'bg-blue-500 text-white',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider ${styles[label] || styles.COLD}`}>
      {label || 'COLD'}
    </span>
  )
}

function ContactChip({ icon, value, positive }) {
  return (
    <div className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium ${
      positive
        ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400'
        : 'bg-gray-100 dark:bg-gray-800 text-gray-500'
    }`}>
      {icon}<span>{value}</span>
    </div>
  )
}

function LeadCard({ lead, onClick }) {
  const score = lead.composite_score || 0
  const borderColor =
    score >= 85
      ? 'border-red-200 dark:border-red-900/50 hover:border-red-400'
      : score >= 70
      ? 'border-amber-200 dark:border-amber-900/50 hover:border-amber-400'
      : 'border-blue-200 dark:border-blue-900/50 hover:border-blue-400'

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      onClick={onClick}
      className={`group relative bg-white dark:bg-gray-900 border rounded-2xl p-5 cursor-pointer transition-all duration-200 hover:shadow-xl hover:-translate-y-0.5 ${borderColor}`}
    >
      <div className={`absolute top-0 left-0 w-1 h-full rounded-l-2xl ${score >= 85 ? 'bg-red-500' : score >= 70 ? 'bg-amber-500' : 'bg-blue-500'}`} />
      <div className="pl-2">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <h3 className="font-bold text-gray-900 dark:text-white text-sm leading-tight truncate group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
              {lead.company_name}
            </h3>
            <div className="flex items-center gap-1.5 mt-1">
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <MapPin className="w-3 h-3" />{lead.city}
              </span>
              <span className="text-gray-300 dark:text-gray-600">·</span>
              <span className="text-xs text-gray-500 truncate max-w-[120px]">{lead.industry}</span>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1.5 shrink-0">
            <ScoreBadge score={score} />
            <LabelPill label={lead.label} />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 mb-3">
          <ContactChip icon={<Globe className="w-3 h-3" />} value={lead.website_alive || lead.website ? 'Live' : 'No Site'} positive={!!(lead.website_alive || lead.website)} />
          <ContactChip icon={<Phone className="w-3 h-3" />} value={lead.phone ? 'Has Phone' : 'No Phone'} positive={!!lead.phone} />
          <ContactChip icon={<Mail className="w-3 h-3" />} value={lead.email ? 'Has Email' : 'No Email'} positive={!!lead.email} />
        </div>

        {(lead.ai_recommendation || lead.pain_point || lead.hot_reason) && (
          <div className="flex items-start gap-2 p-2.5 bg-indigo-50 dark:bg-indigo-950/40 rounded-xl border border-indigo-100 dark:border-indigo-900/50">
            <Sparkles className="w-3.5 h-3.5 text-indigo-500 shrink-0 mt-0.5" />
            <p className="text-[11px] text-indigo-700 dark:text-indigo-300 leading-relaxed line-clamp-2">
              {lead.ai_recommendation || lead.pain_point || lead.hot_reason}
            </p>
          </div>
        )}

        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
          <span className="text-[10px] text-gray-400 capitalize">{lead.source}</span>
          <div className="flex items-center gap-3">
            {(lead.growth_potential) && (
              <span className="flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">
                <TrendingUp className="w-3 h-3" />{lead.growth_potential}
              </span>
            )}
            <span className="text-[10px] text-indigo-500 font-semibold group-hover:underline">View details →</span>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────────
export default function RunSearch({ onJobStart }) {
  const [loading, setLoading]           = useState(false)
  const [stageIdx, setStageIdx]         = useState(0)
  const [stageLabel, setStageLabel]     = useState(AI_STAGES[0])
  const [error, setError]               = useState(null)
  const [results, setResults]           = useState(null)
  const [selectedLead, setSelectedLead] = useState(null)
  const [sortBy, setSortBy]             = useState('score')
  const [liveMode, setLiveMode]         = useState(false) // show live vs mock badge
  const [activeJobId, setActiveJobId]   = useState(null)  // drives LiveStatus panel
  const pollRef = useRef(null)

  const [formData, setFormData] = useState({
    service:      'Website Development',
    industry:     'Hospitals',
    location:     'Mumbai',
    budget_range: '',
    max_leads:    20,
    fast_mode:    true,
  })

  // ── Poll job until done ──────────────────────────────────────────────────────
  const pollJob = (jobId) => new Promise((resolve, reject) => {
    let attempts = 0
    const MAX = 120 // 2 min max
    pollRef.current = setInterval(async () => {
      attempts++
      try {
        const job = await apiService.getJob(jobId)
        if (job.stage) setStageLabel(job.message || job.stage)
        if (job.status === 'done') {
          clearInterval(pollRef.current)
          resolve(job)
        } else if (job.status === 'error') {
          clearInterval(pollRef.current)
          reject(new Error(job.message || 'Pipeline failed'))
        } else if (attempts >= MAX) {
          clearInterval(pollRef.current)
          reject(new Error('Search timed out after 2 minutes'))
        }
      } catch (e) {
        clearInterval(pollRef.current)
        reject(e)
      }
    }, 1000)
  })

  // ── Submit ───────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResults(null)
    setStageIdx(0)
    setStageLabel(AI_STAGES[0])

    // Start AI animation
    const anim = setInterval(() => {
      setStageIdx(i => {
        const next = Math.min(i + 1, AI_STAGES.length - 1)
        setStageLabel(AI_STAGES[next])
        return next
      })
    }, 600)

    try {
      // Always try the live scraper pipeline first
      const jobResp = await apiService.runPipeline({
        service:      formData.service,
        industry:     formData.industry,
        location:     formData.location,
        budget_range: formData.budget_range,
        max_leads:    formData.max_leads,
        fast_mode:    formData.fast_mode,
      })

      clearInterval(anim)
      setActiveJobId(jobResp.job_id)   // ← show LiveStatus panel
      const job = await pollJob(jobResp.job_id)

      // Collect leads from both pipelines
      const dirLeads    = job.result?.directory_pipeline?.leads || []
      const intentLeads = job.result?.intent_pipeline?.leads    || []
      const allLeads    = [...dirLeads, ...intentLeads]

      setLiveMode(true)
      setActiveJobId(null)   // hide LiveStatus once results are in
      setResults({
        returned: allLeads.length,
        results:  allLeads,
        source:   'live',
      })
    } catch (liveErr) {
      clearInterval(anim)
      setActiveJobId(null)   // hide LiveStatus on failure too
      console.warn('Live scraper failed, falling back to mock DB:', liveErr)

      // Fallback: query mock DB instantly
      try {
        const data = await apiService.demoSearch({
          service:      formData.service,
          industry:     formData.industry,
          location:     formData.location,
          max_leads:    formData.max_leads,
          budget_range: formData.budget_range,
        })
        setLiveMode(false)
        setResults({ ...data, source: 'mock' })
      } catch (mockErr) {
        setError(mockErr.error || mockErr.message || 'Search failed')
      }
    } finally {
      setLoading(false)
    }
  }

  const sorted = results?.results
    ? [...results.results].sort((a, b) =>
        sortBy === 'score'
          ? (b.composite_score || 0) - (a.composite_score || 0)
          : new Date(b.created_at) - new Date(a.created_at)
      )
    : []

  return (
    <>
      {/* ── Original search box — layout unchanged ── */}
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
                onChange={e => setFormData({ ...formData, service: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 transition-all"
              >
                {services.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Industry</label>
              <select
                value={formData.industry}
                onChange={e => setFormData({ ...formData, industry: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 transition-all"
              >
                {industries.map(i => <option key={i}>{i}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Location</label>
              <select
                value={formData.location}
                onChange={e => setFormData({ ...formData, location: e.target.value })}
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
                onChange={e => setFormData({ ...formData, budget_range: e.target.value })}
                placeholder="e.g. INR 50k-2L"
                className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 transition-all"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Max Leads</label>
              <input
                type="number"
                value={formData.max_leads}
                onChange={e => setFormData({ ...formData, max_leads: parseInt(e.target.value) || 20 })}
                min={1} max={100}
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
              <><Loader2 className="w-5 h-5 animate-spin" /> {stageLabel}</>
            ) : (
              <><Zap className="w-5 h-5" /> Run AI Search</>
            )}
          </button>
        </form>
      </motion.div>

      {/* ── Live Execution Pipeline (shows while scraper job is running) ── */}
      <AnimatePresence>
        {activeJobId && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
          >
            <LiveStatus jobId={activeJobId} onDone={() => {}} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Results section ── */}
      <AnimatePresence>
        {results && !loading && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-4"
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                    {results.returned} Leads Found
                  </h2>
                  {/* Live vs Mock badge */}
                  {liveMode ? (
                    <span className="flex items-center gap-1 px-2 py-0.5 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-[10px] font-bold uppercase rounded-full">
                      <RefreshCw className="w-2.5 h-2.5" /> Live Scraped
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 text-[10px] font-bold uppercase rounded-full">
                      Demo DB
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-500">
                  {formData.service} · {formData.industry} · {formData.location}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <ArrowUpDown className="w-4 h-4 text-gray-400" />
                <select
                  value={sortBy}
                  onChange={e => setSortBy(e.target.value)}
                  className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="score">Highest Score</option>
                  <option value="recent">Most Recent</option>
                </select>
              </div>
            </div>

            {sorted.length === 0 ? (
              <div className="text-center py-14 glass rounded-2xl">
                <Search className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                <h3 className="font-semibold text-gray-500">No leads found for this combination</h3>
                <p className="text-sm text-gray-400 mt-1">Try a different industry or location</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {sorted.map((lead, i) => (
                  <LeadCard
                    key={lead.id || i}
                    lead={lead}
                    onClick={() => setSelectedLead(lead)}
                  />
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <LeadDetailsModal lead={selectedLead} onClose={() => setSelectedLead(null)} />
    </>
  )
}