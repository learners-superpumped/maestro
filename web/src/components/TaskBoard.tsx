import { TaskBoardCard } from "@/components/TaskBoardCard"

const COLUMN_ORDER = ["pending", "running", "paused", "completed", "failed"]

const COLUMN_LABELS: Record<string, string> = {
  pending: "Pending",
  running: "Running",
  paused: "Paused",
  completed: "Completed",
  failed: "Failed",
}

interface TaskBoardProps {
  tasks: any[]
}

export function TaskBoard({ tasks }: TaskBoardProps) {
  const grouped: Record<string, any[]> = {}
  for (const col of COLUMN_ORDER) grouped[col] = []
  for (const task of tasks) {
    const s = task.effective_status ?? task.status
    if (grouped[s]) grouped[s].push(task)
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {COLUMN_ORDER.map((status) => (
        <div key={status} className="flex-shrink-0 w-[260px]">
          <div className="border-t border-[#e8e5df] pt-3">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[12px] uppercase tracking-wider font-medium text-[#9b9a97]">
                {COLUMN_LABELS[status]}
              </h3>
              {grouped[status].length > 0 && (
                <span className="text-[12px] text-[#9b9a97]">{grouped[status].length}</span>
              )}
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
