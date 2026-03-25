import { useNavigate } from "@tanstack/react-router"
import { StatusBadge } from "@/components/StatusBadge"
import { TaskTypeBadge } from "@/components/TaskTypeBadge"
import { ProgressIndicator } from "@/components/ProgressIndicator"

interface TaskCardProps {
  task: {
    id: string
    title: string
    type: string
    workspace: string
    status: string
    cost_usd?: number
    children_summary?: { total: number; completed: number }
    depends_on?: string[] | null
  }
}

export function TaskBoardCard({ task }: TaskCardProps) {
  const navigate = useNavigate()
  return (
    <div
      onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
      className="bg-white border border-[#e8e5df] rounded p-3 cursor-pointer hover:bg-[#f7f6f3] transition-colors space-y-2"
    >
      <p className="text-[14px] font-medium text-[#37352f] truncate">{task.title}</p>
      <div className="flex items-center gap-2 flex-wrap">
        <TaskTypeBadge type={task.type} />
        <span className="text-[12px] text-[#9b9a97]">{task.workspace}</span>
        {task.depends_on && task.depends_on.length > 0 && (
          <span className="text-[12px] text-[#cb912f]">
            Waiting for {task.depends_on.length} step{task.depends_on.length > 1 ? "s" : ""}
          </span>
        )}
      </div>
      <div className="flex items-center justify-between">
        {task.children_summary && task.children_summary.total > 0 && (
          <ProgressIndicator total={task.children_summary.total} completed={task.children_summary.completed} />
        )}
        {task.cost_usd != null && task.cost_usd > 0 && (
          <span className="text-[12px] text-[#9b9a97] font-mono">${Number(task.cost_usd).toFixed(4)}</span>
        )}
      </div>
    </div>
  )
}
