import { TaskBoardCard } from "@/components/TaskBoardCard"

const COLUMNS = [
  { key: "pending", label: "Pending", color: "#9b9a97" },
  { key: "running", label: "Running", color: "#2383e2" },
  { key: "paused", label: "Paused", color: "#cb912f" },
  { key: "completed", label: "Completed", color: "#4dab9a" },
  { key: "failed", label: "Failed", color: "#eb5757" },
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
    else if (grouped["pending"]) grouped["pending"].push(task)
  }

  return (
    <div className="flex gap-3 overflow-x-auto pb-4">
      {COLUMNS.map((col) => (
        <div key={col.key} className="flex-shrink-0 w-[240px] min-h-[200px]">
          {/* Column header */}
          <div className="flex items-center gap-2 mb-3 pb-2 border-b-2" style={{ borderColor: col.color }}>
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: col.color }} />
            <h3 className="text-[12px] uppercase tracking-wider font-medium text-[#37352f]">
              {col.label}
            </h3>
            <span className="text-[12px] text-[#9b9a97] ml-auto">
              {grouped[col.key].length || ""}
            </span>
          </div>
          {/* Cards */}
          <div className="space-y-2">
            {grouped[col.key].map((task: any) => (
              <TaskBoardCard key={task.id} task={task} />
            ))}
            {grouped[col.key].length === 0 && (
              <div className="text-[12px] text-[#9b9a97] text-center py-6">
                No tasks
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
