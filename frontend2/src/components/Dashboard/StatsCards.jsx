import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Flame, Sun, Snowflake, Clock, TrendingUp, TrendingDown } from 'lucide-react'
import { apiService } from '../../services/api'

const CARD_DEFS = [
  { label: 'HOT Leads',    icon: Flame,     color: '#ef4444', bgColor: 'rgba(239,68,68,0.1)',    labelFilter: 'HOT' },
  { label: 'WARM Leads',   icon: Sun,       color: '#f59e0b', bgColor: 'rgba(245,158,11,0.1)',   labelFilter: 'WARM' },
  { label: 'COLD Leads',   icon: Snowflake, color: '#3b82f6', bgColor: 'rgba(59,130,246,0.1)',   labelFilter: 'COLD' },
  { label: 'Review Queue', icon: Clock,     color: '#a855f7', bgColor: 'rgba(168,85,247,0.1)',   labelFilter: 'review' },
]

function useCountUp(target, duration = 900) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    if (!target) { setValue(0); return }
    let start = 0
    const step = target / (duration / 16)
    const timer = setInterval(() => {
      start += step
      if (start >= target) { setValue(target); clearInterval(timer) }
      else setValue(Math.floor(start))
    }, 16)
    return () => clearInterval(timer)
  }, [target])
  return value
}

function StatCard({ def, value, idx }) {
  const animated = useCountUp(value)
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.1 }}
      whileHover={{ y: -4 }}
      className="relative overflow-hidden rounded-2xl glass shadow-lg hover:shadow-xl transition-all duration-300"
      style={{ boxShadow: `0 20px 25px -5px ${def.color}20` }}
    >
      <div className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="p-3 rounded-xl" style={{ backgroundColor: def.bgColor }}>
            <def.icon style={{ color: def.color, width: 24, height: 24 }} />
          </div>
        </div>
        <h3 className="text-3xl font-bold text-gray-900 dark:text-white mb-1">
          {animated.toLocaleString()}
        </h3>
        <p className="text-gray-500 dark:text-gray-400 text-sm">{def.label}</p>
      </div>
    </motion.div>
  )
}

export default function StatsCards({ refreshTrigger }) {
  const [counts, setCounts] = useState({ HOT: 0, WARM: 0, COLD: 0, review: 0 })
  const [loading, setLoading] = useState(true)

  const fetchCounts = async () => {
    try {
      // Fetch all leads with minimal page size just to get totals
      const [hot, warm, cold, reviewQueue] = await Promise.all([
        apiService.getLeads({ label: 'HOT',  page: 1, page_size: 1 }),
        apiService.getLeads({ label: 'WARM', page: 1, page_size: 1 }),
        apiService.getLeads({ label: 'COLD', page: 1, page_size: 1 }),
        apiService.getReviewQueue(),
      ])
      setCounts({
        HOT:    hot.total    ?? hot.results?.length    ?? 0,
        WARM:   warm.total   ?? warm.results?.length   ?? 0,
        COLD:   cold.total   ?? cold.results?.length   ?? 0,
        review: reviewQueue.total ?? (Array.isArray(reviewQueue) ? reviewQueue.length : reviewQueue.results?.length) ?? 0,
      })
    } catch (err) {
      console.error('StatsCards fetch failed:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchCounts() }, [refreshTrigger])

  const values = [counts.HOT, counts.WARM, counts.COLD, counts.review]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {CARD_DEFS.map((def, idx) => (
        <StatCard key={def.label} def={def} value={values[idx]} idx={idx} />
      ))}
    </div>
  )
}
