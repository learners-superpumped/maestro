import { useNavigate } from "@tanstack/react-router"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusIcon } from "@/components/StatusIcon"
import { formatRelativeTime } from "@/lib/time"

interface Task {
  id: string
  task_number?: number
  title: string
  task_type?: string
  status: string
  updated_at?: string
  created_at: string
}

interface Props {
  tasks: Task[]
  loading: boolean
}

export function RecentTasksSection({ tasks, loading }: Props) {
  const navigate = useNavigate()
  const shown = tasks.slice(0, 5)

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="text-[11px] uppercase tracking-wide font-medium text-[#9b9a97]">
          Recent Tasks
        </span>
      </div>

      <div className="space-y-px">
        {loading &&
          [1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-2.5 px-2 py-2">
              <Skeleton className="h-3.5 w-3.5 rounded-full bg-[#f7f6f3]" />
              <Skeleton className="h-3.5 w-16 bg-[#f7f6f3]" />
              <Skeleton className="h-3.5 flex-1 bg-[#f7f6f3]" />
            </div>
          ))}

        {!loading && shown.length === 0 && (
          <div className="px-2 py-3 text-[12px] text-[#9b9a97]">No tasks</div>
        )}

        {!loading &&
          shown.map((task) => {
            const timeStr = formatRelativeTime(task.updated_at || task.created_at)
            return (
              <button
                key={task.id}
                onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
                className="w-full flex items-center gap-2.5 px-2 py-2 rounded hover:bg-[#f9f9f8] transition-colors text-left"
              >
                <StatusIcon status={task.status} size={14} />
                {task.task_number != null && (
                  <span className="text-[11px] font-mono text-[#9b9a97] shrink-0">
                    MAE-{task.task_number}
                  </span>
                )}
                <span className="text-[13px] text-[#37352f] truncate flex-1">{task.title}</span>
                {task.task_type && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#f4f2ef] text-[#787774] shrink-0">
                    {task.task_type}
                  </span>
                )}
                <span className="text-[11px] text-[#9b9a97] shrink-0">{timeStr}</span>
              </button>
            )
          })}
      </div>
    </div>
  )
}
