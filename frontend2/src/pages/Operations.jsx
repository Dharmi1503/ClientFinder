import React, { useEffect, useState } from 'react'

import { apiService } from '../services/api'

function buildOperationalNotes({ runningJobs, failedJobs, reviewCount }) {
  const notes = []

  if (runningJobs > 0) {
    notes.push(`${runningJobs} job${runningJobs === 1 ? '' : 's'} currently running in this session.`)
  }
  if (reviewCount > 0) {
    notes.push(`${reviewCount} lead${reviewCount === 1 ? '' : 's'} waiting for manual review.`)
  }
  if (failedJobs > 0) {
    notes.push(`${failedJobs} job${failedJobs === 1 ? '' : 's'} failed and should be checked in the backend logs.`)
  }

  if (!notes.length) {
    notes.push('No active jobs or review backlog right now.')
  }

  return notes
}

export default function Operations() {
  const [summary, setSummary] = useState({
    runningJobs: 0,
    reviewCount: 0,
    failedJobs: 0,
  })

  useEffect(() => {
    let ignore = false

    const loadOperations = async () => {
      try {
        const [jobsResponse, reviewResponse] = await Promise.all([
          apiService.getAllJobs(),
          apiService.getReviewQueue(),
        ])

        if (ignore) return

        const jobs = Array.isArray(jobsResponse) ? jobsResponse : []
        const reviewQueue = reviewResponse.leads || []

        setSummary({
          runningJobs: jobs.filter((job) => job.status === 'running').length,
          failedJobs: jobs.filter((job) => job.status === 'error').length,
          reviewCount: reviewQueue.length,
        })
      } catch (error) {
        console.error('Operations fetch failed:', error)
      }
    }

    loadOperations()
    return () => {
      ignore = true
    }
  }, [])

  const cards = [
    { label: 'Import jobs', value: `${summary.runningJobs} running` },
    { label: 'Review queue', value: `${summary.reviewCount} pending` },
    { label: 'Failed jobs', value: `${summary.failedJobs} flagged` },
  ]

  const notes = buildOperationalNotes(summary)

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-soft">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-blue-600">Operations</p>
        <h2 className="mt-2 text-3xl font-bold text-slate-900">Coordinate the work behind every search.</h2>
        <p className="mt-3 text-slate-600">
          Review queue health, live job status, and failure signals from a single operational pane.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {cards.map((card) => (
          <article key={card.label} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-soft">
            <p className="text-sm font-medium text-slate-500">{card.label}</p>
            <p className="mt-3 text-2xl font-bold text-slate-900">{card.value}</p>
          </article>
        ))}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-slate-50 p-6">
        <h3 className="text-lg font-semibold text-slate-900">Operational notes</h3>
        <ul className="mt-3 space-y-3 max-w-3xl text-sm text-slate-600">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </section>
    </div>
  )
}
