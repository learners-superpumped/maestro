import { cn } from "@/lib/utils"
import { Eye, Sparkles } from "lucide-react"

/**
 * Displays task type as a user-friendly badge.
 *
 * System types (review, planning) get a visible badge so users
 * know these are automated. Regular tasks show nothing — they're
 * just "tasks" from the user's perspective.
 */

const SYSTEM_TYPES: Record<string, { label: string; icon: any; color: string; bg: string }> = {
  review: {
    label: "Review",
    icon: Eye,
    color: "text-[#2383e2]",
    bg: "bg-[#2383e2]/8 border-[#2383e2]/15",
  },
  planning: {
    label: "Auto-planned",
    icon: Sparkles,
    color: "text-[#9065b0]",
    bg: "bg-[#9065b0]/8 border-[#9065b0]/15",
  },
}

export function TaskTypeBadge({ type, className }: { type: string; className?: string }) {
  const config = SYSTEM_TYPES[type]

  // Regular tasks — no badge needed, they're just "tasks"
  if (!config) return null

  const Icon = config.icon

  return (
    <span className={cn(
      "inline-flex items-center gap-1 text-[11px] font-medium border rounded px-1.5 py-0.5",
      config.bg,
      config.color,
      className,
    )}>
      <Icon className="h-3 w-3" />
      {config.label}
    </span>
  )
}

/**
 * Returns a human-readable type label for display in metadata.
 * Used in Properties/Details sections where we need text, not a badge.
 */
export function getTaskTypeLabel(type: string): string {
  if (type === "review") return "Review (automated)"
  if (type === "planning") return "Planning (automated)"
  return "Task"
}
