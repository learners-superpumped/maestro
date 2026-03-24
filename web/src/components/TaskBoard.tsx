import { TaskBoardCard } from "@/components/TaskBoardCard"

const COLUMN_ORDER = ["pending", "running", "paused", "completed", "failed"]

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
    return <p className="text-center text-[14px] text-[#9b9a97] py-8">No tasks found</p>
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {columns.map((status) => (
        <div key={status} className="flex-shrink-0 w-[260px]">
          <div className="border-t border-[#e8e5df] pt-3">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[12px] uppercase tracking-wider font-medium text-[#9b9a97]">
                {status.replace("_", " ")}
              </h3>
              <span className="text-[12px] text-[#9b9a97]">{grouped[status].length}</span>
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
