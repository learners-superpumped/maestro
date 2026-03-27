import { useNavigate } from "@tanstack/react-router"
import { Skeleton } from "@/components/ui/skeleton"

interface Goal {
  id: string
  description: string
  enabled: number | boolean
  metrics?: Record<string, any>
}

interface Props {
  goals: Goal[]
  tasksByGoalId: Record<string, { total: number; done: number }>
  loading: boolean
}

const BAR_COLORS = ["#2383e2", "#4dab9a", "#f2994a"]

export function GoalsWidget({ goals, tasksByGoalId, loading }: Props) {
  const navigate = useNavigate()
  const active = goals.filter((g) => g.enabled).slice(0, 3)

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <span className="text-[11px] uppercase tracking-wide font-medium text-[#9b9a97]">
          Goals
        </span>
      </div>

      <div className="space-y-2">
        {loading &&
          [1, 2].map((i) => (
            <div key={i} className="space-y-1 px-1">
              <Skeleton className="h-3.5 w-3/4 bg-[#f7f6f3]" />
              <Skeleton className="h-[3px] w-full bg-[#f7f6f3]" />
            </div>
          ))}

        {!loading && active.length === 0 && (
          <div className="px-1 py-2 text-[12px] text-[#9b9a97]">활성 Goal 없음</div>
        )}

        {!loading &&
          active.map((goal, idx) => {
            const stats = tasksByGoalId[goal.id] ?? { total: 0, done: 0 }
            const pct = stats.total > 0 ? Math.round((stats.done / stats.total) * 100) : 0
            const color = BAR_COLORS[idx % BAR_COLORS.length]
            return (
              <button
                key={goal.id}
                onClick={() => navigate({ to: "/goals" })}
                className="w-full px-1 py-1 rounded hover:bg-[#f9f9f8] transition-colors text-left space-y-1"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[12px] text-[#37352f] truncate">{goal.description}</span>
                  <span className="text-[11px] text-[#9b9a97] shrink-0">
                    {pct}% · {stats.done}/{stats.total}
                  </span>
                </div>
                <div className="h-[3px] w-full bg-[#f4f2ef] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-300"
                    style={{ width: `${pct}%`, backgroundColor: color }}
                  />
                </div>
              </button>
            )
          })}
      </div>
    </div>
  )
}
