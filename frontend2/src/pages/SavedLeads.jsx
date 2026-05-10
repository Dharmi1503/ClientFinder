import React, { useState, useEffect } from 'react'
import { apiService } from '../services/api'

export default function SavedLeads() {
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchLeads()
  }, [])

  const fetchLeads = async () => {
    try {
      setLoading(true)
      const data = await apiService.getLeads({ page: 1, page_size: 50 })
      setLeads(data.results || [])
    } catch (error) {
      console.error('Failed to fetch leads:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Saved Leads</h1>
      {/* Display leads here */}
      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : (
        <div className="grid gap-4">
          {leads.map(lead => (
            <div key={lead.id} className="p-4 bg-white dark:bg-gray-800 rounded-xl">
              <h3 className="font-semibold">{lead.company_name}</h3>
              <p className="text-sm text-gray-500">{lead.city} • {lead.source}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}