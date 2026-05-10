import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Search, Zap, Loader2 } from 'lucide-react'

const services = [
  'AI Automation', 
  'Website Development', 
  'App Development', 
  'Digital Marketing', 
  'ML Solutions',
  'SEO Services',        // Add yours
  'Social Media Marketing', // Add yours
  'CRM Implementation'   // Add yours
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
  'Healthcare'           // Add yours
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
  'Jaipur',              // Add yours
  'Lucknow',             // Add yours
  'Chandigarh',          // Add yours
  'Goa'                  // Add yours
]

export default function SearchPipeline() {
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    service: 'Website Development',
    industry: 'Hospitals',
    location: 'Delhi NCR',
    budget: '',
    maxLeads: 10,
    fastMode: true,
  })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    // Simulate API call
    setTimeout(() => setLoading(false), 2000)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 overflow-hidden"
    >
      <div className="p-6 border-b border-gray-200 dark:border-gray-800">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Search className="w-5 h-5 text-primary-500" />
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
              className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
            >
              {services.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2">Industry</label>
            <select
              value={formData.industry}
              onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
            >
              {industries.map(i => <option key={i}>{i}</option>)}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2">Location</label>
            <select
              value={formData.location}
              onChange={(e) => setFormData({ ...formData, location: e.target.value })}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
            >
              {locations.map(l => <option key={l}>{l}</option>)}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2">Budget Range</label>
            <input
              type="text"
              value={formData.budget}
              onChange={(e) => setFormData({ ...formData, budget: e.target.value })}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2">Max Leads</label>
            <input
              type="number"
              value={formData.maxLeads}
              onChange={(e) => setFormData({ ...formData, maxLeads: parseInt(e.target.value) })}
              min={1}
              max={100}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
            />
          </div>
          
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium">Fast Mode</label>
            <button
              type="button"
              onClick={() => setFormData({ ...formData, fastMode: !formData.fastMode })}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${formData.fastMode ? 'bg-primary-500' : 'bg-gray-300 dark:bg-gray-700'}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${formData.fastMode ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-gradient-to-r from-primary-500 to-accent-500 text-white font-semibold rounded-xl hover:shadow-lg transition-all duration-300 disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Analyzing Market...
            </>
          ) : (
            <>
              <Zap className="w-5 h-5" />
              Run AI Search
            </>
          )}
        </button>
      </form>
    </motion.div>
  )
}