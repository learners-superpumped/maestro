import { useStats } from "@/hooks/queries/use-stats"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Activity, CheckCircle2, DollarSign, ListTodo, AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"

interface StatCardProps {
  title: string
  value: string | number | undefined
  icon: React.ElementType
  iconColor: string
  loading: boolean
}

function StatCard({ title, value, icon: Icon, iconColor, loading }: StatCardProps) {
  return (
    <Card className="bg-gray-900 border-gray-800">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-gray-400">{title}</CardTitle>
        <Icon className={cn("h-4 w-4", iconColor)} />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-24 bg-gray-800" />
        ) : (
          <div className="text-2xl font-bold text-gray-50">
            {value ?? "—"}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function Dashboard() {
  const { data, isLoading } = useStats()

  const todaySpend =
    data?.today_spend_usd != null
      ? `$${Number(data.today_spend_usd).toFixed(4)}`
      : "—"

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-50">Dashboard</h1>
        <p className="text-sm text-gray-400 mt-1">
          Overview of your Maestro workspace
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Running Tasks"
          value={data?.running}
          icon={Activity}
          iconColor="text-blue-500"
          loading={isLoading}
        />
        <StatCard
          title="Pending Approvals"
          value={data?.pending_approvals}
          icon={AlertTriangle}
          iconColor="text-amber-500"
          loading={isLoading}
        />
        <StatCard
          title="Today's Spend"
          value={todaySpend}
          icon={DollarSign}
          iconColor="text-green-500"
          loading={isLoading}
        />
        <StatCard
          title="Total Tasks"
          value={data?.total_tasks}
          icon={ListTodo}
          iconColor="text-indigo-500"
          loading={isLoading}
        />
      </div>

      {/* Status breakdown */}
      {(isLoading || data?.status_counts) && (
        <Card className="bg-gray-900 border-gray-800">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-gray-400 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              Status Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-5 w-full bg-gray-800" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {Object.entries(data?.status_counts ?? {}).map(
                  ([status, count]) => (
                    <div
                      key={status}
                      className="flex items-center justify-between px-3 py-2 bg-gray-800 rounded-md"
                    >
                      <span className="text-xs text-gray-400 capitalize">
                        {status.replace("_", " ")}
                      </span>
                      <span className="text-sm font-semibold text-gray-50">
                        {count as number}
                      </span>
                    </div>
                  )
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Date */}
      {data?.date && (
        <p className="text-xs text-gray-500">
          Stats as of {data.date}
        </p>
      )}
    </div>
  )
}
