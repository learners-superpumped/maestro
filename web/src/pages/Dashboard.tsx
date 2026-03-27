import { useStats } from "@/hooks/queries/use-stats"
import { DashboardKpiRow } from "@/components/dashboard/DashboardKpiRow"
import { DashboardFeed } from "@/components/dashboard/DashboardFeed"
import { DashboardSidebar } from "@/components/dashboard/DashboardSidebar"

export function Dashboard() {
  const { data: stats, isLoading } = useStats()

  return (
    <div className="flex flex-col gap-4 h-full">
      <DashboardKpiRow stats={stats} loading={isLoading} />

      <div className="flex gap-6 flex-1 min-h-0">
        <DashboardFeed />
        <DashboardSidebar />
      </div>
    </div>
  )
}
