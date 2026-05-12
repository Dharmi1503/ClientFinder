import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Activity, CheckCircle, Circle, Terminal } from 'lucide-react'
import { apiService } from '../../services/api'

const STAGE_LABELS = [
  'Discovery',
  'Scraping',
  'Qualifying',
  'Enriching',
  'AI Scoring',
  'Saving',
]

const stageIndex = (stageStr = '') => {
  const s = stageStr.toLowerCase()
  if (s.includes('scrap')) return 1
  if (s.includes('qualif') || s.includes('filter') || s.includes('dedup')) return 2
  if (s.includes('enrich')) return 3
  if (s.includes('scor') || s.includes('ai') || s.includes('message')) return 4
  if (s.includes('sav') || s.includes('done') || s.includes('complet')) return 5
  return 0
}

export default function LiveStatus({ jobId, onDone }) {
  const [currentStage, setCurrentStage] = useState(-1)
  const [logs, setLogs] = useState(['System idle. Waiting for search...'])
  const [isRunning, setIsRunning] = useState(false)
  const [isDone, setIsDone] = useState(false)
  const intervalRef = useRef(null)

  const addLog = (msg) => setLogs(prev => [msg, ...prev].slice(0, 8))

  useEffect(() => {
    if (!jobId) return

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
        if (job.message) {
            addLog(`[${job.stage || 'running'}] ${job.message}`)
        }

        if (job.status === 'done') {
          clearInterval(intervalRef.current)
          setCurrentStage(5)
          setIsRunning(false)
          setIsDone(true)
          if (onDone) onDone()
          addLog(`✅ Done! Pipeline execution completed successfully.`)
        } else if (job.status === 'error') {
          clearInterval(intervalRef.current)
          setIsRunning(false)
          addLog(`❌ Pipeline failed: ${job.error || 'Unknown error'}`)
        }
      } catch (err) {
        // keep polling unless it's a hard error
      }
    }, 2000)

    return () => clearInterval(intervalRef.current)
  }, [jobId])

  const progress = currentStage < 0 ? 0 : Math.round((currentStage / (STAGE_LABELS.length - 1)) * 100)

  return (
    <div className="glass rounded-[2rem] border border-white/20 dark:border-white/5 overflow-hidden shadow-2xl">
      <div className="p-6 border-b border-gray-200/50 dark:border-gray-800/50 flex items-center justify-between bg-white/30 dark:bg-gray-900/30">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl ${isRunning ? 'bg-indigo-500/10 text-indigo-500' : 'bg-gray-100 dark:bg-gray-800 text-gray-400'}`}>
            <Activity className={`w-5 h-5 ${isRunning ? 'animate-pulse' : ''}`} />
          </div>
          <div>
            <h3 className="font-bold text-gray-900 dark:text-white">Live Execution Pipeline</h3>
            <p className="text-xs text-gray-500">Tracking search progress in real-time</p>
          </div>
        </div>
        <AnimatePresence>
          {isDone && (
            <motion.span 
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="px-3 py-1 text-xs bg-emerald-500 text-white rounded-full font-black uppercase tracking-wider shadow-lg shadow-emerald-500/20"
            >
              Complete
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      <div className="p-8">
        {/* Horizontal Steps */}
        <div className="relative mb-12">
          <div className="absolute top-1/2 left-0 w-full h-1 bg-gray-100 dark:bg-gray-800 -translate-y-1/2 z-0" />
          <motion.div 
            className="absolute top-1/2 left-0 h-1 bg-gradient-to-r from-indigo-500 to-cyan-500 -translate-y-1/2 z-0"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 1, ease: "circOut" }}
          />
          
          <div className="relative z-10 flex justify-between">
            {STAGE_LABELS.map((label, idx) => {
              const done = idx < currentStage
              const active = idx === currentStage && isRunning
              return (
                <div key={label} className="flex flex-col items-center gap-3">
                  <div className={`w-10 h-10 rounded-2xl flex items-center justify-center transition-all duration-500 shadow-xl ${
                    done ? 'bg-emerald-500 text-white' : 
                    active ? 'bg-indigo-500 text-white scale-110 shadow-indigo-500/30' : 
                    'bg-white dark:bg-gray-900 text-gray-300 dark:text-gray-600 border border-gray-200 dark:border-gray-800'
                  }`}>
                    {done ? <CheckCircle className="w-5 h-5" /> : <span className="text-sm font-bold">{idx + 1}</span>}
                  </div>
                  <span className={`text-[10px] font-black uppercase tracking-widest ${
                    done || active ? 'text-gray-900 dark:text-white' : 'text-gray-400'
                  }`}>
                    {label}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Horizontal Split for Stats and Logs */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="p-5 rounded-[1.5rem] bg-indigo-500/5 border border-indigo-500/10 flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-widest font-bold mb-1">Current Task</p>
              <h4 className="text-lg font-bold text-gray-900 dark:text-white">
                {currentStage < 0 ? 'Awaiting Job' : STAGE_LABELS[currentStage] || 'Execution Finished'}
              </h4>
            </div>
            <div className="text-right">
              <p className="text-xs text-gray-500 uppercase tracking-widest font-bold mb-1">Completion</p>
              <h4 className="text-2xl font-black text-indigo-500">{progress}%</h4>
            </div>
          </div>

          <div className="relative">
            <div className="absolute top-3 right-3 flex items-center gap-1.5 text-[10px] font-mono text-gray-500">
              <Terminal className="w-3 h-3" />
              LIVE_LOGS
            </div>
            <div className="bg-gray-950 rounded-[1.5rem] p-5 font-mono text-[11px] leading-relaxed h-[100px] overflow-y-auto custom-scrollbar border border-white/5 shadow-inner">
              <AnimatePresence>
                {logs.map((log, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: -5 }}
                    animate={{ opacity: 1, x: 0 }}
                    className={`${idx === 0 ? 'text-indigo-400' : 'text-gray-500'}`}
                  >
                    <span className="opacity-30 mr-2">{'>'}</span>
                    {log}
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}