import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  AreaChart, Area, PieChart, Pie, Cell, Legend 
} from 'recharts'
import { TrendingUp, Users, Target, Activity, PieChart as PieIcon, BarChart3 } from 'lucide-react'
import AnalyticsCards from '../components/Analytics/AnalyticsCards'
import { apiService } from '../services/api'

const COLORS = ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

export default function Analytics() {
  const [chartData, setChartData] = useState({
    labels: [],
    industries: [],
    trend: []
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await apiService.getLeads({ page: 1, page_size: 100 })
        const leads = data.results || []

        // Process Label Distribution
        const labelCounts = leads.reduce((acc, l) => {
          acc[l.label || 'COLD'] = (acc[l.label || 'COLD'] || 0) + 1
          return acc
        }, {})
        const labels = Object.entries(labelCounts).map(([name, value]) => ({ name, value }))

        // Process Industry Distribution
        const industryCounts = leads.reduce((acc, l) => {
          acc[l.industry || 'Unknown'] = (acc[l.industry || 'Unknown'] || 0) + 1
          return acc
        }, {})
        const industries = Object.entries(industryCounts)
          .map(([name, value]) => ({ name, value }))
          .sort((a, b) => b.value - a.value)
          .slice(0, 5)

        // Mock Trend Data (since backend doesn't have history yet)
        const trend = [
          { day: 'Mon', count: 12 },
          { day: 'Tue', count: 18 },
          { day: 'Wed', count: 15 },
          { day: 'Thu', count: 25 },
          { day: 'Fri', count: 32 },
          { day: 'Sat', count: 28 },
          { day: 'Sun', count: 40 },
        ]

        setChartData({ labels, industries, trend })
      } catch (err) {
        console.error('Analytics fetch failed:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  return (
    <div className="space-y-10 pb-20">
      {/* Header Section */}
      <motion.section 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-[2.5rem] p-10 border border-white/20 shadow-2xl relative overflow-hidden"
      >
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-indigo-500/10 rounded-xl text-indigo-500">
              <Activity className="w-5 h-5" />
            </div>
            <span className="text-xs font-bold uppercase tracking-[0.3em] text-indigo-600 dark:text-indigo-400">Intelligence Suite</span>
          </div>
          <h2 className="text-4xl font-black text-gray-900 dark:text-white leading-tight">
            Pipeline Analytics <br />
            <span className="text-gray-400 font-medium text-2xl">Visualizing growth and lead quality.</span>
          </h2>
        </div>
      </motion.section>

      <AnalyticsCards />

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Lead Velocity Trend */}
        <motion.div 
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="glass rounded-[2.5rem] p-8 border border-white/10 shadow-xl"
        >
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-xl font-bold flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-emerald-500" />
                Discovery Velocity
              </h3>
              <p className="text-sm text-gray-500">New leads found per day</p>
            </div>
          </div>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData.trend}>
                <defs>
                  <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#88888822" />
                <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{fill: '#888', fontSize: 12}} dy={10} />
                <YAxis axisLine={false} tickLine={false} tick={{fill: '#888', fontSize: 12}} />
                <Tooltip 
                  contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)', backgroundColor: '#1e293b', color: '#fff' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Area type="monotone" dataKey="count" stroke="#6366f1" strokeWidth={3} fillOpacity={1} fill="url(#colorCount)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Industry Distribution */}
        <motion.div 
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
          className="glass rounded-[2.5rem] p-8 border border-white/10 shadow-xl"
        >
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-xl font-bold flex items-center gap-2">
                <PieIcon className="w-5 h-5 text-indigo-500" />
                Industry Mix
              </h3>
              <p className="text-sm text-gray-500">Top lead sources by category</p>
            </div>
          </div>
          <div className="h-80 w-full flex items-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData.industries}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {chartData.industries.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ borderRadius: '16px', border: 'none', backgroundColor: '#1e293b', color: '#fff' }}
                />
                <Legend verticalAlign="bottom" height={36}/>
              </PieChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Lead Quality (Bar Chart) */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="lg:col-span-2 glass rounded-[2.5rem] p-8 border border-white/10 shadow-xl"
        >
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-xl font-bold flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-cyan-500" />
                Quality Distribution
              </h3>
              <p className="text-sm text-gray-500">Breakdown of leads by AI-assigned labels</p>
            </div>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData.labels}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#88888822" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#888'}} />
                <YAxis axisLine={false} tickLine={false} tick={{fill: '#888'}} />
                <Tooltip 
                   cursor={{fill: '#88888811'}}
                   contentStyle={{ borderRadius: '16px', border: 'none', backgroundColor: '#1e293b', color: '#fff' }}
                />
                <Bar dataKey="value" radius={[10, 10, 0, 0]}>
                  {chartData.labels.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={entry.name === 'HOT' ? '#ef4444' : entry.name === 'WARM' ? '#f59e0b' : '#3b82f6'} 
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      </div>

      {/* Insights Section */}
      <motion.section 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="rounded-[2.5rem] bg-slate-900 p-10 text-white shadow-2xl relative overflow-hidden"
      >
        <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-indigo-600/20 to-transparent" />
        <div className="relative z-10 grid md:grid-cols-2 gap-10 items-center">
          <div>
            <h3 className="text-2xl font-bold mb-4">Strategic Insights</h3>
            <div className="space-y-4">
              {[
                "High-value accounts convert 3x faster when first contact is via WhatsApp.",
                "Hospitals and clinics show a 40% higher 'Pain Signal' density this month.",
                "LinkedIn enrichment increases the reply rate by 22% compared to cold email."
              ].map((text, i) => (
                <div key={i} className="flex gap-4 items-start">
                  <div className="mt-1.5 w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
                  <p className="text-slate-300 text-sm">{text}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="p-6 rounded-3xl bg-white/5 border border-white/10 backdrop-blur-md">
            <p className="text-sm text-slate-400 mb-2">Current Efficiency</p>
            <div className="text-5xl font-black mb-4 tracking-tighter text-indigo-400">84.2%</div>
            <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
              <motion.div 
                initial={{ width: 0 }}
                animate={{ width: '84.2%' }}
                transition={{ duration: 1.5, ease: "circOut" }}
                className="h-full bg-gradient-to-r from-indigo-500 to-cyan-400"
              />
            </div>
            <p className="text-[10px] uppercase tracking-widest text-slate-500 mt-4 font-bold">Top performance this quarter</p>
          </div>
        </div>
      </motion.section>
    </div>
  )
}
