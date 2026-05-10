export default function Operations() {
  const jobs = [
    { label: 'Import jobs', value: '6 running' },
    { label: 'Review queue', value: '14 pending' },
    { label: 'Alerts', value: '2 escalations' },
  ]

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-soft">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-blue-600">Operations</p>
        <h2 className="mt-2 text-3xl font-bold text-slate-900">Coordinate the work behind every search.</h2>
        <p className="mt-3 text-slate-600">
          Review queue health, job status, and escalation points from a single operational pane.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {jobs.map((job) => (
          <article key={job.label} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-soft">
            <p className="text-sm font-medium text-slate-500">{job.label}</p>
            <p className="mt-3 text-2xl font-bold text-slate-900">{job.value}</p>
          </article>
        ))}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-slate-50 p-6">
        <h3 className="text-lg font-semibold text-slate-900">Operational notes</h3>
        <p className="mt-3 max-w-3xl text-sm text-slate-600">
          Use this area for handoff rules, retry logic, and team checklists. It gives the workspace a natural place for
          process control without adding complexity to the main dashboard.
        </p>
      </section>
    </div>
  )
}
