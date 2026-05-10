import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Download, ChevronLeft, ChevronRight, Eye, Search, Loader2 } from 'lucide-react'
import { apiService } from '../../services/api'

const STATUS_OPTIONS = ['New', 'Contacted', 'Replied', 'Meeting', 'Closed', 'Dead']
const PAGE_SIZE = 10

export default function LeadsTable({ refreshTrigger }) {
  const [leads, setLeads] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [updatingId, setUpdatingId] = useState(null)

  const fetchLeads = async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      // backend supports city/source text filter — use search as city for now
      if (search) params.city = search
      const data = await apiService.getLeads(params)
      setLeads(data.results || [])
      setTotal(data.total || 0)
    } catch (err) {
      console.error('LeadsTable fetch failed:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchLeads() }, [page, refreshTrigger])

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => { setPage(1); fetchLeads() }, 400)
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
          <h3 className="text-xl font-semibold">Recent Leads</h3>
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
                  className="transition-colors"
                >
                  <td className="px-6 py-4 font-medium text-gray-900 dark:text-white">
                    {lead.company_name}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded-lg text-sm font-medium ${
                      lead.composite_score >= 70 ? 'bg-green-100 text-green-700' :
                      lead.composite_score >= 40 ? 'bg-amber-100 text-amber-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {lead.composite_score ?? '—'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-400 text-sm">{lead.source}</td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-400 text-sm">{lead.city}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded-lg text-xs font-medium ${getLabelColor(lead.label)}`}>
                      {lead.label || 'COLD'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-400 text-sm max-w-[160px] truncate">
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
                    <a
                      href={lead.website || '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors inline-block"
                      title={lead.website || 'No website'}
                    >
                      <Eye className="w-4 h-4" />
                    </a>
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
    </motion.div>
  )
}