import { ApprovalsWidget } from "./ApprovalsWidget"
import { GoalsWidget } from "./GoalsWidget"
import { SpendChart } from "./SpendChart"
import { SchedulesWidget } from "./SchedulesWidget"
import { AssetsWidget } from "./AssetsWidget"
import { useApprovals } from "@/hooks/queries/use-approvals"
import { useStats } from "@/hooks/queries/use-stats"
import { useDriveStatus } from "@/hooks/queries/use-drive"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"

export function DashboardSidebar() {
  const { data: driveStatus } = useDriveStatus()
  const { data: approvalsData, isLoading: approvalsLoading } = useApprovals()
  const { data: goalsData, isLoading: goalsLoading } = useQuery({
    queryKey: ["goals"],
    queryFn: () => api.goals.list(),
    refetchInterval: 30_000,
  })
  const { data: statsData } = useStats()
  const { data: schedulesData, isLoading: schedulesLoading } = useQuery({
    queryKey: ["schedules"],
    queryFn: () => api.schedules.list(),
    refetchInterval: 60_000,
  })
  const { data: assetsData, isLoading: assetsLoading } = useQuery({
    queryKey: ["assets", undefined],
    queryFn: () => api.assets.list(),
    refetchInterval: 60_000,
  })
  const { data: allTasksData } = useQuery({
    queryKey: ["tasks", undefined],
    queryFn: () => api.tasks.list(),
    refetchInterval: 30_000,
  })

  const approvals = approvalsData?.approvals ?? []
  const goals = goalsData?.goals ?? []
  const schedules = schedulesData?.schedules ?? schedulesData ?? []
  const assets: any[] = assetsData?.assets ?? assetsData ?? []
  const allTasks: any[] = allTasksData?.tasks ?? allTasksData ?? []

  // Build goal task stats from allTasks
  const tasksByGoalId: Record<string, { total: number; done: number }> = {}
  for (const t of allTasks) {
    if (!t.goal_id) continue
    if (!tasksByGoalId[t.goal_id]) tasksByGoalId[t.goal_id] = { total: 0, done: 0 }
    tasksByGoalId[t.goal_id].total++
    if (t.status === "completed") tasksByGoalId[t.goal_id].done++
  }

  const weekSpend: number[] = statsData?.week_spend_by_day ?? [0, 0, 0, 0, 0, 0, 0]
  const todaySpend: number = statsData?.today_spend_usd ?? 0

  const driveConnected = driveStatus?.connected ?? false

  return (
    <div className="w-[256px] shrink-0 border-l border-[#e8e5df] pl-5 space-y-5 overflow-y-auto">
      <ApprovalsWidget approvals={approvals} loading={approvalsLoading} />
      <div className="border-t border-[#e8e5df]" />
      <GoalsWidget goals={goals} tasksByGoalId={tasksByGoalId} loading={goalsLoading} />
      <div className="border-t border-[#e8e5df]" />
      <SpendChart weekSpend={weekSpend} todaySpend={todaySpend} />
      <div className="border-t border-[#e8e5df]" />
      <SchedulesWidget schedules={Array.isArray(schedules) ? schedules : []} loading={schedulesLoading} />
      <div className="border-t border-[#e8e5df]" />
      <AssetsWidget assets={assets} driveConnected={driveConnected} loading={assetsLoading} />
    </div>
  )
}
