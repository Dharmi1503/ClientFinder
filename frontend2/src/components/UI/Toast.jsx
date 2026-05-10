export default function Toast({ title, message }) {
  return (
    <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 shadow-soft">
      <p className="font-semibold">{title}</p>
      <p className="mt-1 text-blue-800">{message}</p>
    </div>
  )
}
