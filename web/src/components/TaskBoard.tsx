import { TaskBoardCard } from "@/components/TaskBoardCard"

const COLUMNS = [
  { key: "pending", label: "Pending" },
  { key: "running", label: "Running" },
  { key: "paused", label: "Paused" },
  { key: "completed", label: "Completed" },
  { key: "failed", label: "Failed" },
]

interface TaskBoardProps {
  tasks: any[]
}

export function TaskBoard({ tasks }: TaskBoardProps) {
  const grouped: Record<string, any[]> = {}
  for (const col of COLUMNS) grouped[col.key] = []
  for (const task of tasks) {
    const s = task.effective_status ?? task.status
    if (grouped[s]) grouped[s].push(task)
    else grouped["pending"]?.push(task)
  }

  return (
    <div className="flex gap-3 overflow-x-auto pb-4">
      {COLUMNS.map((col) => {
        const count = grouped[col.key].length
        return (
          <div key={col.key} className="flex-shrink-0 w-[240px]">
            <div className="flex items-center gap-1.5 mb-3 h-[28px]">
              <h3 className="text-[13px] font-medium text-[#37352f]">
                {col.label}
              </h3>
              {count > 0 && (
                <span className="text-[12px] text-[#9b9a97]">{count}</span>
              )}
            </div>
            <div className="space-y-2 min-h-[120px]">
              {grouped[col.key].map((task: any) => (
                <TaskBoardCard key={task.id} task={task} />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
