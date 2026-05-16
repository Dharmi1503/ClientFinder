import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLocation } from 'react-router-dom'
import { 
  Search, 
  Filter, 
  Download, 
  MoreVertical, 
  ExternalLink, 
  Mail, 
  Linkedin,
  MessageCircle,
  Eye,
  Trash2,
  CheckCircle2,
  XCircle
} from 'lucide-react'
import { apiService } from '../services/api'
import LeadDetailsModal from '../components/Dashboard/LeadDetailsModal'

const STATUS_OPTIONS = ['New', 'Contacted', 'Replied', 'Meeting', 'Closed', 'Dead']

export default function SavedLeads() {
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('All')
  const [selectedLead, setSelectedLead] = useState(null)
  const location = useLocation()

  useEffect(() => {
    fetchLeads()
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const searchQuery = params.get('search')
    if (searchQuery) {
      setSearch(searchQuery)
    }
  }, [location.search])

  const fetchLeads = async () => {
    try {
      setLoading(true)
      const data = await apiService.getLeads({ page: 1, page_size: 100 })
      setLeads(data.results || [])
    } catch (error) {
      console.error('Failed to fetch leads:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleStatusChange = async (id, status) => {
    try {
      await apiService.updateLeadStatus(id, status)
      setLeads(prev => prev.map(l => l.id === id ? { ...l, status } : l))
    } catch (err) {
      console.error('Status update failed:', err)
    }
  }

  const exportToCSV = () => {
    const headers = ['Company', 'Industry', 'City', 'Source', 'Label', 'Score', 'Status', 'Email', 'Phone', 'Website']
    const rows = leads.map(l => [
      l.company_name, l.industry, l.city, l.source, l.label, l.composite_score, l.status, l.email, l.phone, l.website
    ])
    const csvContent = [headers, ...rows].map(e => e.join(",")).join("\n")
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement("a")
    link.href = URL.createObjectURL(blob)
    link.download = `clientfinder_leads_${new Date().toISOString().split('T')[0]}.csv`
    link.click()
  }

  const filteredLeads = leads.filter(l => {
    const matchesSearch = l.company_name.toLowerCase().includes(search.toLowerCase()) || 
                          l.industry.toLowerCase().includes(search.toLowerCase())
    const matchesFilter = filter === 'All' || l.label === filter
    return matchesSearch && matchesFilter
  })

  return (
    <div className="space-y-8 pb-20">
      {/* Header Area */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-4xl font-black text-gray-900 dark:text-white">Saved Leads</h1>
          <p className="text-gray-500 mt-2">Manage and track your high-intent pipeline.</p>
        </div>
        <button 
          onClick={exportToCSV}
          className="flex items-center gap-2 px-6 py-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl font-bold text-sm hover:shadow-lg transition-all"
        >
          <Download className="w-4 h-4" />
          Export CSV
        </button>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input 
            type="text"
            placeholder="Search by company or industry..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-12 pr-4 py-4 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 focus:ring-2 focus:ring-indigo-500 transition-all outline-none"
          />
        </div>
        <div className="flex gap-2">
          {['All', 'HOT', 'WARM', 'COLD'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-6 py-4 rounded-2xl font-bold text-sm transition-all border ${
                filter === f 
                ? 'bg-indigo-600 text-white border-indigo-600 shadow-lg shadow-indigo-500/20' 
                : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 text-gray-500'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Leads Grid/Table */}
      <div className="glass rounded-[2.5rem] overflow-hidden border border-white/20 dark:border-white/5 shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50/50 dark:bg-gray-800/30 border-b border-gray-200 dark:border-gray-800">
                <th className="px-8 py-6 text-xs font-black uppercase tracking-widest text-gray-400">Company</th>
                <th className="px-6 py-6 text-xs font-black uppercase tracking-widest text-gray-400">Score</th>
                <th className="px-6 py-6 text-xs font-black uppercase tracking-widest text-gray-400">Contact</th>
                <th className="px-6 py-6 text-xs font-black uppercase tracking-widest text-gray-400">Status</th>
                <th className="px-8 py-6 text-xs font-black uppercase tracking-widest text-gray-400 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
              <AnimatePresence>
                {filteredLeads.map((lead, idx) => (
                  <motion.tr 
                    key={lead.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.05 }}
                    className="group hover:bg-indigo-500/5 transition-colors cursor-pointer"
                    onClick={() => setSelectedLead(lead)}
                  >
                    <td className="px-8 py-6">
                      <div className="flex flex-col">
                        <span className="font-bold text-gray-900 dark:text-white group-hover:text-indigo-500 transition-colors">{lead.company_name}</span>
                        <span className="text-xs text-gray-500 mt-1">{lead.industry} • {lead.city}</span>
                      </div>
                    </td>
                    <td className="px-6 py-6">
                      <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-black tracking-wider ${
                        lead.label === 'HOT' ? 'bg-red-500/10 text-red-500' :
                        lead.label === 'WARM' ? 'bg-amber-500/10 text-amber-500' :
                        'bg-blue-500/10 text-blue-500'
                      }`}>
                        {lead.label} {lead.composite_score}%
                      </div>
                    </td>
                    <td className="px-6 py-6">
                      <div className="flex gap-2">
                        {lead.phone && (
                          <div className="p-2 rounded-lg bg-green-500/10 text-green-500" title={lead.phone}>
                            <MessageCircle className="w-4 h-4" />
                          </div>
                        )}
                        {lead.email && (
                          <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-500" title={lead.email}>
                            <Mail className="w-4 h-4" />
                          </div>
                        )}
                        {lead.website && (
                          <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500" title={lead.website}>
                            <ExternalLink className="w-4 h-4" />
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-6" onClick={e => e.stopPropagation()}>
                      <select 
                        value={lead.status || 'New'}
                        onChange={(e) => handleStatusChange(lead.id, e.target.value)}
                        className="bg-transparent text-sm font-bold outline-none cursor-pointer hover:text-indigo-500 transition-colors"
                      >
                        {STATUS_OPTIONS.map(s => <option key={s} className="bg-white dark:bg-gray-900">{s}</option>)}
                      </select>
                    </td>
                    <td className="px-8 py-6 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <button 
                          className="p-2 hover:bg-indigo-500 hover:text-white rounded-xl transition-all"
                          onClick={(e) => { e.stopPropagation(); setSelectedLead(lead); }}
                        >
                          <Eye className="w-5 h-5" />
                        </button>
                        <button className="p-2 hover:bg-red-500 hover:text-white rounded-xl transition-all">
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
          {filteredLeads.length === 0 && !loading && (
            <div className="p-20 text-center">
              <div className="w-20 h-20 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center mx-auto mb-4 text-gray-400">
                <Search className="w-10 h-10" />
              </div>
              <h3 className="text-xl font-bold">No leads found</h3>
              <p className="text-gray-500">Try adjusting your filters or search terms.</p>
            </div>
          )}
        </div>
      </div>

      <LeadDetailsModal lead={selectedLead} onClose={() => setSelectedLead(null)} />
    </div>
  )
}