export function ProgressIndicator({ total, completed }: { total: number; completed: number }) {
  if (total === 0) return null
  return (
    <span className="text-[12px] text-[#9b9a97] font-mono">
      {completed}/{total}
    </span>
  )
}
