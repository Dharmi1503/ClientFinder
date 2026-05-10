const analytics = [
  { label: 'Open rate', value: '48.2%', note: '12.4% above average' },
  { label: 'Positive replies', value: '19.7%', note: 'Steady week-over-week' },
  { label: 'Time to first touch', value: '4h 12m', note: 'Improving with automation' },
  { label: 'Conversion value', value: '$92k', note: 'Attributed pipeline' },
]

export default function AnalyticsCards() {
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {analytics.map((item) => (
        <article key={item.label} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-soft">
          <p className="text-sm font-medium text-slate-500">{item.label}</p>
          <p className="mt-3 text-3xl font-bold text-slate-900">{item.value}</p>
          <p className="mt-2 text-sm text-slate-500">{item.note}</p>
        </article>
      ))}
    </section>
  )
}
