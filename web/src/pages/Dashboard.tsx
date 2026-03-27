import { DashboardFeed } from "@/components/dashboard/DashboardFeed"
import { DashboardSidebar } from "@/components/dashboard/DashboardSidebar"

export function Dashboard() {
  return (
    <div className="flex gap-6 h-full min-h-0">
      <DashboardFeed />
      <DashboardSidebar />
    </div>
  )
}
