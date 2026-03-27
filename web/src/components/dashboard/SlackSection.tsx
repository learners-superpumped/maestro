import { useNavigate } from "@tanstack/react-router"
import { Skeleton } from "@/components/ui/skeleton"
import { formatRelativeTime } from "@/lib/time"

interface Task {
  id: string
  title: string
  slack_notification_channel?: string
  updated_at?: string
  created_at: string
}

interface Props {
  tasks: Task[]
  loading: boolean
}

export function SlackSection({ tasks, loading }: Props) {
  const navigate = useNavigate()
  const shown = tasks
    .filter((t) => t.slack_notification_channel)
    .slice(0, 3)

  if (!loading && shown.length === 0) return null

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="text-[11px] uppercase tracking-wide font-medium text-[#9b9a97]">
          Slack-linked Tasks
        </span>
      </div>

      <div className="space-y-px">
        {loading &&
          [1, 2].map((i) => (
            <div key={i} className="flex items-center gap-2.5 px-2 py-2">
              <Skeleton className="h-3.5 w-20 bg-[#f7f6f3]" />
              <Skeleton className="h-3.5 flex-1 bg-[#f7f6f3]" />
            </div>
          ))}

        {!loading &&
          shown.map((task) => {
            const timeStr = formatRelativeTime(task.updated_at || task.created_at)
            return (
              <button
                key={task.id}
                onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
                className="w-full flex items-center gap-2.5 px-2 py-2 rounded hover:bg-[#f9f9f8] transition-colors text-left"
              >
                <span className="text-[11px] font-mono text-[#787774] shrink-0">
                  #{task.slack_notification_channel}
                </span>
                <span className="text-[13px] text-[#37352f] truncate flex-1">{task.title}</span>
                <span className="text-[11px] text-[#9b9a97] shrink-0">{timeStr}</span>
              </button>
            )
          })}
      </div>
    </div>
  )
}
