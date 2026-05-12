import React, { useState } from 'react'
import { motion } from 'framer-motion'
import StatsCards from '../components/Dashboard/StatsCards'
import { Link } from 'react-router-dom'
import RunSearch from './RunSearch'
import LiveStatus from '../components/Dashboard/LiveStatus'
import LeadsTable from '../components/Dashboard/LeadsTable'
import AnalyticsCards from '../components/Analytics/AnalyticsCards'

export default function Dashboard() {
  // Shared state: RunSearch fires onJobStart → LiveStatus polls it
  const [activeJobId, setActiveJobId] = useState(null)
  // refreshTrigger bumps when job completes so StatsCards + LeadsTable reload
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const handleJobStart = (jobId) => {
    setActiveJobId(jobId)
  }

  const handleJobDone = () => {
    // Bump trigger to reload stats + table
    setRefreshTrigger(t => t + 1)
  }

  return (
    <div className="space-y-10 max-w-[1400px] mx-auto px-4 md:px-0 pb-20">
      {/* Welcome Section */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="relative overflow-hidden rounded-[2.5rem] bg-slate-900 p-10 md:p-16 text-white shadow-2xl"
      >
        {/* Animated Background Gradients */}
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-to-br from-indigo-600/30 to-cyan-500/30 rounded-full blur-[100px] -translate-y-1/2 translate-x-1/2 animate-pulse-slow" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-gradient-to-tr from-purple-600/20 to-pink-500/20 rounded-full blur-[80px] translate-y-1/2 -translate-x-1/2 animate-pulse-slow" style={{ animationDelay: '2s' }} />

        <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-10">
          <div className="max-w-2xl text-center md:text-left">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 backdrop-blur-md border border-white/10 mb-6"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-xs font-bold tracking-wider uppercase">System Active: 2.4k Leads Today</span>
            </motion.div>

            <h1 className="text-5xl md:text-6xl font-black tracking-tight mb-6 leading-tight">
              Scale your outreach <br />
              <span className="bg-gradient-to-r from-indigo-400 via-cyan-400 to-indigo-400 bg-200% bg-clip-text text-transparent animate-gradient">with AI Precision.</span>
            </h1>
            <p className="text-xl text-slate-400 leading-relaxed max-w-xl">
              Stop hunting, start closing. ClientFinder uses neural signals to identify high-intent leads before your competitors do.
            </p>
          </div>

          <div className="hidden lg:block relative">
            <div className="w-64 h-64 bg-gradient-to-br from-indigo-500 to-cyan-500 rounded-[3rem] rotate-12 flex items-center justify-center shadow-2xl shadow-indigo-500/40 relative z-10">
              <div className="text-6xl">🚀</div>
            </div>
            <div className="absolute inset-0 bg-white/10 blur-2xl rounded-[3rem] rotate-12 -z-0" />
          </div>
        </div>
      </motion.div>

      {/* Stats Section */}
      <section className="glass rounded-[2.5rem] p-8 border border-white/20 dark:border-white/5">
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-2xl font-bold tracking-tight">Performance Overview</h2>
          <button className="text-sm font-bold text-indigo-500 hover:text-indigo-600 transition-colors">View Detailed Analytics →</button>
        </div>
        <StatsCards refreshTrigger={refreshTrigger} />
      </section>

      {/* AI Search Guideline Section */}
      <section className="max-w-4xl mx-auto w-full">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass rounded-[2.5rem] p-10 border border-indigo-500/10 shadow-2xl shadow-indigo-500/5 relative overflow-hidden"
        >
          {/* Subtle background glow */}
          <div className="absolute -top-24 -right-24 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
          
          <div className="relative z-10 flex flex-col items-center text-center">
            <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 flex items-center justify-center text-indigo-500 mb-6">
              <span className="text-3xl">🚀</span>
            </div>
            
            <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">Start Your Lead Discovery Pipeline</h2>
            <p className="text-gray-600 dark:text-gray-400 max-w-2xl mb-8 text-lg leading-relaxed">
              Our AI search pipeline scans over 7 business directories and social signals in real-time. 
              Target any <span className="text-indigo-600 dark:text-indigo-400 font-semibold">Industry</span> in any <span className="text-indigo-600 dark:text-indigo-400 font-semibold">City</span> to generate HOT leads with personalized outreach strategies.
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full mb-10">
              <div className="p-4 rounded-2xl bg-gray-50 dark:bg-gray-800/50 border border-gray-100 dark:border-gray-700/50">
                <div className="text-indigo-500 font-bold mb-1">Step 1</div>
                <div className="text-sm font-medium">Select Industry</div>
              </div>
              <div className="p-4 rounded-2xl bg-gray-50 dark:bg-gray-800/50 border border-gray-100 dark:border-gray-700/50">
                <div className="text-indigo-500 font-bold mb-1">Step 2</div>
                <div className="text-sm font-medium">Deep AI Scoring</div>
              </div>
              <div className="p-4 rounded-2xl bg-gray-50 dark:bg-gray-800/50 border border-gray-100 dark:border-gray-700/50">
                <div className="text-indigo-500 font-bold mb-1">Step 3</div>
                <div className="text-sm font-medium">Start Outreach</div>
              </div>
            </div>

            <Link 
              to="/run-search" 
              className="px-10 py-5 bg-gradient-to-r from-indigo-600 to-indigo-500 text-white font-black text-lg rounded-2xl hover:shadow-2xl hover:shadow-indigo-500/30 transition-all transform hover:-translate-y-1 active:scale-95 flex items-center gap-3"
            >
              Launch Search Pipeline
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Link>
          </div>
        </motion.div>
      </section>

      {/* Main Content (Leads Table) */}
      <section className="glass rounded-[2.5rem] overflow-hidden border border-white/20 dark:border-white/5">
        <LeadsTable refreshTrigger={refreshTrigger} />
      </section>

      <AnalyticsCards />
    </div>
  )
}