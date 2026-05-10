import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Activity, CheckCircle, Circle } from 'lucide-react'
import { apiService } from '../../services/api'

const STAGE_LABELS = [
  'Discovery',
  'Scraping',
  'Qualifying',
  'Enriching',
  'AI Scoring',
  'Saving Results',
]

// Map backend stage strings → index
const stageIndex = (stageStr = '') => {
  const s = stageStr.toLowerCase()
  if (s.includes('scrap')) return 1
  if (s.includes('qualif') || s.includes('filter') || s.includes('dedup')) return 2
  if (s.includes('enrich')) return 3
  if (s.includes('scor') || s.includes('ai') || s.includes('message')) return 4
  if (s.includes('sav') || s.includes('done') || s.includes('complet')) return 5
  return 0
}

// jobId passed from Dashboard when RunSearch fires
export default function LiveStatus({ jobId }) {
  const [currentStage, setCurrentStage] = useState(-1)
  const [logs, setLogs] = useState(['System ready. Waiting for search...'])
  const [isRunning, setIsRunning] = useState(false)
  const [isDone, setIsDone] = useState(false)
  const intervalRef = useRef(null)

  const addLog = (msg) => setLogs(prev => [msg, ...prev].slice(0, 12))

  useEffect(() => {
    if (!jobId) return

    // New job started — reset
    setCurrentStage(0)
    setIsRunning(true)
    setIsDone(false)
    setLogs([`Job ${jobId} started...`])

    if (intervalRef.current) clearInterval(intervalRef.current)

    intervalRef.current = setInterval(async () => {
      try {
        const job = await apiService.getJob(jobId)
        const idx = stageIndex(job.stage)
        setCurrentStage(idx)
        addLog(`[${job.stage || 'running'}] ${job.message || ''}`)

        if (job.status === 'done') {
          clearInterval(intervalRef.current)
          setCurrentStage(5)
          setIsRunning(false)
          setIsDone(true)
          const total = job.result?.total_leads ?? 0
          const hot = job.result?.hot_leads?.length ?? 0
          addLog(`✅ Done! ${total} leads found. ${hot} HOT.`)
        } else if (job.status === 'error') {
          clearInterval(intervalRef.current)
          setIsRunning(false)
          addLog(`❌ Pipeline failed: ${job.error || 'Unknown error'}`)
        }
      } catch (err) {
        clearInterval(intervalRef.current)
        setIsRunning(false)
        addLog('⚠️ Lost connection to backend.')
      }
    }, 2000)

    return () => clearInterval(intervalRef.current)
  }, [jobId])

  const progress = currentStage < 0 ? 0 : Math.round((currentStage / (STAGE_LABELS.length - 1)) * 100)

  return (
    <div className="rounded-2xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 overflow-hidden h-full">
      <div className="p-6 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold flex items-center gap-2">
              <Activity className={`w-5 h-5 ${isRunning ? 'text-indigo-500 animate-pulse' : 'text-gray-400'}`} />
              Live Status
            </h3>
            <p className="text-xs text-gray-500 mt-1">Real-time pipeline execution</p>
          </div>
          {isDone && (
            <span className="px-2 py-1 text-xs bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400 rounded-lg font-medium">
              Complete
            </span>
          )}
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Progress bar */}
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="font-medium">
              {currentStage < 0 ? 'Idle' : STAGE_LABELS[currentStage] || 'Complete'}
            </span>
            <span className="text-gray-500">{progress}%</span>
          </div>
          <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-indigo-500 to-cyan-500"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>

        {/* Stage timeline */}
        <div className="space-y-3">
          {STAGE_LABELS.map((label, idx) => {
            const done = idx < currentStage
            const active = idx === currentStage && isRunning
            const pending = idx > currentStage
            return (
              <div key={label} className="flex items-center gap-3">
                <div className="relative">
                  {done ? (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  ) : active ? (
                    <CheckCircle className="w-5 h-5 text-indigo-500 animate-pulse" />
                  ) : (
                    <Circle className="w-5 h-5 text-gray-300 dark:text-gray-600" />
                  )}
                  {idx < STAGE_LABELS.length - 1 && (
                    <div className={`absolute top-5 left-2.5 w-0.5 h-5 -translate-x-1/2 ${done ? 'bg-green-500' : 'bg-gray-200 dark:bg-gray-700'}`} />
                  )}
                </div>
                <span className={`text-sm ${done || active ? 'text-gray-900 dark:text-white font-medium' : 'text-gray-400'}`}>
                  {label}
                </span>
              </div>
            )
          })}
        </div>

        {/* Terminal logs */}
        <div>
          <p className="text-xs font-mono text-gray-500 mb-2">Execution Logs</p>
          <div className="bg-gray-900 rounded-xl p-3 font-mono text-xs space-y-1 h-32 overflow-y-auto">
            <AnimatePresence>
              {logs.map((log, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="text-gray-300"
                >
                  {log}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  )
}