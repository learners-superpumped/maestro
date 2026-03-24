import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const statusConfig: Record<string, { label: string; className: string }> = {
  running: {
    label: "Running",
    className: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  },
  completed: {
    label: "Completed",
    className: "bg-green-500/20 text-green-400 border-green-500/30",
  },
  failed: {
    label: "Failed",
    className: "bg-red-500/20 text-red-400 border-red-500/30",
  },
  pending: {
    label: "Pending",
    className: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  },
  paused: {
    label: "Paused",
    className: "bg-violet-500/20 text-violet-400 border-violet-500/30",
  },
  cancelled: {
    label: "Cancelled",
    className: "bg-gray-500/20 text-gray-400 border-gray-500/30",
  },
  approved: {
    label: "Approved",
    className: "bg-sky-500/20 text-sky-400 border-sky-500/30",
  },
  claimed: {
    label: "Claimed",
    className: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  },
  retry_queued: {
    label: "Retry Queued",
    className: "bg-pink-500/20 text-pink-400 border-pink-500/30",
  },
}

interface StatusBadgeProps {
  status: string
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status] ?? {
    label: status,
    className: "bg-gray-700/50 text-gray-400 border-gray-600/30",
  }
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-xs font-medium border",
        config.className,
        className
      )}
    >
      {config.label}
    </Badge>
  )
}
