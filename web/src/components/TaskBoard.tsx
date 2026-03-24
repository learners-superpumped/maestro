import { TaskBoardCard } from "@/components/TaskBoardCard"

const COLUMN_ORDER = ["pending", "running", "paused", "completed", "failed"]
const COLUMN_COLORS: Record<string, string> = {
  pending: "border-amber-500/30",
  running: "border-blue-500/30",
  paused: "border-violet-500/30",
  completed: "border-green-500/30",
  failed: "border-red-500/30",
}

interface TaskBoardProps {
  tasks: any[]
}

export function TaskBoard({ tasks }: TaskBoardProps) {
  // Group tasks by status
  const grouped: Record<string, any[]> = {}
  for (const task of tasks) {
    const s = task.status
    if (!grouped[s]) grouped[s] = []
    grouped[s].push(task)
  }

  // Only show columns that have tasks, in defined order
  const columns = COLUMN_ORDER.filter((s) => grouped[s]?.length)

  if (columns.length === 0) {
    return <p className="text-center text-gray-500 py-8">No tasks found</p>
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {columns.map((status) => (
        <div key={status} className="flex-shrink-0 w-72">
          <div className={`border-t-2 ${COLUMN_COLORS[status] || "border-gray-700"} pt-3`}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wide">
                {status.replace("_", " ")}
              </h3>
              <span className="text-xs text-gray-500">{grouped[status].length}</span>
            </div>
            <div className="space-y-2">
              {grouped[status].map((task: any) => (
                <TaskBoardCard key={task.id} task={task} />
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
