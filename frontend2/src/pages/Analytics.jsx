import AnalyticsCards from '../components/Analytics/AnalyticsCards'

export default function Analytics() {
  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-soft">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-blue-600">Analytics</p>
        <h2 className="mt-2 text-3xl font-bold text-slate-900">Measure what improves pipeline quality.</h2>
        <p className="mt-3 text-slate-600">
          Watch response behavior, handoff timing, and conversion value without leaving the workspace.
        </p>
      </section>

      <AnalyticsCards />

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-soft">
          <h3 className="text-lg font-semibold text-slate-900">Trend snapshot</h3>
          <div className="mt-6 h-56 rounded-3xl bg-gradient-to-br from-blue-50 to-cyan-100 p-6">
            <div className="flex h-full items-end gap-3">
              <div className="h-[45%] w-1/5 rounded-t-2xl bg-blue-600" />
              <div className="h-[60%] w-1/5 rounded-t-2xl bg-cyan-500" />
              <div className="h-[72%] w-1/5 rounded-t-2xl bg-emerald-500" />
              <div className="h-[52%] w-1/5 rounded-t-2xl bg-amber-500" />
              <div className="h-[82%] w-1/5 rounded-t-2xl bg-slate-900" />
            </div>
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-slate-900 p-6 text-white shadow-soft">
          <h3 className="text-lg font-semibold">Insights</h3>
          <ul className="mt-6 space-y-4 text-sm text-slate-300">
            <li>High-value accounts convert faster when first contact lands within six hours.</li>
            <li>Personalized intros increase reply quality more than volume-focused follow-up.</li>
            <li>Industries with narrow buyer pools benefit most from manual review gates.</li>
          </ul>
        </div>
      </section>
    </div>
  )
}
