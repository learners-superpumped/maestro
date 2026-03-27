import { useNavigate } from "@tanstack/react-router"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusIcon } from "@/components/StatusIcon"
import { formatElapsed } from "@/lib/time"

interface Task {
  id: string
  task_number?: number
  title: string
  goal_id?: string
  agent?: string
  started_at?: string
  created_at: string
}

interface Props {
  tasks: Task[]
  loading: boolean
}

export function RunningSection({ tasks, loading }: Props) {
  const navigate = useNavigate()

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1.5">
        {/* Spinning status icon as section header accent */}
        <StatusIcon status="running" size={12} />
        <span className="text-[11px] uppercase tracking-wide font-medium text-[#9b9a97]">
          Running Tasks
        </span>
        {!loading && tasks.length > 0 && (
          <span className="ml-auto text-[11px] text-[#f2994a] font-medium tabular-nums">
            {tasks.length} active
          </span>
        )}
      </div>

      <div className="space-y-px">
        {loading &&
          [1, 2].map((i) => (
            <div key={i} className="flex items-center gap-2.5 px-2 py-2">
              <Skeleton className="h-3.5 w-3.5 rounded-full bg-[#f7f6f3]" />
              <Skeleton className="h-3.5 flex-1 bg-[#f7f6f3]" />
              <Skeleton className="h-3.5 w-12 bg-[#f7f6f3]" />
            </div>
          ))}

        {!loading && tasks.length === 0 && (
          <div className="px-2 py-3 text-[12px] text-[#9b9a97]">No running tasks</div>
        )}

        {!loading &&
          tasks.map((task) => (
            <button
              key={task.id}
              onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
              className="w-full flex items-center gap-2.5 px-2 py-2 rounded hover:bg-[#f9f9f8] transition-colors text-left"
            >
              <StatusIcon status="running" size={14} />
              <div className="flex-1 min-w-0">
                <div className="text-[13px] text-[#37352f] truncate">{task.title}</div>
                {(task.goal_id || task.agent) && (
                  <div className="text-[11px] text-[#9b9a97] truncate">
                    {[task.agent, task.goal_id && `goal:${task.goal_id}`]
                      .filter(Boolean)
                      .join(" · ")}
                  </div>
                )}
              </div>
              <span className="text-[12px] text-[#9b9a97] tabular-nums shrink-0">
                {task.started_at ? formatElapsed(task.started_at) : "—"}
              </span>
            </button>
          ))}
      </div>
    </div>
  )
}
