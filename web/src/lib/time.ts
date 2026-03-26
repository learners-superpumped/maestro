export function formatRelativeTime(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHr = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHr / 24)

  if (diffMin < 1) return "just now"
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHr < 24) return `${diffHr}h ago`
  if (diffDay < 7) return `${diffDay}d ago`
  return date.toLocaleDateString([], { month: "short", day: "numeric" })
}

export function formatElapsed(startIso: string): string {
  const start = new Date(startIso)
  const now = new Date()
  const diffSec = Math.max(0, Math.floor((now.getTime() - start.getTime()) / 1000))
  const h = Math.floor(diffSec / 3600)
  const m = Math.floor((diffSec % 3600) / 60)
  const s = diffSec % 60
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
  return `${m}:${String(s).padStart(2, "0")}`
}

export function formatTaskTime(task: { status: string; started_at?: string; updated_at?: string }): string {
  if (task.status === "running" && task.started_at) {
    return formatElapsed(task.started_at)
  }
  if (task.updated_at) {
    return formatRelativeTime(task.updated_at)
  }
  return "—"
}
