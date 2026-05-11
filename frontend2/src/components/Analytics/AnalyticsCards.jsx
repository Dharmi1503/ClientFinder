import React, { useEffect, useState } from 'react'

import { apiService } from '../../services/api'

const FALLBACK_METRICS = [
  { label: 'Total leads', value: '0', note: 'Saved in the database' },
  { label: 'Average score', value: '0', note: 'Across recent saved leads' },
  { label: 'Review queue', value: '0', note: 'Needs manual review' },
  { label: 'Top source', value: 'N/A', note: 'Most frequent recent source' },
]

function buildMetrics(leads, reviewQueue) {
  const totalLeads = leads.length
  const averageScore = totalLeads
    ? Math.round(
        leads.reduce((sum, lead) => sum + Number(lead.composite_score || 0), 0) / totalLeads
      )
    : 0

  const sourceCounts = leads.reduce((acc, lead) => {
    const source = lead.source || 'unknown'
    acc[source] = (acc[source] || 0) + 1
    return acc
  }, {})

  const topSourceEntry = Object.entries(sourceCounts).sort((a, b) => b[1] - a[1])[0]
  const topSource = topSourceEntry ? topSourceEntry[0] : 'N/A'
  const topSourceCount = topSourceEntry ? topSourceEntry[1] : 0

  return [
    {
      label: 'Total leads',
      value: totalLeads.toLocaleString(),
      note: 'Saved in the database',
    },
    {
      label: 'Average score',
      value: averageScore.toString(),
      note: 'Across recent saved leads',
    },
    {
      label: 'Review queue',
      value: reviewQueue.length.toLocaleString(),
      note: 'Needs manual review',
    },
    {
      label: 'Top source',
      value: topSource,
      note: topSourceCount ? `${topSourceCount} recent leads` : 'No saved source data yet',
    },
  ]
}

export default function AnalyticsCards() {
  const [metrics, setMetrics] = useState(FALLBACK_METRICS)

  useEffect(() => {
    let ignore = false

    const loadMetrics = async () => {
      try {
        const [leadResponse, reviewResponse] = await Promise.all([
          apiService.getLeads({ page: 1, page_size: 100 }),
          apiService.getReviewQueue(),
        ])

        if (ignore) return

        const leads = leadResponse.results || []
        const reviewQueue = reviewResponse.leads || []
        setMetrics(buildMetrics(leads, reviewQueue))
      } catch (error) {
        console.error('AnalyticsCards fetch failed:', error)
      }
    }

    loadMetrics()
    return () => {
      ignore = true
    }
  }, [])

  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {metrics.map((item) => (
        <article key={item.label} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-soft">
          <p className="text-sm font-medium text-slate-500">{item.label}</p>
          <p className="mt-3 text-3xl font-bold text-slate-900">{item.value}</p>
          <p className="mt-2 text-sm text-slate-500">{item.note}</p>
        </article>
      ))}
    </section>
  )
}
