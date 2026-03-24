import { cn } from "@/lib/utils"

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  running:      { color: "bg-[#2383e2]", label: "Running" },
  completed:    { color: "bg-[#4dab9a]", label: "Done" },
  failed:       { color: "bg-[#eb5757]", label: "Failed" },
  pending:      { color: "bg-[#cb912f]", label: "Pending" },
  paused:       { color: "bg-[#9065b0]", label: "Paused" },
  cancelled:    { color: "bg-[#9b9a97]", label: "Cancelled" },
  approved:     { color: "bg-[#2383e2]", label: "Approved" },
  claimed:      { color: "bg-[#cb912f]", label: "Claimed" },
  retry_queued: { color: "bg-[#eb5757]", label: "Retry" },
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const config = STATUS_CONFIG[status] || { color: "bg-[#9b9a97]", label: status }
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[12px] text-[#787774]", className)}>
      {status === "running" ? (
        <span className="relative flex h-2 w-2 shrink-0">
          <span className={cn("animate-ping absolute inline-flex h-full w-full rounded-full opacity-75", config.color)} />
          <span className={cn("relative inline-flex h-2 w-2 rounded-full", config.color)} />
        </span>
      ) : (
        <span className={cn("h-2 w-2 rounded-full shrink-0", config.color)} />
      )}
      {config.label}
    </span>
  )
}
