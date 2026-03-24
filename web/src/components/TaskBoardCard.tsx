import { useNavigate } from "@tanstack/react-router"
import { StatusBadge } from "@/components/StatusBadge"
import { ProgressIndicator } from "@/components/ProgressIndicator"
import { Badge } from "@/components/ui/badge"

interface TaskCardProps {
  task: {
    id: string
    title: string
    type: string
    workspace: string
    status: string
    cost_usd?: number
    children_summary?: { total: number; completed: number }
  }
}

export function TaskBoardCard({ task }: TaskCardProps) {
  const navigate = useNavigate()
  return (
    <div
      onClick={() => navigate({ to: "/tasks/$id", params: { id: task.id } })}
      className="bg-gray-800 border border-gray-700 rounded-lg p-3 cursor-pointer hover:bg-gray-750 hover:border-gray-600 transition-colors duration-200 space-y-2"
    >
      <p className="text-sm text-gray-50 font-medium truncate">{task.title}</p>
      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant="outline" className="text-xs border-gray-600 text-gray-400">{task.type}</Badge>
        <span className="text-xs text-gray-500">{task.workspace}</span>
      </div>
      <div className="flex items-center justify-between">
        {task.children_summary && task.children_summary.total > 0 && (
          <ProgressIndicator total={task.children_summary.total} completed={task.children_summary.completed} />
        )}
        {task.cost_usd != null && task.cost_usd > 0 && (
          <span className="text-xs text-gray-500 font-mono">${Number(task.cost_usd).toFixed(4)}</span>
        )}
      </div>
    </div>
  )
}
