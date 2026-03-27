import { MessageSquare, ChevronRight } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { formatRelativeTime } from "@/lib/time"
import { useConductorPanel } from "@/contexts/conductor-panel-context"

interface Conversation {
  id: string
  title?: string
  message_count?: number
  created_at: string
  updated_at?: string
}

// Stable color based on conversation id
function avatarColor(id: string): string {
  const colors = ["#2383e2", "#4dab9a", "#9065b0", "#f2994a", "#cb912f", "#eb5757"]
  let hash = 0
  for (let i = 0; i < id.length; i++) hash = id.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
}

function initials(title?: string): string {
  if (!title) return "C"
  return title
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("")
}

interface Props {
  conversations: Conversation[]
  loading: boolean
}

export function ConductorSection({ conversations, loading }: Props) {
  const { openConversation } = useConductorPanel()
  const shown = conversations.slice(0, 3)

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          <MessageSquare className="h-3.5 w-3.5 text-[#9b9a97]" />
          <span className="text-[11px] uppercase tracking-wide font-medium text-[#9b9a97]">
            Conductor Conversations
          </span>
        </div>
        <button
          onClick={() => openConversation()}
          className="flex items-center gap-0.5 text-[12px] text-[#2383e2] hover:underline"
        >
          View all
          <ChevronRight className="h-3 w-3" />
        </button>
      </div>

      <div className="space-y-px">
        {loading &&
          [1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-2.5 px-2 py-2">
              <Skeleton className="h-6 w-6 rounded-full bg-[#f7f6f3]" />
              <div className="flex-1 space-y-1">
                <Skeleton className="h-3.5 w-3/4 bg-[#f7f6f3]" />
                <Skeleton className="h-3 w-1/2 bg-[#f7f6f3]" />
              </div>
            </div>
          ))}

        {!loading && shown.length === 0 && (
          <div className="px-2 py-3 text-[12px] text-[#9b9a97]">No conversations</div>
        )}

        {!loading &&
          shown.map((conv) => {
            const color = avatarColor(conv.id)
            const timeStr = formatRelativeTime(conv.updated_at || conv.created_at)
            return (
              <button
                key={conv.id}
                onClick={() => openConversation(conv.id)}
                className="w-full flex items-center gap-2.5 px-2 py-2 rounded hover:bg-[#f9f9f8] transition-colors text-left"
              >
                <div
                  className="h-6 w-6 rounded-full flex items-center justify-center shrink-0 text-white text-[10px] font-semibold"
                  style={{ backgroundColor: color }}
                >
                  {initials(conv.title)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[13px] text-[#37352f] truncate">
                      {conv.title || "New conversation"}
                    </span>
                    <span className="text-[11px] text-[#9b9a97] shrink-0">{timeStr}</span>
                  </div>
                  {conv.message_count != null && (
                    <div className="text-[11px] text-[#9b9a97]">
                      {conv.message_count} message{conv.message_count !== 1 ? "s" : ""}
                    </div>
                  )}
                </div>
                {conv.message_count != null && conv.message_count > 0 && (
                  <span
                    className={cn(
                      "h-4 min-w-4 px-1 rounded-full text-[10px] font-semibold text-white flex items-center justify-center shrink-0",
                      "bg-[#2383e2]"
                    )}
                  >
                    {conv.message_count > 9 ? "9+" : conv.message_count}
                  </span>
                )}
              </button>
            )
          })}
      </div>
    </div>
  )
}
