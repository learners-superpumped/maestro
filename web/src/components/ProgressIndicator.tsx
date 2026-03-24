export function ProgressIndicator({ total, completed }: { total: number; completed: number }) {
  if (total === 0) return null
  return (
    <span className="text-xs text-gray-400 font-mono">
      {completed}/{total}
    </span>
  )
}
