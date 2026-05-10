import React, { useState } from 'react'
import { motion } from 'framer-motion'
import StatsCards from '../components/Dashboard/StatsCards'
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
    <div className="space-y-6">
      {/* Welcome */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-500 p-8 text-white"
      >
        <div className="relative z-10">
          <h1 className="text-3xl font-bold mb-2">Welcome back 👋</h1>
          <p className="text-indigo-100">Find clients smarter with AI-powered lead discovery</p>
        </div>
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/10 rounded-full blur-2xl translate-y-1/2 -translate-x-1/2" />
      </motion.div>

      {/* Stats — refresh when pipeline completes */}
      <StatsCards refreshTrigger={refreshTrigger} />

      {/* Search + Live Status side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <RunSearch onJobStart={handleJobStart} />
        </div>
        <div>
          <LiveStatus jobId={activeJobId} onDone={handleJobDone} />
        </div>
      </div>

      {/* Analytics */}
      <AnalyticsCards />

      {/* Leads table — refresh when pipeline completes */}
      <LeadsTable refreshTrigger={refreshTrigger} />
    </div>
  )
}