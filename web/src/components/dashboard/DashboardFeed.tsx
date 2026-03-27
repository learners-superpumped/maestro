import { ConductorSection } from "./ConductorSection"
import { RunningSection } from "./RunningSection"
import { RecentTasksSection } from "./RecentTasksSection"
import { SlackSection } from "./SlackSection"
import { useConductorConversations } from "@/hooks/queries/use-conductor-conversations"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"

export function DashboardFeed() {
  const { data: convData, isLoading: convLoading } = useConductorConversations()
  const { data: runningData, isLoading: runningLoading } = useQuery({
    queryKey: ["tasks", { status: "running" }],
    queryFn: () => api.tasks.list({ status: "running" }),
    refetchInterval: 10_000,
  })
  const { data: allTasksData, isLoading: tasksLoading } = useQuery({
    queryKey: ["tasks", undefined],
    queryFn: () => api.tasks.list(),
    refetchInterval: 30_000,
  })

  const conversations = convData?.conversations ?? []
  const runningTasks = runningData?.tasks ?? runningData ?? []
  const allTasks: any[] = allTasksData?.tasks ?? allTasksData ?? []

  return (
    <div className="flex-1 min-w-0 space-y-5">
      <ConductorSection conversations={conversations} loading={convLoading} />
      <div className="border-t border-[#f4f2ef]" />
      <RunningSection tasks={Array.isArray(runningTasks) ? runningTasks : []} loading={runningLoading} />
      <div className="border-t border-[#f4f2ef]" />
      <RecentTasksSection tasks={Array.isArray(allTasks) ? allTasks : []} loading={tasksLoading} />
      <SlackSection tasks={Array.isArray(allTasks) ? allTasks : []} loading={tasksLoading} />
    </div>
  )
}
