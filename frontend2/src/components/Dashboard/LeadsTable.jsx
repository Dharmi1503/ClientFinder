import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Download, ChevronLeft, ChevronRight, Eye, Search, Loader2, Sparkles } from 'lucide-react'
import { apiService } from '../../services/api'
import LeadDetailsModal from './LeadDetailsModal'

const STATUS_OPTIONS = ['New', 'Contacted', 'Replied', 'Meeting', 'Closed', 'Dead']
const PAGE_SIZE = 10
const VIEW_OPTIONS = [
  { label: 'Recent', value: 'recent' },
  { label: 'HOT', value: 'HOT' },
  { label: 'WARM', value: 'WARM' },
  { label: 'COLD', value: 'COLD' },
]

const PIPELINE_OPTIONS = [
  { label: 'All Leads', value: 'all' },
  { label: 'Main Discovery', value: 'main_pipeline' },
  { label: 'Intent-Only', value: 'intent_pipeline' },
]

export default function LeadsTable({ refreshTrigger }) {
  const [leads, setLeads] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [view, setView] = useState('recent')
  const [loading, setLoading] = useState(true)
  const [updatingId, setUpdatingId] = useState(null)
  const [selectedLead, setSelectedLead] = useState(null)
  const [pipeline, setPipeline] = useState('all')

  const [debouncedSearch, setDebouncedSearch] = useState('')

  const fetchLeads = async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE, sort_by: view === 'recent' ? 'recent' : 'score' }
      if (view !== 'recent') params.label = view
      if (debouncedSearch) params.city = debouncedSearch
      if (pipeline !== 'all') params.pipeline = pipeline
      const data = await apiService.getLeads(params)
      setLeads(data.results || [])
      setTotal(data.total || 0)
    } catch (err) {
      console.error('LeadsTable fetch failed:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLeads()
  }, [page, view, pipeline, debouncedSearch, refreshTrigger])

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
    }, 400)
    return () => clearTimeout(t)
  }, [search])

  const handleStatusChange = async (id, status) => {
    setUpdatingId(id)
    try {
      await apiService.updateLeadStatus(id, status)
      setLeads(prev => prev.map(l => l.id === id ? { ...l, status } : l))
    } catch (err) {
      console.error('Status update failed:', err)
    } finally {
      setUpdatingId(null)
    }
  }

  const getLabelColor = (label) => {
    switch (label) {
      case 'HOT':  return 'bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400'
      case 'WARM': return 'bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400'
      default:     return 'bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400'
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
      className="rounded-2xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 overflow-hidden"
    >
      {/* Header */}
      <div className="p-6 border-b border-gray-200 dark:border-gray-800">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-xl font-semibold">Recent Leads</h3>
            <p className="text-sm text-gray-500">Showing the newest pipeline results by default.</p>
          </div>
          <div className="flex gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Filter by city..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 pr-4 py-2 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 transition-all text-sm"
              />
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-col md:flex-row justify-between gap-4">
          <div className="flex flex-wrap gap-2">
            {VIEW_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => {
                  setPage(1)
                  setView(option.value)
                }}
                className={`px-4 py-2 rounded-xl text-sm font-semibold border transition-colors ${
                  view === option.value
                    ? 'bg-indigo-500 text-white border-indigo-500'
                    : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-700 hover:border-indigo-400'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="flex bg-gray-100 dark:bg-gray-800 p-1 rounded-xl w-fit self-end">
            {PIPELINE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  setPage(1)
                  setPipeline(opt.value)
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  pipeline === opt.value
                    ? 'bg-white dark:bg-gray-700 text-indigo-600 dark:text-indigo-400 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        {loading ? (
          <div className="flex items-center justify-center py-16 gap-2 text-gray-400">
            <Loader2 className="w-5 h-5 animate-spin" />
            Loading leads...
          </div>
        ) : leads.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-20 h-20 mx-auto mb-4 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center">
              <Search className="w-10 h-10 text-gray-400" />
            </div>
            <h3 className="text-lg font-medium mb-2">No leads found</h3>
            <p className="text-gray-500">Run a search to discover potential clients</p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800/50">
              <tr>
                {['Company', 'Score', 'Source', 'City', 'Label', 'Pain Signal', 'Status', 'Actions'].map(h => (
                  <th key={h} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
              {leads.map((lead) => (
                <motion.tr
                  key={lead.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  whileHover={{ backgroundColor: 'rgba(99,102,241,0.04)' }}
                  onClick={() => setSelectedLead(lead)}
                  className="transition-colors cursor-pointer"
                >
                  <td className="px-6 py-4 font-medium text-gray-900 dark:text-white">
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                        <span>{lead.company_name}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-bold uppercase ${
                          lead.pipeline_type === 'intent_pipeline' 
                            ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
                            : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                        }`}>
                          {lead.pipeline_type === 'intent_pipeline' ? 'Intent' : 'Main'}
                        </span>
                      </div>
                      {lead.rating && (
                        <span className="text-[10px] text-amber-500 flex items-center gap-0.5">
                          ⭐ {lead.rating} ({lead.review_count || 0} reviews)
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="group relative cursor-help">
                      <span className={`px-2 py-1 rounded-lg text-sm font-medium ${
                        lead.composite_score >= 72 ? 'bg-red-100 text-red-700' :
                        lead.composite_score >= 48 ? 'bg-amber-100 text-amber-700' :
                        'bg-blue-100 text-blue-700'
                      }`}>
                        {Math.round(lead.composite_score) ?? '—'}
                      </span>
                      {/* Breakdown Tooltip */}
                      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-32 p-2 bg-gray-800 text-white text-[10px] rounded shadow-xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                        <div className="flex justify-between"><span>Fit:</span> <span>{lead.fit_score}</span></div>
                        <div className="flex justify-between"><span>Intent:</span> <span>{lead.intent_score}</span></div>
                        <div className="flex justify-between"><span>Contact:</span> <span>{lead.contact_score}</span></div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-400 text-sm capitalize">{lead.source}</td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-400 text-sm">{lead.city}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded-lg text-xs font-medium ${getLabelColor(lead.label)}`}>
                      {lead.label || 'COLD'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-400 text-sm max-w-[160px] truncate" title={lead.pain_point}>
                    {lead.pain_point || '—'}
                  </td>
                  <td className="px-6 py-4">
                    <select
                      value={lead.status || 'New'}
                      onChange={(e) => handleStatusChange(lead.id, e.target.value)}
                      disabled={updatingId === lead.id}
                      className="text-xs px-2 py-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 disabled:opacity-50"
                    >
                      {STATUS_OPTIONS.map(s => <option key={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); setSelectedLead(lead); }}
                        className="p-1.5 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded-lg hover:bg-indigo-100 transition-colors"
                        title="View AI Strategy"
                      >
                        <Sparkles className="w-4 h-4" />
                      </button>
                      <a
                        href={lead.website || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors inline-block"
                        title={lead.website || 'No website'}
                      >
                        <Eye className="w-4 h-4" />
                      </a>
                    </div>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {!loading && leads.length > 0 && (
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-800 flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total} results
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const p = i + 1
              return (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`px-3 py-1 rounded-lg text-sm ${page === p ? 'bg-indigo-500 text-white' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}`}
                >
                  {p}
                </button>
              )
            })}
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <LeadDetailsModal 
        lead={selectedLead} 
        onClose={() => setSelectedLead(null)} 
      />
    </motion.div>
  )
}