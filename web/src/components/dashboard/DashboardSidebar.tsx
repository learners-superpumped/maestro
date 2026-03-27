import { ApprovalsWidget } from "./ApprovalsWidget"
import { GoalsWidget } from "./GoalsWidget"
import { SpendChart } from "./SpendChart"
import { SchedulesWidget } from "./SchedulesWidget"
import { AssetsWidget } from "./AssetsWidget"
import { useApprovals } from "@/hooks/queries/use-approvals"
import { useGoals } from "@/hooks/queries/use-goals"
import { useStats } from "@/hooks/queries/use-stats"
import { useSchedules } from "@/hooks/queries/use-schedules"
import { useAssets } from "@/hooks/queries/use-assets"
import { useTasks } from "@/hooks/queries/use-tasks"

export function DashboardSidebar() {
  const { data: approvalsData, isLoading: approvalsLoading } = useApprovals()
  const { data: goalsData, isLoading: goalsLoading } = useGoals()
  const { data: statsData } = useStats()
  const { data: schedulesData, isLoading: schedulesLoading } = useSchedules()
  const { data: assetsData, isLoading: assetsLoading } = useAssets()
  const { data: allTasksData } = useTasks()

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

  // Check if Drive is connected (any asset present implies connection)
  const driveConnected = assets.length > 0

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
